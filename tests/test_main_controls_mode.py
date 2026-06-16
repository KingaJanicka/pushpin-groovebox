"""Tests for MainControlsMode - the top-row transport/navigation buttons."""

import push2_python.constants

from modes.main_controls_mode import MainControlsMode


def make_mode(app):
    return MainControlsMode(app, settings=None)


def test_note_button_toggles_layout(app):
    mode = make_mode(app)
    assert mode.on_button_pressed(push2_python.constants.BUTTON_NOTE) is True
    app.toggle_melodic_rhythmic_slice_modes.assert_called_once()
    assert app.pads_need_update is True
    assert app.buttons_need_update is True


def test_setup_button_toggles_settings(app):
    mode = make_mode(app)
    assert mode.on_button_pressed(push2_python.constants.BUTTON_SETUP) is True
    app.toggle_and_rotate_settings_mode.assert_called_once()


def test_mute_button_enters_mute_mode_when_inactive(app):
    app.is_mode_active.return_value = False
    mode = make_mode(app)
    assert mode.on_button_pressed(push2_python.constants.BUTTON_MUTE) is True
    app.set_mute_mode.assert_called_once()


def test_toggle_display_button_flips_flag(app):
    app.use_push2_display = True
    mode = make_mode(app)
    assert mode.on_button_pressed(push2_python.constants.BUTTON_USER) is True
    assert app.use_push2_display is False


def test_update_buttons_smoke(app, push):
    app.is_mode_active.return_value = False
    app.use_push2_display = True
    app.menu_mode.should_be_enabled.return_value = True
    mode = make_mode(app)
    mode.update_buttons()
    assert push.buttons.set_button_color.called
