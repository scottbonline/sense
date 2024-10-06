from enum import Enum, auto
from datetime import datetime
from typing import Optional
import ciso8601
import uuid
from .sense_exceptions import *

API_URL = "https://api.sense.com/apiservice/api/v1/"
WS_URL = "wss://clientrt.sense.com/monitors/%s/realtimefeed?access_token=%s"
API_TIMEOUT = 5
WSS_TIMEOUT = 5
RATE_LIMIT = 60


class Scale(Enum):
    DAY = auto()
    WEEK = auto()
    MONTH = auto()
    YEAR = auto()
    CYCLE = auto()


class SenseDevice:
    def __init__(self, id):
        self.id = id
        self.name = ""
        self.icon = ""
        self.is_on = False
        self.power_w = 0.0
        self.daily_kwh = 0.0
        self.weekly_kwh = 0.0
        self.monthly_kwh = 0.0
        self.yearly_kwh = 0.0


class SenseableBase(object):
    def __init__(
        self,
        username: str = None,
        password: str = None,
        api_timeout: int = API_TIMEOUT,
        wss_timeout: int = WSS_TIMEOUT,
        ssl_verify: bool = True,
        ssl_cafile: str = "",
        device_id: str = None,
    ):
        """Initialize SenseableBase object."""

        # Timeout instance variables
        self.api_timeout = api_timeout
        self.wss_timeout = wss_timeout
        self.rate_limit = RATE_LIMIT
        self.last_realtime_call = 0

        self._mfa_token = ""
        self._realtime = {}
        self._devices: dict[str, SenseDevice] = {}
        self._trend_data: dict[Scale, dict] = {}
        self._monitor = {}
        for scale in Scale:
            self._trend_data[scale] = {}
        self.set_ssl_context(ssl_verify, ssl_cafile)
        if device_id:
            self.device_id = device_id
        else:
            self.device_id = str(uuid.uuid4()).replace("-", "")

        self.headers = {"x-sense-device-id": self.device_id}

        if username and password:
            self.authenticate(username, password)

    def load_auth(self, access_token: str, user_id: str, device_id: str, refresh_token: str):
        """Load the authentication data from a previous session."""
        self.device_id = device_id
        data = {
            "access_token": access_token,
            "user_id": user_id,
            "refresh_token": refresh_token,
        }
        self._set_auth_data(data)

    def set_monitor_id(self, monitor_id: str):
        self.sense_monitor_id = monitor_id

    def _set_auth_data(self, data):
        """Set the authentication data for the session."""
        self.sense_access_token = data["access_token"]
        self.sense_user_id = data["user_id"]
        self.refresh_token = data["refresh_token"]

        # create the auth header
        self.headers = {
            "x-sense-device-id": self.device_id,
            "Authorization": "bearer {}".format(self.sense_access_token),
        }

    def _update_device_trends(self, scale: Scale):
        if not self._trend_data[scale]["consumption"].get("devices"):
            return
        for d in self._trend_data[scale]["consumption"]["devices"]:
            id = d["id"]
            if id not in self._devices:
                self._devices[id] = SenseDevice(id)
                self._devices[id].icon = d["icon"]
            if not self._devices[id].name:
                self._devices[id].name = d["name"]
            if scale == Scale.DAY:
                self._devices[id].daily_kwh = d["total_kwh"]
            elif scale == Scale.WEEK:
                self._devices[id].weekly_kwh = d["total_kwh"]
            elif scale == Scale.MONTH:
                self._devices[id].monthly_kwh = d["total_kwh"]
            elif scale == Scale.YEAR:
                self._devices[id].yearly_kwh = d["total_kwh"]

    @property
    def devices(self) -> list[SenseDevice]:
        """List of discovered device names."""
        return self._devices.values()

    def _set_realtime(self, data):
        """Sets the realtime data structure."""
        json_devices = data.get("devices", {})
        if not json_devices:
            return
        self._realtime = data
        for dev in self._devices.values():
            dev.is_on = False
            dev.power_w = 0
        for d in json_devices:
            id = d["id"]
            if id not in self._devices:
                self._devices[id] = SenseDevice(id)
            self._devices[id].power_w = float(d["w"])
            self._devices[id].is_on = self._devices[id].power_w > 0

    def get_realtime(self):
        """Outdated. Return the raw realtime data structure.
        Access sense.devices instead."""
        return self._realtime

    @property
    def active_power(self) -> float:
        return self._realtime.get("w", 0)

    @property
    def active_solar_power(self) -> float:
        return self._realtime.get("solar_w", 0)

    @property
    def active_voltage(self) -> float:
        return self._realtime.get("voltage", [])

    @property
    def active_frequency(self) -> float:
        return self._realtime.get("hz", 0)

    @property
    def daily_usage(self) -> float:
        return self.get_stat(Scale.DAY, "consumption")

    @property
    def daily_production(self) -> float:
        return self.get_stat(Scale.DAY, "production")

    @property
    def daily_production_pct(self) -> float:
        return self.get_stat(Scale.DAY, "production_pct")

    @property
    def daily_net_production(self) -> float:
        return self.get_stat(Scale.DAY, "net_production")

    @property
    def daily_from_grid(self) -> float:
        return self.get_stat(Scale.DAY, "from_grid")

    @property
    def daily_to_grid(self) -> float:
        return self.get_stat(Scale.DAY, "to_grid")

    @property
    def daily_solar_powered(self) -> float:
        return self.get_stat(Scale.DAY, "solar_powered")

    @property
    def weekly_usage(self) -> float:
        return self.get_stat(Scale.WEEK, "consumption")

    @property
    def weekly_production(self) -> float:
        return self.get_stat(Scale.WEEK, "production")

    @property
    def weekly_production_pct(self) -> float:
        return self.get_stat(Scale.WEEK, "production_pct")

    @property
    def weekly_net_production(self) -> float:
        return self.get_stat(Scale.WEEK, "net_production")

    @property
    def weekly_from_grid(self) -> float:
        return self.get_stat(Scale.WEEK, "from_grid")

    @property
    def weekly_to_grid(self) -> float:
        return self.get_stat(Scale.WEEK, "to_grid")

    @property
    def weekly_solar_powered(self) -> float:
        return self.get_stat(Scale.WEEK, "solar_powered")

    @property
    def monthly_usage(self) -> float:
        return self.get_stat(Scale.MONTH, "consumption")

    @property
    def monthly_production(self) -> float:
        return self.get_stat(Scale.MONTH, "production")

    @property
    def monthly_production_pct(self) -> float:
        return self.get_stat(Scale.MONTH, "production_pct")

    @property
    def monthly_net_production(self) -> float:
        return self.get_stat(Scale.MONTH, "net_production")

    @property
    def monthly_from_grid(self) -> float:
        return self.get_stat(Scale.MONTH, "from_grid")

    @property
    def monthly_to_grid(self) -> float:
        return self.get_stat(Scale.MONTH, "to_grid")

    @property
    def monthly_solar_powered(self) -> float:
        return self.get_stat(Scale.MONTH, "solar_powered")

    @property
    def yearly_usage(self) -> float:
        return self.get_stat(Scale.YEAR, "consumption")

    @property
    def yearly_production(self) -> float:
        return self.get_stat(Scale.YEAR, "production")

    @property
    def yearly_production_pct(self) -> float:
        return self.get_stat(Scale.YEAR, "production_pct")

    @property
    def yearly_net_production(self) -> float:
        return self.get_stat(Scale.YEAR, "net_production")

    @property
    def yearly_from_grid(self) -> float:
        return self.get_stat(Scale.YEAR, "from_grid")

    @property
    def yearly_to_grid(self) -> float:
        return self.get_stat(Scale.YEAR, "to_grid")

    @property
    def yearly_solar_powered(self) -> float:
        return self.get_stat(Scale.YEAR, "solar_powered")

    @property
    def active_devices(self):
        return [d.name for d in self._devices.values() if d.is_on]

    @property
    def time_zone(self) -> str:
        return self._monitor.get("time_zone", "")

    def trend_start(self, scale: Scale) -> Optional[datetime]:
        """Return start of trend last updated."""
        if "start" not in self._trend_data[scale]:
            return None
        try:
            return ciso8601.parse_datetime(self._trend_data[scale]["start"])
        except ValueError:
            pass
        return None

    def get_stat(self, scale: Scale, key: str) -> float:
        if scale not in self._trend_data or key not in self._trend_data[scale]:
            return 0
        data = self._trend_data[scale][key]
        if not isinstance(data, (dict, float, int)):
            return 0
        if isinstance(data, dict):
            return data.get("total", 0)
        return data

    def get_trend(self, scale: str, key: any) -> float:
        """Return trend data item from last update."""
        if isinstance(key, bool):
            key = "production" if key is True else "consumption"
        else:
            key = "consumption" if key == "usage" else key
        return self.get_stat(Scale[scale], key)
