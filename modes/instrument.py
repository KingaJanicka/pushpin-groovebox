import logging
import engine
import mido
import isobar as iso
from pythonosc.udp_client import SimpleUDPClient
from pythonosc.osc_server import AsyncIOOSCUDPServer
from pythonosc.dispatcher import Dispatcher
from modes.osc_device import OSCDevice
from modes.mod_matrix_device import ModMatrixDevice
from modes.audio_in_device import AudioInDevice
from definitions import PyshaMode
import asyncio
logger = logging.getLogger("osc_instrument")
# logger.setLevel(level=logging.DEBUG)
from time import sleep

class Instrument(PyshaMode):
    engine = None
    timeline = None

    def __init__(
        self,
        instrument_short_name,
        instrument_definition,
        device_definitions,
        get_current_instrument_color_helper,
        app,
        **kwargs
    ):
        self.app = app
        self.transports = []
        self.devices = []
        self.instrument_nodes = []
        self.instrument_ports = []
        self.slots = [
            {"address": "/param/a/osc/1/type", "value": 0.0},
            {"address": "/param/a/osc/2/type", "value": 0.0},
            None,
            None,
            None,
            {"address": "/param/fx/a/1/type", "value": 0.0},
            {"address": "/param/fx/a/2/type", "value": 0.0},
            {"address": "/param/fx/global/1/type", "value": 0.0},
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        ]
        self.name = instrument_short_name
        self.osc_in_port = instrument_definition.get("osc_in_port", None)
        self.osc_out_port = instrument_definition.get("osc_out_port", None)
        self.log_in = logger.getChild(f"in-{self.osc_in_port}")
        self.log_out = logger.getChild(f"out-{self.osc_out_port}")

        # this is vestigal and I think only has anything to do with external midi being sent
        # TODO remove and replace with Isobar midi in????
        self.midi_in_name = f'{instrument_definition["instrument_short_name"]}'
        self.midi_out_name = f'{instrument_definition["instrument_short_name"]}'

        # self.midi_in_device = mido.open_output(
        #     self.midi_in_name,
        #     client_name=self.midi_in_name,
        # )
        
        # self.midi_in_device = iso.MidiInputDevice(device_name=self.midi_in_name)
        self.midi_out_device = iso.MidiOutputDevice(
            device_name=self.midi_out_name, send_clock=True, virtual=True
        )
        self.midi_in_device = self.midi_out_device

        midi_out_idx = [self.midi_in_name in output for output in iso.get_midi_input_names()].index(
            True
        )
        
        self.timeline = iso.Timeline(
            self.app.tempo, 
            output_device=self.midi_out_device
        )
        
        print("MIDI", midi_out_idx, mido.get_input_names()[midi_out_idx])
        if kwargs.get("engine", "surge-xt-cli") == "surge-xt-cli":
            self.engine = engine.SurgeXTEngine(app, midi_device_idx=midi_out_idx, instrument_definition=instrument_definition)
                   
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
                # print(f'making a dispatcher for slot {slot["address"]}')

                dispatcher.map(slot["address"], self.set_slot_state)
        for x in range(16):
            self.devices.append([])

        for device_name in device_definitions:
            if device_name == "mod_matrix":
                device = ModMatrixDevice(
                    self.osc,
                    get_color=get_current_instrument_color_helper,
                    osc_in_port=self.osc_in_port,
                    osc_out_port=self.osc_out_port,
                    app=app,
                    engine=self.engine
                )
            elif device_name == "audio_1" or device_name == "audio_2":
                device = AudioInDevice(
                    device_definitions[device_name],
                    self.osc,
                    get_color=get_current_instrument_color_helper,
                    osc_in_port=self.osc_in_port,
                    osc_out_port=self.osc_out_port,
                    app=app,
                    engine=self.engine
                )
            else:
                device = OSCDevice(
                    device_definitions[device_name],
                    self.osc,
                    get_color=get_current_instrument_color_helper,
                    osc_in_port=self.osc_in_port,
                    osc_out_port=self.osc_out_port,
                    app=app,
                    engine=self.engine
                )

            slot_idx = device_definitions[device_name]["slot"]
            self.devices[slot_idx].append(device)
        self.current_devices = []
        print(
            "Loaded {0} devices for instrument {1}".format(
                sum([len(slot) for slot in self.devices]),
                self.name,
            )
        )
        # Check what's mapped
        # print(dispatcher._map.keys())
        # self.query_all_params()

        self.devices_modulation = []
        
        # gets all the modulation devices
        for slot_idx, slot_devices in enumerate(self.devices):
            for device in slot_devices:
                if 8 <= slot_idx <= 15:
                    self.devices_modulation.append(device)

        self.update_current_devices()

    def update_current_devices(self):
        updated_devices = []
        for slot_idx, slot_devices in enumerate(self.devices):
            for device in slot_devices:
                if slot_idx == 2 or slot_idx == 3 or slot_idx == 4:
                    updated_devices.append(device)
                else:
                    slot = self.slots[slot_idx]
                    for init in device.init:
                        if init["address"] == slot["address"] and int(init["value"]) == float(slot["value"]):
                            updated_devices.append(device)
        self.current_devices = updated_devices
        return
    


    def set_slot_state(self, *resp):
        address, value, *rest = resp
        # print(f"Setting state of slot {address} to {value}")
        for slot in self.slots:
            if slot and slot["address"] == address:
                # if slot["value"] != value:
                #     print("slot ", slot["address"], slot["value"],  " disselected")
                #     print("slot ", address, value,  " selected")
                
                # This compares new value with current value and fires a selected/disselected call
                if slot["address"] == ('/param/a/osc/1/type' or 'param/a/osc/2/type') and value == 4 and slot["value"] != 4:
                    print("audio in selected")
                    pass

                if slot["address"] == ('/param/a/osc/1/type' or 'param/a/osc/2/type') and value != 4 and slot["value"] == 4:
                    print("audio in dis-selected")
                    pass


                if float(slot["value"]) != float(value):
                    slot["value"] = float(value)
                    break
        self.update_current_devices()
                

    async def init_devices(self):
        for slot_idx, slot_devices in enumerate(self.devices):
            for device in slot_devices:
                if slot_idx == 2 or slot_idx == 3 or slot_idx == 4:
                    await device.select()
                else:
                    slot = self.slots[slot_idx]
                    for init in device.init:
                        if init["address"] == slot["address"] and int(
                            init["value"]
                        ) == float(slot["value"]):
                            await device.select()

    def init_devices_sync(self):
        for slot_idx, slot_devices in enumerate(self.devices):
            for device in slot_devices:
                if slot_idx == 2 or slot_idx == 3 or slot_idx == 4:
                    device.select_sync()
                else:
                    slot = self.slots[slot_idx]
                    for init in device.init:
                        if init["address"] == slot["address"] and int(
                            init["value"]
                        ) == float(slot["value"]):
                            device.select_sync()



    def query_devices(self):
        for slot_idx, slot_devices in enumerate(self.devices):
            for device in slot_devices:
                if slot_idx == 2 or slot_idx == 3 or slot_idx == 4:
                    device.query_visible_controls()
                else:
                    slot = self.slots[slot_idx]
                    for init in device.init:
                        if init["address"] == slot["address"] and int(
                            init["value"]
                        ) == float(slot["value"]):
                            device.query_visible_controls()

    def query_all_controls(self):
        for slot_idx, slot_devices in enumerate(self.devices):
            for device in slot_devices:
                if slot_idx == 2 or slot_idx == 3 or slot_idx == 4:
                    device.query_all_controls()
                else:
                    slot = self.slots[slot_idx]
                    for init in device.init:
                        if init["address"] == slot["address"] and int(
                            init["value"]
                        ) == float(slot["value"]):
                            device.query_all_controls()

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
            self.query_slots()
            self.query_devices()
            
            # This starts the Surge-XT instances
            asyncio.create_task(self.engine.start())

    def query_all_params(self):
        # TODO: this is broken
        # # print(self.devices)
        # for device in self.devices:
        #     print(device.label)
            # device.query_all()
        client = self.osc["client"]
        if client:
            # print(f"Querying all_params on {self.name}")
            client.send_message("/q/all_params", None)

    def query_slots(self):
        client = self.osc["client"]
        if client:
            for slot in self.slots:
                if slot:
                    # print(f'querrying slot /q{slot["address"]}')
                    client.send_message(f'/q{slot["address"]}', None)

    """
    Close transports on ctrl+c
    
    @TODO is this still needed?
    """

    def close_transports(self):
        # print("Closing transports")
        # for transport in self.transports:
        #     transport.close()
        pass

    def send_message(self, *args):
        client = self.osc["client"]
        if client:
            return client.send_message(*args)
