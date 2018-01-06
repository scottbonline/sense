import json
import requests
import sys
import pprint
import getpass

# https://api.sense.com/apiservice/api/v1/authenticate
# https://api.sense.com/apiservice/api/v1/app/monitors/?/devices
# https://api.sense.com/apiservice/api/v1/app/monitors/?/devices/always_on
# https://api.sense.com/apiservice/api/v1/app/monitors/?/devices/unknown
# https://api.sense.com/apiservice/api/v1/app/monitors/?/devices/?
# https://api.sense.com/apiservice/api/v1/app/users/?/timeline?n_items=30
# https://api.sense.com/apiservice/api/v1/app/monitors/?/status


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

s, headers, sense_user_id, sense_monitor_id = build_sense_api_session()
print s
print headers
print sense_user_id
print sense_monitor_id



response = s.get('https://api.sense.com/apiservice/api/v1/app/monitors/%s/devices' % sense_monitor_id, headers=headers)
response = s.get('https://api.sense.com/apiservice/api/v1/app/monitors/%s/devices/always_on' % sense_monitor_id, headers=headers)

payload = {'n_items': 30}
response = s.get('https://api.sense.com/apiservice/api/v1/users/%s/timeline' % sense_user_id, headers=headers, data=payload)

# View info on your monitor
response = s.get('https://api.sense.com/apiservice/api/v1/app/monitors/%s/status' % sense_monitor_id, headers=headers)

# View notification preferences
payload = {'monitor_id': '%s' % sense_monitor_id}
response = s.get('https://api.sense.com/apiservice/api/v1/users/%s/notifications' % sense_user_id, headers=headers, data=payload)

pprint.pprint(response.json())



