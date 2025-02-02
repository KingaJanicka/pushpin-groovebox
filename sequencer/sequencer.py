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

    timeline = iso.timeline

    def __init__(
        self, instrument_name, timeline, tick_callback, playhead, send_osc_func
    ):
        self.name = instrument_name
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

        for x in range(default_number_of_steps):
            self.locks.append([None, None, None, None, None, None, None, None])

        self.timeline = timeline.schedule(
            {
                "action": lambda: (
                    tick_callback(self.name, len(self.gate)),
                    self.seq(),
                ),
                "duration": 0.25,
            }
        )

    def seq(self):
        # This should be syncing well but for some reason it does not
        playhead = int((iso.PCurrentTime.get_beats(self) * 4 + 0.01) % 64)
        if self.gate[playhead] is True:
            print(self.name, "NAME")
            print("sent note seq", self.name)
            self.send_osc_func("/mnote", [float(25), float(0)], self.name)
            self.send_osc_func("/mnote", [float(25), float(127)], self.name)

        if self.gate[playhead] is False:
            self.send_osc_func("/mnote", [float(25), float(0)], self.name)

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
 
        