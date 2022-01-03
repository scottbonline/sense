import asyncio
import json
import ssl

import aiohttp
import websockets

from .sense_api import *
from .sense_exceptions import *


class ASyncSenseable(SenseableBase):
    def __init__(
        self,
        username=None,
        password=None,
        api_timeout=API_TIMEOUT,
        wss_timeout=WSS_TIMEOUT,
        client_session=None,
    ):
        """Init the ASyncSenseable object."""
        self._client_session = client_session or aiohttp.ClientSession()
        self.ssl_context = None

        super().__init__(
            username=username,
            password=password,
            api_timeout=api_timeout,
            wss_timeout=wss_timeout,
        )

    async def authenticate(self, username, password, ssl_verify=True, ssl_cafile=""):
        auth_data = {"email": username, "password": password}

        # Use custom ssl verification, if specified
        if not ssl_verify:
            self.ssl_context = ssl.create_default_context()
            self.ssl_context.check_hostname = False
            self.ssl_context.verify_mode = ssl.CERT_NONE
        elif ssl_cafile:
            self.ssl_context = ssl.create_default_context(cafile=ssl_cafile)
        else:
            self.ssl_context = ssl.create_default_context()

        # Get auth token
        try:
            async with self._client_session.post(
                API_URL + "authenticate", timeout=self.api_timeout, data=auth_data
            ) as resp:

                # check for 200 return
                if resp.status != 200:
                    raise SenseAuthenticationException(
                        "Please check username and password. API Return Code: %s"
                        % resp.status
                    )

                # Build out some common variables
                self.set_auth_data(await resp.json())
        except Exception as ex:
            raise SenseAPITimeoutException("Connection failure: %s" % ex) from ex

    # Update the realtime data for asyncio
    async def update_realtime(self):
        # rate limit API calls
        if (
            self._realtime
            and self.rate_limit
            and self.last_realtime_call + self.rate_limit > time()
        ):
            return self._realtime
        self.last_realtime_call = time()
        await self.async_realtime_stream(single=True)

    async def async_realtime_stream(self, callback=None, single=False):
        """ Reads realtime data from websocket"""
        url = WS_URL % (self.sense_monitor_id, self.sense_access_token)
        # hello, features, [updates,] data
        async with websockets.connect(url, ssl=self.ssl_context) as ws:
            while True:
                try:
                    message = await asyncio.wait_for(
                        ws.recv(), timeout=self.wss_timeout
                    )
                except asyncio.TimeoutError as ex:
                    raise SenseAPITimeoutException("API websocket timed out") from ex

                result = json.loads(message)
                if result.get("type") == "realtime_update":
                    data = result["payload"]
                    self.set_realtime(data)
                    if callback:
                        callback(data)
                    if single:
                        return
                elif result.get("type") == "error":
                    data = result["payload"]
                    raise SenseWebsocketException(data["error_reason"])

    async def get_realtime_future(self, callback):
        """ Returns an async Future to parse realtime data with callback"""
        await self.async_realtime_stream(callback)

    async def api_call(self, url, payload={}):
        timeout = aiohttp.ClientTimeout(total=self.api_timeout)
        try:
            async with self._client_session.get(
                API_URL + url, headers=self.headers, timeout=timeout, data=payload
            ) as resp:
                return await resp.json()
        except asyncio.TimeoutError as ex:
            # timed out
            raise SenseAPITimeoutException("API call timed out") from ex

    async def get_trend_data(self, scale, dt=None):
        if scale.upper() not in valid_scales:
            raise Exception("%s not a valid scale" % scale)
        if not dt:
            dt = datetime.now().replace(hour=12)
        json = self.api_call(
            "app/history/trends?monitor_id=%s&scale=%s&start=%s"
            % (self.sense_monitor_id, scale, dt.isoformat())
        )
        self._trend_data[scale] = await json

    async def update_trend_data(self, dt=None):
        for scale in valid_scales:
            await self.get_trend_data(scale, dt)

    async def get_discovered_device_names(self):
        # lots more info in here to be parsed out
        json = self.api_call("app/monitors/%s/devices" % self.sense_monitor_id)
        self._devices = await [entry["name"] for entry in json]
        return self._devices

    async def get_discovered_device_data(self):
        json = self.api_call("monitors/%s/devices" % self.sense_monitor_id)
        return await json
