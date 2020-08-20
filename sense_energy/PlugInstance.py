# Copyright 2020, Charles Powell

import hashlib
from time import time

class PlugInstance:

    def __init__(self, alias, start_time, power=0, current = 0, voltage=120, mac=None, device_id=None):      
        self.alias = alias
        self.start_time = start_time
        
        self.voltage = voltage
        self.power = power
        self.current = current
        
        if not self.power:
            self.power = self.voltage*self.current
        if not self.current:
            self.current = self.power/self.voltage

        if device_id: self.device_id = device_id
        else: self.device_id = self.generate_deviceid()
        
        if mac: self.mac = mac
        else: self.mac = self.generate_mac()

    def generate_mac(self):
        end = [int(self.device_id[i:i+2],16) for i in range(0, len(self.device_id), 2)]
        mac = [53, 75, 31] + end[:3]
        return ':'.join('%02x' % b for b in mac)

    def generate_deviceid(self):
        return hashlib.sha1(self.alias.encode('utf-8')).hexdigest()

    def generate_response(self):
        # Response dict
        response = {
            "emeter": {
                "get_realtime": {
                    "current": self.current,
                    "voltage": self.voltage,
                    "power": self.power,
                    "total": 0,     # Unsure if this needs a value, appears not to
                    "err_code": 0   # No errors here!
                }
            },
            "system": {
                "get_sysinfo": {
                    "err_code": 0,
                    "sw_ver": "1.2.5 Build 171206 Rel.085954",
                    "hw_ver": "1.0",
                    "type": "IOT.SMARTPLUGSWITCH",
                    "model": "HS110(US)",
                    "mac": self.mac.upper(),
                    "deviceId": self.device_id.upper(),
                    "hwId": "60FF6B258734EA6880E186F8C96DDC61",
                    "fwId": "00000000000000000000000000000000",
                    "oemId": "FFF22CFF774A0B89F7624BFC6F50D5DE",
                    "alias": self.alias,
                    "dev_name": "Wi-Fi Smart Plug With Energy Monitoring",
                    "icon_hash": "",
                    "relay_state": 1,  # Assuming it's on, not sure it matters
                    "on_time": time() - self.start_time,
                    "active_mode": "none",
                    "feature": "TIM:ENE",
                    "updating": 0,
                    "rssi": -60,    # Great wifi signal
                    "led_off": 0,   # Probably not important
                    "latitude": 39.8283,    # Center of the US
                    "longitude": -98.5795   # Center of the US
                }
            }
        }
        return response
 