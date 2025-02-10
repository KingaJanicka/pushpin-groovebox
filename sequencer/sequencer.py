import asyncio
import isobar as iso

from pythonosc.udp_client import SimpleUDPClient

default_number_of_steps = 64

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


class Sequencer(object):
    pitch = 64
    is_running = False
    tick_callback = None
    send_osc_func = None
    playhead = 0
    gate = list()  # boolean
    pitch1 = list()  # int (midi note)
    pitch2 = list()
    pitch3 = list()
    trig_mute = list()  # boolean
    accent = list()  # int
    swing = list()  # int
    slide = list()  # boolean
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
        self.note = [False] * default_number_of_steps
        self.gate = [False] * default_number_of_steps
        self.pitch1 = [False] * default_number_of_steps
        self.pitch2 = [False] * default_number_of_steps
        self.pitch3 = [False] * default_number_of_steps
        self.trig_mute = [False] * default_number_of_steps
        self.accent = [False] * default_number_of_steps
        self.swing = [False] * default_number_of_steps
        self.slide = [False] * default_number_of_steps
        self.playhead = playhead
        self.send_osc_func = send_osc_func
        self.timeline = timeline
        for item in iso.io.midi.get_midi_input_names():
            if item.startswith(self.name) == True:
                self.midi_in_name = item
        
        self.midi_in_device = iso.MidiInputDevice(device_name=self.midi_in_name)
        self.midi_out_device = iso.MidiOutputDevice(device_name=f"{self.name} sequencer", send_clock=True, virtual=True)
        # TODO: had to remove the input device from here for this to work
        self.local_timeline = iso.Timeline(tempo=120, output_device=self.midi_out_device)
        self.note_track = self.local_timeline.schedule({"note": None, "duration": 0.25, "gate": 0.2, "amplitude": 127})
        for x in range(default_number_of_steps):
            self.locks.append([None, None, None, None, None, None, None, None])
        # We should use track.update() to update the sequencers to match the pad state
        self.playhead_track = timeline.schedule(
            {
                "action": lambda: (
                    tick_callback(self.name, len(self.gate)),
                    self.seq_playhead_update(),
                ),
                "duration": 0.25,
            }
        )

    def seq_playhead_update(self):
        playhead = int((iso.PCurrentTime.get_beats(self) * 4 + 0.01) % 64)
        
    def update_notes(self):
        for idx, note in enumerate(self.note):
            if self.gate[idx] == True:
                self.note[idx] = 64
            if self.gate[idx] == False:
                self.note[idx] = None
        self.note_track.update(events=iso.PDict({"note": iso.PSequence(self.note), "duration": iso.PSequence([0.25]), "gate": iso.PSequence([0.2]), "amplitude": iso.PSequence([127])}))


    def get_track(self, lane):
        if lane == "gate":
            return self.gate
        elif lane == "pitch1":
            return self.pitch1
        elif lane == "pitch2":
            return self.pitch2
        elif lane == "pitch3":
            return self.pitch3
        elif lane == "trig_mute":
            return self.trig_mute
        elif lane == "accent":
            return self.accent
        elif lane == "swing":
            return self.swing
        elif lane == "slide":
            return self.slide

    def set_states(self, lane, values):
        for index, value in enumerate(values):
            self.set_state(lane, index, value)

    def set_state(self, lane, index, value):
        # print(f"lane: {lane} index: {index} value: {value}")
        self.update_notes()
        if lane == "gate":
            self.gate[index] = value
        elif lane == "pitch1":
            self.pitch1[index] = value
        elif lane == "pitch2":
            self.pitch2[index] = value
        elif lane == "pitch3":
            self.pitch3[index] = value
        elif lane == "trig_mute":
            self.trig_mute[index] = value
        elif lane == "accent":
            self.accent[index] = value
        elif lane == "swing":
            self.swing[index] = value
        elif lane == "slide":
            self.slide[index] = value

    def set_lock_state(self, index, parameter_idx, value):
        self.locks[index][parameter_idx] = value
 
        