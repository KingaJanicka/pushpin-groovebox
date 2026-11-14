"""Key tracking on mono2k (the Monomachine's ASSIGN > KEY): m2k-jack's own track parameters 75-80.
Two rows of a DEST and an ADD (75-78), as VEL's, with the note number as the source: a note adds
(ADD - 64) x note / 127 steps to DEST, from its note-on to the next. Then HPF and LPF (79, 80):
whether the high-pass and the low-pass follow the note (on, MONO2K's own way) or stay where note 60
puts them (off, the default).

Renders through the built binary (engines/m2k/build.sh); skipped without it.
"""
import json
import math
import os
import struct
import subprocess
import wave

import pytest

from engines.m2k import gen_definitions
from tests.test_m2k_velocity import BINARY, M2K_DIR, SETUP, VOL, WDTH, built, nrpn, trace

KDST1, KADD1, KDST2, KADD2, KHPF, KLPF = 75, 76, 77, 78, 79, 80
VADD1, VDST1 = 72, 71
SAW = 5                                          # SWAV-SAW: bright enough for a filter to tell


def key_row(t: float, row: int, dest_param: int, add: int) -> list[str]:
    dst, add_p = (KDST1, KADD1) if row == 1 else (KDST2, KADD2)
    return nrpn(t, dst, dest_param + 1) + nrpn(t, add_p, add)


def wdth_on(tmp_path, note: int, setup: list[str]) -> int:
    lines = SETUP + setup + [f"0.1 144 {note} 100", "0.3 128 {note} 0".format(note=note)]
    return trace(tmp_path, lines, WDTH, [0.2])[0]


@built
@pytest.mark.parametrize("note", [24, 60, 120])
def test_a_note_adds_add_scaled_by_its_number(tmp_path, note):
    assert wdth_on(tmp_path, note, key_row(0, 1, WDTH, 64 + 32)) == 64 * 256 + 32 * 256 * note // 127


@built
def test_add_below_64_takes_away_and_note_0_adds_nothing(tmp_path):
    assert wdth_on(tmp_path, 127, key_row(0, 1, WDTH, 64 - 20)) == (64 - 20) * 256
    assert wdth_on(tmp_path, 0, key_row(0, 1, WDTH, 64 - 20)) == 64 * 256


@built
def test_the_second_row_reaches_its_own_dest(tmp_path):
    lines = SETUP + key_row(0, 2, VOL, 64 - 8) + ["0.1 144 127 100"]
    vol_init = trace(tmp_path, ["0 144 60 100"], VOL, [0.05])[0]
    assert trace(tmp_path, lines, VOL, [0.2])[0] == vol_init - 8 * 256


@built
def test_the_next_note_replaces_it(tmp_path):
    lines = SETUP + key_row(0, 1, WDTH, 64 + 32) + [
        "0.2 144 120 100", "0.3 128 120 0", "0.5 144 30 100", "0.6 128 30 0"]
    high, released, low = trace(tmp_path, lines, WDTH, [0.25, 0.4, 0.55])
    assert high == released == 64 * 256 + 32 * 256 * 120 // 127
    assert low == 64 * 256 + 32 * 256 * 30 // 127


@built
def test_key_and_velocity_add_up_on_one_dest(tmp_path):
    setup = key_row(0, 1, WDTH, 64 + 10) + nrpn(0, VDST1, WDTH + 1) + nrpn(0, VADD1, 64 + 10)
    assert wdth_on(tmp_path, 127, setup) == 64 * 256 + 10 * 256 + 10 * 256 * 100 // 127


@built
def test_a_machine_turns_key_off(tmp_path):
    lines = key_row(0, 1, WDTH, 64 - 20) + ["0.05 176 14 0", "0.06 176 73 64", "0.1 144 127 100"]
    assert trace(tmp_path, lines, WDTH, [0.2])[0] == 64 * 256


# ------------------------------------------------------ the filters' tracking


def render(tmp_path, lines: list[str]) -> list[int]:
    (tmp_path / "s.txt").write_text("\n".join(lines) + "\n")
    out = tmp_path / "r.wav"
    subprocess.run([BINARY, "--render", str(out), "--seconds", "0.4", "--script", str(tmp_path / "s.txt")],
                   check=True, capture_output=True)
    w = wave.open(str(out))
    n = w.getnframes()
    return list(struct.unpack(f"<{2 * n}h", w.readframes(n))[0::2])


def brightness(x: list[int]) -> float:
    """The signal's slope against its level: higher with more treble."""
    x = x[5000:15000]
    level = math.sqrt(sum(v * v for v in x) / len(x))
    slope = math.sqrt(sum((x[i] - x[i - 1]) ** 2 for i in range(1, len(x))) / len(x))
    return slope / level


