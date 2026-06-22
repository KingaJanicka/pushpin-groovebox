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


default_number_of_steps = 64

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

    def __init__(
        self, instrument, tick_callback, playhead, send_osc_func, global_timeline, app
    ):
        self.locks = []

        # stores values per step
        for step_idx in range(default_number_of_steps):
            self.locks.append([])
            for device_idx in range(17):
                self.locks[step_idx].append(
                    [None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None]
                )
        
        self.app = app
        # Immutable param snapshot refreshed each frame by the asyncio thread.
        # The MIDI clock thread reads this atomically — see SequencerParams.
        self.params: SequencerParams = SequencerParams()
        # True while waiting for the asyncio thread to call global_timeline.reset().
        # Prevents reset_index() from firing on every tick during the ~33ms gap.
        self._pending_reset: bool = False
        self.step_index = 0
        self.step_count = 0
        self.prev_step_index = 0
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
        
    def seq_playhead_update(self):
        # Take a single atomic reference to the param snapshot for this tick.
        # All UI-owned values are read from here, not from app/mode objects.
        params = self.params

        if not params.sequencer_is_playing:
            return

        self.playhead = int((iso.PCurrentTime.get_beats(self) * 4 + 0.01))  # type: ignore[arg-type]

        main_step_count = round(
            (self.app.global_timeline.current_time + 0.1) * params.main_seq_time_scale / 2, 1
        )

        if main_step_count >= params.main_pattern_len * params.main_seq_time_scale / 2:
            if not self._pending_reset:
                self._pending_reset = True
                self.reset_index()
                self.scale_count = 0
                self.next_step_index = 0
                # Signal the asyncio thread to reset the timeline rather than
                # calling it here — resetting the timeline from within its own
                # tick callback corrupts internal iteration state.
                self.app.timeline_needs_reset = True
            # Don't advance steps while waiting for the timeline to reset.
            return
        else:
            self._pending_reset = False

        if self.scale_count == 0:
            # Play the note, reset the counter for the time scale
            self.step_count += 1
            self.evaluate_and_play_notes()
            self.scale_count = params.seq_time_scale + 1

        elif self.scale_count != 0:
            # This has to do with the time scale setting
            # This block makes sure we only fire every X 1/32nd notes
            self.scale_count -= 1

        if self.scale_count == 1:
            # Increment right before the note is played, so the visual feedback
            # lines up. The if clause prevents going over the bounds with next step
            # and avoids visual glitches with the playhead.
            if self.step_count == params.pattern_len:
                self.reset_index()
                self.next_step_index = 0
            else:
                self.increment_index()
                self.increment_next_step_index(index=self.step_index)
                
    


    def increment_index(self, index = None):
        
        current_index = index if index != None else self.step_index
        next_step_index = (current_index + 1) % 64
        
        
        column = int(next_step_index / 8)
        skips_idx = column*8
        
        if self.gate[next_step_index] != False and self.mutes_skips[skips_idx] != True:
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
        
        column = int(next_step_index / 8)
        skips_idx = column*8
        
        if self.gate[next_step_index] != False and self.mutes_skips[skips_idx] != True:
            self.next_step_index = next_step_index
            return 
        
        else:
            self.increment_next_step_index(index=next_step_index)
            
    def increment_previous_step_index(self, index = None):
        current_index = index if index != None else self.step_index
        prev_step_index = (current_index - 1) % 64
        column = int(prev_step_index / 8)
        skips_idx = column*8
        
    
        if self.gate[prev_step_index] != False and self.mutes_skips[skips_idx] != True:
            self.prev_step_index = prev_step_index
            return 
        
        else:
            self.increment_previous_step_index(index=prev_step_index)
        
    def reset_index(self):
        self.step_count = 0
        self.step_index = 0
        self.next_step_index = 1
        
    def evaluate_and_play_notes(self):
        try:
            # Read all UI-owned values from the immutable snapshot — not from
            # app/mode objects directly, which are owned by the asyncio thread.
            params = self.params
            gate_track_active = params.gate_track_active

            instrument = self.app.instruments[self.name]

            if self.gate[self.step_index] != "Off" and gate_track_active:
                gate = 1
                pitch = self.pitch[self.step_index] if self.pitch[self.step_index] is not None else 0
                octave = self.octave[self.step_index] * 12 if self.octave[self.step_index] is not None else 0

                pitch_and_octave = pitch + octave
                velocity = ((self.velocity[self.step_index] + 1) * 16 - 1) if self.velocity[self.step_index] is not None else 1
                gate = None

                gate_len = params.gate_len
                
                column = int(self.step_index / 8)
                mutes_idx = column*8+1
                
                
                prob = 1
                
                # checking columns for the True statement
                for x in range(7):
                    if self.mutes_skips[mutes_idx + x] == True:
                        prob = x
                        
                next_step_index = self.next_step_index
                
                if self.gate[next_step_index] == "Tie":
                    gate = 0.3
                else:
                    gate = 0.25 * gate_len
            
                
                if prob >= random.randint(1, 6):
                    # We need to reset values that were changed by param locks
                    for control in self.controls_to_reset:
                        self.app.send_osc(control.address, float(control.value), instrument.name)
                    self.timeline.schedule(
                        {"note": pitch_and_octave, "gate": gate, "amplitude": velocity}, count=1, output_device=self.midi_out_device
                    )
                    self.controls_to_reset.clear()
            
            
            # This sends the param locks, out of the prev if statement
            # so it triggers even if the gate is off
            for slot_idx, slot in enumerate(instrument.slots):
                # get lock_scale value, mult by lock_val
                lock_scale_value = None
                if self.lock_scale[self.step_index] == 0:
                    lock_scale_value = 0
                else:
                    lock_scale_value = self.lock_scale[self.step_index] / 7
                if slot != None:
                    for device_idx, device in enumerate(instrument.devices[slot_idx]):
                        for command in enumerate(device.init):
                            
                            if command[1]["address"] == slot["address"] and command[1]["value"] == slot["value"]:
                                # we have the right device
                                # Now we just need to enum the controls and send the values 
                                for control_idx, control in enumerate(device.controls):
                                    lock_address = control.address
                                    lock_value = None
                                    if self.locks[self.step_index][slot_idx][control_idx] != None:
                                        lock_value = self.locks[self.step_index][slot_idx][control_idx] 
                                        if hasattr(control, "value"):
                                            lock_offset = lock_value - control.value
                                            value_after_scale = lock_offset * lock_scale_value + control.value
                                            if lock_value != None:
                                                self.app.send_osc(lock_address, value_after_scale, instrument.name)
                                                self.controls_to_reset.append(control)
                                    else:
                                        lock_value = 0
                # This elif branch is for slots that have only one device and therefore
                # don't have the device address/val in the init
                elif slot_idx == 2 or slot_idx == 3 or slot_idx == 4:
                    for device_idx, device in enumerate(instrument.devices[slot_idx]):
                        # we have the right device
                        # Now we just need to enum the controls and send the values 
                        for control_idx, control in enumerate(device.controls):
                            lock_address = control.address
                            lock_value = None
                            if self.locks[self.step_index][slot_idx][control_idx] != None:
                                lock_value = self.locks[self.step_index][slot_idx][control_idx] 
                                if hasattr(control, "value"):
                                    lock_offset = lock_value - control.value
                                    value_after_scale = lock_offset * lock_scale_value + control.value
                                    if lock_value != None and lock_address != None:
                                        self.app.send_osc(lock_address, value_after_scale, instrument.name)
                                        self.controls_to_reset.append(control)
                            else:
                                lock_value = 0


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
        trig_edit_active = self.app.is_mode_active(self.app.trig_edit_mode)
        device = self.app.osc_mode.get_current_instrument_device()
        device_idx = None
        
        if trig_edit_active == True:
            device_idx = self.app.trig_edit_mode.slot
        else:
            device_idx = device.slot
            
        # print(f"Set_lock_state: index {index}, device_idx {device_idx}, param_idx {parameter_idx}, value {value}")
        selected_track = self.app.metro_sequencer_mode.selected_track
        for x in range(8):
            self.locks[index * 8 + x][device_idx][parameter_idx] = value



    def get_lock_state(self, index, parameter_idx):
        # print(f"Get_lock_state: index {index}, param_idx {parameter_idx}")
        trig_edit_active = self.app.is_mode_active(self.app.trig_edit_mode)
        device = self.app.osc_mode.get_current_instrument_device()
        device_idx = None
        
        if trig_edit_active == True:
            device_idx = self.app.trig_edit_mode.slot
        else:
            device_idx = device.slot
            
        selected_track = self.app.metro_sequencer_mode.selected_track
        return self.locks[index * 8][device_idx][parameter_idx]

    def clear_all_locks_for_step(self, index):
        device = self.app.osc_mode.get_current_instrument_device()
        for x in range(8):
            for device_idx in range(17):
                for parameter_idx in range(16):
                    self.locks[index * 8 + x][device_idx][parameter_idx] = None
            