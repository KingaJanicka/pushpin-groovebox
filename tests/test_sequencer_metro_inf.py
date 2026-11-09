"""INF on the SCALE page's Seq Steps / Main Steps.

Normally the track jumps back to its first step every Seq Steps steps, and the
main pattern resets every track every Main Steps steps. INF turns that reset
off, so the sequence keeps running forward through all its steps.
"""
from unittest.mock import MagicMock

import pytest

from sequencer.sequencer_metro import SequencerMetro
from sequencer.sequencer_params import INF_STEPS, SequencerParams


@pytest.fixture
def seq(app):
    s = SequencerMetro.__new__(SequencerMetro)
    s.app = app
    s.gate = ["On"] * 64
    s.mutes_skips = [False] * 64
    s.step_index = 0
    s.next_step_index = 1
    s.main_ticks_to_reset = 0
    s.seq_ticks_to_reset = 0
    s.evaluate_and_play_notes = MagicMock()
    s.step_is_skipped = lambda idx: False
    return s


def run(seq, ticks, **params):
    """Tick ``ticks`` times; return the step played on each tick (None = none)."""
    seq.params = SequencerParams(sequencer_is_playing=True, **params)
    played = []
    for _ in range(ticks):
        seq.evaluate_and_play_notes.reset_mock()
        seq.advance_and_evaluate_main_tick()
        seq.advance_and_evaluate_sequencer_tick()
        played.append(seq.step_index if seq.evaluate_and_play_notes.called else None)
    return played


def test_finite_seq_steps_loop_back_to_the_first_step(seq):
    played = run(seq, 8, pattern_len=4, main_pattern_len=64)
    assert played == [0, 1, 2, 3, 0, 1, 2, 3]


def test_inf_seq_steps_never_reset_the_track(seq):
    played = run(seq, 70, pattern_len=INF_STEPS, main_pattern_len=INF_STEPS)
    # Runs through all 64 steps, then carries on round (no reset in between)
    assert played == [i % 64 for i in range(70)]


def test_inf_seq_steps_keep_the_time_scale(seq):
    played = run(seq, 8, seq_time_scale=2, pattern_len=INF_STEPS,
                 main_pattern_len=INF_STEPS)
    assert played == [0, None, 1, None, 2, None, 3, None]


def test_finite_main_steps_reset_an_inf_track(seq):
    played = run(seq, 8, pattern_len=INF_STEPS, main_pattern_len=3)
    assert played == [0, 1, 2, 0, 1, 2, 0, 1]


def test_inf_main_steps_never_reset_the_track(seq):
    # Track still loops on its own Seq Steps; the main pattern leaves it alone
    played = run(seq, 10, pattern_len=4, main_pattern_len=INF_STEPS)
    assert played == [0, 1, 2, 3, 0, 1, 2, 3, 0, 1]
    # A 3-step main pattern would have cut that loop short
    seq.step_index = 0
    seq.main_ticks_to_reset = seq.seq_ticks_to_reset = 0
    assert run(seq, 6, pattern_len=4, main_pattern_len=3) == [0, 1, 2, 0, 1, 2]


def test_inf_skips_ungated_steps(seq):
    seq.gate = [False] * 64
    for i in (0, 5, 9):
        seq.gate[i] = "On"
    played = run(seq, 5, pattern_len=INF_STEPS, main_pattern_len=INF_STEPS)
    assert played == [0, 5, 9, 0, 5]


def test_switching_from_inf_back_to_finite_loops_again(seq):
    run(seq, 10, pattern_len=INF_STEPS, main_pattern_len=INF_STEPS)
    played = run(seq, 8, pattern_len=4, main_pattern_len=INF_STEPS)
    assert 0 in played and max(p for p in played if p is not None) < 14
