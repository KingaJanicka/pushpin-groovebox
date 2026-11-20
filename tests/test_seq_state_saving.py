"""Saving and loading sequences (per clip) and the SCALE page (global).

Each test runs in its own temp dir: the state files are relative paths.
"""
import json
from unittest.mock import MagicMock

import push2_python.constants
import pytest

from definitions import TRACK_NAMES_METRO
from modes.clip_selection_mode import ClipSelectionMode
from modes.metro_sequencer_mode import (
    SCALE_AUTOSAVE_SECONDS,
    MetroSequencerMode,
    _make_track_controls,
)
from osc_controls import ControlSpacer
import sequencer.sequencer_metro as sequencer_metro
from sequencer.sequencer_metro import SequencerMetro


def empty_state():
    return {
        "locks": [[None] * 4 for _ in range(64)],
        "note": [None] * 64,
        "pitch": [False] * 64,
        "octave": [4] * 64,
        "velocity": [False] * 64,
        "gate": [False] * 64,
        "mutes_skips": [False] * 64,
        "lock_scale": [7] * 64,
        "aux_3": [False] * 64,
        "aux_4": [False] * 64,
    }


@pytest.fixture(autouse=True)
def in_tmp_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sequencer_metro._init_state_cache.clear()
    with open(sequencer_metro.INIT_STATE_FILENAME, "w") as f:
        json.dump(empty_state(), f)
    yield tmp_path
    sequencer_metro._init_state_cache.clear()


def make_seq(app, name="INST1"):
    s = SequencerMetro.__new__(SequencerMetro)
    s.app = app
    s.name = name
    s.load_state()  # no clip file: the init state
    return s


# ---------------------------------------------------------------------------
# SequencerMetro: one track's clip files
# ---------------------------------------------------------------------------

def test_round_trip_keeps_every_track_including_velocity(app):
    seq = make_seq(app)
    seq.pitch = list(range(64))
    seq.velocity = [v % 8 for v in range(64)]
    seq.gate = [True] * 64
    seq.aux_2 = ["a"] * 64
    seq.save_state(clip=3)

    other = make_seq(app)
    other.load_state(clip=3)
    assert other.get_state() == seq.get_state()
    assert other.velocity == [v % 8 for v in range(64)]


def test_loading_a_clip_replaces_the_previous_clips_velocity(app):
    seq = make_seq(app)
    seq.velocity = [5] * 64
    seq.save_state(clip=1)
    seq.velocity = [2] * 64
    seq.save_state(clip=2)

    seq.load_state(clip=1)
    assert seq.velocity == [5] * 64


def test_clip_without_file_loads_the_init_state(app):
    seq = make_seq(app)
    seq.velocity = [6] * 64
    seq.load_state(clip=7)
    assert seq.get_state() == empty_state()
    assert seq.velocity == [False] * 64


def test_empty_clip_without_file_is_not_written(app, in_tmp_dir):
    seq = make_seq(app)
    seq.save_state(clip=4)
    assert not (in_tmp_dir / seq.get_state_filename(4)).exists()


def test_emptied_clip_with_a_file_is_written(app, in_tmp_dir):
    seq = make_seq(app)
    seq.gate = [True] * 64
    seq.save_state(clip=4)
    seq.gate = [False] * 64           # cleared by hand: that's the clip now
    seq.save_state(clip=4)
    with open(in_tmp_dir / seq.get_state_filename(4)) as f:
        assert json.load(f)["gate"] == [False] * 64


def test_delete_removes_the_file_and_empties_the_sequence(app, in_tmp_dir):
    seq = make_seq(app)
    seq.gate = [True] * 64
    seq.save_state(clip=2)

    seq.delete_state(clip=2)
    assert not (in_tmp_dir / seq.get_state_filename(2)).exists()
    assert seq.gate == [False] * 64
    seq.save_state(clip=2)            # switching away doesn't bring it back
    assert not (in_tmp_dir / seq.get_state_filename(2)).exists()


def test_delete_of_a_clip_without_file_does_not_raise(app):
    make_seq(app).delete_state(clip=6)


