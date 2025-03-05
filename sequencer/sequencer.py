import asyncio
import isobar as iso
import random
from pythonosc.udp_client import SimpleUDPClient

default_number_of_steps = 64

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


class Sequencer(object):
    pitch = 64
    is_running = False
    tick_callback = None
    send_osc_func = None
    playhead = 0
    gate_1 = list()  # boolean
    pitch_1 = list()  # int (midi note)
    trig_mute_1 = list()
    accent_1 = list()
    aux_1 = list()  # boolean
    aux_2 = list()  # int
    aux_3 = list()  # int
    aux_4 = list()  # boolean
    locks = list() # for locks of trig menu
    playhead_track = None
    note_track = None
    midi_out_device = None
    midi_in_name = None
    midi_in_device = None


    def __init__(
        self, instrument_name, timeline, tick_callback, playhead, send_osc_func, app
    ):
        self.locks = {}
        for key in TRACK_NAMES:
            self.locks[key] = []
            for x in range(default_number_of_steps):
                self.locks[key].append([None, None, None, None, None, None, None, None, None])
        self.app = app
        self.show_locks = False
        self.steps_held = []
        self.name = instrument_name
        self.note = [None] * default_number_of_steps
        self.gate_1 = [False] * default_number_of_steps
        self.pitch_1 = [False] * default_number_of_steps
        self.trig_mute_1 = [False] * default_number_of_steps
        self.accent_1 = [False] * default_number_of_steps
        self.aux_1 = [False] * default_number_of_steps
        self.aux_2 = [False] * default_number_of_steps
        self.aux_3 = [False] * default_number_of_steps
        self.aux_4 = [False] * default_number_of_steps
        self.playhead = playhead
        self.send_osc_func = send_osc_func
        self.timeline = timeline
        for item in iso.io.midi.get_midi_input_names():
            if item.startswith(self.name) == True:
                self.midi_in_name = item
        
        self.note_pattern = iso.PSeq(self.note)
        self.midi_in_device = iso.MidiInputDevice(device_name=self.midi_in_name)
        self.midi_out_device = iso.MidiOutputDevice(device_name=f"{self.name} sequencer", send_clock=True, virtual=True)
        # TODO: had to remove the input device from here for this to work
        self.local_timeline = iso.Timeline(tempo=120, output_device=self.midi_out_device)
        # We should use track.update() to update the sequencers to match the pad state
        self.playhead_track = timeline.schedule(
            {
                "action": lambda: (
                    tick_callback(self.name, len(self.gate_1)),
                    self.seq_playhead_update(),
                ),
                "duration": 0.25,
            }
        )

    def seq_playhead_update(self):
        self.playhead = int((iso.PCurrentTime.get_beats(self) * 4 + 0.01))
        self.update_notes()
        self.evaluate_and_play_notes()

    def evaluate_and_play_notes(self):
        try:
        # Setting values used by all tracks
            instrument_name = self.get_current_instrument_short_name_helper()
            instrument_state = self.app.trig_edit_mode.state[instrument_name]
            instrument_scale_edit_controls = self.app.sequencer_mode.instrument_scale_edit_controls[instrument_name]
            note = None
            gate = None
            amplitude = None
            schedule_note = True
        # Setting values per track
            # Gate track stuff
            gate_track_len = instrument_scale_edit_controls["gate_1"][0].value
            gate_step = self.playhead % int(gate_track_len)
            gate_trig_menu_locks = self.locks["gate_1"][gate_step]    
            gate_loop_count = int(self.playhead / int(gate_track_len))
            gate_recur_default = self.app.trig_edit_mode.state[instrument_name]["gate_1"][8]
            gate_recur = int(gate_recur_default) if gate_trig_menu_locks[8] == None else int(gate_trig_menu_locks[8])
            gate_recur_len = int(self.trig_edit_mode.state[instrument_name]["gate_1"][7])

            gate_pitch = int(gate_trig_menu_locks[0]) if gate_trig_menu_locks[0] is not None else int(instrument_state["gate_1"][0]) 
            gate_octave = int(gate_trig_menu_locks[1]) * 12 if gate_trig_menu_locks[1] is not None else int(instrument_state["gate_1"][1])*12 
            gate_note = gate_pitch + gate_octave
            gate_velocity = instrument_state["gate_1"][2] if instrument_state["gate_1"][2] is not None else int(instrument_state["gate_1"][2])
            gate_gate = instrument_state["gate_1"][3]
            gate_prob = True if instrument_state["gate_1"][4] >= random.random() else False
            gate_recur_binary_list = [int(i) for i in bin(gate_recur)[2:] ]
             
            
            # Note track stuff
            pitch_track_len = instrument_scale_edit_controls["pitch_1"][0].value
            pitch_step = self.playhead % int(pitch_track_len)
            pitch_trig_menu_locks = self.locks["pitch_1"][pitch_step]   
            pitch_loop_count = int(self.playhead / int(pitch_track_len))
            pitch_recur_default = self.app.trig_edit_mode.state[instrument_name]["pitch_1"][8]
            pitch_recur = int(pitch_recur_default) if pitch_trig_menu_locks[8] == None else int(pitch_trig_menu_locks[8])
            pitch_recur_len = int(self.trig_edit_mode.state[instrument_name]["pitch_1"][7])

            pitch_pitch = int(pitch_trig_menu_locks[0]) if pitch_trig_menu_locks[0] is not None else int(instrument_state["pitch_1"][0]) 
            pitch_octave = int(pitch_trig_menu_locks[1]) * 12 if pitch_trig_menu_locks[1] is not None else int(instrument_state["pitch_1"][1])*12 
            pitch_note = pitch_pitch + pitch_octave
            pitch_velocity = instrument_state["pitch_1"][2] if instrument_state["pitch_1"][2] is not None else int(instrument_state["pitch_1"][2])
            pitch_gate = instrument_state["pitch_1"][3]
            pitch_prob = True if instrument_state["pitch_1"][4] >= random.random() else False
            pitch_recur_binary_list = [int(i) for i in bin(pitch_recur)[2:] ]
            
            # Mute track stuff
            trig_mute_track_len = instrument_scale_edit_controls["trig_mute_1"][0].value
            trig_mute_step = self.playhead % int(trig_mute_track_len)
            trig_mute_trig_menu_locks = self.locks["trig_mute_1"][trig_mute_step]  
            trig_mute_prob = True if instrument_state["trig_mute_1"][4] >= random.random() else False     
            trig_mute_loop_count = int(self.playhead / int(trig_mute_track_len))
            trig_mute_recur_default = self.app.trig_edit_mode.state[instrument_name]["trig_mute_1"][8]
            trig_mute_recur = int(trig_mute_recur_default) if trig_mute_trig_menu_locks[8] == None else int(trig_mute_trig_menu_locks[8]) 
            trig_mute_recur_len = int(self.trig_edit_mode.state[instrument_name]["trig_mute_1"][7])
            
            trig_mute_recur_binary_list = [int(i) for i in bin(trig_mute_recur)[2:] ]
           
            # Accent track stuff
            accent_track_len = instrument_scale_edit_controls["accent_1"][0].value
            accent_step = self.playhead % int(trig_mute_track_len)
            accent_trig_menu_locks = self.locks["accent_1"][accent_step]  
            accent_prob = True if instrument_state["accent_1"][4] >= random.random() else False  
            accent_velocity = instrument_state["accent_1"][2] if instrument_state["accent_1"][2] is not None else int(instrument_state["accent_1"][2])
            accent_loop_count = int(self.playhead / int(accent_track_len))
            accent_recur_default = self.app.trig_edit_mode.state[instrument_name]["accent_1"][8]
            accent_recur = int(accent_recur_default) if accent_trig_menu_locks[8] == None else int(accent_trig_menu_locks[8])
            accent_recur_len = int(self.trig_edit_mode.state[instrument_name]["accent_1"][7]) 
            
            accent_recur_binary_list = [int(i) for i in bin(accent_recur)[2:] ]
            
        # Evaluate all tracks
            # Evaluate Gate track, note and amp here to avoid a None value
            note = gate_note
            amplitude = gate_velocity
            # TODO: make this loop count max out with last enc on the trig menu
            if self.gate_1[gate_step] == True and gate_prob == True and gate_recur_binary_list[int(gate_loop_count % gate_recur_len)] == 1:
                gate =  gate_gate
                
            # Evaluate Pitch track
            if self.pitch_1[pitch_step] == True and pitch_prob == True and pitch_recur_binary_list[int(pitch_loop_count % pitch_recur_len)] == 1:
                note = pitch_note
                amplitude = pitch_velocity

            # Evaluate Mute track
            if self.trig_mute_1[trig_mute_step] == True and trig_mute_prob == True and trig_mute_recur_binary_list[int(trig_mute_loop_count % trig_mute_recur_len)] == 1:
                schedule_note = False

            # Evaluate Accent track
            if self.accent_1[accent_step] == True and accent_prob == True and accent_recur_binary_list[int(accent_loop_count % accent_recur_len)] == 1:
                amplitude = accent_velocity

        # Schedule the note
        # TODO: should we grab all the evals from one step before the playhead, 
        # then schedule it one note in the future to allow for some drift?
        # Not sure how much time this entire eval process takes, might introduce flanging? 
            if schedule_note == True:
                self.local_timeline.schedule({"note": note, "gate": gate, "amplitude": amplitude}, count=1)
        except Exception as e:
            print("Error in evaluate_and_play_notes, ",e)

    def update_notes(self):
        for idx, note in enumerate(self.note):
            if self.gate_1[idx] == True:
                self.note[idx] = 64
                
            if self.gate_1[idx] == False:
                self.note[idx] = None

    def get_track(self, lane):
        if lane == "gate_1":
            return self.gate_1
        elif lane == "pitch_1":
            return self.pitch_1
        elif lane == "trig_mute_1":
            return self.trig_mute_1
        elif lane == "accent_1":
            return self.accent_1
        elif lane == "aux_1":
            return self.aux_1
        elif lane == "aux_2":
            return self.aux_2
        elif lane == "aux_3":
            return self.aux_3
        elif lane == "aux_4":
            return self.aux_4
        
    def get_current_instrument_short_name_helper(self):
        return self.app.instrument_selection_mode.get_current_instrument_short_name()

    def set_states(self, lane, values):
        for index, value in enumerate(values):
            self.set_state(lane, index, value)

    def set_state(self, lane, index, value):
        # print(f"lane: {lane} index: {index} value: {value}")
        self.update_notes()
        if lane == "gate_1":
            self.gate_1[index] = value
        elif lane == "pitch_1":
            self.pitch_1[index] = value
        elif lane == "trig_mute_1":
            self.trig_mute_1[index] = value
        elif lane == "accent_1":
            self.accent_1[index] = value
        elif lane == "aux_1":
            self.aux_1[index] = value
        elif lane == "aux_2":
            self.aux_2[index] = value
        elif lane == "aux_3":
            self.aux_3[index] = value
        elif lane == "aux_4":
            self.aux_4[index] = value

    def set_lock_state(self, index, parameter_idx, value):
        # print(f"Set_lock_state: index {index}, param_idx {parameter_idx}, value {value}")
        selected_track = self.app.sequencer_mode.selected_track
        self.locks[selected_track][index][parameter_idx] = value
 

    def get_lock_state(self, index, parameter_idx):
        # print(f"Set_lock_state: index {index}, param_idx {parameter_idx}, value {value}")
        selected_track = self.app.sequencer_mode.selected_track
        return self.locks[selected_track][index][parameter_idx]
        