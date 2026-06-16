"""Tests for SettingsMode - paged performance/MIDI/about settings screen."""

import push2_python.constants

from modes.settings_mode import SettingsMode


ENCODER_NAMES = [
    push2_python.constants.ENCODER_TRACK1_ENCODER,
    push2_python.constants.ENCODER_TRACK2_ENCODER,
    push2_python.constants.ENCODER_TRACK3_ENCODER,
    push2_python.constants.ENCODER_TRACK4_ENCODER,
    push2_python.constants.ENCODER_TRACK5_ENCODER,
    push2_python.constants.ENCODER_TRACK6_ENCODER,
]


def make_mode(app, push):
    # initialize() iterates push.encoders.available_names, so it must be real.
    push.encoders.available_names = list(ENCODER_NAMES)
    return SettingsMode(app, settings=None)


def test_move_to_next_page_wraps_after_last(app, push):
    mode = make_mode(app, push)
    mode.current_page = 0
    assert mode.move_to_next_page() is False  # -> 1
    assert mode.current_page == 1
    assert mode.move_to_next_page() is False  # -> 2
    assert mode.current_page == 2
    assert mode.move_to_next_page() is True  # wraps -> 0
    assert mode.current_page == 0
    assert app.buttons_need_update is True


def test_initialize_seeds_encoder_state(app, push):
    mode = make_mode(app, push)
    for name in ENCODER_NAMES:
        assert name in mode.encoders_state
        assert "last_message_received" in mode.encoders_state[name]


def test_encoder_track1_sets_root_note_on_page_0(app, push):
    mode = make_mode(app, push)
    mode.current_page = 0
    app.melodic_mode.root_midi_note = 60
    assert (
        mode.on_encoder_rotated(push2_python.constants.ENCODER_TRACK1_ENCODER, 1)
        is True
    )
    app.melodic_mode.set_root_midi_note.assert_called_once_with(61)
    assert app.pads_need_update is True


def test_upper_row_2_toggles_aftertouch_mode_on_page_0(app, push):
    mode = make_mode(app, push)
    mode.current_page = 0
    app.melodic_mode.use_poly_at = False
    assert (
        mode.on_button_pressed(push2_python.constants.BUTTON_UPPER_ROW_2) is True
    )
    assert app.melodic_mode.use_poly_at is True
    app.push.pads.set_polyphonic_aftertouch.assert_called_once()


def test_update_buttons_smoke_all_pages(app, push):
    mode = make_mode(app, push)
    for page in (0, 1, 2):
        mode.current_page = page
        mode.update_buttons()  # should not raise
    assert push.buttons.set_button_color.called
