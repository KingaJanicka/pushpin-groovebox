import asyncio
import isobar as iso
import random
import json
import os
import traceback
import random
from pythonosc.udp_client import SimpleUDPClient
from definitions import TRACK_NAMES_METRO


default_number_of_steps = 64

class SequencerMetro(object):
    pitch = 64
    is_running = False
    tick_callback = None
    send_osc_func = None
    playhead = 0
    pitch = list()  # boolean
    octave = list()  # int (midi note)
    gate = list()
    mutes_skips = list()
    aux_1 = list()  # boolean
    aux_2 = list()  # int
    aux_3 = list()  # int
    aux_4 = list()  # boolean
    locks = list()  # for locks of trig menu
    playhead_track = None
    note_track = None
    midi_out_device = None
    midi_in_name = None
    midi_in_device = None
    index = None

    def __init__(
        self, instrument, tick_callback, playhead, send_osc_func, global_timeline, app
    ):
        self.locks = {}
        self.seq_filename = f"seq_metro_{instrument.name}.json"
        for key in TRACK_NAMES_METRO:
            self.locks[key] = []
            for x in range(default_number_of_steps):
                self.locks[key].append(
                    [None, None, None, None, None, None, None, None, None]
                )

        self.app = app
        self.step_index = 0
        self.step_count = 0
        self.show_locks = False
        self.next_step_index = 1
        self.steps_held = []
        self.name = instrument.name
        self.note = [None] * default_number_of_steps
        self.pitch = [False] * default_number_of_steps
        self.octave = [False] * default_number_of_steps
        self.velocity = [False] * default_number_of_steps
        self.gate = [False] * default_number_of_steps
        self.mutes_skips = [False] * default_number_of_steps
        self.aux_1 = [False] * default_number_of_steps
        self.aux_2 = [False] * default_number_of_steps
        self.aux_3 = [False] * default_number_of_steps
        self.playhead = playhead
        self.send_osc_func = send_osc_func
        self.timeline = global_timeline
        for item in iso.io.midi.get_midi_input_names():
            if item.startswith(self.name) == True:
                self.midi_in_name = item

        self.note_pattern = iso.PSeq(self.note)
        
        self.local_timeline = instrument.timeline
        self.midi_in_device = instrument.midi_out_device
        self.midi_in_name = instrument.midi_in_name
        self.midi_out_device = instrument.midi_out_device
        
        # We should use track.update() to update the sequencers to match the pad state
        self.playhead_track = instrument.timeline.schedule(
            {
                "action": lambda: (
                    tick_callback(self.name, len(self.pitch)),
                    self.seq_playhead_update(),
                ),
                "duration": 0.25,
            }
        )

    def get_track_by_name(self, name):
        if name == TRACK_NAMES_METRO[0]:
            return self.pitch
        elif name == TRACK_NAMES_METRO[1]:
            return self.octave
        elif name == TRACK_NAMES_METRO[2]:
            return self.velocity
        elif name == TRACK_NAMES_METRO[3]:
            return self.gate
        elif name == TRACK_NAMES_METRO[4]:
            return self.mutes_skips
        elif name == TRACK_NAMES_METRO[5]:
            return self.aux_1
        elif name == TRACK_NAMES_METRO[6]:
            return self.aux_2
        elif name == TRACK_NAMES_METRO[7]:
            return self.aux_3
        
    def load_state(self):
        try:
            if os.path.exists(self.seq_filename):
                dump = json.load(open(self.seq_filename))
                self.locks = dump["locks"]
                self.note = dump["note"]
                self.pitch = dump[TRACK_NAMES_METRO[0]]
                self.octave = dump[TRACK_NAMES_METRO[1]]
                self.aux_4 = dump[TRACK_NAMES_METRO[2]]
                self.gate = dump[TRACK_NAMES_METRO[3]]
                self.mutes_skips = dump[TRACK_NAMES_METRO[4]]
                self.aux_1 = dump[TRACK_NAMES_METRO[5]]
                self.aux_2 = dump[TRACK_NAMES_METRO[6]]
                self.aux_3 = dump[TRACK_NAMES_METRO[7]]
                
                self.app.metro_sequencer_mode.update_pads_to_seq_state()
        except Exception as e:
            print("Exception in seq load_state")
            traceback.print_exc()

    def save_state(self):
        try:
            # pass
            sequencer_state = {
                "locks": self.locks,
                "note": self.note,
                TRACK_NAMES_METRO[0]: self.pitch,
                TRACK_NAMES_METRO[1]: self.octave,
                TRACK_NAMES_METRO[2]: self.velocity,
                TRACK_NAMES_METRO[3]: self.gate,
                TRACK_NAMES_METRO[4]: self.mutes_skips,
                TRACK_NAMES_METRO[5]: self.aux_1,
                TRACK_NAMES_METRO[6]: self.aux_2,
                TRACK_NAMES_METRO[7]: self.aux_3,
            }
            json.dump(
                sequencer_state, open(self.seq_filename, "w")
            )  # Save to file
        except Exception as e:
            print("Exception in seq save_state")
            traceback.print_exc()

    def seq_playhead_update(self):
        # Playhead is off by one
        
        self.playhead = int((iso.PCurrentTime.get_beats(self) * 4 + 0.01))
        # self.update_notes()
        
        controls = self.app.metro_sequencer_mode.instrument_scale_edit_controls[self.name]
        
        pattern_len = controls[0].value
        
        
        if int(pattern_len) < self.step_count:
            self.reset_index()
        
        self.evaluate_and_play_notes()
        self.increment_index()

    def increment_index(self, index = None):
        
        current_index = index if index != None else self.step_index
        next_step_index = (current_index + 1) % 64
        
        
        column = int(next_step_index / 8)
        skips_idx = column*8
        
        if self.gate[next_step_index] != False and self.mutes_skips[skips_idx] != True:
            self.step_index = next_step_index
            self.app.metro_sequencer_mode.update_pads()
            self.step_count += 1 
            return
        else:
            self.increment_index(index=next_step_index)
            
    def increment_next_step_index(self, index = None):
        current_index = index if index != None else self.step_index
        next_step_index = (current_index + 1) % 64
        
        column = int(next_step_index / 8)
        skips_idx = column*8
        
        if self.gate[next_step_index] != False and self.mutes_skips[skips_idx] != True:
            self.next_step_index = next_step_index
            return 
        
        else:
            self.increment_next_step_index(index=next_step_index)
        
    def reset_index(self):
        self.step_index = 0
        self.step_count = 0
        self.next_step_index = 1
        
    def evaluate_and_play_notes(self):
        try:
            gate_track_active = self.app.mute_mode.tracks_active[self.name][
                "gate_1"
            ]
            
            if self.gate[self.step_index] != "Off" and gate_track_active == True:
                
                
                gate = 1
                pitch = self.pitch[self.step_index] if self.pitch[self.step_index] != None else 0 
                octave = self.octave[self.step_index] * 12 if self.octave[self.step_index] != None else 0 
            
                pitch_and_octave = pitch + octave
                velocity = ((self.velocity[self.step_index] + 1) * 16 - 1) if self.velocity[self.step_index] != None else 1 
                gate = None
                gate_len = self.app.trig_edit_mode.controls[3].value
                
                column = int(self.step_index / 8)
                mutes_idx = column*8+1
                
                
                prob = None
    
                # checking columns for the True statement
                for x in range(7):
                    if self.mutes_skips[mutes_idx + x] == True:
                        prob = x
                        
                self.increment_next_step_index(index=self.step_index)
                next_step_index = self.next_step_index
                
                if self.gate[next_step_index] == "Tie":
                    gate = 0.3
                else:
                    gate = 0.25 * gate_len
            
            

                if prob >= random.randint(1, 6):
            
                    self.local_timeline.schedule(
                        {"note": pitch_and_octave, "gate": gate, "amplitude": velocity}, count=1
                    )
        except Exception as e:
            print("Error in evaluate_and_play_notes")
            traceback.print_exc()


    def update_notes(self):
        for idx, note in enumerate(self.note):
            if self.pitch[idx] == True:
                self.note[idx] = 64

            if self.pitch[idx] == False:
                self.note[idx] = None

    def get_track(self, lane):
        if lane == TRACK_NAMES_METRO[0]:
            return self.pitch
        elif lane == TRACK_NAMES_METRO[1]:
            return self.octave
        elif lane == TRACK_NAMES_METRO[2]:
            return self.velocity
        elif lane == TRACK_NAMES_METRO[3]:
            return self.gate
        elif lane == TRACK_NAMES_METRO[4]:
            return self.mutes_skips
        elif lane == TRACK_NAMES_METRO[5]:
            return self.aux_1
        elif lane == TRACK_NAMES_METRO[6]:
            return self.aux_2
        elif lane == TRACK_NAMES_METRO[7]:
            return self.aux_3

    def get_current_instrument_short_name_helper(self):
        return self.app.instrument_selection_mode.get_current_instrument_short_name()

    def set_states(self, lane, values):
        for index, value in enumerate(values):
            self.set_state(lane, index, value)

    def set_state(self, lane, index, value):
        # print(f"lane: {lane} index: {index} value: {value}")
        self.update_notes()
        lane = lane[0]
        if lane == TRACK_NAMES_METRO[0]:
            self.pitch[index] = value
        elif lane == TRACK_NAMES_METRO[1]:
            self.octave[index] = value
        elif lane == TRACK_NAMES_METRO[2]:
            self.velocity[index] = value
        elif lane == TRACK_NAMES_METRO[3]:
            self.gate[index] = value
        elif lane == TRACK_NAMES_METRO[4]:
            self.mutes_skips[index] = value
        elif lane == TRACK_NAMES_METRO[5]:
            self.aux_1[index] = value
        elif lane == TRACK_NAMES_METRO[6]:
            self.aux_2[index] = value
        elif lane == TRACK_NAMES_METRO[7]:
            self.aux_3[index] = value

    def set_lock_state(self, index, parameter_idx, value):
        # print(f"Set_lock_state: index {index}, param_idx {parameter_idx}, value {value}")
        selected_track = self.app.sequencer_mode.selected_track
        self.locks[selected_track][index][parameter_idx] = value

    def get_lock_state(self, index, parameter_idx):
        # print(f"Set_lock_state: index {index}, param_idx {parameter_idx}, value {value}")
        selected_track = self.app.sequencer_mode.selected_track
        return self.locks[selected_track][index][parameter_idx]
