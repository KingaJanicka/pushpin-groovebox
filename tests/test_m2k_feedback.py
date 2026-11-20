"""Feedback on mono2k: m2k-jack's own track parameters 81-83 and 85-87, the FEEDBACK device (slot 10).
FEEDBACK takes a tap on the track (SOURCE, 85: after its machine, its filters, its amp, or by default
its whole out, its delay too) one sample later to a destination (DEST, 86: by default back into its chain
before DIST, AMP IN, or any parameter an LFO reaches) on its own track or another (TRACK, 87); it is
bipolar about 64 (below: inverted). Its EQ (82, 83) is a band as FX's EQ is, 64 gain flat. The tracks a
feedback joins render a sample at a time (patches/0007), which with no feedback sounds as whole blocks do.

The render tests run the built binary (engines/m2k/build.sh); skipped without it.
"""
import json
import math
import os
import struct
import subprocess
import tempfile
import wave
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from engines.m2k import gen_definitions
from tests.test_m2k_velocity import BINARY, M2K_DIR, built, nrpn

FDBK, FEQF, FEQG = 81, 82, 83
FSRC, FDST, FTRK, FEQON = 85, 86, 87, 88
OSC_FM = 72                                      # DEST past MONO2K's 71 parameters: the machine's frequency
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
    loop's peak stays clear of the track's ceiling (27.6k before it; a sample late, the loop adds in phase)."""
    assert max(abs(v) for v in during(render(tmp_path, setup))) < 25000


@built
def test_gentle_feedback_lifts_the_sound_a_little(tmp_path):
    """FEEDBACK 90 (a gain of 0.17), a sample late: in phase with the saw's low partials, a little louder."""
    plain = during(render(tmp_path, []))
    gentle = during(render(tmp_path, nrpn(0.01, FDBK, 90)))
    assert gentle != plain
    assert rms(plain) < rms(gentle) < 1.4 * rms(plain)


@built
def test_below_64_feeds_back_inverted(tmp_path):
    up = render(tmp_path, nrpn(0.01, FDBK, 64 + 40))
    down = render(tmp_path, nrpn(0.01, FDBK, 64 - 40))
    plain = render(tmp_path, [])
    assert down != plain and down != up


@built
def test_feedback_dies_with_the_note(tmp_path):
    """The amp's envelope is in the loop: late in the release (SWAV-SAW's is long) it is hardly louder than
    the same note without feedback, and nothing keeps it going after."""
    fed = render(tmp_path, nrpn(0.01, FDBK, 127), seconds=4.0)
    plain = render(tmp_path, [], seconds=4.0)
    late = slice(int(1.8 * 44100), None)
    assert max(abs(v) for v in fed[late]) <= 1.05 * max(abs(v) for v in plain[late]) + 4
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
def test_eq_switched_off_is_not_heard(tmp_path):
    """The EQ's switch off: the loop as with a flat EQ, whatever EQF and EQG say; on, as they say."""
    loop = [*nrpn(0.01, FDBK, 110)]
    eq = [*nrpn(0.01, FEQF, 20), *nrpn(0.01, FEQG, 127)]
    flat = render(tmp_path, loop)
    assert render(tmp_path, [*loop, *eq, *nrpn(0.01, FEQON, 0)]) == flat
    assert render(tmp_path, [*loop, *eq, *nrpn(0.01, FEQON, 127)]) != flat


@built
def test_eq_does_nothing_without_feedback(tmp_path):
    plain = render(tmp_path, [])
    assert render(tmp_path, [*nrpn(0.01, FEQF, 20), *nrpn(0.01, FEQG, 127)]) == plain


