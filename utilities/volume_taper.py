"""Fader-position -> gain curve for the per-track volume encoder.

``app.volumes`` holds *fader positions* in ``0.0..1.0`` (what the encoder
moves and what the display shows). The Pure Data volume node multiplies the
audio by whatever number it receives, so sending the position straight through
gave a linear-amplitude fader: most of the travel sat in the loud top few dB
and all the quiet range was crammed into the last few clicks.

Instead the position maps onto a decibel scale: full travel spans
``FADER_DB_RANGE`` dB, so each encoder step is the same number of dB and the
knob feels even across its range. Position ``0.0`` is true silence.
"""

from __future__ import annotations

import math

FADER_DB_RANGE = 60.0
"""dB covered between the lowest non-zero position and the top (0 dB)."""

FADER_STEP = 0.01
"""Fader movement per encoder click (100 clicks top to bottom, 0.6 dB each)."""


def fader_to_gain(position: float) -> float:
    """Return the linear gain for a fader ``position`` in ``0.0..1.0``."""
    if position <= 0.0:
        return 0.0
    position = min(position, 1.0)
    return 10.0 ** ((position - 1.0) * FADER_DB_RANGE / 20.0)


def gain_to_fader(gain: float) -> float:
    """Inverse of :func:`fader_to_gain`; gains below the range map to 0."""
    if gain <= 0.0:
        return 0.0
    position = 1.0 + 20.0 * math.log10(gain) / FADER_DB_RANGE
    return min(max(position, 0.0), 1.0)


def step_fader(position: float, increment: int, step: float = FADER_STEP) -> float:
    """Move ``position`` by ``increment`` encoder clicks, clamped to ``0..1``."""
    new_position = round(position + increment * step, 6)
    return min(max(new_position, 0.0), 1.0)


DEFAULT_TRACK_FADER = round(gain_to_fader(0.6), 2)
"""Default position: ~0.93, about the same loudness as the old linear 0.6."""
