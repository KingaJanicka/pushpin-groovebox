import definitions
import mido
import push2_python
import time
import os
import json
from glob import glob
from display_utils import show_notification
from display_utils import show_text
from pathlib import Path
import re


class PresetSelectionMode(definitions.PyshaMode):

    xor_group = "pads"

    presets = {}
    presets_filename = "presets.json"
    pad_pressing_states = {}
    pad_quick_press_time = 0.400
    current_page = 0
    patches = {}
    current_selection = {}
    encoder_0 = 0
    encoder_1 = 0
    encoder_2 = 0
    encoder_3 = 0
    encoder_4 = 0
    encoder_5 = 0
    encoder_6 = 0
    encoder_7 = 0
    patches_dicts = []

    def initialize(self, settings=None):
        for (
            instrument_short_name
        ) in self.get_all_distinct_instrument_short_names_helper():
            self.current_selection[instrument_short_name] = []
            self.presets[instrument_short_name] = [None] * 8
        # self.load_config()

        self.patches["Factory"] = self.create_dict_from_paths(
            glob(
                f"**/*.fxp",
                recursive=True,
                root_dir=definitions.FACTORY_PATCHES_FOLDER,
            )
        )

        self.patches["Third Party"] = self.create_dict_from_paths(
            glob(
                f"**/*.fxp",
                recursive=True,
                root_dir=definitions.THIRD_PARTY_PATCHES_FOLDER,
            )
        )

        self.patches["User"] = self.create_dict_from_paths(
            glob(
                f"**/*.fxp",
                recursive=True,
                root_dir=definitions.USER_PATCHES_FOLDER,
            )
        )

    def create_dict_from_paths(self, arr):
        d = dict()
        for path in arr:
            parent = d
            for dir in path.split("/"):
                filename_arr = dir.split(".")
                filename = filename_arr[0]
                if dir not in parent:
                    if dir.endswith(".fxp"):

                        parent[filename] = path
                    else:

                        parent[filename] = dict()
                parent = parent[filename]
        return d

    def load_config(self):
        if os.path.exists(self.presets_filename):
            self.presets = json.load(open(self.presets_filename))

    def save_config(self, presets=None):
        json.dump(presets or self.presets, self.presets_filename)

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

    def add_preset(self, preset_number, bank_number):
        instrument_short_name = (
            self.app.instrument_selection_mode.get_current_instrument_short_name()
        )
        if instrument_short_name not in self.presets:
            self.presets[instrument_short_name] = []
        self.presets[instrument_short_name].append((preset_number, bank_number))
        json.dump(self.presets, open(self.presets_filename, "w"))  # Save to file

    def get_all_distinct_instrument_short_names_helper(self):
        return (
            self.app.instrument_selection_mode.get_all_distinct_instrument_short_names()
        )

    def get_current_instrument_short_name_helper(self):
        return self.app.instrument_selection_mode.get_current_instrument_short_name()

    def remove_preset(self, preset_number, bank_number):
        instrument_short_name = (
            self.app.instrument_selection_mode.get_current_instrument_short_name()
        )
        if instrument_short_name in self.presets:
            self.presets[instrument_short_name] = [
                (fp_preset_number, fp_bank_number)
                for fp_preset_number, fp_bank_number in self.presets[
                    instrument_short_name
                ]
                if preset_number != fp_preset_number or bank_number != fp_bank_number
            ]
            json.dump(self.presets, open(self.presets_filename, "w"))  # Save to file

    def preset_num_in_favourites(self, preset_number, bank_number):
        instrument_short_name = (
            self.app.instrument_selection_mode.get_current_instrument_short_name()
        )
        if instrument_short_name not in self.presets:
            return False
        for fp_preset_number, fp_bank_number in self.presets[instrument_short_name]:
            if preset_number == fp_preset_number and bank_number == fp_bank_number:
                return True
        return False

    def get_current_page(self):
        # Returns the current page of presets being displayed in the pad grid
        # page 0 = bank 0, presets 0-63
        # page 1 = bank 0, presets 64-127
        # page 2 = bank 1, presets 0-63
        # page 3 = bank 1, presets 64-127
        # ...
        # The number of total available pages depends on the synth.
        return self.current_page

    def get_num_banks(self):
        # Returns the number of available banks of the selected instrument
        return self.app.instrument_selection_mode.get_current_instrument_info()[
            "n_banks"
        ]

    def get_bank_names(self):
        # Returns list of bank names
        return self.app.instrument_selection_mode.get_current_instrument_info()[
            "bank_names"
        ]

    def get_num_pages(self):
        # Returns the number of available preset pages per instrument (2 per bank)
        return self.get_num_banks() * 2

    def next_page(self):
        if self.current_page < self.get_num_pages() - 1:
            self.current_page += 1
        else:
            self.current_page = self.get_num_pages() - 1
        self.app.pads_need_update = True
        self.app.buttons_need_update = True
        self.notify_status_in_display()

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
        else:
            self.current_page = 0
        self.app.pads_need_update = True
        self.app.buttons_need_update = True
        self.notify_status_in_display()

    def has_prev_next_pages(self):
        has_next = False
        has_prev = False
        if self.get_current_page() < self.get_num_pages() - 1:
            has_next = True
        if self.get_current_page() > 0:
            has_prev = True
        return (has_prev, has_next)

    def pad_ij_to_bank_and_preset_num(self, pad_ij):
        preset_num = (self.get_current_page() % 2) * 64 + pad_ij[0] * 8 + pad_ij[1]
        bank_num = self.get_current_page() // 2
        return (preset_num, bank_num)

    def send_select_new_preset(self, preset_num):
        msg = mido.Message(
            "program_change", program=preset_num
        )  # Should this be 1-indexed?
        self.app.send_midi(msg)

    def send_select_new_bank(self, bank_num):
        # If synth only has 1 bank, don't send bank change messages
        if self.get_num_banks() > 1:
            msg = mido.Message(
                "control_change", control=0, value=bank_num
            )  # Should this be 1-indexed?
            self.app.send_midi(msg)

    def notify_status_in_display(self):
        bank_number = self.get_current_page() // 2 + 1
        bank_names = self.get_bank_names()
        if bank_names is not None:
            bank_name = bank_names[bank_number - 1]
        else:
            bank_name = bank_number
        self.app.add_display_notification(
            "Preset FARTS: bank {0}, presets {1}".format(
                bank_name, "1-64" if self.get_current_page() % 2 == 0 else "65-128"
            )
        )

    def activate(self):
        self.update_pads()
        self.notify_status_in_display()

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
        show_prev, show_next = self.has_prev_next_pages()
        if show_prev:
            self.push.buttons.set_button_color(
                push2_python.constants.BUTTON_LEFT, definitions.WHITE
            )
        else:
            self.push.buttons.set_button_color(
                push2_python.constants.BUTTON_LEFT, definitions.BLACK
            )
        if show_next:
            self.push.buttons.set_button_color(
                push2_python.constants.BUTTON_RIGHT, definitions.WHITE
            )
        else:
            self.push.buttons.set_button_color(
                push2_python.constants.BUTTON_RIGHT, definitions.BLACK
            )

    def update_pads(self):
        instrument_short_name = (
            self.app.instrument_selection_mode.get_current_instrument_short_name()
        )
        instrument_color = (
            self.app.instrument_selection_mode.get_current_instrument_color()
        )
        color_matrix = []
        for i in range(0, 8):
            row_colors = []
            for j in range(0, 8):
                cell_color = instrument_color
                preset_num, bank_num = self.pad_ij_to_bank_and_preset_num((i, j))
                if not self.presets[instrument_short_name][preset_num]:
                    cell_color = f"{cell_color}_darker2"  # If preset not in favourites, use a darker version of the instrument color
                row_colors.append(cell_color)
            color_matrix.append(row_colors)
        self.push.pads.set_pads_color(color_matrix)

    def on_pad_pressed(self, pad_n, pad_ij, velocity):
        self.pad_pressing_states[pad_n] = (
            time.time()
        )  # Store time at which pad_n was pressed
        self.push.pads.set_pad_color(pad_ij, color=definitions.GREEN)
        return True  # Prevent other modes to get this event

    def on_pad_released(self, pad_n, pad_ij, velocity):
        pressing_time = self.pad_pressing_states.get(pad_n, None)
        is_long_press = False
        if pressing_time is None:
            # Consider quick press (this should not happen as self.pad_pressing_states[pad_n] should have been set before)
            pass
        else:
            if time.time() - pressing_time > self.pad_quick_press_time:
                # Consider this is a long press
                is_long_press = True
            self.pad_pressing_states[pad_n] = None  # Reset pressing time to none

        preset_num, bank_num = self.pad_ij_to_bank_and_preset_num(pad_ij)

        if is_long_press:
            # Add/remove preset to favourites, don't send any MIDI
            if not self.preset_num_in_favourites(preset_num, bank_num):
                self.add_preset(preset_num, bank_num)
            else:
                self.remove_preset(preset_num, bank_num)
        else:
            # Send midi message to select the bank and preset preset
            self.send_select_new_bank(bank_num)
            self.send_select_new_preset(preset_num)
            bank_names = self.get_bank_names()
            if bank_names is not None:
                bank_name = bank_names[bank_num]
            else:
                bank_name = bank_num + 1
            self.app.add_display_notification(
                "Selected bank {0}, preset {1}".format(
                    bank_name,  # Show 1-indexed value
                    preset_num + 1,  # Show 1-indexed value
                )
            )

        self.app.pads_need_update = True
        return True  # Prevent other modes to get this event

    def update_display(self, ctx, w, h):
        current = self.current_selection[
            self.get_current_instrument_short_name_helper()
        ]
        if len(current) == 0:
            options = self.patches.keys()

        for idx, folder_name in enumerate(options):
            background = None
            if idx == int(self.encoder_0):
                background = definitions.LIME
            show_text(
                ctx,
                0,
                20 * idx + 5,
                folder_name,
                height=20,
                font_color=definitions.WHITE,
                background_color=background,
                font_size_percentage=1,
                center_vertically=True,
                center_horizontally=True,
                rectangle_padding=1,
            )
        chosen_folder = None
        if 0 <= self.encoder_0 < 1:
            chosen_folder = self.patches["Factory"]
        elif 1 <= self.encoder_0 < 2:
            chosen_folder = self.patches["Third Party"]
        elif 2 <= self.encoder_0 < 3:
            chosen_folder = self.patches["User"]
        for idx1, nest1 in enumerate(chosen_folder.items()):
            for idx2, nest2 in enumerate(nest1):
                if isinstance(nest2, dict) and idx1 == 0:
                    for idx3, nest3 in enumerate(nest2):
                        if isinstance(nest3, dict):
                            pass
                        else:
                            show_text(
                                ctx,
                                2,
                                20 * idx3 + 5,
                                nest3,
                                height=20,
                                font_color=definitions.WHITE,
                                background_color=background,
                                font_size_percentage=1,
                                center_vertically=True,
                                center_horizontally=True,
                                rectangle_padding=1,
                            )
                elif isinstance(nest2, str):
                    show_text(
                        ctx,
                        1,
                        20 * idx1 + 5,
                        nest2,
                        height=20,
                        font_color=definitions.WHITE,
                        background_color=background,
                        font_size_percentage=1,
                        center_vertically=True,
                        center_horizontally=True,
                        rectangle_padding=1,
                    )
            # encoder_1 = 0
            # if encoder_1 == idx:
            #     for idx, nest2 in enumerate(chosen_folder[encoder_1]):
            #         show_text(
            #             ctx,
            #             2,
            #             20 * idx + 5,
            #             nest2,
            #             height=20,
            #             font_color=definitions.WHITE,
            #             background_color=background,
            #             font_size_percentage=1,
            #             center_vertically=True,
            #             center_horizontally=True,
            #             rectangle_padding=1,
            #         )

    def on_button_pressed(self, button_name):
        if button_name in [
            push2_python.constants.BUTTON_LEFT,
            push2_python.constants.BUTTON_RIGHT,
        ]:
            show_prev, show_next = self.has_prev_next_pages()
            if button_name == push2_python.constants.BUTTON_LEFT and show_prev:
                self.prev_page()
            elif button_name == push2_python.constants.BUTTON_RIGHT and show_next:
                self.next_page()
            return True

    def on_encoder_rotated(self, encoder_name, increment):
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
            if encoder_name == push2_python.constants.ENCODER_TRACK1_ENCODER:
                if 0 <= self.encoder_0 + increment * 0.1 < len(self.patches):
                    self.encoder_0 += increment * 0.1
                else:
                    pass
            if encoder_name == push2_python.constants.ENCODER_TRACK2_ENCODER:
                self.encoder_1 += increment * 0.1
        except ValueError:
            pass  # Encoder not in list
