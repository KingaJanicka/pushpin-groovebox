from __future__ import annotations

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
import m2k_state
log = logging.getLogger("preset_selection_mode")

# mono2k tracks' current slots are saved this often (seconds) when they changed,
# so a power cut loses at most that much of a sound's edits
M2K_AUTOSAVE_SECONDS = 5.0
# Holding a slot's pad this long (seconds) opens the browser, as SELECT + pad does
PAD_LONG_PRESS_SECONDS = 0.5

# log.setLevel(level=logging.DEBUG)


class PresetSelectionMode(definitions.PyshaMode):

    xor_group = "pads"

    presets = {}
    presets_filename = "presets.json"
    last_pad_in_column_pressed = {}
    current_page = 0
    patches = {}
    state: list[float | int] = [0] * 8
    patches_dicts = []
    current_address = None
    select_button_held = False
    browser_active = False
    # A pad held without SELECT opens the browser after PAD_LONG_PRESS_SECONDS.
    # Opened that way, releasing the pad loads a sound only once an encoder has
    # moved the browser: it opens on the slot's own preset, and just holding and
    # letting go must not reload that over the slot's edits.
    _pad_down_at = None
    _opened_by_long_press = False
    _browsed = False
    # mono2k: each track's slot names (browser ids), its sound catalogue, and
    # what was last saved for each track (to autosave only changes)
    m2k_presets = {}
    m2k_presets_filename = "m2k_presets.json"
    m2k_sounds = None
    m2k_state_folder = definitions.M2K_STATE_FOLDER
    _m2k_saved = {}
    _m2k_autosave_at = 0.0
    _browsing_m2k = False

    def initialize(self, settings=None):
        for idx, instrument_short_name in enumerate(
            self.get_all_distinct_instrument_short_names_helper()
        ):
            self.presets[instrument_short_name] = [
                f"{definitions.FACTORY_PATCHES_FOLDER}/Templates/Init Saw"
            ] * 8
            self.last_pad_in_column_pressed[instrument_short_name] = (0, idx)

        try:
            self.patches["Factory"] = self.create_dict_from_paths(
                glob(
                    f"**/*.fxp",
                    recursive=True,
                    root_dir=definitions.FACTORY_PATCHES_FOLDER,
                )
            )
            print(definitions.FACTORY_PATCHES_FOLDER)
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
        except Exception as e:
            print("Exception in preset mode init ",e)
        try:
            
            self.load_presets()
        except:
            self.save_presets()

        self.m2k_sounds = m2k_state.M2KSounds.load(user_folder=definitions.M2K_USER_PRESETS_FOLDER)
        self.m2k_presets = {
            name: [None] * 8 for name in self.get_all_distinct_instrument_short_names_helper()
        }
        self._m2k_saved = {}
        self.load_m2k_presets()

    # ------------------------------------------------------------------ mono2k

    def load_m2k_presets(self):
        try:
            with open(self.m2k_presets_filename) as f:
                saved = json.load(f)
        except (OSError, ValueError):
            return
        for name, slots in saved.items():
            if name in self.m2k_presets and isinstance(slots, list):
                self.m2k_presets[name] = (list(slots) + [None] * 8)[:8]

    def save_m2k_presets(self):
        try:
            with open(self.m2k_presets_filename, "w") as f:
                json.dump(self.m2k_presets, f, indent=1)
        except OSError as e:
            log.warning("could not save %s: %s", self.m2k_presets_filename, e)

    def m2k_instrument(self, instrument_short_name):
        """The instrument if it's playing mono2k (and the sounds are known), else None."""
        if self.m2k_sounds is None:
            return None
        instrument = self.app.instruments.get(instrument_short_name, None)
        if instrument is None or getattr(instrument, "active_engine_name", None) != "mono2k":
            return None
        return instrument

    def m2k_slot_path(self, instrument_short_name, slot):
        return os.path.join(self.m2k_state_folder, f"{instrument_short_name}_{slot}.json")

    def current_slot(self, instrument_short_name):
        return self.last_pad_in_column_pressed[instrument_short_name][0]

    def save_m2k_slot(self, instrument, slot=None):
        """Save what the track's mono2k voice plays into its slot (default: the current one)."""
        if self.m2k_sounds is None:
            return
        slot = self.current_slot(instrument.name) if slot is None else slot
        sound = m2k_state.capture(instrument.osc["client"], self.m2k_sounds)
        if sound is None:
            return
        try:
            self.m2k_sounds.write(self.m2k_slot_path(instrument.name, slot), sound)
            self._m2k_saved[instrument.name] = (slot, sound.params, sound.machine)
        except OSError as e:
            log.warning("could not save %s slot %s: %s", instrument.name, slot, e)

    def load_m2k_slot(self, instrument, slot):
        """Play the track's slot on its mono2k voice: the saved sound, or for an
        empty slot its machine's INIT (the definition's m2k_machine, else the first)."""
        if self.m2k_sounds is None:
            return
        sound = self.m2k_sounds.read(self.m2k_slot_path(instrument.name, slot))
        if sound is None:
            machine = getattr(instrument, "definition", {}).get("m2k_machine", 0) or 0
            sound = self.m2k_sounds.machine_sound(int(machine))
        m2k_state.apply(sound, instrument.osc["client"], self.m2k_sounds)
        self._m2k_saved[instrument.name] = (slot, sound.params, sound.machine)

    def restore_m2k_slot(self, instrument):
        """The track's current slot's saved sound, if it has one, on its mono2k voice."""
        if self.m2k_instrument(instrument.name) is None:
            return
        slot = self.current_slot(instrument.name)
        if os.path.isfile(self.m2k_slot_path(instrument.name, slot)):
            self.load_m2k_slot(instrument, slot)

    def restore_m2k_slots(self):
        """At startup: each track playing mono2k gets its current slot's saved sound."""
        for name in self.app.instruments:
            self.restore_m2k_slot(self.app.instruments[name])

    def autosave_m2k(self, now=None):
        """Save each mono2k track's current slot when its sound changed (at most
        every M2K_AUTOSAVE_SECONDS)."""
        now = time.monotonic() if now is None else now
        if now - self._m2k_autosave_at < M2K_AUTOSAVE_SECONDS:
            return
        self._m2k_autosave_at = now
        for name in self.app.instruments:
            instrument = self.m2k_instrument(name)
            if instrument is None:
                continue
            sound = m2k_state.capture(instrument.osc["client"], self.m2k_sounds)
            if sound is None:
                continue
            if self._m2k_saved.get(name) != (self.current_slot(name), sound.params, sound.machine):
                self.save_m2k_slot(instrument)

    # --------------------------------------------------------------- renaming

    def rename_target(self, instrument_short_name):
        """The current slot's preset, if it's a user preset that can be renamed:
        ("mono2k", name) or ("surge", path without .fxp); else None."""
        slot = self.current_slot(instrument_short_name)
        if self.m2k_instrument(instrument_short_name) is not None:
            sound_id = self.m2k_presets.get(instrument_short_name, [None] * 8)[slot]
            if sound_id and sound_id.startswith(m2k_state.USER + "/") and sound_id.split("/", 1)[1] in self.m2k_sounds.user_files():
                return ("mono2k", sound_id.split("/", 1)[1])
            return None
        path = self.presets.get(instrument_short_name, [None] * 8)[slot]
        if path and path.startswith(definitions.USER_PATCHES_FOLDER + "/") and os.path.isfile(path + ".fxp"):
            return ("surge", path)
        return None

    @staticmethod
    def _name_problem(name):
        if not name or name in (".", "..") or "/" in name or "\\" in name:
            return "That name can't be used"
        return None

    def rename_preset(self, instrument_short_name, new_name):
        """Rename the current slot's user preset to ``new_name``, and every slot
        that uses it. Returns None when done, or why not."""
        new_name = new_name.strip()
        problem = self._name_problem(new_name)
        if problem:
            return problem
        target = self.rename_target(instrument_short_name)
        if target is None:
            return "This slot's preset isn't a user preset"
        kind, old = target
        if kind == "mono2k":
            if new_name == old:
                return None
            files = self.m2k_sounds.user_files()
            if new_name in files:
                return "That name is taken"
            new_path = os.path.join(self.m2k_sounds.user_folder, f"{new_name}.json")
            sound = self.m2k_sounds.read(files[old])
            if sound is None:
                return "The preset couldn't be read"
            sound.name = new_name
            self.m2k_sounds.write(new_path, sound)
            os.remove(files[old])
            old_id, new_id = f"{m2k_state.USER}/{old}", f"{m2k_state.USER}/{new_name}"
            for slots in self.m2k_presets.values():
                for i, sound_id in enumerate(slots):
                    if sound_id == old_id:
                        slots[i] = new_id
            self.save_m2k_presets()
        else:
            new_path = os.path.join(os.path.dirname(old), new_name)
            if new_path == old:
                return None
            if os.path.exists(new_path + ".fxp"):
                return "That name is taken"
            os.rename(old + ".fxp", new_path + ".fxp")
            for slots in self.presets.values():
                for i, path in enumerate(slots):
                    if path == old:
                        slots[i] = new_path
            self.save_presets()
            self.patches["User"] = self.create_dict_from_paths(
                glob("**/*.fxp", recursive=True, root_dir=definitions.USER_PATCHES_FOLDER)
            )
        self.set_knob_postions()
        self.app.add_display_notification(f"Renamed to {new_name}")
        return None

    def start_rename(self):
        """Upper button 3: rename the current slot's user preset on the Push."""
        name = self.get_current_instrument_short_name_helper()
        target = self.rename_target(name)
        if target is None:
            hint = "Save to New first" if self.m2k_instrument(name) is not None else "only Surge user patches"
            self.app.add_display_notification(f"Only user presets can be renamed ({hint})")
            return
        kind, old = target
        current = old if kind == "mono2k" else os.path.basename(old)
        slot = self.current_slot(name) + 1
        self.app.rename_mode.start(
            f"Rename {name} slot {slot}: {current}",
            current,
            lambda new_name: self.rename_preset(name, new_name),
            cancel_button=push2_python.constants.BUTTON_UPPER_ROW_3,
        )

    def browser_tree(self):
        """The preset browser's tree for the current track's engine."""
        if self.m2k_instrument(self.get_current_instrument_short_name_helper()) is not None:
            return self.m2k_sounds.tree()
        return self.patches

    def slot_label(self, instrument_short_name, index):
        """What the slot grid shows for a slot."""
        if self.m2k_instrument(instrument_short_name) is not None:
            sound_id = self.m2k_presets.get(instrument_short_name, [None] * 8)[index]
            return sound_id.split("/")[-1] if sound_id else "-"
        return self._resolve_preset(self.presets[instrument_short_name][index]).split("/")[-1]


    DEFAULT_PRESET = f"{definitions.FACTORY_PATCHES_FOLDER}/Templates/Init Saw"

    def _resolve_preset(self, path):
        """Return path if non-empty, otherwise the Init Saw fallback."""
        return path if path else self.DEFAULT_PRESET

    def init_surge_preset_state(self):
        print("Init surge preset state")
        # TODO: this regen routine is fucked
        # As checked with the GUI
        for idx, instrument in enumerate(self.app.instruments):
            # print(self.presets[instrument])
            for index in range(8):
                preset_name = f"{instrument}_{index}"           
                preset_path = f"{definitions.SURGE_STATE_FOLDER}/{preset_name}"
                # print("preset_path", preset_path)
                does_file_exist = os.path.isfile(f"{preset_path}.fxp")
                if does_file_exist == False:
                    # print('regen')
                    # print(self.presets[instrument][index], preset_path)
                    self.send_osc("/patch/load", self._resolve_preset(self.presets[instrument][index]), instrument_shortname=instrument)
                    time.sleep(0.1)
                    self.send_osc("/patch/save", preset_path, instrument_shortname=instrument)
                    time.sleep(0.1)
            

    def save_pad_to_state(self):
        
        # This saves to the surge_state folder
        # Making sure we don't overwrite the actual synth patches
        
        # TODO: I think this should be saving corectly now
        instrument_shortname = (
            self.app.instrument_selection_mode.get_current_instrument_short_name()
        )
        instrument_index = self.app.instrument_selection_mode.get_current_instrument_info()["instrument_index"]
        preset_index = self.last_pad_in_column_pressed[instrument_shortname][0]
        preset_name = f"{instrument_shortname}_{preset_index}"            
        preset_path = f"{definitions.SURGE_STATE_FOLDER}/{preset_name}"
        # print(preset_path)
        try:
            self.send_osc("/patch/save", None, instrument_shortname=instrument_shortname)
        except Exception as e:
            print("error in save_pad_to_state", e)

    def save_all_presets_to_state(self):
        # print("saving presets")
        for name in self.app.instruments:
            instrument = self.m2k_instrument(name)
            if instrument is not None:
                self.save_m2k_slot(instrument)
        for idx, instrument_shortname in enumerate(self.app.instruments):
            preset_index = self.last_pad_in_column_pressed[instrument_shortname][0]
            preset_name = f"{instrument_shortname}_{preset_index}"            
            preset_path = f"{definitions.SURGE_STATE_FOLDER}/{preset_name}"
            # print(preset_path)
            self.send_osc("/patch/save", preset_path, instrument_shortname=instrument_shortname)
            # time.sleep(1)
            
        # self.app.osc_mode.save_state()
        # print("saved presets to state")

    async def load_init_state(self, instrument_shortname):
        # Check if there is a preset in the state dir
        # If yes load that
        # If not then load the normal patch and save to the state
        # TODO: Neither this nor the pad func seem to work
        # TODO: State is still being loaded, but where?
        preset_name = f"{instrument_shortname}_{0}"            
        preset_path = f"{definitions.SURGE_STATE_FOLDER}/{preset_name}"
        instrument = self.app.instruments[instrument_shortname]
        self.send_osc("/patch/load", preset_path, instrument_shortname=instrument_shortname)
        # print("loading preset", preset_path)
        await asyncio.sleep(0.5)
        if not getattr(instrument, "plays_surge", True):
            # The patch went to the track's Surge; the pages showing are another
            # engine's, and re-selecting them would reset its sound
            return
        instrument.query_slots()
        await asyncio.sleep(0.5)
        instrument.update_current_devices()
        await asyncio.sleep(0.5)
        # instrument.query_all_controls()
        for device in instrument.current_devices:
            await device.select()
            device.query_all()
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
        # self.save_all_presets_to_state()
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
        self.push.buttons.set_button_color(
            push2_python.constants.BUTTON_SELECT, definitions.BLACK
        )
        self.app.buttons_need_update = True
        self.app.pads_need_update = True
        self.save_all_presets_to_state()
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
        self.push.buttons.set_button_color(
            push2_python.constants.BUTTON_SELECT, definitions.WHITE
        )
        self.push.buttons.set_button_color(
            push2_python.constants.BUTTON_SHIFT, definitions.BLACK
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
        if self.last_pad_in_column_pressed[instrument_short_name] != pad_ij:
            m2k_instrument = self.m2k_instrument(instrument_short_name)
            if m2k_instrument is not None:
                # Keep the edits of the slot being left, then play the new one
                self.save_m2k_slot(m2k_instrument, self.current_slot(instrument_short_name))
            self.last_pad_in_column_pressed[instrument_short_name] = pad_ij
            if m2k_instrument is not None:
                self.load_m2k_slot(m2k_instrument, pad_ij[0])
            self.set_knob_postions()
            preset_name = f"{instrument_short_name}_{pad_ij[0]}"
            preset_path = f"{definitions.SURGE_STATE_FOLDER}/{preset_name}"
            log.debug(f"Loading {preset_path}")
            self.send_osc("/patch/load", preset_path, instrument_shortname=instrument_short_name)
            
        idx_j = pad_ij[1]
        self.update_pads()
        self.app.steps_held.append(idx_j)

        if self.select_button_held:
            self.browser_active = True
            self._opened_by_long_press = False
            self._pad_down_at = None
        else:
            self._pad_down_at = time.monotonic()

        # Resets the last knob position on the mod matrix
        # to avoid indexing OOB when switching presets
        instrument = self.app.osc_mode.get_current_instrument()
        devices = self.app.osc_mode.get_current_instrument_devices()
        for device in devices:
            if device.label == "Mod Matrix":
                device.controls[7] = 0

        return True  # Prevent other modes to get this event

    def check_for_delayed_actions(self, now=None):
        """A slot's pad held long enough opens the browser."""
        if self._pad_down_at is None or self.browser_active or not self.app.steps_held:
            return
        now = time.monotonic() if now is None else now
        if now - self._pad_down_at >= PAD_LONG_PRESS_SECONDS:
            self._pad_down_at = None
            self.browser_active = True
            self._opened_by_long_press = True
            self._browsed = False
            self.set_knob_postions()

    def browser_choice_wanted(self):
        """Whether releasing the pad should load the browsed sound into the slot."""
        if not (self.browser_active and self.current_address):
            return False
        return self._browsed or not self._opened_by_long_press

    def set_pad_preset_slot(self, pad_ij):
        """Load the browsed preset into the selected slot on long press.

        Returns True when a new preset was actually loaded, False otherwise.
        """
        for idx, instrument_shortname in enumerate(self.app.instruments):
            if idx == pad_ij[1]:
                preset_number = self.last_pad_in_column_pressed[instrument_shortname][0]

                m2k_instrument = self.m2k_instrument(instrument_shortname)
                if m2k_instrument is not None:
                    if not self.browser_choice_wanted():
                        return False
                    sound = self.m2k_sounds.resolve(self.current_address)
                    if sound is None:
                        return False
                    m2k_state.apply(sound, m2k_instrument.osc["client"], self.m2k_sounds)
                    self.save_m2k_slot(m2k_instrument, preset_number)
                    self.m2k_presets[instrument_shortname][preset_number] = self.current_address
                    self.save_m2k_presets()
                    return True

                if self.browser_choice_wanted():
                    # Load the chosen preset into Surge XT
                    self.send_osc("/patch/load", self.current_address, instrument_shortname=instrument_shortname)
                    time.sleep(0.5)

                    # Overwrite the surge_state slot for this pad with the new preset
                    preset_name = f"{instrument_shortname}_{preset_number}"
                    preset_path = f"{definitions.SURGE_STATE_FOLDER}/{preset_name}"
                    log.debug(f"Saving new preset to state: {preset_path}")
                    self.send_osc("/patch/save", preset_path, instrument_shortname=instrument_shortname)
                    time.sleep(0.5)

                    # Record the new source path in presets.json so the display name updates
                    self.presets[instrument_shortname][preset_number] = self.current_address
                    self.save_presets()
                    return True
        return False

    async def _refresh_devices_after_preset_load(self, instrument_shortname):
        """Re-query slot types and re-select devices after a new preset is loaded.

        Surge replies to /q messages asynchronously, so we must sleep between
        query_slots() and update_current_devices() to let the OSC replies arrive.
        """
        instrument = self.app.instruments[instrument_shortname]
        if not getattr(instrument, "plays_surge", True):
            return  # the preset is Surge's; another engine's pages are showing
        instrument.query_slots()
        await asyncio.sleep(0.5)
        instrument.update_current_devices()
        await asyncio.sleep(0.5)
        for device in instrument.current_devices:
            await device.select()
            device.query_all()

    def on_pad_released(self, pad_n, pad_ij, velocity):
        instrument = self.app.osc_mode.get_current_instrument()

        preset_loaded = False
        try:
            preset_loaded = self.set_pad_preset_slot(pad_ij)
        except Exception as e:
            print("exception in set_pad_preset", e)

        if preset_loaded:
            # Slot types may have changed — refresh with proper async delays so
            # Surge's OSC replies arrive before we call update_current_devices.
            instrument_shortname = instrument.name
            self.app.queue.append(
                self._refresh_devices_after_preset_load(instrument_shortname)
            )
        else:
            instrument.query_slots()
            instrument.query_all_controls()
            instrument.update_current_devices()
            if getattr(instrument, "plays_surge", True):
                # (re-sending a mono2k machine's init would reset its sound to INIT)
                instrument.init_devices_sync()

        self.update_pads()
        idx_j = pad_ij[1]
        self.app.steps_held.remove(idx_j)
        self.browser_active = False
        self._pad_down_at = None
        self._opened_by_long_press = False
        self._browsed = False

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

            if isinstance(val, str) and idx - 2 <= self.state[level] <= idx + 2:
                if idx == int(self.state[level]):
                    if self._browsing_m2k:
                        self.current_address = val          # a mono2k sound id
                    else:
                        self.current_address = os.path.splitext(self.get_preset_path(val))[
                            0
                        ]
                show_text(
                    ctx,
                    level,
                    item_height * (idx - int(self.state[level])) + padding_top + 70,
                    Path(val).stem,
                    height=item_height,
                    font_color=text_color,
                    background_color=bg_color,
                    font_size_percentage=1,
                    center_vertically=True,
                    center_horizontally=True,
                    rectangle_padding=1,
                )
            elif isinstance(val, dict) and idx - 2 <= self.state[level] <= idx + 2:
                show_text(
                    ctx,
                    level,
                    item_height * (idx - int(self.state[level])) + padding_top + 70,
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
        return (chosen_folder or "") + "/" + preset

    def update_display(self, ctx, w, h):
        if self.browser_active and len(self.app.steps_held) != 0:
            self._browsing_m2k = self.m2k_instrument(self.get_current_instrument_short_name_helper()) is not None
            self.nested_draw(ctx, self.browser_tree(), level=0, max_height=h)
            show_text(
                ctx,
                0,
                15,
                "Save to Current",
                height=15,
                font_color=definitions.WHITE,
            )
            show_text(
                ctx,
                1,
                15,
                "Save to New",
                height=15,
                font_color=definitions.WHITE,
            )
            show_text(
                ctx,
                2,
                15,
                "Rename",
                height=15,
                font_color=definitions.WHITE,
            )
            # show_text(
            #     ctx,
            #     3,
            #     15,
            #     "Save Active to Current",
            #     height=15,
            #     font_color=definitions.WHITE,
            # )
            # show_text(
            #     ctx,
            #     4,
            #     15,
            #     "Save Active to New",
            #     height=15,
            #     font_color=definitions.WHITE,
            # )
            show_text(
                ctx,
                6,
                15,
                "Set All to Current",
                height=15,
                font_color=definitions.WHITE,
            )
            show_text(
                ctx,
                7,
                15,
                "Save All to New",
                height=15,
                font_color=definitions.WHITE,
            )
        else:
            for instrument_idx, instrument in enumerate(self.app.instruments):
                for index in range(8):
                    preset_name = [self.slot_label(instrument, index)]
                    
                    instrument_info = self.app.instrument_selection_mode.instruments_info[instrument_idx]
                    instrument_short_name = instrument_info["instrument_short_name"]
                    font_color = instrument_info["color"]
                    
                    if (
                        index == self.last_pad_in_column_pressed[instrument_short_name][0]
                        and instrument_idx == self.last_pad_in_column_pressed[instrument_short_name][1]
                    ):
                        font_color = definitions.WHITE
                    show_text(
                        ctx,
                        instrument_idx,
                        15 + 15*index,
                        f"{preset_name[-1]}",
                        height=15,
                        font_color=font_color,
                    )
                    
            
    def set_knob_postions(self):
        instrument_short_name = (
            self.app.instrument_selection_mode.get_current_instrument_short_name()
        )
        if self.m2k_instrument(instrument_short_name) is not None:
            # Open the browser on the slot's sound: walk its id down the tree
            sound_id = self.m2k_presets[instrument_short_name][self.current_slot(instrument_short_name)]
            for idx in range(len(self.state)):
                self.state[idx] = 0
            level = self.m2k_sounds.tree()
            for idx, piece in enumerate((sound_id or "").split("/")):
                if not isinstance(level, dict) or piece not in level or idx >= len(self.state):
                    break
                self.state[idx] = list(level).index(piece)
                level = level[piece]
            return
        preset_number = self.last_pad_in_column_pressed[instrument_short_name][0]
        preset_address = self._resolve_preset(self.presets[instrument_short_name][preset_number])

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
                if level is None:
                    break
                self.state[idx + 1] = list(level).index(piece)
                level = level[piece]  # who knows what this line does? But it works!
        except Exception as e:
            print(
                f"ERROR in preset_selection_mode set_knob_positions() at {preset_address}"
            )
            traceback.print_exc()

    def on_button_pressed(self, button_name):
        if button_name == push2_python.constants.BUTTON_SELECT:
            self.select_button_held = True
            return True

        elif button_name in [
            push2_python.constants.BUTTON_LEFT,
            push2_python.constants.BUTTON_RIGHT,
        ]:
            show_prev, show_next = self.has_prev_next_pages()
            if button_name == push2_python.constants.BUTTON_LEFT and show_prev:
                self.prev_page()
            elif button_name == push2_python.constants.BUTTON_RIGHT and show_next:
                self.next_page()
            return True
        # elif button_name in push2_python.constants.BUTTON_UPPER_ROW_6:
        #     self.save_all_presets_to_state()
        
        elif button_name == push2_python.constants.BUTTON_UPPER_ROW_1 and self.m2k_instrument(
            self.get_current_instrument_short_name_helper()
        ) is not None:
            # "Save to Current": the track's sound into its slot
            instrument = self.m2k_instrument(self.get_current_instrument_short_name_helper())
            self.save_m2k_slot(instrument)
            self.app.add_display_notification(f"{instrument.name}: saved to slot {self.current_slot(instrument.name) + 1}")
            return True

        elif button_name == push2_python.constants.BUTTON_UPPER_ROW_2 and self.m2k_instrument(
            self.get_current_instrument_short_name_helper()
        ) is not None:
            # "Save to New": the track's sound as a new user preset, and its slot named after it
            instrument = self.m2k_instrument(self.get_current_instrument_short_name_helper())
            sound = m2k_state.capture(instrument.osc["client"], self.m2k_sounds)
            if sound is not None and self.m2k_sounds.user_folder:
                sound_id = self.m2k_sounds.save_user(sound)
                slot = self.current_slot(instrument.name)
                self.m2k_presets[instrument.name][slot] = sound_id
                self.save_m2k_presets()
                self.save_m2k_slot(instrument, slot)
                self.app.add_display_notification(f"Saved {sound_id.split('/')[-1]}")
            return True

        elif button_name in push2_python.constants.BUTTON_UPPER_ROW_1:
            instrument_short_name = (
                self.app.instrument_selection_mode.get_current_instrument_short_name()
            )
            preset_number = self.last_pad_in_column_pressed[instrument_short_name][0]
            self.presets[instrument_short_name][preset_number] = self.current_address
            if len(self.app.steps_held) != 0:
                self.save_pad_to_state()
            # self.app.metro_sequencer_mode.save_state()
            
            
        elif button_name == push2_python.constants.BUTTON_UPPER_ROW_3:
            self.start_rename()
            return True

        elif button_name == push2_python.constants.BUTTON_UPPER_ROW_7 and self.m2k_instrument(
            self.get_current_instrument_short_name_helper()
        ) is not None:
            # Name the slot after the browsed sound (mono2k's own list, not Surge's)
            instrument_short_name = self.get_current_instrument_short_name_helper()
            if self.current_address:
                self.m2k_presets[instrument_short_name][self.current_slot(instrument_short_name)] = self.current_address
                self.save_m2k_presets()
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

    def on_button_released(self, button_name):
        if button_name == push2_python.constants.BUTTON_SELECT:
            self.select_button_held = False
            return True

    def on_encoder_rotated(self, encoder_name, increment):
        if self.browser_active:
            self._browsed = True
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

            current_dict = self.browser_tree()
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

    def get_instrument_color_helper(self, i):
        return self.app.instrument_selection_mode.get_instrument_color(i)