# SPDX-License-Identifier: GPL-3.0-only
"""Generate pushpin's device pages for mono2k tracks from the MONO2K core.

    python engines/m2k/gen_definitions.py                 # runs engines/m2k/build/m2k-jack --describe
    python engines/m2k/gen_definitions.py describe.json   # or reads a saved dump

Writes engines/m2k/definitions/*.json, the same format as Surge's device
definitions. Every control's address is "/cc/<number>"; on a mono2k track the
instrument's MidiCCClient turns those into MIDI CCs (see cc_client.py).
Parameters no page control reaches are "/m2k/param/<number>" (NRPN 1:<number>).

Also writes engines/m2k/sounds.json for saving and loading whole sounds
(m2k_state.py) and for the preset browser: every parameter's number, label and
CC (if any), each machine's INIT sound, and MONO2K's factory library.

  slot 0      one device per machine (SYN A-H). Its init selects the machine
              (CC 14) and sends the machine's whole INIT sound, so every page
              shows the values m2k-jack actually has.
  slots 1-7   AMP, FILT, FX, DSTR, LFO 1-3: always shown, one per slot.
  A machine's second page: BANK (DIGI-WAV only) and PTCH. An LFO's: TRCK.

The labels and INIT values come from MONO2K (GPL-3.0-only), which is why the
generated files live here and not in pushpin's MIT-licensed definitions/.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "definitions")
SOUNDS_PATH = os.path.join(HERE, "sounds.json")
BINARY = os.path.join(HERE, "build", "m2k-jack")

# page -> (file stem, device name, slot); file stems sort into display order.
# One device per slot (p-locks are stored by slot), all on the first page with
# the machine in slot 0 (engine.M2KEngine.always_shown_slots)
PAGES = {
    "AMP": ("10_amp", "AMP", 1),
    "FILT": ("20_filt", "FILT", 2),
    "FX": ("30_fx", "FX", 3),
    "DSTR": ("40_dstr", "DSTR", 4),
    "LFO1": ("50_lfo1", "LFO 1", 5),
    "LFO2": ("51_lfo2", "LFO 2", 6),
    "LFO3": ("52_lfo3", "LFO 3", 7),
}
# A process plays one track, so an LFO can only modulate its own: TRCK stays as INIT sets it.
HIDDEN_LABELS = {"TRCK", "-"}
# Frequencies whose one step is 1/8 octave: half a step per encoder click (m2k-jack takes 14-bit NRPN
# and glides between values, so the in-between values are heard)
FINE_STEP = 0.5
FINE_STEP_LABELS = {("FILT", "BASE"), ("FILT", "WDTH"), ("FX", "EQF"), ("FX", "DBAS")}

# DSTR's page: BITS FOLD XOR VERB (their CCs), then MONO2K's MOD effect, which
# no CC reaches (NRPN 1:<param>): its type as a menu, rate, depth and mix
DSTR_CCS = (16, 17, 18, 19)
MOD_TYPE, MOD_RATE, MOD_DEPTH, MOD_MIX = 66, 67, 68, 69
MOD_TYPES = ["CHOR", "FLNG", "PHAS"]          # MONO2K's own names (m2k_ui.c, K_MODT)
MENU_CLICKS_PER_ITEM = 4


# The LFO pages' destination: a device switch (knob 0) whose groups each hold a
# menu of that device's parameters (knob 1), as Surge's filter-type pages do.
# MONO2K's DEST is the target parameter's number + 1 (0: off).
# SYN's entries name the current machine's own controls (label_from: the
# machine device in slot 0, its k-th control); "SYN A".."SYN H" until known.
LFO_TARGETS = [
    ("SYN", [(p, f"SYN {'ABCDEFGH'[p]}") for p in range(8)]),
    ("AMP", list(range(8, 16))),
    ("FILT", list(range(16, 24))),
    ("FX", list(range(24, 32))),
    ("DSTR", [32, 33, 34, 35, 66, 67, 68, 69]),
    ("LFO 1", list(range(44, 50))),              # (not an LFO's own TRCK and DEST)
    ("LFO 2", list(range(52, 58))),
    ("LFO 3", list(range(60, 66))),
]
LFO_TRCK, LFO_DEST = 0, 1                         # an LFO page's params by position
CLICKS_PER_ITEM = 4


def lfo_target_switch(dest_cc: int, labels: dict[int, str]) -> dict:
    address = cc_address(dest_cc)

    def item(label: str, value: int, label_from: dict | None = None) -> dict:
        entry = {"$type": "menu-item", "label": label,
                 "onselect": {"$type": "message", "address": address, "value": value}}
        if label_from is not None:
            entry["label_from"] = label_from
        return entry

    def group(label: str, items: list[dict]) -> dict:
        return {"$type": "group", "label": label, "controls": [
            {"$type": "control-menu", "menu_label": "LFO DESTINATION", "step": 1 / CLICKS_PER_ITEM, "items": items}]}

    groups = [group("OFF", [item("OFF", 0)])]
    for device, params in LFO_TARGETS:
        entries = [p if isinstance(p, tuple) else (p, labels.get(p, str(p))) for p in params]
        groups.append(group(device, [
            item(label, p + 1, {"slot": 0, "control": p} if device == "SYN" else None) for p, label in entries]))
    return {"$type": "control-switch", "menu_label": "DEVICE", "clicks_per_group": CLICKS_PER_ITEM,
            "select_by_value": True, "groups": groups}


def lfo_track_menu(trck_cc: int) -> dict:
    """The track an LFO modulates, in m2k-jack's own encoding for pushpin:
    0 the LFO's own track, 1-8 track 1-8 (MONO2K's own needs >127 for 7-8)."""
    address = cc_address(trck_cc)
    items = [("OWN", 0)] + [(f"TRK {n}", n) for n in range(1, 9)]
    return {
        "$type": "control-menu",
        "menu_label": "LFO TRACK",
        "step": 1 / CLICKS_PER_ITEM,
        "items": [{"$type": "menu-item", "label": label,
                   "onselect": {"$type": "message", "address": address, "value": value}} for label, value in items],
    }


def choice_value(i: int, n: int) -> int:
    """The middle of choice i of n on 0-127, as MONO2K's factory encodes it."""
    return (i * 128 + 64) // n

