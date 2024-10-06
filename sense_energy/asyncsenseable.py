import asyncio
import ssl
import sys
from functools import lru_cache
from time import time
from datetime import timezone

import aiohttp
import orjson
import websockets

from .sense_api import *
from .sense_exceptions import *

if sys.version_info[:2] < (3, 11):
    from async_timeout import timeout as asyncio_timeout
else:
    from asyncio import timeout as asyncio_timeout


@lru_cache(maxsize=None)
def get_ssl_context(ssl_verify: bool, ssl_cafile: str) -> ssl.SSLContext:
    """Create or set the SSL context. Use custom ssl verification, if specified."""
    if not ssl_verify:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
    elif ssl_cafile:
        ssl_context = ssl.create_default_context(cafile=ssl_cafile)
    else:
        ssl_context = ssl.create_default_context()
    return ssl_context


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

    def set_ssl_context(self, ssl_verify: bool, ssl_cafile: str):
        """Create or set the SSL context. Use custom ssl verification, if specified."""
        self.ssl_context = get_ssl_context(ssl_verify, ssl_cafile)

    async def authenticate(self, username: str, password: str, ssl_verify: bool = True, ssl_cafile: str = "") -> None:
        """Authenticate with username (email) and password. Optionally set SSL context as well.
        This or `load_auth` must be called once at the start of the session."""
        auth_data = {"email": username, "password": password}
        self.set_ssl_context(ssl_verify, ssl_cafile)

        # Get auth token
        async with self._client_session.post(
            API_URL + "authenticate",
            headers=self.headers,
            timeout=self.api_timeout,
            data=auth_data,
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
                    f"Please check username and password. API Return Code: {resp.status}"
                )

            # Build out some common variables
            data = await resp.json()
            self._set_auth_data(data)
            self.set_monitor_id(data["monitors"][0]["id"])
            await self.fetch_devices()

    async def validate_mfa(self, code: str) -> None:
        """Validate a multi-factor authentication code after authenticate raised SenseMFARequiredException.
        Authentication process is completed if code is valid."""
        mfa_data = {
            "totp": code,
            "mfa_token": self._mfa_token,
            "client_time:": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

        # Get auth token
        async with self._client_session.post(
            API_URL + "authenticate/mfa",
            headers=self.headers,
            timeout=self.api_timeout,
            data=mfa_data,
        ) as resp:
            # check for 200 return
            if resp.status != 200:
                raise SenseAuthenticationException(f"API Return Code: {resp.status}")

            # Build out some common variables
            data = await resp.json()
            self._set_auth_data(data)
            self.set_monitor_id(data["monitors"][0]["id"])
            await self.fetch_discovered_devices()

    async def renew_auth(self) -> None:
        """Renew the authentication token."""
        renew_data = {
            "user_id": self.sense_user_id,
            "refresh_token": self.refresh_token,
        }

        # Get auth token
        async with self._client_session.post(
            API_URL + "renew",
            headers=self.headers,
            timeout=self.api_timeout,
            data=renew_data,
        ) as resp:
            # check for 200 return
            if resp.status != 200:
                raise SenseAuthenticationException(f"API Return Code: {resp.status}")

            self._set_auth_data(await resp.json())

    async def logout(self) -> None:
        """Log out of Sense."""
        # Get auth token
        async with self._client_session.get(API_URL + "logout", timeout=self.api_timeout) as resp:
            # check for 200 return
            if resp.status != 200:
                raise SenseAPIException(f"API Return Code: {resp.status}")

    async def update_realtime(self, retry: bool = True) -> None:
        """Update the realtime data (device status and current power)."""
        # rate limit API calls
        now = time()
        if self._realtime and self.rate_limit and self.last_realtime_call + self.rate_limit > now:
            return self._realtime
        self.last_realtime_call = now
        try:
            await self.async_realtime_stream(single=True)
        except SenseAuthenticationException as e:
            if retry:
                await self.renew_auth()
                await self.update_realtime(False)
            else:
                raise e

    async def async_realtime_stream(self, callback: callable = None, single: bool = False) -> None:
        """Reads realtime data from websocket.  Data is passed to callback if available.
        Continues reading realtime stream data forever unless 'single' is set to True.
        """
        url = WS_URL % (self.sense_monitor_id, self.sense_access_token)
        # hello, features, [updates,] data
        async with websockets.connect(url, ssl=self.ssl_context) as ws:
            while True:
                try:
                    async with asyncio_timeout(self.wss_timeout):
                        message = await ws.recv()
                except asyncio.TimeoutError as ex:
                    raise SenseAPITimeoutException("API websocket timed out") from ex

                result = orjson.loads(message)
                if result.get("type") == "realtime_update":
                    data = result["payload"]
                    self._set_realtime(data)
                    if callback:
                        callback(data)
                    if single:
                        return
                elif result.get("type") == "error":
                    data = result["payload"]
                    if not data["authorized"]:
                        raise SenseAuthenticationException("Web Socket Unauthorized")
                    raise SenseWebsocketException(data["error_reason"])

    async def get_realtime_future(self, callback: callable) -> None:
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

    async def get_trend_data(self, scale: Scale, dt: datetime = None) -> None:
        """Update trend data for specified scale from API.
        Optionally set a date to fetch data from."""
        if not dt:
            dt = datetime.now(timezone.utc)
        json = self._api_call(
            f"app/history/trends?monitor_id={self.sense_monitor_id}"
            + f"&device_id=always_on&scale={scale.name}&start={dt.strftime('%Y-%m-%dT%H:%M:%S')}"
        )
        self._trend_data[scale] = await json
        self._update_device_trends(scale)

    async def update_trend_data(self, dt: datetime = None) -> None:
        """Update trend data of all scales from API.
        Optionally set a date to fetch data from."""
        for scale in Scale:
            await self.get_trend_data(scale, dt)

    async def get_monitor_data(self):
        """Get monitor overview info from API."""
        json = await self._api_call(f"app/monitors/{self.sense_monitor_id}/overview")
        if "monitor_overview" in json and "monitor" in json["monitor_overview"]:
            self._monitor = json["monitor_overview"]["monitor"]
        return self._monitor

    async def fetch_devices(self) -> None:
        """Fetch discovered devices from API."""
        json = await self._api_call(f"app/monitors/{self.sense_monitor_id}/devices/overview")
        for device in json["devices"]:
            if not device["tags"].get("DeviceListAllowed", True):
                continue
            id = device["id"]
            if id not in self._devices:
                self._devices[id] = SenseDevice(id)
            self._devices[id].name = device["name"]
            self._devices[id].icon = device["icon"]

    async def get_discovered_device_names(self) -> list[str]:
        """Outdated. Get list of device names from API.
        Use fetch_discovered_devices and sense.devices instead."""
        await self.fetch_devices()
        return [d.name for d in self._devices.values()]

    async def get_discovered_device_data(self):
        """Outdated. Get list of raw device data from API.
        Use fetch_discovered_devices and sense.devices instead."""
        json = self._api_call(f"monitors/{self.sense_monitor_id}/devices/overview")
        return await json["devices"]
