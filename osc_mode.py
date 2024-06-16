import definitions
import push2_python
import json
import os
import logging
from definitions import PyshaMode, OFF_BTN_COLOR
from display_utils import show_text
from glob import glob
from pathlib import Path
from osc_instrument import OSCInstrument
import asyncio

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

    instruments = {}
    current_device_index_and_page = [0, 0]
    instrument_page = 0
    transports = []

    def initialize(self, settings=None):
        device_names = [
            Path(device_file).stem
            for device_file in glob("./device_definitions/*.json")
        ]
        device_definitions = {}

        effect_names = [
            Path(effect_file).stem
            for effect_file in glob("./effect_definitions/*.json")
        ]

        modulation_names = [
            Path(effect_file).stem
            for effect_file in glob("./modulation_definitions/*.json")
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

            self.instruments[instrument_short_name] = OSCInstrument(
                instrument_short_name,
                instrument_definition,
                device_definitions,
                get_current_instrument_color_helper=self.get_current_instrument_color_helper,
                app=self.app,
            )

    def close_transports(self):
        for instrument in self.instruments:
            self.instruments[instrument].close_transports()

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
        instrument = self.instruments.get(instrument_shortname, None)

        devices = []

        for slot_idx, slot_devices in enumerate(instrument.devices):
            for device in slot_devices:
                if slot_idx == 2 or slot_idx == 3 or slot_idx == 4:
                    devices.append(device)
                elif 8 <= slot_idx <= 15:
                    devices.append(device)
                else:
                    slot = instrument.slots[slot_idx]
                    for init in device.init:
                        if init["address"] == slot["address"] and int(
                            init["value"]
                        ) == float(slot["value"]):
                            devices.append(device)

        return devices

    def get_current_instrument_page_devices(self):
        instrument_shortname = self.get_current_instrument_short_name_helper()
        instrument = self.instruments.get(instrument_shortname, None)

        devices = []
        devices_modulation = []

        for slot_idx, slot_devices in enumerate(instrument.devices):
            for device in slot_devices:
                if slot_idx == 2 or slot_idx == 3 or slot_idx == 4:
                    devices.append(device)
                elif 8 <= slot_idx <= 15:
                    devices_modulation.append(device)
                else:
                    slot = instrument.slots[slot_idx]
                    for init in device.init:
                        if init["address"] == slot["address"] and int(
                            init["value"]
                        ) == float(slot["value"]):
                            devices.append(device)

        if self.instrument_page == 0:
            return devices
        else:
            return devices_modulation

    def query_devices(self):
        self.instruments[self.get_current_instrument_short_name_helper()].query_slots()
        # devices = self.get_current_instrument_devices()
        # for device in devices:
        #     device.query()

    def get_current_instrument(self):
        instrument = self.instruments[self.get_current_instrument_short_name_helper()]
        if instrument:
            return instrument

    def get_current_instrument_device(self):
        device, __ = self.get_current_instrument_device_and_page()
        return device

    def get_current_instrument_device_and_page(self):
        device_idx, page = self.current_device_index_and_page
        current_device = self.get_current_instrument_page_devices()[device_idx]
        return (current_device, page)

    def get_current_slot_devices(self):
        instrument_shortname = (
            self.app.osc_mode.get_current_instrument_short_name_helper()
        )
        instrument = self.app.osc_mode.instruments.get(instrument_shortname, None)
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
        # TODO: Not sure how I feel about the query here

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
        for count, name in enumerate(self.upper_row_button_names):
            if count < current_device.size:
                self.push.buttons.set_button_color(name, definitions.WHITE)
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
            if button_name == push2_python.constants.BUTTON_LEFT:
                self.update_current_instrument_page(new_instrument_page=0)
            elif button_name == push2_python.constants.BUTTON_RIGHT:
                self.update_current_instrument_page(new_instrument_page=1)
            return True

    def on_encoder_rotated(self, encoder_name, increment):
        try:
            current_device = self.get_current_instrument_device()
            if current_device.label == "Mod Matrix":
                current_device.on_encoder_rotated(encoder_name, increment)
            else:
                current_device.on_encoder_rotated(encoder_name, increment)
        except Exception as err:
            print("Exception as err in OscMode ")
            print("encoder not in list")
            print(err)
            pass  # Encoder not in list

        return True  # Always return True because encoder should not be used in any other mode if this is first active