def cc_address(cc: int) -> str:
    return f"/cc/{cc}"


def param_address(param: int) -> str:
    return f"/m2k/param/{param}"


def cc_by_param(describe: dict) -> dict[int, int]:
    """Parameter number -> its CC, for the parameters a page control reaches."""
    ccs = {p["id"]: p["cc"] for p in describe["params"]}
    for s in describe["machines"][0]["syn"]:
        ccs[s["id"]] = s["cc"]
    return ccs


# ------------------------------------------------- MONO2K's own words for values
#
# m2k-jack --describe gives, for every parameter, what MONO2K's screen shows
# for each value 0-127 (m2k_ui.c's fmt(): a text and a unit) and, for a choice
# (a wave, a mode, a ratio), which choice each value is. A choice, or anything
# with few enough distinct values (BITS), becomes a menu of them; a quantity
# (a time, a frequency, a note length) stays a knob that shows the words.

MAX_MENU_ITEMS = 24                               # (FM+'s 24 ratios; a 128-value quantity stays a knob)
K_NUM, K_BI = 0, 1                                # plain numbers: nothing to name

# param number -> its address, filled by build() (a label table may follow another parameter)
ADDRESS_OF: dict[int, str] = {}


def value_label(text: str, unit: str) -> str:
    """One value's words, short enough for a Push column."""
    if not unit:
        return text
    if unit.startswith("/"):                      # DTIM: 37 "/256 NOTE" -> 37/256
        return text + unit.split()[0]
    if unit.startswith("X "):                     # the drums' sweep: 1.5 "X PITCH" -> 1.5X
        return text + "X"
    if len(unit) > 5 or unit in ("STILL", "RATIO"):   # ("PREV TRK"; a ratio is plain; STOP's "STILL")
        return text
    return f"{text} {unit}"


