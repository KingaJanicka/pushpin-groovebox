import definitions
import push2_python
import os
import json

from user_interface.display_utils import show_text


class InstrumentSelectionMode(definitions.PyshaMode):

    instruments_info = []
    instrument_button_names_a = [
        push2_python.constants.BUTTON_LOWER_ROW_1,
        push2_python.constants.BUTTON_LOWER_ROW_2,
        push2_python.constants.BUTTON_LOWER_ROW_3,
        push2_python.constants.BUTTON_LOWER_ROW_4,
        push2_python.constants.BUTTON_LOWER_ROW_5,
        push2_python.constants.BUTTON_LOWER_ROW_6,
        push2_python.constants.BUTTON_LOWER_ROW_7,
        push2_python.constants.BUTTON_LOWER_ROW_8,
    ]

    selected_instrument = 0
    instrument_selection_quick_press_time = 0.400

    def initialize(self, settings=None):
        # if settings is not None:
        #   self.pyramidi_channel = settings.get(
        #         "pyramidi_channel", self.pyramidi_channel
        #   )

        self.create_instruments()

    def create_instruments(self):
        tmp_instruments_data = {}

        if os.path.exists(definitions.INSTRUMENT_LISTING_PATH):
            track_instruments = json.load(open(definitions.INSTRUMENT_LISTING_PATH))
            for i, instrument_short_name in enumerate(track_instruments):
                if instrument_short_name not in tmp_instruments_data:
                    try:
                        instrument_data = json.load(
                            open(
                                os.path.join(
                                    definitions.INSTRUMENT_DEFINITION_FOLDER,
                                    "{}.json".format(instrument_short_name),
                                )
                            )
                        )
                        tmp_instruments_data[instrument_short_name] = instrument_data
                    except FileNotFoundError:
                        # No definition file for instrument exists
                        instrument_data = {}
                else:
                    instrument_data = tmp_instruments_data[instrument_short_name]
                color = instrument_data.get("color", None)
                if color is None:
                    if instrument_short_name != "-":
                        color = definitions.COLORS_NAMES[i % 8]
                    else:
                        color = definitions.GRAY_DARK
                self.instruments_info.append(
                    {
                        "instrument_name": "{0}{1}".format(
                            (i % 16) + 1, ["A", "B", "C", "D"][i // 16]
                        ),
                        "instrument_name": instrument_data.get("instrument_name", "-"),
                        "instrument_short_name": instrument_short_name,
                        "midi_channel": instrument_data.get("midi_channel", -1),
                        "osc_in_port": instrument_data.get("osc_in_port", 0),
                        "osc_out_port": instrument_data.get("osc_out_port", 0),
                        "color": color,
                        "n_banks": instrument_data.get("n_banks", 1),
                        "bank_names": instrument_data.get("bank_names", None),
                        "default_layout": instrument_data.get(
                            "default_layout", definitions.LAYOUT_SEQUENCER
                        ),
                        "illuminate_local_notes": instrument_data.get(
                            "illuminate_local_notes", True
                        ),
                    }
                )
            print("Created {0} instruments!".format(len(self.instruments_info)))

    def get_settings_to_save(self):
        return {}

    def get_all_distinct_instrument_short_names(self):
        distinct = list(
            set(
                [
                    instrument["instrument_short_name"]
                    for instrument in self.instruments_info
                ]
            )
        )

        # Ensure instrument short names are in order
        distinct.sort()

        return distinct

    def get_current_instrument_info(self):
        return self.instruments_info[self.selected_instrument]

    def get_current_instrument_osc_out_port(self):
        return self.get_current_instrument_info()["osc_out_port"]

    def get_current_instrument_osc_in_port(self):
        return self.get_current_instrument_info()["osc_in_port"]

    def get_current_instrument_short_name(self):
        return self.get_current_instrument_info()["instrument_short_name"]

    def get_instrument_color(self, i):
        return self.instruments_info[i]["color"]

    def get_current_instrument_color(self):
        return self.get_instrument_color(self.selected_instrument)

    def get_current_instrument_color_rgb(self):
        return definitions.get_color_rgb_float(self.get_current_instrument_color())

    def load_current_default_layout(self):
        if (
            self.get_current_instrument_info()["default_layout"]
            == definitions.LAYOUT_MELODIC
        ):
            self.app.set_melodic_mode()
        elif (
            self.get_current_instrument_info()["default_layout"]
            == definitions.LAYOUT_RHYTHMIC
        ):
            self.app.set_rhythmic_mode()
        elif (
            self.get_current_instrument_info()["default_layout"]
            == definitions.LAYOUT_SLICES
        ):
            self.app.set_slice_notes_mode()
        # elif (
        #     self.get_current_instrument_info()["default_layout"]
        #     == definitions.LAYOUT_SEQUENCER
        # ):
        #     self.app.set_sequencer_mode()

    def clean_currently_notes_being_played(self):
        if self.app.is_mode_active(self.app.melodic_mode):
            self.app.melodic_mode.remove_all_notes_being_played()
        elif self.app.is_mode_active(self.app.rhythmic_mode):
            self.app.rhythmic_mode.remove_all_notes_being_played()
        # elif self.app.is_mode_active(self.app.sequencer_mode):
        #     self.app.sequencer_mode.update_pads()

    def select_instrument(self, instrument_idx):
        # Selects a instrument and activates its melodic/rhythmic layout
        # Note that if this is called from a mode form the same xor group with melodic/rhythmic modes,
        # that other mode will be deactivated.
        self.selected_instrument = instrument_idx
        # self.load_current_default_layout()
        # Commented out so that mode stays the same as intruments switch
        self.clean_currently_notes_being_played()

        try:
            # self.app.midi_cc_mode.new_instrument_selected()
            self.app.osc_mode.new_instrument_selected()
            self.app.preset_selection_mode.new_instrument_selected()
            # self.app.sequencer_mode.new_instrument_selected()
            self.app.trig_edit_mode.new_instrument_selected()
        except AttributeError as e:
            print("ATTRIBUTE ERROR", e)
            # Might fail if MIDICCMode/PresetSelectionMode/PyramidTrackTriggeringMode not initialized
            pass

    def activate(self):
        self.update_buttons()
        self.update_pads()

    def deactivate(self):
        for button_name in self.instrument_button_names_a:
            self.push.buttons.set_button_color(button_name, definitions.BLACK)

    def update_buttons(self):
        for count, name in enumerate(self.instrument_button_names_a):
            color = self.instruments_info[count]["color"]
            self.push.buttons.set_button_color(name, color)

        # for count, name in enumerate(self.instrument_button_names_b):
        #     color = self.get_current_instrument_color()
        #     equivalent_instrument_num = (self.selected_instrument % 8) + count * 8
        #     if self.selected_instrument == equivalent_instrument_num:
        #         self.push.buttons.set_button_color(name, definitions.WHITE)
        #         self.push.buttons.set_button_color(
        #             name, color, animation=definitions.DEFAULT_ANIMATION
        #         )
        #     else:
        #         self.push.buttons.set_button_color(name, color)

    def update_display(self, ctx, w, h):

        # Draw instrument selector labels
        height = 20
        for i in range(0, 8):
            instrument_color = self.instruments_info[i]["color"]
            volume = self.app.volumes[i*2]
            volume_parsed = int(volume*100)
            if self.selected_instrument % 8 == i:
                background_color = instrument_color
                font_color = definitions.BLACK
            else:
                background_color = definitions.BLACK
                font_color = instrument_color
            instrument_short_name = f'{self.instruments_info[i]["instrument_short_name"]}    {volume_parsed}'

            show_text(
                ctx,
                i,
                h - height,
                instrument_short_name,
                height=height,
                font_color=font_color,
                background_color=background_color,
            )

    def on_button_pressed(self, button_name):
        if button_name in self.instrument_button_names_a:
            self.select_instrument(self.instrument_button_names_a.index(button_name))
            self.app.buttons_need_update = True
            self.app.pads_need_update = True
            return True

    def on_button_released(self, button_name):
        return True
