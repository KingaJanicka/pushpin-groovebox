import definitions
import push2_constants
from sequencer import Sequencer
from melodic_mode import MelodicMode
import isobar as iso
import os
import sys

EMPTY_PATTERN = []

TRACK_NAMES = [
    "gate",
    "pitch1",
    "pitch2",
    "pitch3",
    "trig_mute",
    "accent",
    "swing",
    "slide",
]
TRACK_COLORS = {
    "gate": definitions.BLUE,
    "pitch1": definitions.GREEN,
    "pitch2": definitions.GREEN,
    "pitch3": definitions.GREEN,
    "trig_mute": definitions.RED,
    "accent": definitions.PURPLE,
    "swing": definitions.YELLOW,
    "slide": definitions.TURQUOISE,
}


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
    current_selected_section_and_page = {}
    instrument_sequencers = {}
    tempo = 120
    timeline = iso.Timeline(tempo, output_device=iso.DummyOutputDevice())
    selected_instrument = "gate"

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
            )

    def start_timeline(self):
        self.timeline.background()

    def stop_timeline(self):
        self.timeline.stop()

    def get_settings_to_save(self):
        return {}

    def pad_ij_to_midi_note(self, pad_ij):
        return self.sequencer_pad_matrix[pad_ij[0]][pad_ij[1]]

    def update_octave_buttons(self):
        # Rhythmic does not have octave buttons
        pass

    def sequencer_on_tick(self, instrument_name, length):
        # print(self.get_current_instrument_osc_port())

        self.update_pads()
        if self.get_current_instrument_short_name_helper() == instrument_name:
            self.playhead = (self.playhead + 1) % length

    def get_all_distinct_instrument_short_names_helper(self):
        return (
            self.app.instrument_selection_mode.get_all_distinct_instrument_short_names()
        )

    def get_current_instrument_short_name_helper(self):
        return self.app.instrument_selection_mode.get_current_instrument_short_name()

    def get_current_instrument_osc_port(self):
        return self.app.instrument_selection_mode.get_current_instrument_info()[
            "osc_port"
        ]

    def new_instrument_selected(self):
        instrument_index = self.app.instrument_selection_mode.selected_instrument % 8
        instrument_index = int(
            (self.app.instrument_selection_mode.selected_instrument - instrument_index)
            / 8
        )

        self.selected_instrument = TRACK_NAMES[instrument_index]
        print(self.selected_instrument)
        # print(self.app.osc_mode.get_current_instrument_osc_address_sections())

    def update_pads(self):
        try:
            seq = self.instrument_sequencers[
                self.get_current_instrument_short_name_helper()
            ]
            seq_pad_state = seq.get_instrument(self.selected_instrument)
            button_colors = [definitions.OFF_BTN_COLOR] * len(seq_pad_state)
            for i, value in enumerate(seq.get_instrument(self.selected_instrument)):
                if value:
                    button_colors[i] = TRACK_COLORS[self.selected_instrument]

                corresponding_midi_note = self.sequencer_pad_matrix[int(i / 8)][
                    int(i % 8)
                ]

                if self.playhead == i and self.timeline.running:
                    button_colors[i] = definitions.WHITE
                # print("on midi note", self.is_midi_note_being_played(corresponding_midi_note) )
                # otherwise if a pad is being pushed and it's not active currently, turn it on
                # print(self.on_pad_pressed( 0 , [int(i/8), int(i%8)], 127))

                if (
                    self.is_midi_note_being_played(corresponding_midi_note)
                    and seq_pad_state[i] is False
                ):
                    # print("pad activated")
                    button_colors[i] = TRACK_COLORS[self.selected_instrument]
                    seq.set_state(self.selected_instrument, i, True)

                # otherwise if a pad is being pushed and it is active, turn it off
                elif (
                    self.is_midi_note_being_played(corresponding_midi_note)
                    and seq_pad_state[i] is True
                ):
                    # print("pad disactivated")
                    button_colors[i] = definitions.OFF_BTN_COLOR
                    seq.set_state(self.selected_instrument, i, False)

                # if self.is_midi_note_being_played(corresponding_midi_note):
                # print("MIDI NOTE PLAYED")
                # print(seq_pad_state[i])
                # # otherwise if a pad is on, leave it on
                # elif self.seq_pad_state[self.get_current_instrument_short_name_helper()][i] is not None:
                #     button_colors[i] = definitions.NOTE_ON_COLOR

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

    def on_button_pressed(self, button_name):
        if (
            button_name == push2_constants.BUTTON_OCTAVE_UP
            or button_name == push2_constants.BUTTON_OCTAVE_DOWN
        ):
            # Don't react to octave up/down buttons as these are not used in rhythm mode
            pass
        elif button_name == push2_constants.BUTTON_DELETE:

            self.selected_instrument = TRACK_NAMES[6]
        elif button_name == push2_constants.BUTTON_PLAY:
            self.start_timeline()
            print("play")

        elif button_name == push2_constants.BUTTON_STOP:
            self.stop_timeline()
            print("stop")
        else:
            # For the other buttons, refer to the base class
            super().on_button_pressed(button_name)
