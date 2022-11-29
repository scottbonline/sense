import asyncio
import json
import ssl

import aiohttp
import websockets

from .sense_api import *
from .sense_exceptions import *


class ASyncSenseable(SenseableBase):
    def __init__(
        self,
        username=None,
        password=None,
        api_timeout=API_TIMEOUT,
        wss_timeout=WSS_TIMEOUT,
        client_session=None,
        ssl_verify=True,
        ssl_cafile="",
        device_id=None,
    ):
        """Init the ASyncSenseable object."""
        self._client_session = client_session or aiohttp.ClientSession()

        super().__init__(
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
            self.ssl_context = ssl.create_default_context()
            self.ssl_context.check_hostname = False
            self.ssl_context.verify_mode = ssl.CERT_NONE
        elif ssl_cafile:
            self.ssl_context = ssl.create_default_context(cafile=ssl_cafile)
        else:
            self.ssl_context = ssl.create_default_context()

    async def authenticate(self, username, password, ssl_verify=True, ssl_cafile=""):
        """Authenticate with username (email) and password. Optionally set SSL context as well.
        This or `load_auth` must be called once at the start of the session."""
        auth_data = {"email": username, "password": password}
        self.set_ssl_context(ssl_verify, ssl_cafile)

        # Get auth token
        async with self._client_session.post(
            API_URL + "authenticate", headers=self.headers, timeout=self.api_timeout, data=auth_data
        ) as resp:

            # check MFA code required
            if resp.status == 401:
                data = await resp.json()
                if "mfa_token" in data:
                    self._mfa_token = data["mfa_token"]
                    raise SenseMFARequiredException(data["error_reason"])

            # check for 200 return
            if resp.status != 200:
                raise SenseAuthenticationException(
                    "Please check username and password. API Return Code: %s" % resp.status
                )

            # Build out some common variables
            data = await resp.json()
            self._set_auth_data(data)
            self.set_monitor_id(data["monitors"][0]["id"])

    async def validate_mfa(self, code):
        """Validate a multi-factor authentication code after authenticate raised SenseMFARequiredException.
        Authentication process is completed if code is valid."""
        mfa_data = {
            "totp": code,
            "mfa_token": self._mfa_token,
            "client_time:": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

        # Get auth token
        async with self._client_session.post(
            API_URL + "authenticate/mfa", headers=self.headers, timeout=self.api_timeout, data=mfa_data
        ) as resp:

            # check for 200 return
            if resp.status != 200:
                raise SenseAuthenticationException(f"API Return Code: {resp.status}")

            # Build out some common variables
            data = await resp.json()
            self._set_auth_data(data)
            self.set_monitor_id(data["monitors"][0]["id"])

    async def renew_auth(self):
        renew_data = {
            "user_id": self.sense_user_id,
            "refresh_token": self.refresh_token,
        }

        # Get auth token
        async with self._client_session.post(
            API_URL + "renew", headers=self.headers, timeout=self.api_timeout, data=renew_data
        ) as resp:

            # check for 200 return
            if resp.status != 200:
                raise SenseAuthenticationException(f"API Return Code: {resp.status}")

            self._set_auth_data(await resp.json())

    async def logout(self):
        # Get auth token
        async with self._client_session.get(API_URL + "logout", timeout=self.api_timeout, data=renew_data) as resp:
            # check for 200 return
            if resp.status != 200:
                raise SenseAPIException(f"API Return Code: {resp.status}")

    async def update_realtime(self):
        """Update the realtime data (device status and current power)."""
        # rate limit API calls
        if self._realtime and self.rate_limit and self.last_realtime_call + self.rate_limit > time():
            return self._realtime
        self.last_realtime_call = time()
        await self.async_realtime_stream(single=True)

    async def async_realtime_stream(self, callback=None, single=False):
        """Reads realtime data from websocket.  Data is passed to callback if available.
        Continues reading realtime stream data forever unless 'single' is set to True."""
        url = WS_URL % (self.sense_monitor_id, self.sense_access_token)
        # hello, features, [updates,] data
        async with websockets.connect(url, ssl=self.ssl_context) as ws:
            while True:
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=self.wss_timeout)
                except asyncio.TimeoutError as ex:
                    raise SenseAPITimeoutException("API websocket timed out") from ex

                result = json.loads(message)
                if result.get("type") == "realtime_update":
                    data = result["payload"]
                    self._set_realtime(data)
                    if callback:
                        callback(data)
                    if single:
                        return
                elif result.get("type") == "error":
                    data = result["payload"]
                    raise SenseWebsocketException(data["error_reason"])

    async def get_realtime_future(self, callback):
        """Returns an async Future to parse realtime data with callback"""
        await self.async_realtime_stream(callback)

    async def _api_call(self, url, payload={}, retry=False):
        """Make a call to the Sense API directly and return the json results."""
        timeout = aiohttp.ClientTimeout(total=self.api_timeout)
        try:
            async with self._client_session.get(
                API_URL + url, headers=self.headers, timeout=timeout, data=payload
            ) as resp:
                if not retry and resp.status == 401:
                    await self.renew_auth()
                    return await self._api_call(url, payload, True)

                # 4xx represents unauthenticated
                if resp.status == 401 or resp.status == 403 or resp.status == 404:
                    raise SenseAuthenticationException(f"API Return Code: {resp.status}")

                if resp.status != 200:
                    raise SenseAPIException(f"API Return Code: {resp.status}")

                return await resp.json()
        except asyncio.TimeoutError as ex:
            # timed out
            raise SenseAPITimeoutException("API call timed out") from ex

    async def get_trend_data(self, scale, dt=None):
        """Update trend data for specified scale from API.
        Optionally set a date to fetch data from."""
        if scale.upper() not in valid_scales:
            raise Exception("%s not a valid scale" % scale)
        if not dt:
            dt = datetime.utcnow()
        json = self._api_call(
            "app/history/trends?monitor_id=%s&scale=%s&start=%s"
            % (self.sense_monitor_id, scale, dt.strftime("%Y-%m-%dT%H:%M:%S"))
        )
        self._trend_data[scale] = await json

    async def update_trend_data(self, dt=None):
        """Update trend data of all scales from API.
        Optionally set a date to fetch data from."""
        for scale in valid_scales:
            await self.get_trend_data(scale, dt)

    async def get_monitor_data(self):
        """Get monitor overview info from API."""
        json = await self._api_call("app/monitors/%s/overview" % self.sense_monitor_id)
        if "monitor_overview" in json and "monitor" in json["monitor_overview"]:
            self._monitor = json["monitor_overview"]["monitor"]
        return self._monitor

    async def get_discovered_device_names(self):
        """Get list of device names from API."""
        json = self._api_call("app/monitors/%s/devices" % self.sense_monitor_id)
        self._devices = await [entry["name"] for entry in json]
        return self._devices

    async def get_discovered_device_data(self):
        """Get list of raw device data from API."""
        json = self._api_call("monitors/%s/devices" % self.sense_monitor_id)
        return await json
