import json
import requests
from datetime import datetime
from websocket import create_connection

API_URL = 'https://api.sense.com/apiservice/api/v1/'
API_TIMEOUT = 1
WSS_TIMEOUT = 1

class Senseable(object):

    def __init__(self, username, password):
        auth_data = {
            "email": username,
            "password": password
        }

        # Create session
        self.s = requests.session()
        self._realtime = None
        self._devices = []

        # Get auth token
        try:
            response = self.s.post('https://api.sense.com/apiservice/api/v1/authenticate', auth_data, timeout=API_TIMEOUT)
        except Exception as e:
            raise Exception('Connection failure: %s' % e)

        # check for 200 return
        if response.status_code != 200:
            raise Exception("Please check username and password. API Return Code: %s" % response.status_code)

        # Build out some common variables
        self.sense_access_token = response.json()['access_token']
        self.sense_user_id = response.json()['user_id']
        self.sense_monitor_id = response.json()['monitors'][0]['id']

        # create the auth header
        self.headers = {'Authorization': 'bearer {}'.format(self.sense_access_token)}

    @property
    def devices(self):
        """Return devices."""
        return self._devices

    def get_realtime(self):
        ws = create_connection("wss://clientrt.sense.com/monitors/%s/realtimefeed?access_token=%s" %
                               (self.sense_monitor_id, self.sense_access_token),
                               timeout=WSS_TIMEOUT)

        while True:
            result = json.loads(ws.recv())
            if 'payload' in result and not 'features' in result['payload']:
                self._realtime = result['payload']
                return self._realtime

    @property
    def active_power(self):
        if not self._realtime: self.get_realtime()
        return self._realtime.get('w', 0)

    @property
    def active_solar_power(self):
        if not self._realtime: self.get_realtime()
        return self._realtime.get('solar_w', 0)

    @property
    def active_devices(self):
        if not self._realtime: self.get_realtime()
        return [d['name'] for d in self._realtime.get('devices', {})]

    def get_discovered_device_names(self):
        # lots more info in here to be parsed out
        response = self.s.get(API_URL + 'app/monitors/%s/devices' % self.sense_monitor_id, headers=self.headers)
        self._devices = [entry['name'] for entry in response.json()]
        return self._devices

    def get_discovered_device_data(self):
        response = self.s.get(API_URL + 'monitors/%s/devices' % self.sense_monitor_id, headers=self.headers)
        return response.json()

    def always_on_info(self):
        # Always on info - pretty generic similar to the web page
        response = self.s.get(API_URL + 'app/monitors/%s/devices/always_on' % self.sense_monitor_id,
                              headers=self.headers)
        return response.json()

    def get_monitor_info(self):
        # View info on your monitor & device detection status
        response = self.s.get(API_URL + 'app/monitors/%s/status' % self.sense_monitor_id, headers=self.headers)
        return response.json()

    def get_device_info(self, device_id):
        # Get specific informaton about a device
        response = self.s.get(API_URL + 'app/monitors/%s/devices/%s' % (self.sense_monitor_id, device_id),
                              headers=self.headers)
        return response.json()

    def get_notification_preferences(self):
        # Get notification preferences
        payload = {'monitor_id': '%s' % self.sense_monitor_id}
        response = self.s.get(API_URL + 'users/%s/notifications' % self.sense_user_id, headers=self.headers,
                              data=payload)
        return response.json()

    def get_daily_usage(self):
        response = self.s.get(API_URL + 'app/history/trends?monitor_id=%s&scale=DAY&start=%s' % (self.sense_monitor_id, datetime.now().isoformat()), headers=self.headers)
        data = response.json()
        if "consumption" not in data or "total" not in data['consumption']: return 0
        return data['consumption']['total']

    def get_all_usage_data(self):
        payload = {'n_items': 30}
        # lots of info in here to be parsed out
        response = self.s.get(API_URL + 'users/%s/timeline' % self.sense_user_id, headers=self.headers, data=payload)
        return response.json()


if __name__ == "__main__":
    import pprint
    import getpass

    # collect authn data
    username = input("Please enter you Sense username (email address): ")
    password = getpass.getpass("Please enter your Sense password: ")
    sense = Senseable(username, password)
    print ("Active:", sense.active_power, "W")
    print ("Active Solar:", sense.active_solar_power, "W")
    print ("Active Devices:", ", ".join(sense.active_devices))
