# sense_api
Sense Energy Monitor API Interface [WIP]

Systematic access to the Sense monitor data. Exploratory work on pulling data from Sense
to be used in other tools - Smartthings, ActiveTiles, etc. 

Python version based on the work done here in Powershell:
https://gist.github.com/mbrownnycnyc/db3209a1045746f5e287ea6b6631e19c


### Todo

- Add POST/PUT where/if applicable
- CLI
- Improved error handling
- 

### Install

Python 2.7 with the following dependencies
```
pip install requests
pip install websocket-client
```

### Example Usage:
```
(.venv_1)  ~/code/sense   stable > python sense_api.py
Please enter you Sense username (email address): blah@blah.com
Please enter your Sense password:
Active: 2846.24267578 W
Active Solar: No Solar Found W
Active Devices: Other, Always On, Fridge
```

There are plenty of methods for you to call so modify however you see fit

```
>> sense = s('your_username_here', 'your_password_here')

>>> dir(sense)
['__doc__', '__init__', '__module__', '_realtime', 'active_devices', 'active_power', 'active_solar_power', 'always_on_info', 'devices', 'get_all_usage_data', 'get_device_info', 'get_discovered_device_data', 'get_discovered_device_names', 'get_monitor_info', 'get_notification_preferences', 'get_realtime', 'headers', 's', 'sense_access_token', 'sense_monitor_id', 'sense_user_id']

>>> sense.active_power
2734.8173828125

>>> sense.sense_monitor_id
24752

>>> pprint.pprint(sense.get_monitor_info())
{u'device_detection': {u'found': [],
                       u'in_progress': [{u'icon': u'washer',
                                         u'name': u'Possible Dryer',
                                         u'progress': 8},
                                        {u'icon': u'stove',
                                         u'name': u'Possible Stove',
                                         u'progress': 5},
                                        {u'icon': u'heater',
                                         u'name': u'Possible Water heater',
                                         u'progress': 12}],
                       u'num_detected': 2},
 u'monitor_info': {u'mac': u'xxxxxxx',
                   u'ndt_enabled': True,
                   u'online': True,
                   u'serial': u'xxxxxxx',
                   u'signal': u'-33 dBm',
                   u'ssid': u'11',
                   u'version': u'1.8.1661-bc40c79-master'},
 u'signals': {u'progress': 100, u'status': u'OK'}}
