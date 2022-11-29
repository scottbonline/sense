# Copyright 2020, Charles Powell

# SenseLink is a tool that emulates the energy monitoring functionality of TP-Link Kasa HS110 Smart Plugs,
# and allows you to report "custom" power usage to your Sense Home Energy Monitor based on other parameters.

import logging
import asyncio
import json

from .tplink_encryption import *
from .plug_instance import PlugInstance

SENSE_TP_LINK_PORT = 9999


class SenseLinkServerProtocol:
    def __init__(self, devices):
        self._devices = devices
        self.should_respond = True

    def connection_made(self, transport):
        self.transport = transport

    def connection_lost(self, exc):
        pass

    def datagram_received(self, data, addr):
        decrypted_data = tp_link_decrypt(data)

        try:
            json_data = json.loads(decrypted_data)
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
                    json_resp = json.dumps(response, separators=(",", ":"))
                    encrypted_resp = tp_link_encrypt(json_resp)
                    # Strip leading 4 bytes for...some reason
                    encrypted_resp = encrypted_resp[4:]

                    # Allow disabling response
                    if self.should_respond:
                        # Send response
                        logging.debug(f"Sending response: {response}")
                        self.transport.sendto(encrypted_resp, addr)
                    else:
                        # Do not send response, but log for debugging
                        logging.debug(f"SENSE_RESPONSE disabled, response content: {response}")
            else:
                logging.debug(f"Ignoring non-emeter JSON from {addr}: {json_data}")

        # Appears to not be JSON
        except ValueError:
            logging.debug("Did not receive valid json")


class SenseLink:
    _devices = []

    def __init__(self, devices, port=SENSE_TP_LINK_PORT):
        self.port = port
        self._devices = devices

    def print_instance_wattages(self):
        for inst in self._devices():
            logging.info(f"Plug {inst.alias} power: {inst.power}")

    async def start(self):
        loop = asyncio.get_running_loop()
        self.transport, self.protocol = await loop.create_datagram_endpoint(
            lambda: SenseLinkServerProtocol(self._devices), local_addr=("0.0.0.0", self.port)
        )

    async def stop(self):
        self.transport.close()
