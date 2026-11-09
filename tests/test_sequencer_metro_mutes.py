"""Pitch / octave track mutes in SequencerMetro.evaluate_and_play_notes.

A muted pitch track holds the note's pitch at the last note played while the
octave keeps following its track; a muted octave track does the reverse.
"""
from unittest.mock import MagicMock, patch

import pytest

from sequencer.sequencer_metro import SequencerMetro
from sequencer.sequencer_params import SequencerParams

PITCHES = [0, 3, 5, 7, 2, 4, 6, 1]
OCTAVES = [4, 5, 3, 6, 2, 4, 5, 3]


@pytest.fixture
def seq(app):
    s = SequencerMetro.__new__(SequencerMetro)
    s.app = app
    s.name = "INST1"
    instrument = MagicMock()
    instrument.slots = []                      # no p-locks to send
    app.instruments = {"INST1": instrument}
    s.locks = [[[None] * 18 for _ in range(17)] for _ in range(64)]
    s.lock_scale = [0] * 64
    s.gate = ["On"] * 64
    s.velocity = [1] * 64
    s.mutes_skips = [False] * 64
    s.pitch = PITCHES * 8
    s.octave = OCTAVES * 8
    s.controls_to_reset = []
    s.next_step_index = 1
    s.timeline = MagicMock()
    s.params = SequencerParams(sequencer_is_playing=True)
    return s


def play(seq, step, **mutes):
    seq.params = SequencerParams(sequencer_is_playing=True, **mutes)
    seq.step_index, seq.next_step_index = step, step + 1
    seq.timeline.schedule.reset_mock()
    with patch("sequencer.sequencer_metro.random.randint", return_value=1):
        seq.evaluate_and_play_notes()
    return seq.timeline.schedule.call_args[0][0]["note"]


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
