"""Feedback on mono2k: m2k-jack's own track parameters 81-83 and 85-86, FILT's second page.
FEEDBACK takes a tap on the track (SOURCE, 85: after its machine, its filters, its amp, or by default
its whole out, its delay too) a block later to a destination (DEST, 86: by default back into its chain
before DIST, AMP IN, or any parameter an LFO reaches); it is bipolar about 64 (below: inverted). Its EQ
(82, 83) is a band as FX's EQ is, 64 gain flat.

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
FSRC, FDST = 85, 86
OSC, FILT, AMP, OUT = 16, 48, 80, 112             # SOURCE: the middle of each quarter
WDTH = 17
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
    assert d["param_count"] == 87
    tail = d["params_all"][81:84]
    assert [(p["param"], p["label"], p["name"]) for p in tail] == [
        (81, "FDBK", "FEEDBACK"), (82, "FEQF", "FEEDBACK EQ FREQ"), (83, "FEQG", "FEEDBACK EQ GAIN")]
    assert [p["bipolar"] for p in tail] == [True, False, True]
    eqf = next(p for p in d["params_all"] if p["param"] == 24)                # FX's EQF: the same words
    assert tail[1]["values"] == eqf["values"]
    assert all(m["kit"][81:84] == [64, 64, 64] for m in d["machines"])
    assert all(s["kit"][81:84] == [64, 64, 64] for s in d["library"])
    routing = d["params_all"][85:87]
    assert [(p["param"], p["label"], p["name"]) for p in routing] == [
        (85, "FSRC", "FEEDBACK SOURCE"), (86, "FDST", "FEEDBACK DEST")]
    assert all(m["kit"][85:87] == [127, 0] for m in d["machines"])            # OUT, into AMP IN: as before
    assert all(s["kit"][85:87] == [127, 0] for s in d["library"])


# ------------------------------------------------------------- SOURCE and DEST


@built
def test_the_default_source_and_dest_are_the_old_loop(tmp_path):
    """OUT into AMP IN, said outright, plays what FEEDBACK alone always did."""
    old = render(tmp_path, nrpn(0.01, FDBK, 110))
    assert render(tmp_path, [*nrpn(0.01, FSRC, OUT), *nrpn(0.01, FDST, 0), *nrpn(0.01, FDBK, 110)]) == old


@built
@pytest.mark.parametrize("source", [OSC, FILT, AMP, OUT], ids=["osc", "filt", "amp", "out"])
def test_each_source_is_off_at_64(tmp_path, source):
    plain = render(tmp_path, [])
    assert render(tmp_path, [*nrpn(0.01, FSRC, source), *nrpn(0.01, FDBK, 64)]) == plain


@built
def test_each_source_feeds_back_something_of_its_own(tmp_path):
    plain = render(tmp_path, [])
    fed = {s: render(tmp_path, [*nrpn(0.01, FSRC, s), *nrpn(0.01, FDBK, 110)]) for s in (OSC, FILT, AMP, OUT)}
    assert all(x != plain for x in fed.values())
    assert len({tuple(x) for x in fed.values()}) == 4


@built
@pytest.mark.parametrize("source", [OSC, FILT, AMP], ids=["osc", "filt", "amp"])
def test_a_tap_dies_with_the_note(tmp_path, source):
    """A silent track's chain takes no tap: nothing keeps the loop going after the release."""
    fed = render(tmp_path, [*nrpn(0.01, FSRC, source), *nrpn(0.01, FDBK, 127)], seconds=4.0)
    assert max(abs(v) for v in fed[int(3.5 * 44100):]) < 32


def wdth_trace(tmp_path, setup: list[str]) -> list[int]:
    from tests.test_m2k_velocity import trace
    times = [0.2 + i * 0.0015 for i in range(40)]
    return trace(tmp_path, [f"0 176 14 {SAW}", "0 176 73 64", *setup, *NOTE], WDTH, times)


@built
def test_feedback_into_a_parameter_moves_it_with_the_sound(tmp_path):
    """DEST WDTH: the tap's block mean moves the low-pass's width while the note plays."""
    still = wdth_trace(tmp_path, [*nrpn(0.01, FDST, WDTH + 1)])
    assert len(set(still)) == 1                                   # (FEEDBACK at 64: nothing moves)
    moved = wdth_trace(tmp_path, [*nrpn(0.01, FSRC, OSC), *nrpn(0.01, FDST, WDTH + 1), *nrpn(0.01, FDBK, 127)])
    assert len(set(moved)) > 10
    assert min(moved) < still[0] < max(moved)                     # (both ways: a saw swings about 0)


@built
def test_feedback_into_a_parameter_is_not_added_to_the_sound(tmp_path):
    """Into a parameter, nothing goes back in before DIST: DEST on a parameter the sound doesn't hear (an LFO's
    depth with its LFO off) leaves it as it was."""
    plain = render(tmp_path, [])
    lfo3_dpth = 63
    assert render(tmp_path, [*nrpn(0.01, FDST, lfo3_dpth + 1), *nrpn(0.01, FDBK, 127)]) == plain


# ------------------------------------------------------------- FILT's second page


def page(stem: str) -> dict:
    with open(os.path.join(M2K_DIR, f"{stem}.json")) as f:
        return json.load(f)


def filt_page() -> dict:
    return page("20_filt")


def test_filt_second_page_starts_with_feedback_and_its_eq():
    controls = filt_page()["controls"]
    assert gen_definitions.slots(controls) == 16                    # (two pages of eight knobs)
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


def test_filt_second_page_routes_the_feedback_on_knobs_4_to_6():
    controls = filt_page()["controls"]
    source, dest = controls[11:13]
    assert source["menu_label"] == "Feedback Source"
    assert [(i["label"], i["onselect"]["address"], i["onselect"]["value"]) for i in source["items"]] == [
        ("OSC", "/m2k/param/85", OSC), ("Filt", "/m2k/param/85", FILT), ("Amp", "/m2k/param/85", AMP),
        ("Out", "/m2k/param/85", OUT)]
    assert dest["$type"] == "control-switch" and dest["menu_label"] == "Device"   # (DEVICE, then its DEST menu)
    groups = dest["groups"]
    assert groups[0]["label"] == "Amp In"
    assert groups[0]["controls"][0]["items"][0]["onselect"] == {"$type": "message", "address": "/m2k/param/86",
                                                               "value": 0}
    assert [g["label"] for g in groups[1:]] == ["Syn", "Amp", "Filt", "FX", "Dstr", "LFO 1", "LFO 2", "LFO 3"]
    wdth = next(i for i in groups[3]["controls"][0]["items"] if i["onselect"]["value"] == WDTH + 1)
    assert wdth["onselect"]["address"] == "/m2k/param/86"


def test_filter_trig_stays_last_and_the_first_page_is_unchanged():
    """The DEVICE switch takes two knobs (its DEST menu beside it): FILTER TRIG stays on the second page's
    eighth, where its p-locks are."""
    controls = filt_page()["controls"]
    assert gen_definitions.slots(controls[8:14]) == 7
    assert controls[13]["$type"] == "control-spacer"
    assert controls[14]["menu_label"] == "Filter Trig"
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
