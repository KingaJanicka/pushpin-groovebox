"""Feedback on mono2k: m2k-jack's own track parameters 81-83, FILT's second page
(only the page: the loop still goes in before DIST and the filters). FEEDBACK takes the
track's own out (after its chain and its delay) back into its chain before DIST, a block later; it is
bipolar about 64 (below: inverted). Its EQ (82, 83) is a band as FX's EQ is, 64 gain flat.

The render tests run the built binary (engines/m2k/build.sh); skipped without it.
"""
import json
import math
import os
import struct
import subprocess
import wave
from unittest.mock import MagicMock

import pytest

from engines.m2k import gen_definitions
from tests.test_m2k_velocity import BINARY, M2K_DIR, built, nrpn

FDBK, FEQF, FEQG = 81, 82, 83
SAW = 5                                          # SWAV-SAW
NOTE = ["0.1 144 48 100", "0.4 128 48 0"]


def render(tmp_path, setup: list[str], seconds: float = 0.6) -> list[int]:
    """Track 1 alone (its stem: no reverb return), left channel."""
    (tmp_path / "s.txt").write_text("\n".join([f"0 176 14 {SAW}", *setup, *NOTE]) + "\n")
    subprocess.run([BINARY, "--render", str(tmp_path / "r.wav"), "--seconds", str(seconds),
                    "--script", str(tmp_path / "s.txt"), "--stems", str(tmp_path / "x")],
                   check=True, capture_output=True)
    w = wave.open(str(tmp_path / "x_t1.wav"))
    n = w.getnframes()
    return list(struct.unpack(f"<{w.getnchannels() * n}h", w.readframes(n))[0::w.getnchannels()])


def rms(x: list[int]) -> float:
    return math.sqrt(sum(v * v for v in x) / len(x))


def during(x: list[int], rate: int = 44100) -> list[int]:
    """The held note, past its attack."""
    return x[int(0.2 * rate):int(0.35 * rate)]


@built
def test_feedback_is_off_at_64_and_by_default(tmp_path):
    plain = render(tmp_path, [])
    assert render(tmp_path, nrpn(0.01, FDBK, 64)) == plain


@built
def test_full_feedback_drives_the_chain_harder(tmp_path):
    plain = render(tmp_path, [])
    full = render(tmp_path, nrpn(0.01, FDBK, 127))
    assert full != plain
    assert rms(during(full)) > 1.5 * rms(during(plain))


@built
@pytest.mark.parametrize("setup", [
    nrpn(0.01, FDBK, 127),
    [*nrpn(0.01, FDBK, 127), *nrpn(0.01, FEQF, 100), *nrpn(0.01, FEQG, 127)],
], ids=["full", "full with the EQ boosted"])
def test_a_screaming_loop_is_held_down_by_the_tanh(tmp_path, setup):
    """The tanh after the EQ and the gain keeps what goes back in under about -8.7 dB of full scale: the
    loop's peak stays well clear of the track's ceiling (27.6k before it)."""
    assert max(abs(v) for v in during(render(tmp_path, setup))) < 20000


@built
def test_gentle_feedback_passes_the_tanh_nearly_as_it_was(tmp_path):
    plain = during(render(tmp_path, []))
    gentle = during(render(tmp_path, nrpn(0.01, FDBK, 90)))
    assert gentle != plain
    assert abs(rms(gentle) - rms(plain)) < 0.1 * rms(plain)


@built
def test_below_64_feeds_back_inverted(tmp_path):
    up = render(tmp_path, nrpn(0.01, FDBK, 64 + 40))
    down = render(tmp_path, nrpn(0.01, FDBK, 64 - 40))
    plain = render(tmp_path, [])
    assert down != plain and down != up


@built
def test_feedback_dies_with_the_note(tmp_path):
    """The amp's envelope is in the loop: late in the release (SWAV-SAW's is long) it is no louder than
    the same note without feedback, and nothing keeps it going after."""
    fed = render(tmp_path, nrpn(0.01, FDBK, 127), seconds=4.0)
    plain = render(tmp_path, [], seconds=4.0)
    late = slice(int(1.8 * 44100), None)
    assert max(abs(v) for v in fed[late]) <= max(abs(v) for v in plain[late]) + 4
    assert max(abs(v) for v in fed[int(3.5 * 44100):]) < 32


@built
def test_a_machine_turns_feedback_off(tmp_path):
    plain = render(tmp_path, [])
    assert render(tmp_path, [*nrpn(0, FDBK, 127), f"0.01 176 14 {SAW}"]) == plain


@built
def test_eq_is_flat_at_gain_64_and_shapes_the_feedback_otherwise(tmp_path):
    fb = nrpn(0.01, FDBK, 110)
    flat = render(tmp_path, fb)
    assert render(tmp_path, [*fb, *nrpn(0.01, FEQF, 20)]) == flat     # (no gain: the frequency does nothing)
    assert render(tmp_path, [*fb, *nrpn(0.01, FEQG, 127)]) != flat
    assert render(tmp_path, [*fb, *nrpn(0.01, FEQG, 0)]) != flat


