import asyncio
import isobar as iso

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
        self, instrument_name, timeline, tick_callback, playhead, send_osc_func
    ):
        
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
        for x in range(default_number_of_steps):
            self.locks.append([None, None, None, None, None, None, None, None])
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
        # TODO: Somewhere a crash occurs when a note is played
        self.playhead = int((iso.PCurrentTime.get_beats(self) * 4 + 0.01) % 64)
        self.update_notes()
        
        if self.gate_1[self.playhead] == True and self.trig_mute_1[self.playhead] != True:
            amplitude = 127 if self.accent_1 else 64
            self.local_timeline.schedule({"note": 64, "gate": 0.2, "amplitude": amplitude}, count=1)
        
        
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
        print("Set_lock_state")
        self.locks[index][parameter_idx] = value
 
        