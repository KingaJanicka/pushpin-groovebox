"""m2k-jack takes its tempo from MIDI clock: a delay of a 1/4 note follows it.

Renders through the built binary (engines/m2k/build.sh); skipped without it.
"""
import os
import struct
import subprocess
import wave

import pytest

BINARY = os.path.join(os.path.dirname(__file__), "..", "engines", "m2k", "build", "m2k-jack")
pytestmark = pytest.mark.skipif(not os.access(BINARY, os.X_OK), reason="m2k-jack isn't built")

KICK = 15                                          # DRM-KICK: a short hit


def script(bpm: float | None, jitter: float = 0.0) -> str:
    import random
    rnd = random.Random(7)
    lines = [(0.0, f"0 176 14 {KICK}"), (0.01, "0.01 176 84 127"),           # DSND full,
             (0.01, "0.01 176 85 0"), (0.01, "0.01 176 83 64")]               # no feedback, DTIM a 1/4 note
    if bpm:
        per, k = 60.0 / bpm / 24, 0
        while k * per < 3.0:
            t = max(0.0, k * per + rnd.uniform(-jitter, jitter))
            lines.append((t, f"{t:.6f} 248 0 0"))
            k += 1
    lines += [(2.0, "2.0 144 60 120"), (2.05, "2.05 128 60 0")]
    return "\n".join(line for _, line in sorted(lines)) + "\n"


def echo_ms(tmp_path, text: str) -> float:
    """How long after the hit its echo comes: found on the envelope (1 ms bins), then to the
    sample by matching the hit's first 30 ms against the signal around there."""
    (tmp_path / "s.txt").write_text(text)
    out = tmp_path / "r.wav"
    subprocess.run([BINARY, "--render", str(out), "--seconds", "3.2", "--script", str(tmp_path / "s.txt")],
                   check=True, capture_output=True)
    w = wave.open(str(out))
    rate, n = w.getframerate(), w.getnframes()
    d = struct.unpack(f"<{2 * n}h", w.readframes(n))
    x = [d[2 * i] + d[2 * i + 1] for i in range(n)]
    step = rate // 1000
    env = [sum(abs(v) for v in x[i:i + step]) for i in range(0, n, step)]
    hit = 1990
    coarse = max(range(300, 900), key=lambda lag: sum(a * b for a, b in zip(env[hit + lag:hit + lag + 60], env[hit:])))
    h0, width = hit * step, int(0.03 * rate)
    dry = x[h0:h0 + width]
    lags = range((coarse - 15) * step, (coarse + 15) * step)
    best = max(lags, key=lambda lag: sum(a * b for a, b in zip(x[h0 + lag:h0 + lag + width], dry)))
    return best * 1000.0 / rate


def test_a_delay_follows_the_clocks_tempo(tmp_path):
    base = echo_ms(tmp_path, script(None))                       # no clock: MONO2K's own 120
    slow = echo_ms(tmp_path, script(90))
    fast = echo_ms(tmp_path, script(140))
    assert abs((slow - base) - (60000 / 90 - 500)) <= 0.5        # +166.7 ms
    assert abs((fast - base) - (60000 / 140 - 500)) <= 0.5       # -71.4 ms


def test_a_jittery_clock_keeps_the_delay_where_it_is(tmp_path):
    steady = echo_ms(tmp_path, script(100))
    jittery = echo_ms(tmp_path, script(100, jitter=0.003))        # a few ms either way a pulse (a Python thread's)
    assert abs(jittery - steady) <= steady * 0.0025               # (m2k-jack's hysteresis)
