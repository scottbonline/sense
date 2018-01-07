import json
import requests
import sys
import pprint
import getpass


class sensenable():

    def __init__(self):
        # collect authn data
        username = raw_input("Please enter you Sense username (email address): ")
        password = getpass.getpass("Please enter your Sense password: ")
        # hardcode for easier testing
        #username = ''
        #password = ''
        auth_data = {
            "email": username,
            "password": password
        }

        # Create session
        self.s = requests.session()

        # Get auth token
        try:
            response = self.s.post('https://api.sense.com/apiservice/api/v1/authenticate', auth_data)
        except Exception as e:
            print 'Connection failure: %s' % e
            sys.exit(1)

        # check for 200 return
        if response.status_code != 200:
            raise Exception("Please check username and password. API Return Code: %s" % response.status_code)
            sys.exit(1)

        # Build out some common variables
        sense_auth_token         = response.json()['access_token']
        self.sense_user_id       = response.json()['user_id']
        self.sense_monitor_id    = response.json()['monitors'][0]['id'] 

        # create the auth header
        self.headers = {'Authorization': 'bearer {}'.format(sense_auth_token)}


    def get_usage(s, sense_monitor_id, start ,granularity): # NOT WORKING

        valid_granularity = [
            'second',
            'minute',
            'hour',
            'day',
            'week',
            'month',
            'year']

        # check for UTC format
        valid_start = "2018-01-01T00:00:00.000Z"

        valid_frames = 5400 #number of data samples you will retrive. the android client default is 5400

        payload = {
            'monitor_id': sense_monitor_id,
            'granularity': 'MINUTE',
            'start': valid_start,
            'frames': valid_frames
            }
        print payload
        #response = s.get('https://api.sense.com/apiservice/api/v1/app/history/usage?monitor_id=%s&granularity=$%s&start=%s&frames=%s' % (sense_monitor_id, 'MINUTE', valid_start, valid_frames), headers=headers)
        response = s.get('https://api.sense.com/apiservice/api/v1/app/history/usage', headers=headers, data=payload)
        return response


    def get_discovered_device_names(self):
        # lots more info in here to be parsed out
        response = self.s.get('https://api.sense.com/apiservice/api/v1/app/monitors/%s/devices' % self.sense_monitor_id, headers=self.headers)
        devices = [entry['name'] for entry in response.json()]
        return devices


    def get_discovered_device_data(self):
        response = self.s.get('https://api.sense.com/apiservice/api/v1/app/monitors/%s/devices' % self.sense_monitor_id, headers=self.headers)
        return response.json()


    def always_on_info(self):
        # Always on info - pretty generic similar to the web page
        response = self.s.get('https://api.sense.com/apiservice/api/v1/app/monitors/%s/devices/always_on' % self.sense_monitor_id, headers=self.headers)
        return response.json()


    def get_monitor_info(self):
        # View info on your monitor & device detection status
        response = self.s.get('https://api.sense.com/apiservice/api/v1/app/monitors/%s/status' % self.sense_monitor_id, headers=self.headers)
        return response.json()


    def get_device_info(self, device_id):
        # Get specific informaton about a device
        response = self.s.get('https://api.sense.com/apiservice/api/v1/app/monitors/%s/devices/%s' % (self.sense_monitor_id, self.device_id), headers=self.headers)
        return response.json()


    def get_notification_preferences(self):
        # Get notification preferences
        payload = {'monitor_id': '%s' % self.sense_monitor_id}
        response = self.s.get('https://api.sense.com/apiservice/api/v1/users/%s/notifications' % self.sense_user_id, headers=self.headers, data=payload)
        return response.json()


    def get_daily_kWh(self):
        payload = {'n_items': 30}
        response = self.s.get('https://api.sense.com/apiservice/api/v1/users/%s/timeline' % self.sense_user_id, headers=self.headers, data=payload)
        return response.json()['items'][1]['body']


    def get_all_usage_data(self):
        payload = {'n_items': 30}
        # lots of info in here to be parsed out
        response = self.s.get('https://api.sense.com/apiservice/api/v1/users/%s/timeline' % self.sense_user_id, headers=self.headers, data=payload)
        return response.json()



def main():
    #foo = sensenable()
    #pprint.pprint(foo.get_daily_kWh())
    pass


if __name__ == "__main__":
    main()

