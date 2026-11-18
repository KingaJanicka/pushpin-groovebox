"""Velocity's modulations on mono2k (the Monomachine's ASSIGN > VEL): m2k-jack's own track
parameters 71-74, two rows of a DEST (the parameter's number + 1, 0 off) and an ADD (bipolar about
64). A note at velocity v adds (ADD - 64) x v / 127 steps to DEST, from its note-on to the next.

The render tests read a parameter as the DSP hears it (--trace-param: track 1's, in 1/256 of a
step, once a block) through the built binary (engines/m2k/build.sh); skipped without it.
"""
import json
import os
import subprocess

import pytest

from engines.m2k import gen_definitions

BINARY = os.path.join(os.path.dirname(__file__), "..", "engines", "m2k", "build", "m2k-jack")
M2K_DIR = os.path.join(os.path.dirname(__file__), "..", "engines", "m2k", "definitions")
built = pytest.mark.skipif(not os.access(BINARY, os.X_OK), reason="m2k-jack isn't built")

SR = 44100
WDTH, WDTH_CC, VOL = 17, 73, 13                  # FILT WIDTH (MONO2K's parameter number, its CC); AMP VOL
VDST1, VADD1, VDST2, VADD2 = 71, 72, 73, 74


def nrpn(t: float, param: int, value: int, ch: int = 0) -> list[str]:
    """NRPN 1:<param> = value, as pushpin's MidiCCClient sends it."""
    cc = 176 + ch
    return [f"{t} {cc} 99 1", f"{t} {cc} 98 {param}", f"{t} {cc} 6 {value}"]


def vel_row(t: float, row: int, dest_param: int, add: int, ch: int = 0) -> list[str]:
    dst, add_p = (VDST1, VADD1) if row == 1 else (VDST2, VADD2)
    return nrpn(t, dst, dest_param + 1, ch) + nrpn(t, add_p, add, ch)


# WDTH in the middle, so it can move both ways (the INIT's is 127); well before the first note
SETUP = [f"0 176 {WDTH_CC} 64"]


def trace(tmp_path, lines: list[str], param: int, times: list[float]) -> list[int]:
    """Track 1's ``param`` (Q8) as the DSP read it at each of ``times`` (seconds)."""
    (tmp_path / "s.txt").write_text("\n".join(lines) + "\n")
    out = subprocess.run(
        [BINARY, "--render", str(tmp_path / "r.wav"), "--seconds", str(max(times) + 0.02),
         "--script", str(tmp_path / "s.txt"), "--trace-param", str(param)],
        check=True, capture_output=True, text=True).stderr
    blocks = [tuple(int(x) for x in line.split()) for line in out.splitlines() if line.strip()]
    return [[v for s, v in blocks if s <= t * SR][-1] for t in times]


def wdth_during_note(tmp_path, velocity: int, setup: list[str]) -> int:
    lines = SETUP + setup + [f"0.1 144 60 {velocity}", "0.3 128 60 0"]
    return trace(tmp_path, lines, WDTH, [0.2])[0]


@built
@pytest.mark.parametrize("velocity", [127, 64, 15])
def test_a_note_adds_add_scaled_by_its_velocity(tmp_path, velocity):
    got = wdth_during_note(tmp_path, velocity, vel_row(0, 1, WDTH, 64 + 32))
    assert got == 64 * 256 + 32 * 256 * velocity // 127


@built
def test_add_below_64_takes_away(tmp_path):
    assert wdth_during_note(tmp_path, 127, vel_row(0, 1, WDTH, 64 - 20)) == (64 - 20) * 256


@built
@pytest.mark.parametrize("setup", [vel_row(0, 1, WDTH, 64), vel_row(0, 1, -1, 127), []],
                         ids=["add-64", "dest-off", "nothing-set"])
def test_no_modulation_without_a_dest_and_an_add(tmp_path, setup):
    assert wdth_during_note(tmp_path, 127, setup) == 64 * 256


@built
def test_both_rows_add_up_on_one_dest(tmp_path):
    setup = vel_row(0, 1, WDTH, 64 + 10) + vel_row(0, 2, WDTH, 64 + 5)
    assert wdth_during_note(tmp_path, 127, setup) == (64 + 15) * 256


@built
def test_the_second_row_reaches_its_own_dest(tmp_path):
    lines = SETUP + vel_row(0, 1, WDTH, 64 + 10) + vel_row(0, 2, VOL, 64 - 8) + ["0.1 144 60 127"]
    vol_init = trace(tmp_path, ["0 144 60 127"], VOL, [0.05])[0]
    assert trace(tmp_path, lines, VOL, [0.2])[0] == vol_init - 8 * 256
    assert trace(tmp_path, lines, WDTH, [0.2])[0] == (64 + 10) * 256


