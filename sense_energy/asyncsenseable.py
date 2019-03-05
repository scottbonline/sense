import asyncio
import aiohttp
import json
import websockets

from .sense_api import *
from .sense_exceptions import *

class ASyncSenseable(SenseableBase):
    
    async def authenticate(self, username, password):
        auth_data = {
            "email": username,
            "password": password
        }

        # Get auth token
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(API_URL+'authenticate',
                                        data=auth_data) as resp:

                    # check for 200 return
                    if resp.status != 200:
                        raise SenseAuthenticationException(
                            "Please check username and password. API Return Code: %s" %
                            resp.status)

                    # Build out some common variables
                    self.set_auth_data(await resp.json())
        except Exception as e:
            raise Exception('Connection failure: %s' % e)
                
    # Update the realtime data for asyncio
    async def update_realtime(self):
        # rate limit API calls
        if self._realtime and self.rate_limit and \
           self.last_realtime_call + self.rate_limit > time():
            return self._realtime
        self.last_realtime_call = time()
        await self.async_realtime_stream(single=True)
    
    async def async_realtime_stream(self, callback=None, single=False):
        """ Reads realtime data from websocket"""
        url = WS_URL % (self.sense_monitor_id, self.sense_access_token)
        # hello, features, [updates,] data
        async with websockets.connect(url) as ws:
            while True:
                try:
                    message = await asyncio.wait_for(
                        ws.recv(), timeout=self.wss_timeout)
                except asyncio.TimeoutError:
                    raise SenseAPITimeoutException("API websocket timed out")
                
                result = json.loads(message)
                if result.get('type') == 'realtime_update':
                    data = result['payload']
                    self.set_realtime(data)
                    if callback: callback(data)
                    if single: return
            
    async def get_realtime_future(self, callback):
        """ Returns an async Future to parse realtime data with callback"""
        await self.async_realtime_stream(callback)
        
    async def api_call(self, url, payload={}):
        timeout = aiohttp.ClientTimeout(total=self.api_timeout)
        async with aiohttp.ClientSession() as session:
            async with session.get(API_URL + url,
                          headers=self.headers,
                          timeout=timeout,
                          data=payload) as resp:
                return await resp.json()
        # timed out
        raise SenseAPITimeoutException("API call timed out") 

    async def get_trend_data(self, scale):
        if scale.upper() not in valid_scales:
            raise Exception("%s not a valid scale" % scale)
        t = datetime.now().replace(hour=12)
        json = self.api_call(
            'app/history/trends?monitor_id=%s&scale=%s&start=%s' %
            (self.sense_monitor_id, scale, t.isoformat()))
        self._trend_data[scale] = await json

    async def update_trend_data(self):
        for scale in valid_scales:
            await self.get_trend_data(scale)

    async def get_discovered_device_names(self):
        # lots more info in here to be parsed out
        json = self.api_call('app/monitors/%s/devices' %
                                 self.sense_monitor_id)
        self._devices = await [entry['name'] for entry in json]
        return self._devices

    async def get_discovered_device_data(self):
        json = self.api_call('monitors/%s/devices' %
                             self.sense_monitor_id)
        return await json