@built
def test_describe_exports_feedback_after_key():
    d = json.loads(subprocess.run([BINARY, "--describe"], check=True, capture_output=True, text=True).stdout)
    assert d["param_count"] == 89
    tail = d["params_all"][81:84]
    assert [(p["param"], p["label"], p["name"]) for p in tail] == [
        (81, "FDBK", "FEEDBACK"), (82, "FEQF", "FEEDBACK EQ FREQ"), (83, "FEQG", "FEEDBACK EQ GAIN")]
    assert [p["bipolar"] for p in tail] == [True, False, True]
    eqf = next(p for p in d["params_all"] if p["param"] == 24)                # FX's EQF: the same words
    assert tail[1]["values"] == eqf["values"]
    assert all(m["kit"][81:84] == [64, 64, 64] for m in d["machines"])
    assert all(s["kit"][81:84] == [64, 64, 64] for s in d["library"])
    routing = d["params_all"][85:89]
    assert [(p["param"], p["label"], p["name"]) for p in routing] == [
        (85, "FSRC", "FEEDBACK SOURCE"), (86, "FDST", "FEEDBACK DEST"), (87, "FTRK", "FEEDBACK FROM TRACK"),
        (88, "FEQ", "FEEDBACK EQ")]
    # OUT, into its own AMP IN, the EQ switched on (flat at 64): as before
    assert all(m["kit"][85:89] == [127, 0, 0, 127] for m in d["machines"])
    assert all(s["kit"][85:89] == [127, 0, 0, 127] for s in d["library"])


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
    """DEST WDTH: the tap moves the low-pass's width while the note plays."""
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


# ------------------------------------------------------------- TRACK: into another track


def render_two(tmp_path, setup: list[str], seconds: float = 0.6) -> tuple[list[int], list[int]]:
    """Track 1 and track 2 (both SWAV-SAW, an octave apart) each playing a note, their stems' left channels."""
    lines = [f"0 176 14 {SAW}", f"0 177 14 {SAW}", *setup, *NOTE, "0.1 145 60 100", "0.4 129 60 0"]
    lines = sorted(lines, key=lambda line: float(line.split()[0]))      # (the script plays in order)
    (tmp_path / "s.txt").write_text("\n".join(lines) + "\n")
    subprocess.run([BINARY, "--render", str(tmp_path / "r.wav"), "--seconds", str(seconds),
                    "--script", str(tmp_path / "s.txt"), "--stems", str(tmp_path / "x")],
                   check=True, capture_output=True)
    out = []
    for n in (1, 2):
        w = wave.open(str(tmp_path / f"x_t{n}.wav"))
        k = w.getnframes()
        out.append(list(struct.unpack(f"<{w.getnchannels() * k}h", w.readframes(k))[0::w.getnchannels()]))
    return out[0], out[1]


@built
def test_own_track_is_the_default_and_track_1_names_it_outright(tmp_path):
    own = render_two(tmp_path, nrpn(0.01, FDBK, 110))
    assert render_two(tmp_path, [*nrpn(0.01, FTRK, 1), *nrpn(0.01, FDBK, 110)]) == own


@built
@pytest.mark.parametrize("source", [OSC, OUT], ids=["osc", "out"])
def test_feedback_from_another_track_into_amp_in(tmp_path, source):
    """TRACK says where the feedback comes from: track 2's page taking from track 1 (TRK 1) puts track 1's
    tap into track 2's chain: track 2 changes, track 1 plays as with none."""
    plain1, plain2 = render_two(tmp_path, [])
    t1, t2 = render_two(tmp_path, [*nrpn(0.01, FSRC, source, ch=1), *nrpn(0.01, FTRK, 1, ch=1),
                                   *nrpn(0.01, FDBK, 110, ch=1)])
    assert t1 == plain1
    assert t2 != plain2
    assert rms(during(t2)) > 1.1 * rms(during(plain2))


@built
def test_two_tracks_can_feed_each_other(tmp_path):
    """Track 1 from track 2 and track 2 from track 1, a sample late both ways: both change."""
    plain1, plain2 = render_two(tmp_path, [])
    setup = [*nrpn(0.01, FTRK, 2), *nrpn(0.01, FDBK, 110),
             *nrpn(0.01, FTRK, 1, ch=1), *nrpn(0.01, FDBK, 110, ch=1)]
    t1, t2 = render_two(tmp_path, setup)
    assert t1 != plain1 and t2 != plain2


@built
def test_feedback_into_another_tracks_parameter(tmp_path):
    """Track 1's page taking track 2's OSC tap into its own WDTH: track 1's width swings with track 2's note, track
    2 is as it was."""
    from tests.test_m2k_velocity import trace
    times = [0.2 + i * 0.0015 for i in range(40)]
    setup = [*nrpn(0.01, FSRC, OSC), *nrpn(0.01, FDST, WDTH + 1), *nrpn(0.01, FTRK, 2), *nrpn(0.01, FDBK, 127)]
    lines = [f"0 176 14 {SAW}", "0 176 73 64", f"0 177 14 {SAW}", *setup, *NOTE, "0.1 145 60 100", "0.4 129 60 0"]
    moved = trace(tmp_path, sorted(lines, key=lambda line: float(line.split()[0])), WDTH, times)
    assert len(set(moved)) > 10 and min(moved) < 64 * 256 < max(moved)
    _, plain2 = render_two(tmp_path, [])
    assert render_two(tmp_path, setup)[1] == plain2


