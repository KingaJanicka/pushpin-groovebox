"""Tests for MetroSequencerMode - the metronome/global-timeline sequencer.

initialize() builds SequencerMetro objects against the global timeline, so it is
patched out; the global timeline is mocked to keep transport calls side-effect free.
"""

import pytest
from unittest.mock import MagicMock, patch

from definitions import TRACK_NAMES_METRO
from modes.metro_sequencer_mode import (
    MetroSequencerMode,
    TRACK_COLORS,
    track_button_names,
    _make_track_controls,
    _SCALE_ITEMS,
    _STEP_ITEMS,
)


@pytest.fixture
def metro(app, mocker):
    mocker.patch.object(MetroSequencerMode, "initialize")
    app.instrument_selection_mode.selected_instrument = 0
    mode = MetroSequencerMode(app, settings=None, send_osc_func=app.send_osc)
    # Set the instance attributes that initialize() would normally populate.
    mode.global_timeline = MagicMock()
    mode.instrument_sequencers = {"INST1": MagicMock()}
    mode.selected_track = TRACK_NAMES_METRO[0]
    mode.metro_seq_pad_state = {}
    mode.instrument_scale_edit_controls = {}
    mode.rachets = {}
    mode.pads_press_time = [False] * 64
    mode.steps_held = []
    mode.show_scale_menu = False
    mode.sequencer_is_playing = False
    mode.draw_pads = True
    mode.disable_controls = False
    mode.playhead = 0
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


# ---------------------------------------------------------------------------
# _SCALE_ITEMS / _STEP_ITEMS — module-level data extracted from initialize()
# ---------------------------------------------------------------------------

def test_scale_items_count_and_range():
    assert len(_SCALE_ITEMS) == 32
    values = [item["onselect"]["value"] for item in _SCALE_ITEMS]
    assert values == list(range(1, 33))
    assert _SCALE_ITEMS[0]["label"] == "1/32"
    assert _SCALE_ITEMS[-1]["label"] == "32/32"


def test_step_items_count_and_range():
    assert len(_STEP_ITEMS) == 63
    # First chunk: 2/32 .. 32/32 (31 items)
    assert _STEP_ITEMS[0]["label"] == "2/32"
    assert _STEP_ITEMS[0]["onselect"]["value"] == 2
    assert _STEP_ITEMS[30]["label"] == "32/32"
    assert _STEP_ITEMS[30]["onselect"]["value"] == 32
    # Second chunk: 1+1/32 .. 1+32/32 (32 items)
    assert _STEP_ITEMS[31]["label"] == "1+1/32"
    assert _STEP_ITEMS[31]["onselect"]["value"] == 33
    assert _STEP_ITEMS[-1]["label"] == "1+32/32"
    assert _STEP_ITEMS[-1]["onselect"]["value"] == 64


# ---------------------------------------------------------------------------
# _make_track_controls() — builds the 8-control list for one instrument
# ---------------------------------------------------------------------------

def test_make_track_controls_returns_eight_controls():
    color_func = MagicMock(return_value="cyan")
    controls = _make_track_controls(color_func)
    assert len(controls) == 8


def test_make_track_controls_default_values():
    from osc_controls import OSCControl, ControlSpacer, OSCControlMenu
    color_func = MagicMock(return_value="cyan")
    controls = _make_track_controls(color_func)
    assert isinstance(controls[0], OSCControl), "index 0 should be Gate Len"
    assert isinstance(controls[1], ControlSpacer)
    assert isinstance(controls[2], ControlSpacer)
    assert isinstance(controls[3], ControlSpacer)
    assert isinstance(controls[4], OSCControlMenu), "index 4 should be Seq Time Scale"
    assert isinstance(controls[5], OSCControlMenu), "index 5 should be Seq Steps"
    assert isinstance(controls[6], OSCControlMenu), "index 6 should be Main Time Scale"
    assert isinstance(controls[7], OSCControlMenu), "index 7 should be Main Steps"
    # Verify the pre-set defaults match what sequencer_metro relies on.
    assert controls[6].value == 2, "Main Time Scale default should be 2"
    assert controls[7].value == 64, "Main Steps default should be 64"


