# Copyright 2020, Charles Powell

# SenseLink is a tool that emulates the energy monitoring functionality of TP-Link Kasa HS110 Smart Plugs,
# and allows you to report "custom" power usage to your Sense Home Energy Monitor based on other parameters.

import asyncio
import logging
from typing import Iterator, Optional, Union

import orjson
from kasa_crypt import decrypt as tp_link_decrypt
from kasa_crypt import encrypt as tp_link_encrypt

from .plug_instance import PlugInstance

SENSE_TP_LINK_PORT = 9999

_LOGGER = logging.getLogger(__name__)


class SenseLinkServerProtocol:
    """Class to represent a SenseLink server."""

    def __init__(self, devices: callable[[], Iterator[PlugInstance]]) -> None:
        """Initialize the SenseLink server."""
        self._devices = devices
        self.should_respond = True
        self.transport: Optional[asyncio.DatagramTransport] = None

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        """Handle new connection."""
        self.transport = transport

    def connection_lost(self, exc) -> None:
        """Handle lost connection."""
        pass

    def datagram_received(self, data: bytes, addr: Union[tuple[str, int], tuple[str, int, int, int]]) -> None:
        """Handle incoming UDP datagram."""
        try:
            decrypted_data = tp_link_decrypt(data)
        except UnicodeDecodeError:
            _LOGGER.debug(f"Failed to decrypt data from {addr}")
            return

        try:
            json_data = orjson.loads(decrypted_data)
            # Sense requests the emeter and system parameters
            if (
                "emeter" in json_data
                and "get_realtime" in json_data["emeter"]
                and "system" in json_data
                and "get_sysinfo" in json_data["system"]
            ):
                # Check for non-empty values, to prevent echo storms
                if json_data["emeter"]["get_realtime"]:
                    # This is a self-echo, common with Docker without --net=Host!
                    logging.debug("Ignoring non-empty/non-Sense UDP request")
                    return

                logging.debug(f"Broadcast received from {addr}: {json_data}")

                # Build and send responses
                for plug in self._devices():
                    # Build response
                    response = plug.generate_response()
                    json_resp = orjson.dumps(response)
                    encrypted_resp = tp_link_encrypt(json_resp.decode("utf-8"))
                    # Strip leading 4 bytes for...some reason
                    encrypted_resp = encrypted_resp[4:]

                    # Allow disabling response
                    if self.should_respond:
                        # Send response
                        logging.debug("Sending response: %s", response)
                        self.transport.sendto(encrypted_resp, addr)
                    else:
                        # Do not send response, but log for debugging
                        _LOGGER.debug("SENSE_RESPONSE disabled, response content: %s", response)
            else:
                _LOGGER.debug(f"Ignoring non-emeter JSON from %s: %s", addr, json_data)

        # Appears to not be JSON
        except ValueError:
            _LOGGER.debug("Did not receive valid json")


class SenseLink:
    """Class to represent a SenseLink server."""

    _devices = []

    def __init__(self, devices: callable[[], Iterator[PlugInstance]], port=SENSE_TP_LINK_PORT) -> None:
        """Initialize the SenseLink server."""
        self.port = port
        self._devices = devices

    def print_instance_wattages(self) -> None:
        """Log the current wattages of all instances."""
        for inst in self._devices():
            logging.info(f"Plug {inst.alias} power: {inst.power}")

    async def start(self) -> None:
        """Start the SenseLink server."""
        loop = asyncio.get_running_loop()
        self.transport, self.protocol = await loop.create_datagram_endpoint(
            lambda: SenseLinkServerProtocol(self._devices), local_addr=("0.0.0.0", self.port)
        )

    async def stop(self) -> None:
        """Stop the SenseLink server."""
        self.transport.close()
