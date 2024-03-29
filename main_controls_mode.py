import definitions
import push2_python
import time

TOGGLE_DISPLAY_BUTTON = push2_python.constants.BUTTON_USER
SETTINGS_BUTTON = push2_python.constants.BUTTON_SETUP
MELODIC_RHYTHMIC_TOGGLE_BUTTON = push2_python.constants.BUTTON_NOTE
PYRAMID_TRACK_TRIGGERING_BUTTON = push2_python.constants.BUTTON_ADD_TRACK
PRESET_SELECTION_MODE_BUTTON = push2_python.constants.BUTTON_ADD_DEVICE
DDRM_TONE_SELECTION_MODE_BUTTON = push2_python.constants.BUTTON_DEVICE
CLIP_BUTTON = push2_python.constants.BUTTON_CLIP


class MainControlsMode(definitions.PyshaMode):
    preset_selection_button_pressing_time = None
    button_quick_press_time = 0.400

    def activate(self):
        self.update_buttons()

    def deactivate(self):
        self.push.buttons.set_button_color(
            MELODIC_RHYTHMIC_TOGGLE_BUTTON, definitions.BLACK
        )
        self.push.buttons.set_button_color(TOGGLE_DISPLAY_BUTTON, definitions.BLACK)
        self.push.buttons.set_button_color(SETTINGS_BUTTON, definitions.BLACK)
        self.push.buttons.set_button_color(
            PYRAMID_TRACK_TRIGGERING_BUTTON, definitions.BLACK
        )
        self.push.buttons.set_button_color(
            PRESET_SELECTION_MODE_BUTTON, definitions.BLACK
        )
        self.push.buttons.set_button_color(
            DDRM_TONE_SELECTION_MODE_BUTTON, definitions.BLACK
        )
        self.push.buttons.set_button_color(CLIP_BUTTON, definitions.BLACK)

    def update_buttons(self):
        # Note button, to toggle melodic/rhythmic mode
        self.push.buttons.set_button_color(
            MELODIC_RHYTHMIC_TOGGLE_BUTTON, definitions.WHITE
        )

        # Mute button, to toggle display on/off
        if self.app.use_push2_display:
            self.push.buttons.set_button_color(TOGGLE_DISPLAY_BUTTON, definitions.WHITE)
        else:
            self.push.buttons.set_button_color(
                TOGGLE_DISPLAY_BUTTON, definitions.OFF_BTN_COLOR
            )

        # Settings button, to toggle settings mode
        if self.app.is_mode_active(self.app.settings_mode):
            self.push.buttons.set_button_color(SETTINGS_BUTTON, definitions.BLACK)
            self.push.buttons.set_button_color(
                SETTINGS_BUTTON,
                definitions.WHITE,
                animation=definitions.DEFAULT_ANIMATION,
            )
        else:
            self.push.buttons.set_button_color(
                SETTINGS_BUTTON, definitions.OFF_BTN_COLOR
            )

        # Preset selection mode
        if self.app.is_mode_active(self.app.preset_selection_mode):
            self.push.buttons.set_button_color(
                PRESET_SELECTION_MODE_BUTTON, definitions.BLACK
            )
            self.push.buttons.set_button_color(
                PRESET_SELECTION_MODE_BUTTON,
                definitions.WHITE,
                animation=definitions.DEFAULT_ANIMATION,
            )
        else:
            self.push.buttons.set_button_color(
                PRESET_SELECTION_MODE_BUTTON, definitions.OFF_BTN_COLOR
            )

        # DDRM tone selector mode
        if self.app.ddrm_tone_selector_mode.should_be_enabled():
            if self.app.is_mode_active(self.app.ddrm_tone_selector_mode):
                self.push.buttons.set_button_color(
                    DDRM_TONE_SELECTION_MODE_BUTTON, definitions.BLACK
                )
                self.push.buttons.set_button_color(
                    DDRM_TONE_SELECTION_MODE_BUTTON,
                    definitions.WHITE,
                    animation=definitions.DEFAULT_ANIMATION,
                )
            else:
                self.push.buttons.set_button_color(
                    DDRM_TONE_SELECTION_MODE_BUTTON, definitions.OFF_BTN_COLOR
                )
        else:
            self.push.buttons.set_button_color(
                DDRM_TONE_SELECTION_MODE_BUTTON, definitions.BLACK
            )

    def on_button_pressed(self, button_name):
        if button_name == MELODIC_RHYTHMIC_TOGGLE_BUTTON:
            self.app.toggle_melodic_rhythmic_slice_modes()
            self.app.pads_need_update = True
            self.app.buttons_need_update = True
            return True
        elif button_name == SETTINGS_BUTTON:
            self.app.toggle_and_rotate_settings_mode()
            self.app.buttons_need_update = True
            return True
        elif button_name == TOGGLE_DISPLAY_BUTTON:
            self.app.use_push2_display = not self.app.use_push2_display
            if not self.app.use_push2_display:
                self.push.display.send_to_display(
                    self.push.display.prepare_frame(
                        self.push.display.make_black_frame()
                    )
                )
            self.app.buttons_need_update = True
            return True
        elif button_name == PRESET_SELECTION_MODE_BUTTON:
            if self.app.is_mode_active(self.app.preset_selection_mode):
                # If already active, deactivate and set pressing time to None
                self.app.unset_preset_selection_mode()
                self.preset_selection_button_pressing_time = None
            else:
                # Activate preset selection mode and store time button pressed
                self.app.set_preset_selection_mode()
                self.preset_selection_button_pressing_time = time.time()
            self.app.buttons_need_update = True
            return True
        elif button_name == DDRM_TONE_SELECTION_MODE_BUTTON:
            if self.app.ddrm_tone_selector_mode.should_be_enabled():
                self.app.toggle_ddrm_tone_selector_mode()
                self.app.buttons_need_update = True
            return True

    def on_button_released(self, button_name):
        if button_name == PRESET_SELECTION_MODE_BUTTON:
            # Decide if short press or long press
            pressing_time = self.preset_selection_button_pressing_time
            is_long_press = False
            if pressing_time is None:
                # Consider quick press (this should not happen pressing time should have been set before)
                pass
            else:
                if time.time() - pressing_time > self.button_quick_press_time:
                    # Consider this is a long press
                    is_long_press = True
                self.preset_selection_button_pressing_time = None

            if is_long_press:
                # If long press, deactivate preset selection mode, else do nothing
                self.app.unset_preset_selection_mode()
                self.app.buttons_need_update = True

            return True
