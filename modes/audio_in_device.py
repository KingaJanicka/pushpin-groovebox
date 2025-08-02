from osc_controls import (
    OSCControl,
    ControlSpacer,
    OSCControlSwitch,
    OSCGroup,
)
import push2_python
import logging
import asyncio
import traceback
from definitions import PyshaMode
from engine import connectPipewireSourceToPipewireDest
from engine import disconnectPipewireSourceFromPipewireDest
logger = logging.getLogger("osc_device")
# logger.setLevel(level=logging.DEBUG)
from ratelimit import limits


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
        self.input_gains = [0 ,0 ,0 ,0 ,0 ,0 ,0 ,0]
        self.engine = engine
        self.label = ""
        self.definition = {}
        # self.modmatrix = config.get("modmatrix", True)
        self.modmatrix = False
        self.controls = []
        self.page = 0
        self.slot = None
        self.definition = config
        self.osc = osc
        self.label = config.get("name", "Device")
        self.dispatcher = osc.get("dispatcher", None)
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
        osc_number = self.slot + 1
        audio_channel_control = OSCControl(
            {
                "$type": "control-range",
                "label": "Audio Channel",
                "address": f"/param/a/osc/{osc_number}/param1",
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
                "address": f"/param/a/osc/{osc_number}/param2",
                "min": 0,
                "max": 1,
            },
            self.get_color,
            self.send_message,
        )
        self.dispatcher.map(audio_gain_control.address, audio_gain_control.set_state)
        self.controls.append(audio_gain_control)

        in_1_gain = OSCControl(
            {
                "$type": "control-range",
                "label": "In 1 Gain",
                "address": "None",
                "min": 0,
                "max": 1,
            },
            self.get_color,
            self.set_duplex_volumes,
        )
        self.controls.append(in_1_gain)

        in_2_gain = OSCControl(
            {
                "$type": "control-range",
                "label": "In 2 Gain",
                "address": "None",
                "min": 0,
                "max": 1,
            },
            self.get_color,
            self.set_duplex_volumes,
        )
        self.controls.append(in_2_gain)

        in_3_gain = OSCControl(
            {
                "$type": "control-range",
                "label": "In 3 Gain",
                "address": "None",
                "min": 0,
                "max": 1,
            },
            self.get_color,
            self.set_duplex_volumes,
        )
        self.controls.append(in_3_gain)
        
        in_4_gain = OSCControl(
            {
                "$type": "control-range",
                "label": "In 4 Gain",
                "address": "None",
                "min": 0,
                "max": 1,
            },
            self.get_color,
            self.set_duplex_volumes,
        )
        self.controls.append(in_4_gain)

        low_cut_control = OSCControl(
            {
                "$type": "control-range",
                "label": "Low Cut",
                "address": f"/param/a/osc/{osc_number}/param6",
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
                "address": f"/param/a/osc/{osc_number}/param7",
                "min": 0,
                "max": 1,
            },
            self.get_color,
            self.send_message,
        )
        self.dispatcher.map(high_cut_control.address, high_cut_control.set_state)
        self.controls.append(high_cut_control)
        for control in self.get_visible_controls():
            if hasattr(control, "select"):
                control.select()
        # self.update()

    def update(self):
        name = self.engine.instrument["instrument_name"]
        control_def = {
            "$type": "control-switch",
            "label": name,
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

        for instrument in self.app.instruments.values():
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

        overwitch = self.app.external_instruments[0]
        overwitch_def = None
        overwitch_def = {
            "$type": "group",
            "label": f'{overwitch.name}',
            "pid": f'{overwitch.engine.PID or 0}',
            "onselect": {
                "$type": "message",
                "$comment": "",
                "address": "/bla",
                "value": overwitch.engine.PID or 0,
            },
            "controls": [
                {
                    "$type": "control-menu",
                    "items": [
                    ],
                }
            ],
        }
    
        for port in overwitch.engine.pw_ports["output"]:
            control = {
                            "$type": "menu-item",
                            "label": port["info"]["props"]["port.name"],
                            "onselect": {
                                "$type": "message",
                                "$comment": "RingMod",
                                "address": "/bla",
                                "value": overwitch.engine.PID or 0,
                            },
                        }
            overwitch_def["controls"][0]["items"].append(control)
        control_def["groups"].append(overwitch_def)
        for out in range(1, 5):
            try:
                menu = OSCControlSwitch(
                    control_def, self.get_color, self.connect_ports_duplex, self.dispatcher
                )
                self.controls.append(menu)
            except Exception as e:
                print("Exception in update in audio_in_device")
                traceback.print_exc()


    async def select(self):
        # self.query_visible_controls()
        self.update()
        for cmd in self.init:
            self.send_message(cmd["address"], float(cmd["value"]))
            await asyncio.sleep(0.1)
    
    def select_sync(self):
        # self.query_visible_controls()
        self.update()
        for cmd in self.init:
            self.send_message(cmd["address"], float(cmd["value"]))
            
    

    def send_message(self, *args):
        self.log_out.debug(args)
        return self.osc["client"].send_message(*args)
    
    
    def set_duplex_volumes(self, *args):
        duplex_node = self.engine.duplex_node
        channel_volumes = []
        for val in self.input_gains:
            if val == None:
                val = 0.0
            channel_volumes.extend([val, val])
        device_id = duplex_node["id"]
        # cli_string = f"pw-cli s {device_id} Props '{{monitorVolumes: {channel_volumes}}}'"
        # self.app.queue.append(asyncio.create_subprocess_shell(cli_string, stdout=asyncio.subprocess.PIPE))
        
        
        for idx in range(8):
            left_channel_idx = idx * 2
            right_channel_idx = left_channel_idx + 1
            # Value only from left because we want to have it center
            volume_value = channel_volumes[left_channel_idx]
            self.engine.duplex_node_osc_client.send_message(f"/vol_{left_channel_idx}", float(volume_value))
            self.engine.duplex_node_osc_client.send_message(f"/vol_{right_channel_idx}", float(volume_value))


    def update_input_gains(self):
        devices = self.app.osc_mode.get_current_instrument_devices()
        value_1 = None 
        value_2 = None 
        value_3 = None 
        value_4 = None 
        value_5 = None 
        value_6 = None 
        value_7 = None 
        value_8 = None
        
        if devices[0].label == "Audio In":
            value_1 = devices[0].controls[2].value
            value_2 = devices[0].controls[3].value
            value_3 = devices[0].controls[4].value
            value_4 = devices[0].controls[5].value
        
        if devices[1].label == "Audio In":

            value_5 = devices[1].controls[2].value
            value_6 = devices[1].controls[3].value
            value_7 = devices[1].controls[4].value
            value_8 = devices[1].controls[5].value
        
        for device in devices:
            if device.label == "Audio In":
                device.input_gains[0] = value_1
                device.input_gains[1] = value_2
                device.input_gains[2] = value_3
                device.input_gains[3] = value_4
                device.input_gains[4] = value_5
                device.input_gains[5] = value_6
                device.input_gains[6] = value_7
                device.input_gains[7] = value_8

    def connect_ports_duplex(self, *args):

        [addr, val] = args
        if val != None:
            column_index = None 
            if self.slot == 0:
                column_index = int(self.last_knob_turned / 2 ) 
            if self.slot == 1:
                column_index = int(self.last_knob_turned / 2 ) + 4
           
            current_instrument_ports = self.engine.pw_ports
            duplex_ports = self.engine.duplex_ports

            duplex_in_L = duplex_ports["inputs"][f'Input {column_index}']["L"]['id']
            duplex_in_R = duplex_ports["inputs"][f'Input {column_index}']["R"]['id']
            duplex_out_L = duplex_ports["outputs"][f'Output {column_index}']["L"]['id']
            duplex_out_R = duplex_ports["outputs"][f'Output {column_index}']["R"]['id']
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
                        self.app.queue.append(disconnectPipewireSourceFromPipewireDest(disconnect_L, duplex_in_L))
                        self.app.queue.append(disconnectPipewireSourceFromPipewireDest(disconnect_R, duplex_in_R))
                        self.app.queue.append(disconnectPipewireSourceFromPipewireDest(duplex_out_L, dest_L))
                        self.app.queue.append(disconnectPipewireSourceFromPipewireDest(duplex_out_R, dest_R))
                self.engine.connections[column_index]["L"] = None
                self.engine.connections[column_index]["R"] = None
                return
                
            try:
                source_instrument = self.get_instrument_for_pid(val)
                source_instrument_ports = source_instrument.engine.pw_ports
                current_instrument_ports = self.engine.pw_ports
                source_L = None
                source_R = None
                dest_L = None
                dest_R=None
                
                #We're getting IDs for left and right ports, input and output
               
                if source_instrument.name != "Overwitch":
                    for port in source_instrument_ports['output']:
                        if port.get("info", []).get("props",[]).get("audio.channel", None) == "FL":
                            source_L = port['id']
                        elif port.get("info", []).get("props",[]).get("audio.channel", None) == "FR":
                            source_R = port['id']
                else:
                    # gets the selected values for all 8 menus and assigns the right port
                    control_idx = column_index % 4
                    control =  self.controls[8 + control_idx].get_active_group()
                    control_label = control.controls[0].label
                    for port in source_instrument_ports['output']:
                        if control_label == port["info"]["props"]["port.name"]:
                            source_L = port['id']
                            source_R = port['id']
                #makes sure we don't send the same command over and over
                if source_L == self.engine.connections[column_index]["L"] and source_R == self.engine.connections[column_index]["R"]:
                    return
                
                # This bit disconnects previously conneted synth within a column
                for port in current_instrument_ports['input']:
                    if port['info']['props']['audio.channel'] == "FL":
                        dest_L = port['id']
                    elif port['info']['props']['audio.channel'] == "FR":
                        dest_R = port['id']

                if self.engine.connections[column_index]["L"] != (source_L or None)  and self.engine.connections[column_index]["R"] != (source_R or None) :
                    disconnect_L = self.engine.connections[column_index]["L"]
                    disconnect_R = self.engine.connections[column_index]["R"]
                    if disconnect_L and disconnect_R is not None:
                        self.app.queue.append(disconnectPipewireSourceFromPipewireDest(disconnect_L, duplex_in_L))
                        self.app.queue.append(disconnectPipewireSourceFromPipewireDest(disconnect_R, duplex_in_R))
                        self.app.queue.append(disconnectPipewireSourceFromPipewireDest(duplex_out_L, dest_L))
                        self.app.queue.append(disconnectPipewireSourceFromPipewireDest(duplex_out_R, dest_R))

                # Connects to currently selected instance, assigns the port IDs for later reference
                for index, connection in enumerate(self.engine.connections):
                    if index == column_index:
                        connection["L"] = source_L
                        connection["R"] = source_R
                self.app.queue.append(connectPipewireSourceToPipewireDest(source_L, duplex_in_L))
                self.app.queue.append(connectPipewireSourceToPipewireDest(source_R, duplex_in_R))
                self.app.queue.append(connectPipewireSourceToPipewireDest(duplex_out_L, dest_L))
                self.app.queue.append(connectPipewireSourceToPipewireDest(duplex_out_R, dest_R))
                print("end of try ")
            except Exception as e:
                print("Error in connect_ports_duplex in audio_in_device")
                traceback.print_exc()
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
        instruments = self.app.instruments
        external = self.app.external_instruments
        for instrument in instruments.values():
            if instrument.engine.PID == pid:
                return instrument
        for instrument in external:
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
        #This if statement is for setting post-synth volume levels
        if encoder_name == push2_python.constants.ENCODER_MASTER_ENCODER:
            instrument = self.app.osc_mode.get_current_instrument()
            all_volumes = self.app.volumes
            instrument_idx = instrument.osc_in_port % 10
            track_L_volume = all_volumes[instrument_idx * 2]
            track_R_volume = all_volumes[instrument_idx * 2 +1]
            #This specific wording of elif is needed
            # to ensure we can reach max/min values
            if track_L_volume + increment*0.01 <= 0:
                track_L_volume = 0
                track_R_volume = 0
            elif track_L_volume + increment*0.01 >=1:
                track_L_volume = 1
                track_R_volume = 1
            else:
                track_L_volume = track_L_volume + increment*0.01
                track_R_volume = track_R_volume + increment*0.01
            all_volumes[instrument_idx*2] = track_L_volume
            all_volumes[instrument_idx*2 +1] = track_R_volume
            self.app.volumes = all_volumes
            self.app.set_master_volumes()

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
            if self.app.sequencer_mode.disable_controls == False and self.app.metro_sequencer_mode.disable_controls == False:
                visible_controls = self.get_visible_controls()
                control = visible_controls[encoder_idx]
                control.update_value(increment)
                self.last_knob_turned = encoder_idx
                match encoder_idx:
                    case 2 | 3 | 4 | 5:
                        self.update_input_gains()

        
        except ValueError:
            pass  # Encoder not in list
