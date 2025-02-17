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


    
    def update_display(self, ctx, w, h):
        visible_controls = self.controls
        offset = 0
        seq = self.app.sequencer_mode.instrument_sequencers[self.get_current_instrument_short_name_helper()]
        for control in visible_controls:
            draw_lock = True if len(seq.steps_held) is not 0 else False
            if offset + 1 <= 8:
                try:
                    step_idx = seq.steps_held[0] if draw_lock == True else None
                    if draw_lock == True:
                        # TODO: Does not get past this draw call, if the pads are pressed
                        # Weird Shenaningans with the draw_lock value
                        # TODO: When pad is pressed we are not calling this func at all???
                        lock_value = seq.locks[step_idx][offset]
                        control.draw(ctx, offset, draw_lock=draw_lock, lock_value=lock_value)
                        offset += 1
                    else:
                        print("else loop")
                        # self.app.osc_mode.update_display(ctx)
                        control.draw(ctx, offset)
                        offset += 1
                        # print("else draw lock")
                except Exception as e:
                    print("Exception in trig_edit_mode.update_display()")
                    print(e)
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
            control = self.controls[encoder_idx]
            control.update_value(increment)
            self.prepare_lock()
        
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
        except ValueError:
            pass
