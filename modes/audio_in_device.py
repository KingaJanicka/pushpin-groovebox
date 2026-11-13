from osc_controls import (
    OSCControl,
    ControlSpacer,
    OSCControlSwitch,
    OSCGroup,
)
import copy
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

# Page 2's source switches: a group per source, its onselect value the
# source's index in AudioInDevice.sources
SOURCE_ADDRESS = "/route"
NO_SOURCE_ADDRESS = "/"
NO_SOURCE_LABEL = "None sel."


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
        self.page_one_controls = []
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
        self.switches = []
        self.sources = []
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
        self.page_one_controls.append(audio_channel_control)

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
        self.page_one_controls.append(audio_gain_control)

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
        self.page_one_controls.append(in_1_gain)

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
        self.page_one_controls.append(in_2_gain)

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
        self.page_one_controls.append(in_3_gain)
        
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
        self.page_one_controls.append(in_4_gain)

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
        self.page_one_controls.append(low_cut_control)

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
        self.page_one_controls.append(high_cut_control)
        self.gain_controls = [in_1_gain, in_2_gain, in_3_gain, in_4_gain]
        for control in self.get_visible_controls():
            if hasattr(control, "select"):
                control.select()
        # self.update()

    def update(self):
        """Rebuild page 2: a source switch (and its menu) for each of this
        device's 4 duplex columns, each showing what the column is linked to."""
        self.controls.clear()
        for control in self.page_one_controls:
            self.controls.append(control)
        name = self.engine.instrument["instrument_name"]
        control_def = {
            "$type": "control-switch",
            "label": name,
            "groups": [{
                "$type": "group",
                "label": NO_SOURCE_LABEL,
                "onselect": {
                    "$type": "message",
                    "$comment": "Disconnect the column",
                    "address": NO_SOURCE_ADDRESS,
                    "value": 0,
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
                                    "$comment": "Disconnect the column",
                                    "address": NO_SOURCE_ADDRESS,
                                    "value": 0,
                                },
                            },
                        ],
                    }
                ],
            }],
        }

        # A source is named by its place in self.sources, not its engine's PID:
        # every mono2k track plays in the same m2k-jack process.
        self.sources = list(self.app.instruments.values())
        for index, instrument in enumerate(self.sources):
            control_def["groups"].append({
                "$type": "group",
                "label": f'{instrument.name}',
                "onselect": {
                    "$type": "message",
                    "$comment": "",
                    "address": SOURCE_ADDRESS,
                    "value": index,
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
                                    "$comment": "",
                                    "address": SOURCE_ADDRESS,
                                    "value": index,
                                },
                            },
                        ],
                    }
                ],
            })

        overwitch = self.app.external_instruments[0] if self.app.external_instruments else None
        if overwitch is not None and overwitch.engine.PID is not None:
            index = len(self.sources)
            self.sources.append(overwitch)
            control_def["groups"].append({
                "$type": "group",
                "label": f'{overwitch.name}',
                "onselect": {
                    "$type": "message",
                    "$comment": "",
                    "address": SOURCE_ADDRESS,
                    "value": index,
                },
                "controls": [
                    {
                        "$type": "control-menu",
                        # Each item is one of Overwitch's (mono) outputs; the
                        # column takes the item showing on the menu
                        "items": [
                            {
                                "$type": "menu-item",
                                "label": port["info"]["props"]["port.name"],
                                "onselect": {
                                    "$type": "message",
                                    "$comment": "",
                                    "address": SOURCE_ADDRESS,
                                    "value": index,
                                },
                            }
                            for port in overwitch.engine.pw_ports["output"]
                        ],
                    }
                ],
            })

        self.switches = []
        for column_offset in range(4):
            try:
                switch = OSCControlSwitch(
                    control_def, self.get_color, self.connect_ports_duplex, self.dispatcher
                )
            except Exception:
                logger.exception("Audio In: building the source switch failed")
                continue
            self.show_routing(switch, self.column_for(column_offset))
            self.switches.append(switch)
            self.controls.append(switch)

    def show_routing(self, switch, column):
        """Point a freshly built switch at what its column is linked to."""
        connection = self.engine.connections[column]
        source = connection.get("source")
        if source is None:
            return
        labels = [group.label for group in switch.groups]
        if source not in labels:
            return
        idx = labels.index(source)
        switch.value = float(idx)
        switch.knob_value = float(idx)
        port_label = connection.get("port")
        if port_label is not None:
            menu = switch.groups[idx].controls[0]
            items = [item.label for item in menu.items]
            if port_label in items:
                menu.value = items.index(port_label)

    def empty_func(self, *args):
        pass

    async def select(self):
        # self.query_visible_controls()
        self.update()
        for cmd in self.init:
            self.send_message(cmd["address"], float(cmd["value"]))
            await asyncio.sleep(0.2)

    async def spawn_puredata_node(self):
        instrument_name = self.app.instrument_selection_mode.get_current_instrument_short_name()
        await self.app.instruments[instrument_name].engine.start_pd_node()
        await self.app.instruments[instrument_name].engine.configure_pipewire()

    async def kill_puredata_node(self):
        instrument_name = self.app.instrument_selection_mode.get_current_instrument_short_name()
        await self.app.instruments[instrument_name].engine.kill_pd_node()

    def select_sync(self):
        # self.query_visible_controls()
        self.update()
        for cmd in self.init:
            self.send_message(cmd["address"], float(cmd["value"]))

    def send_message(self, *args):
        self.log_out.debug(args)
        return self.osc["client"].send_message(*args)

    def set_duplex_volumes(self, *args):
        """An "In N Gain" knob moved: send every column's level to the duplex
        node (each column is a stereo pair of its channels)."""
        # The knob has its new value already; the gains must follow it before
        # they're sent, or the node gets the knob's previous value
        self.update_input_gains()
        client = self.engine.duplex_node_osc_client
        if client is None:
            return
        for column, gain in enumerate(self.input_gains):
            volume_value = float(gain or 0.0)
            client.send_message(f"/vol_{2 * column}", volume_value)
            client.send_message(f"/vol_{2 * column + 1}", volume_value)

    def update_input_gains(self):
        """Collect the track's 8 column gains: slot 0's Audio In device has
        columns 0-3, slot 1's columns 4-7. Both devices share the result."""
        devices = self.app.osc_mode.get_current_instrument_devices()
        audio_ins = [d for d in devices if isinstance(d, AudioInDevice)]
        if self not in audio_ins:
            audio_ins.append(self)
        gains = [None] * 8
        for device in audio_ins:
            base = 4 * (device.slot or 0)
            for offset, control in enumerate(device.gain_controls):
                gains[base + offset] = control.value
        for device in audio_ins:
            device.input_gains[:] = gains

    def column_for(self, column_offset):
        """Duplex column of this device's ``column_offset``-th switch (0-3)."""
        return column_offset + 4 * (self.slot or 0)

    def source_ports(self, source, column):
        """(L, R) PipeWire port ids that ``source`` feeds a column with, or None."""
        if source is None:
            return None
        if source in self.app.external_instruments:
            # Overwitch: the mono output its menu shows, to both sides
            switch = self.switches[column % 4]
            item = switch.get_active_group().controls[0].get_active_menu_item()
            if item is None:
                return None
            for port in source.engine.pw_ports["output"]:
                if port["info"]["props"].get("port.name") == item.label:
                    return port["id"], port["id"]
            return None
        eng = source.engine
        out_L_name, out_R_name = eng.output_port_names
        source_L = next((p["id"] for p in eng.pw_ports["output"] if eng.port_is(p, (out_L_name,))), None)
        source_R = next((p["id"] for p in eng.pw_ports["output"] if eng.port_is(p, (out_R_name,))), None)
        if source_L is None or source_R is None:
            return None
        return source_L, source_R

    def connect_ports_duplex(self, *args):
        """A column's source switch or menu changed: link the chosen source's
        outputs into that column's duplex input (unlinking the old source).

        The duplex outputs are linked to Surge's input once, when the node
        starts (SurgeXTEngine.connect_links_to_duplex_node), and stay linked:
        the app queue runs its tasks concurrently, so unlinking and relinking
        an output here could leave it unlinked.
        """
        addr, val, *rest = args
        # Switches and menus also ask for "/q..." with no value
        if val is None or addr not in (SOURCE_ADDRESS, NO_SOURCE_ADDRESS):
            return
        column = self.column_for(int(self.last_knob_turned / 2))

        duplex_in = self.engine.duplex_ports["inputs"][f"Input {column}"]
        if not duplex_in["L"] or not duplex_in["R"]:
            logger.warning("Audio In: the duplex node isn't up; can't route column %s", column)
            return
        duplex_in_L = duplex_in["L"]["id"]
        duplex_in_R = duplex_in["R"]["id"]

        source_label = None
        port_label = None
        new_L = new_R = None
        if addr == SOURCE_ADDRESS:
            idx = int(val)
            source = self.sources[idx] if 0 <= idx < len(self.sources) else None
            ports = self.source_ports(source, column)
            if ports is None:
                logger.warning("Audio In: no output ports for source %s", getattr(source, "name", val))
                return
            new_L, new_R = ports
            source_label = source.name
            if source in self.app.external_instruments:
                port_label = self.switches[column % 4].get_active_group().controls[0].label

        connection = self.engine.connections[column]
        old_L, old_R = connection["L"], connection["R"]
        if (old_L, old_R) == (new_L, new_R):
            return

        if old_L is not None and old_R is not None:
            self.app.queue.append(disconnectPipewireSourceFromPipewireDest(old_L, duplex_in_L))
            self.app.queue.append(disconnectPipewireSourceFromPipewireDest(old_R, duplex_in_R))

        connection["L"], connection["R"] = new_L, new_R
        connection["source"] = source_label
        connection["port"] = port_label
        if new_L is not None and new_R is not None:
            self.app.queue.append(connectPipewireSourceToPipewireDest(new_L, duplex_in_L))
            self.app.queue.append(connectPipewireSourceToPipewireDest(new_R, duplex_in_R))


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
        if encoder_name == push2_python.constants.ENCODER_SWING_ENCODER:
            instrument = self.app.osc_mode.get_current_instrument()
            self.app.adjust_track_volume(instrument, increment)

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
            if self.app.metro_sequencer_mode.disable_controls == False:
                visible_controls = self.get_visible_controls()
                control = visible_controls[encoder_idx]
                # Before update_value: a source switch's callback routes the
                # column of the knob being turned
                self.last_knob_turned = encoder_idx
                control.update_value(increment)
        
        except ValueError:
            pass  # Encoder not in list
    def on_encoder_released(self, encoder_name):
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
            if self.page == 1:
                # try:
                #     self.connect_ports_duplex("Dummy", "dummy")
                # except Exception as e:
                #     print(e)
                # print("after connect")
                pass
        
        except ValueError:
            pass
