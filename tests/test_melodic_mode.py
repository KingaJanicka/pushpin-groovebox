"""Tests for MelodicMode and its subclasses (RhythmicMode, SliceNotesMode).

These modes carry most of the note-grid logic in the app, so they're the
highest-value target for coverage. The hardware (`self.push`) and the host app
are provided as mocks by the `app`/`push` fixtures in conftest.py.
"""

import pytest
import push2_python.constants

import definitions
from modes.melodic_mode import MelodicMode
from modes.rhythmic_mode import RhythmicMode
from modes.slice_notes_mode import SliceNotesMode


@pytest.fixture
def melodic(app):
    mode = MelodicMode(app, settings=None, send_osc_func=app.send_osc)
    # MelodicMode keeps notes_being_played at class scope; isolate per-test.
    mode.remove_all_notes_being_played()
    mode.set_root_midi_note(0)
    return mode


# --------------------------------------------------------------------------- #
# Pad <-> MIDI note mapping
# --------------------------------------------------------------------------- #


def test_pad_ij_to_midi_note_uses_root_and_layout(melodic):
    melodic.set_root_midi_note(0)
    # Bottom-left pad (row 7, col 0) maps to the root note.
    assert melodic.pad_ij_to_midi_note((7, 0)) == 0
    # Each column adds 1 semitone, each row up adds 5.
    assert melodic.pad_ij_to_midi_note((7, 1)) == 1
    assert melodic.pad_ij_to_midi_note((6, 0)) == 5
    assert melodic.pad_ij_to_midi_note((0, 7)) == 7 * 5 + 7


def test_pad_ij_to_midi_note_shifts_with_root(melodic):
    melodic.set_root_midi_note(60)
    assert melodic.pad_ij_to_midi_note((7, 0)) == 60


# --------------------------------------------------------------------------- #
# Note naming and scale helpers
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "note_number,expected",
    [
        (0, "C-2"),
        (60, "C3"),
        (61, "C#3"),
        (69, "A3"),
    ],
)
def test_note_number_to_name(melodic, note_number, expected):
    assert melodic.note_number_to_name(note_number) == expected


def test_is_midi_note_root_octave(melodic):
    melodic.set_root_midi_note(0)
    assert melodic.is_midi_note_root_octave(0) is True
    assert melodic.is_midi_note_root_octave(12) is True
    assert melodic.is_midi_note_root_octave(7) is False


def test_is_black_key_midi_note(melodic):
    melodic.set_root_midi_note(0)
    # With root C, the scale_pattern marks C, D, E, F, G, A, B as white keys.
    assert melodic.is_black_key_midi_note(0) is False  # C
    assert melodic.is_black_key_midi_note(1) is True  # C#
    assert melodic.is_black_key_midi_note(3) is True  # D#


# --------------------------------------------------------------------------- #
# Root-note clamping
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "value,expected",
    [(-5, 0), (0, 0), (64, 64), (127, 127), (200, 127)],
)
def test_set_root_midi_note_clamps(melodic, value, expected):
    melodic.set_root_midi_note(value)
    assert melodic.root_midi_note == expected


# --------------------------------------------------------------------------- #
# Notes-being-played bookkeeping
# --------------------------------------------------------------------------- #


def test_add_and_remove_note_being_played(melodic):
    melodic.add_note_being_played(60, "push")
    assert melodic.is_midi_note_being_played(60) is True

    # A different source for the same note is tracked separately.
    melodic.add_note_being_played(60, "midi")
    melodic.remove_note_being_played(60, "push")
    assert melodic.is_midi_note_being_played(60) is True  # still held by "midi"

    melodic.remove_note_being_played(60, "midi")
    assert melodic.is_midi_note_being_played(60) is False


def test_remove_all_notes_being_played(melodic):
    melodic.add_note_being_played(60, "push")
    melodic.add_note_being_played(64, "push")
    melodic.remove_all_notes_being_played()
    assert melodic.notes_being_played == []


# --------------------------------------------------------------------------- #
# Aftertouch / poly-AT parameter clamping
# --------------------------------------------------------------------------- #


def test_set_channel_at_range_start_clamps(melodic):
    melodic.channel_at_range_end = 800
    melodic.set_channel_at_range_start(100)
    assert melodic.channel_at_range_start == 401
    melodic.set_channel_at_range_start(5000)
    assert melodic.channel_at_range_start == 799
    melodic.set_channel_at_range_start(500)
    assert melodic.channel_at_range_start == 500


