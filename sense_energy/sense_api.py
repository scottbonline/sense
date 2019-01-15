import json
import requests
import sys
from time import time
from datetime import datetime
from requests.exceptions import ReadTimeout

from .sense_exceptions import *
from . import ws_sync
if sys.version_info < (3, 6):
    from . import ws_sync as websocket
else:
    from . import ws_async as websocket

API_URL = 'https://api.sense.com/apiservice/api/v1/'
WS_URL = "wss://clientrt.sense.com/monitors/%s/realtimefeed?access_token=%s"
API_TIMEOUT = 5
WSS_TIMEOUT = 5
RATE_LIMIT = 30

# for the last hour, day, week, month, or year
valid_scales = ['HOUR', 'DAY', 'WEEK', 'MONTH', 'YEAR']


class Senseable(object):

    def __init__(self, username=None, password=None,
                 api_timeout=API_TIMEOUT, wss_timeout=WSS_TIMEOUT):

        # Timeout instance variables
        self.api_timeout = api_timeout
        self.wss_timeout = wss_timeout
        
        self._realtime = {}
        self._devices = []
        self._trend_data = {}        
        for scale in valid_scales: self._trend_data[scale] = {}

        if username and password:
            self.authenticate(username, password)

    def authenticate(self, username, password):
        auth_data = {
            "email": username,
            "password": password
        }

        # Create session
        self.s = requests.session()

        # Get auth token
        try:
            response = self.s.post(API_URL+'authenticate',
                                   auth_data, timeout=self.api_timeout)
        except Exception as e:
            raise Exception('Connection failure: %s' % e)

        # check for 200 return
        if response.status_code != 200:
            raise SenseAuthenticationException(
                "Please check username and password. API Return Code: %s" %
                response.status_code)

        # Build out some common variables
        self.sense_access_token = response.json()['access_token']
        self.sense_user_id = response.json()['user_id']
        self.sense_monitor_id = response.json()['monitors'][0]['id']

        # create the auth header
        self.headers = {'Authorization': 'bearer {}'.format(
            self.sense_access_token)}

    @property
    def devices(self):
        """Return devices."""
        return self._devices

    def get_realtime(self):
        # rate limit API calls
        if self._realtime and self.rate_limit and \
           self.last_realtime_call + self.rate_limit > time():
            return self._realtime
        url = WS_URL % (self.sense_monitor_id, self.sense_access_token)
        self._realtime = websocket.get_realtime(url, self.wss_timeout)
        self.last_realtime_call = time()
        return self._realtime
    
    def get_realtime_stream(self):
        """ Reads realtime data from websocket
            Continues until loop broken"""
        url = WS_URL % (self.sense_monitor_id, self.sense_access_token)
        stream = ws_sync.get_realtime_stream(url, self.wss_timeout)
        while True:
            self._realtime = next(stream)
            yield self._realtime
            
    def get_realtime_future(self, callback):
        """ Returns an async Future to parse realtime data with callback"""
        def cb(data):
            self._realtime = data
            callback(data)
        url = WS_URL % (self.sense_monitor_id, self.sense_access_token)
        return websocket.get_realtime_future(url, self.wss_timeout, cb)

    def api_call(self, url, payload={}):
        try:
            return self.s.get(API_URL + url,
                              headers=self.headers,
                              timeout=self.api_timeout,
                              data=payload)
        except ReadTimeout:
            raise SenseAPITimeoutException("API call timed out")        

    @property
    def active_power(self):
        if not self._realtime: self.get_realtime()
        return self._realtime.get('w', 0)

    @property
    def active_solar_power(self):
        if not self._realtime: self.get_realtime()
        return self._realtime.get('solar_w', 0)

    @property
    def active_voltage(self):
        if not self._realtime: self.get_realtime()
        return self._realtime.get('voltage', 0)
    
    @property
    def active_frequency(self):
        if not self._realtime: self.get_realtime()
        return self._realtime.get('hz', 0)
    
    @property
    def daily_usage(self):
        return self.get_trend('DAY', False)

    @property
    def daily_production(self):
        return self.get_trend('DAY', True)
    
    @property
    def weekly_usage(self):
        # Add today's usage
        return self.get_trend('WEEK', False)

    @property
    def weekly_production(self):
        # Add today's production
        return self.get_trend('WEEK', True)
    
    @property
    def monthly_usage(self):
        # Add today's usage
        return self.get_trend('MONTH', False)

    @property
    def monthly_production(self):
        # Add today's production
        return self.get_trend('MONTH', True)
    
    @property
    def yearly_usage(self):
        # Add this month's usage
        return self.get_trend('YEAR', False)

    @property
    def yeary_production(self):
        # Add this month's production
        return self.get_trend('YEAR', True)

    @property
    def active_devices(self):
        if not self._realtime: self.get_realtime()
        return [d['name'] for d in self._realtime.get('devices', {})]

    def get_trend(self, scale, is_production):
        key = "production" if is_production else "consumption"
        if not self._trend_data[scale]: self.get_trend_data(scale)         
        if key not in self._trend_data[scale]: return 0
        total = self._trend_data[scale][key].get('total', 0)
        if scale == 'WEEK' or scale == 'MONTH':
            return total + self.get_trend('DAY', is_production)
        if scale == 'YEAR':
            return total + self.get_trend('MONTH', is_production)
        return total

    def get_discovered_device_names(self):
        # lots more info in here to be parsed out
        response = self.api_call('app/monitors/%s/devices' %
                                 self.sense_monitor_id)
        self._devices = [entry['name'] for entry in response.json()]
        return self._devices

    def get_discovered_device_data(self):
        response = self.api_call('monitors/%s/devices' %
                                 self.sense_monitor_id)
        return response.json()

    def always_on_info(self):
        # Always on info - pretty generic similar to the web page
        response = self.api_call('app/monitors/%s/devices/always_on' %
                                 self.sense_monitor_id)
        return response.json()

    def get_monitor_info(self):
        # View info on your monitor & device detection status
        response = self.api_call('app/monitors/%s/status' %
                                 self.sense_monitor_id)
        return response.json()

    def get_device_info(self, device_id):
        # Get specific informaton about a device
        response = self.api_call('app/monitors/%s/devices/%s' %
                                 (self.sense_monitor_id, device_id))
        return response.json()

    def get_notification_preferences(self):
        # Get notification preferences
        payload = {'monitor_id': '%s' % self.sense_monitor_id}
        response = self.api_call('users/%s/notifications' %
                                 self.sense_user_id, payload)
        return response.json()
    
    def get_trend_data(self, scale):
        if scale.upper() not in valid_scales:
            raise Exception("%s not a valid scale" % scale)
        t = datetime.now().replace(hour=12)
        response = self.api_call(
            'app/history/trends?monitor_id=%s&scale=%s&start=%s' %
            (self.sense_monitor_id, scale, t.isoformat()))
        self._trend_data[scale] = response.json()

    def update_trend_data(self):
        for scale in valid_scales:
            self.get_trend_data(scale)

    def get_all_usage_data(self):
        payload = {'n_items': 30}
        # lots of info in here to be parsed out
        response = self.s.get('users/%s/timeline' %
                              self.sense_user_id, payload)
        return response.json()


if __name__ == "__main__":
    import pprint
    import getpass

    # collect authn data
    username = raw_input("Please enter you Sense username (email address): ")
    password = getpass.getpass("Please enter your Sense password: ")
    sense = Senseable(username, password)
    print ("Active:", sense.active_power, "W")
    print ("Active Solar:", sense.active_solar_power, "W")
    print ("Active Devices:", ", ".join(sense.active_devices))
    print ("Active Voltage:", sense.active_voltage, "V")
    print ("Active Frequency:", sense.active_frequency, "Hz")
