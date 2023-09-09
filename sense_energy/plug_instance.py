# Copyright 2020, Charles Powell

import hashlib
from time import time
from typing import Optional, Dict, Any
from functools import lru_cache


@lru_cache(maxsize=256)
def _generate_mac(device_id: str) -> str:
    """Generate a MAC address from the device ID only once."""
    end = [int(device_id[i : i + 2], 16) for i in range(0, len(device_id), 2)]
    mac = [53, 75, 31] + end[:3]
    return ":".join("%02X" % b for b in mac)


@lru_cache(maxsize=256)
def _generate_device_id(id: str) -> str:
    """Generate a device ID from the ID only once."""
    return hashlib.sha1(id.encode("utf-8")).hexdigest().upper()


class PlugInstance:
    """Class to represent a single plug instance."""

    __slots__ = (
        "id",
        "voltage",
        "power",
        "current",
        "alias",
        "start_time",
        "device_id",
        "mac",
    )

    def __init__(
        self,
        id: str,
        start_time: Optional[float] = None,
        alias: Optional[str] = None,
        power=0.0,
        current=0.0,
        voltage=120.0,
        mac: Optional[str] = None,
        device_id: Optional[str] = None,
    ) -> None:
        """Initialize a plug instance."""
        self.id = id
        self.voltage = voltage
        self.power = power
        self.current = current
        if not self.power:
            self.power = self.voltage * self.current
        if not self.current:
            self.current = self.power / self.voltage
        self.alias = alias or id
        self.start_time = start_time or time() - 1
        if device_id:
            self.device_id = device_id.upper()
        else:
            self.device_id = _generate_device_id(id)
        if mac:
            self.mac = mac.upper()
        else:
            self.mac = _generate_mac(self.device_id)

    def generate_response(self) -> Dict[str, Dict[str, Any]]:
        """Generate a response dict for the plug."""
        # Response dict
        return {
            "emeter": {
                "get_realtime": {
                    "current": self.current,
                    "voltage": self.voltage,
                    "power": self.power,
                    "total": 0,  # Unsure if this needs a value, appears not to
                    "err_code": 0,  # No errors here!
                }
            },
            "system": {
                "get_sysinfo": {
                    "err_code": 0,
                    "sw_ver": "1.2.5 Build 171206 Rel.085954",
                    "hw_ver": "1.0",
                    "type": "IOT.SMARTPLUGSWITCH",
                    "model": "HS110(US)",
                    "mac": self.mac,
                    "deviceId": self.device_id,
                    "hwId": "60FF6B258734EA6880E186F8C96DDC61",
                    "fwId": "00000000000000000000000000000000",
                    "oemId": "FFF22CFF774A0B89F7624BFC6F50D5DE",
                    "alias": self.alias,
                    "dev_name": "Wi-Fi Smart Plug With Energy Monitoring",
                    "icon_hash": "",
                    "relay_state": 1 if self.power > 0 else 0,
                    "on_time": time() - self.start_time,
                    "active_mode": "none",
                    "feature": "TIM:ENE",
                    "updating": 0,
                    "rssi": -60,  # Great wifi signal
                    "led_off": 0,  # Probably not important
                    "latitude": 39.8283,  # Center of the US
                    "longitude": -98.5795,  # Center of the US
                }
            },
        }