@built
def test_feedback_into_a_silent_tracks_amp_in_is_not_heard(tmp_path):
    """It goes through the track's own amp: a track with no note, taking from one that plays, hears none."""
    lines = [f"0 176 14 {SAW}", f"0 177 14 {SAW}", *nrpn(0.01, FTRK, 1, ch=1), *nrpn(0.01, FDBK, 127, ch=1), *NOTE]
    lines = sorted(lines, key=lambda line: float(line.split()[0]))      # (the script plays in order)
    (tmp_path / "s.txt").write_text("\n".join(lines) + "\n")
    subprocess.run([BINARY, "--render", str(tmp_path / "r.wav"), "--seconds", "0.6",
                    "--script", str(tmp_path / "s.txt"), "--stems", str(tmp_path / "x")],
                   check=True, capture_output=True)
    w = wave.open(str(tmp_path / "x_t2.wav"))
    assert max(abs(v) for v in struct.unpack(f"<{w.getnchannels() * w.getnframes()}h",
                                             w.readframes(w.getnframes()))) == 0


# ------------------------------------------------------------- the FEEDBACK device


def page(stem: str) -> dict:
    with open(os.path.join(M2K_DIR, f"{stem}.json")) as f:
        return json.load(f)


def fdbk_page() -> dict:
    return page("62_fdbk")


def test_feedback_has_a_device_of_its_own_on_the_second_instrument_page():
    """Slot 10: past VEL (8) and KEY TRACK (9), so it's on the second instrument page (Right), and every m2k
    track shows it. One page of eight knobs."""
    from engine import M2KEngine
    device = fdbk_page()
    assert (device["name"], device["slot"]) == ("Feedback", 10)
    assert 10 in M2KEngine.always_shown_slots
    assert gen_definitions.slots(device["controls"]) == 8


def test_feedback_device_knobs_1_to_4_route_it():
    """Knobs 1-2: DEVICE and its DEST menu, where it goes on this track; knob 3: SOURCE, where it's taken from, on
    knob 4's track."""
    dest, source, track = fdbk_page()["controls"][:3]
    assert dest["$type"] == "control-switch" and dest["menu_label"] == "Device"
    groups = dest["groups"]
    assert groups[0]["label"] == "Amp In"
    assert groups[0]["controls"][0]["items"][0]["onselect"] == {"$type": "message", "address": "/m2k/param/86",
                                                               "value": 0}
    assert [g["label"] for g in groups[1:]] == ["Syn", "Amp", "Filt", "FX", "Dstr", "LFO 1", "LFO 2", "LFO 3"]
    wdth = next(i for i in groups[3]["controls"][0]["items"] if i["onselect"]["value"] == WDTH + 1)
    assert wdth["onselect"]["address"] == "/m2k/param/86"
    syn = groups[1]["controls"][0]["items"]                 # SYN A-H (the machine's own names), then OSC FM
    assert [i["onselect"]["value"] for i in syn] == [*range(1, 9), OSC_FM]
    assert syn[-1]["label"] == "OSC FM" and "label_from" not in syn[-1]
    assert source["menu_label"] == "Feedback Source"
    assert [(i["label"], i["onselect"]["address"], i["onselect"]["value"]) for i in source["items"]] == [
        ("OSC", "/m2k/param/85", OSC), ("Filt", "/m2k/param/85", FILT), ("Amp", "/m2k/param/85", AMP),
        ("Out", "/m2k/param/85", OUT)]
    assert track["menu_label"] == "From Track"
    # (named as pushpin shows its tracks, 1-8)
    assert [(i["label"], i["onselect"]["address"], i["onselect"]["value"]) for i in track["items"]] == [
        ("Own", "/m2k/param/87", 0)] + [(f"Trk {n}", "/m2k/param/87", n) for n in range(1, 9)]


