import asyncio
import isobar as iso
import random
import json
import os
import traceback
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

    def __init__(
        self, instrument_name, timeline, tick_callback, playhead, send_osc_func, app
    ):
        self.locks = {}
        self.seq_filename = f"seq_metro_{instrument_name}.json"
        for key in TRACK_NAMES_METRO:
            self.locks[key] = []
            for x in range(default_number_of_steps):
                self.locks[key].append(
                    [None, None, None, None, None, None, None, None, None]
                )

        self.app = app
        self.show_locks = False
        self.steps_held = []
        self.name = instrument_name
        self.note = [None] * default_number_of_steps
        self.pitch = [False] * default_number_of_steps
        self.octave = [False] * default_number_of_steps
        self.gate = [False] * default_number_of_steps
        self.mutes_skips = [False] * default_number_of_steps
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
        self.midi_out_device = iso.MidiOutputDevice(
            device_name=f"{self.name} sequencer", send_clock=True, virtual=True
        )
        # TODO: had to remove the input device from here for this to work
        self.local_timeline = iso.Timeline(
            tempo=120, output_device=self.midi_out_device
        )
        # We should use track.update() to update the sequencers to match the pad state
        self.playhead_track = timeline.schedule(
            {
                "action": lambda: (
                    tick_callback(self.name, len(self.pitch)),
                    self.seq_playhead_update(),
                ),
                "duration": 0.25,
            }
        )

    def load_state(self):
        try:
            if os.path.exists(self.seq_filename):
                dump = json.load(open(self.seq_filename))
                self.locks = dump["locks"]
                self.note = dump["note"]
                self.pitch = dump[TRACK_NAMES_METRO[0]]
                self.octave = dump[TRACK_NAMES_METRO[1]]
                self.gate = dump[TRACK_NAMES_METRO[2]]
                self.mutes_skips = dump[TRACK_NAMES_METRO[3]]
                self.aux_1 = dump[TRACK_NAMES_METRO[4]]
                self.aux_2 = dump[TRACK_NAMES_METRO[5]]
                self.aux_3 = dump[TRACK_NAMES_METRO[6]]
                self.aux_4 = dump[TRACK_NAMES_METRO[7]]
        except Exception as e:
            print("Exception in seq load_state")
            traceback.print_exc()

    def save_state(self):
        try:
            sequencer_state = {
                "locks": self.locks,
                "note": self.note,
                TRACK_NAMES_METRO[0]: self.pitch,
                TRACK_NAMES_METRO[1]: self.octave,
                TRACK_NAMES_METRO[2]: self.gate,
                TRACK_NAMES_METRO[3]: self.mutes_skips,
                TRACK_NAMES_METRO[4]: self.aux_1,
                TRACK_NAMES_METRO[5]: self.aux_2,
                TRACK_NAMES_METRO[6]: self.aux_3,
                TRACK_NAMES_METRO[7]: self.aux_4,
            }
            json.dump(
                sequencer_state, open(self.seq_filename, "w")
            )  # Save to file
        except Exception as e:
            print("Exception in seq save_state")
            traceback.print_exc()

    def seq_playhead_update(self):
        self.playhead = int((iso.PCurrentTime.get_beats(self) * 4 + 0.01))
        self.update_notes()
        self.evaluate_and_play_notes()

    def evaluate_and_play_notes(self):
        try:
            pass
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
            return self.gate
        elif lane == TRACK_NAMES_METRO[3]:
            return self.mutes_skips
        elif lane == TRACK_NAMES_METRO[4]:
            return self.aux_1
        elif lane == TRACK_NAMES_METRO[5]:
            return self.aux_2
        elif lane == TRACK_NAMES_METRO[6]:
            return self.aux_3
        elif lane == TRACK_NAMES_METRO[7]:
            return self.aux_4

    def get_current_instrument_short_name_helper(self):
        return self.app.instrument_selection_mode.get_current_instrument_short_name()

    def set_states(self, lane, values):
        for index, value in enumerate(values):
            self.set_state(lane, index, value)

    def set_state(self, lane, index, value):
        # print(f"lane: {lane} index: {index} value: {value}")
        self.update_notes()
        if lane == TRACK_NAMES_METRO[0]:
            self.pitch[index] = value
        elif lane == TRACK_NAMES_METRO[1]:
            self.octave[index] = value
        elif lane == TRACK_NAMES_METRO[2]:
            self.gate[index] = value
        elif lane == TRACK_NAMES_METRO[3]:
            self.mutes_skips[index] = value
        elif lane == TRACK_NAMES_METRO[4]:
            self.aux_1[index] = value
        elif lane == TRACK_NAMES_METRO[5]:
            self.aux_2[index] = value
        elif lane == TRACK_NAMES_METRO[6]:
            self.aux_3[index] = value
        elif lane == TRACK_NAMES_METRO[7]:
            self.aux_4[index] = value

    def set_lock_state(self, index, parameter_idx, value):
        # print(f"Set_lock_state: index {index}, param_idx {parameter_idx}, value {value}")
        selected_track = self.app.sequencer_mode.selected_track
        self.locks[selected_track][index][parameter_idx] = value

    def get_lock_state(self, index, parameter_idx):
        # print(f"Set_lock_state: index {index}, param_idx {parameter_idx}, value {value}")
        selected_track = self.app.sequencer_mode.selected_track
        return self.locks[selected_track][index][parameter_idx]