# ---------------------------------------------------------------------------
# MetroSequencerMode: SCALE page and saving every track
# ---------------------------------------------------------------------------

@pytest.fixture
def metro(app, mocker):
    mocker.patch.object(MetroSequencerMode, "initialize")
    mode = MetroSequencerMode(app, settings=None, send_osc_func=app.send_osc)
    mode.instrument_scale_edit_controls = {
        name: _make_track_controls(lambda: "cyan") for name in ("INST1", "INST2")
    }
    mode.instrument_sequencers = {"INST1": MagicMock(), "INST2": MagicMock()}
    app.clip_selection_mode.last_pad_in_column_pressed = {"INST1": (0, 0), "INST2": (0, 1)}
    return mode


def set_scale(controls, gate, seq_scale, seq_steps, main_scale, main_steps):
    for idx, value in zip((0, 4, 5, 6, 7), (gate, seq_scale, seq_steps, main_scale, main_steps)):
        controls[idx].value = value


def scale_values(controls):
    return [None if isinstance(c, ControlSpacer) else c.value for c in controls]


def test_scale_page_saves_every_track_with_spacers_as_none(metro, in_tmp_dir):
    set_scale(metro.instrument_scale_edit_controls["INST1"], 0.5, 3, 14, 4, 30)
    set_scale(metro.instrument_scale_edit_controls["INST2"], 0.25, 1, 6, 2, 62)
    metro.save_scale_state()

    with open(in_tmp_dir / metro.scale_menu_filename) as f:
        saved = json.load(f)
    assert saved == {
        "INST1": [0.5, None, None, None, 3, 14, 4, 30],
        "INST2": [0.25, None, None, None, 1, 6, 2, 62],
    }


def test_scale_page_round_trip(metro, app, mocker):
    set_scale(metro.instrument_scale_edit_controls["INST1"], 0.5, 3, 14, 4, 30)
    set_scale(metro.instrument_scale_edit_controls["INST2"], 0.25, 1, 6, 2, 62)
    metro.save_scale_state()

    fresh = MetroSequencerMode(app, settings=None, send_osc_func=app.send_osc)
    fresh.instrument_scale_edit_controls = {
        name: _make_track_controls(lambda: "cyan") for name in ("INST1", "INST2")
    }
    fresh.load_scale_state()
    for name in ("INST1", "INST2"):
        assert scale_values(fresh.instrument_scale_edit_controls[name]) == scale_values(
            metro.instrument_scale_edit_controls[name]
        )


def test_track_missing_from_file_keeps_defaults_and_others_still_load(metro, in_tmp_dir):
    with open(in_tmp_dir / metro.scale_menu_filename, "w") as f:
        json.dump({"INST2": [0.75, None, None, None, 5, 9, 6, 20]}, f)
    metro.load_scale_state()

    assert scale_values(metro.instrument_scale_edit_controls["INST2"]) == [
        0.75, None, None, None, 5, 9, 6, 20]
    assert scale_values(metro.instrument_scale_edit_controls["INST1"]) == scale_values(
        _make_track_controls(lambda: "cyan"))


def test_old_file_with_values_in_spacer_slots_still_loads(metro, in_tmp_dir):
    with open(in_tmp_dir / metro.scale_menu_filename, "w") as f:
        json.dump({"INST1": [0.3, 2, 2, 1.8, 3.1, 6.2, 3.1, 6.2]}, f)
    metro.load_scale_state()
    controls = metro.instrument_scale_edit_controls["INST1"]
    assert scale_values(controls) == [0.3, None, None, None, 3.1, 6.2, 3.1, 6.2]
    assert not hasattr(controls[1], "value")


def test_missing_or_corrupt_file_leaves_defaults(metro, in_tmp_dir):
    defaults = scale_values(metro.instrument_scale_edit_controls["INST1"])
    metro.load_scale_state()                          # no file
    (in_tmp_dir / metro.scale_menu_filename).write_text("{not json")
    metro.load_scale_state()
    assert scale_values(metro.instrument_scale_edit_controls["INST1"]) == defaults


