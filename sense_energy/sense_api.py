from enum import Enum, auto
from datetime import datetime, timedelta, timezone
from typing import Optional
import ciso8601
import uuid
from .sense_exceptions import *

API_URL = "https://api.sense.com/apiservice/api/v1/"
WS_URL = "wss://clientrt.sense.com/monitors/%s/realtimefeed?access_token=%s"
API_TIMEOUT = 5
WSS_TIMEOUT = 5
RATE_LIMIT = 60

MIN_VERSION_REALTIME_UPDATE_API = "1.64"
SW_VERSION_CHECK_INTERVAL = 86400 # 1 day


class Scale(Enum):
    DAY = auto()
    WEEK = auto()
    MONTH = auto()
    YEAR = auto()
    CYCLE = auto()
    # New members must be appended. Scale uses auto(), so inserting a member
    # ahead of an existing one renumbers it and breaks consumers that persisted
    # the integer values.
    HOUR = auto()


# The period scales fetched by update_trend_data(). Scale.HOUR is deliberately
# excluded: it describes a single clock hour and is only meaningful when the
# caller asks for a specific hour via get_trend_data().
TREND_SCALES = (Scale.DAY, Scale.WEEK, Scale.MONTH, Scale.YEAR, Scale.CYCLE)


class SenseDevice:
    def __init__(self, id):
        self.id = id
        self.name = ""
        self.icon = ""
        self.is_on = False
        self.power_w = 0.0
        self.energy_kwh = {}
        for scale in Scale:
            self.energy_kwh[scale] = 0.0


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
        self._trend_data_updated: dict[Scale, datetime] = {}
        self._monitor = {}
        for scale in Scale:
            self._trend_data[scale] = {}
            self._trend_data_updated[scale] = datetime(2000, 1, 1, tzinfo=timezone.utc)
        self.set_ssl_context(ssl_verify, ssl_cafile)
        if device_id:
            self.device_id = device_id
        else:
            self.device_id = str(uuid.uuid4()).replace("-", "")

        self.headers = {"x-sense-device-id": self.device_id}

        if username and password:
            self.authenticate(username, password)

        self._sw_version = ""

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

    @staticmethod
    def _transform_usage_response(usage_data: dict, solar_data: dict = None) -> dict:
        """Transform new API response format to legacy format."""
        legacy_format = {
            "start": usage_data.get("start"),
            "consumption": {
                "total": usage_data.get("consumption", {}).get("usage_total_kwh", 0),
                "devices": [
                    {
                        "id": d["id"],
                        "name": d["name"],
                        "icon": d["icon"],
                        "total_kwh": d.get("consumption", {}).get("usage_total_kwh", 0)
                    }
                    for d in usage_data.get("device_breakdown", [])
                ]
            }
        }
        
        if solar_data and "total" in solar_data:
            solar_total = solar_data["total"]
            legacy_format["from_grid"] = solar_total.get("from_grid_kwh")
            legacy_format["to_grid"] = solar_total.get("to_grid_kwh")
            legacy_format["production"] = {
                "total": solar_total.get("production_kwh", 0)
            }
            legacy_format["solar_powered"] = solar_total.get("solar_percentage")
            legacy_format["net_production"] = solar_total.get("net_kwh")
            
            consumption_total = legacy_format["consumption"]["total"]
            production_total = solar_total.get("production_kwh", 0)
            if consumption_total > 0:
                legacy_format["production_pct"] = round(production_total / consumption_total * 100)
            else:
                legacy_format["production_pct"] = 100 if production_total > 0 else 0
        else:
            legacy_format["from_grid"] = None
            legacy_format["to_grid"] = None
            legacy_format["production"] = {"total": 0}
            legacy_format["solar_powered"] = None
            legacy_format["net_production"] = None
            legacy_format["production_pct"] = None
        
        return legacy_format

    def _format_trend_start(self, dt: datetime) -> str:
        """Format a datetime for the API's `start` parameter, which reads as UTC.

        Naive datetimes are sent verbatim, since their intended zone is unknowable.
        """
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%S")

    @staticmethod
    def _at(values, index: int) -> float:
        """Return values[index], or 0.0 if it is missing or not a number."""
        if isinstance(values, list) and 0 <= index < len(values):
            if isinstance(values[index], (int, float)):
                return values[index]
        return 0.0

    @staticmethod
    def _rescale(value: float, derived_total: float, actual_total) -> float:
        """Scale a derived hourly value so the day's hours sum to actual_total."""
        if not value or not derived_total or actual_total is None:
            return value
        return value * (actual_total / derived_total)

    def _transform_hour_response(
        self, dt: datetime, usage_data: dict, solar_data: dict = None
    ) -> Optional[dict]:
        """Build one clock hour from a DAY response's per-hour breakdown arrays.

        The arrays hold one entry per clock hour of the monitor's local day and
        are sized by the API across DST (23 on spring-forward, 25 on fall-back),
        so the hour is found by counting whole hours from the response's own
        `start` rather than assuming 24. Returns None when the day fetched does
        not cover dt, leaving any previously stored hour alone.
        """
        try:
            day_start = ciso8601.parse_datetime(usage_data.get("start", ""))
        except (ValueError, TypeError):
            return None
        totals = usage_data.get("consumption", {}).get("usage_breakdown_kwh")
        if not isinstance(totals, list):
            return None
        index = int((dt - day_start).total_seconds() // 3600)
        if not 0 <= index < len(totals):
            return None

        consumption = self._at(totals, index)
        hour = {
            "start": (day_start + timedelta(hours=index)).isoformat(),
            "consumption": {"usage_total_kwh": consumption},
            "device_breakdown": [
                {
                    "id": d["id"],
                    "name": d["name"],
                    "icon": d["icon"],
                    "consumption": {
                        "usage_total_kwh": self._at(
                            d.get("consumption", {}).get("usage_breakdown_kwh"), index
                        )
                    },
                }
                for d in usage_data.get("device_breakdown", [])
            ],
        }

        breakdown = (solar_data or {}).get("breakdown")
        if not isinstance(breakdown, dict):
            return self._transform_usage_response(hour)

        # from_grid/to_grid have no hourly form, so derive them from the hourly
        # net and rescale to the exact daily totals the API does report.
        nets = breakdown.get("net_kwh")
        nets = nets if isinstance(nets, list) else []
        net = self._at(nets, index)
        production = self._at(breakdown.get("production_kwh"), index)
        day_total = solar_data.get("total", {})
        to_grid = self._rescale(
            max(0.0, net),
            sum(v for v in nets if isinstance(v, (int, float)) and v > 0),
            day_total.get("to_grid_kwh"),
        )
        from_grid = self._rescale(
            max(0.0, -net),
            sum(-v for v in nets if isinstance(v, (int, float)) and v < 0),
            day_total.get("from_grid_kwh"),
        )
        solar_to_home = min(max(0.0, production - to_grid), consumption)
        return self._transform_usage_response(
            hour,
            {
                "total": {
                    "from_grid_kwh": from_grid,
                    "to_grid_kwh": to_grid,
                    "production_kwh": production,
                    "net_kwh": net,
                    "solar_percentage": (
                        round(solar_to_home / consumption * 100) if consumption else 0
                    ),
                }
            },
        )

    def _update_device_trends(self, scale: Scale):
        consumption = self._trend_data[scale].get("consumption", {})
        if not consumption.get("devices"):
            return
        if scale != Scale.HOUR:
            if update := self.trend_update(scale):
                if update < self._trend_data_updated[scale]:
                    return
                self._trend_data_updated[scale] = update

        for d in self._devices.values():
            d.energy_kwh[scale] = 0
        for d in self._trend_data[scale]["consumption"]["devices"]:
            id = d["id"]
            if id not in self._devices:
                # try to match device name and combine with newer device
                for did in self._devices:
                    if self._devices[did].name == d["name"]:
                        id = did
                        break
                else:
                    self._devices[id] = SenseDevice(id)
                    self._devices[id].icon = d["icon"]
            if not self._devices[id].name:
                self._devices[id].name = d["name"]
            self._devices[id].energy_kwh[scale] += d["total_kwh"]

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
    def active_voltage(self) -> list[float]:
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

    @staticmethod
    def _auth_error_message(message: str, data) -> str:
        """Append the API's error_reason (if any) from a parsed response body to message."""
        if isinstance(data, dict) and data.get("error_reason"):
            return f"{message}, {data['error_reason']}"
        return message

    def trend_start(self, scale: Scale) -> Optional[datetime]:
        """Return start of trend last updated."""
        if "start" not in self._trend_data[scale]:
            return None
        try:
            return ciso8601.parse_datetime(self._trend_data[scale]["start"])
        except ValueError:
            pass
        return None

    def trend_update(self, scale: Scale) -> Optional[datetime]:
        """Return an update value of trend last updated."""

        update = self.trend_start(scale)
        if not update or scale not in self._trend_data:
            return None
        val = self._trend_data[scale]["from_grid"]
        if val is None:
            val = self._trend_data[scale]["consumption"]["total"]
        val /= 100.0
        seconds = int(val)
        microseconds = int((val % 1) * 1000000)
        return update + timedelta(seconds=seconds, microseconds=microseconds)

    def get_stat(self, scale: Scale, key: str) -> float:
        key = "consumption" if key == "usage" else key
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