def test_make_track_controls_menu_labels():
    color_func = MagicMock(return_value="cyan")
    controls = _make_track_controls(color_func)
    assert controls[4].menu_label == "Seq Time Scale"
    assert controls[5].menu_label == "Seq Steps"
    assert controls[6].menu_label == "Main Time Scale"
    assert controls[7].menu_label == "Main Steps"


# ---------------------------------------------------------------------------
# _default_pad_state() — static helper
# ---------------------------------------------------------------------------

def test_default_pad_state_shape():
    state = MetroSequencerMode._default_pad_state()
    assert len(state) == 8, "should have 8 rows"
    assert all(len(row) == 8 for row in state), "each row should have 8 columns"


def test_default_pad_state_bottom_row_active():
    state = MetroSequencerMode._default_pad_state()
    assert all(v is True for v in state[7]), "bottom row should be all True"
    assert all(v is False for row in state[:7] for v in row), "top 7 rows should be all False"


def test_default_pad_state_returns_independent_lists():
    a = MetroSequencerMode._default_pad_state()
    b = MetroSequencerMode._default_pad_state()
    a[0][0] = True
    assert b[0][0] is False, "each call should return a new independent grid"


# ---------------------------------------------------------------------------
# _init_instrument() — per-instrument state initialisation
# ---------------------------------------------------------------------------

@pytest.fixture
def metro_for_init(app, mocker):
    """A MetroSequencerMode instance wired for _init_instrument() tests."""
    mocker.patch.object(MetroSequencerMode, "initialize")
    mode = MetroSequencerMode(app, settings=None, send_osc_func=app.send_osc)
    mode.instrument_sequencers = {}
    mode.metro_seq_pad_state = {}
    mode.instrument_scale_edit_controls = {}
    mode.rachets = {}
    mode.playhead = 0
    mode.global_timeline = MagicMock()
    # Patch SequencerMetro so _init_instrument doesn't need real MIDI hardware.
    mocker.patch("modes.metro_sequencer_mode.SequencerMetro")
    return mode


def test_init_instrument_creates_sequencer(metro_for_init, app):
    from modes.metro_sequencer_mode import SequencerMetro
    metro_for_init._init_instrument("INST1")
    SequencerMetro.assert_called_once_with(
        app.instruments["INST1"],
        metro_for_init.sequencer_on_tick,
        metro_for_init.playhead,
        metro_for_init.send_osc_func,
        metro_for_init.global_timeline,
        app,
    )
    assert "INST1" in metro_for_init.instrument_sequencers


def test_init_instrument_creates_pad_state_for_all_tracks(metro_for_init):
    metro_for_init._init_instrument("INST1")
    pad_state = metro_for_init.metro_seq_pad_state["INST1"]
    assert set(pad_state.keys()) == set(TRACK_NAMES_METRO)
    for track_name, grid in pad_state.items():
        assert len(grid) == 8, f"{track_name}: should have 8 rows"
        assert all(len(row) == 8 for row in grid), f"{track_name}: each row should have 8 columns"


def test_init_instrument_pad_state_bottom_row_active(metro_for_init):
    metro_for_init._init_instrument("INST1")
    for track_name in TRACK_NAMES_METRO:
        grid = metro_for_init.metro_seq_pad_state["INST1"][track_name]
        assert all(v is True for v in grid[7]), \
            f"{track_name}: bottom row should start active"


def test_init_instrument_creates_scale_edit_controls(metro_for_init):
    metro_for_init._init_instrument("INST1")
    controls = metro_for_init.instrument_scale_edit_controls["INST1"]
    assert len(controls) == 8


def test_init_instrument_creates_rachets(metro_for_init):
    metro_for_init._init_instrument("INST1")
    rachets = metro_for_init.rachets["INST1"]
    assert len(rachets) == 64
    assert all(v is False for v in rachets)


def test_init_instrument_independent_pad_states(metro_for_init):
    metro_for_init._init_instrument("INST1")
    metro_for_init._init_instrument("INST2")
    grid1 = metro_for_init.metro_seq_pad_state["INST1"][TRACK_NAMES_METRO[0]]
    grid2 = metro_for_init.metro_seq_pad_state["INST2"][TRACK_NAMES_METRO[0]]
    grid1[0][0] = "modified"
    assert grid2[0][0] is False, "instruments should have independent pad state grids"
