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

    # def send_lower_row(self):
    #     if self.lower_row_selected in tone_selector_values:
    #         for _, midi_cc, midi_val in tone_selector_values[self.lower_row_selected]:
    #             values_to_send = [midi_val]
    #             for val in values_to_send:
    #                 msg = mido.Message('control_change', control=midi_cc, value=val)  # Should we subtract 1 from midi_cc because mido being 0-indexed?
    #                 self.app.send_midi(msg)
    #                 if self.inter_message_message_min_time_ms:
    #                     time.sleep(self.inter_message_message_min_time_ms*1.0/1000)

    # def send_upper_row(self):
    #     if self.upper_row_selected in tone_selector_values:
    #         for midi_cc, _, midi_val in tone_selector_values[self.upper_row_selected]:
    #             values_to_send = [midi_val]
    #             for val in values_to_send:
    #                 msg = mido.Message('control_change', control=midi_cc, value=val)  # Should we subtract 1 from midi_cc because mido being 0-indexed?
    #                 self.app.send_midi(msg)
    #                 if self.inter_message_message_min_time_ms:
    #                     time.sleep(self.inter_message_message_min_time_ms*1.0/1000)

    def activate(self):
        self.update_buttons()

    def deactivate(self):
        for button_name in (
            self.upper_row_button_names
            + self.lower_row_button_names
            + [
                push2_python.constants.BUTTON_PAGE_LEFT,
                push2_python.constants.BUTTON_PAGE_RIGHT,
            ]
        ):
            self.push.buttons.set_button_color(button_name, definitions.BLACK)

    def update_buttons(self):

        for count, name in enumerate(self.upper_row_button_names):
            try:
                tone_name = self.upper_row_names[count + self.page_n * 8]
                self.push.buttons.set_button_color(name, self.colors[tone_name])
            except IndexError:
                self.push.buttons.set_button_color(name, definitions.OFF_BTN_COLOR)

        for count, name in enumerate(self.lower_row_button_names):
            try:
                tone_name = self.lower_row_names[count + self.page_n * 8]
                self.push.buttons.set_button_color(name, self.colors[tone_name])
            except IndexError:
                self.push.buttons.set_button_color(name, definitions.OFF_BTN_COLOR)

        show_prev, show_next = self.get_should_show_next_prev()
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

    def update_display(self, ctx, w, h):
        # instrumet_shortname = (
        #     self.app.osc_mode.get_current_instrument_short_name_helper()
        # )
        # instrument = self.app.osc_mode.instruments.get(instrumet_shortname, None)
        # current_device = self.app.osc_mode.get_current_instrument_device()
        # current_device_slot = current_device.slot

        # devices_in_current_slot = []

        # for slot_idx, slot_devices in enumerate(instrument.devices):
        #     for device in slot_devices:
        #         if device.slot == current_device_slot:
        #             devices_in_current_slot.append(device)
        #             # print(device.label)
        devices_in_current_slot = self.app.osc_mode.get_current_slot_devices()
        for device in devices_in_current_slot:
            print(device.label)
        show_text(
            ctx,
            7,
            20,
            "menu mode",
            height=50,
            font_color=definitions.BLACK,
            background_color=definitions.GRAY_LIGHT,
            font_size_percentage=0.2,
            center_vertically=True,
            center_horizontally=True,
            rectangle_padding=1,
        )

    # if not self.app.is_mode_active(self.app.settings_mode):
    #     # If settings mode is active, don't draw the upper parts of the screen because settings page will
    #     # "cover them"

    #     start = self.page_n * 8

    #     # Draw upper row
    #     for i, name in enumerate(self.upper_row_names[start:][:8]):
    #         font_color = self.font_colors[self.colors[name]]
    #         if name == self.upper_row_selected:
    #             background_color = self.colors[name]
    #         else:
    #             background_color = self.colors[name] + "_darker1"
    #         height = 80
    #         top_offset = 0
    #         show_text(
    #             ctx,
    #             i,
    #             top_offset,
    #             name.upper(),
    #             height=height,
    #             font_color=font_color,
    #             background_color=background_color,
    #             font_size_percentage=0.2,
    #             center_vertically=True,
    #             center_horizontally=True,
    #             rectangle_padding=1,
    #         )

    #     # Draw lower row
    #     for i, name in enumerate(self.lower_row_names[start:][:8]):
    #         if name != NAME_FUNKY_4:
    #             font_color = self.font_colors[self.colors[name]]
    #             if name == self.lower_row_selected:
    #                 background_color = self.colors[name]
    #             else:
    #                 background_color = self.colors[name] + "_darker1"
    #             height = 80
    #             top_offset = 80
    #             show_text(
    #                 ctx,
    #                 i,
    #                 top_offset,
    #                 name.upper(),
    #                 height=height,
    #                 font_color=font_color,
    #                 background_color=background_color,
    #                 font_size_percentage=0.2,
    #                 center_vertically=True,
    #                 center_horizontally=True,
    #                 rectangle_padding=1,
    #             )

    def on_button_pressed(self, button_name):
        if button_name in self.upper_row_button_names:
            start = self.page_n * 8
            button_idx = self.upper_row_button_names.index(button_name)
            try:
                self.upper_row_selected = self.upper_row_names[button_idx + start]
                self.send_upper_row()
            except IndexError:
                # Do nothing because the button has no assigned tone
                pass
            return True

        elif button_name in self.lower_row_button_names:
            start = self.page_n * 8
            button_idx = self.lower_row_button_names.index(button_name)
            try:
                self.lower_row_selected = self.lower_row_names[button_idx + start]
                self.send_lower_row()
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
