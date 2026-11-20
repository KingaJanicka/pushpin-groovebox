"""FX-FM, pushpin's own mono2k machine (patches/0005-fx-fm-machine.patch): one of MONO2K's 32
waves (DIGI-WAV's M2K bank, whatever BANK holds) on the track's note is the carrier, and the track
before is its modulator, heard after its amp and filter, before its VOL. SYN: WAVE DEP DEC MIX FB
TONE TUNE INP. Its second page's CARRIER (m2k-jack's own parameter 84) puts the carrier on the track
before's pitch instead, and its PTCH sets the carrier's interval to the modulator.

Track 1 plays a held, plain GND-SIN at G3 (196 Hz) and track 2 plays FX-FM at C4 (261.6 Hz): the
carrier's sidebands land at 261.6 +- k x 196 Hz, apart from every harmonic of either note.

The render tests run the built binary (engines/m2k/build.sh); skipped without it.
"""
import cmath
import json
import math
import os
import struct
import subprocess
import wave

import pytest

from tests.test_m2k_velocity import BINARY, M2K_DIR, built, nrpn

GSIN, FXFM = 0, 19
WAVE, DEP, DEC, MIX, FB, TONE, TUNE, INP = range(48, 56)   # SYN A-H's CCs
BANK = 70                                                  # DIGI-WAV's wave bank (NRPN 1:70), 64-127 M64
M2K_WAVES = ["Sine", "Saw", "Sqr", "Tri", "Orgn", "Bell", "Glas", "Plst", "Ltex", "Chrm", "Holw", "Nasl", "Voxa", "Voxo",
             "Voxi", "Buzz", "Puls", "Form", "Strg", "Mtl1", "Mtl2", "Odd8", "Even", "Ramp", "Step", "Bits", "8bit",
             "Sid1", "Knif", "Spik", "Crsh", "Noiz"]
CARRIER = 84                                               # NRPN 1:84, 64-127 the track before's pitch
PTCH = 20                                                  # DSTR's track pitch, semitones about 64
FC, FM = 261.63, 196.00                                    # C4 (the carrier), G3 (the modulator)

# track 1 a plain sine (no FOLD, no 2nd harmonic), held (HOLD, DEC 127); track 2 FX-FM
SETUP = [f"0 176 14 {GSIN}", f"0 177 14 {FXFM}", "0.01 176 48 0", "0.01 176 54 0", "0.01 176 57 127",
         "0.01 176 58 127"]
NOTES = ["0.1 144 55 100", "0.1 145 60 100"]


def render(tmp_path, extra: list[str], seconds: float = 0.8) -> tuple[list[int], int]:
    """Track 2's stem (left channel) and its sample rate."""
    (tmp_path / "s.txt").write_text("\n".join([*SETUP, *extra, *NOTES]) + "\n")
    subprocess.run([BINARY, "--render", str(tmp_path / "r.wav"), "--seconds", str(seconds),
                    "--script", str(tmp_path / "s.txt"), "--stems", str(tmp_path / "x")],
                   check=True, capture_output=True)
    w = wave.open(str(tmp_path / "x_t2.wav"))
    n, ch = w.getnframes(), w.getnchannels()
    return list(struct.unpack(f"<{ch * n}h", w.readframes(n))[0::ch]), w.getframerate()


def spectrum(x: list[int], rate: int, freqs, start: float = 0.3, end: float = 0.4) -> dict:
    """Each frequency's amplitude over [start, end) s, as a share of the window's peak amplitude
    (the RMS x sqrt 2: a lone sine reads 1). Hann-windowed, so a strong partial 65 Hz away doesn't leak in."""
    seg = x[int(start * rate):int(end * rate)]
    n = len(seg)
    w = [0.5 - 0.5 * math.cos(2 * math.pi * i / n) for i in range(n)]
    total = math.sqrt(sum(v * v for v in seg) / n) * math.sqrt(2)
    return {f: abs(sum(v * w[i] * cmath.exp(-2j * math.pi * f * i / rate) for i, v in enumerate(seg))) / sum(w) * 2 / total
            for f in freqs}


def bessel(n: int, b: float) -> float:
    return sum((-1) ** m / (math.factorial(m) * math.factorial(m + n)) * (b / 2) ** (2 * m + n) for m in range(40))