def test_feedback_device_knobs_5_to_8_are_its_eq_and_amount():
    eq_on, eqf, eqg, fdbk = fdbk_page()["controls"][3:7]
    assert eq_on["menu_label"] == "Feedback EQ"
    assert [(i["label"], i["onselect"]["address"], i["onselect"]["value"]) for i in eq_on["items"]] == [
        ("EQ Off", "/m2k/param/88", 0), ("EQ On", "/m2k/param/88", 127)]
    assert (eqf["label"], eqf["address"]) == ("Feedback EQ Freq", "/m2k/param/82")
    assert (eqg["label"], eqg["address"]) == ("Feedback EQ Gain", "/m2k/param/83")
    assert eqg["bipolar"] == 1
    assert (fdbk["label"], fdbk["address"]) == ("Feedback", "/m2k/param/81")
    assert fdbk["bipolar"] == 1 and fdbk["display_center"] == 64


def test_feedback_eq_reads_as_fx_eq():
    fx = json.load(open(os.path.join(M2K_DIR, "30_fx.json")))["controls"]
    eqf = fdbk_page()["controls"][4]
    assert eqf["value_labels"] == fx[0]["value_labels"] and eqf["step"] == fx[0]["step"] == 0.5


@pytest.mark.parametrize("stem, trig", [("10_amp", "Amp Trig"), ("20_filt", "Filter Trig")])
def test_amp_and_filt_second_pages_are_their_trig_alone(stem, trig):
    controls = page(stem)["controls"]
    assert [c["$type"] for c in controls[8:15]] == ["control-spacer"] * 7
    assert controls[15]["menu_label"] == trig
    assert not any(c.get("address", "").startswith("/m2k/param/8") for c in controls)


def test_filt_first_page_is_unchanged():
    assert [c["address"] for c in page("20_filt")["controls"][:8]] == [f"/cc/{cc}" for cc in range(72, 80)]


def test_no_feedback_device_without_its_parameters():
    """A describe from before feedback (an older binary): no FEEDBACK device."""
    assert gen_definitions.feedback_controls({}) == []


def test_p_locks_on_mono2k_feedback_play(app):
    """FEEDBACK (slot 10), its eighth position: FEEDBACK."""
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
    seq.locks[0][10][7] = 20.0
    seq.evaluate_and_play_notes()
    assert sent == [("/m2k/param/81", 20.0)]


# ------------------------------------------------------------- a sample at a time


def render_with(tmp_path, lines: list[str], *flags: str, seconds: float = 0.8) -> dict[str, bytes]:
    """Every file a render writes (the mix, each track's stem, the return), as bytes, in a folder of its own."""
    tmp_path = Path(tempfile.mkdtemp(dir=tmp_path))
    lines = sorted(lines, key=lambda line: float(line.split()[0]))          # (the script plays in order)
    (tmp_path / "s.txt").write_text("\n".join(lines) + "\n")
    subprocess.run([BINARY, "--render", str(tmp_path / "r.wav"), "--seconds", str(seconds),
                    "--script", str(tmp_path / "s.txt"), "--stems", str(tmp_path / "x"), *flags],
                   check=True, capture_output=True)
    return {p.name: p.read_bytes() for p in sorted(tmp_path.glob("*.wav"))}


FXD, GNOI = 13, 14
# every stage of the chain on: DIST, EQ, FOLD, XOR, the delay (sent to, fed back), MOD (a chorus, mixed in)
CHAIN = ["0 176 60 110", "0 176 81 127", "0 176 80 30", "0 176 17 40", "0 176 18 20", "0 176 83 100", "0 176 84 90",
         *nrpn(0, 66, 40), *nrpn(0, 69, 90)]
TWO_NOTES = ["0.05 144 48 120", "0.05 145 55 90", "0.3 128 48 0", "0.3 129 55 0",
             "0.5 144 52 60", "0.5 145 50 60", "0.6 128 52 0", "0.6 129 50 0"]


def stepping_cases():
    for machine in range(20):
        # (FX-DYN's compressor hears its whole block first: stepped, it hears the block before; tested below)
        second = (machine + 1) % 20 if (machine + 1) % 20 != FXD else 0
        for chain in ("plain", "chain"):
            yield pytest.param(machine, second, chain, id=f"{machine}-{chain}")


