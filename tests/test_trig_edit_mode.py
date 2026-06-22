"""Tests for TrigEditMode - per-step trig parameter editing.

controls and state are class-level on TrigEditMode and initialize() appends to
them, so both are reset before each construction to keep tests independent.
"""

import pytest

from definitions import TRACK_NAMES_METRO
from modes.trig_edit_mode import TrigEditMode


@pytest.fixture
def trig(app):
    TrigEditMode.controls = []
    TrigEditMode.state = {}
    app.metro_sequencer_mode.selected_track = TRACK_NAMES_METRO[0]
    mode = TrigEditMode(app, settings=None)
    return mode


def test_initialize_builds_eight_controls(trig):
    assert len(trig.controls) == 8


def test_initialize_seeds_state_per_instrument_and_track(trig):
    assert set(trig.state.keys()) == {"INST1", "INST2"}
    for instrument in ("INST1", "INST2"):
        for track in TRACK_NAMES_METRO:
            # 8 control values + a trailing recurrence byte (255).
            assert len(trig.state[instrument][track]) == 9


def test_should_be_enabled(trig):
    assert trig.should_be_enabled() is True


def test_get_current_page_defaults_to_zero(trig):
    assert trig.get_current_page() == 0


def test_helpers_delegate_to_app(trig, app):
    assert trig.get_current_instrument_short_name_helper() == "INST1"
    assert trig.get_all_distinct_instrument_short_names_helper() == ["INST1", "INST2"]


def test_update_state_loads_control_values_from_state(trig):
    # The 8th control (recurrence) initialises to 8 in the seeded state.
    trig.controls[7].value = 0  # perturb
    trig.update_state()
    assert trig.controls[7].value == 8


def test_new_instrument_selected_resets_page_and_flags(trig, app):
    trig.current_page = 3
    trig.new_instrument_selected()
    assert trig.current_page == 0
    assert app.pads_need_update is True
    assert app.buttons_need_update is True
