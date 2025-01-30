import definitions
import push2_python
import os
import json
from glob import glob
from user_interface.display_utils import show_text
from pathlib import Path
import logging

log = logging.getLogger("preset_selection_mode")

# log.setLevel(level=logging.DEBUG)


class TrigEditMode(definitions.PyshaMode):

    # xor_group = "pads"
    pad_pressing_states = {}
    last_pad_in_column_pressed = {}
    pad_quick_press_time = 0.400
    current_page = 0
    patches = {}
    state = [0] * 8
    patches_dicts = []
    current_address = None

    def initialize(self, settings=None):
        pass

    def activate(self):
        self.current_page = 0
        self.update_buttons()
        self.update_pads()

    def new_instrument_selected(self):
        self.current_page = 0
        self.app.pads_need_update = True
        self.app.buttons_need_update = True

    def should_be_enabled(self):
        return True

    def get_all_distinct_instrument_short_names_helper(self):
        return (
            self.app.instrument_selection_mode.get_all_distinct_instrument_short_names()
        )

    def get_current_instrument_short_name_helper(self):
        return self.app.instrument_selection_mode.get_current_instrument_short_name()

    def get_current_page(self):
        return self.current_page

    def activate(self):
        self.update_pads()
        self.set_knob_postions()

    def deactivate(self):
        self.app.push.pads.set_all_pads_to_color(color=definitions.BLACK)
        self.push.buttons.set_button_color(
            push2_python.constants.BUTTON_LEFT, definitions.BLACK
        )
        self.push.buttons.set_button_color(
            push2_python.constants.BUTTON_RIGHT, definitions.BLACK
        )
        self.app.buttons_need_update = True
        self.app.pads_need_update = True

    # def update_buttons(self):
    #     pass


    def update_display(self, ctx, w, h):
        # self.nested_draw(ctx, self.patches, level=0, max_height=h)
        show_text(
            ctx,
            6,
            15,
            "FART YOUR HEART OUT",
            height=15,
            font_color=definitions.WHITE,
        )


    def on_button_pressed(self, button_name):
        pass

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

            current_dict = self.patches
            for level in range(encoder_idx):
                for idx, entry in enumerate(current_dict.values()):
                    if int(self.state[level]) == idx:
                        if isinstance(entry, dict):
                            current_dict = entry

            if (
                0
                <= self.state[encoder_idx] + increment * 0.1
                < len(current_dict.keys())
            ):
                if int(self.state[encoder_idx] + increment * 0.1) != int(
                    self.state[encoder_idx]
                ):
                    for idx in range(encoder_idx + 1, 8 - encoder_idx):
                        self.state[idx] = 0

                self.state[encoder_idx] += increment * 0.1

        except ValueError:
            pass  # Encoder not in list

    def send_osc(self, *args, instrument_shortname=None):
        instrument = self.app.osc_mode.instruments.get(
            instrument_shortname or self.app.osc_mode.get_current_instrument_short_name_helper(), None
        )
        if instrument:
            return instrument.send_message(*args)
