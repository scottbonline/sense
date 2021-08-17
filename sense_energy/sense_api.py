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
        return self.get_trend('DAY', 'consumption')

    @property
    def daily_production(self):
        return self.get_trend('DAY', 'production')

    @property
    def daily_production_pct(self):
        return self.get_trend('DAY', 'production_pct')

    @property
    def daily_net_production(self):
        return self.get_trend('DAY', 'net_production')

    @property
    def daily_from_grid(self):
        return self.get_trend('DAY', 'from_grid')

    @property
    def daily_to_grid(self):
        return self.get_trend('DAY', 'to_grid')

    @property
    def daily_solar_powered(self):
        return self.get_trend('DAY', 'solar_powered')

    @property
    def weekly_usage(self):
        return self.get_trend('WEEK', 'consumption')

    @property
    def weekly_production(self):
        return self.get_trend('WEEK', 'production')

    @property
    def weekly_production_pct(self):
        return self.get_trend('WEEK', 'production_pct')

    @property
    def weekly_net_production(self):
        return self.get_trend('WEEK', 'net_production')

    @property
    def weekly_from_grid(self):
        return self.get_trend('WEEK', 'from_grid')

    @property
    def weekly_to_grid(self):
        return self.get_trend('WEEK', 'to_grid')

    @property
    def weekly_solar_powered(self):
        return self.get_trend('WEEK', 'solar_powered')

    @property
    def monthly_usage(self):
        return self.get_trend('MONTH', 'consumption')

    @property
    def monthly_production(self):
        return self.get_trend('MONTH', 'production')

    @property
    def monthly_production_pct(self):
        return self.get_trend('MONTH', 'production_pct')

    @property
    def monthly_net_production(self):
        return self.get_trend('MONTH', 'net_production')

    @property
    def monthly_from_grid(self):
        return self.get_trend('MONTH', 'from_grid')

    @property
    def monthly_to_grid(self):
        return self.get_trend('MONTH', 'to_grid')

    @property
    def monthly_solar_powered(self):
        return self.get_trend('MONTH', 'solar_powered')

    @property
    def yearly_usage(self):
        return self.get_trend('YEAR', 'consumption')

    @property
    def yearly_production(self):
        return self.get_trend('YEAR', 'production')

    @property
    def yearly_production_pct(self):
        return self.get_trend('YEAR', 'production_pct')

    @property
    def yearly_net_production(self):
        return self.get_trend('YEAR', 'net_production')

    @property
    def yearly_from_grid(self):
        return self.get_trend('YEAR', 'from_grid')

    @property
    def yearly_to_grid(self):
        return self.get_trend('YEAR', 'to_grid')

    @property
    def yearly_solar_powered(self):
        return self.get_trend('YEAR', 'solar_powered')

    @property
    def active_devices(self):
        return [d['name'] for d in self._realtime.get('devices', {})]

    def get_trend(self, scale, key):
        if isinstance(key, bool):
            key = 'production' if key is True else 'consumption'
        else:
            key = 'consumption' if key == 'usage' else key
        if key not in self._trend_data[scale]: return 0
        # Perform a check for a valid type
        if not isinstance(self._trend_data[scale][key], (dict, float, int)): return 0
        if isinstance(self._trend_data[scale][key], dict):
            total = self._trend_data[scale][key].get('total', 0)
        else:
            total = self._trend_data[scale][key]
        return total
