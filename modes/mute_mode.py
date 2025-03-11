import definitions
from controllers import push2_constants
import push2_python
from modes.melodic_mode import MelodicMode
import isobar as iso
import os
import sys
import time
from user_interface.display_utils import show_text
from osc_controls import (
    OSCControl,
    ControlSpacer,
    OSCControlSwitch,
    OSCGroup,
)
from modes.sequencer_mode import TRACK_COLORS
from definitions import TRACK_NAMES

track_button_names = [
    push2_python.constants.BUTTON_1_32T,
    push2_python.constants.BUTTON_1_32,
    push2_python.constants.BUTTON_1_16T,
    push2_python.constants.BUTTON_1_16,
    push2_python.constants.BUTTON_1_8T,
    push2_python.constants.BUTTON_1_8,
    push2_python.constants.BUTTON_1_4T,
    push2_python.constants.BUTTON_1_4,
]


class MuteMode(MelodicMode):
    sequencer_pad_matrix = [
        range(92, 100),
        range(84, 92),
        range(76, 84),
        range(68, 76),
        range(60, 68),
        range(52, 60),
        range(44, 52),
        range(36, 44),
    ]

    current_selected_section_and_page = {}
    pads_press_time = [False] * 64
    pad_quick_press_time = 0.400
    disable_controls = False
    tracks_active ={}
    
    def initialize(self, settings):
        super().initialize(settings)
    
        for (
            instrument_short_name
        ) in self.get_all_distinct_instrument_short_names_helper():
            self.tracks_active[instrument_short_name] = {}
            for track_name in TRACK_NAMES:
                self.tracks_active[instrument_short_name][track_name] = True

    def get_settings_to_save(self):
        return {}

    def pad_ij_to_midi_note(self, pad_ij):
        return self.sequencer_pad_matrix[pad_ij[0]][pad_ij[1]]

    def update_octave_buttons(self):
        # Rhythmic does not have octave buttons
        pass

    def get_all_distinct_instrument_short_names_helper(self):
        return (
            self.app.instrument_selection_mode.get_all_distinct_instrument_short_names()
        )

    def get_current_instrument_short_name_helper(self):
        return self.app.instrument_selection_mode.get_current_instrument_short_name()

    def get_current_instrument_osc_port(self):
        return self.app.instrument_selection_mode.get_current_instrument_info()[
            "osc_out_port"
        ]

    def get_current_instrument_color_helper(self):
        return self.app.instrument_selection_mode.get_current_instrument_color()

    def new_instrument_selected(self):
        pass

    def update_display(self, ctx, w, h):
        pass

    def update_pads(self):
        try:
            instrument_name = self.get_current_instrument_short_name_helper()
            seq_pad_state = self.tracks_active
            button_colors = [definitions.OFF_BTN_COLOR] * 64
            # Takes state of mutes and lights up the pads accordingly
            for (inst_index, 
                instrument_short_name
                ) in enumerate(self.get_all_distinct_instrument_short_names_helper()):
                for track_index, track_name in enumerate(TRACK_NAMES):
                    pad_idx = inst_index + 8 * track_index

                    if self.tracks_active[instrument_short_name][track_name] == True:
                        button_colors[pad_idx] = TRACK_COLORS[track_name]
                    elif self.tracks_active[instrument_short_name][track_name] == False:
                        button_colors[pad_idx] = definitions.BLACK


            # makes the values into a multi-dimensional array
            button_colors_array = []

            while button_colors:
                chunk, button_colors = button_colors[:8], button_colors[8:]
                button_colors_array.append(chunk)

            self.push.pads.set_pads_color(button_colors_array)
        except Exception as exception:
            exception_message = str(exception)
            exception_type, exception_object, exception_traceback = sys.exc_info()
            filename = os.path.split(exception_traceback.tb_frame.f_code.co_filename)[1]

            print(
                f"{exception_message} {exception_type} {filename}, Line {exception_traceback.tb_lineno}"
            )

    def on_pad_pressed(self, pad_n, pad_ij, velocity):

        for (inst_index, 
                instrument_short_name
                ) in enumerate(self.get_all_distinct_instrument_short_names_helper()):
                for track_index, track_name in enumerate(TRACK_NAMES):
                    # print(pad_ij[1], inst_index, "ssss",pad_ij[0], track_index)
                    if pad_ij[1] == inst_index and pad_ij[0] == track_index:
                        # If a pad is off, turn it on
                        if self.tracks_active[instrument_short_name][track_name] == False:
                            self.tracks_active[instrument_short_name][track_name] = True

                        # If it's on, turn if off
                        elif self.tracks_active[instrument_short_name][track_name] == True:
                            self.tracks_active[instrument_short_name][track_name] = False
        self.app.pads_need_update = True

    