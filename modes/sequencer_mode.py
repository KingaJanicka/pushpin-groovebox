import definitions
from controllers import push2_constants
import push2_python
from sequencer.sequencer import Sequencer
from modes.melodic_mode import MelodicMode
import isobar as iso
import os
import sys
import time
import json
import traceback
from user_interface.display_utils import show_text
from osc_controls import (
    OSCControl,
    ControlSpacer,
    OSCControlSwitch,
    OSCGroup,
)
from definitions import TRACK_NAMES, USER_CONFIG_FOLDER

EMPTY_PATTERN = []

TRACK_COLORS = {
    "gate_1": definitions.BLUE,
    "pitch_1": definitions.GREEN,
    "trig_mute_1": definitions.RED,
    "accent_1": definitions.YELLOW,
    "aux_1": definitions.CYAN,
    "aux_2": definitions.CYAN,
    "aux_3": definitions.CYAN,
    "aux_4": definitions.CYAN,
}

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


class SequencerMode(MelodicMode):
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

    playhead = 0
    seq_tick = 0
    timeline_is_playing = False
    current_selected_section_and_page = {}
    instrument_sequencers = {}
    tempo = 120
    show_scale_menu = False
    timeline = iso.Timeline(tempo, output_device=iso.DummyOutputDevice())
    selected_track = "gate_1"
    scale_menu_filename = f"{USER_CONFIG_FOLDER}/scale_menu.json"
    pads_press_time = [False] * 64
    pad_quick_press_time = 0.400
    disable_controls = False
    instrument_scale_edit_controls = {}
    scale_edit_controls = []

    def initialize(self, settings):
        super().initialize(settings)
        for (
            instrument_short_name
        ) in self.get_all_distinct_instrument_short_names_helper():
            self.instrument_sequencers[instrument_short_name] = Sequencer(
                instrument_short_name,
                self.timeline,
                self.sequencer_on_tick,
                self.playhead,
                self.send_osc_func,
                self.app,
            )
            self.instrument_scale_edit_controls[instrument_short_name] = {}
            for track_name in TRACK_NAMES:
                menu = []

                len = OSCControl(
                    {
                        "$type": "control-range",
                        "label": "Steps",
                        "address": f"/",
                        "min": 0,
                        "max": 64,
                    },
                    self.get_current_instrument_color_helper,
                    None,
                )
                len.value = 64
                menu.append(len)
                self.instrument_scale_edit_controls[instrument_short_name][
                    track_name
                ] = menu
                
    def load_state(self):
        # Loads seq state
        for (
            instrument_short_name
        ) in self.get_all_distinct_instrument_short_names_helper():
            self.instrument_sequencers[instrument_short_name].load_state()

        # Loads Trig edit state
        self.app.trig_edit_mode.load_state()

        # # Loads Osc mode state
        # self.app.osc_mode.load_state()

        # Loads scale edit menu
        try:
            dump = None
            if os.path.exists(self.scale_menu_filename):
                dump = json.load(open(self.scale_menu_filename))
                for (
                    instrument_short_name
                ) in self.get_all_distinct_instrument_short_names_helper():
                    for track_name in TRACK_NAMES:
                        for idx, control in enumerate(
                            self.instrument_scale_edit_controls[instrument_short_name][
                                track_name
                            ]
                        ):
                            control.value = dump[instrument_short_name][track_name][idx]
        except Exception as e:
            print("Exception in sequencer_mode, load_state")
            traceback.print_exc()

    def save_state(self):
        # Saves seq state
        scale_edit_state = {}
        try:
            for (
                instrument_short_name
            ) in self.get_all_distinct_instrument_short_names_helper():

                self.instrument_sequencers[instrument_short_name].save_state()
                scale_edit_state[instrument_short_name] = {}
                # Populates the temp scale_edit_state array with current state
                for track_name in TRACK_NAMES:
                    scale_edit_state[instrument_short_name][track_name] = [
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                    ]
                    for index, control in enumerate(
                        self.instrument_scale_edit_controls[instrument_short_name][
                            track_name
                        ]
                    ):
                        scale_edit_state[instrument_short_name][track_name][
                            index
                        ] = control.value
        except Exception as e:
            print("Error in saving scale_edit state")
            traceback.print_exc()
        # Saves scale edit menu
        try:
            json.dump(
                scale_edit_state, open(self.scale_menu_filename, "w")
            )  # Save to file
        except Exception as e:
            print("Exception in trig_edit save_state")
            traceback.print_exc()

        # Saves Trig edit state
        self.app.trig_edit_mode.save_state()
        
        # # Saves Osc mode state
        # self.app.osc_mode.save_state()


    def start_timeline(self):
        for (
            instrument_short_name
        ) in self.get_all_distinct_instrument_short_names_helper():
            self.instrument_sequencers[
                instrument_short_name
            ].local_timeline.background()

        self.timeline.background()

    def stop_timeline(self):
        for (
            instrument_short_name
        ) in self.get_all_distinct_instrument_short_names_helper():
            self.instrument_sequencers[instrument_short_name].local_timeline.stop()

        self.timeline.stop()

    def get_settings_to_save(self):
        return {}

    def pad_ij_to_midi_note(self, pad_ij):
        return self.sequencer_pad_matrix[pad_ij[0]][pad_ij[1]]

    def update_octave_buttons(self):
        # Rhythmic does not have octave buttons
        pass
    
    
    def sequencer_on_tick(self, instrument_name, length):
        # if seq is active
        if self.app.is_mode_active(self.app.sequencer_mode):
            self.update_pads()
            self.app.trig_edit_mode.update_button_colours()
        if self.get_current_instrument_short_name_helper() == instrument_name:
            self.playhead = self.instrument_sequencers[instrument_name].playhead

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
        instrument_index = self.app.instrument_selection_mode.selected_instrument % 8
        instrument_index = int(
            (self.app.instrument_selection_mode.selected_instrument - instrument_index)
            / 8
        )

        self.selected_instrument = TRACK_NAMES[0]

        device = self.app.osc_mode.get_current_instrument_device()
        device.disable_controls = self.disable_controls
        # print(self.selected_instrument)
        # print(self.app.osc_mode.get_current_instrument_osc_address_sections())

    def update_display(self, ctx, w, h):
        if self.show_scale_menu == True:
            background_colour = self.get_current_instrument_color_helper()
            instrument_name = self.get_current_instrument_short_name_helper()
            track_name = self.selected_track
            track_controls = self.instrument_scale_edit_controls[instrument_name][
                track_name
            ]
            # ctx.save()
            ctx.move_to(0, 0)
            ctx.line_to(0, 135)
            ctx.line_to(960, 135)
            ctx.line_to(960, 0)
            ctx.set_source_rgb(255, 0, 0)
            ctx.close_path()
            ctx.fill_preserve()
            offset = 0
            for control in track_controls:
                control.draw(ctx, offset)
                offset += 1

            show_text(
                ctx,
                1,
                20,
                instrument_name,
                height=30,
                font_color=definitions.WHITE,
                background_color=background_colour,
                font_size_percentage=0.8,
                center_vertically=True,
                center_horizontally=True,
                rectangle_padding=1,
            )
            show_text(
                ctx,
                2,
                20,
                track_name,
                height=30,
                font_color=definitions.WHITE,
                background_color=background_colour,
                font_size_percentage=0.8,
                center_vertically=True,
                center_horizontally=True,
                rectangle_padding=1,
            )
            # ctx.restore()

    def update_pads(self):
        try:
            instrument_name = self.get_current_instrument_short_name_helper()
            seq = self.instrument_sequencers[instrument_name]
            seq_pad_state = seq.get_track(self.selected_track)
            button_colors = [definitions.OFF_BTN_COLOR] * len(seq_pad_state)
            selected_track_controls = self.instrument_scale_edit_controls[
                instrument_name
            ][self.selected_track]
            track_length = selected_track_controls[0]
            for i, value in enumerate(seq.get_track(self.selected_track)):

                if i < int(track_length.value):
                    if value:
                        button_colors[i] = TRACK_COLORS[self.selected_track]

                    # Set pad colours for on/off states of the seq
                    if seq_pad_state[i] is True:
                        button_colors[i] = TRACK_COLORS[self.selected_track]

                    if seq_pad_state[i] is False:
                        button_colors[i] = definitions.OFF_BTN_COLOR
                # Turn pads that are outside the bounds of the sequence black/off
                else:
                    button_colors[i] = definitions.BLACK

            # Draw the playhead
            if self.timeline_is_playing == True:
                step = seq.playhead % int(track_length.value)
                button_colors[step] = definitions.WHITE

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
        seq = self.instrument_sequencers[
            self.get_current_instrument_short_name_helper()
        ]
        seq_pad_state = seq.get_track(self.selected_track)
        idx = pad_n - 36
        idx = pad_ij[0] * 8 + pad_ij[1]
        self.app.steps_held.append(idx)
        # If a pad is off, turn it on
        if seq_pad_state[idx] == False:
            seq.set_state(self.selected_track, idx, True)
            self.app.pads_need_update = True

        # If it's on, save the time and cont in on_pad_released
        elif seq_pad_state[idx] == True:
            self.pads_press_time[idx] = time.time()
            # call func to show lock here

    def on_pad_released(self, pad_n, pad_ij, velocity):
        seq = self.instrument_sequencers[
            self.get_current_instrument_short_name_helper()
        ]
        seq_pad_state = seq.get_track(self.selected_track)
        idx = pad_ij[0] * 8 + pad_ij[1]
        epoch_time = time.time()
        press_time = epoch_time - self.pads_press_time[idx]
        # Short Press - turn the pad off, reset the timer
        if (
            press_time <= self.pad_quick_press_time
            and self.pads_press_time[idx] != False
        ):
            seq.set_state(self.selected_track, idx, False)
            self.pads_press_time[idx] = False

        # Long Press - keep the pad on, trigger a lock preview
        elif press_time > self.pad_quick_press_time:
            pass
            # seq.set_state(self.selected_track, idx, False

        self.app.steps_held.remove(idx)
        self.save_state()
        self.app.pads_need_update = True

    def on_button_pressed(self, button_name):
        seq = self.instrument_sequencers[
            self.get_current_instrument_short_name_helper()
        ]
        if button_name in track_button_names:
            idx = track_button_names.index(button_name)
            self.selected_track = TRACK_NAMES[idx]
            self.app.trig_edit_mode.update_state()
            self.app.buttons_need_update = True
            self.app.pads_need_update = True

        elif (
            button_name == push2_constants.BUTTON_OCTAVE_UP
            or button_name == push2_constants.BUTTON_OCTAVE_DOWN
        ):
            # Don't react to octave up/down buttons as these are not used in rhythm mode
            pass
        elif button_name == push2_constants.BUTTON_DELETE:

            self.selected_track = TRACK_NAMES[6]
        elif button_name == push2_constants.BUTTON_PLAY:
            if self.timeline_is_playing == False:
                self.start_timeline()
                self.timeline_is_playing = True

            elif self.timeline_is_playing == True:
                self.stop_timeline()
                self.timeline_is_playing = False
        elif button_name == push2_constants.BUTTON_SCALE:
            self.disable_controls = True if self.show_scale_menu == False else False
            self.show_scale_menu = True if self.show_scale_menu == False else False

        else:
            # For the other buttons, refer to the base class
            super().on_button_pressed(button_name)

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
            # Check for state of pads here, if pads are being touched, set lock
            seq = self.instrument_sequencers[
                self.get_current_instrument_short_name_helper()
            ]
            try:
                if len(self.app.steps_held) != 0:
                    for mode in self.app.active_modes:
                        if mode == self.app.trig_edit_mode:
                            idx = self.app.steps_held[0]
                            value = None

                            if seq.get_lock_state(idx, encoder_idx) is None:
                                value = self.app.trig_edit_mode.controls[
                                    encoder_idx
                                ].value

                            else:
                                # calmping to min/max values, scaling
                                control = self.app.trig_edit_mode.controls[encoder_idx]
                                lock_value = seq.get_lock_state(idx, encoder_idx)

                                min = 0 if hasattr(control, "items") else control.min
                                max = (
                                    len(control.items)
                                    if hasattr(control, "items")
                                    else control.max
                                )
                                range = max - min
                                incr = increment * range / 100
                                if min <= (lock_value + incr) <= max:
                                    value = lock_value + incr
                                else:
                                    value = lock_value

                            seq.set_lock_state(idx, encoder_idx, value)
                            return
                if self.show_scale_menu == True:
                    # Update scale menu controls
                    instrument_name = self.get_current_instrument_short_name_helper()
                    track_name = self.selected_track
                    track_controls = self.instrument_scale_edit_controls[
                        instrument_name
                    ][track_name]

                    control = track_controls[encoder_idx]
                    min = control.min if hasattr(control, "min") else 0
                    max = control.max if hasattr(control, "max") else len(control.items)
                    range = max - min
                    incr = increment * range / 100
                    if min < control.value + incr < max:
                        control.value = control.value + incr
                    if min >= (control.value + incr):
                        control.value = min
                    if max < (control.value + incr):
                        control.value = max - incr

                    self.update_pads()
                self.app.trig_edit_mode.update_button_colours()
            except Exception as e:
                traceback.print_exc()

        except Exception as e:
            traceback.print_exc()
