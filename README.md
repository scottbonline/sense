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

### Example Usage:
```
(pyvienv)  ~/code/sense/sense_energy   stable ●  python sense_api.py
Please enter you Sense username (email address): 
Please enter your Sense password:
('Active:', 2917.29736328125, 'W')
('Active Solar:', 0, 'W')
('Active Devices:', u'Other, Always On')
```

There are plenty of methods for you to call so modify however you see fit

If using the API to log data, you should only create one instance of Senseable and 
then reuse that to get the updated stats.  Creating the instance authenticates 
with the Sense API which should only be once every 15-20 minutes at most.  
Calling the `update_trend_data()` function will update all the trend stats 
and `get_realtime()` will retrieve the latest real time stats. 

The get_realtime() is by default rate limited to one call per 30 seconds. This can
be modified by setting the Senseable object attribute `rate_limit` to a different value.
