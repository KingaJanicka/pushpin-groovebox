from __future__ import annotations

import asyncio
import isobar as iso
import random
import json
import os
import traceback
from pythonosc.udp_client import SimpleUDPClient
from definitions import TRACK_NAMES_METRO
from sequencer.sequencer_params import SequencerParams


def lockable_controls(device):
    """(lock index, control) for every control a p-lock can be on, across all
    of the device's pages. Locks are recorded and shown at page * 8 + position
    on the page; playing only the page on screen (indexed 0..7) dropped every
    other page's locks and put page 1's on whichever page was showing."""
    pages = getattr(device, "pages", None)
    if not pages:
        yield from enumerate(device.get_visible_controls())
        return
    for page_idx, page in enumerate(pages):
        for position, control in enumerate(page):
            index = page_idx * 8 + position
            if index >= LOCKS_PER_DEVICE:
                return
            yield index, control


def lock_message(control, value):
    """The (address, value) a p-lock of ``value`` on ``control`` plays. A menu's
    locks are item positions: play the item's own message, not the position
    (most of Surge's menus send their position, but not all, and mono2k's
    MOD type sends 21/64/106)."""
    items = getattr(control, "items", None)
    if items:
        idx = min(max(int(round(float(value))), 0), len(items) - 1)
        item = items[idx]
        if item.address is not None and item.value is not None:
            return item.address, float(item.value)
    return control.address, value


default_number_of_steps = 64
LOCKS_PER_DEVICE = 18          # the length of each device's list in self.locks

from typing import Any