def test_set_channel_at_range_end_clamps(melodic):
    melodic.channel_at_range_start = 401
    melodic.set_channel_at_range_end(100)
    assert melodic.channel_at_range_end == 402
    melodic.set_channel_at_range_end(9999)
    assert melodic.channel_at_range_end == 2000


def test_set_poly_at_max_range_clamps(melodic):
    melodic.set_poly_at_max_range(-1)
    assert melodic.poly_at_max_range == 0
    melodic.set_poly_at_max_range(200)
    assert melodic.poly_at_max_range == 127


def test_set_poly_at_curve_bending_clamps(melodic):
    melodic.set_poly_at_curve_bending(-1)
    assert melodic.poly_at_curve_bending == 0
    melodic.set_poly_at_curve_bending(500)
    assert melodic.poly_at_curve_bending == 100


def test_get_poly_at_curve_returns_128_values(melodic):
    curve = melodic.get_poly_at_curve()
    assert len(curve) == 128
    assert all(isinstance(v, int) for v in curve)


# --------------------------------------------------------------------------- #
# Settings round-trip
# --------------------------------------------------------------------------- #


def test_settings_round_trip(app):
    settings = {
        "use_poly_at": False,
        "root_midi_note": 50,
        "channel_at_range_start": 410,
        "channel_at_range_end": 900,
        "poly_at_max_range": 30,
        "poly_at_curve_bending": 70,
    }
    mode = MelodicMode(app, settings=settings, send_osc_func=app.send_osc)
    saved = mode.get_settings_to_save()
    assert saved == settings


# --------------------------------------------------------------------------- #
# MIDI input updates the note list and flags a pad refresh
# --------------------------------------------------------------------------- #


def test_on_midi_in_note_on_off(melodic, app):
    note_on = type("Msg", (), {"type": "note_on", "note": 60, "velocity": 100})()
    melodic.on_midi_in(note_on, source="ext")
    assert melodic.is_midi_note_being_played(60) is True
    assert app.pads_need_update is True

    note_off = type("Msg", (), {"type": "note_off", "note": 60, "velocity": 0})()
    melodic.on_midi_in(note_off, source="ext")
    assert melodic.is_midi_note_being_played(60) is False


def test_on_midi_in_note_on_zero_velocity_is_note_off(melodic):
    melodic.add_note_being_played(60, "ext")
    zero_vel = type("Msg", (), {"type": "note_on", "note": 60, "velocity": 0})()
    melodic.on_midi_in(zero_vel, source="ext")
    assert melodic.is_midi_note_being_played(60) is False


# --------------------------------------------------------------------------- #
# Pad press/release drive MIDI + OSC out
# --------------------------------------------------------------------------- #


def test_on_pad_pressed_sends_midi_and_osc(melodic, app):
    result = melodic.on_pad_pressed(pad_n=0, pad_ij=(7, 0), velocity=100)
    assert result is True
    assert app.send_midi.called
    # OSC note message is sent with the instrument short name as the third arg.
    app.send_osc.assert_any_call("/mnote", [0.0, 100.0], "INST1")


def test_on_pad_released_sends_note_off(melodic, app):
    result = melodic.on_pad_released(pad_n=0, pad_ij=(7, 0), velocity=0)
    assert result is True
    app.send_osc.assert_any_call("/mnote/rel", [0.0, 0.0], "INST1")


def test_fixed_velocity_mode_forces_velocity_127(melodic, app):
    melodic.fixed_velocity_mode = True
    melodic.on_pad_pressed(pad_n=0, pad_ij=(7, 0), velocity=10)
    sent = app.send_midi.call_args[0][0]
    assert sent.velocity == 127


# --------------------------------------------------------------------------- #
# Buttons: octave shift, accent, touchstrip mode, transport
# --------------------------------------------------------------------------- #


def test_octave_up_down_buttons(melodic, app):
    melodic.set_root_midi_note(60)
    assert melodic.on_button_pressed(push2_python.constants.BUTTON_OCTAVE_UP) is True
    assert melodic.root_midi_note == 72
    assert app.pads_need_update is True

    assert melodic.on_button_pressed(push2_python.constants.BUTTON_OCTAVE_DOWN) is True
    assert melodic.root_midi_note == 60