@built
def test_eq_boost_feeds_back_louder_and_a_cut_quieter(tmp_path):
    """The band at 64 (a saw's body): the level follows the gain one way. (Its depth is half FX's EQ's in
    dB, m2k_jack.c's pp_fb_eq_gain.)"""
    def level(gain: int) -> float:
        return rms(during(render(tmp_path, [*nrpn(0.01, FDBK, 90), *nrpn(0.01, FEQF, 64),
                                            *nrpn(0.01, FEQG, gain)])))
    cut, flat, boost = level(0), level(64), level(96)
    assert cut < flat < boost


@built
def test_eq_does_nothing_without_feedback(tmp_path):
    plain = render(tmp_path, [])
    assert render(tmp_path, [*nrpn(0.01, FEQF, 20), *nrpn(0.01, FEQG, 127)]) == plain


@built
def test_describe_exports_feedback_after_key():
    d = json.loads(subprocess.run([BINARY, "--describe"], check=True, capture_output=True, text=True).stdout)
    assert d["param_count"] == 84
    tail = d["params_all"][81:]
    assert [(p["param"], p["label"], p["name"]) for p in tail] == [
        (81, "FDBK", "FEEDBACK"), (82, "FEQF", "FEEDBACK EQ FREQ"), (83, "FEQG", "FEEDBACK EQ GAIN")]
    assert [p["bipolar"] for p in tail] == [True, False, True]
    eqf = next(p for p in d["params_all"] if p["param"] == 24)                # FX's EQF: the same words
    assert tail[1]["values"] == eqf["values"]
    assert all(m["kit"][81:] == [64, 64, 64] for m in d["machines"])
    assert all(s["kit"][81:] == [64, 64, 64] for s in d["library"])


# ------------------------------------------------------------- FILT's second page


def page(stem: str) -> dict:
    with open(os.path.join(M2K_DIR, f"{stem}.json")) as f:
        return json.load(f)


def filt_page() -> dict:
    return page("20_filt")


def test_filt_second_page_starts_with_feedback_and_its_eq():
    controls = filt_page()["controls"]
    assert len(controls) == 16
    fdbk, eqf, eqg = controls[8:11]
    assert (fdbk["label"], fdbk["address"]) == ("Feedback", "/m2k/param/81")
    assert fdbk["bipolar"] == 1 and fdbk["display_center"] == 64
    assert (eqf["label"], eqf["address"]) == ("Feedback EQ Freq", "/m2k/param/82")
    assert (eqg["label"], eqg["address"]) == ("Feedback EQ Gain", "/m2k/param/83")
    assert eqg["bipolar"] == 1


def test_feedback_eq_reads_as_fx_eq():
    fx = json.load(open(os.path.join(M2K_DIR, "30_fx.json")))["controls"]
    eqf = filt_page()["controls"][9]
    assert eqf["value_labels"] == fx[0]["value_labels"] and eqf["step"] == fx[0]["step"] == 0.5


def test_filter_trig_stays_last_and_the_first_page_is_unchanged():
    controls = filt_page()["controls"]
    assert [c["$type"] for c in controls[11:15]] == ["control-spacer"] * 4
    assert controls[15]["menu_label"] == "Filter Trig"
    assert [c["address"] for c in controls[:8]] == [f"/cc/{cc}" for cc in range(72, 80)]


def test_amp_second_page_is_the_trig_alone_again():
    controls = page("10_amp")["controls"]
    assert [c["$type"] for c in controls[8:15]] == ["control-spacer"] * 7
    assert controls[15]["menu_label"] == "Amp Trig"
    assert not any(c.get("address", "").startswith("/m2k/param/8") for c in controls)


def test_no_feedback_page_without_its_parameters():
    """A describe from before feedback (an older binary): FILT's second page is the trig alone."""
    assert gen_definitions.feedback_controls({}) == []


def test_p_locks_on_mono2k_feedback_play(app):
    """FILT (slot 2), its ninth position: FEEDBACK."""
    from sequencer.sequencer_metro import SequencerMetro
    from tests.test_cc_client import make_instrument

    instrument, _ = make_instrument(app)
    app.instruments = {"Pushpin 2": instrument}
    sent = []
    app.send_osc = lambda address, value, name: sent.append((address, value))
    seq = SequencerMetro.__new__(SequencerMetro)
    seq.app = app
    seq.name = "Pushpin 2"
    seq.locks = [[[None] * 18 for _ in range(17)] for _ in range(64)]
    seq.lock_scale = [7] * 64
    seq.step_index = 0
    seq.gate = ["Off"] * 64
    seq.controls_to_reset = []
    seq.params = MagicMock(gate_track_active=False)
    seq.locks[0][2][8] = 20.0
    seq.evaluate_and_play_notes()
    assert sent == [("/m2k/param/81", 20.0)]
