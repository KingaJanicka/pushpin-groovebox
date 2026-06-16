"""Tests for MetroSequencerMode - the metronome/global-timeline sequencer.

initialize() builds SequencerMetro objects against the global timeline, so it is
patched out; the global timeline is mocked to keep transport calls side-effect free.
"""

import pytest
from unittest.mock import MagicMock

from definitions import TRACK_NAMES_METRO
from modes.metro_sequencer_mode import (
    MetroSequencerMode,
    TRACK_COLORS,
    track_button_names,
)


@pytest.fixture
def metro(app, mocker):
    mocker.patch.object(MetroSequencerMode, "initialize")
    MetroSequencerMode.instrument_sequencers = {}
    MetroSequencerMode.selected_track = TRACK_NAMES_METRO[0]
    app.instrument_selection_mode.selected_instrument = 0
    mode = MetroSequencerMode(app, settings=None, send_osc_func=app.send_osc)
    mode.global_timeline = MagicMock()
    mode.instrument_sequencers = {"INST1": MagicMock()}
    return mode


def test_track_colors_cover_all_metro_tracks():
    assert set(TRACK_COLORS.keys()) == set(TRACK_NAMES_METRO)


def test_pad_ij_to_midi_note(metro):
    assert metro.pad_ij_to_midi_note((0, 0)) == 92
    assert metro.pad_ij_to_midi_note((7, 0)) == 36


def test_index_pad_roundtrip(metro):
    assert metro.index_to_pad_ij(0) == [7, 0]
    assert metro.ij_to_index(7, 0) == 0


def test_get_settings_to_save_is_empty(metro):
    assert metro.get_settings_to_save() == {}


def test_helpers_delegate(metro):
    assert metro.get_current_instrument_short_name_helper() == "INST1"
    assert metro.get_current_instrument_osc_port() == 7001


def test_start_stop_timeline_drive_global_timeline(metro):
    metro.start_timeline()
    metro.global_timeline.background.assert_called_once()
    metro.stop_timeline()
    metro.global_timeline.stop.assert_called_once()


def test_active_track_button_on_smoke(metro, push):
    metro.selected_track = TRACK_NAMES_METRO[0]
    metro.active_track_button_on()
    assert push.buttons.set_button_color.called


def test_new_instrument_selected_sets_default_track(metro):
    metro.new_instrument_selected()
    assert metro.selected_instrument == TRACK_NAMES_METRO[0]
