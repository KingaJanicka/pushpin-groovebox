"""Tests for MuteMode - per-track mute grid for the sequencer."""

import pytest
import push2_python.constants

from definitions import TRACK_NAMES_METRO
from modes.mute_mode import MuteMode, track_button_names


@pytest.fixture
def mute(app):
    # tracks_active is class-level state; reset it so tests are independent.
    MuteMode.tracks_active = {}
    mode = MuteMode(app, settings=None)
    return mode


def test_initialize_marks_all_tracks_active(mute):
    # Two instruments come from the fixture's get_all_distinct... mock.
    assert set(mute.tracks_active.keys()) == {"INST1", "INST2"}
    for instrument in ("INST1", "INST2"):
        for track in TRACK_NAMES_METRO:
            assert mute.tracks_active[instrument][track] is True


def test_pad_layout_maps_to_sequencer_matrix(mute):
    assert mute.pad_ij_to_midi_note((0, 0)) == 92
    assert mute.pad_ij_to_midi_note((0, 7)) == 99
    assert mute.pad_ij_to_midi_note((7, 0)) == 36


def test_on_pad_pressed_toggles_track_mute(mute, app):
    # pad_ij is (track_index, instrument_index); (0, 0) -> INST1 / first track.
    assert mute.tracks_active["INST1"][TRACK_NAMES_METRO[0]] is True
    mute.on_pad_pressed(0, (0, 0), 100)
    assert mute.tracks_active["INST1"][TRACK_NAMES_METRO[0]] is False
    assert app.pads_need_update is True

    mute.on_pad_pressed(0, (0, 0), 100)
    assert mute.tracks_active["INST1"][TRACK_NAMES_METRO[0]] is True


def test_track_button_selects_metro_track(mute, app):
    mute.on_button_pressed(track_button_names[0])
    assert app.metro_sequencer_mode.selected_track == TRACK_NAMES_METRO[0]
    app.trig_edit_mode.update_state.assert_called_once()
    app.set_metro_sequencer_mode.assert_called_once()


def test_play_button_toggles_transport(mute, app):
    app.metro_sequencer_mode.sequencer_is_playing = False
    mute.on_button_pressed(push2_python.constants.BUTTON_PLAY)
    app.metro_sequencer_mode.start_timeline.assert_called_once()
    assert app.metro_sequencer_mode.sequencer_is_playing is True