def saw_note(tmp_path, note: int, setup: list[str] = (), filt: list[str] = ("0.01 176 73 30",)) -> list[int]:
    """SWAV-SAW through a low-pass 30 steps over BASE (WDTH), or ``filt``'s, at ``note``."""
    return render(tmp_path, [f"0 176 14 {SAW}", *filt, *setup, f"0.1 144 {note} 100"])


def on(param: int) -> list[str]:
    return nrpn(0.02, param, 127)


def off(param: int) -> list[str]:
    return nrpn(0.02, param, 0)


@built
@pytest.mark.parametrize("param", [KHPF, KLPF])
def test_tracking_off_sits_where_note_60_puts_the_filter(tmp_path, param):
    assert saw_note(tmp_path, 60, off(param)) == saw_note(tmp_path, 60, on(param))
    assert saw_note(tmp_path, 84, off(param)) != saw_note(tmp_path, 84, on(param))


@built
@pytest.mark.parametrize("param", [KHPF, KLPF])
def test_tracking_is_off_by_default(tmp_path, param):
    """pushpin's default, not MONO2K's (whose filters always track)."""
    assert saw_note(tmp_path, 84) == saw_note(tmp_path, 84, off(param))


@built
def test_lpf_off_keeps_a_high_note_dark(tmp_path):
    assert brightness(saw_note(tmp_path, 84, off(KLPF))) < 0.6 * brightness(saw_note(tmp_path, 84, on(KLPF)))


@built
def test_hpf_off_thins_a_low_note(tmp_path):
    """A high-pass a little over the note: tracking off, a low note's fundamental is cut far deeper."""
    hp = ("0.01 176 72 40", "0.01 176 73 127")       # BASE up, the low-pass wide open
    tracked = saw_note(tmp_path, 36, on(KHPF), filt=hp)
    fixed = saw_note(tmp_path, 36, off(KHPF), filt=hp)
    assert brightness(fixed) > 1.3 * brightness(tracked)


@built
def test_switches_are_on_from_64(tmp_path):
    assert saw_note(tmp_path, 84, nrpn(0.02, KLPF, 64)) == saw_note(tmp_path, 84, on(KLPF))
    assert saw_note(tmp_path, 84, nrpn(0.02, KLPF, 63)) == saw_note(tmp_path, 84, off(KLPF))


@built
def test_a_machine_turns_tracking_off(tmp_path):
    tail = [f"0.01 176 14 {SAW}", "0.02 176 73 30", "0.1 144 84 100"]
    assert render(tmp_path, [*nrpn(0, KLPF, 127), *tail]) == render(tmp_path, tail)
    assert render(tmp_path, tail) == render(tmp_path, [*tail[:2], *off(KLPF), tail[2]])


@built
def test_describe_exports_key_after_vel():
    d = json.loads(subprocess.run([BINARY, "--describe"], check=True, capture_output=True, text=True).stdout)
    assert [(p["param"], p["name"]) for p in d["params_all"][75:81]] == [
        (75, "KEY 1 DEST"), (76, "KEY 1 ADD"), (77, "KEY 2 DEST"), (78, "KEY 2 ADD"),
        (79, "HPF TRACKING"), (80, "LPF TRACKING")]
    assert all(m["kit"][75:81] == [0, 64, 0, 64, 0, 0] for m in d["machines"])
    assert all(s["kit"][75:81] == [0, 64, 0, 64, 0, 0] for s in d["library"])


# ------------------------------------------------------------ the KEY TRACK page


def key_page() -> dict:
    with open(os.path.join(M2K_DIR, "61_key.json")) as f:
        return json.load(f)


def test_key_page_is_in_slot_9_after_vel():
    page = key_page()
    assert page["name"] == "Key Track" and page["slot"] == 9


def test_key_page_rows_are_device_dest_add_and_a_filters_tracking():
    controls = key_page()["controls"]
    assert [c["$type"] for c in controls] == ["control-switch", "control-range", "control-menu"] * 2
    assert gen_definitions.slots(controls) == 8
    assert (controls[1]["address"], controls[4]["address"]) == ("/m2k/param/76", "/m2k/param/78")
    assert controls[1]["bipolar"] == 1 and controls[1]["display_center"] == 64
    dests = [c["groups"][0]["controls"][0]["items"][0]["onselect"]["address"] for c in (controls[0], controls[3])]
    assert dests == ["/m2k/param/75", "/m2k/param/77"]
    assert controls[0]["groups"][1]["controls"][0]["menu_label"] == "Key Destination"


@pytest.mark.parametrize("position, param, name", [(2, KHPF, "HPF"), (5, KLPF, "LPF")])
def test_tracking_menus_are_off_then_on(position, param, name):
    menu = key_page()["controls"][position]
    assert menu["menu_label"] == f"{name} Tracking"
    assert [(i["label"], i["onselect"]["address"], i["onselect"]["value"]) for i in menu["items"]] == [
        (f"{name} Off", f"/m2k/param/{param}", 0), (f"{name} On", f"/m2k/param/{param}", 127)]