@built
def test_it_holds_until_the_next_note_on_whose_velocity_replaces_it(tmp_path):
    lines = SETUP + vel_row(0, 1, WDTH, 64 + 32) + [
        "0.2 144 60 127", "0.3 128 60 0",             # let go: the release keeps it
        "0.5 144 60 32", "0.6 128 60 0"]
    # (before: once SETUP's WDTH has glided to 64)
    before, held, released, softer = trace(tmp_path, lines, WDTH, [0.19, 0.25, 0.4, 0.55])
    assert before == 64 * 256                         # no note yet
    assert held == released == (64 + 32) * 256
    assert softer == 64 * 256 + 32 * 256 * 32 // 127


@built
def test_the_add_is_14_bit(tmp_path):
    """CC 38 after CC 6: the fraction in 1/128 of a step (the core keeps 1/256)."""
    setup = vel_row(0, 1, WDTH, 64 + 16) + ["0 176 38 64"]   # ADD 80.5
    assert wdth_during_note(tmp_path, 127, setup) == 64 * 256 + 16 * 256 + 128


@built
def test_a_machine_turns_vel_off(tmp_path):
    lines = vel_row(0, 1, WDTH, 64 - 20) + ["0.05 176 14 0", f"0.06 176 {WDTH_CC} 64", "0.1 144 60 127"]
    assert trace(tmp_path, lines, WDTH, [0.2])[0] == 64 * 256


@built
def test_vel_is_the_tracks_own(tmp_path):
    """Track 2's VEL and notes leave track 1 (the one traced) alone."""
    lines = SETUP + vel_row(0, 1, WDTH, 64 + 32, ch=1) + ["0.1 145 60 127", "0.1 144 60 100"]
    assert trace(tmp_path, lines, WDTH, [0.2])[0] == 64 * 256


@built
def test_describe_exports_vel_after_mono2ks_parameters():
    d = json.loads(subprocess.run([BINARY, "--describe"], check=True, capture_output=True, text=True).stdout)
    assert d["param_count"] == 87
    assert [(p["param"], p["name"]) for p in d["params_all"][71:75]] == [
        (71, "VEL 1 DEST"), (72, "VEL 1 ADD"), (73, "VEL 2 DEST"), (74, "VEL 2 ADD")]
    assert all(m["kit"][71:75] == [0, 64, 0, 64] for m in d["machines"])


# ------------------------------------------------------------- the VEL page


def vel_page() -> dict:
    with open(os.path.join(M2K_DIR, "60_vel.json")) as f:
        return json.load(f)


def test_vel_page_is_in_slot_8_on_the_second_instrument_page():
    page = vel_page()
    assert page["name"] == "Velocity" and page["slot"] == 8


def test_vel_page_rows_are_device_dest_add_and_a_gap():
    controls = vel_page()["controls"]
    assert [c["$type"] for c in controls] == ["control-switch", "control-range", "control-spacer"] * 2
    assert gen_definitions.slots(controls) == 8          # (a switch shows its menu beside it: four knobs a row)
    add1, add2 = controls[1], controls[4]
    assert (add1["address"], add2["address"]) == ("/m2k/param/72", "/m2k/param/74")
    assert add1["bipolar"] == 1 and add1["display_center"] == 64 and (add1["min"], add1["max"]) == (0, 127)


def test_vel_destinations_are_the_lfos_and_send_dest_plus_one():
    switch = vel_page()["controls"][0]
    groups = {g["label"]: g["controls"][0]["items"] for g in switch["groups"]}
    assert list(groups) == ["Off", "Syn", "Amp", "Filt", "FX", "Dstr", "LFO 1", "LFO 2", "LFO 3"]
    assert groups["Off"][0]["onselect"] == {"$type": "message", "address": "/m2k/param/71", "value": 0}
    width = next(i for i in groups["Filt"] if i["onselect"]["value"] == WDTH + 1)
    assert width["onselect"]["address"] == "/m2k/param/71"
    assert switch["groups"][1]["controls"][0]["menu_label"] == "Vel Destination"
    # the second row's own DEST
    assert vel_page()["controls"][3]["groups"][0]["controls"][0]["items"][0]["onselect"]["address"] == "/m2k/param/73"


def test_lfo_pages_keep_their_destination_menu_label():
    with open(os.path.join(M2K_DIR, "50_lfo1.json")) as f:
        switch = json.load(f)["controls"][0]
    assert switch["groups"][1]["controls"][0]["menu_label"] == "LFO Destination"
    assert switch["groups"][1]["controls"][0]["items"][0]["onselect"]["address"] == "/cc/89"
