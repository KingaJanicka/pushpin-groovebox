"""Write docs/manual/devices.json, the device pages the website's manual draws.

The manual's Push 2 screen shows the same devices a track has in Pushpin:
Surge XT's oscillators, filters, amp and effects on the first page and its
LFOs, macros and mod matrix on the second; mono2k's machine, amp, filter, FX,
distortion and LFOs, then velocity, key tracking and feedback. This reads the
definition files the app loads and lays each device's controls out in pages of
eight, as OSCDevice.pages does.

    python tools/build_manual_devices.py          # rewrite the file
    python tools/build_manual_devices.py --check  # exit 1 if it is out of date

tests/test_manual_data.py runs the check, so edit a definition and rerun this.
"""

from __future__ import annotations

import hashlib
import json
import sys
from glob import glob
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "manual" / "devices.json"

ENGINES = {
    "surge": {
        "label": "Surge XT",
        "folders": ["definitions/device_definitions", "definitions/effect_definitions", "definitions/modulation_definitions"],
        # Slots 0-7 are the first instrument page, 8-15 the second (MODULATION_SLOTS)
        "pages": [list(range(0, 8)), list(range(8, 16))],
        # What the manual shows in a slot that holds one of several devices
        "defaults": {0: "classic_1", 1: "modern_2", 5: "delay_1", 6: "chorus_2", 7: "reverb2_global"},
        # Slot names for the device menu's title
        "slot_names": {0: "Osc 1", 1: "Osc 2", 2: "Filters", 3: "Filter EG", 4: "Amp", 5: "FX 1", 6: "FX 2", 7: "FX 3",
                       8: "LFO 1", 9: "LFO 2", 10: "LFO 3", 11: "LFO 4", 12: "LFO 5", 13: "LFO 6", 14: "Macros", 15: "Mod Matrix"},
    },
    "mono2k": {
        "label": "Monomachine",
        "folders": ["engines/m2k/definitions"],
        "pages": [list(range(0, 8)), list(range(8, 16))],
        "defaults": {0: "00_machine_05"},
        "slot_names": {0: "Machine"},
    },
}


def demo_fraction(*keys: str) -> float:
    """A steady made-up knob position, so the example pages don't all sit at zero."""
    digest = hashlib.sha1("/".join(keys).encode()).digest()
    return round(0.15 + 0.7 * digest[0] / 255, 2)


def item_label(item: dict) -> str:
    """OSCMenuItem's static label (an empty one shows empty, as on the Push)."""
    return item.get("label", "")


def flat_label(control: dict) -> str:
    """What Instrument._slot_control_label names a device's control by: its menu
    label, else its label, else "-" (a spacer)."""
    return control.get("menu_label") or control.get("label") or "-"


# Surge's recorded words for knob values (tools/surge_value_labels.py), applied
# as modes/device_definitions.py apply_value_tables does
SURGE_LABELS = json.loads((ROOT / "definitions" / "surge_value_labels.json").read_text())

# Every value table the controls use, stored once: id -> words
TABLES: dict[str, list[str]] = {}


def table_id(words: list[str]) -> str:
    key = hashlib.sha1(json.dumps(words).encode()).hexdigest()[:10]
    TABLES[key] = words
    return key


def value_words(control: dict, device: str, group: str) -> dict:
    """What OSCControl.display_text uses instead of the bare number: Surge's
    value_table, mono2k's value_labels or value_labels_by, or display_center."""
    out: dict = {}
    stem = device.split("/", 1)[1]
    recorded = SURGE_LABELS["devices"].get(stem, {}).get(group, {}).get(control.get("address"))
    if recorded in SURGE_LABELS["tables"]:
        out["table"] = table_id(SURGE_LABELS["tables"][recorded])
    if control.get("value_labels"):
        out["labels"] = table_id(control["value_labels"])
    by = control.get("value_labels_by")
    if by:
        out["labels_by"] = {"address": by["address"], "choices": int(by.get("choices", len(by["tables"]))),
                            "tables": [table_id(t) for t in by["tables"]]}
    if control.get("display_center") is not None:
        out["center"] = control["display_center"]
    return out


