"""m2k-jack plays a note's velocity as MONO2K's accent: over 100 the note is louder by the
pattern's ACNT (60 in the blank pattern: VOL x (256 + 120) / 256), any other velocity alike.

Renders through the built binary (engines/m2k/build.sh); skipped without it.
"""
import math
import os
import struct
import subprocess
import wave

import pytest

BINARY = os.path.join(os.path.dirname(__file__), "..", "engines", "m2k", "build", "m2k-jack")
pytestmark = pytest.mark.skipif(not os.access(BINARY, os.X_OK), reason="m2k-jack isn't built")

ACCENT = (256 + 2 * 60) / 256                      # MONO2K's accent at ACNT 60, about +3.3 dB


def rms(tmp_path, lines: list[str], start: float, end: float) -> float:
    """The render's RMS (both channels) from ``start`` to ``end`` seconds."""
    (tmp_path / "s.txt").write_text("\n".join(lines) + "\n")
    out = tmp_path / "r.wav"
    subprocess.run([BINARY, "--render", str(out), "--seconds", str(end + 0.05),
                    "--script", str(tmp_path / "s.txt")], check=True, capture_output=True)
    w = wave.open(str(out))
    rate, n = w.getframerate(), w.getnframes()
    d = struct.unpack(f"<{2 * n}h", w.readframes(n))
    x = d[2 * int(start * rate):2 * int(end * rate)]
    return math.sqrt(sum(v * v for v in x) / len(x))


def note(tmp_path, velocity: int, setup: tuple[str, ...] = ()) -> float:
    return rms(tmp_path, [*setup, f"0 144 60 {velocity}", "0.3 128 60 0"], 0.0, 0.25)


@pytest.mark.parametrize("velocity", [101, 127])
def test_a_velocity_over_100_is_an_accent(tmp_path, velocity):
    assert note(tmp_path, velocity) / note(tmp_path, 100) == pytest.approx(ACCENT, rel=0.01)


@pytest.mark.parametrize("velocity", [1, 64])
def test_a_velocity_up_to_100_plays_as_100(tmp_path, velocity):
    assert note(tmp_path, velocity) == pytest.approx(note(tmp_path, 100), rel=1e-6)


def test_a_note_with_no_filter_trig_is_accented_too(tmp_path):
    no_filter_trig = ("0 176 22 127",)               # CC 22: the note keeps the filter's envelope
    ratio = note(tmp_path, 127, no_filter_trig) / note(tmp_path, 100, no_filter_trig)
    assert ratio == pytest.approx(ACCENT, rel=0.01)


def test_a_note_with_no_amp_trig_accents_the_sounding_note(tmp_path):
    """As MONO2K's sequencer plays a trigless step: the amp goes on, at the step's accent."""
    def after_trigless(velocity: int) -> float:
        return rms(tmp_path, ["0 144 60 100", "0.1 176 21 127", f"0.1 144 62 {velocity}",
                              "0.4 128 62 0", "0.4 128 60 0"], 0.15, 0.3)
    assert after_trigless(127) / after_trigless(100) == pytest.approx(ACCENT, rel=0.02)