@built
@pytest.mark.parametrize("machine, second, chain", stepping_cases())
def test_a_sample_at_a_time_sounds_as_whole_blocks_do(tmp_path, machine, second, chain):
    """--sample-step renders every track a sample at a time in step (patches/0007: any slice of a block), as feedback
    makes the tracks it joins: with none it must be the whole blocks to the bit, every machine on track 1 and the
    next on track 2 (an FX machine there hears track 1 a sample at a time), with the chain's stages on or not. (One
    edge is not: a delay whose track sends it a whole block of exact silence, its line already silent, goes to sleep
    in a whole block, while a sample at a time it can't know the block will be silent and runs on: a few LSB in a
    silent delay's filters, GND-NOIS's long release reaches it in 1.5 s with this chain.)"""
    lines = [f"0 176 14 {machine}", f"0 177 14 {second}", *(CHAIN if chain == "chain" else []), *TWO_NOTES]
    assert render_with(tmp_path, lines) == render_with(tmp_path, lines, "--sample-step")


@built
def test_fx_dyn_a_sample_at_a_time_hears_the_block_before(tmp_path):
    """FX-DYN's gain comes from its whole block's peak; a sample at a time it comes from the block before's, so it
    differs, but hardly: the same level within a dB."""
    lines = ["0 176 14 5", f"0 177 14 {FXD}", *TWO_NOTES]
    whole = render_with(tmp_path, lines)["x_t2.wav"]
    stepped = render_with(tmp_path, lines, "--sample-step")["x_t2.wav"]
    level = [rms(struct.unpack(f"<{len(x[44:]) // 2}h", x[44:])[int(0.1 * 44100):int(0.3 * 44100)]) for x in (whole,
                                                                                                         stepped)]
    assert whole != stepped
    assert abs(20 * math.log10(level[1] / level[0])) < 1.0


SINE_HELD = ["0 176 14 0", "0 176 57 127", "0 176 58 127"]      # GND-SIN, its HOLD and DEC held
SINE_NOTE = ["0.05 144 89 100", "0.45 128 89 0"]                 # 1397 Hz: 16 samples are half its period


def level(x: bytes, start: float = 0.15, end: float = 0.3) -> float:
    samples = struct.unpack(f"<{len(x[44:]) // 2}h", x[44:])[0::2]
    return rms(samples[int(start * 44100):int(end * 44100)])


def sine_gain(tmp_path, setup: list[str], held=SINE_HELD, note=SINE_NOTE, stem="x_t1.wav") -> float:
    """A track's level with ``setup`` over its level without, on a sine 16 samples are half a period of: a feedback
    a sample late adds to it (1 + g), one a block late (16 samples) would take from it (1 - g)."""
    return level(render_with(tmp_path, held + setup + note)[stem]) / level(render_with(tmp_path, held + note)[stem])


@built
@pytest.mark.parametrize("source", [OSC, FILT, AMP], ids=["osc", "filt", "amp"])
def test_a_tap_into_its_own_amp_in_comes_back_a_sample_later(tmp_path, source):
    """FEEDBACK 96: a gain of 0.25, so about 1.25 (the tanh takes a little off)."""
    assert 1.15 < sine_gain(tmp_path, [*nrpn(0.01, FSRC, source), *nrpn(0.01, FDBK, 96)]) < 1.3


@built
def test_out_comes_back_a_sample_later_too(tmp_path):
    """OUT, after MOD, VOL, the pan and the delay (all a sample at a time too): it adds to the sine (less: VOL and the
    pan have taken it down before the tap)."""
    assert 1.03 < sine_gain(tmp_path, [*nrpn(0.01, FSRC, OUT), *nrpn(0.01, FDBK, 96)]) < 1.2


@built
def test_another_tracks_amp_in_hears_it_a_sample_later(tmp_path):
    """Track 1 and track 2 play the same sine; track 2 taking track 1's OSC into its AMP IN adds to track 2's (1.25),
    and leaves track 1 as it was."""
    held = SINE_HELD + [line.replace(" 176 ", " 177 ") for line in SINE_HELD]
    note = SINE_NOTE + ["0.05 145 89 100", "0.45 129 89 0"]
    setup = [*nrpn(0.01, FSRC, OSC, ch=1), *nrpn(0.01, FTRK, 1, ch=1), *nrpn(0.01, FDBK, 96, ch=1)]
    assert 1.15 < sine_gain(tmp_path, setup, held, note, "x_t2.wav") < 1.3
    assert sine_gain(tmp_path, setup, held, note, "x_t1.wav") == 1.0


