# sense_api
Sense Energy Monitor API Interface [WIP]

Systematic access to the Sense monitor data. Exploratory work on pulling data from Sense
to be used in other tools - Smartthings, ActiveTiles, etc. 

Python version based on the work done here in Powershell:
https://gist.github.com/mbrownnycnyc/db3209a1045746f5e287ea6b6631e19c

Notes:

- Main focus on GET requests. POST/PUT still be worked on
- I figured out endpoints using Chrome developer tools while browsing the the Sense web page


Example Usage:
```
>> from sense_api import sensenable as s

>>> foo = s()

>>> dir(foo)
['__doc__', '__init__', '__module__', 'always_on_info', 'get_all_usage_data', 'get_daily_kWh', 'get_device_info', 'get_discovered_device_data', 'get_discovered_device_names', 'get_monitor_info', 'get_notification_preferences', 'get_usage', 'headers', 's', 'sense_monitor_id', 'sense_user_id']


>>> foo.get_daily_kWh()

u'Your average daily usage is 79.4 kWh.'

>>> foo.get_discovered_device_names()

[u'Gameroom Heat', u'Always On', u'Fridge', u'Other']

>>> pprint.pprint(foo.get_monitor_info())
{u'device_detection': {u'found': [{u'icon': u'fridge',
                                   u'name': u'Fridge',
                                   u'progress': 73}],
                       u'in_progress': [{u'icon': u'washer',
                                         u'name': u'Possible Dryer',
                                         u'progress': 8},
                                        {u'icon': u'stove',
                                         u'name': u'Possible Stove',
                                         u'progress': 5}],
                       u'num_detected': 2},
 u'monitor_info': {u'mac': u'xx.xx.xx.xx',
                   u'ndt_enabled': True,
                   u'online': True,
                   u'serial': u'xxxxxxx',
                   u'signal': u'-31 dBm',
                   u'ssid': u'xxxxx',
                   u'version': u'1.8.1661-bc40c79-master'},
 u'signals': {u'progress': 100, u'status': u'OK'}}
```
