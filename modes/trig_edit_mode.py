import definitions
import push2_python
from controllers import push2_constants
import os
import json
from osc_controls import (
    OSCControl,
    ControlSpacer,
    OSCControlSwitch,
    OSCGroup,
    OSCControlMenu,
)
from glob import glob
from user_interface.display_utils import show_text
from pathlib import Path
import traceback
import logging
from definitions import TRACK_NAMES

log = logging.getLogger("preset_selection_mode")

# log.setLevel(level=logging.DEBUG)


class TrigEditMode(definitions.PyshaMode):
    # Should we fold this under the sequencer/seq mode so it will init per instrument
    # Right now controls are shared between instruments
    current_page = 0
    controls = []
    state = {}
    current_address = None
    trig_edit_filename = "trig_edit.json"
    is_active = False
    slot = 16 # Might need to change this back to None

    def initialize(self, settings=None, **kwargs):
        self.is_active = False
        self.get_color = kwargs.get("get_color")
        # Sets up controls for the trig menu
        note = OSCControlMenu(
            {
                "$type": "control-menu",
                "items": [
                    {
                        "$type": "menu-item",
                        "label": "C",
                        "onselect": {
                            "$type": "message",
                            "$comment": "Sine",
                            "address": "/",
                            "value": 0,
                        },
                    },
                    {
                        "$type": "menu-item",
                        "label": "C#/Db",
                        "onselect": {
                            "$type": "message",
                            "$comment": "Sine",
                            "address": "/",
                            "value": 1,
                        },
                    },
                    {
                        "$type": "menu-item",
                        "label": "D",
                        "onselect": {
                            "$type": "message",
                            "$comment": "Sine",
                            "address": "/",
                            "value": 2,
                        },
                    },
                    {
                        "$type": "menu-item",
                        "label": "D#/Eb",
                        "onselect": {
                            "$type": "message",
                            "$comment": "Sine",
                            "address": "/",
                            "value": 3,
                        },
                    },
                    {
                        "$type": "menu-item",
                        "label": "E",
                        "onselect": {
                            "$type": "message",
                            "$comment": "Sine",
                            "address": "/",
                            "value": 4,
                        },
                    },
                    {
                        "$type": "menu-item",
                        "label": "F/E#",
                        "onselect": {
                            "$type": "message",
                            "$comment": "Sine",
                            "address": "/",
                            "value": 5,
                        },
                    },
                    {
                        "$type": "menu-item",
                        "label": "F#/Gb",
                        "onselect": {
                            "$type": "message",
                            "$comment": "Sine",
                            "address": "/",
                            "value": 6,
                        },
                    },
                    {
                        "$type": "menu-item",
                        "label": "F#/Gb",
                        "onselect": {
                            "$type": "message",
                            "$comment": "Sine",
                            "address": "/",
                            "value": 6,
                        },
                    },
                    {
                        "$type": "menu-item",
                        "label": "G",
                        "onselect": {
                            "$type": "message",
                            "$comment": "Sine",
                            "address": "/",
                            "value": 7,
                        },
                    },
                    {
                        "$type": "menu-item",
                        "label": "G#/Ab",
                        "onselect": {
                            "$type": "message",
                            "$comment": "Sine",
                            "address": "/",
                            "value": 8,
                        },
                    },
                    {
                        "$type": "menu-item",
                        "label": "A",
                        "onselect": {
                            "$type": "message",
                            "$comment": "Sine",
                            "address": "/",
                            "value": 9,
                        },
                    },
                    {
                        "$type": "menu-item",
                        "label": "A#/Bb",
                        "onselect": {
                            "$type": "message",
                            "$comment": "Sine",
                            "address": "/",
                            "value": 10,
                        },
                    },
                    {
                        "$type": "menu-item",
                        "label": "B",
                        "onselect": {
                            "$type": "message",
                            "$comment": "Sine",
                            "address": "/",
                            "value": 11,
                        },
                    },
                ],
            },
            self.get_current_instrument_color_helper,
            self.send_message,
        )
        self.controls.append(note)

        octave = OSCControlMenu(
            {
                "$type": "control-menu",
                "items": [
                    {
                        "$type": "menu-item",
                        "label": "Oct -2",
                        "onselect": {
                            "$type": "message",
                            "$comment": "Sine",
                            "address": "/",
                            "value": 0,
                        },
                    },
                    {
                        "$type": "menu-item",
                        "label": "Oct -1",
                        "onselect": {
                            "$type": "message",
                            "$comment": "Sine",
                            "address": "/",
                            "value": 1,
                        },
                    },
                    {
                        "$type": "menu-item",
                        "label": "Oct 0",
                        "onselect": {
                            "$type": "message",
                            "$comment": "Sine",
                            "address": "/",
                            "value": 2,
                        },
                    },
                    {
                        "$type": "menu-item",
                        "label": "Oct 1",
                        "onselect": {
                            "$type": "message",
                            "$comment": "Sine",
                            "address": "/",
                            "value": 3,
                        },
                    },
                    {
                        "$type": "menu-item",
                        "label": "Oct 2",
                        "onselect": {
                            "$type": "message",
                            "$comment": "Sine",
                            "address": "/",
                            "value": 4,
                        },
                    },
                    {
                        "$type": "menu-item",
                        "label": "Oct 3",
                        "onselect": {
                            "$type": "message",
                            "$comment": "Sine",
                            "address": "/",
                            "value": 5,
                        },
                    },
                    {
                        "$type": "menu-item",
                        "label": "Oct 4",
                        "onselect": {
                            "$type": "message",
                            "$comment": "Sine",
                            "address": "/",
                            "value": 6,
                        },
                    },
                    {
                        "$type": "menu-item",
                        "label": "Oct 5",
                        "onselect": {
                            "$type": "message",
                            "$comment": "Sine",
                            "address": "/",
                            "value": 6,
                        },
                    },
                    {
                        "$type": "menu-item",
                        "label": "Oct 6",
                        "onselect": {
                            "$type": "message",
                            "$comment": "Sine",
                            "address": "/",
                            "value": 7,
                        },
                    },
                    {
                        "$type": "menu-item",
                        "label": "Oct 7",
                        "onselect": {
                            "$type": "message",
                            "$comment": "Sine",
                            "address": "/",
                            "value": 8,
                        },
                    },
                    {
                        "$type": "menu-item",
                        "label": "Oct 8",
                        "onselect": {
                            "$type": "message",
                            "$comment": "Sine",
                            "address": "/",
                            "value": 9,
                        },
                    },
                ],
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
                "max": 127,
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
                "min": 0.1,
                "max": 0.9,
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

        not_cond = OSCControl(
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
                "max": 8,
            },
            self.get_current_instrument_color_helper,
            self.send_message,
        )
        recur.value = 8
        self.controls.append(recur)

        for instrument in self.get_all_distinct_instrument_short_names_helper():
            self.state[instrument] = {}
            for track in TRACK_NAMES:
                self.state[instrument][track] = []
                for control in self.controls:
                    self.state[instrument][track].append(control.value)
                self.state[instrument][track].append(255)

    def load_state(self):
        try:
            if os.path.exists(self.trig_edit_filename):
                dump = json.load(open(self.trig_edit_filename))
                self.state = dump
        except Exception as e:
            print("Exception in trig_edit load_state")
            traceback.print_exc()

    def save_state(self):
        try:
            json.dump(self.state, open(self.trig_edit_filename, "w"))  # Save to file
        except Exception as e:
            print("Exception in trig_edit save_state")
            traceback.print_exc()

    def send_message(self, *args):
        # self.log_out.debug(args)
        # return self.osc["client"].send_message(*args)
        pass

    def activate(self):
        self.is_active = True
        self.update_button_colours()
        self.current_page = 0
        self.update_buttons()
        self.update_pads()

    def new_instrument_selected(self):
        self.current_page = 0
        self.app.pads_need_update = True
        self.app.buttons_need_update = True
        self.update_state()

    def update_state(self):
        current_state = self.state[self.get_current_instrument_short_name_helper()]
        track_name = self.app.sequencer_mode.selected_track
        for idx, control in enumerate(self.controls):
            control.value = current_state[track_name][idx]

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

    def deactivate(self):
        self.is_active = False
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
        seq = None
        if self.app.is_mode_active(self.app.sequencer_mode) == True:
            seq = self.app.sequencer_mode.instrument_sequencers[
                self.get_current_instrument_short_name_helper()
            ]
        elif self.app.is_mode_active(self.app.metro_sequencer_mode) == True:
            seq = self.app.metro_sequencer_mode.instrument_sequencers[
                self.get_current_instrument_short_name_helper()
            ]
        for control in visible_controls:
            draw_lock = True if len(seq.steps_held) != 0 else False
            if offset + 1 <= 8:
                try:
                    step_idx = seq.steps_held[0] if draw_lock == True else None
                    lock_value = (
                        seq.get_lock_state(step_idx, offset)
                        if step_idx != None
                        else None
                    )
                    # print("Draw lock:", draw_lock, " Lock Value:", lock_value)
                    if draw_lock == True and lock_value != None:
                        control.draw(
                            ctx, offset, draw_lock=draw_lock, lock_value=lock_value
                        )
                        offset += 1
                    else:
                        control.draw(ctx, offset)
                        offset += 1
                except Exception as e:
                    print("Exception in trig_edit_mode.update_display()")
                    traceback.print_exc()
                    pass

    def on_button_pressed(self, button_name):
        if (
            button_name == push2_constants.BUTTON_UPPER_ROW_1
            or push2_constants.BUTTON_UPPER_ROW_2
            or push2_constants.BUTTON_UPPER_ROW_3
            or push2_constants.BUTTON_UPPER_ROW_4
            or push2_constants.BUTTON_UPPER_ROW_5
            or push2_constants.BUTTON_UPPER_ROW_6
            or push2_constants.BUTTON_UPPER_ROW_7
            or push2_constants.BUTTON_UPPER_ROW_8
        ):
            try:
                instrument = self.get_current_instrument_short_name_helper()
                seq = self.app.sequencer_mode.instrument_sequencers[instrument]
                idx = seq.steps_held[0] if len(seq.steps_held) != 0 else 0
                selected_track = self.app.sequencer_mode.selected_track
                lock = seq.get_lock_state(idx, 8)
                current_state = self.state[instrument][selected_track][8]
                value = int(current_state) if lock == None else int(lock)
                binary_list = [int(i) for i in bin(value)[2:]]
                if len(binary_list) != 8:
                    list = binary_list.copy()
                    while len(list) <= 8:
                        list.append(0)
                
                
                binary_list = list
                try:
                    button_idx = int(button_name[-1]) - 1
                except:
                    return
                # Updates the binary number
                print(binary_list, button_idx)
                if binary_list[button_idx] == True:
                    binary_list[button_idx] = 0
                else:
                    binary_list[button_idx] = 1
                # Converts binary to int
                new_int = int("".join(map(str, binary_list)), 2)
                if len(seq.steps_held) > 0:
                    # set lock
                    seq.set_lock_state(idx, 8, new_int)
                else:
                    # set state
                    self.state[instrument][selected_track][8] = new_int
                self.update_button_colours()
            except Exception as e:
                print("Exception in on_button_presed in trig_edit_mode")
                traceback.print_exc()
                pass

    def update_button_colours(self):
        if self.is_active == True:
            instrument = self.get_current_instrument_short_name_helper()
            instrument_scale_edit_controls = (
                self.app.sequencer_mode.instrument_scale_edit_controls[instrument]
            )
            selected_track = self.app.sequencer_mode.selected_track
            seq = self.app.sequencer_mode.instrument_sequencers[instrument]
            sel_track_len = instrument_scale_edit_controls[selected_track][0].value

            idx = seq.steps_held[0] if len(seq.steps_held) != 0 else 0
            lock = seq.get_lock_state(idx, 8)
            current_state = self.state[instrument][selected_track][8]
            value = int(current_state) if lock == None else int(lock)
            binary_list = [int(i) for i in bin(value)[2:]]
            recur_len = int(self.state[instrument][selected_track][7]) + 1

            loop_count = int(seq.playhead / int(sel_track_len)) % recur_len
            for idx, item in enumerate(binary_list):
                button_name = f"Upper Row {idx + 1}"
                if idx < recur_len:
                    if idx == loop_count:
                        button_color = definitions.GREEN
                    else:
                        button_color = (
                            definitions.WHITE if item == True else definitions.OFF_BTN_COLOR
                        )
                else:
                    button_color = definitions.BLACK
                self.app.push.buttons.set_button_color(button_name, button_color)

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
            seq = self.app.sequencer_mode.instrument_sequencers[
                self.get_current_instrument_short_name_helper()
            ]
            if len(seq.steps_held) != 0:
                if self.app.sequencer_mode.disable_controls == False and self.app.metro_sequencer_mode.disable_controls == False:
                    pass
            else:
                control = self.controls[encoder_idx]

                try:
                    min = control.min if hasattr(control, "min") else 0
                    max = control.max if hasattr(control, "max") else len(control.items)
                    range = max - min
                    incr = increment * range / 100
                    if min < control.value + incr < max:
                        control.value = control.value + incr
                    if min >= (control.value + incr):
                        control.value = min
                    if max < (control.value + incr):
                        control.value = max - incr

                    # control.update_value(increment)
                    track_name = self.app.sequencer_mode.selected_track
                    self.state[self.get_current_instrument_short_name_helper()][track_name][
                        encoder_idx
                    ] = control.value
                    if encoder_idx == 7:
                        self.update_button_colours()
                except Exception as e:
                    print("Error in on_encoder_rotated in TrigEditMode")
                    traceback.print_exc()
        except ValueError:
            pass  # Encoder not in list

    def send_osc(self, *args, instrument_shortname=None):
        instrument = self.app.instruments.get(
            instrument_shortname
            or self.app.osc_mode.get_current_instrument_short_name_helper(),
            None,
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
