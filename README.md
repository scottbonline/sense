# sense_api
## Sense Energy Monitor API Interface
The Sense API provides access to the unofficial API for the Sense Energy Monitor.  Through the API,
one can retrieve both realtime and trend data including individual devices.

Systematic access to the Sense monitor data. Exploratory work on pulling data from Sense
to be used in other tools - HomeASsistant, Smartthings, ActiveTiles, etc. 

Python version based on the work done here in Powershell:
https://gist.github.com/mbrownnycnyc/db3209a1045746f5e287ea6b6631e19c

## Local Device Emulation
The SenseLink class emulates the energy monitoring functionality of TP-Link Kasa HS110 Smart Plugs
 and allows you to report "custom" power usage to your Sense Home Energy Monitor.  This requires 
enabling "TP-Link HS110/HS300 Smart Plug" in the Sense app.

Based off the work of https://github.com/cbpowell/SenseLink

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

### Web API Example Usage:
```python
    from sense_energy import Senseable
    sense = Senseable()
    sense.authenticate(username, password)
    sense.update_realtime()
    sense.update_trend_data()
    print ("Active:", sense.active_power, "W")
    print ("Active Solar:", sense.active_solar_power, "W")
    print ("Daily:", sense.daily_usage, "KWh")
    print ("Daily Solar:", sense.daily_production, "KWh")
    print ("Active Devices:",", ".join(sense.active_devices))
```

There are plenty of methods for you to call so modify however you see fit

If using the API to log data, you should only create one instance of Senseable and 
then reuse that to get the updated stats.  Creating the instance authenticates 
with the Sense API which should only be once every 15-20 minutes at most.  
Calling the `update_trend_data()` function will update all the trend stats 
and `get_realtime()` will retrieve the latest real time stats.

The get_realtime() is by default rate limited to one call per 30 seconds. This can
be modified by setting the Senseable object attribute `rate_limit` to a different value.

### Local emulation Example Usage:
```python
	async def test():
		import time
		def test_devices():
			devices = [PlugInstance("lamp1", start_time=time()-20, alias="Lamp", power=10), 
					   PlugInstance("fan1", start_time=time()-300, alias="Fan", power=140)]
			for d in devices:
				yield d
		sl = SenseLink(test_devices)
		await sl.start()
		try:
			await asyncio.sleep(180)  # Serve for 3 minutes
		finally:
			await sl.stop()

	if __name__ == "__main__":
		asyncio.run(test())
```