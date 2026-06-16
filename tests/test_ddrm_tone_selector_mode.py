"""Tests for DDRMToneSelectorMode - tone bank selection for the DDRM synth."""

import push2_python.constants

from modes.ddrm_tone_selector_mode import (
    DDRMToneSelectorMode,
    tone_selector_values,
    NAME_STRING_1,
)


def make_mode(app):
    mode = DDRMToneSelectorMode(app, settings=None)
    # Avoid the inter-message sleeps during tests.
    mode.inter_message_message_min_time_ms = 0
    mode.page_n = 0
    return mode


def test_should_be_enabled_only_for_ddrm(app):
    mode = make_mode(app)
    app.instrument_selection_mode.get_current_instrument_short_name.return_value = "X"
    assert mode.should_be_enabled() is False
    app.instrument_selection_mode.get_current_instrument_short_name.return_value = (
        "DDRM"
    )
    assert mode.should_be_enabled() is True


def test_get_should_show_next_prev(app):
    mode = make_mode(app)
    mode.page_n = 0
    assert mode.get_should_show_next_prev() == (False, True)
    mode.page_n = 1
    assert mode.get_should_show_next_prev() == (True, False)


def test_send_upper_row_sends_one_cc_per_param(app):
    mode = make_mode(app)
    mode.send_messages_double = False
    mode.upper_row_selected = NAME_STRING_1
    mode.send_upper_row()
    assert app.send_midi.call_count == len(tone_selector_values[NAME_STRING_1])


def test_send_upper_row_double_sends_two_per_param(app):
    mode = make_mode(app)
    mode.send_messages_double = True
    mode.upper_row_selected = NAME_STRING_1
    mode.send_upper_row()
    assert app.send_midi.call_count == 2 * len(tone_selector_values[NAME_STRING_1])


def test_send_lower_row_noop_for_unknown_selection(app):
    mode = make_mode(app)
    mode.lower_row_selected = "not-a-real-tone"
    mode.send_lower_row()
    app.send_midi.assert_not_called()


def test_upper_row_button_selects_and_sends(app):
    mode = make_mode(app)
    mode.page_n = 0
    result = mode.on_button_pressed(push2_python.constants.BUTTON_UPPER_ROW_1)
    assert result is True
    # First upper-row name is a String tone; selection should be recorded and sent.
    assert mode.upper_row_selected == mode.upper_row_names[0]
    assert app.send_midi.called


def test_page_buttons_toggle_page(app):
    mode = make_mode(app)
    mode.page_n = 0
    assert mode.on_button_pressed(push2_python.constants.BUTTON_PAGE_RIGHT) is True
    assert mode.page_n == 1
    assert mode.on_button_pressed(push2_python.constants.BUTTON_PAGE_LEFT) is True
    assert mode.page_n == 0


def test_update_buttons_smoke(app, push):
    mode = make_mode(app)
    mode.update_buttons()
    assert push.buttons.set_button_color.called
