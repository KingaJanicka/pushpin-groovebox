from display_utils import show_text
from osc_controls import (
    OSCControlMenu,
)

import push2_python
import logging
import definitions

logger = logging.getLogger("mod_matrix_device")
# logger.setLevel(level=logging.DEBUG)


class ModMatrixDevice(definitions.PyshaMode):
    @property
    def size(self):
        return 8

    def __init__(
        self,
        osc={"client": {}, "server": {}, "dispatcher": {}},
        **kwargs,
    ):
        self.app = kwargs["app"]
        self.label = ""
        self.definition = {}
        self.modmatrix = False
        self.controls = [0] * 8
        self.src_cat_column = 0
        self.src_type_column = 1
        self.device_column = 2
        self.control_column = 3
        self.page = 0
        self.slot = None
        self.osc = osc
        self.label = "Mod Matrix"
        self.dispatcher = osc.get("dispatcher", None)
        self.slot = None
        self.log_in = logger.getChild(f"in-{kwargs['osc_in_port']}")
        self.log_out = logger.getChild(f"out-{kwargs['osc_out_port']}")
        self.init = []
        self.is_active = False
        self.all_active_devices = []

        # TODO: Move those to JSON or sth, super ugly and unruly here
        self.mod_sources_macros = [
            {"address": "/mod/macro_1", "label": "Macro 1"},
            {"address": "/mod/macro_2", "label": "Macro 2"},
            {"address": "/mod/macro_3", "label": "Macro 3"},
            {"address": "/mod/macro_4", "label": "Macro 4"},
            {"address": "/mod/macro_5", "label": "Macro 5"},
            {"address": "/mod/macro_6", "label": "Macro 6"},
            {"address": "/mod/macro_7", "label": "Macro 7"},
            {"address": "/mod/macro_8", "label": "Macro 8"},
        ]
        self.mod_sources_internal = [
            {"address": "/mod/at", "label": "Aftertouch"},
            {"address": "/mod/breath", "label": "Breath"},
            {"address": "/mod/expr", "label": "Expression"},
            {"address": "/mod/sus", "label": "Sustain"},
            {"address": "/mod/pb", "label": "Pitch Bend"},
            {"address": "/mod/vel", "label": "Velocity"},
            {"address": "/mod/rel_vel", "label": "Release Vel"},
            {"address": "/mod/keytrk", "label": "Keytrack"},
            {"address": "/mod/pat", "label": "Poly AT"},
            {"address": "/mod/timbre", "label": "Timbre"},
            {"address": "/mod/mw", "label": "ModWheel"},
            {"address": "/mod/alt_bi", "label": "Alt Bipolar"},
            {"address": "/mod/alt_uni", "label": "Alt Unipol."},
            {"address": "/mod/rand_bi/0", "label": "Rand Bi 0"},
            {"address": "/mod/rand_uni/0", "label": "Rand Uni 0"},
            {"address": "/mod/rand_bi/1", "label": "Rand Bi 1"},
            {"address": "/mod/a/lowest_key", "label": "Lowest Key"},
            {"address": "/mod/a/highest_key", "label": "Highest Key"},
            {"address": "/mod/a/latest_key", "label": "Latest Key"},
        ]
        self.mod_sources_lfos = [
            {"address": "/mod/a/feg", "label": "Filter EG"},
            {"address": "/mod/a/aeg", "label": "Amp EG"},
            {"address": "/mod/a/slfo_1/0", "label": "LFO1"},
            {"address": "/mod/a/slfo_1/1", "label": "LFO1 Raw WF"},
            {"address": "/mod/a/slfo_1/2", "label": "LFO1 EG Only"},
            {"address": "/mod/a/slfo_2/0", "label": "LFO2"},
            {"address": "/mod/a/slfo_2/1", "label": "LFO2 Raw WF"},
            {"address": "/mod/a/slfo_2/2", "label": "LFO2 EG Only"},
            {"address": "/mod/a/slfo_3/0", "label": "LFO3"},
            {"address": "/mod/a/slfo_3/1", "label": "LFO3 Raw WF"},
            {"address": "/mod/a/slfo_3/2", "label": "LFO3 EG Only"},
            {"address": "/mod/a/slfo_4/0", "label": "LFO4"},
            {"address": "/mod/a/slfo_4/1", "label": "LFO4 Raw WF"},
            {"address": "/mod/a/slfo_4/2", "label": "LFO4 EG Only"},
            {"address": "/mod/a/slfo_5/0", "label": "LFO5"},
            {"address": "/mod/a/slfo_5/1", "label": "LFO5 Raw WF"},
            {"address": "/mod/a/slfo_5/2", "label": "LFO5 EG Only"},
            {"address": "/mod/a/slfo_6/0", "label": "LFO6"},
            {"address": "/mod/a/slfo_6/1", "label": "LFO6 Raw WF"},
            {"address": "/mod/a/slfo_6/2", "label": "LFO6 EG Only"},
        ]
        self.all_mod_src = [
            {"values": self.mod_sources_macros, "label": "Macros"},
            {"values": self.mod_sources_internal, "label": "Internal"},
            {"values": self.mod_sources_lfos, "label": "LFOs"},
        ]

        get_color = kwargs.get("get_color")
        # # Configure controls
        # for i in range(9):
        #     control = OSCControlMenu(
        #         {"$type": "control-menu"}, get_color, self.send_message
        #     )
        #     self.controls.append(control)

        # TODO: make those actually work
        self.map_dispatchers()
        print(self.mod_sources_macros[0]["address"])

    def map_dispatchers(self):
        for source in self.mod_sources_macros:
            self.dispatcher.map(source["address"], self.set_state)

        for source in self.mod_sources_internal:
            self.dispatcher.map(source["address"], self.set_state)

        for source in self.mod_sources_lfos:
            self.dispatcher.map(source["address"], self.set_state)

    def set_state(self, address, *args):
        print("set state")
        value, depth, *rest = args
        # self.log.debug((address, value))
        # self.value = value

    def select(self):
        self.is_active = True

    def send_message(self, *args):
        self.log_out.debug(args)
        return self.osc["client"].send_message(*args)

    def query(self):
        pass

    def query_all(self):
        self.send_message("/q/all_mods")

    def get_all_active_devices(self):
        instrument = self.app.osc_mode.get_current_instrument()
        devices = self.app.osc_mode.get_current_instrument_devices()
        return devices

    def get_all_mod_matrix_devices(self):
        instrument = self.app.osc_mode.get_current_instrument()
        devices = self.app.osc_mode.get_current_instrument_devices()
        for device in devices.copy():
            if device.modmatrix == False:
                devices.remove(device)
        return devices

    def get_device_in_slot(self, slot):
        instrument = self.app.osc_mode.get_current_instrument()
        devices = self.app.osc_mode.get_current_instrument_devices()
        for device in devices:
            if device.slot == slot:
                return device

    def get_controls_for_device_in_slot(self, slot):
        instrument = self.app.osc_mode.get_current_instrument()
        devices = self.app.osc_mode.get_current_instrument_devices()
        for device in devices:
            if device.slot == slot:
                controls = device.get_all_controls()
                return controls

    def get_all_mod_matrix_controls_for_device_in_slot(self, slot):
        instrument = self.app.osc_mode.get_current_instrument()
        devices = self.app.osc_mode.get_current_instrument_devices()
        for device in devices:
            if device.slot == slot:
                controls = device.get_all_controls()
                for control in controls.copy():
                    if control.modmatrix == False:
                        controls.remove(control)
                return controls

    def get_color_helper(self):
        return self.app.osc_mode.get_current_instrument_color_helper()

    def draw(self, ctx):
        # TODO: we keep accessing out of range I think
        selected_src_cat = int(self.controls[self.src_cat_column])
        selected_src_type = int(self.controls[self.src_type_column])
        devices = self.get_all_mod_matrix_devices()
        selected_device = int(self.controls[self.device_column])
        controls = self.get_all_mod_matrix_controls_for_device_in_slot(selected_device)
        selected_control = int(self.controls[self.control_column])
        # TODO: those src draws are borked, it's my shitty data structure at work
        self.draw_src_column(
            ctx, self.src_cat_column, self.all_mod_src, selected_src_cat
        )
        self.draw_src_column(
            ctx,
            self.src_cat_column + 1,
            self.all_mod_src[selected_src_cat]["values"],
            selected_src_type,
        )
        self.draw_dest_column(ctx, self.device_column, devices, selected_device)
        self.draw_dest_column(ctx, self.control_column, controls, selected_control)

    def draw_src_column(self, ctx, offset, list, selected_idx):
        # Draw Device Names
        margin_top = 30
        next_prev_height = 15
        val_height = 25
        next_label = ""
        prev_label = ""

        # TODO: is this busted?
        if 0 > selected_idx - 2:
            prev_prev_label = " "
        else:
            prev_prev_label = list[selected_idx - 2]["label"]

        if 0 > selected_idx - 1:
            prev_label = " "
        else:
            prev_label = list[selected_idx - 1]["label"]

        try:
            sel_label = list[selected_idx]["label"]
        except:
            sel_label = " "

        try:
            next_label = list[selected_idx + 1]["label"]
        except:
            next_label = " "

        try:
            next_next_label = list[selected_idx + 2]["label"]
        except:
            next_next_label = " "

        # Prev Prev device
        show_text(
            ctx,
            offset,
            margin_top,
            prev_prev_label,
            height=next_prev_height,
            font_color=definitions.WHITE,
        )

        # Prev device
        show_text(
            ctx,
            offset,
            margin_top + next_prev_height,
            prev_label,
            height=next_prev_height,
            font_color=definitions.WHITE,
        )

        # Cur sel value
        color = self.get_color_helper()
        show_text(
            ctx,
            offset,
            margin_top + 2 * next_prev_height,
            sel_label,
            height=val_height,
            font_color=color,
        )

        # Next name
        show_text(
            ctx,
            offset,
            margin_top + 2 * next_prev_height + val_height,
            next_label,
            height=next_prev_height,
            font_color=definitions.WHITE,
        )

        # Next Next name
        show_text(
            ctx,
            offset,
            margin_top + 3 * next_prev_height + val_height,
            next_next_label,
            height=next_prev_height,
            font_color=definitions.WHITE,
        )

    def draw_dest_column(self, ctx, offset, list, selected_idx):
        # Draw Device Names
        margin_top = 30
        next_prev_height = 15
        val_height = 25
        next_label = ""
        prev_label = ""

        # TODO: is this busted?

        if 0 > selected_idx - 2:
            prev_prev_label = " "
        else:
            prev_prev_label = list[selected_idx - 2].label

        if 0 > selected_idx - 1:
            prev_label = " "
        else:
            prev_label = list[selected_idx - 1].label

        try:
            sel_label = list[selected_idx].label
        except:
            sel_label = " "

        try:
            next_label = list[selected_idx + 1].label
        except:
            next_label = " "

        try:
            next_next_label = list[selected_idx + 2].label
        except:
            next_next_label = " "

        # Prev Prev device
        show_text(
            ctx,
            offset,
            margin_top,
            prev_prev_label,
            height=next_prev_height,
            font_color=definitions.WHITE,
        )

        # Prev device
        show_text(
            ctx,
            offset,
            margin_top + next_prev_height,
            prev_label,
            height=next_prev_height,
            font_color=definitions.WHITE,
        )

        # Cur sel value
        color = self.get_color_helper()
        show_text(
            ctx,
            offset,
            margin_top + 2 * next_prev_height,
            sel_label,
            height=val_height,
            font_color=color,
        )

        # Next name
        show_text(
            ctx,
            offset,
            margin_top + 2 * next_prev_height + val_height,
            next_label,
            height=next_prev_height,
            font_color=definitions.WHITE,
        )

        # Next Next name
        show_text(
            ctx,
            offset,
            margin_top + 3 * next_prev_height + val_height,
            next_next_label,
            height=next_prev_height,
            font_color=definitions.WHITE,
        )

    def get_next_prev_pages(self):
        return False, False

    def set_page(self, page):
        self.select()

    def query_visible_controls(self):
        pass

    def query_all_controls(self):
        pass

    def get_visible_controls(self):
        return self.controls

    def get_all_controls(self):
        return self.controls

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
            new_value = visible_controls[encoder_idx] + increment * 0.1
            # TODO: This will need to be more complex later but works for testing
            devices = self.get_all_mod_matrix_devices()
            selected_device = int(self.controls[self.device_column])
            controls = self.get_all_mod_matrix_controls_for_device_in_slot(
                selected_device
            )

            if encoder_idx == self.src_cat_column and 0 < new_value <= len(
                self.all_mod_src
            ):
                if int(visible_controls[encoder_idx]) - int(new_value) != 0:
                    visible_controls[self.src_type_column] = 0
                visible_controls[encoder_idx] = new_value
            if encoder_idx == self.src_type_column and 0 < new_value <= len(
                self.all_mod_src[int(visible_controls[0])]["values"]
            ):
                visible_controls[encoder_idx] = new_value

            if encoder_idx == self.device_column and 0 < new_value <= len(devices):
                if int(visible_controls[encoder_idx]) - int(new_value) != 0:
                    visible_controls[self.src_type_column] = 0
                visible_controls[encoder_idx] = new_value
            if encoder_idx == self.control_column and 0 < new_value <= len(controls):
                visible_controls[encoder_idx] = new_value

        except ValueError as e:
            print(e)
            print("ValueError as e in ModMatrix")