def test_accent_button_toggles_fixed_velocity(melodic):
    before = melodic.fixed_velocity_mode
    melodic.on_button_pressed(push2_python.constants.BUTTON_ACCENT)
    assert melodic.fixed_velocity_mode is (not before)


def test_play_button_starts_and_stops_transport(melodic, app):
    app.metro_sequencer_mode.sequencer_is_playing = False
    melodic.on_button_pressed(push2_python.constants.BUTTON_PLAY)
    assert app.metro_sequencer_mode.start_timeline.called
    assert app.metro_sequencer_mode.sequencer_is_playing is True

    melodic.on_button_pressed(push2_python.constants.BUTTON_PLAY)
    assert app.metro_sequencer_mode.stop_timeline.called
    assert app.metro_sequencer_mode.sequencer_is_playing is False


# --------------------------------------------------------------------------- #
# Touchstrip + sustain pedal
# --------------------------------------------------------------------------- #


def test_on_touchstrip_pitch_bend(melodic, app):
    assert melodic.on_touchstrip(8000) is True
    sent = app.send_midi.call_args[0][0]
    assert sent.type == "pitchwheel"


def test_on_touchstrip_modulation_wheel(melodic, app):
    melodic.modulation_wheel_mode = True
    assert melodic.on_touchstrip(64) is True
    sent = app.send_midi.call_args[0][0]
    assert sent.type == "control_change"
    assert sent.control == 1


def test_on_sustain_pedal(melodic, app):
    assert melodic.on_sustain_pedal(True) is True
    sent = app.send_midi.call_args[0][0]
    assert sent.type == "control_change"
    assert sent.control == 64
    assert sent.value == 127


# --------------------------------------------------------------------------- #
# update_pads pushes a color matrix to the hardware
# --------------------------------------------------------------------------- #


def test_update_pads_sends_8x8_matrix(melodic, push):
    melodic.update_pads()
    push.pads.set_pads_color.assert_called_once()
    matrix = push.pads.set_pads_color.call_args[0][0]
    assert len(matrix) == 8
    assert all(len(row) == 8 for row in matrix)


# --------------------------------------------------------------------------- #
# RhythmicMode overrides the pad layout
# --------------------------------------------------------------------------- #


@pytest.fixture
def rhythmic(app):
    mode = RhythmicMode(app, settings=None, send_osc_func=app.send_osc)
    mode.remove_all_notes_being_played()
    return mode


def test_rhythmic_pad_layout(rhythmic):
    assert rhythmic.pad_ij_to_midi_note((0, 0)) == 64
    assert rhythmic.pad_ij_to_midi_note((7, 0)) == 36
    assert rhythmic.pad_ij_to_midi_note((7, 7)) == 71


def test_rhythmic_ignores_octave_buttons(rhythmic):
    # Octave buttons are a no-op in rhythmic mode (should not raise).
    assert rhythmic.on_button_pressed(push2_python.constants.BUTTON_OCTAVE_UP) is None


def test_rhythmic_update_pads(rhythmic, push):
    rhythmic.update_pads()
    push.pads.set_pads_color.assert_called_once()


# --------------------------------------------------------------------------- #
# SliceNotesMode
# --------------------------------------------------------------------------- #


@pytest.fixture
def slices(app):
    mode = SliceNotesMode(app, settings=None, send_osc_func=app.send_osc)
    mode.remove_all_notes_being_played()
    mode.start_note = 0
    return mode


def test_slice_pad_layout(slices):
    slices.start_note = 0
    assert slices.pad_ij_to_midi_note((7, 0)) == 0
    assert slices.pad_ij_to_midi_note((7, 1)) == 1
    assert slices.pad_ij_to_midi_note((6, 0)) == 8


def test_slice_octave_up_advances_start_note_and_clamps(slices, app):
    slices.start_note = 0
    slices.on_button_pressed(push2_python.constants.BUTTON_OCTAVE_UP)
    assert slices.start_note == 16
    # Repeatedly pressing up clamps at the configured maximum.
    for _ in range(20):
        slices.on_button_pressed(push2_python.constants.BUTTON_OCTAVE_UP)
    assert slices.start_note == 128 - 16 * 4


def test_slice_octave_down_clamps_at_zero(slices):
    slices.start_note = 0
    slices.on_button_pressed(push2_python.constants.BUTTON_OCTAVE_DOWN)
    assert slices.start_note == 0
