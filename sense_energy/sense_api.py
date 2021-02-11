import json
import sys
from time import time
from datetime import datetime

from .sense_exceptions import *

API_URL = 'https://api.sense.com/apiservice/api/v1/'
WS_URL = "wss://clientrt.sense.com/monitors/%s/realtimefeed?access_token=%s"
API_TIMEOUT = 5
WSS_TIMEOUT = 5
RATE_LIMIT = 60

# for the last hour, day, week, month, or year
valid_scales = ['HOUR', 'DAY', 'WEEK', 'MONTH', 'YEAR']


class SenseableBase(object):

    def __init__(self, username=None, password=None,
                 api_timeout=API_TIMEOUT, wss_timeout=WSS_TIMEOUT):

        # Timeout instance variables
        self.api_timeout = api_timeout
        self.wss_timeout = wss_timeout
        self.rate_limit = RATE_LIMIT
        self.last_realtime_call = 0
        
        self._realtime = {}
        self._devices = []
        self._trend_data = {}        
        for scale in valid_scales: self._trend_data[scale] = {}

        if username and password:
            self.authenticate(username, password)

    def set_auth_data(self, data):
        self.sense_access_token = data['access_token']
        self.sense_user_id = data['user_id']
        self.sense_monitor_id = data['monitors'][0]['id']

        # create the auth header
        self.headers = {'Authorization': 'bearer {}'.format(
            self.sense_access_token)}
        

    @property
    def devices(self):
        """Return devices."""
        return self._devices
    
    def set_realtime(self, data):
        self._realtime = data
        self.last_realtime_call = time()
        
    def get_realtime(self):
        return self._realtime     

    @property
    def active_power(self):
        return self._realtime.get('w', 0)

    @property
    def active_solar_power(self):
        return self._realtime.get('solar_w', 0)

    @property
    def active_voltage(self):
        return self._realtime.get('voltage', [])
    
    @property
    def active_frequency(self):
        return self._realtime.get('hz', 0)
    
    @property
    def daily_usage(self):
        return self.get_trend('DAY', False)

    @property
    def daily_production(self):
        return self.get_trend('DAY', True)
    
    @property
    def weekly_usage(self):
        return self.get_trend('WEEK', False)

    @property
    def weekly_production(self):
        return self.get_trend('WEEK', True)
    
    @property
    def monthly_usage(self):
        return self.get_trend('MONTH', False)

    @property
    def monthly_production(self):
        return self.get_trend('MONTH', True)
    
    @property
    def yearly_usage(self):
        return self.get_trend('YEAR', False)

    @property
    def yearly_production(self):
        return self.get_trend('YEAR', True)

    @property
    def active_devices(self):
        return [d['name'] for d in self._realtime.get('devices', {})]

    def get_trend(self, scale, is_production):
        key = "production" if is_production else "consumption"       
        if key not in self._trend_data[scale]: return 0
        total = self._trend_data[scale][key].get('total', 0)
        if scale == 'WEEK' or scale == 'MONTH':
            return total + self.get_trend('DAY', is_production)
        if scale == 'YEAR':
            return total + self.get_trend('MONTH', is_production)
        return total
