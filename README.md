# sense_api
Sense Energy Monitor API Interface [WIP]

Systematic access to the Sense monitor data. Exploratory work on pulling data from Sense
to be used in other tools - Smartthings, ActiveTiles, etc. 

Python version based on the work done here in Powershell:
https://gist.github.com/mbrownnycnyc/db3209a1045746f5e287ea6b6631e19c

### Contributors

Feel free to fork and PR! 

https://github.com/kbickar

### Todo

- Add POST/PUT where/if applicable
- CLI
- Improved error handling


### Install

```
pip install sense_energy
```

### Example Usage
```python
    sense = Senseable()
    sense.authenticate(username, password)
    sense.update_realtime()
    sense.update_trend_data()
    print ("Active:",sense.active_power,"W")
    print ("Active Solar:",sense.active_solar_power,"W")
    print ("Daily:",sense.daily_usage,"KW")
    print ("Daily Solar:",sense.daily_production,"KW")
    print ("Active Devices:",", ".join(sense.active_devices))
```

If using the API to log data, you should only create one instance of Senseable and 
then reuse that to get the updated stats.  Creating the instance authenticates 
with the Sense API which should only be once every 15-20 minutes at most.  
Calling the `update_trend_data()` function will update all the trend stats 
and `get_realtime()` will retrieve the latest real time stats. 

The get_realtime() is by default rate limited to one call per 30 seconds. This can
be modified by setting the Senseable object attribute `rate_limit` to a different value.

### Methods

There are two types of API calls made by the library. Those to get the realtime data, and those to get trend/device/usage/historic data:

Method | Description
-- | --
`always_on_info()` | Always on info - pretty generic similar to the web page.
`authenticate(username, password)` | -
`get_all_usage_data()` | Returns the last 30 usage events like devices being turned on for X minutes.
`get_device_info(device_id)` | Get specific informaton about a device.
`get_discovered_device_data()` | Returns a list of the discovered devices including all the data available on the API (name, type, powered on, etc).
`get_discovered_device_names()` | Returns a list of the names of devices discovered.
`get_monitor_info()` | View info on your monitor & device detection status.
`get_realtime_stream()` | Reads realtime data from websocket. Continues until loop broken.
`get_trend_data(scale)` | Fetches the trend data for a scale of time (e.g. day, month, year). It's mostly used when called by `update_trend_data()` which will get the trend data for all of the scales.
`update_realtime()` | Update the realtime data.
