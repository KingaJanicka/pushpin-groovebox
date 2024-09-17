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
        self.last_knob_turned = 0
        self.app = kwargs["app"]
        self.engine = engine
        self.label = ""
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
                    "$type": "message",
                    "$comment": "",
                    "address": "/",
                    "value": None,
                },
                "controls": [
                    {
                        "$type": "control-menu",
                        "items": [
                            {
                                "$type": "menu-item",
                                "label": "None",
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
                    "address": "/bla",
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
                                    "address": "/bla",
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

    def connect_ports(self, *args):

        [addr, val] = args
        column_index = None 
        if self.slot == 0:
            column_index = int(self.last_knob_turned / 2 ) 
        if self.slot == 1:
            column_index = int(self.last_knob_turned / 2 ) + 4
        #TODO: this is super wet, needs a dry
        
        current_instrument_ports = self.engine.pw_ports
        dest_L = None
        dest_R = None

        # This bit handles selecting a None input, just disconnects if something was already connected
        if addr == "/":
            disconnect_L = self.engine.connections[column_index]["L"]
            disconnect_R = self.engine.connections[column_index]["R"]
            for port in current_instrument_ports['input']:
                if port['info']['props']['audio.channel'] == "FL":
                    dest_L = port['id']
                elif port['info']['props']['audio.channel'] == "FR":
                    dest_R = port['id']
            if (disconnect_L != None) and (disconnect_R != None):
                asyncio.run(disconnectPipewireSourceFromPipewireDest(disconnect_L, dest_L))
                asyncio.run(disconnectPipewireSourceFromPipewireDest(disconnect_R, dest_R))
            self.engine.connections[column_index]["L"] = None
            self.engine.connections[column_index]["R"] = None
            return
            
        try:
            print("Try branch")
            print(self.engine.connections)
            source_instrument = self.get_instrument_for_pid(val)
            source_instrument_ports = source_instrument.engine.pw_ports

            current_instrument_ports = self.engine.pw_ports
            source_L = None
            source_R = None
            dest_L = None
            dest_R=None

            #We're getting IDs for left and right ports, input and output
            for port in source_instrument_ports['output']:
                if port['info']['props']['audio.channel'] == "FL":
                    source_L = port['id']
                elif port['info']['props']['audio.channel'] == "FR":
                    source_R = port['id']

            # This bit disconnects previously conneted synth within a column
            for port in current_instrument_ports['input']:
                if port['info']['props']['audio.channel'] == "FL":
                    dest_L = port['id']
                elif port['info']['props']['audio.channel'] == "FR":
                    dest_R = port['id']
            
            if self.engine.connections[column_index]["L"] != (source_L or None)  and self.engine.connections[column_index]["R"] != (source_R or None) :
                # print("col idx: ", column_index)
                print("disconnect prev synth")
                disconnect_L = self.engine.connections[column_index]["L"]
                disconnect_R = self.engine.connections[column_index]["R"]
                if disconnect_L and disconnect_R is not None:
                    print("disconnect not none loop")
                    print(disconnect_L, disconnect_R, dest_L, dest_R)
                    asyncio.run(disconnectPipewireSourceFromPipewireDest(disconnect_L, dest_L))
                    asyncio.run(disconnectPipewireSourceFromPipewireDest(disconnect_R, dest_R))


            # Connects to currently selected instance, assigns the port IDs for later reference
            for index, connection in enumerate(self.engine.connections):
                if index == column_index:
                    print("connect current synth")
                    connection["L"] = source_L
                    connection["R"] = source_R

            asyncio.run(connectPipewireSourceToPipewireDest(source_L, dest_L))
            asyncio.run(connectPipewireSourceToPipewireDest(source_R, dest_R))

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
        # for item in self.clients:
        #     print(item)

    def query_all_controls(self):
        all_controls = self.get_all_controls()
        self.update()
        for control in all_controls:
            if hasattr(control, "address") and control.address is not None:
                self.send_message("/q" + control.address, None)

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
        return None

    def get_visible_controls(self):
        return self.pages[self.page]


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
            self.last_knob_turned = encoder_idx
        except ValueError:
            pass  # Encoder not in list