def value_labels(table: dict) -> list[str]:
    return [value_label(t, u) for t, u in zip(table["text"], table["unit"])]


def runs(keys: list) -> list[tuple[int, int]]:
    """The [lo, hi] runs of equal keys over 0-127."""
    out, lo = [], 0
    for v in range(1, len(keys) + 1):
        if v == len(keys) or keys[v] != keys[lo]:
            out.append((lo, v - 1))
            lo = v
    return out


def value_menu(label: str, address: str, labels: list[str], keys: list) -> dict:
    items = [
        {"$type": "menu-item", "label": labels[(lo + hi + 1) // 2], "range": [lo, hi],
         "onselect": {"$type": "message", "address": address, "value": (lo + hi + 1) // 2}}
        for lo, hi in runs(keys)
    ]
    clicks = CLICKS_PER_ITEM if len(items) <= 8 else 2
    return {"$type": "control-menu", "menu_label": label, "step": 1 / clicks, "items": items}


def described(c: dict, param: dict) -> dict:
    """``c`` (a knob) as MONO2K names its values: a menu, or a knob with words."""
    kind = param.get("kind", K_NUM)
    if kind in (K_NUM, K_BI) or ("values" not in param and "values_by" not in param):
        return c
    if "values_by" in param:
        by = param["values_by"]
        tables = [value_labels(t) for t in by["tables"]]
        c["value_labels_by"] = {"address": ADDRESS_OF.get(by["param"], param_address(by["param"])),
                                "choices": len(tables), "tables": tables}
        return c
    labels = value_labels(param["values"])
    keys = param.get("choice") or labels
    if "choice" in param or len(runs(keys)) <= MAX_MENU_ITEMS:
        return value_menu(c["label"], c["address"], labels, keys)
    c["value_labels"] = labels
    c.pop("display_center", None)                 # (the words say which way)
    return c


def display_name(param: dict) -> str:
    """MONO2K's full name for a parameter (ATCK -> ATTACK), its four letters where it has none."""
    name = param.get("name") or ""
    return name if name and name != "-" else param["label"]


# ------------------------------------------------ units MONO2K's screen leaves out
#
# MONO2K shows some parameters as bare 0-127 though the DSP gives them a unit
# (m2k_dsp.c). These get their words here, from the same formulas.

# AMP's HOLD: v / 32 of a beat (m2k_ui.c's K_AHLD), 127 holding until the note ends. Its time
# depends on the tempo, so the control works it out as it draws (osc_controls.OSCControl)
HOLD_BEATS_PER_VALUE = 1 / 32
INF = 127


def octaves_by_env(v: int) -> str:
    """BASE/WIDTH BY ENV: the envelope at full moves the cutoff 7 d|d| / 256 filter steps of
    1/8 octave, d = v - 64 (m2k_dsp.c)."""
    d = v - 64
    octs = 7 * d * abs(d) / 256 / 8
    return "0 OCT" if d == 0 else f"{octs:+.1f} OCT" if abs(octs) < 10 else f"{octs:+.0f} OCT"


def start_phase(v: int) -> str:
    """An LFO's PHAS: v << 25 of the 2^32 cycle, so 360 / 128 degrees a step."""
    return f"{round(v * 360 / 128)}°"


UNIT_LABELS = {
    ("FILT", "B-OF"): octaves_by_env,
    ("FILT", "W-OF"): octaves_by_env,
    **{(f"LFO{n}", "PHAS"): start_phase for n in (1, 2, 3)},
}


def with_units(c: dict, page: str | None, label: str) -> dict:
    if c.get("$type") != "control-range":
        return c
    if (page, label) == ("AMP", "HOLD"):
        c["tempo_time"] = {"beats_per_value": HOLD_BEATS_PER_VALUE, "inf_value": INF}
    elif (page, label) in UNIT_LABELS:
        c["value_labels"] = [UNIT_LABELS[page, label](v) for v in range(128)]
        c.pop("display_center", None)
    return c


def control(cc: int, param: dict, page: str | None = None, address: str | None = None) -> dict:
    if param["label"] in HIDDEN_LABELS:
        return {"$type": "control-spacer"}
    c = {
        "$type": "control-range",
        "label": display_name(param),
        "address": address or cc_address(cc),
        "min": 0,
        "max": param["max"],
    }
    if param["bipolar"]:
        c["bipolar"] = 1
    if (page, param["label"]) in FINE_STEP_LABELS:
        c["step"] = FINE_STEP
    if page and page.startswith("LFO") and param["label"] == "DPTH":
        c["bipolar"] = 1                          # MONO2K's LFO depth is signed about 64
        c["display_center"] = 64                  # (shown -64..+63 where the words aren't known)
    return with_units(described(c, param), page, param["label"])


# A machine page's second page: BANK (DIGI-WAV only, MONO2K's own wave bank
# choice) then PTCH, the track's pitch in semitones
WAVE_MACHINE = "DIGI-WAV"
WAVE_BANK = 70
BANKS = ["M2K", "M64"]                            # MONO2K's 32 waves, the 64 (m2k_ui.c, K_WBNK)
PTCH_CC = 20


def wave_bank_menu() -> dict:
    return {
        "$type": "control-menu",
        "menu_label": "WAVE BANK",
        "step": 1 / CLICKS_PER_ITEM,
        "items": [
            {"$type": "menu-item", "label": name,
             "onselect": {"$type": "message", "address": param_address(WAVE_BANK), "value": choice_value(i, len(BANKS))}}
            for i, name in enumerate(BANKS)
        ],
    }


def machine_page_two(machine: dict, ptch: dict | None) -> list[dict]:
    if ptch is None:
        return []
    first = wave_bank_menu() if machine["name"] == WAVE_MACHINE else {"$type": "control-spacer"}
    pitch = control(PTCH_CC, ptch)
    if "value_labels" not in pitch:
        pitch["display_center"] = 64              # semitones either way
    return [first, pitch]


def machine_device(machine: dict, machine_cc: int, ccs: dict[int, int] | None = None,
                   ptch: dict | None = None) -> dict:
    init = [{"$type": "message", "$comment": "machine", "address": cc_address(machine_cc), "value": machine["index"]}]
    init += [
        {"$type": "message", "address": cc_address(int(cc)), "value": value}
        for cc, value in machine["init"].items()
    ]
    # The rest of its INIT sound, so pushpin knows every parameter of the track
    # (what m2k_state.py saves) from the moment a machine is chosen
    if ccs is not None and "kit" in machine:
        init += [
            {"$type": "message", "address": param_address(param), "value": value}
            for param, value in enumerate(machine["kit"])
            if param not in ccs
        ]
    return {
        "name": machine["name"],
        "slot": 0,
        "init": init,
        "controls": [control(s["cc"], s["param"]) for s in machine["syn"]] + machine_page_two(machine, ptch),
    }


def param_control(param: int, label: str, mx: int = 127) -> dict:
    return {"$type": "control-range", "label": label, "address": param_address(param), "min": 0, "max": mx}


def mod_type_menu() -> dict:
    return {
        "$type": "control-menu",
        "menu_label": "MOD TYPE",
        "step": 1 / MENU_CLICKS_PER_ITEM,
        "items": [
            {
                "$type": "menu-item",
                "label": name,
                "onselect": {"$type": "message", "address": param_address(MOD_TYPE),
                             "value": choice_value(i, len(MOD_TYPES))},
            }
            for i, name in enumerate(MOD_TYPES)
        ],
    }


def dstr_controls(params: list[dict], labels: dict[int, str], all_params: dict[int, dict] | None = None) -> list[dict]:
    by_cc = {p["cc"]: p for p in params}
    controls = [control(cc, by_cc[cc]["param"], "DSTR") for cc in DSTR_CCS]
    for p in (MOD_TYPE, MOD_RATE, MOD_DEPTH, MOD_MIX):
        info = (all_params or {}).get(p)
        if info is not None and "values" in info:
            controls.append(control(0, dict(info, max=127, bipolar=False), "DSTR", param_address(p)))
        elif p == MOD_TYPE:
            controls.append(mod_type_menu())
        else:
            controls.append(param_control(p, labels.get(p, str(p))))
    return controls


def page_devices(params: list[dict], labels: dict[int, str] | None = None,
                 all_params: dict[int, dict] | None = None) -> dict[str, dict]:
    devices = {}
    for page, (stem, name, slot) in PAGES.items():
        if page == "DSTR" and labels is not None:
            controls = dstr_controls(params, labels, all_params)
        elif page.startswith("LFO") and labels is not None:
            lfo = [p for p in params if p["page"] == page]
            controls = [lfo_target_switch(lfo[LFO_DEST]["cc"], labels)]
            controls += [control(p["cc"], p["param"], page) for i, p in enumerate(lfo) if i not in (LFO_TRCK, LFO_DEST)]
            controls.append(lfo_track_menu(lfo[LFO_TRCK]["cc"]))      # control 9: the second page
        else:
            controls = [control(p["cc"], p["param"], page) for p in params if p["page"] == page]
        devices[stem] = {"name": name, "slot": slot, "init": [], "controls": controls}
    return devices


def build(describe: dict) -> dict[str, dict]:
    # (the LFOs' destination menus name their targets in full too)
    labels = {p["param"]: display_name(p) for p in describe["params_all"]} if "params_all" in describe else None
    all_params = {p["param"]: p for p in describe.get("params_all", [])}
    ADDRESS_OF.clear()
    ADDRESS_OF.update({p["id"]: cc_address(p["cc"]) for p in describe["params"] if "id" in p})
    files = page_devices(describe["params"], labels, all_params)
    ccs = cc_by_param(describe) if "kit" in describe["machines"][0] else None
    ptch = next((p["param"] for p in describe["params"] if p["cc"] == PTCH_CC), None)
    for m in describe["machines"]:
        files[f"00_machine_{m['index']:02d}"] = machine_device(m, describe["machine_cc"], ccs, ptch)
    return files


def build_sounds(describe: dict) -> dict:
    """sounds.json: what m2k_state.py and the preset browser need."""
    ccs = cc_by_param(describe)
    return {
        "machine_cc": describe["machine_cc"],
        "param_count": describe["param_count"],
        "params": [
            {"param": p["param"], "label": p["label"], "name": p["name"], "cc": ccs.get(p["param"])}
            for p in describe["params_all"]
        ],
        "machines": [{"index": m["index"], "name": m["name"], "kit": m["kit"]} for m in describe["machines"]],
        "categories": describe["categories"],
        "library": [
            {k: s[k] for k in ("name", "category", "machine", "root", "what", "kit")}
            for s in describe["library"]
        ],
    }


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        with open(argv[1]) as f:
            describe = json.load(f)
    else:
        describe = json.loads(subprocess.run([BINARY, "--describe"], check=True, capture_output=True, text=True).stdout)
    os.makedirs(OUT_DIR, exist_ok=True)
    for name in os.listdir(OUT_DIR):
        if name.endswith(".json"):
            os.remove(os.path.join(OUT_DIR, name))
    files = build(describe)
    for stem, device in files.items():
        with open(os.path.join(OUT_DIR, f"{stem}.json"), "w") as f:
            json.dump(device, f, indent="\t")
            f.write("\n")
    print(f"wrote {len(files)} device definitions to {OUT_DIR}")
    with open(SOUNDS_PATH, "w") as f:
        json.dump(build_sounds(describe), f, indent=1)
        f.write("\n")
    print(f"wrote {SOUNDS_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
