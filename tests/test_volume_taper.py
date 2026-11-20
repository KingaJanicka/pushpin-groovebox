import math

import pytest

from utilities.volume_taper import (
    DEFAULT_TRACK_FADER,
    FADER_DB_RANGE,
    fader_to_gain,
    gain_to_fader,
    step_fader,
)


def db(gain):
    return 20 * math.log10(gain)


def test_endpoints():
    assert fader_to_gain(0.0) == 0.0
    assert fader_to_gain(-0.5) == 0.0
    assert fader_to_gain(1.0) == pytest.approx(1.0)
    assert fader_to_gain(1.5) == pytest.approx(1.0)


def test_each_step_is_the_same_number_of_db():
    step_db = FADER_DB_RANGE / 100
    for pos in (0.1, 0.2, 0.5, 0.8, 0.99):
        assert db(fader_to_gain(pos + 0.01)) - db(fader_to_gain(pos)) == pytest.approx(step_db)


def test_midpoint_is_half_the_db_range():
    assert db(fader_to_gain(0.5)) == pytest.approx(-FADER_DB_RANGE / 2)


def test_gain_to_fader_round_trips():
    for pos in (0.05, 0.3, 0.6, 0.93, 1.0):
        assert gain_to_fader(fader_to_gain(pos)) == pytest.approx(pos)
    assert gain_to_fader(0.0) == 0.0
    assert gain_to_fader(1e-9) == 0.0


def test_default_keeps_old_loudness():
    # The old linear default sent 0.6 straight to the volume node.
    assert fader_to_gain(DEFAULT_TRACK_FADER) == pytest.approx(0.6, abs=0.02)


@pytest.mark.parametrize(
    "start, increment, expected",
    [(0.5, 1, 0.51), (0.5, -3, 0.47), (0.995, 1, 1.0), (0.005, -1, 0.0), (0.0, -5, 0.0), (1.0, 5, 1.0)],
)
def test_step_fader_clamps(start, increment, expected):
    assert step_fader(start, increment) == pytest.approx(expected)


def test_step_fader_reaches_exact_zero_from_float_drift():
    pos = 0.6
    for _ in range(60):
        pos = step_fader(pos, -1)
    assert pos == 0.0
    assert fader_to_gain(pos) == 0.0
