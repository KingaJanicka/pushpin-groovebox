import definitions
import push2_python
import os
import json
import traceback
from glob import glob
from user_interface.display_utils import show_text
from pathlib import Path
import logging
import time
import asyncio

log = logging.getLogger("clip_selection_mode")
from controllers import push2_constants

# log.setLevel(level=logging.DEBUG)


class ClipSelectionMode(definitions.PyshaMode):

    xor_group = "pads"

    presets = {}
    presets_filename = "presets.json"
    clips = []
    last_pad_in_column_pressed = {}
    pad_quick_press_time = 0.400
    current_page = 0
    patches = {}
    state = [0] * 8
    patches_dicts = []
    current_address = None

    def initialize(self, settings=None):
        self.clips = [
            [False, False, False, False, False, False, False, False],
            [False, False, False, False, False, False, False, False],
            [False, False, False, False, False, False, False, False],
            [False, False, False, False, False, False, False, False],
            [False, False, False, False, False, False, False, False],
            [False, False, False, False, False, False, False, False],
            [False, False, False, False, False, False, False, False],
            [False, False, False, False, False, False, False, False],
        ]
        for idx, instrument_short_name in enumerate(
            self.get_all_distinct_instrument_short_names_helper()
        ):
            self.last_pad_in_column_pressed[instrument_short_name] = (0, idx)

    def save_pad_to_state(self):
        return
        instrument_shortname = (
            self.app.instrument_selection_mode.get_current_instrument_short_name()
        )
        instrument_index = (
            self.app.instrument_selection_mode.get_current_instrument_info()[
                "instrument_index"
            ]
        )
        preset_index = self.last_pad_in_column_pressed[instrument_shortname][0]
        preset_name = f"{instrument_shortname}_{preset_index}"
        preset_path = f"{definitions.SURGE_STATE_FOLDER}/{preset_name}"
        print(preset_path)
        self.send_osc(
            "/patch/save", preset_path, instrument_shortname=instrument_shortname
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

    def new_instrument_selected(self):
        self.current_page = 0
        # self.save_all_presets_to_state()
        self.app.pads_need_update = True
        self.app.buttons_need_update = True

    def should_be_enabled(self):
        return True

    def get_all_distinct_instrument_short_names_helper(self):
        return (
            self.app.instrument_selection_mode.get_all_distinct_instrument_short_names()
        )

    def get_current_page(self):
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

    def get_current_instrument_short_name_helper(self):
        return self.app.instrument_selection_mode.get_current_instrument_short_name()

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

    def notify_status_in_display(self):
        bank_number = self.get_current_page() // 2 + 1
        bank_names = self.get_bank_names()
        if bank_names is not None:
            bank_name = bank_names[bank_number - 1]
        else:
            bank_name = bank_number
        self.app.add_display_notification(
            "Preset: bank {0}, presets {1}".format(
                bank_name, "1-64" if self.get_current_page() % 2 == 0 else "65-128"
            )
        )

    def list_clips(self):
        self.clips = [
            [False, False, False, False, False, False, False, False],
            [False, False, False, False, False, False, False, False],
            [False, False, False, False, False, False, False, False],
            [False, False, False, False, False, False, False, False],
            [False, False, False, False, False, False, False, False],
            [False, False, False, False, False, False, False, False],
            [False, False, False, False, False, False, False, False],
            [False, False, False, False, False, False, False, False],
        ]
        
        try:
            files = glob("seq_metro_*_*.json")
            for filename in files:
                [inst, clip] = (
                    os.path.basename(filename)
                    .replace("seq_metro_", "")
                    .replace(".json", "")
                    .split("_")
                )
                inst_number = inst[-1]
                # print(inst, inst_number, clip)
                self.clips[int(clip)][int(inst_number)] = True
        except Exception as e:
            print(e)

    def activate(self):
        self.list_clips()
        self.update_pads()
        instrument_short_name = (
            self.app.instrument_selection_mode.get_current_instrument_short_name()
        )
        sequencer = self.app.metro_sequencer_mode.instrument_sequencers[
            instrument_short_name
        ]
        sequencer.save_state(clip=self.last_pad_in_column_pressed[instrument_short_name][0])
    
        
        self.push.buttons.set_button_color(
            push2_constants.BUTTON_DELETE, definitions.GRAY_DARK
        )

    def deactivate(self):
        self.app.push.pads.set_all_pads_to_color(color=definitions.BLACK)
        self.push.buttons.set_button_color(
            push2_constants.BUTTON_DELETE, definitions.BLACK
        )
        self.push.buttons.set_button_color(
            push2_python.constants.BUTTON_LEFT, definitions.BLACK
        )
        self.push.buttons.set_button_color(
            push2_python.constants.BUTTON_RIGHT, definitions.BLACK
        )
        self.app.buttons_need_update = True
        self.app.pads_need_update = True
        # self.save_all_presets_to_state()
        try:
            for idx, instrument_shortname in enumerate(self.app.instruments):
                instrument = self.app.instruments[instrument_shortname]

                instrument.update_current_devices()
        except Exception as e:
            pass

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
        color_matrix = []
        for i in range(0, 8):
            row_colors = []
            for j in range(0, 8):
                instrument_info = self.app.instrument_selection_mode.instruments_info[j]
                instrument_short_name = instrument_info["instrument_short_name"]
                base_color = instrument_info["color"]
                if self.clips[i][j] == True:
                    cell_color = f"{base_color}_darker1"
                elif self.clips[i][j] == False:
                    cell_color = definitions.BLACK
                
                if (
                    i == self.last_pad_in_column_pressed[instrument_short_name][0]
                    and j == self.last_pad_in_column_pressed[instrument_short_name][1]
                ):
                    cell_color = base_color

                # if (
                #     not hasattr(self.clips, instrument_short_name)
                #     or not self.clips[instrument_short_name][j]
                # ):
                #     cell_color = f"{cell_color}_darker1"  # If preset not in favourites, use a darker version of the instrument color
                # elif (
                #     i == self.last_pad_in_column_pressed[instrument_short_name][0]
                #     and j == self.last_pad_in_column_pressed[instrument_short_name][1]
                # ):
                #     cell_color = definitions.WHITE
                row_colors.append(cell_color)
            color_matrix.append(row_colors)
        self.push.pads.set_pads_color(color_matrix)

    def on_pad_pressed(self, pad_n, pad_ij, velocity):
        selected_pad_instrument_shortname = None
        for idx, instrument_short_name in enumerate(
            self.get_all_distinct_instrument_short_names_helper()
        ):
            if idx == pad_ij[1]:
                selected_pad_instrument_shortname = instrument_short_name

        sequencer = self.app.metro_sequencer_mode.instrument_sequencers[
            selected_pad_instrument_shortname
        ]
        last_pad_pressed = self.last_pad_in_column_pressed[selected_pad_instrument_shortname]
        if last_pad_pressed == pad_ij:
            # print("save clip", last_pad_pressed[0])
            sequencer.save_state(clip=last_pad_pressed[0])

        self.last_pad_in_column_pressed[selected_pad_instrument_shortname] = pad_ij
        self.update_pads()

        sequencer.load_state(clip=pad_ij[0])

        return True  # Prevent other modes to get this event

    def on_pad_released(self, pad_n, pad_ij, velocity):
        return True  # Prevent other modes to get this event

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


        elif button_name in push2_python.constants.BUTTON_UPPER_ROW_7:
            return
            instrument_short_name = (
                self.app.instrument_selection_mode.get_current_instrument_short_name()
            )
            preset_number = self.last_pad_in_column_pressed[instrument_short_name][0]
            self.presets[instrument_short_name][preset_number] = self.current_address
            self.save_presets()
            self.app.metro_sequencer_mode.save_state()

        elif button_name == push2_python.constants.BUTTON_PLAY:
            metro = self.app.metro_sequencer_mode
            if metro.sequencer_is_playing == False:
                metro.start_timeline()
                metro.sequencer_is_playing = True

            elif metro.sequencer_is_playing == True:
                metro.stop_timeline()
                metro.sequencer_is_playing = False

        elif button_name == push2_python.constants.BUTTON_DELETE:
            instrument_short_name = (
                self.app.instrument_selection_mode.get_current_instrument_short_name()
            )
            sequencer = self.app.metro_sequencer_mode.instrument_sequencers[
                instrument_short_name
            ]
            last_pad_pressed = self.last_pad_in_column_pressed[instrument_short_name]
            sequencer.delete_state(clip=last_pad_pressed[0])
            self.clips[last_pad_pressed[0]][last_pad_pressed[1]] = False
            self.app.pads_need_update = True

    def send_osc(self, *args, instrument_shortname=None):
        instrument = self.app.instruments.get(
            instrument_shortname
            or self.app.osc_mode.get_current_instrument_short_name_helper(),
            None,
        )
        # print(instrument_shortname, instrument)
        if instrument:
            return instrument.send_message(*args)
