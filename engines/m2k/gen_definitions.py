# SPDX-License-Identifier: GPL-3.0-only
"""Generate pushpin's device pages for mono2k tracks from the MONO2K core.

    python engines/m2k/gen_definitions.py                 # runs engines/m2k/build/m2k-jack --describe
    python engines/m2k/gen_definitions.py describe.json   # or reads a saved dump

Writes engines/m2k/definitions/*.json, the same format as Surge's device
definitions. Every control's address is "/cc/<number>"; on a mono2k track the
instrument's MidiCCClient turns those into MIDI CCs (see cc_client.py).

  slot 0      one device per machine (SYN A-H). Its init selects the machine
              (CC 14) and sends the machine's whole INIT sound, so every page
              shows the values m2k-jack actually has.
  slots 2-4   AMP, FILT, FX, DSTR: always shown.
  slots 8-10  LFO 1-3: the modulation page.

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
BINARY = os.path.join(HERE, "build", "m2k-jack")

# page -> (file stem, device name, slot); file stems sort into display order
PAGES = {
    "AMP": ("10_amp", "AMP", 2),
    "FILT": ("20_filt", "FILT", 3),
    "FX": ("30_fx", "FX", 4),
    "DSTR": ("40_dstr", "DSTR", 4),
    "LFO1": ("50_lfo1", "LFO 1", 8),
    "LFO2": ("51_lfo2", "LFO 2", 9),
    "LFO3": ("52_lfo3", "LFO 3", 10),
}
# A process plays one track, so an LFO can only modulate its own: TRCK stays as INIT sets it.
HIDDEN_LABELS = {"TRCK", "-"}


def cc_address(cc: int) -> str:
    return f"/cc/{cc}"


def control(cc: int, param: dict) -> dict:
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
    return c


def machine_device(machine: dict, machine_cc: int) -> dict:
    init = [{"$type": "message", "$comment": "machine", "address": cc_address(machine_cc), "value": machine["index"]}]
    init += [
        {"$type": "message", "address": cc_address(int(cc)), "value": value}
        for cc, value in machine["init"].items()
    ]
    return {
        "name": machine["name"],
        "slot": 0,
        "init": init,
        "controls": [control(s["cc"], s["param"]) for s in machine["syn"]],
    }


def page_devices(params: list[dict]) -> dict[str, dict]:
    devices = {}
    for page, (stem, name, slot) in PAGES.items():
        devices[stem] = {
            "name": name,
            "slot": slot,
            "init": [],
            "controls": [control(p["cc"], p["param"]) for p in params if p["page"] == page],
        }
    return devices


def build(describe: dict) -> dict[str, dict]:
    files = page_devices(describe["params"])
    for m in describe["machines"]:
        files[f"00_machine_{m['index']:02d}"] = machine_device(m, describe["machine_cc"])
    return files


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
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
