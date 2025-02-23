import definitions
from controllers import push2_constants
import push2_python
from sequencer.sequencer import Sequencer
from modes.melodic_mode import MelodicMode
import isobar as iso
import os
import sys
import time

from modes.trig_edit_mode import TrigEditMode
EMPTY_PATTERN = []

TRACK_NAMES = [
    "gate_1",
    "pitch_1",
    "trig_mute_1",
    "accent_1",
    "aux_1",
    "aux_2",
    "aux_3",
    "aux_4",
]
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
    timeline = iso.Timeline(tempo, output_device=iso.DummyOutputDevice())
    selected_track = "gate_1"
    pads_press_time = [False] * 64
    pad_quick_press_time = 0.400
    
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
                self.app
            )

    def start_timeline(self):
        for (
            instrument_short_name
        ) in self.get_all_distinct_instrument_short_names_helper():
            self.instrument_sequencers[instrument_short_name].local_timeline.background()
        
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
        self.update_pads()
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

    def new_instrument_selected(self):
        instrument_index = self.app.instrument_selection_mode.selected_instrument % 8
        instrument_index = int(
            (self.app.instrument_selection_mode.selected_instrument - instrument_index)
            / 8
        )

        self.selected_instrument = TRACK_NAMES[0]
        # print(self.selected_instrument)
        # print(self.app.osc_mode.get_current_instrument_osc_address_sections())


    def update_pads(self):
        try:
            seq = self.instrument_sequencers[
                self.get_current_instrument_short_name_helper()
            ]
            seq_pad_state = seq.get_track(self.selected_track)
            button_colors = [definitions.OFF_BTN_COLOR] * len(seq_pad_state)
            

            for i, value in enumerate(seq.get_track(self.selected_track)):
                if value:
                    button_colors[i] = TRACK_COLORS[self.selected_track]

                # Set pad colours for on/off states of the seq
                if (seq_pad_state[i] is True):
                    button_colors[i] = TRACK_COLORS[self.selected_track]

                if seq_pad_state[i] is False:
                    button_colors[i] = definitions.OFF_BTN_COLOR

            # Draw the playhead
            playhead = seq.playhead
            button_colors[playhead] = definitions.WHITE

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
        idx = pad_ij[0]*8 + pad_ij[1]
        seq.steps_held.append(idx)
        # If a pad is off, turn it on
        if seq_pad_state[idx] == False:
            seq.set_state(self.selected_track, idx, True)

        # If it's on, save the time and cont in on_pad_released
        elif seq_pad_state[idx] == True:
            self.pads_press_time[idx] = time.time()
            # call func to show lock here

    def on_pad_released(self, pad_n, pad_ij, velocity):
        seq = self.instrument_sequencers[
            self.get_current_instrument_short_name_helper()
        ]
        seq_pad_state = seq.get_track(self.selected_track)
        idx = pad_ij[0]*8 + pad_ij[1]
        epoch_time = time.time()
        press_time = epoch_time - self.pads_press_time[idx]
        # Short Press - turn the pad off, reset the timer
        if press_time <= self.pad_quick_press_time and self.pads_press_time[idx] != False:
            seq.set_state(self.selected_track, idx, False)
            self.pads_press_time[idx] = False
            
        # Long Press - keep the pad on, trigger a lock preview
        elif press_time > self.pad_quick_press_time:
            pass
            # seq.set_state(self.selected_track, idx, False

        seq.steps_held.remove(idx)
        self.app.pads_need_update = True

    def on_button_pressed(self, button_name):
        if button_name in track_button_names:
            idx = track_button_names.index(button_name)
            self.selected_track = TRACK_NAMES[idx]
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
            device = self.app.osc_mode.get_current_instrument_device()
            try:
                if len(seq.steps_held) != 0:
                    for mode in self.app.active_modes:
                        if mode == self.app.trig_edit_mode:
                            value = self.app.trig_edit_mode.controls[encoder_idx].value
                            idx = seq.steps_held[0]
                            self.app.trig_edit_mode.on_encoder_rotated(encoder_name, increment)
                            seq.set_lock_state(idx, encoder_idx, value)
                            return
            except Exception as e:
                print(e)

            current_device = self.app.osc_mode.get_current_instrument_device()
            current_device.on_encoder_rotated(encoder_name, increment)
        except Exception as e:
            print(e)
