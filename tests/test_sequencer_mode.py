"""Tests for SequencerMode - step sequencer grid + transport.

initialize() builds isobar Sequencer objects, so it is patched out and a mock
sequencer is injected. The class-level real isobar Timeline means transport
methods are patched in the PLAY test to avoid spawning background threads.
"""

import pytest
from unittest.mock import MagicMock
from controllers import push2_constants

from definitions import TRACK_NAMES
from modes.sequencer_mode import SequencerMode, TRACK_COLORS, track_button_names


@pytest.fixture
def seq(app, mocker):
    mocker.patch.object(SequencerMode, "initialize")
    SequencerMode.instrument_sequencers = {}
    SequencerMode.instrument_scale_edit_controls = {}
    SequencerMode.selected_track = "gate_1"
    SequencerMode.timeline_is_playing = False
    app.steps_held = []
    app.instrument_selection_mode.selected_instrument = 0
    mode = SequencerMode(app, settings=None, send_osc_func=app.send_osc)
    mode.instrument_sequencers = {"INST1": MagicMock()}
    return mode


def test_track_colors_cover_all_track_names():
    assert set(TRACK_COLORS.keys()) == set(TRACK_NAMES)


def test_pad_ij_to_midi_note():
    mode = SequencerMode.__new__(SequencerMode)
    assert mode.pad_ij_to_midi_note((0, 0)) == 92
    assert mode.pad_ij_to_midi_note((7, 7)) == 43


def test_get_settings_to_save_is_empty(seq):
    assert seq.get_settings_to_save() == {}


def test_helpers_delegate(seq):
    assert seq.get_current_instrument_short_name_helper() == "INST1"
    assert seq.get_current_instrument_osc_port() == 7001


def test_track_button_selects_track(seq, app):
    seq.on_button_pressed(track_button_names[1])
    assert seq.selected_track == TRACK_NAMES[1]
    app.trig_edit_mode.update_state.assert_called_once()
    assert app.pads_need_update is True


def test_play_button_toggles_timeline(seq, mocker):
    start = mocker.patch.object(seq, "start_timeline")
    stop = mocker.patch.object(seq, "stop_timeline")
    seq.timeline_is_playing = False

    seq.on_button_pressed(push2_constants.BUTTON_PLAY)
    start.assert_called_once()
    assert seq.timeline_is_playing is True

    seq.on_button_pressed(push2_constants.BUTTON_PLAY)
    stop.assert_called_once()
    assert seq.timeline_is_playing is False


def test_scale_button_toggles_scale_menu(seq):
    seq.show_scale_menu = False
    seq.on_button_pressed(push2_constants.BUTTON_SCALE)
    assert seq.show_scale_menu is True
    assert seq.disable_controls is True


def test_new_instrument_selected_sets_default_track(seq, app):
    seq.new_instrument_selected()
    assert seq.selected_instrument == TRACK_NAMES[0]
