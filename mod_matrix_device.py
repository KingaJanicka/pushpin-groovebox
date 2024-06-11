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

    def draw(self, ctx):
        if self.is_active:
            show_text(
                ctx,
                0,
                20,
                "MOD MATRIX",
                height=25,
                font_color=definitions.BLACK,
                background_color=definitions.YELLOW,
                font_size_percentage=0.8,
                center_vertically=True,
                center_horizontally=True,
                rectangle_padding=1,
            )
            instrument = self.app.osc_mode.get_current_instrument()
            device = instrument.get_device_in_slot(1)

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
