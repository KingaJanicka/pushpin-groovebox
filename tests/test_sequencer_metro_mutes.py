"""Sequencer track mutes in SequencerMetro.

A muted pitch, octave or velocity track holds that part of the note at the
last note played while the other parts keep following their tracks. A muted
lock-scale track holds the last p-lock scaling. A muted mutes/skips track
plays every step: no skips, 100% probability.
"""
from unittest.mock import MagicMock, patch

import pytest

from sequencer.sequencer_metro import SequencerMetro
from sequencer.sequencer_params import SequencerParams

PITCHES = [0, 3, 5, 7, 2, 4, 6, 1]
OCTAVES = [4, 5, 3, 6, 2, 4, 5, 3]
VELOCITIES = [0, 7, 3, 5, 1, 6, 2, 4]
LOCK_SCALES = [7, 0, 3, 5, 1, 6, 2, 4]


def amplitude(v):
    return (v + 1) * 16 - 1


@pytest.fixture
def seq(app):
    s = SequencerMetro.__new__(SequencerMetro)
    s.app = app
    s.name = "INST1"
    instrument = MagicMock()
    instrument.slots = []                      # no p-locks to send
    app.instruments = {"INST1": instrument}
    s.locks = [[[None] * 18 for _ in range(17)] for _ in range(64)]
    s.gate = ["On"] * 64
    s.velocity = VELOCITIES * 8
    s.lock_scale = LOCK_SCALES * 8
    s.mutes_skips = [False] * 64
    s.pitch = PITCHES * 8
    s.octave = OCTAVES * 8
    s.controls_to_reset = []
    s.next_step_index = 1
    s.timeline = MagicMock()
    s.params = SequencerParams(sequencer_is_playing=True)
    return s


def evaluate(seq, step, roll=1, **mutes):
    """Play ``step`` with the probability dice showing ``roll``; return the
    scheduled event, or None when no note was scheduled."""
    seq.params = SequencerParams(sequencer_is_playing=True, **mutes)
    seq.step_index, seq.next_step_index = step, step + 1
    seq.timeline.schedule.reset_mock()
    with patch("sequencer.sequencer_metro.random.randint", return_value=roll):
        seq.evaluate_and_play_notes()
    if not seq.timeline.schedule.called:
        return None
    return seq.timeline.schedule.call_args[0][0]


def play(seq, step, **mutes):
    return evaluate(seq, step, **mutes)["note"]


def test_unmuted_tracks_play_each_steps_pitch_and_octave(seq):
    for step in range(4):
        assert play(seq, step) == PITCHES[step] + OCTAVES[step] * 12


def test_muted_pitch_holds_pitch_but_octave_moves(seq):
    play(seq, 0)                                               # pitch 0, octave 4
    for step in (1, 2, 3):
        assert play(seq, step, pitch_track_active=False) == PITCHES[0] + OCTAVES[step] * 12


def test_muted_octave_holds_octave_but_pitch_moves(seq):
    play(seq, 1)                                               # pitch 3, octave 5
    for step in (2, 3, 4):
        assert play(seq, step, octave_track_active=False) == PITCHES[step] + OCTAVES[1] * 12


def test_both_muted_holds_the_whole_note(seq):
    play(seq, 2)
    for step in (3, 4, 5):
        assert play(seq, step, pitch_track_active=False, octave_track_active=False) == (
            PITCHES[2] + OCTAVES[2] * 12
        )


def test_hold_survives_and_unmute_follows_the_track_again(seq):
    play(seq, 0)
    play(seq, 1, pitch_track_active=False)                    # held pitch stays 0
    play(seq, 2, pitch_track_active=False)
    assert play(seq, 3, pitch_track_active=False) == PITCHES[0] + OCTAVES[3] * 12
    assert play(seq, 4) == PITCHES[4] + OCTAVES[4] * 12       # unmuted: back to the track


def test_mute_before_any_note_uses_the_steps_own_value(seq):
    assert play(seq, 3, pitch_track_active=False, octave_track_active=False) == (
        PITCHES[3] + OCTAVES[3] * 12
    )


# ------------------------------------------------------------------ velocity

def test_unmuted_velocity_follows_the_track(seq):
    for step in range(4):
        assert evaluate(seq, step)["amplitude"] == amplitude(VELOCITIES[step])


def test_muted_velocity_holds_the_last_notes_velocity(seq):
    evaluate(seq, 1)                                           # velocity 7
    for step in (2, 3, 4):
        event = evaluate(seq, step, velocity_track_active=False)
        assert event["amplitude"] == amplitude(VELOCITIES[1])
        assert event["note"] == PITCHES[step] + OCTAVES[step] * 12  # pitch/octave still move
    assert evaluate(seq, 5)["amplitude"] == amplitude(VELOCITIES[5])  # unmuted again


# --------------------------------------------------------------- mutes/skips

def set_probability(seq, column, row):
    """Light only probability row ``row`` (1-7) of ``column``."""
    for r in range(1, 8):
        seq.mutes_skips[column * 8 + r] = (r == row)


def test_probability_row_decides_whether_the_note_plays(seq):
    set_probability(seq, 0, 2)                                 # prob 1 of 6
    assert evaluate(seq, 0, roll=6) is None
    assert evaluate(seq, 0, roll=1) is not None


def test_muted_mutes_skips_always_plays(seq):
    set_probability(seq, 0, 1)                                 # prob 0: never plays
    assert evaluate(seq, 0, roll=1) is None
    for roll in range(1, 7):
        assert evaluate(seq, 0, roll=roll, mutes_skips_track_active=False) is not None


def test_skipped_column_is_jumped_over(seq):
    seq.mutes_skips[8] = True                                  # skip column 1 (steps 8-15)
    seq.params = SequencerParams(sequencer_is_playing=True)
    seq.app.pads_need_update = False
    seq.step_index = 7
    seq.increment_index()
    assert seq.step_index == 16


def test_muted_mutes_skips_plays_skipped_columns(seq):
    seq.mutes_skips[8] = True
    seq.params = SequencerParams(sequencer_is_playing=True, mutes_skips_track_active=False)
    seq.step_index = 7
    seq.increment_index()
    assert seq.step_index == 8
    seq.increment_next_step_index(index=7)
    assert seq.next_step_index == 8
    seq.increment_previous_step_index(index=9)
    assert seq.prev_step_index == 8


# ---------------------------------------------------------------- lock scale

def lock_scale(seq, step, **mutes):
    seq.step_index = step
    return seq.lock_scale_for_step(SequencerParams(**mutes))


def test_unmuted_lock_scale_follows_the_track(seq):
    assert lock_scale(seq, 0) == 1.0                           # 7 / 7
    assert lock_scale(seq, 1) == 0                             # 0
    assert lock_scale(seq, 2) == pytest.approx(3 / 7)


def test_muted_lock_scale_holds_the_last_scaling(seq):
    lock_scale(seq, 2)                                         # 3 / 7
    for step in (3, 4, 5):
        assert lock_scale(seq, step, lock_scale_track_active=False) == pytest.approx(3 / 7)
    assert lock_scale(seq, 6) == pytest.approx(2 / 7)          # unmuted again


def test_lock_scale_muted_before_any_step_uses_the_steps_own_value(seq):
    assert lock_scale(seq, 3, lock_scale_track_active=False) == pytest.approx(5 / 7)
