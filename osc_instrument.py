import logging
from pythonosc.udp_client import SimpleUDPClient
from pythonosc.osc_server import AsyncIOOSCUDPServer
from pythonosc.dispatcher import Dispatcher
import asyncio
import time
from osc_device import OSCDevice

logger = logging.getLogger("osc_device")
logger.setLevel(level=logging.DEBUG)


class OSCInstrument(object):
    def __init__(
        self,
        instrument_short_name,
        instrument_definition,
        device_definitions,
        get_current_instrument_color_helper,
    ):
        self.transports = []
        self.devices = []
        self.slots = [
            {"address": "/param/a/osc/1/type", "value": 0.0},
            {"address": "/param/a/osc/2/type", "value": 0.0},
            None,
            None,
            None,
            {"address": "/param/fx/a/1/type", "value": 0.0},
            {"address": "/param/fx/a/2/type", "value": 0.0},
            {"address": "/param/fx/global/1/type", "value": 0.0},
        ]

        self.name = instrument_short_name
        self.osc_in_port = instrument_definition.get("osc_in_port", None)
        self.osc_out_port = instrument_definition.get("osc_out_port", None)
        self.log_in = logger.getChild(f"in-{self.osc_in_port}")
        self.log_out = logger.getChild(f"out-{self.osc_out_port}")

        client = None
        server = None
        dispatcher = Dispatcher()
        dispatcher.set_default_handler(lambda *message: self.log_in.debug(message))

        if self.osc_in_port:
            client = SimpleUDPClient("127.0.0.1", self.osc_in_port)

        self.osc = {"client": client, "server": server, "dispatcher": dispatcher}
        # populate slot values
        for slot_idx, slot in enumerate(self.slots):
            if slot:
                dispatcher.map(slot["address"], self.set_slot_state)

        for x in range(8):
            self.devices.append([])

        for device_name in device_definitions:
            device = OSCDevice(
                device_definitions[device_name],
                self.osc,
                get_color=get_current_instrument_color_helper,
                osc_in_port=self.osc_in_port,
                osc_out_port=self.osc_out_port,
            )
            slot_idx = device_definitions[device_name]["slot"]

            self.devices[slot_idx].append(device)

        print(
            "Loaded {0} devices for instrument {1}".format(
                sum([len(slot) for slot in self.devices]),
                self.name,
            )
        )

    def set_slot_state(self, *resp):
        address, value, *rest = resp
        for slot in self.slots:
            if slot and slot["address"] == address:
                if float(slot["value"]) != float(value):
                    slot["value"] = float(value)
                    break

    """
    Initialise OSC servers and add to transport array so they can be gracefully closed
    """

    async def start(self, loop):
        if self.osc_out_port:
            server = AsyncIOOSCUDPServer(
                ("127.0.0.1", self.osc_out_port), self.osc["dispatcher"], loop
            )

            transport, protocol = (
                await server.create_serve_endpoint()
            )  # Create datagram endpoint and start serving

            self.transports.append(transport)
            self.log_out.debug(f"Receiving OSC on port {self.osc_out_port}")

    def query_all_params(self):
        client = self.osc["client"]
        if client:
            print(f"Querying all_params on {self.name}")
            client.send_message("/q/all_params", None)

    """
    Close transports on ctrl+c
    
    @TODO is this still needed?
    """

    def close_transports(self):
        # print("Closing transports")
        # for transport in self.transports:
        #     transport.close()
        pass
