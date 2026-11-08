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
LFO_TARGETS = [
    ("SYN", [(p, f"SYN {'ABCDEFGH'[p]}") for p in range(8)]),
    ("AMP", list(range(8, 16))),
    ("FILT", list(range(16, 24))),
    ("FX", list(range(24, 32))),
    ("DSTR", [32, 33, 34, 35, 66, 67, 68, 69]),
    ("TRK", list(range(36, 42))),
    ("LFO 1", list(range(44, 50))),              # (not an LFO's own TRCK and DEST)
    ("LFO 2", list(range(52, 58))),
    ("LFO 3", list(range(60, 66))),
]
LFO_TRCK, LFO_DEST = 0, 1                         # an LFO page's params by position
CLICKS_PER_ITEM = 4


def lfo_target_switch(dest_cc: int, labels: dict[int, str]) -> dict:
    address = cc_address(dest_cc)

    def item(label: str, value: int) -> dict:
        return {"$type": "menu-item", "label": label,
                "onselect": {"$type": "message", "address": address, "value": value}}

    def group(label: str, items: list[dict]) -> dict:
        return {"$type": "group", "label": label, "controls": [
            {"$type": "control-menu", "menu_label": "DEST", "step": 1 / CLICKS_PER_ITEM, "items": items}]}

    groups = [group("OFF", [item("OFF", 0)])]
    for device, params in LFO_TARGETS:
        entries = [p if isinstance(p, tuple) else (p, labels.get(p, str(p))) for p in params]
        groups.append(group(device, [item(label, p + 1) for p, label in entries]))
    return {"$type": "control-switch", "clicks_per_group": CLICKS_PER_ITEM, "select_by_value": True,
            "groups": groups}


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


def control(cc: int, param: dict, page: str | None = None) -> dict:
    if param["label"] in HIDDEN_LABELS:
        return {"$type": "control-spacer"}
    c = {
        "$type": "control-range",
        "label": param["label"],
        "address": cc_address(cc),
        "min": 0,
        "max": param["max"],
    }
    if param["bipolar"]:
        c["bipolar"] = 1
    if (page, param["label"]) in FINE_STEP_LABELS:
        c["step"] = FINE_STEP
    return c


def machine_device(machine: dict, machine_cc: int, ccs: dict[int, int] | None = None) -> dict:
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
        "controls": [control(s["cc"], s["param"]) for s in machine["syn"]],
    }


def param_control(param: int, label: str, mx: int = 127) -> dict:
    return {"$type": "control-range", "label": label, "address": param_address(param), "min": 0, "max": mx}


def mod_type_menu() -> dict:
    return {
        "$type": "control-menu",
        "menu_label": "TYPE",
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


def dstr_controls(params: list[dict], labels: dict[int, str]) -> list[dict]:
    by_cc = {p["cc"]: p for p in params}
    controls = [control(cc, by_cc[cc]["param"], "DSTR") for cc in DSTR_CCS]
    controls.append(mod_type_menu())
    controls += [param_control(p, labels.get(p, str(p))) for p in (MOD_RATE, MOD_DEPTH, MOD_MIX)]
    return controls


def page_devices(params: list[dict], labels: dict[int, str] | None = None) -> dict[str, dict]:
    devices = {}
    for page, (stem, name, slot) in PAGES.items():
        if page == "DSTR" and labels is not None:
            controls = dstr_controls(params, labels)
        elif page.startswith("LFO") and labels is not None:
            lfo = [p for p in params if p["page"] == page]
            controls = [lfo_target_switch(lfo[LFO_DEST]["cc"], labels)]
            controls += [control(p["cc"], p["param"], page) for i, p in enumerate(lfo) if i not in (LFO_TRCK, LFO_DEST)]
        else:
            controls = [control(p["cc"], p["param"], page) for p in params if p["page"] == page]
        devices[stem] = {"name": name, "slot": slot, "init": [], "controls": controls}
    return devices


def build(describe: dict) -> dict[str, dict]:
    labels = {p["param"]: p["label"] for p in describe["params_all"]} if "params_all" in describe else None
    files = page_devices(describe["params"], labels)
    ccs = cc_by_param(describe) if "kit" in describe["machines"][0] else None
    for m in describe["machines"]:
        files[f"00_machine_{m['index']:02d}"] = machine_device(m, describe["machine_cc"], ccs)
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
