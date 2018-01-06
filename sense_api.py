import json
import requests
import sys
import pprint
import getpass


def build_sense_api_session():
	username = raw_input("Please enter you Sense username (email address): ")
	password = getpass.getpass("Please enter your Sense password: ")

	auth_data = {
		"email": username,
		"password": password
	}
	# Create session
	session = requests.session()

	# Get auth token
	foo = session.post('https://api.sense.com/apiservice/api/v1/authenticate', auth_data)
	# check for 200 return
	if foo.status_code != 200:
		print "Please check username and password. Returned: %s" % foo.status_code
		sys.exit(1)

	# Build out some common variables
	sense_auth_token 	= foo.json()['access_token']
	sense_user_id 		= foo.json()['user_id']
	sense_monitor_id 	= foo.json()['monitors'][0]['id'] 

	# create the auth header
	headers = {'Authorization': 'bearer {}'.format(sense_auth_token)}

	return (session, headers, sense_user_id, sense_monitor_id)


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


def get_discovered_device_names():
	# lots more info in here to be parsed out
	response = s.get('https://api.sense.com/apiservice/api/v1/app/monitors/%s/devices' % sense_monitor_id, headers=headers)
	devices = [entry['name'] for entry in response.json()]
	return devices


def discovered_device_data():
	response = s.get('https://api.sense.com/apiservice/api/v1/app/monitors/%s/devices' % sense_monitor_id, headers=headers)
	return response.json()


def always_on_info():
	# Always on info - pretty generic similar to the web page
	response = s.get('https://api.sense.com/apiservice/api/v1/app/monitors/%s/devices/always_on' % sense_monitor_id, headers=headers)
	return response.json()


def get_monitor_info():
	# View info on your monitor & device detection status
	response = s.get('https://api.sense.com/apiservice/api/v1/app/monitors/%s/status' % sense_monitor_id, headers=headers)
	return response.json()


def get_device_info(device_id):
	# Get specific informaton about a device
	response = s.get('https://api.sense.com/apiservice/api/v1/app/monitors/%s/devices/%s' % (sense_monitor_id, device_id), headers=headers)
	return response.json()


def get_notification_preferences():
	# Get notification preferences
	payload = {'monitor_id': '%s' % sense_monitor_id}
	response = s.get('https://api.sense.com/apiservice/api/v1/users/%s/notifications' % sense_user_id, headers=headers, data=payload)
	return response.json()


def get_daily_kWh():
	payload = {'n_items': 30}
	response = s.get('https://api.sense.com/apiservice/api/v1/users/%s/timeline' % sense_user_id, headers=headers, data=payload)
	return response.json()['items'][1]['body']


def get_all_usage_data():
	payload = {'n_items': 30}
	# lots of info in here to be parsed out
	response = s.get('https://api.sense.com/apiservice/api/v1/users/%s/timeline' % sense_user_id, headers=headers, data=payload)
	return response.json()


def main():

	boo = get_daily_kWh()
	pprint.pprint(boo)

if __name__ == "__main__":
	s, headers, sense_user_id, sense_monitor_id = build_sense_api_session()
	main()

