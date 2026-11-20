"""m2k-jack plays a note on over the track's held note (pushpin's Tie) as MONO2K's slide: the pitch
glides to the new note and the amp goes on, not restarted. The slid-from note's note-off is ignored;
the same note held over itself is a tie and lasts to its last note-off.

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

LOW, HIGH = 57, 69                                  # an octave apart: the pitch doubles


def render(tmp_path, lines: list[str]) -> tuple[int, list[int]]:
    (tmp_path / "s.txt").write_text("\n".join(lines) + "\n")
    out = tmp_path / "r.wav"
    subprocess.run([BINARY, "--render", str(out), "--seconds", "1.0", "--script", str(tmp_path / "s.txt")],
                   check=True, capture_output=True)
    w = wave.open(str(out))
    rate, n = w.getframerate(), w.getnframes()
    d = struct.unpack(f"<{2 * n}h", w.readframes(n))
    return rate, [d[2 * i] + d[2 * i + 1] for i in range(n)]


def at(rendered, start: float, length: float = 0.02) -> tuple[float, float]:
    """(rising zero crossings a second, RMS) over ``length`` seconds from ``start``."""
    rate, x = rendered
    seg = x[int(start * rate):int((start + length) * rate)]
    crossings = sum(1 for i in range(1, len(seg)) if seg[i - 1] < 0 <= seg[i])
    return crossings / length, math.sqrt(sum(v * v for v in seg) / len(seg))


def sound(track: int, decay: int, port: int = 0) -> list[str]:
    """GND-SIN with ATK 0, HOLD 0 or long, DEC ``decay``, a short REL, PORT ``port``."""
    cc = 176 + track
    hold = 127 if decay == 127 else 0
    return [f"0 {cc} 14 0", f"0.01 {cc} 56 0", f"0.01 {cc} 57 {hold}", f"0.01 {cc} 58 {decay}",
            f"0.01 {cc} 59 10", f"0.01 {cc} 63 {port}"]


def notes(track: int, *events: tuple[float, bool, int]) -> list[str]:
    return [f"{t} {(144 if on else 128) + track} {n} {100 if on else 0}" for t, on, n in events]


SEPARATE = ((0.1, True, LOW), (0.39, False, LOW), (0.4, True, HIGH), (0.8, False, HIGH))
OVERLAP = ((0.1, True, LOW), (0.4, True, HIGH), (0.42, False, LOW), (0.8, False, HIGH))


@pytest.mark.parametrize("track", [0, 1])           # track 1 was the core's keys' track, on a path of its own
def test_an_overlapping_note_slides_without_restarting_the_amp(tmp_path, track):
    slid = render(tmp_path, sound(track, decay=70) + notes(track, *OVERLAP))
    retrigged = render(tmp_path, sound(track, decay=70) + notes(track, *SEPARATE))
    low_pitch, before = at(slid, 0.36)
    high_pitch, after = at(slid, 0.45)
    assert high_pitch / low_pitch == pytest.approx(2.0, rel=0.1)    # it glided to the new note
    assert after < before                                            # the decay went on
    assert after < 0.3 * at(retrigged, 0.45)[1]                      # a new note restarts it


def test_separate_notes_still_retrigger(tmp_path):
    rendered = render(tmp_path, sound(0, decay=70) + notes(0, *SEPARATE))
    assert at(rendered, 0.45)[1] > 3 * at(rendered, 0.36)[1]


def test_the_slid_from_notes_note_off_doesnt_end_the_note(tmp_path):
    rendered = render(tmp_path, sound(0, decay=127) + notes(0, *OVERLAP))
    held = at(rendered, 0.3)[1]
    assert at(rendered, 0.5)[1] == pytest.approx(held, rel=0.1)      # past the low note's note-off at 0.42
    assert at(rendered, 0.85)[1] < 0.01 * held                       # the high note's own note-off ends it


def test_a_note_tied_over_itself_lasts_to_its_last_note_off(tmp_path):
    tie = ((0.1, True, LOW), (0.4, True, LOW), (0.42, False, LOW), (0.8, False, LOW))
    rendered = render(tmp_path, sound(0, decay=127) + notes(0, *tie))
    pitch, held = at(rendered, 0.3)
    assert at(rendered, 0.5) == pytest.approx((pitch, held), rel=0.1)
    assert at(rendered, 0.85)[1] < 0.01 * held


def test_port_slows_the_slide(tmp_path):
    quick = render(tmp_path, sound(0, decay=127) + notes(0, *OVERLAP))
    slow = render(tmp_path, sound(0, decay=127, port=64) + notes(0, *OVERLAP))
    low_pitch = at(quick, 0.36)[0]
    assert at(quick, 0.42)[0] / low_pitch == pytest.approx(2.0, rel=0.1)   # PORT 0: there within 20 ms
    assert at(slow, 0.42)[0] / low_pitch < 1.7                              # PORT 64: still on its way