def goertzel(x: bytes, hz: float) -> float:
    s = struct.unpack(f"<{len(x[44:]) // 2}h", x[44:])[0::2][int(0.15 * 44100):int(0.35 * 44100)]
    w = 2 * math.pi * hz / 44100
    return math.hypot(sum(v * math.cos(w * i) for i, v in enumerate(s)), sum(v * math.sin(w * i) for i, v in enumerate(s)))


@built
def test_a_parameter_moves_at_audio_rate(tmp_path):
    """A pure sine (FOLD and HARM off) at 1397 Hz into its own VOL: moved every sample, VOL rides the sine and makes
    its second harmonic (a block at a time the moves would average out over its 16 samples, half a period)."""
    pure = SINE_HELD + ["0 176 48 0", "0 176 54 0"]
    vol = 13
    plain = render_with(tmp_path, pure + SINE_NOTE)["x_t1.wav"]
    fed = render_with(tmp_path, pure + [*nrpn(0.01, FSRC, OSC), *nrpn(0.01, FDST, vol + 1), *nrpn(0.01, FDBK, 120)]
                      + SINE_NOTE)["x_t1.wav"]
    f0 = 440 * 2 ** ((89 - 69) / 12)
    second = [goertzel(x, 2 * f0) / goertzel(x, f0) for x in (plain, fed)]
    assert second[1] > 3 * second[0] and second[1] > 0.2


PURE_PAIR = [line for ch in (0, 1) for line in (f"0 {176 + ch} 14 0", f"0 {176 + ch} 57 127", f"0 {176 + ch} 58 127",
                                                f"0 {176 + ch} 48 0", f"0 {176 + ch} 54 0")]
PAIR_NOTES = ["0.05 144 76 100", "0.45 128 76 0", "0.05 145 57 100", "0.45 129 57 0"]   # 659 Hz on 1, 220 Hz on 2
F1, F2 = 440 * 2 ** (7 / 12), 220.0


def osc_fm(amount: int) -> list[str]:
    """Track 1 taking track 2's OSC into OSC FM."""
    return [*nrpn(0.01, FSRC, OSC), *nrpn(0.01, FTRK, 2), *nrpn(0.01, FDST, OSC_FM), *nrpn(0.01, FDBK, amount)]


def off_carrier(x: bytes) -> float:
    """The share of the energy at 659 + n 220 Hz (n -10..10) that isn't the carrier's."""
    amps = [goertzel(x, abs(F1 + n * F2)) ** 2 for n in range(-10, 11) if abs(F1 + n * F2) > 20]
    return 1 - goertzel(x, F1) ** 2 / sum(amps)


@built
@pytest.mark.parametrize("amount", [90, 127])
def test_osc_fm_is_phase_modulation_as_deep_as_the_fm_machines(tmp_path, amount):
    """Phase modulation, as FM+ and FX-FM: a full-scale tap at FEEDBACK's top is 19 rad, FX-FM's deepest. Already at
    FEEDBACK 90 nearly all the sine's energy has gone to its sidebands (frequency modulation through the pitch, held
    off zero, left most of it on the carrier)."""
    plain = render_with(tmp_path, PURE_PAIR + PAIR_NOTES)["x_t1.wav"]
    fed = render_with(tmp_path, PURE_PAIR + osc_fm(amount) + PAIR_NOTES)["x_t1.wav"]
    assert off_carrier(plain) < 0.3 and off_carrier(fed) > 0.9


@built
def test_osc_fm_leaves_a_noise_machine_as_it_was(tmp_path):
    """GND-NOIS has no oscillator to bend: OSC FM on it changes nothing (the tracks a sample at a time sound as whole
    blocks do)."""
    lines = [f"0 176 14 {GNOI}", "0 177 14 0", *PAIR_NOTES]
    plain = render_with(tmp_path, lines)["x_t1.wav"]
    assert render_with(tmp_path, lines + osc_fm(127))["x_t1.wav"] == plain


@built
def test_osc_fm_is_not_heard_at_64_nor_added_to_the_sound(tmp_path):
    """OSC FM with FEEDBACK at 64 (none) plays as without; it moves the frequency, not AMP IN."""
    plain = render(tmp_path, [])
    assert render(tmp_path, [*nrpn(0.01, FSRC, OSC), *nrpn(0.01, FDST, OSC_FM)]) == plain
