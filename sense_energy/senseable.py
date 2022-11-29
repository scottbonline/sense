import json
import requests
import ssl
from requests.exceptions import ReadTimeout
from websocket import create_connection
from websocket._exceptions import WebSocketTimeoutException

from .sense_api import *
from .sense_exceptions import *


class Senseable(SenseableBase):
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
        """Init the Senseable object."""

        # Create session
        self.s = requests.session()
        self.set_ssl_context(ssl_verify, ssl_cafile)

        SenseableBase.__init__(
            self,
            username=username,
            password=password,
            api_timeout=api_timeout,
            wss_timeout=wss_timeout,
            ssl_verify=ssl_verify,
            ssl_cafile=ssl_cafile,
            device_id=device_id,
        )

    def set_ssl_context(self, ssl_verify, ssl_cafile):
        """Create or set the SSL context. Use custom ssl verification, if specified."""
        if not ssl_verify:
            self.s.verify = False
        elif ssl_cafile:
            self.s.verify = ssl_cafile

    def authenticate(self, username, password, ssl_verify=True, ssl_cafile=""):
        """Authenticate with username (email) and password. Optionally set SSL context as well.
        This or `load_auth` must be called once at the start of the session."""
        auth_data = {"email": username, "password": password}

        # Get auth token
        try:
            resp = self.s.post(API_URL + "authenticate", auth_data, headers=self.headers, timeout=self.api_timeout)
        except Exception as e:
            raise Exception("Connection failure: %s" % e)

        # check MFA code required
        if resp.status_code == 401:
            data = resp.json()
            if "mfa_token" in data:
                self._mfa_token = data["mfa_token"]
                raise SenseMFARequiredException(data["error_reason"])

        # check for 200 return
        if resp.status_code != 200:
            raise SenseAuthenticationException(
                "Please check username and password. API Return Code: %s" % resp.status_code
            )

        data = resp.json()
        self._set_auth_data(data)
        self.set_monitor_id(data["monitors"][0]["id"])

    def validate_mfa(self, code):
        """Validate a multi-factor authentication code after authenticate raised SenseMFARequiredException.
        Authentication process is completed if code is valid."""
        mfa_data = {
            "totp": code,
            "mfa_token": self._mfa_token,
            "client_time:": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        # Get auth token
        try:
            resp = self.s.post(API_URL + "authenticate/mfa", mfa_data, headers=self.headers, timeout=self.api_timeout)
        except Exception as e:
            raise Exception("Connection failure: %s" % e)

        # check for 200 return
        if resp.status_code != 200:
            raise SenseAuthenticationException(
                "Please check username and password. API Return Code: %s" % resp.status_code
            )

        data = resp.json()
        self._set_auth_data(data)
        self.set_monitor_id(data["monitors"][0]["id"])

    def renew_auth(self):
        renew_data = {
            "user_id": self.sense_user_id,
            "refresh_token": self.refresh_token,
        }

        # Get auth token
        try:
            resp = self.s.post(API_URL + "renew", renew_data, headers=self.headers, timeout=self.api_timeout)
        except Exception as e:
            raise Exception("Connection failure: %s" % e)

        # check for 200 return
        if resp.status_code != 200:
            raise SenseAuthenticationException(
                "Please check username and password. API Return Code: %s" % resp.status_code
            )

        self._set_auth_data(resp.json())

    def logout(self):
        try:
            resp = self.s.get(API_URL + "logout", timeout=self.api_timeout)
        except Exception as e:
            raise Exception("Connection failure: %s" % e)

        # check for 200 return
        if resp.status_code != 200:
            raise SenseAPIException("API Return Code: %s", resp.status_code)

    def update_realtime(self):
        """Update the realtime data (device status and current power)."""
        # rate limit API calls
        if self._realtime and self.rate_limit and self.last_realtime_call + self.rate_limit > time():
            return self._realtime
        url = WS_URL % (self.sense_monitor_id, self.sense_access_token)
        next(self.get_realtime_stream())

    def get_realtime_stream(self):
        """Reads realtime data from websocket.  Realtime data variable is set and data is
        returned through generator. Continues until loop broken."""
        ws = 0
        url = WS_URL % (self.sense_monitor_id, self.sense_access_token)
        try:
            ws = create_connection(url, timeout=self.wss_timeout, sslopt={"cert_reqs": ssl.CERT_NONE})
            while True:  # hello, features, [updates,] data
                result = json.loads(ws.recv())
                if result.get("type") == "realtime_update":
                    data = result["payload"]
                    self._set_realtime(data)
                    yield data
        except WebSocketTimeoutException:
            raise SenseAPITimeoutException("API websocket timed out")
        finally:
            if ws:
                ws.close()

    def _api_call(self, url, payload={}, retry=False):
        """Make a call to the Sense API directly and return the json results."""
        try:
            resp = self.s.get(
                API_URL + url,
                headers=self.headers,
                timeout=self.api_timeout,
                params=payload,
            )

            if not retry and resp.status_code == 401:
                self.renew_auth()
                return self._api_call(url, payload, True)

            # 4xx represents unauthenticated
            if resp.status_code == 401 or resp.status_code == 403 or resp.status_code == 404:
                raise SenseAuthenticationException("API Return Code: %s", resp.status_code)
            return resp.json()
        except ReadTimeout:
            raise SenseAPITimeoutException("API call timed out")

    def get_trend_data(self, scale, dt=None):
        """Update trend data for specified scale from API.
        Optionally set a date to fetch data from."""
        if scale.upper() not in valid_scales:
            raise Exception("%s not a valid scale" % scale)
        if not dt:
            dt = datetime.utcnow()
        self._trend_data[scale] = self._api_call(
            "app/history/trends?monitor_id=%s&scale=%s&start=%s"
            % (self.sense_monitor_id, scale, dt.strftime("%Y-%m-%dT%H:%M:%S"))
        )

    def update_trend_data(self, dt=None):
        """Update trend data of all scales from API.
        Optionally set a date to fetch data from."""
        for scale in valid_scales:
            self.get_trend_data(scale, dt)

    def get_monitor_data(self):
        """Get monitor overview info from API."""
        json = self._api_call("app/monitors/%s/overview" % self.sense_monitor_id)
        if "monitor_overview" in json and "monitor" in json["monitor_overview"]:
            self._monitor = json["monitor_overview"]["monitor"]
        return self._monitor

    def get_discovered_device_names(self):
        """Get list of device names from API."""
        json = self._api_call("app/monitors/%s/devices" % self.sense_monitor_id)
        self._devices = [entry["name"] for entry in json]
        return self._devices

    def get_discovered_device_data(self):
        """Get list of raw device data from API."""
        return self._api_call("monitors/%s/devices" % self.sense_monitor_id)

    def always_on_info(self):
        """Always on info from API - pretty generic similar to the web page."""
        return self._api_call("app/monitors/%s/devices/always_on" % self.sense_monitor_id)

    def get_monitor_info(self):
        """View info on monitor & device detection status from API."""
        return self._api_call("app/monitors/%s/status" % self.sense_monitor_id)

    def get_device_info(self, device_id):
        """Get specific informaton about a device from API."""
        return self._api_call("app/monitors/%s/devices/%s" % (self.sense_monitor_id, device_id))

    def get_all_usage_data(self, payload={"n_items": 30}):
        """Gets usage data by device from API

        Args:
            payload (dict, optional): known params are:
                n_items: the number of items to return
                device_id: limit results to a specific device_id
                prior_to_item:. date in format YYYY-MM-DDTHH:MM:SS.mmmZ
                rollup: ?

                Defaults to {'n_items': 30}.

        Returns:
            dict: usage data
        """
        # lots of info in here to be parsed out
        return self._api_call("users/%s/timeline" % (self.sense_user_id), payload)