def convert(control: dict, device: str, group: str = "") -> dict | None:
    """One control as the manual draws it; None for a spacer."""
    kind = control.get("$type")
    if kind in ("control-spacer", "control-spacer-address"):
        return None
    if kind == "control-range":
        lo, hi = control.get("min", 0), control.get("max", 1)
        value = lo + (hi - lo) * demo_fraction(device, control.get("label", ""), control.get("address", ""))
        value = round(value) if hi - lo > 2 else round(value, 2)
        return {"t": "range", "label": control.get("label", ""), "address": control.get("address"), "min": lo, "max": hi,
                "bipolar": bool(control.get("bipolar")), "value": value, **value_words(control, device, group)}
    if kind == "control-menu":
        raw = control.get("items", [])
        items = [item_label(i) for i in raw] or ["-"]
        address = next((i.get("onselect", {}).get("address") for i in raw if i.get("onselect")), None)
        out = {"t": "menu", "label": control.get("menu_label"), "address": address, "items": items, "value": 0,
               # what each item sends: a control whose words follow this menu reads it
               "values": [i.get("onselect", {}).get("value") for i in raw]}
        # items named after another device's control (label_from): {item: [slot, control]}
        named = {str(n): [int(i["label_from"]["slot"]), int(i["label_from"]["control"])] for n, i in enumerate(raw) if i.get("label_from")}
        if named:
            out["from"] = named
        return out
    if kind == "control-switch":
        groups = [{"label": g.get("label", ""), "controls": [convert(c, device, g.get("label", "")) for c in g.get("controls", [])]}
                  for g in control.get("groups", [])]
        return {"t": "switch", "label": control.get("menu_label"), "groups": groups, "value": min(1, len(groups) - 1)}
    if kind == "control-macro":
        return {"t": "range", "label": control.get("label", "Macro"), "min": 0, "max": 1, "bipolar": False,
                "value": demo_fraction(device, control.get("label", ""))}
    return {"t": "range", "label": control.get("label", kind or "?"), "min": 0, "max": 1, "bipolar": False, "value": 0}


def size(control: dict | None) -> int:
    if control and control["t"] == "switch":
        return max((len(g["controls"]) for g in control["groups"]), default=0) + 1
    return 1


def pages_of(controls: list[dict | None]) -> list[list[dict | None]]:
    """Pages of eight, as OSCDevice.pages: a control that won't fit starts a new
    page, and a switch is followed by its active group's controls."""
    pages: list[list[dict | None]] = [[]]
    for control in controls:
        if len(pages[-1]) + size(control) > 8:
            pages[-1] += [None] * (8 - len(pages[-1]))
            pages.append([])
        pages[-1].append(control)
        if control and control["t"] == "switch" and control["groups"]:
            pages[-1] += control["groups"][control["value"]]["controls"]
    pages[-1] += [None] * (8 - len(pages[-1]))
    return [page[:8] for page in pages]


def mod_matrix() -> list[list[dict | None]]:
    """ModMatrixDevice draws its own screen: source, destination, depth, and its three actions."""
    def menu(items, value):
        return {"t": "menu", "label": None, "items": items, "value": value}
    return [[
        menu(["Macros", "LFOs", "Voice"], 1),
        menu(["LFO 1", "LFO 2", "LFO 3", "LFO 4"], 0),
        menu(["Osc 1", "Filters", "Filter EG", "Amp"], 1),
        menu(["F1 Freq", "F1 Res", "Depth", "Keytrack"], 0),
        {"t": "range", "label": "Depth", "min": -1, "max": 1, "bipolar": True, "value": 0.4},
        {"t": "label", "label": "Set Mapping"},
        {"t": "label", "label": "Delete Mapping"},
        {"t": "label", "label": "Scroll Mappings"},
    ]]


def build() -> dict:
    TABLES.clear()
    out: dict = {"$comment": "Generated by tools/build_manual_devices.py from the definition files; don't edit by hand.",
                 "engines": {}, "devices": {}, "tables": TABLES}
    for engine, spec in ENGINES.items():
        slots: dict[int, list[str]] = {}
        for folder in spec["folders"]:
            for path in sorted(glob(str(ROOT / folder / "*.json"))):
                definition = json.loads(Path(path).read_text())
                key = f"{engine}/{Path(path).stem}"
                slot = int(definition["slot"])
                if Path(path).stem == "mod_matrix":
                    pages = mod_matrix()
                else:
                    pages = pages_of([convert(c, key) for c in definition.get("controls", [])])
                out["devices"][key] = {"label": definition.get("name", Path(path).stem), "slot": slot, "pages": pages,
                                       "names": [flat_label(c) for c in definition.get("controls", [])]}
                slots.setdefault(slot, []).append(key)
        defaults = {slot: f"{engine}/{stem}" for slot, stem in spec["defaults"].items()}
        out["engines"][engine] = {
            "label": spec["label"],
            "pages": [[s for s in page if s in slots] for page in spec["pages"]],
            # ADD DEVICE lists a slot's devices by name (OSCMode.get_current_slot_devices
            # sorts on device.label), not in file order
            "slots": {str(s): sorted(keys, key=lambda k: out["devices"][k]["label"]) for s, keys in sorted(slots.items())},
            "shown": {str(s): defaults.get(s, keys[0]) for s, keys in sorted(slots.items())},
            "slot_names": {str(s): name for s, name in spec["slot_names"].items()},
        }
    return out


def render() -> str:
    return json.dumps(build(), ensure_ascii=False, separators=(",", ":")) + "\n"


if __name__ == "__main__":
    text = render()
    if "--check" in sys.argv:
        current = OUT.read_text() if OUT.exists() else ""
        sys.exit(0 if current == text else 1)
    OUT.write_text(text)
    print(f"wrote {OUT.relative_to(ROOT)} ({len(text) // 1024} KB)")
