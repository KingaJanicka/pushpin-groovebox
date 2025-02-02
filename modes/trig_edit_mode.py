import definitions
import push2_python
import os
import json
from osc_controls import (
    OSCControl,
    ControlSpacer,
    OSCControlSwitch,
    OSCGroup,
)
from glob import glob
from user_interface.display_utils import show_text
from pathlib import Path
import logging

log = logging.getLogger("preset_selection_mode")

# log.setLevel(level=logging.DEBUG)


class TrigEditMode(definitions.PyshaMode):

    current_page = 0
    controls = []
    state = [0] * 8
    current_address = None
    encoder_touch_state = [False, False, False, False, False, False, False, False]

    def initialize(self, settings=None, **kwargs):

        self.get_color = kwargs.get("get_color")
        # Sets up controls for the trig menu
        note = OSCControl(
            {
                "$type": "control-range",
                "label": "Note",
                "address": f"/",
                "min": 0,
                "max": 1,
            },
            self.get_current_instrument_color_helper,
            self.send_message,
        )
        self.controls.append(note)

        octave = OSCControl(
            {
                "$type": "control-range",
                "label": "Octave",
                "address": f"/",
                "min": 0,
                "max": 1,
            },
            self.get_current_instrument_color_helper,
            self.send_message,
        )
        self.controls.append(octave)

        velocity = OSCControl(
            {
                "$type": "control-range",
                "label": "Velocity",
                "address": f"/",
                "min": 0,
                "max": 1,
            },
            self.get_current_instrument_color_helper,
            self.send_message,
        )
        self.controls.append(velocity)

        len = OSCControl(
            {
                "$type": "control-range",
                "label": "Length",
                "address": f"/",
                "min": 0,
                "max": 1,
            },
            self.get_current_instrument_color_helper,
            self.send_message,
        )
        self.controls.append(len)

        prob = OSCControl(
            {
                "$type": "control-range",
                "label": "Prob%",
                "address": f"/",
                "min": 0,
                "max": 1,
            },
            self.get_current_instrument_color_helper,
            self.send_message,
        )
        self.controls.append(prob)

        not_cond= OSCControl(
            {
                "$type": "control-range",
                "label": "Not",
                "address": f"/",
                "min": 0,
                "max": 1,
            },
            self.get_current_instrument_color_helper,
            self.send_message,
        )
        self.controls.append(not_cond)

        cond = OSCControl(
            {
                "$type": "control-range",
                "label": "Condition",
                "address": f"/",
                "min": 0,
                "max": 1,
            },
            self.get_current_instrument_color_helper,
            self.send_message,
        )
        self.controls.append(cond)

        recur = OSCControl(
            {
                "$type": "control-range",
                "label": "Recurrance",
                "address": f"/",
                "min": 0,
                "max": 1,
            },
            self.get_current_instrument_color_helper,
            self.send_message,
        )
        self.controls.append(recur)

    def send_message(self):
        pass

    def activate(self):
        self.current_page = 0
        self.update_buttons()
        self.update_pads()

    def new_instrument_selected(self):
        self.current_page = 0
        self.app.pads_need_update = True
        self.app.buttons_need_update = True

    def should_be_enabled(self):
        return True

    def get_all_distinct_instrument_short_names_helper(self):
        return (
            self.app.instrument_selection_mode.get_all_distinct_instrument_short_names()
        )

    def get_current_instrument_short_name_helper(self):
        return self.app.instrument_selection_mode.get_current_instrument_short_name()

    def get_current_instrument_color_helper(self):
        return self.app.instrument_selection_mode.get_current_instrument_color()

    def get_current_page(self):
        return self.current_page

    def activate(self):
        self.update_pads()
        self.set_knob_postions()

    def deactivate(self):
        self.app.push.pads.set_all_pads_to_color(color=definitions.BLACK)
        self.push.buttons.set_button_color(
            push2_python.constants.BUTTON_LEFT, definitions.BLACK
        )
        self.push.buttons.set_button_color(
            push2_python.constants.BUTTON_RIGHT, definitions.BLACK
        )
        self.app.buttons_need_update = True
        self.app.pads_need_update = True

    def update_buttons(self):
        pass

    def prepare_lock(self):
        seq = self.app.sequencer_mode.instrument_sequencers[self.get_current_instrument_short_name_helper()]
        notes_being_played = []
        notes_being_played = self.app.sequencer_mode.notes_being_played
        print("Notes played", notes_being_played)

        # Take all notes being pressed
        # Convert to index by removing 36
        # loop to check for all knobs being touched / turned
        # if a knob is turned use seq.set_lock_state to set lock at said index to said note values

        # TODO: This is getting close but I don't think it works just yet
        for encoder_idx, encoder_state in enumerate(self.encoder_touch_state):
            if encoder_state == True:
                for note in notes_being_played:
                    seq_idx = note["note"] - 36
                    seq.set_lock_state(seq_idx, encoder_idx, self.controls[encoder_idx].value)
                    
    
    def update_display(self, ctx, w, h):
        visible_controls = self.controls
        offset = 0
        for control in visible_controls:
            if offset + 1 <= 8:
                try:
                    control.draw(ctx, offset)
                    offset += 1
                except:
                    pass
    def on_button_pressed(self, button_name):
        pass

    def on_encoder_rotated(self, encoder_name, increment=0.01):
        try:
            encoder_idx = [
                push2_python.constants.ENCODER_TRACK1_ENCODER,
                push2_python.constants.ENCODER_TRACK2_ENCODER,
                push2_python.constants.ENCODER_TRACK3_ENCODER,
                push2_python.constants.ENCODER_TRACK4_ENCODER,
                push2_python.constants.ENCODER_TRACK5_ENCODER,
                push2_python.constants.ENCODER_TRACK6_ENCODER,
                push2_python.constants.ENCODER_TRACK7_ENCODER,
                push2_python.constants.ENCODER_TRACK8_ENCODER,
            ].index(encoder_name)
            self.prepare_lock()
            control = self.controls[encoder_idx]
            control.update_value(increment)
        
        except ValueError:
            pass  # Encoder not in list

    def send_osc(self, *args, instrument_shortname=None):
        instrument = self.app.osc_mode.instruments.get(
            instrument_shortname or self.app.osc_mode.get_current_instrument_short_name_helper(), None
        )
        if instrument:
            return instrument.send_message(*args)

    def on_encoder_touched(self, encoder_name):
        try:
            encoder_idx = [
                push2_python.constants.ENCODER_TRACK1_ENCODER,
                push2_python.constants.ENCODER_TRACK2_ENCODER,
                push2_python.constants.ENCODER_TRACK3_ENCODER,
                push2_python.constants.ENCODER_TRACK4_ENCODER,
                push2_python.constants.ENCODER_TRACK5_ENCODER,
                push2_python.constants.ENCODER_TRACK6_ENCODER,
                push2_python.constants.ENCODER_TRACK7_ENCODER,
                push2_python.constants.ENCODER_TRACK8_ENCODER,
            ].index(encoder_name)
            self.encoder_touch_state[encoder_idx] = True
            

        except ValueError:
            pass

    
    def on_encoder_released(self, encoder_name):
        try:
            encoder_idx = [
                push2_python.constants.ENCODER_TRACK1_ENCODER,
                push2_python.constants.ENCODER_TRACK2_ENCODER,
                push2_python.constants.ENCODER_TRACK3_ENCODER,
                push2_python.constants.ENCODER_TRACK4_ENCODER,
                push2_python.constants.ENCODER_TRACK5_ENCODER,
                push2_python.constants.ENCODER_TRACK6_ENCODER,
                push2_python.constants.ENCODER_TRACK7_ENCODER,
                push2_python.constants.ENCODER_TRACK8_ENCODER,
            ].index(encoder_name)
            self.encoder_touch_state[encoder_idx] = False
        except ValueError:
            pass
