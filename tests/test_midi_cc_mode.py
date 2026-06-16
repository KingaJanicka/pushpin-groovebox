"""Tests for MIDICCMode and MIDICCControl.

Instruments without a definition file fall back to 128 generated CC controls,
which is what the fixture instruments do - no real files are read/written.
"""

import pytest
from unittest.mock import MagicMock
import push2_python.constants

from modes.midi_cc_mode import MIDICCMode, MIDICCControl


# --------------------------------------------------------------------------- #
# MIDICCControl
# --------------------------------------------------------------------------- #


def test_cc_control_update_value_clamps_and_sends():
    send = MagicMock()
    control = MIDICCControl(10, "Cutoff", "Filter", get_color_func=MagicMock(), send_midi_func=send)
    control.value = 64

    control.update_value(10)
    assert control.value == 74
    msg = send.call_args[0][0]
    assert msg.type == "control_change"
    assert msg.control == 10
    assert msg.value == 74

    control.update_value(1000)
    assert control.value == 127  # clamped at vmax
    control.update_value(-1000)
    assert control.value == 0  # clamped at vmin


# --------------------------------------------------------------------------- #
# MIDICCMode
# --------------------------------------------------------------------------- #


@pytest.fixture
def midicc(app):
    MIDICCMode.instrument_midi_control_ccs = {}
    MIDICCMode.current_selected_section_and_page = {}
    MIDICCMode.active_midi_control_ccs = []
    return MIDICCMode(app, settings=None)


def test_initialize_creates_default_cc_banks(midicc):
    # Two fixture instruments, each with the 128 default CC controls.
    assert set(midicc.instrument_midi_control_ccs.keys()) == {"INST1", "INST2"}
    assert len(midicc.instrument_midi_control_ccs["INST1"]) == 128


def test_default_sections_are_16_wide(midicc):
    sections = midicc.get_current_instrument_midi_cc_sections()
    # 128 CCs in groups of 16 -> 8 sections.
    assert len(sections) == 8
    assert sections[0] == "0 to 15"


def test_initial_section_and_page(midicc):
    assert midicc.get_currently_selected_midi_cc_section_and_page() == ("0 to 15", 0)


def test_controls_for_section_and_page_returns_eight(midicc):
    page = midicc.get_midi_cc_controls_for_current_instrument_section_and_page()
    assert len(page) == 8


def test_show_next_prev_for_first_page(midicc):
    show_prev, show_next = midicc.get_should_show_midi_cc_next_prev_pages_for_section()
    assert show_prev is False
    assert show_next is True  # 16 controls in the section, 8 per page


def test_page_right_advances_page(midicc, app):
    assert (
        midicc.on_button_pressed(push2_python.constants.BUTTON_PAGE_RIGHT) is True
    )
    _, page = midicc.get_currently_selected_midi_cc_section_and_page()
    assert page == 1
    assert app.buttons_need_update is True


def test_encoder_rotate_updates_active_control(midicc, app):
    midicc.new_instrument_selected()  # populate active_midi_control_ccs
    midicc.active_midi_control_ccs[0].value = 64
    midicc.on_encoder_rotated(push2_python.constants.ENCODER_TRACK1_ENCODER, 5)
    assert midicc.active_midi_control_ccs[0].value == 69
    assert app.send_midi.called