SIDEBANDS = (FC, FC + FM, FC + 2 * FM)


def test_fx_fm_has_a_generated_machine_page():
    device = json.load(open(os.path.join(M2K_DIR, "00_machine_19.json")))
    assert device["name"] == "FX-FM"
    assert device["init"][0]["address"] == "/cc/14" and device["init"][0]["value"] == FXFM
    labels = [c.get("label") or c.get("menu_label") for c in device["controls"][:8]]
    assert labels == ["Carrier Wave", "FM Depth", "Depth Decay", "Mix", "Feedback", "Mod Tone", "Tune", "Input"]
    carrier = device["controls"][8]                         # the second page's first knob
    assert carrier["$type"] == "control-menu" and carrier["menu_label"] == "Carrier"
    assert [(i["label"], i["onselect"]["address"], i["onselect"]["value"]) for i in carrier["items"]] == [
        ("Own Note", "/m2k/param/84", 0), ("Prev Trk", "/m2k/param/84", 127)]
    assert {"address": "/m2k/param/84", "value": 0} in [
        {k: m[k] for k in ("address", "value")} for m in device["init"]]      # the INIT: its own note


def test_only_fx_fm_has_the_carrier_switch():
    for name in sorted(os.listdir(M2K_DIR)):
        if name.startswith("00_machine_") and name != "00_machine_19.json":
            controls = json.load(open(os.path.join(M2K_DIR, name)))["controls"]
            assert all(c.get("menu_label") != "Carrier" for c in controls), name


@built
def test_describe_exports_the_carrier_switch_after_feedback():
    d = json.loads(subprocess.run([BINARY, "--describe"], check=True, capture_output=True, text=True).stdout)
    assert d["param_count"] == 89
    carr = d["params_all"][CARRIER]
    assert (carr["param"], carr["label"], carr["name"]) == (CARRIER, "CARR", "FM CARRIER")
    assert all(m["kit"][CARRIER] == 0 for m in d["machines"])


@built
def test_fx_fm_is_the_last_machine():
    out = subprocess.run([BINARY, "--list-machines"], check=True, capture_output=True, text=True).stdout
    assert out.splitlines()[-1] == f"{FXFM}\tFX-FM"


@built
def test_depth_0_is_the_plain_carrier(tmp_path):
    x, rate = render(tmp_path, [f"0.01 177 {DEP} 0"])
    s = spectrum(x, rate, SIDEBANDS)
    assert s[FC] > 0.99
    assert s[FC + FM] < 0.01 and s[FC + 2 * FM] < 0.01


@built
def test_a_silent_track_before_leaves_the_carrier_plain(tmp_path):
    """Track 1 off (CC 9): nothing to modulate with, so the full depth sounds as depth 0."""
    full, _ = render(tmp_path, ["0 176 9 0", f"0.01 177 {DEP} 127"])
    none, _ = render(tmp_path, ["0 176 9 0", f"0.01 177 {DEP} 0"])
    assert full == none


@built
def test_the_track_before_puts_sidebands_on_the_carrier(tmp_path):
    x, rate = render(tmp_path, [])                       # the INIT's depth
    s = spectrum(x, rate, SIDEBANDS)
    assert s[FC + FM] > 0.2 and s[FC + 2 * FM] > 0.05
    assert s[FC] < 0.9


@built
def test_the_sidebands_follow_bessel_functions(tmp_path):
    """At a low index (one reading of J1 / J0): the second sideband is where J2 says. DEP 40 off this
    near-full-scale sine is about 0.75 rad, 4/3 of FM+'s law (0.56 there)."""
    x, rate = render(tmp_path, [f"0.01 177 {DEP} 40"])
    s = spectrum(x, rate, SIDEBANDS)
    ratio = s[FC + FM] / s[FC]
    beta = min((abs(bessel(1, b / 1000) / bessel(0, b / 1000) - ratio), b / 1000) for b in range(1, 2000))[1]
    assert 0.65 < beta < 0.85
    assert s[FC + 2 * FM] / s[FC] == pytest.approx(bessel(2, beta) / bessel(0, beta), rel=0.15)


