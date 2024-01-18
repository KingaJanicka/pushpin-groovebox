import definitions
import push2_constants
from sequencer import Sequencer
from melodic_mode import MelodicMode

import asyncio
import os, sys

EMPTY_PATTERN =[]

seq = Sequencer()

class SequencerMode(MelodicMode):
    sequencer_pad_matrix = [
        range(92, 100),
        range(84, 92),
        range(76, 84),
        range(68, 76),
        range(60, 68),
        range(52, 60),
        range(44, 52),
        range(36, 44)
    ]

    playhead = 0
    seq_tick = 0
    def initialize(self, settings):
        super().initialize(settings)
        self.sequencer_pad_state = [None] * 64

    def start_sequencer(self):
        seq.start(self.sequencer_on_tick)

    def stop_sequencer(self):
        seq.stop()

    def get_settings_to_save(self):
        return {}

    def pad_ij_to_midi_note(self, pad_ij):
        return self.sequencer_pad_matrix[pad_ij[0]][pad_ij[1]]

    def update_octave_buttons(self):
        # Rhythmic does not have octave buttons
        pass

    def sequencer_on_tick(self, state):
        self.update_pads()
        self.playhead = (self.playhead + 1 ) % 64

    
    def update_pads(self):
        try:
            button_colors = [definitions.OFF_BTN_COLOR] * len(seq.gates)
        
            for i, value in enumerate(seq.gates):
                if value:
                    button_colors[i] = definitions.NOTE_ON_COLOR
                
                corresponding_midi_note = self.sequencer_pad_matrix[int(i/8)][int(i%8)]
                
                if self.playhead == i and seq.is_running:
                    button_colors[i] = definitions.WHITE

                # print("on midi note", self.is_midi_note_being_played(corresponding_midi_note) )
                # otherwise if a pad is being pushed and it's not active currently, turn it on
                # print(self.on_pad_pressed( 0 , [int(i/8), int(i%8)], 127))

                #      TODO: bug, won't work if sequencer is playing
                if self.is_midi_note_being_played(corresponding_midi_note) and self.sequencer_pad_state[i] is None:
                    print("pad activated")
                    button_colors[i] = definitions.NOTE_ON_COLOR
                    self.sequencer_pad_state[i] = True
                    seq.set_state('gates', i, True)
                
                # otherwise if a pad is being pushed and it is active, turn it off
                elif self.is_midi_note_being_played(corresponding_midi_note):
                    print("pad disactivated")
                    button_colors[i] = definitions.OFF_BTN_COLOR
                    seq.set_state('gates', i, False)
                    self.sequencer_pad_state[i] = None
                
                # # otherwise if a pad is on, leave it on
                # elif self.sequencer_pad_state[i] is not None:
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
            
            print(f"{exception_message} {exception_type} {filename}, Line {exception_traceback.tb_lineno}")
            

    def on_button_pressed(self, button_name):
        if button_name == push2_constants.BUTTON_OCTAVE_UP or button_name == push2_constants.BUTTON_OCTAVE_DOWN:
            # Don't react to octave up/down buttons as these are not used in rhythm mode
            pass

        elif button_name == push2_constants.BUTTON_PLAY:
            self.start_sequencer()

        elif button_name == push2_constants.BUTTON_STOP:
            self.stop_sequencer()
            print('stop')
        else:
            # For the other buttons, refer to the base class
            super().on_button_pressed(button_name)
