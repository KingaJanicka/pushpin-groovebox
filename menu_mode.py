import definitions
import mido
import push2_python
import time
import math
import json
import os
import push2_constants

from definitions import PyshaMode
from display_utils import show_text


class MenuMode(PyshaMode):

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

    page_n = 0
    selected_menu_item_index = 0
    upper_row_selected = ""
    lower_row_selected = ""
    inter_message_message_min_time_ms = 4  # ms wait time after each message to DDRM

    def __init__(self, app, settings=None, send_osc_func=None):
        super().__init__(app, settings=settings)
        self.send_osc_func = send_osc_func

    def should_be_enabled(self):
        return True

    def get_should_show_next_prev(self):
        show_prev = self.page_n == 1
        show_next = self.page_n == 0
        return show_prev, show_next

    def activate(self):
        device = self.app.osc_mode.get_current_instrument_device()
        devices_in_current_slot = self.app.osc_mode.get_current_slot_devices()
        for idx, item in enumerate(devices_in_current_slot):
            if item == device:
                self.selected_menu_item_index = idx

        self.update_buttons()

    def deactivate(self):
        instrument = self.app.osc_mode.get_current_instrument()
        # print("called q slots")
        # TODO: I have no clue why the fricity frick this sleep needs to be here
        # TODO: But it does and the FX switching will lag behind one selection if not
        time.sleep(0.1)
        instrument.query_slots()
        for button_name in (
            self.upper_row_button_names
            + self.lower_row_button_names
            + [
                push2_python.constants.BUTTON_PAGE_LEFT,
                push2_python.constants.BUTTON_PAGE_RIGHT,
            ]
        ):
            self.push.buttons.set_button_color(button_name, definitions.BLACK)

    def update_display(self, ctx, w, h):
        devices_in_current_slot = self.app.osc_mode.get_current_slot_devices()
        for idx, device in enumerate(devices_in_current_slot):
            if idx == self.selected_menu_item_index:
                background_color = definitions.YELLOW
            else:
                background_color = definitions.GRAY_LIGHT
            if idx < 8:
                show_text(
                    ctx,
                    idx,
                    20,
                    device.label,
                    height=25,
                    font_color=definitions.BLACK,
                    background_color=background_color,
                    font_size_percentage=0.8,
                    center_vertically=True,
                    center_horizontally=True,
                    rectangle_padding=1,
                )
            elif idx < 16:
                show_text(
                    ctx,
                    idx - 8,
                    45,
                    device.label,
                    height=25,
                    font_color=definitions.BLACK,
                    background_color=background_color,
                    font_size_percentage=0.8,
                    center_vertically=True,
                    center_horizontally=True,
                    rectangle_padding=1,
                )
            elif idx < 24:
                show_text(
                    ctx,
                    idx - 16,
                    70,
                    device.label,
                    height=25,
                    font_color=definitions.BLACK,
                    background_color=background_color,
                    font_size_percentage=0.8,
                    center_vertically=True,
                    center_horizontally=True,
                    rectangle_padding=1,
                )
            elif idx < 32:
                show_text(
                    ctx,
                    idx - 24,
                    95,
                    device.label,
                    height=25,
                    font_color=definitions.BLACK,
                    background_color=background_color,
                    font_size_percentage=0.8,
                    center_vertically=True,
                    center_horizontally=True,
                    rectangle_padding=1,
                )
            elif idx < 40:
                show_text(
                    ctx,
                    idx - 24,
                    110,
                    device.label,
                    height=25,
                    font_color=definitions.BLACK,
                    background_color=background_color,
                    font_size_percentage=0.8,
                    center_vertically=True,
                    center_horizontally=True,
                    rectangle_padding=1,
                )

    def update_buttons(self):
        pass

    def on_button_pressed(self, button_name):
        devices_in_current_slot = self.app.osc_mode.get_current_slot_devices()
        instrument_shortname = (
            self.app.osc_mode.get_current_instrument_short_name_helper()
        )

        if button_name is push2_constants.BUTTON_LEFT:
            if self.selected_menu_item_index - 1 >= 0:
                self.selected_menu_item_index -= 1
        elif button_name is push2_constants.BUTTON_RIGHT:
            number_of_devices_in_current_slot = len(devices_in_current_slot)
            if (
                0
                <= self.selected_menu_item_index + 1
                < number_of_devices_in_current_slot
            ):
                self.selected_menu_item_index += 1
        elif button_name is push2_constants.BUTTON_UP:
            number_of_devices_in_current_slot = len(devices_in_current_slot)
            if (
                0
                <= self.selected_menu_item_index - 8
                < number_of_devices_in_current_slot
            ):
                self.selected_menu_item_index -= 8
        elif button_name is push2_constants.BUTTON_DOWN:
            number_of_devices_in_current_slot = len(devices_in_current_slot)
            if (
                0
                <= self.selected_menu_item_index + 8
                < number_of_devices_in_current_slot
            ):
                self.selected_menu_item_index += 8

        elif button_name == push2_constants.BUTTON_ADD_DEVICE:
            selected_device = devices_in_current_slot[self.selected_menu_item_index]
            try:
                for message in selected_device.init:
                    self.app.send_osc(
                        message["address"],
                        float(message["value"]),
                        instrument_shortname,
                    )
                    print("sending stuffs")
                    # TODO: might need removing
                # TODO: need to figure out why FX take two button clicks to swap while osc take one
                devices = self.app.osc_mode.get_current_instrument_devices()
                for device in devices:
                    if device.label == selected_device.label:
                        device.query_visible_controls()
                self.app.toggle_menu_mode()
                self.app.buttons_need_update = True
            except IndexError:
                # Do nothing because the button has no assigned tone
                pass
            return True

        elif button_name in [
            push2_python.constants.BUTTON_PAGE_LEFT,
            push2_python.constants.BUTTON_PAGE_RIGHT,
        ]:
            show_prev, show_next = self.get_should_show_next_prev()
            if button_name == push2_python.constants.BUTTON_PAGE_LEFT and show_prev:
                self.page_n = 0
            elif button_name == push2_python.constants.BUTTON_PAGE_RIGHT and show_next:
                self.page_n = 1
            self.app.buttons_need_update = True
            return True
