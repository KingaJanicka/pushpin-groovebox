import definitions
import push2_python.constants

from modes.melodic_mode import MelodicMode


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

    sequencer_pad_state = {}
    def initialize(self, settings):
        super().initialize(settings)
        for row in self.sequencer_pad_matrix:
            for cell in row:
                self.sequencer_pad_state[cell] = None
        # self.api = WarpApi()
        # self.api.song.edit(tempo=40)

        # DEVICE = demo.suggest_device(self.api, 'IAC Driver IAC Bus')
        # self.api.instruments.add('kick_inst', device=DEVICE, channel=1, min_octave=0, base_octave=0, max_octave=10,
        #                     osc_out="127.0.0.1:1030", osc_commands={"note_on": "mnote", "note_off": "mnote/rel"})
        # self.api.instruments.add(name='kick', instrument='kick_inst', muted=False)

        # self.api.patterns.add(name='kick_4_4', slots=[
        #     Slot(note='C', octave=4),
        #     Slot(rest=True),
        #     Slot(rest=True),
        #     Slot(rest=True),
        #     Slot(note='C', octave=4),
        #     Slot(rest=True),
        #     Slot(rest=True),
        # ])

    def get_settings_to_save(self):
        return {}

    def pad_ij_to_midi_note(self, pad_ij):
        return self.sequencer_pad_matrix[pad_ij[0]][pad_ij[1]]

    def update_octave_buttons(self):
        # Rhythmic does not have octave buttons
        pass

    def update_pads(self):
        color_matrix = []
        for i in range(0, 8):
            row_colors = []
            for j in range(0, 8):
                corresponding_midi_note = self.pad_ij_to_midi_note([i, j])
                cell_color = definitions.BLACK

                # if i >= 4 and j < 4:
                #     # This is the main 4x4 grid
                #     cell_color = self.app.instrument_selection_mode.get_current_instrument_color()
                # elif i >= 4 and j >= 4:
                #     cell_color = definitions.GRAY_LIGHT
                # elif i < 4 and j < 4:
                #     cell_color = definitions.GRAY_LIGHT
                # elif i < 4 and j >= 4:
                #     cell_color = definitions.GRAY_LIGHT
                if (
                    self.is_midi_note_being_played(corresponding_midi_note)
                    and self.sequencer_pad_state[corresponding_midi_note] is None
                ):
                    cell_color = definitions.NOTE_ON_COLOR
                    self.sequencer_pad_state[corresponding_midi_note] = True
                elif self.is_midi_note_being_played(corresponding_midi_note):
                    self.sequencer_pad_state[corresponding_midi_note] = None
                elif self.sequencer_pad_state[corresponding_midi_note] is not None:
                    cell_color = definitions.NOTE_ON_COLOR
                row_colors.append(cell_color)
            color_matrix.append(row_colors)

        self.push.pads.set_pads_color(color_matrix)

    def on_button_pressed(self, button_name):
        if (
            button_name == push2_python.constants.BUTTON_OCTAVE_UP
            or button_name == push2_python.constants.BUTTON_OCTAVE_DOWN
        ):
            # Don't react to octave up/down buttons as these are not used in rhythm mode
            pass
        else:
            # For the other buttons, refer to the base class
            super().on_button_pressed(button_name)
