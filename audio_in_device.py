from osc_controls import (
    OSCControl,
    OSCControlMacro,
    ControlSpacer,
    OSCSpacerAddress,
    OSCControlSwitch,
    OSCControlMenu,
    OSCGroup,
)
import definitions
from display_utils import show_text
import push2_python
import logging
import asyncio
from definitions import PyshaMode
from engine import getAllClients
from engine import getAllNodes
from engine import getAllPorts
from engine import connectPipewireSourceToPipewireDest
from engine import disconnectPipewireSourceFromPipewireDest

logger = logging.getLogger("osc_device")
# logger.setLevel(level=logging.DEBUG)


class AudioInDevice(PyshaMode):
    @property
    def size(self):
        i = 0
        for control in self.controls:
            i += control.size

        return i

    @property
    def pages(self):
        pages = [[]]
        idx = 0
        for control in self.controls:
            current_page = pages[idx]

            # If control won't fit
            if len(current_page) + control.size > 8:
                # Fill remaining page with spacers
                for x in range(8 - len(current_page)):
                    current_page.append(ControlSpacer())

                # Create a new page and make it current
                pages.append([])
                idx += 1
                current_page = pages[idx]

            current_page.append(control)
            if isinstance(control, OSCControlSwitch):
                active_group: OSCGroup = control.get_active_group()
                for c in active_group.controls:
                    current_page.append(c)
        return pages

    @property
    def instrument(self):
        return self.get_instrument_for_pid(self.engine.PID)

    def __init__(
        self,
        config,
        osc={"client": {}, "server": {}, "dispatcher": {}},
        engine=None,
        **kwargs,
    ):
        self.app = kwargs["app"]
        self.engine = engine
        self.label = ""
        self.clients = []
        self.definition = {}
        self.controls = []
        self.page = 0
        self.slot = None
        self.definition = config
        self.osc = osc
        self.label = config.get("name", "Device")
        self.dispatcher = osc.get("dispatcher", None)
        self.instrument_nodes = []
        self.instrument_ports = []
        self.slot = config.get("slot", None)
        self.log_in = logger.getChild(f"in-{kwargs['osc_in_port']}")
        self.log_out = logger.getChild(f"out-{kwargs['osc_out_port']}")
        # IMPORTANT: if using query_all_params do not uncomment the following:
        # self.dispatcher.map("*", lambda *message: self.log_in.debug(message))
        self.init = config.get("init", [])
        self.get_color = kwargs.get("get_color")
        control_definitions = config.get("controls", [])
        # Configure controls
        audio_channel_control = OSCControl(
            {
                "$type": "control-range",
                "label": "Audio Channel",
                "address": "/param/a/osc/1/param1",
                "min": 0,
                "max": 1,
                "bipolar": 1,
            },
            self.get_color,
            self.send_message,
        )
        self.dispatcher.map(
            audio_channel_control.address, audio_channel_control.set_state
        )
        self.controls.append(audio_channel_control)

        audio_gain_control = OSCControl(
            {
                "$type": "control-range",
                "label": "Audio Gain",
                "address": "/param/a/osc/1/param2",
                "min": 0,
                "max": 1,
            },
            self.get_color,
            self.send_message,
        )
        self.dispatcher.map(audio_gain_control.address, audio_gain_control.set_state)
        self.controls.append(audio_gain_control)

        self.controls.append(ControlSpacer())
        self.controls.append(ControlSpacer())
        self.controls.append(ControlSpacer())
        self.controls.append(ControlSpacer())

        low_cut_control = OSCControl(
            {
                "$type": "control-range",
                "label": "Low Cut",
                "address": "/param/a/osc/1/param6",
                "min": 0,
                "max": 1,
            },
            self.get_color,
            self.send_message,
        )
        self.dispatcher.map(low_cut_control.address, low_cut_control.set_state)
        self.controls.append(low_cut_control)

        high_cut_control = OSCControl(
            {
                "$type": "control-range",
                "label": "High Cut",
                "address": "/param/a/osc/1/param7",
                "min": 0,
                "max": 1,
            },
            self.get_color,
            self.send_message,
        )
        self.dispatcher.map(high_cut_control.address, high_cut_control.set_state)
        self.controls.append(high_cut_control)

        for client in self.clients:
            for item in client:
                print(item)
        # for control_def in control_definitions:
        #     match control_def["$type"]:
        #         case "control-spacer":
        #             self.controls.append(ControlSpacer())
        #         case "control-macro":
        #             self.controls.append(
        #                 OSCControlMacro(control_def, get_color, self.send_message)
        #             )
        #             for param in control_def["params"]:
        #                 self.dispatcher.map(param.address, control.set_state)
        #         case "control-range":
        #             control = OSCControl(control_def, get_color, self.send_message)
        #             self.dispatcher.map(control.address, control.set_state)
        #             self.controls.append(control)
        #         case "control-spacer-address":
        #             control = OSCSpacerAddress(control_def, self.send_message)
        #             self.dispatcher.map(control.address, control.set_state)
        #             self.controls.append(control)
        #         case "control-switch":
        #             control = OSCControlSwitch(
        #                 control_def, get_color, self.send_message, self.dispatcher
        #             )
        #             if control.address:
        #                 self.dispatcher.map(control.address, control.set_state)

        #             self.controls.append(control)

        #         case "control-menu":
        #             control = OSCControlMenu(control_def, get_color, self.send_message)
        #             if control.address:
        #                 self.dispatcher.map(control.address, control.set_state)

        #             # for item in control.items:
        #             #     if item.address:
        #             #         self.dispatcher.map(item.address, control.set_state)
        #             #     else:
        #             #         raise Exception(f"{item} has no message.address property")

        #             self.controls.append(control)
        #         case _:
        #             Exception(
        #                 f"Invalid parameter: {control_def}; did you forget $type?"
        #             )
        # asyncio.create_task(self.query_clients)
        # Call /q endpoints for each control currently displayed
        # self.query_visible_controls()
        # mapped_addresses = self.dispatcher
        # Select if it has a select attribute


        for control in self.get_visible_controls():
            if hasattr(control, "select"):
                control.select()

    def update(self):
        control_def = {
            "$type": "control-switch",
            "label": f"{self.instrument.name}",
            "groups": [{
                "$type": "group",
                "label": "None sel.",
                "onselect": {
                    # "$type": "message",
                    # "$comment": "",
                    # "address": "/",
                    # "value": 1,
                },
                "controls": [
                    {
                        "$type": "control-menu",
                        "items": [
                            {
                                "$type": "menu-item",
                                "label": "",
                                "onselect": {
                                    "$type": "message",
                                    "$comment": "RingMod",
                                    "address": "/",
                                    "value": 0,
                                },
                            },
                        ],
                    }
                ],
            }],
        }

        for instrument in self.app.osc_mode.instruments.values():
            # print(client["info"]["props"]["object.serial"])
            # dest_instrument = self.get_instrument_for_pid(
            #     client["info"]["props"]["object.serial"]
            # )
            dest = {
                "$type": "group",
                "label": f'{instrument.name}',
                "pid": f'{instrument.engine.PID}',
                "onselect": {
                    "$type": "message",
                    "$comment": "",
                    "address": "/",
                    "value": instrument.engine.PID,
                },
                "controls": [
                    {
                        "$type": "control-menu",
                        "items": [
                            {
                                "$type": "menu-item",
                                "label": "L+R",
                                "onselect": {
                                    "$type": "message",
                                    "$comment": "RingMod",
                                    "address": "/",
                                    "value": instrument.engine.PID,
                                },
                            },
                        ],
                    }
                ],
            }
            control_def["groups"].append(dest)
    
        for out in range(1, 5):
            try:
                menu = OSCControlSwitch(
                    control_def, self.get_color, self.connect_ports, self.dispatcher
                )
                self.controls.append(menu)
            except Exception as e:
                print(e)
    

        

    def select(self):
        # self.query_visible_controls()
        print("device init______________")
        for cmd in self.init:
            self.send_message(cmd["address"], float(cmd["value"]))

    def send_message(self, *args):
        self.log_out.debug(args)
        return self.osc["client"].send_message(*args)

    async def get_instrument_nodes(self, PID=None):
        nodes = await getAllNodes()
        #getting nodes for instrument
        #TODO: broken, this is getting only one node when it should be giving us way more
        instrument_nodes = []
        for node in nodes:
                if node.get("info",{}).get("props",{}).get("application.process.id", None) == (PID or self.engine.PID):
                    instrument_nodes.append(node)
        self.instrument_nodes = instrument_nodes
        instrument = self.get_instrument_for_pid(self.engine.PID)
        instrument.instrument_nodes = instrument_nodes
        return instrument_nodes      

    async def get_instrument_ports(self):
        all_ports = await getAllPorts()
        instrument_ports = []
        #getting nodes for instrument
        instrument_nodes = await self.get_instrument_nodes()

        for port in all_ports:
            # with nodes we can associate nodes with clients/instruments via PID
            # And ports with nodes via ID/node.id
            # With those IDs in place we can start calling pw-link
 
            # print(instrument_node["id"], port["info"]["props"]["node.id"])
            for instrument_node in instrument_nodes:
                if port.get("info",{}).get("props", {}).get("node.id", None) == instrument_node.get("id", None):
                    instrument_ports.append(port)
        self.instrument_ports = instrument_ports
        instrument = self.get_instrument_for_pid(self.engine.PID)
        instrument.instrument_ports = instrument_ports
        return instrument_ports

    async def get_ports_and_nodes(self):
        instrument_ports = await self.get_instrument_ports()
        # print(instrument_ports)
        # for port in instrument_ports:
        #     print(port)

    async def update_all_instruments_ports_and_nodes(self):
        instruments = self.app.osc_mode.instruments
        for instrument in instruments.values():
            instrument.get_ports_and_nodes()


    def connect_ports(self, *args):
        try:
            source_instrument = self.get_instrument_for_pid(args[1])
            print(source_instrument.instrument_ports)
            source_instrument_ports = {"L": None, "R": None}
            current_instrument_ports = {"L": None, "R": None}

            #This for loop gets a stereo pair of output ports
            #TODO: this source_instrument.instrument_ports thing does not work
            #      Because it's only done when device is selected
            
            for port in source_instrument.instrument_ports:
                if port.get("info",[]).get("direction",None):
                    if port.get("info", []).get("props",[]).get("port.name","None") =="output_FL":
                        source_instrument_ports["L"] = port
                    elif port.get("info", []).get("props",[]).get("port.name","None") =="output_FR":
                        source_instrument_ports["R"] = port
            

            for port in self.instrument_ports:
                if port.get("info",[]).get("direction",None):
                    if port.get("info", []).get("props",[]).get("port.name","None") =="input_FL":
                        current_instrument_ports["L"] = port
                    elif port.get("info", []).get("props",[]).get("port.name","None") =="input_FR":
                        current_instrument_ports["R"] = port

            #TODO: uncommenting the 2nd print or the connect functions seems to break something and exception is thrown

            print(source_instrument_ports.get("L", []).get("id", None), "  ", current_instrument_ports.get("L", []).get("id", None))
            print(source_instrument_ports.get("R", []).get("id", None), "  ", current_instrument_ports.get("R", []).get("id", None))

            # asyncio.run(connectPipewireSourceToPipewireDest(source_instrument_ports.get("L", []).get("id", None), current_instrument_ports.get("L", []).get("id", None)))
            # asyncio.run(connectPipewireSourceToPipewireDest(source_instrument_ports.get("R", []).get("id", None), current_instrument_ports.get("R", []).get("id", None)))

        except Exception as e:
            print("Error in connect_ports")
            print(e)
        # connectPipewireSourceToPipewireDest()
        


    def query(self):
        for control in self.get_visible_controls():
            control.query()

    def query_all(self):
        for control in self.controls:
            control.query()

    def draw(self, ctx):
        # show_text(
        #     ctx,
        #     1,
        #     50,
        #    "FART",
        #     height=15,
        #     font_color=definitions.WHITE,
        # )
        visible_controls = self.get_visible_controls()
        all_controls = self.pages
        offset = 0
        for control in all_controls[self.page]:
            if offset + 1 <= 8:
                control.draw(ctx, offset)
                offset += 1
        offset = 0
        other_page = (self.page + 1) % 2
        try:
            for control in all_controls[other_page]:
                if offset + 1 <= 8:
                    control.draw_submenu(ctx, offset)
                    offset += 1
        except:
            pass

    def get_next_prev_pages(self):
        show_prev = False
        if self.page > 0:
            show_prev = True

        show_next = False
        if (self.page + 1) < len(self.pages):
            show_next = True

        return show_prev, show_next

    def set_page(self, page):
        self.page = page
        
        # self.query_visible_controls()
        # print("PAGE: ", self.page)
        # print(*self.pages[self.page], sep="\n")

    def query_visible_controls(self):
        visible_controls = self.get_visible_controls()
        for control in visible_controls:
            if hasattr(control, "address") and control.address is not None:
                self.send_message("/q" + control.address, None)
        asyncio.run(self.query_clients())
        # for item in self.clients:
        #     print(item)

    def query_all_controls(self):
        all_controls = self.get_all_controls()
        for control in all_controls:
            if hasattr(control, "address") and control.address is not None:
                self.send_message("/q" + control.address, None)
        asyncio.run(self.query_clients())

    def get_pipewire_config(self):
        for item in self.clients:
            pid = item["info"]["props"].get("application.process.id")
            if pid == self.engine.PID:
                return item

    def get_instrument_for_pid(self, pid):
        instruments = self.app.osc_mode.instruments
        for instrument in instruments.values():
            if instrument.engine.PID == pid:
                return instrument
        
        return False

    def get_visible_controls(self):
        return self.pages[self.page]

    async def query_clients(self):
        data = await getAllClients()
        self.clients = data
        self.get_pipewire_config()
        self.get_instrument_for_pid(self.engine.PID)
        self.update()
        await self.get_ports_and_nodes()

    def get_all_controls(self):
        try:
            all_controls = self.pages[0] + self.pages[1]
        except:
            all_controls = self.pages[0]
        return all_controls

    def on_encoder_rotated(self, encoder_name, increment):
        try:
            encoder_idx = [
                push2_python.constants.ENCODER_TRACK1_ENCODER,
                push2_python.constants.ENCODER_TRACK2_ENCODER,
                push2_python.constants.ENCODER_TRACK3_ENCODER,
                push2_python.constants.ENCODER_TRACK4_ENCODER,
                push2_python.constants.ENCODER_TRACK5_ENCODER,
                push2_python.constants.ENCODER_TRACK6_ENCODER,
                push2_python.constants.ENCODER_TRACK7_ENCODER,
                push2_python.constants.ENCODER_TRACK8_ENCODER,
            ].index(encoder_name)
            visible_controls = self.get_visible_controls()
            control = visible_controls[encoder_idx]
            control.update_value(increment)
        except ValueError:
            pass  # Encoder not in list
