import definitions
import push2_python
import json
import os
import logging
from definitions import PyshaMode
from user_interface.display_utils import show_text
from glob import glob
from pathlib import Path
from modes.instrument import Instrument
from ratelimit import RateLimitException
import traceback
import numbers
import time


import sys
import struct
import xml.dom.minidom

from osc_controls import (
    OSCControl,
    ControlSpacer,
    OSCControlMacro,
    OSCGroup,
    OSCControlSwitch,
    OSCControlMenu,
    OSCMenuItem,
)

logger = logging.getLogger("osc_mode")


class OSCMode(PyshaMode):
    upper_row_button_names = [
        push2_python.constants.BUTTON_UPPER_ROW_1,
        push2_python.constants.BUTTON_UPPER_ROW_2,
        push2_python.constants.BUTTON_UPPER_ROW_3,
        push2_python.constants.BUTTON_UPPER_ROW_4,
        push2_python.constants.BUTTON_UPPER_ROW_5,
        push2_python.constants.BUTTON_UPPER_ROW_6,
        push2_python.constants.BUTTON_UPPER_ROW_7,
        push2_python.constants.BUTTON_UPPER_ROW_8,
    ]

    lower_row_button_names = [
        push2_python.constants.BUTTON_LOWER_ROW_1,
        push2_python.constants.BUTTON_LOWER_ROW_2,
        push2_python.constants.BUTTON_LOWER_ROW_3,
        push2_python.constants.BUTTON_LOWER_ROW_4,
        push2_python.constants.BUTTON_LOWER_ROW_5,
        push2_python.constants.BUTTON_LOWER_ROW_6,
        push2_python.constants.BUTTON_LOWER_ROW_7,
        push2_python.constants.BUTTON_LOWER_ROW_8,
    ]

    current_device_index_and_page = [0, 0]
    instrument_page = 0
    state = {}
    transports = []
    cli_needs_update = False
    osc_mode_filename = "osc_mode.json"
    def initialize(self, settings=None):
        device_names = [
            Path(device_file).stem
            for device_file in glob("./definitions/device_definitions/*.json")
        ]
        device_definitions = {}

        effect_names = [
            Path(effect_file).stem
            for effect_file in glob("./definitions/effect_definitions/*.json")
        ]

        modulation_names = [
            Path(modulation_file).stem
            for modulation_file in glob("./definitions/modulation_definitions/*.json")
        ]
        for device_name in device_names:
            try:
                device_definitions[device_name] = json.load(
                    open(
                        os.path.join(
                            definitions.DEVICE_DEFINITION_FOLDER,
                            "{}.json".format(device_name),
                        )
                    )
                )
            except FileNotFoundError:
                device_definitions[device_name] = {}

        for effect_name in effect_names:
            try:
                device_definitions[effect_name] = json.load(
                    open(
                        os.path.join(
                            definitions.EFFECT_DEFINITION_FOLDER,
                            "{}.json".format(effect_name),
                        )
                    )
                )
            except FileNotFoundError:
                device_definitions[effect_name] = {}

        for modulation_name in modulation_names:
            try:
                device_definitions[modulation_name] = json.load(
                    open(
                        os.path.join(
                            definitions.MODULATION_DEFINITIONS_FOLDER,
                            "{}.json".format(modulation_name),
                        )
                    )
                )
            except FileNotFoundError:
                device_definitions[modulation_name] = {}

        for (
            instrument_short_name
        ) in self.get_all_distinct_instrument_short_names_helper():
            print(
                os.path.join(
                    definitions.INSTRUMENT_DEFINITION_FOLDER,
                    "{}.json".format(instrument_short_name),
                )
            )
            instrument_definition = json.load(
                open(
                    os.path.join(
                        definitions.INSTRUMENT_DEFINITION_FOLDER,
                        "{}.json".format(instrument_short_name),
                    )
                )
            )

            self.app.instruments[instrument_short_name] = Instrument(
                instrument_short_name,
                instrument_definition,
                device_definitions,
                get_current_instrument_color_helper=self.get_current_instrument_color_helper,
                app=self.app,
            )

    def load_state(self):
        try:
            print("Loading Osc_mode state")
            if os.path.exists(self.osc_mode_filename):
                dump = json.load(open(self.osc_mode_filename))
                state = dump
                self.state = dump
                for (
                instrument_short_name
                ) in self.get_all_distinct_instrument_short_names_helper():
                    devices = self.get_instrument_devices(instrument_short_name)
                    
                    # Unpacking patch
                    path = self.app.preset_selection_mode.get_preset_path_for_instrument(instrument_short_name)
                    patch = path + ".fxp"
                    with open(patch, mode='rb') as patchFile:
                        patchContent = patchFile.read()

                    patchHeader = struct.unpack("<4siiiiiii", patchContent[60:92])
                    xmlsize = patchHeader[1]
                    # print("Patch Header Values: {0}".format(patchHeader))
                    xmlct = patchContent[92:(92 + xmlsize)].decode('utf-8')

                    dom = xml.dom.minidom.parseString(xmlct)
                    pretty_xml_as_string = dom.toprettyxml()
                    # print(pretty_xml_as_string)

                    # Getting the right device for slot
                    for device_index, device in enumerate(devices):
                        # Replaces the control values with state
                        values = []
                        # TODO: This breaks with our current state model
                        for control_index, control in enumerate(device.controls):
                            try:    
                                state_value = state[instrument_short_name][device_index][control_index]
                            except Exception as e:
                                print(e)

                            if isinstance(control, OSCControl) or isinstance(control, OSCControlMenu):
                                # Update state of the devices and send OSC message
                                if control.value != state_value and isinstance(state_value, numbers.Number):
                                    if hasattr(control, "address") and control.address != None:
                                        control.value = float(state[instrument_short_name][device_index][control_index])
                                        self.app.send_osc(control.address, float(control.value), instrument_short_name)
                            elif isinstance(control, OSCGroup):
                                # control.select()
                                pass
                            elif isinstance(control, OSCControlSwitch):
                                # Nested items need more care with saving their state
                                control.value = state_value[0]
                                active_group = control.get_active_group()
                                for idx, active_group_control in enumerate(active_group.controls):
                                    active_group_control.value = state_value[idx + 1]
                                    self.app.send_osc(active_group_control.address, int(state_value[idx + 1]), instrument_short_name)
                                active_group.select()
                                    
            else:
                # if file does not exist, create one
                self.save_state()
        except Exception as e:
            print("Exception in trig_edit load_state")
            traceback.print_exc()

    def save_state(self):
        try:
            state = {}
            for (
            instrument_short_name
            ) in self.get_all_distinct_instrument_short_names_helper():
                devices = self.get_instrument_devices(instrument_short_name)
                instrument_state = {instrument_short_name: []}
                # TODO: This breaks with Switches
                # Getting the right device for slot
                for index, device in enumerate(devices):
                    # Appending the control values to the state list
                    values = []
                    for control in device.controls:
                        if isinstance(control, OSCControl) or isinstance(control, OSCControlMenu):
                            values.append(control.value)
                        elif isinstance(control, OSCControlSwitch):
                            nested_values = []
                            nested_values.append(control.value)
                            active_group = control.get_active_group()
                            for nested_control in active_group.controls:
                                nested_values.append(nested_control.value)
                            # print(control.label, nested_values)
                            values.append(nested_values)
                            # print("Group save")
                        else:
                            values.append(None)
                    instrument_state[instrument_short_name].append(values)
                state.update(instrument_state)

            json.dump(state, open(self.osc_mode_filename, "w"))  # Save to file
            self.state = state
            # print("saved osc_mode state")
        except Exception as e:
            print("Exception in osc_mode save_state")
            traceback.print_exc()



    def close_transports(self):
        for instrument in self.app.instruments:
            self.app.instruments[instrument].close_transports()

    def get_all_distinct_instrument_short_names_helper(self):
        return (
            self.app.instrument_selection_mode.get_all_distinct_instrument_short_names()
        )

    def get_current_instrument_color_helper(self):
        return self.app.instrument_selection_mode.get_current_instrument_color()

    def get_current_instrument_short_name_helper(self):
        return self.app.instrument_selection_mode.get_current_instrument_short_name()

    def get_current_instrument_devices(self):
        instrument_shortname = self.get_current_instrument_short_name_helper()
        instrument = self.app.instruments.get(instrument_shortname, None)
        return instrument.current_devices

    def get_instrument_devices(self, instrument_short_name):
        instrument = self.app.instruments.get(instrument_short_name, None)
        return instrument.current_devices

    def get_current_instrument_page_devices(self):
        instrument_shortname = self.get_current_instrument_short_name_helper()
        instrument = self.app.instruments.get(instrument_shortname, None)
        if self.instrument_page == 0:
            return instrument.current_devices
        elif self.instrument_page == 1:
            return instrument.devices_modulation

    def query_devices(self):
        self.app.instruments[self.get_current_instrument_short_name_helper()].query_slots()
        # devices = self.get_current_instrument_devices()
        # for device in devices:
        #     device.query()

    def get_current_instrument(self):
        instrument = self.app.instruments[self.get_current_instrument_short_name_helper()]
        if instrument:
            return instrument

    def get_current_instrument_device(self):
        device, __ = self.get_current_instrument_device_and_page()
        return device

    def get_current_instrument_device_and_page(self):
        device_idx, page = self.current_device_index_and_page
        devices = self.get_current_instrument_page_devices()
        current_device = devices[device_idx]
        return (current_device, page)

    def get_current_slot_devices(self):
        instrument_shortname = (
            self.app.osc_mode.get_current_instrument_short_name_helper()
        )
        instrument = self.app.instruments.get(instrument_shortname, None)
        current_device = self.app.osc_mode.get_current_instrument_device()
        current_device_slot = current_device.slot

        devices_in_current_slot = []

        for slot_idx, slot_devices in enumerate(instrument.devices):
            for device in slot_devices:
                if device.slot == current_device_slot:
                    devices_in_current_slot.append(device)
        devices_in_current_slot_sorted = devices_in_current_slot.copy()
        devices_in_current_slot_sorted.sort(key=lambda x: x.label)

        return devices_in_current_slot_sorted

    def update_current_device_page(self, new_device=None, new_page=None):
        current_device_idx, current_page = self.current_device_index_and_page
        result = [current_device_idx, current_page]

        # resets page if device is swapepd
        if new_device != current_device_idx:
            result[1] = 0

        if new_device != None:
            result[0] = new_device

        if new_page != None:
            result[1] = new_page

        self.current_device_index_and_page = result
        new_current_device = self.get_current_instrument_device()
        # self.query_devices()
        new_current_device.set_page(new_page)
        self.app.buttons_need_update = True

    def update_current_instrument_page(self, new_device=None, new_instrument_page=None):
        # TODO: Make this page switching work with more instrument pages
        # if for some reason someone wants more than 16 devices
        
        # Only pages when you're not trying to pick a new device
        if self.app.is_mode_active(self.app.menu_mode) == False:
            self.instrument_page = new_instrument_page
            self.app.buttons_need_update = True
            self.query_all_instrument_page_params()

    def query_all_instrument_page_params(self):
        current_instrument_devices = self.get_current_instrument_page_devices()
        for device in current_instrument_devices:
            device.query_all_controls()

    def new_instrument_selected(self):
        pass
        # self.query_devices()
        # if new_instrument:
        #     for device in new_instrument.devices:
        #         print(device)
        #         device.query_visible_controls()

    def activate(self):
        # self.query_devices()
        self.update_buttons()

    def deactivate(self):
        for button_name in self.upper_row_button_names + [
            push2_python.constants.BUTTON_PAGE_LEFT,
            push2_python.constants.BUTTON_PAGE_RIGHT,
        ]:
            self.push.buttons.set_button_color(button_name, definitions.BLACK)

    def update_buttons(self):
        current_device = self.get_current_instrument_device()
        instrument_name = self.get_current_instrument_short_name_helper()
        pad_state = self.app.metro_sequencer_mode.metro_seq_pad_state[instrument_name]
        seq_pad_state = pad_state[self.app.metro_sequencer_mode.selected_track]
        seq = self.app.metro_sequencer_mode.instrument_sequencers[self.get_current_instrument_short_name_helper()]
        index = None
        try:
            index = self.app.steps_held[0]
        except:
            pass
        for count, name in enumerate(self.upper_row_button_names):
            if count < current_device.size:
                if index != None:
                    for value in seq.locks[index*8][count+self.instrument_page]:
                        if value != None:
                            self.push.buttons.set_button_color(name, definitions.WHITE)
                else:
                    self.push.buttons.set_button_color(name, self.get_current_instrument_color_helper())
            else:
                self.push.buttons.set_button_color(name, definitions.BLACK)

        show_prev, show_next = current_device.get_next_prev_pages()
        if show_prev:
            self.push.buttons.set_button_color(
                push2_python.constants.BUTTON_PAGE_LEFT, definitions.WHITE
            )
        else:
            self.push.buttons.set_button_color(
                push2_python.constants.BUTTON_PAGE_LEFT, definitions.BLACK
            )
        if show_next:
            self.push.buttons.set_button_color(
                push2_python.constants.BUTTON_PAGE_RIGHT, definitions.WHITE
            )
        else:
            self.push.buttons.set_button_color(
                push2_python.constants.BUTTON_PAGE_RIGHT, definitions.BLACK
            )

        if self.instrument_page == 1:
            self.push.buttons.set_button_color(
                push2_python.constants.BUTTON_LEFT, definitions.WHITE
            )
        else:
            self.push.buttons.set_button_color(
                push2_python.constants.BUTTON_LEFT, definitions.BLACK
            )
        if self.instrument_page == 0:
            self.push.buttons.set_button_color(
                push2_python.constants.BUTTON_RIGHT, definitions.WHITE
            )
        else:
            self.push.buttons.set_button_color(
                push2_python.constants.BUTTON_RIGHT, definitions.BLACK
            )

    def update_display(self, ctx, w, h):
        """
        If settings mode is active, don't draw the upper parts of the screen
        because settings page will "cover them"
        """
        if not self.app.is_mode_active(self.app.settings_mode):
            # Draw OSCDevice names
            devices = self.get_current_instrument_page_devices()
            if devices:
                height = 20
                for i, device in enumerate(devices):
                    show_text(ctx, i, 0, device.label, background_color=definitions.RED)

                    is_selected = False
                    selected_device, _ = self.get_current_instrument_device_and_page()
                    if selected_device == device:
                        is_selected = True

                    current_instrument_color = (
                        self.get_current_instrument_color_helper()
                    )
                    if is_selected:
                        background_color = current_instrument_color
                        font_color = definitions.BLACK
                    else:
                        background_color = definitions.BLACK
                        font_color = current_instrument_color
                    show_text(
                        ctx,
                        i,
                        0,
                        device.label,
                        height=height,
                        font_color=font_color,
                        background_color=background_color,
                    )

            # Draw OSCControls
            device = self.get_current_instrument_device()
            if device:
                device.draw(ctx)

    def on_button_pressed(self, button_name):
        selected_device, _ = self.get_current_instrument_device_and_page()
        show_prev, show_next = selected_device.get_next_prev_pages()
        _, current_page = self.get_current_instrument_device_and_page()

        if button_name in self.upper_row_button_names:
            if self.app.sequencer_mode.show_scale_menu != True:
                if self.app.metro_sequencer_mode.show_scale_menu != True:
                    current_instrument_devices = self.get_current_instrument_page_devices()
                    _, current_page = self.get_current_instrument_device_and_page()

                    idx = self.upper_row_button_names.index(button_name)
                    if idx < len(current_instrument_devices):
                        new_device = current_instrument_devices[idx]
                        # Stay on the same device page if new instrument, otherwise go to next page

                        new_page = (
                            0
                            if new_device != selected_device
                            else (
                                current_page - 1
                                if show_prev
                                else current_page + 1 if show_next else 0
                            )
                        )

                        self.update_current_device_page(idx, new_page=new_page)
                    return True
        elif button_name in self.lower_row_button_names:
            self.update_current_device_page(new_page=0)  # Reset page on new instrument
        elif button_name in [
            push2_python.constants.BUTTON_PAGE_LEFT,
            push2_python.constants.BUTTON_PAGE_RIGHT,
        ]:
            if button_name == push2_python.constants.BUTTON_PAGE_LEFT and show_prev:
                self.update_current_device_page(new_page=current_page - 1)
            elif button_name == push2_python.constants.BUTTON_PAGE_RIGHT and show_next:
                self.update_current_device_page(new_page=current_page + 1)
            return True

        elif button_name in [
            push2_python.constants.BUTTON_LEFT,
            push2_python.constants.BUTTON_RIGHT,
        ]:
            instrument_shortname = self.get_current_instrument_short_name_helper()
            instrument = self.app.instruments.get(instrument_shortname, None)
            instrument.update_current_devices()
            if button_name == push2_python.constants.BUTTON_LEFT:
                self.update_current_instrument_page(new_instrument_page=0)
            elif button_name == push2_python.constants.BUTTON_RIGHT:
                self.update_current_instrument_page(new_instrument_page=1)
            instrument.update_current_devices()
            return True

    def on_encoder_rotated(self, encoder_name, increment):
        try:
            if encoder_name == push2_python.constants.ENCODER_TEMPO_ENCODER:
                old_tempo = self.app.tempo
                self.app.tempo = old_tempo + increment
                self.app.global_timeline.tempo = self.app.tempo
                self.app.add_display_notification(f'Tempo: {self.app.tempo}')
            metro = self.app.metro_sequencer_mode
            # This call makes sure we always use the right enc_rot call
            # Because the seq has its own due to how param locks work
            if len(self.app.steps_held) == 0 and metro.show_scale_menu == False:
                current_device = self.get_current_instrument_device()
                current_device.on_encoder_rotated(encoder_name, increment)
            else:
                metro.on_encoder_rotated(encoder_name, increment)
        except RateLimitException:
            pass
        except Exception as err:
            print("Exception as err in OscMode")
            print(traceback.format_exc())

        return True  # Always return True because encoder should not be used in any other mode if this is first active

    def on_encoder_touched(self, encoder_name):
        try:
            current_device = self.get_current_instrument_device()
            if current_device.label == "Mod Matrix":
                # TODO: something is bugged when this func gets called, only with encoder 7 (one for deleting)
                current_device.on_encoder_touched(encoder_name)

            else:
                pass
                # current_device.on_encoder_rotated(encoder_name)
        except Exception as err:
            print("Exception in on_encoder_touched in osc_mode")
            traceback.print_exc()
            pass  # Encoder not in list
    def on_encoder_released(self, encoder_name):
        try:
            current_device = self.get_current_instrument_device()
            if current_device.label == "Audio In":
                # TODO: something is bugged when this func gets called, only with encoder 7 (one for deleting)
                current_device.on_encoder_released(encoder_name)

            else:
                pass
                # current_device.on_encoder_rotated(encoder_name)
        except Exception as err:
            print("Exception in on_encoder_touched in osc_mode")
            traceback.print_exc()
            pass  # Encoder not in list
