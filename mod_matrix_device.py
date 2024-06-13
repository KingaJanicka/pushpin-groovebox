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
        self.controls = []
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
        get_color = kwargs.get("get_color")
        # # Configure controls
        # for i in range(9):
        #     control = OSCControlMenu(
        #         {"$type": "control-menu"}, get_color, self.send_message
        #     )
        #     self.controls.append(control)

        # TODO query values

    def select(self):
        print("mod matrix is active")
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

    def get_color_helper(self):
        return self.app.osc_mode.get_current_instrument_color_helper()

    def draw(self, ctx):

        devices = self.get_all_active_devices()
        selected_device = 3
        controls = self.get_controls_for_device_in_slot(selected_device)
        selected_control = 14
        self.draw_column(ctx, 3, devices, selected_device)
        self.draw_column(ctx, 4, controls, selected_control)

    def draw_column(self, ctx, offset, list, selected_idx):

        # Draw Device Names
        margin_top = 30
        next_prev_height = 15
        val_height = 25
        next_label = ""
        prev_label = ""

        try:
            prev_prev_label = list[selected_idx - 2].label
        except:
            prev_prev_label = ""

        try:
            prev_label = list[selected_idx - 1].label
        except:
            prev_label = ""

        try:
            sel_label = list[selected_idx].label
        except:
            sel_label = ""

        try:
            next_label = list[selected_idx + 1].label
        except:
            sel_label = ""

        try:
            next_next_label = list[selected_idx + 2].label
        except:
            next_next_label = ""

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
            control = visible_controls[encoder_idx]
            control.update_value(increment)
        except ValueError:
            pass  # Encoder not in list
