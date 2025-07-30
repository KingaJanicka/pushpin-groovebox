import definitions
import push2_python
import time
from controllers import push2_constants

TOGGLE_DISPLAY_BUTTON = push2_python.constants.BUTTON_USER
SETUP_BUTTON = push2_python.constants.BUTTON_SETUP
NOTE_BUTTON = push2_python.constants.BUTTON_NOTE
ADD_TRACK_BUTTON = push2_python.constants.BUTTON_ADD_TRACK
ADD_DEVICE_BUTTON = push2_python.constants.BUTTON_ADD_DEVICE
DEVICE_BUTTON = push2_python.constants.BUTTON_DEVICE
CLIP_BUTTON = push2_python.constants.BUTTON_CLIP
BROWSE_BUTTON = push2_python.constants.BUTTON_BROWSE
CONVERT_BUTTON = push2_python.constants.BUTTON_CONVERT
DOUBLE_LOOP_BUTTON = push2_python.constants.BUTTON_DOUBLE_LOOP
QUANTIZE_BUTTON = push2_python.constants.BUTTON_QUANTIZE
MUTE_BUTTON = push2_python.constants.BUTTON_MUTE


class MainControlsMode(definitions.PyshaMode):
    preset_selection_button_pressing_time = None
    button_quick_press_time = 0.400

    def activate(self):
        self.update_buttons()

    def deactivate(self):
        self.push.buttons.set_button_color(NOTE_BUTTON, definitions.BLACK)
        self.push.buttons.set_button_color(TOGGLE_DISPLAY_BUTTON, definitions.BLACK)
        self.push.buttons.set_button_color(SETUP_BUTTON, definitions.BLACK)
        self.push.buttons.set_button_color(ADD_TRACK_BUTTON, definitions.BLACK)
        self.push.buttons.set_button_color(ADD_DEVICE_BUTTON, definitions.BLACK)
        self.push.buttons.set_button_color(DEVICE_BUTTON, definitions.BLACK)
        self.push.buttons.set_button_color(CLIP_BUTTON, definitions.BLACK)

    def update_buttons(self):
        # Note button, to toggle melodic/rhythmic mode
        self.push.buttons.set_button_color(NOTE_BUTTON, definitions.WHITE)

        # Mute button, to toggle display on/off
        if self.app.use_push2_display:
            self.push.buttons.set_button_color(TOGGLE_DISPLAY_BUTTON, definitions.WHITE)
        else:
            self.push.buttons.set_button_color(
                TOGGLE_DISPLAY_BUTTON, definitions.OFF_BTN_COLOR
            )

        # Settings button, to toggle settings mode
        if self.app.is_mode_active(self.app.settings_mode):
            self.push.buttons.set_button_color(SETUP_BUTTON, definitions.BLACK)
            self.push.buttons.set_button_color(
                SETUP_BUTTON,
                definitions.WHITE,
                animation=definitions.DEFAULT_ANIMATION,
            )
        else:
            self.push.buttons.set_button_color(SETUP_BUTTON, definitions.OFF_BTN_COLOR)

        # Preset selection mode
        if self.app.is_mode_active(self.app.preset_selection_mode):
            self.push.buttons.set_button_color(BROWSE_BUTTON, definitions.BLACK)
            self.push.buttons.set_button_color(
                BROWSE_BUTTON,
                definitions.WHITE,
                animation=definitions.DEFAULT_ANIMATION,
            )
        else:
            self.push.buttons.set_button_color(BROWSE_BUTTON, definitions.OFF_BTN_COLOR)

        # Menu mode
        if self.app.menu_mode.should_be_enabled():
            if self.app.is_mode_active(self.app.menu_mode):
                self.push.buttons.set_button_color(ADD_DEVICE_BUTTON, definitions.BLACK)
                self.push.buttons.set_button_color(
                    ADD_DEVICE_BUTTON,
                    definitions.WHITE,
                    animation=definitions.DEFAULT_ANIMATION,
                )
            else:
                self.push.buttons.set_button_color(
                    ADD_DEVICE_BUTTON,
                    definitions.OFF_BTN_COLOR,
                    push2_constants.ANIMATION_STATIC,
                )
        else:
            self.push.buttons.set_button_color(ADD_DEVICE_BUTTON, definitions.BLACK)

    def on_button_pressed(self, button_name):
        if button_name == NOTE_BUTTON:
            self.app.toggle_melodic_rhythmic_slice_modes()
            self.app.pads_need_update = True
            self.app.buttons_need_update = True
            return True
        elif button_name == MUTE_BUTTON:
            if self.app.is_mode_active(self.app.mute_mode) != True:
                self.app.set_mute_mode()
            else:
                self.app.set_metro_sequencer_mode()
            
            self.app.pads_need_update = True
            self.app.buttons_need_update = True
            return True
        elif button_name == SETUP_BUTTON:
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
        elif button_name == BROWSE_BUTTON:
            if self.app.preset_selection_mode.should_be_enabled():
                self.app.toggle_preset_selection_mode()
                self.app.buttons_need_update = True
            return True
        elif button_name == ADD_DEVICE_BUTTON:
            if self.app.menu_mode.should_be_enabled():
                self.app.toggle_menu_mode()
                self.app.buttons_need_update = True
            return True
        elif button_name  == CLIP_BUTTON:
            if self.app.trig_edit_mode.should_be_enabled():
                # TODO: commented out beause it's broken with the current seq model
                # self.app.toggle_trig_edit_mode()
                self.app.buttons_need_update = True
            return True

    def on_button_released(self, button_name):
        if button_name == BROWSE_BUTTON:
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
