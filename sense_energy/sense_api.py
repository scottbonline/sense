import uuid
from time import time
from datetime import datetime

from .sense_exceptions import *

API_URL = "https://api.sense.com/apiservice/api/v1/"
WS_URL = "wss://clientrt.sense.com/monitors/%s/realtimefeed?access_token=%s"
API_TIMEOUT = 5
WSS_TIMEOUT = 5
RATE_LIMIT = 60

# for the last day, week, month, or year
valid_scales = ["DAY", "WEEK", "MONTH", "YEAR"]


class SenseableBase(object):
    def __init__(
        self,
        username=None,
        password=None,
        api_timeout=API_TIMEOUT,
        wss_timeout=WSS_TIMEOUT,
        ssl_verify=True,
        ssl_cafile="",
        device_id=None,
    ):
        """Initialize SenseableBase object."""

        # Timeout instance variables
        self.api_timeout = api_timeout
        self.wss_timeout = wss_timeout
        self.rate_limit = RATE_LIMIT
        self.last_realtime_call = 0

        self._mfa_token = ""
        self._realtime = {}
        self._devices = []
        self._trend_data = {}
        self._monitor = {}
        for scale in valid_scales:
            self._trend_data[scale] = {}
        self.set_ssl_context(ssl_verify, ssl_cafile)
        if device_id:
            self.device_id = device_id
        else:
            self.device_id = str(uuid.uuid4()).replace("-", "")

        self.headers = {"x-sense-device-id": self.device_id}

        if username and password:
            self.authenticate(username, password)

    def load_auth(self, access_token, user_id, device_id, refresh_token):
        """Load the authentication data from a previous session."""
        self.device_id = device_id
        data = {
            "access_token": access_token,
            "user_id": user_id,
            "refresh_token": refresh_token,
        }
        self._set_auth_data(data)

    def set_monitor_id(self, monitor_id):
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

    @property
    def devices(self):
        """List of discovered device names."""
        return self._devices

    def _set_realtime(self, data):
        """Sets the realtime data structure."""
        self._realtime = data
        self.last_realtime_call = time()

    def get_realtime(self):
        """Return the raw realtime data structure."""
        return self._realtime

    @property
    def active_power(self):
        return self._realtime.get("w", 0)

    @property
    def active_solar_power(self):
        return self._realtime.get("solar_w", 0)

    @property
    def active_voltage(self):
        return self._realtime.get("voltage", [])

    @property
    def active_frequency(self):
        return self._realtime.get("hz", 0)

    @property
    def daily_usage(self):
        return self.get_trend("DAY", "consumption")

    @property
    def daily_production(self):
        return self.get_trend("DAY", "production")

    @property
    def daily_production_pct(self):
        return self.get_trend("DAY", "production_pct")

    @property
    def daily_net_production(self):
        return self.get_trend("DAY", "net_production")

    @property
    def daily_from_grid(self):
        return self.get_trend("DAY", "from_grid")

    @property
    def daily_to_grid(self):
        return self.get_trend("DAY", "to_grid")

    @property
    def daily_solar_powered(self):
        return self.get_trend("DAY", "solar_powered")

    @property
    def weekly_usage(self):
        return self.get_trend("WEEK", "consumption")

    @property
    def weekly_production(self):
        return self.get_trend("WEEK", "production")

    @property
    def weekly_production_pct(self):
        return self.get_trend("WEEK", "production_pct")

    @property
    def weekly_net_production(self):
        return self.get_trend("WEEK", "net_production")

    @property
    def weekly_from_grid(self):
        return self.get_trend("WEEK", "from_grid")

    @property
    def weekly_to_grid(self):
        return self.get_trend("WEEK", "to_grid")

    @property
    def weekly_solar_powered(self):
        return self.get_trend("WEEK", "solar_powered")

    @property
    def monthly_usage(self):
        return self.get_trend("MONTH", "consumption")

    @property
    def monthly_production(self):
        return self.get_trend("MONTH", "production")

    @property
    def monthly_production_pct(self):
        return self.get_trend("MONTH", "production_pct")

    @property
    def monthly_net_production(self):
        return self.get_trend("MONTH", "net_production")

    @property
    def monthly_from_grid(self):
        return self.get_trend("MONTH", "from_grid")

    @property
    def monthly_to_grid(self):
        return self.get_trend("MONTH", "to_grid")

    @property
    def monthly_solar_powered(self):
        return self.get_trend("MONTH", "solar_powered")

    @property
    def yearly_usage(self):
        return self.get_trend("YEAR", "consumption")

    @property
    def yearly_production(self):
        return self.get_trend("YEAR", "production")

    @property
    def yearly_production_pct(self):
        return self.get_trend("YEAR", "production_pct")

    @property
    def yearly_net_production(self):
        return self.get_trend("YEAR", "net_production")

    @property
    def yearly_from_grid(self):
        return self.get_trend("YEAR", "from_grid")

    @property
    def yearly_to_grid(self):
        return self.get_trend("YEAR", "to_grid")

    @property
    def yearly_solar_powered(self):
        return self.get_trend("YEAR", "solar_powered")

    @property
    def active_devices(self):
        return [d["name"] for d in self._realtime.get("devices", {})]

    @property
    def time_zone(self):
        return self._monitor.get("time_zone", "")

    def trend_start(self, scale):
        """Return start of trend last updated."""
        if "start" not in self._trend_data[scale]:
            return None
        start_iso = self._trend_data[scale]["start"].replace("Z", "+00:00")
        return datetime.strptime(start_iso, "%Y-%m-%dT%H:%M:%S.%f%z")

    def get_trend(self, scale, key):
        """Return trend data item from last update."""
        if isinstance(key, bool):
            key = "production" if key is True else "consumption"
        else:
            key = "consumption" if key == "usage" else key
        if key not in self._trend_data[scale]:
            return 0
        # Perform a check for a valid type
        if not isinstance(self._trend_data[scale][key], (dict, float, int)):
            return 0
        if isinstance(self._trend_data[scale][key], dict):
            total = self._trend_data[scale][key].get("total", 0)
        else:
            total = self._trend_data[scale][key]
        return total