@built
def test_more_depth_takes_more_from_the_carrier(tmp_path):
    def carrier(dep: int) -> float:
        x, rate = render(tmp_path, [f"0.01 177 {DEP} {dep}"])
        return spectrum(x, rate, [FC])[FC]
    assert carrier(0) > carrier(40) > carrier(60)


@built
def test_depth_decay_falls_back_to_the_carrier(tmp_path):
    """DEC 127 holds the depth; DEC 0 lets it fall from the trig, so late in the note the carrier is
    nearly alone again."""
    held, rate = render(tmp_path, [f"0.01 177 {DEP} 70", f"0.01 177 {DEC} 127"])
    fall, _ = render(tmp_path, [f"0.01 177 {DEP} 70", f"0.01 177 {DEC} 0"])
    late = {"start": 0.6, "end": 0.7}
    assert spectrum(held, rate, [FC + FM], **late)[FC + FM] > 0.2
    assert spectrum(fall, rate, [FC], **late)[FC] > 0.99


def test_wave_is_a_knob_naming_mono2ks_32_waves():
    """As DIGI-WAV's WAVE on the M2K bank: four values a wave; no BANK, so one table of names."""
    wave_knob = json.load(open(os.path.join(M2K_DIR, "00_machine_19.json")))["controls"][0]
    assert wave_knob["$type"] == "control-range" and "value_labels_by" not in wave_knob
    assert wave_knob["value_labels"] == [name for name in M2K_WAVES for _ in range(4)]
    digi = json.load(open(os.path.join(M2K_DIR, "00_machine_07.json")))["controls"][0]
    assert digi["value_labels_by"]["tables"][0] == wave_knob["value_labels"]          # DIGI-WAV's, on M2K


def test_fx_fm_has_no_wave_bank():
    controls = json.load(open(os.path.join(M2K_DIR, "00_machine_19.json")))["controls"]
    assert all(c.get("menu_label") != "Wave Bank" for c in controls)


@built
def test_the_init_carrier_is_the_sine(tmp_path):
    assert render(tmp_path, [f"0.01 177 {WAVE} 0"]) == render(tmp_path, [])


@built
def test_a_saw_carrier_has_its_harmonics(tmp_path):
    sine, rate = render(tmp_path, [f"0.01 177 {DEP} 0"])
    saw, _ = render(tmp_path, [f"0.01 177 {DEP} 0", f"0.01 177 {WAVE} 4"])
    assert spectrum(sine, rate, [2 * FC])[2 * FC] < 0.01
    s = spectrum(saw, rate, [FC, 2 * FC, 3 * FC])
    assert s[2 * FC] / s[FC] == pytest.approx(1 / 2, abs=0.1)                       # a saw: 1 / n
    assert s[3 * FC] / s[FC] == pytest.approx(1 / 3, abs=0.1)


@built
def test_wave_plays_the_wave_it_names_never_between_two(tmp_path):
    """Values 4-7 are all SAW (the names' four a wave): the same sound, not a fade toward SQR."""
    first, _ = render(tmp_path, [f"0.01 177 {WAVE} 4"])
    assert render(tmp_path, [f"0.01 177 {WAVE} 7"])[0] == first
    assert render(tmp_path, [f"0.01 177 {WAVE} 8"])[0] != first


@built
def test_wave_ignores_the_bank(tmp_path):
    m2k, _ = render(tmp_path, [f"0.01 177 {WAVE} 20"])
    assert render(tmp_path, [*nrpn(0.01, BANK, 127, ch=1), f"0.01 177 {WAVE} 20"])[0] == m2k


@built
def test_mix_0_is_the_track_before_as_it_came_in(tmp_path):
    x, rate = render(tmp_path, [f"0.01 177 {MIX} 0"])
    s = spectrum(x, rate, [FM, FC])
    assert s[FM] > 0.99 and s[FC] < 0.01


@built
def test_input_0_and_tone_closed_turn_the_modulation_down(tmp_path):
    def sideband(*extra: str) -> float:
        x, rate = render(tmp_path, [f"0.01 177 {DEP} 70", *extra])
        return spectrum(x, rate, [FC + FM])[FC + FM]
    full = sideband()
    assert sideband(f"0.01 177 {INP} 0") < 0.01
    assert sideband(f"0.01 177 {TONE} 0") < full / 4