def test_autosave_only_when_changed_and_at_most_every_interval(metro, in_tmp_dir):
    path = in_tmp_dir / metro.scale_menu_filename
    metro.autosave_scale_state(now=100.0)
    assert not path.exists()                          # nothing changed

    metro.scale_state_dirty = True
    metro.autosave_scale_state(now=100.0)
    assert path.exists() and metro.scale_state_dirty is False

    metro.instrument_scale_edit_controls["INST1"][5].value = 20
    metro.scale_state_dirty = True
    metro.autosave_scale_state(now=100.0 + SCALE_AUTOSAVE_SECONDS / 2)
    assert json.loads(path.read_text())["INST1"][5] != 20   # too soon
    metro.autosave_scale_state(now=100.0 + SCALE_AUTOSAVE_SECONDS)
    assert json.loads(path.read_text())["INST1"][5] == 20


def test_turning_a_scale_encoder_marks_the_page_for_saving(metro, app):
    app.steps_held = []
    metro.steps_held = []
    metro.encoder_incr_since_held = [False] * 8
    metro.show_scale_menu = True
    metro.on_encoder_rotated(push2_python.constants.ENCODER_TRACK5_ENCODER, 10)
    assert metro.scale_state_dirty is True


def test_save_sequences_saves_each_track_into_the_clip_its_on(metro, app):
    app.clip_selection_mode.last_pad_in_column_pressed = {"INST1": (3, 0), "INST2": (5, 1)}
    metro.save_sequences()
    metro.instrument_sequencers["INST1"].save_state.assert_called_once_with(clip=3)
    metro.instrument_sequencers["INST2"].save_state.assert_called_once_with(clip=5)


def test_load_state_loads_each_track_from_its_clip(metro, app):
    app.clip_selection_mode.last_pad_in_column_pressed = {"INST1": (2, 0), "INST2": (0, 1)}
    metro.load_state()
    metro.instrument_sequencers["INST1"].load_state.assert_called_once_with(clip=2)
    metro.instrument_sequencers["INST2"].load_state.assert_called_once_with(clip=0)


def test_save_state_saves_sequences_and_scale_page(metro, in_tmp_dir):
    metro.save_state()
    metro.instrument_sequencers["INST1"].save_state.assert_called_once_with(clip=0)
    assert (in_tmp_dir / metro.scale_menu_filename).exists()


# ---------------------------------------------------------------------------
# ClipSelectionMode: switching clips
# ---------------------------------------------------------------------------

@pytest.fixture
def clips(app, mocker):
    mocker.patch.object(ClipSelectionMode, "initialize")
    mode = ClipSelectionMode(app, settings=None)
    mode.last_pad_in_column_pressed = {"INST1": (0, 0), "INST2": (0, 1)}
    mode.clips = [[False] * 8 for _ in range(8)]
    app.instrument_selection_mode.instruments_info = [
        {"instrument_short_name": f"INST{j + 1}", "color": "cyan"} for j in range(8)
    ]
    for j in range(2, 8):
        mode.last_pad_in_column_pressed[f"INST{j + 1}"] = (0, j)
    app.metro_sequencer_mode.instrument_sequencers = {"INST1": MagicMock(), "INST2": MagicMock()}
    return mode


def test_switching_clip_saves_the_one_being_left_then_loads_the_new_one(clips, app):
    seq = app.metro_sequencer_mode.instrument_sequencers["INST1"]
    order = MagicMock()
    seq.save_state.side_effect = lambda clip: order("save", clip)
    seq.load_state.side_effect = lambda clip: order("load", clip)

    clips.on_pad_pressed(0, (4, 0), 127)

    assert [c.args for c in order.call_args_list] == [("save", 0), ("load", 4)]
    assert clips.last_pad_in_column_pressed["INST1"] == (4, 0)
    app.metro_sequencer_mode.instrument_sequencers["INST2"].save_state.assert_not_called()


def test_opening_the_clip_page_saves_every_track_first(clips, app, mocker):
    order = MagicMock()
    app.metro_sequencer_mode.save_sequences.side_effect = lambda: order("save")
    mocker.patch.object(ClipSelectionMode, "list_clips", lambda self: order("list"))
    clips.activate()
    assert [c.args for c in order.call_args_list] == [("save",), ("list",)]