class SequencerMetro(object):
    tick_callback: Any = None
    send_osc_func: Any = None
    playhead = 0
    pitch: list[Any] = []
    octave: list[Any] = []
    gate: list[Any] = []
    mutes_skips: list[Any] = []
    lock_scale: list[Any] = []
    aux_2: list[Any] = []
    aux_3: list[Any] = []
    aux_4: list[Any] = []
    locks: list[Any] = []
    note: list[int | None] = []
    playhead_track: Any = None
    note_track: Any = None
    midi_out_device: Any = None
    midi_in_name: str | None = None
    midi_in_device: Any = None
    index: Any = None
    # The pitch, octave and velocity of the last note played, and the last
    # p-lock scaling used: what a muted track holds them at.
    held_pitch: int | None = None
    held_octave: int | None = None
    held_velocity: int | None = None
    held_lock_scale: float | None = None

    def __init__(
        self, instrument, tick_callback, playhead, send_osc_func, global_timeline, app
    ):
        self.locks = []

        # stores values per step
        for step_idx in range(default_number_of_steps):
            self.locks.append([])
            for device_idx in range(17):
                self.locks[step_idx].append(
                    [None] * LOCKS_PER_DEVICE
                )
        
        self.app = app
        # Immutable param snapshot refreshed each frame by the asyncio thread.
        # The MIDI clock thread reads this atomically — see SequencerParams.
        self.params: SequencerParams = SequencerParams()
        # True while waiting for the asyncio thread to call global_timeline.reset().
        # Prevents reset_index() from firing on every tick during the ~33ms gap.
        self._pending_reset: bool = False
        self.main_ticks_to_reset = 0
        self.seq_ticks_to_reset = 0
        self.prev_step_index = 0
        self.step_index = 0
        self.show_locks = False
        self.next_step_index = 1
        self.steps_held = []
        self.scale_count = 1
        self.controls_to_reset = []
        self.name = instrument.name
        self.note = [None] * default_number_of_steps
        self.pitch = [False] * default_number_of_steps
        self.octave = [False] * default_number_of_steps
        self.velocity = [False] * default_number_of_steps
        self.gate = [False] * default_number_of_steps
        self.mutes_skips = [False] * default_number_of_steps
        self.lock_scale = [False] * default_number_of_steps
        self.aux_2 = [False] * default_number_of_steps
        self.aux_3 = [False] * default_number_of_steps
        self.playhead = playhead
        self.send_osc_func = send_osc_func
        self.timeline = global_timeline
        for item in iso.io.midi.get_midi_input_names():
            if item.startswith(self.name) == True:
                self.midi_in_name = item

        self.note_pattern = iso.PSeq(self.note)
        self.midi_in_device = instrument.midi_out_device
        self.midi_in_name = instrument.midi_in_name
        self.midi_out_device = instrument.midi_out_device

        # self.load_state()

        # We should use track.update() to update the sequencers to match the pad state
        self.playhead_track = self.timeline.schedule(
            {
                "action": lambda: (
                    # tick_callback(self.name, len(self.pitch)),
                    self.seq_playhead_update(),
                ),
                "duration": 0.0625,
            }, 
        )
    def reschedule_playhead_tracks(self):
        # unschedule
        # TODO: finish this func
        self.timeline.unschedule(self.playhead_track)
        
        # self.playhead_track = self.timeline.schedule(
        #     {
        #         "action": lambda: (
        #             # tick_callback(self.name, len(self.pitch)),
        #             self.seq_playhead_update(),
        #         ),
        #         "duration": 0.0625,
        #     }, 
        # )

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
            return self.lock_scale
        elif name == TRACK_NAMES_METRO[6]:
            return self.aux_2
        elif name == TRACK_NAMES_METRO[7]:
            return self.aux_3
        
    def get_state_filename(self, clip=0):
        return f"seq_metro_{self.name}_{clip}.json"
        
        
    def load_state(self, clip=0):
        seq_filename = self.get_state_filename(clip=clip)
        try:
            if os.path.exists(seq_filename):
                dump = json.load(open(seq_filename))
            elif os.path.exists(f"init_state.json"):
                dump = json.load(open("init_state.json"))
            self.locks = dump["locks"]
            self.note = dump["note"]
            self.pitch = dump[TRACK_NAMES_METRO[0]]
            self.octave = dump[TRACK_NAMES_METRO[1]]
            self.aux_4 = dump[TRACK_NAMES_METRO[2]]
            self.gate = dump[TRACK_NAMES_METRO[3]]
            self.mutes_skips = dump[TRACK_NAMES_METRO[4]]
            self.lock_scale = dump[TRACK_NAMES_METRO[5]]
            self.aux_2 = dump[TRACK_NAMES_METRO[6]]
            self.aux_3 = dump[TRACK_NAMES_METRO[7]]
            
            self.app.metro_sequencer_mode.update_pads_to_seq_state()
        except Exception as e:
            print("Exception in seq load_state")
            traceback.print_exc()

    def save_state(self, clip=0):
        seq_filename = self.get_state_filename(clip=clip)
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
                TRACK_NAMES_METRO[5]: self.lock_scale,
                TRACK_NAMES_METRO[6]: self.aux_2,
                TRACK_NAMES_METRO[7]: self.aux_3,
            }
            json.dump(
                sequencer_state, open(seq_filename, "w")
            )  # Save to file
        except Exception as e:
            print("Exception in seq save_state")
            traceback.print_exc()

    def delete_state(self, clip):
        seq_filename = self.get_state_filename(clip=clip)
        os.remove(seq_filename)
        
    def advance_and_evaluate_main_tick(self):
        # Counts down ticks down to zero from length of main reset
        
        if self.main_ticks_to_reset <= 0:
            self.main_ticks_to_reset = self.params.main_pattern_len * self.params.main_seq_time_scale
            # Sets this to zero so it resets in the fuction below
            self.seq_ticks_to_reset = 0
            
        self.main_ticks_to_reset -= 1
        
    def advance_and_evaluate_sequencer_tick(self):
        pattern_was_reset = False
        
        # This first branch for when we reset, so we don't skip over the first step
        if self.seq_ticks_to_reset == 0:
            self.seq_ticks_to_reset = self.params.seq_time_scale * self.params.pattern_len
            self.reset_index()
            self.evaluate_and_play_notes()

        elif self.seq_ticks_to_reset % self.params.seq_time_scale <= 0:
            self.increment_index()
            self.increment_next_step_index(index=self.step_index)
            self.evaluate_and_play_notes()

        self.seq_ticks_to_reset -= 1
                

    def seq_playhead_update(self):
        # Take a single atomic reference to the param snapshot for this tick.
        # All UI-owned values are read from here, not from app/mode objects.
        params = self.params
        if not params.sequencer_is_playing:
            return
        
        self.playhead = self.get_current_playhead_value()

        self.advance_and_evaluate_main_tick()
                
        self.advance_and_evaluate_sequencer_tick()

    def get_current_playhead_value(self):
        return int((iso.PCurrentTime.get_beats(self) * 4 + 0.01))  # type: ignore[arg-type]

    def reset_index(self):
        self.step_index = 0
        self.next_step_index = 0
        self.increment_next_step_index(index=self.step_index)
        

    def increment_index(self, index = None):
        
        current_index = index if index != None else self.step_index
        next_step_index = (current_index + 1) % 64
        
        
        if self.gate[next_step_index] != False and not self.step_is_skipped(next_step_index):
            self.step_index = next_step_index
            # Signal the asyncio thread to update pads — calling update_pads()
            # directly here runs push2_python USB code from the MIDI clock thread,
            # which races with the asyncio event loop doing the same.
            self.app.pads_need_update = True
            return
        else:
            self.increment_index(index=next_step_index)
            
    def increment_next_step_index(self, index = None):
        current_index = index if index != None else self.step_index
        next_step_index = (current_index + 1) % 64
        
        if self.gate[next_step_index] != False and not self.step_is_skipped(next_step_index):
            self.next_step_index = next_step_index
            return 
        
        else:
            self.increment_next_step_index(index=next_step_index)
            
    def increment_previous_step_index(self, index = None):
        current_index = index if index != None else self.step_index
        prev_step_index = (current_index - 1) % 64
        if self.gate[prev_step_index] != False and not self.step_is_skipped(prev_step_index):
            self.prev_step_index = prev_step_index
            return 
        
        else:
            self.increment_previous_step_index(index=prev_step_index)
        
    def evaluate_and_play_notes(self):
        try:
            # Read all UI-owned values from the immutable snapshot — not from
            # app/mode objects directly, which are owned by the asyncio thread.
            params = self.params
            gate_track_active = params.gate_track_active

            instrument = self.app.instruments[self.name]

            if self.gate[self.step_index] != "Off" and gate_track_active:
                gate = 1
                pitch, octave, velocity = self.note_for_step(params)
                pitch_and_octave = pitch + octave * 12
                gate = None

                gate_len = params.gate_len
                
                prob = self.probability_for_step(params)

                next_step_index = self.next_step_index
                
                if self.gate[next_step_index] == "Tie":
                    gate = 0.3
                else:
                    gate = 0.25 * gate_len
            
                
                if prob >= random.randint(1, 6):
                    # We need to reset values that were changed by param locks
                    for control, unlocked in self.controls_to_reset:
                        # print(control.name, control.label)
                        if control.name == "Switch":
                            control.reset_group()
                        else:
                            # Back to the value it had before the lock. Not
                            # control.value: the synth's echo of the lock has
                            # overwritten that with the locked value, which made
                            # every p-lock stick after its step.
                            control.value = unlocked
                            self.app.send_osc(*lock_message(control, float(unlocked)), instrument.name)
                    self.held_pitch, self.held_octave, self.held_velocity = pitch, octave, velocity
                    self.timeline.schedule(
                        {"note": pitch_and_octave, "gate": gate, "amplitude": velocity}, count=1,
                        # the track's active engine's port (Surge's, or its mono2k port), looked up
                        # each step so an engine switch takes effect on the next note
                        output_device=instrument.midi_out_device
                    )
                    self.controls_to_reset.clear()
            
            
            # This sends the param locks, out of the prev if statement
            # so it triggers even if the gate is off
            lock_scale_value = self.lock_scale_for_step(params)
            for slot_idx, slot in enumerate(instrument.slots):
                if slot != None:
                    for device_idx, device in enumerate(instrument.devices[slot_idx]):
                        for command in enumerate(device.init):
                            
                            if command[1]["address"] == slot["address"] and command[1]["value"] == slot["value"]:
                                # we have the right device
                                # Now we just need to enum the controls and send the values 
                                # This needs to go through VISIBLE controls, so that groups don't get shafted
                                for control_idx, control in lockable_controls(device):
                                    lock_address = control.address
                                    lock_value = None
                                    if self.locks[self.step_index][slot_idx][control_idx] != None:
                                        lock_value = self.locks[self.step_index][slot_idx][control_idx] 
                                        if hasattr(control, "value"):
                                            unlocked = self.remember_unlocked(control)   # (before the lock and its echo)
                                            lock_offset = lock_value - unlocked
                                            value_after_scale = lock_offset * lock_scale_value + unlocked
                                            
                                            if lock_value != None and lock_address != None:
                                                self.play_lock(control, value_after_scale, instrument)
                                            elif lock_value != None and control.name == "Switch":
                                                    control.update_value_lock(value_after_scale)
                                            
                                                
                                    else:
                                        lock_value = 0
                # This elif branch is for slots that have only one device and therefore
                # don't have the device address/val in the init
                elif slot_idx in getattr(instrument.engine, "always_shown_slots", (2, 3, 4)):
                    for device_idx, device in enumerate(instrument.devices[slot_idx]):
                        # we have the right device
                        # Now we just need to enum the controls and send the values 
                        # Visible controls so we don't ommit groups
                        for control_idx, control in lockable_controls(device):
                            lock_address = control.address
                            lock_value = None
                            if self.locks[self.step_index][slot_idx][control_idx] != None:
                                lock_value = self.locks[self.step_index][slot_idx][control_idx] 
                                if hasattr(control, "value"):
                                    unlocked = self.remember_unlocked(control)   # (before the lock and its echo)
                                    lock_offset = lock_value - unlocked
                                    value_after_scale = lock_offset * lock_scale_value + unlocked
                                    
                                    if lock_value != None and lock_address != None:
                                        self.play_lock(control, value_after_scale, instrument)
                                    elif lock_value != None and control.name == "Switch":
                                            control.update_value_lock(value_after_scale)
                                    
                            else:
                                lock_value = 0


        except Exception as e:
            print("Error in evaluate_and_play_notes")
            traceback.print_exc()


    def note_for_step(self, params):
        """The (pitch, octave, velocity) the current step plays. A muted pitch,
        octave or velocity track holds that part at the last note played; the
        other parts still follow their tracks. Nothing played yet: the step's
        own value."""
        pitch = self.pitch[self.step_index]
        pitch = pitch if pitch is not None else 0
        octave = self.octave[self.step_index]
        octave = octave if octave is not None else 0
        velocity = self.velocity[self.step_index]
        velocity = (velocity + 1) * 16 - 1 if velocity is not None else 1
        if not params.pitch_track_active and self.held_pitch is not None:
            pitch = self.held_pitch
        if not params.octave_track_active and self.held_octave is not None:
            octave = self.held_octave
        if not params.velocity_track_active and self.held_velocity is not None:
            velocity = self.held_velocity
        return pitch, octave, velocity

    def probability_for_step(self, params):
        """The current step's chance to play, out of 6 (it plays when this is
        at least a roll of 1-6). Rows 1-7 of the step's mutes/skips column
        pick it; a muted mutes/skips track always plays."""
        if not params.mutes_skips_track_active:
            return 6
        mutes_idx = int(self.step_index / 8) * 8 + 1
        prob = 1
        for x in range(7):
            if self.mutes_skips[mutes_idx + x] == True:
                prob = x
        return prob

    def step_is_skipped(self, index):
        """Whether the step at ``index`` is skipped: row 0 of its mutes/skips
        column. Nothing is skipped while the mutes/skips track is muted."""
        if not self.params.mutes_skips_track_active:
            return False
        return self.mutes_skips[int(index / 8) * 8] == True

    def lock_scale_for_step(self, params):
        """How much of each p-lock the current step applies, 0-1. A muted
        lock-scale track keeps the last scaling used. Nothing used yet: the
        step's own value."""
        if not params.lock_scale_track_active and self.held_lock_scale is not None:
            return self.held_lock_scale
        scale = self.lock_scale[self.step_index]
        self.held_lock_scale = 0 if scale == 0 else scale / 7
        return self.held_lock_scale

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
            return self.lock_scale
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
        # print(f"lane: {lane} index: {index} value: {value}")s
        
        # print(device.label, device.slot)
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
            self.lock_scale[index] = value
        elif lane == TRACK_NAMES_METRO[6]:
            self.aux_2[index] = value
        elif lane == TRACK_NAMES_METRO[7]:
            self.aux_3[index] = value

    def set_lock_state(self, index, parameter_idx, value):
        device = self.app.osc_mode.get_current_instrument_device()
        device_idx = device.slot
            
        # print(f"Set_lock_state: index {index}, device_idx {device_idx}, param_idx {parameter_idx}, value {value}")
        selected_track = self.app.metro_sequencer_mode.selected_track
        for x in range(8):
            self.locks[index * 8 + x][device_idx][parameter_idx] = value



    def get_lock_state(self, index, parameter_idx):
        # print(f"Get_lock_state: index {index}, param_idx {parameter_idx}")
        device = self.app.osc_mode.get_current_instrument_device()
        device_idx = device.slot
            
        selected_track = self.app.metro_sequencer_mode.selected_track
        return self.locks[index * 8][device_idx][parameter_idx]

    def play_lock(self, control, value, instrument):
        """Send a p-lock without moving the control's display: it keeps the
        knob's position, and the lock shows only while its pad is held. The
        synth's echo of the lock is ignored, whether it comes back at once
        (mono2k's MIDI-CC client) or later (Surge over OSC)."""
        knob = control.value
        address, sent = lock_message(control, value)
        echoes = getattr(control, "lock_echoes", None) or getattr(control, "recent_sends", None)
        if echoes is not None:
            echoes.add(sent)
        self.app.send_osc(address, sent, instrument.name)
        control.value = knob

    def remember_unlocked(self, control):
        """A lock is about to be sent to ``control``: keep the value it goes back
        to (its own, from before any lock still waiting to be undone), and
        return it: the base a scaled lock is measured from."""
        for c, unlocked in self.controls_to_reset:
            if c is control:
                return unlocked
        self.controls_to_reset.append((control, control.value))
        return control.value

    def clear_all_locks(self):
        """Every step's p-locks: they are stored by page position, so they
        mean other parameters once the track plays another engine."""
        for step_locks in self.locks:
            for device_locks in step_locks:
                for parameter_idx in range(len(device_locks)):
                    device_locks[parameter_idx] = None

    def clear_all_locks_for_step(self, index):
        device = self.app.osc_mode.get_current_instrument_device()
        for x in range(8):
            for device_idx in range(17):
                for parameter_idx in range(16):
                    self.locks[index * 8 + x][device_idx][parameter_idx] = None
            

    