@built
def test_feedback_adds_the_carriers_own_harmonics(tmp_path):
    plain, rate = render(tmp_path, [f"0.01 177 {DEP} 0"])
    fed, _ = render(tmp_path, [f"0.01 177 {DEP} 0", f"0.01 177 {FB} 127"])
    assert spectrum(plain, rate, [2 * FC])[2 * FC] < 0.01
    assert spectrum(fed, rate, [2 * FC])[2 * FC] > 0.1


@built
def test_on_the_first_track_there_is_no_modulator(tmp_path):
    """Track 1 has no track before it: FX-FM there is its plain carrier, whatever the depth."""
    def first(dep: int) -> list[int]:
        (tmp_path / "s.txt").write_text("\n".join([f"0 176 14 {FXFM}", f"0.01 176 {DEP} {dep}",
                                                   "0.1 144 60 100"]) + "\n")
        subprocess.run([BINARY, "--render", str(tmp_path / "r.wav"), "--seconds", "0.4",
                        "--script", str(tmp_path / "s.txt"), "--stems", str(tmp_path / "x")],
                       check=True, capture_output=True)
        w = wave.open(str(tmp_path / "x_t1.wav"))
        return list(struct.unpack(f"<{w.getnchannels() * w.getnframes()}h", w.readframes(w.getnframes())))
    assert first(127) == first(0)


# ------------------------------------------------------------- CARRIER: the track before's pitch


def prev_trk(*extra: str) -> list[str]:
    return [*nrpn(0.01, CARRIER, 127, ch=1), *extra]


@built
def test_carrier_on_the_track_before_plays_its_pitch(tmp_path):
    """FX-FM plays C4, the track before G3: switched, the carrier is on G3."""
    x, rate = render(tmp_path, prev_trk(f"0.01 177 {DEP} 0"))
    s = spectrum(x, rate, [FC, FM])
    assert s[FM] > 0.99 and s[FC] < 0.01


@built
def test_carrier_on_the_track_before_ignores_the_fx_tracks_own_note(tmp_path):
    def with_own_note(note: int) -> list[int]:
        notes = NOTES[1]
        try:
            NOTES[1] = f"0.1 145 {note} 100"
            return render(tmp_path, prev_trk())[0]
        finally:
            NOTES[1] = notes
    assert with_own_note(60) == with_own_note(72)


@built
def test_on_the_track_before_ptch_sets_the_ratio_to_the_modulator(tmp_path):
    """PTCH +12 on FX-FM: the carrier an octave over the modulator (ratio 2); with depth, the sidebands
    sit on the modulator's harmonics (2 +- k: all of them), not around FX-FM's own note."""
    x, rate = render(tmp_path, prev_trk(f"0.01 177 {PTCH} 76"))
    s = spectrum(x, rate, [FM, 2 * FM, 3 * FM, FC, FC + FM])
    assert s[FM] + s[2 * FM] + s[3 * FM] > 0.9
    assert s[FC] < 0.01 and s[FC + FM] < 0.01


@built
def test_carrier_on_the_track_before_follows_its_ptch_and_adds_its_own(tmp_path):
    up_there, rate = render(tmp_path, prev_trk(f"0.01 177 {DEP} 0", f"0.01 176 {PTCH} 76"))   # +12 before
    assert spectrum(up_there, rate, [2 * FM])[2 * FM] > 0.99
    up_here, _ = render(tmp_path, prev_trk(f"0.01 177 {DEP} 0", f"0.01 177 {PTCH} 76"))       # +12 here
    assert spectrum(up_here, rate, [2 * FM])[2 * FM] > 0.99


@built
def test_carrier_back_on_its_own_note(tmp_path):
    own, _ = render(tmp_path, [*nrpn(0.01, CARRIER, 127, ch=1), *nrpn(0.02, CARRIER, 0, ch=1)])
    assert own == render(tmp_path, [])[0]


@built
def test_a_machine_puts_the_carrier_back_on_its_own_note(tmp_path):
    again, _ = render(tmp_path, [*nrpn(0.01, CARRIER, 127, ch=1), f"0.02 177 14 {FXFM}"])
    assert again == render(tmp_path, [])[0]
