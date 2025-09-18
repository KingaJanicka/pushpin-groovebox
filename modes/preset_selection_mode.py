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
log = logging.getLogger("preset_selection_mode")

# log.setLevel(level=logging.DEBUG)


class PresetSelectionMode(definitions.PyshaMode):

    xor_group = "pads"

    presets = {}
    presets_filename = "presets.json"
    pad_pressing_states = {}
    last_pad_in_column_pressed = {}
    pad_quick_press_time = 0.400
    current_page = 0
    patches = {}
    state = [0] * 8
    patches_dicts = []
    current_address = None

    def initialize(self, settings=None):
        for idx, instrument_short_name in enumerate(
            self.get_all_distinct_instrument_short_names_helper()
        ):
            self.presets[instrument_short_name] = [
                f"{definitions.FACTORY_PATCHES_FOLDER}/Templates/Init Saw"
            ] * 8
            self.last_pad_in_column_pressed[instrument_short_name] = (0, idx)

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

        try:
            
            self.load_presets()
        except:
            self.save_presets()


    def init_surge_preset_state(self):
        print("Init surge preset state")
        for idx, instrument in enumerate(self.app.instruments):
            for index in range(8):
                preset_name = f"{instrument}_{index}"            
                preset_path = f"{definitions.SURGE_STATE_FOLDER}/{preset_name}"
                does_file_exist = os.path.isfile(f"{preset_path}.fxp") 
                if does_file_exist == False:
                    print('regen')
                    self.send_osc("/patch/load", self.presets[instrument][idx], instrument_shortname=instrument)
                    time.sleep(0.1)
                    self.send_osc("/patch/save", preset_path, instrument_shortname=instrument)
                    time.sleep(0.1)
            

    def save_pad_to_state(self):
        instrument_shortname = (
            self.app.instrument_selection_mode.get_current_instrument_short_name()
        )
        instrument_index = self.app.instrument_selection_mode.get_current_instrument_info()["instrument_index"]
        preset_index = self.last_pad_in_column_pressed[instrument_shortname][0]
        preset_name = f"{instrument_shortname}_{preset_index}"            
        preset_path = f"{definitions.SURGE_STATE_FOLDER}/{preset_name}"
        print(preset_path)
        self.send_osc("/patch/save", preset_path, instrument_shortname=instrument_shortname)

    def save_all_presets_to_state(self):
        print("saving presets")
        for idx, instrument_shortname in enumerate(self.app.instruments):
            preset_index = self.last_pad_in_column_pressed[instrument_shortname][0]
            preset_name = f"{instrument_shortname}_{preset_index}"            
            preset_path = f"{definitions.SURGE_STATE_FOLDER}/{preset_name}"
            # print(preset_path)
            self.send_osc("/patch/save", preset_path, instrument_shortname=instrument_shortname)
            # time.sleep(1)
            
        # self.app.osc_mode.save_state()
        print("saved presets to state")

    async def load_init_state(self, instrument_shortname):
        # Check if there is a preset in the state dir
        # If yes load that
        # If not then load the normal patch and save to the state
    
        preset_name = f"{instrument_shortname}_{0}"            
        preset_path = f"{definitions.SURGE_STATE_FOLDER}/{preset_name}"
        self.send_osc("/patch/load", preset_path, instrument_shortname=instrument_shortname)
        self.send_osc("/q/all_params",preset_path, instrument_shortname=instrument_shortname)
        instrument = self.app.instruments[instrument_shortname]
        await asyncio.sleep(1)
        instrument.query_slots()
        await asyncio.sleep(1)
        instrument.update_current_devices()
        await asyncio.sleep(2)
        instrument.query_all_controls()
        self.send_osc("/q/all_params",preset_path, instrument_shortname=instrument_shortname)
        instrument.query_all_controls()

        # Turns out we don't need those statements but leaving them in here just
        # in case this pattern is needed later 
        # if instrument.current_devices[0].label == "Audio In":
        #     print(instrument.name)

        # elif instrument.current_devices[1].label == "Audio In":
        #     print(instrument.name)

        # time.sleep(1)
        # instrument.init_devices_sync()
        # print("end of load init presets")
        
        
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

    def load_presets(self):
        if os.path.exists(self.presets_filename):
            self.presets = json.load(open(self.presets_filename))

    def save_presets(self):
        json.dump(self.presets, open(self.presets_filename, "w"))  # Save to file

    def new_instrument_selected(self):
        self.current_page = 0
        self.save_all_presets_to_state()
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
        self.save_presets()

    def get_all_distinct_instrument_short_names_helper(self):
        return (
            self.app.instrument_selection_mode.get_all_distinct_instrument_short_names()
        )

    def get_current_instrument_short_name_helper(self):
        return self.app.instrument_selection_mode.get_current_instrument_short_name()

    def get_preset_path_for_instrument(self, instrument_shortname):
        preset_tuple = self.last_pad_in_column_pressed[instrument_shortname]
        preset_index = preset_tuple[0]
        preset = self.presets[instrument_shortname][preset_index]
        path = self.get_preset_path(preset)
        return preset

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
            self.save_presets()

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

    # def send_select_new_preset(self, preset_num):
    #     msg = mido.Message(
    #         "program_change", program=preset_num
    #     )  # Should this be 1-indexed?
    #     self.app.send_midi(msg)

    # def send_select_new_bank(self, bank_num):
    #     # If synth only has 1 bank, don't send bank change messages
    #     if self.get_num_banks() > 1:
    #         msg = mido.Message(
    #             "control_change", control=0, value=bank_num
    #         )  # Should this be 1-indexed?
    #         self.app.send_midi(msg)

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

    def activate(self):
        self.update_pads()
        self.notify_status_in_display()
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
                cell_color = instrument_info["color"]

                if not self.presets[instrument_short_name][j]:
                    cell_color = f"{cell_color}_darker1"  # If preset not in favourites, use a darker version of the instrument color
                elif (
                    i == self.last_pad_in_column_pressed[instrument_short_name][0]
                    and j == self.last_pad_in_column_pressed[instrument_short_name][1]
                ):
                    cell_color = definitions.WHITE
                row_colors.append(cell_color)
            color_matrix.append(row_colors)
        self.push.pads.set_pads_color(color_matrix)

    def on_pad_pressed(self, pad_n, pad_ij, velocity):
        if pad_ij[1] != self.app.instrument_selection_mode.selected_instrument:
            self.app.instrument_selection_mode.select_instrument(pad_ij[1])

        instrument_short_name = (
            self.app.instrument_selection_mode.get_current_instrument_short_name()
        )
        self.last_pad_in_column_pressed[instrument_short_name] = pad_ij
        self.set_knob_postions()
        log.debug(f"Loading {self.presets[instrument_short_name][pad_ij[0]]}")
        self.send_osc("/patch/load", self.presets[instrument_short_name][pad_ij[0]])
        self.update_pads()

        # Resets the last knob position on the mod matrix
        # to avoid indexing OOB when switching presets
        instrument = self.app.osc_mode.get_current_instrument()
        devices = self.app.osc_mode.get_current_instrument_devices()
        for device in devices:
            if device.label == "Mod Matrix":
                device.controls[7] = 0

        return True  # Prevent other modes to get this event

    def on_pad_released(self, pad_n, pad_ij, velocity):
        instrument = self.app.osc_mode.get_current_instrument()
        instrument.query_slots()
        instrument.query_all_controls()
        instrument.update_current_devices()
        instrument.init_devices_sync()
        self.update_pads()
        return True  # Prevent other modes to get this event

    def nested_draw(
        self,
        ctx,
        current,
        level,
        max_height,
        item_height=20,
        padding_top=5,
        instrument_selector_height=20,
    ):
        for idx, entry in enumerate(current.items()):
            key, val = entry
            bg_color = (
                definitions.YELLOW
                if int(self.state[level]) == idx
                else definitions.GREEN
            )
            text_color = (
                definitions.BLACK
                if int(self.state[level]) == idx
                else definitions.WHITE
            )

            if isinstance(val, str) and idx - 2 <= self.state[level] <= idx + 3:
                if idx == int(self.state[level]):
                    self.current_address = os.path.splitext(self.get_preset_path(val))[
                        0
                    ]
                show_text(
                    ctx,
                    level,
                    item_height * (idx - int(self.state[level])) + padding_top + 60,
                    Path(val).stem,
                    height=item_height,
                    font_color=text_color,
                    background_color=bg_color,
                    font_size_percentage=1,
                    center_vertically=True,
                    center_horizontally=True,
                    rectangle_padding=1,
                )
            elif isinstance(val, dict) and idx - 2 <= self.state[level] <= idx + 3:
                show_text(
                    ctx,
                    level,
                    item_height * (idx - int(self.state[level])) + padding_top + 60,
                    key,
                    height=item_height,
                    font_color=text_color,
                    background_color=bg_color,
                    font_size_percentage=1,
                    center_vertically=True,
                    center_horizontally=True,
                    rectangle_padding=1,
                )
                if int(self.state[level]) == idx:
                    self.nested_draw(ctx, val, level=level + 1, max_height=max_height)

    def get_preset_path(self, preset):
        chosen_folder = None
        if 0 <= self.state[0] < 1:
            chosen_folder = definitions.FACTORY_PATCHES_FOLDER
        elif 1 <= self.state[0] < 2:
            chosen_folder = definitions.THIRD_PARTY_PATCHES_FOLDER
        elif 2 <= self.state[0] < 3:
            chosen_folder = definitions.USER_PATCHES_FOLDER
        return chosen_folder + "/" + preset

    def update_display(self, ctx, w, h):
        self.nested_draw(ctx, self.patches, level=0, max_height=h)
        show_text(
            ctx,
            6,
            15,
            "Set Preset",
            height=15,
            font_color=definitions.WHITE,
        )

    def set_knob_postions(self):
        # TODO: This funciton is not working corretly really
        # Presets won't draw correctly when switching instrumnents, some won't draw at all
        # Needs to set all knobs not just one
        instrument_short_name = (
            self.app.instrument_selection_mode.get_current_instrument_short_name()
        )
        preset_number = self.last_pad_in_column_pressed[instrument_short_name][0]
        preset_address = self.presets[instrument_short_name][preset_number]

        address_array = (
            preset_address.replace(definitions.FACTORY_PATCHES_FOLDER, "")
            .replace(definitions.THIRD_PARTY_PATCHES_FOLDER, "")
            .replace(definitions.USER_PATCHES_FOLDER, "")[1:]
            .split("/")
        )
        # address_array[-1] = address_array[-1] + ".fxp"
        level = None

        try:
            if definitions.FACTORY_PATCHES_FOLDER in preset_address:
                self.state[0] = 0
                level = self.patches["Factory"]
            elif definitions.THIRD_PARTY_PATCHES_FOLDER in preset_address:
                self.state[0] = 1
                level = self.patches["Third Party"]
            elif definitions.USER_PATCHES_FOLDER in preset_address:
                self.state[0] = 2
                level = self.patches["User"]

            for idx, piece in enumerate(address_array):
                self.state[idx + 1] = list(level).index(piece)
                level = level[piece]  # who knows what this line does? But it works!
        except Exception as e:
            print(
                f"ERROR in preset_selection_mode set_knob_positions() at {preset_address}"
            )
            traceback.print_exc()

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
            instrument_short_name = (
                self.app.instrument_selection_mode.get_current_instrument_short_name()
            )
            preset_number = self.last_pad_in_column_pressed[instrument_short_name][0]
            self.presets[instrument_short_name][preset_number] = self.current_address
            self.save_presets()
        
        elif button_name == push2_python.constants.BUTTON_PLAY:
            metro = self.app.metro_sequencer_mode
            if metro.sequencer_is_playing == False:
                metro.start_timeline()
                metro.sequencer_is_playing = True

            elif metro.sequencer_is_playing == True:
                metro.stop_timeline()
                metro.sequencer_is_playing = False


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

            current_dict = self.patches
            for level in range(encoder_idx):
                for idx, entry in enumerate(current_dict.values()):
                    if int(self.state[level]) == idx:
                        if isinstance(entry, dict):
                            current_dict = entry

            if (
                0
                <= self.state[encoder_idx] + increment * 0.1
                < len(current_dict.keys())
            ):
                if int(self.state[encoder_idx] + increment * 0.1) != int(
                    self.state[encoder_idx]
                ):
                    for idx in range(encoder_idx + 1, 8 - encoder_idx):
                        self.state[idx] = 0

                self.state[encoder_idx] += increment * 0.1

        except ValueError:
            pass  # Encoder not in list

    def send_osc(self, *args, instrument_shortname=None):
        instrument = self.app.instruments.get(
            instrument_shortname or self.app.osc_mode.get_current_instrument_short_name_helper(), None
        )
        # print(instrument_shortname, instrument)
        if instrument:
            return instrument.send_message(*args)
