"""Record how Surge XT shows every knob's values, for the Push display.

    "/Applications/Surge XT.app/Contents/MacOS/surge-xt-cli" \\
        --osc-in-port=19030 --osc-out-port=19040 --no-stdin &
    python tools/surge_value_labels.py      # writes definitions/surge_value_labels.json

Surge sends nothing back when pushpin sets a parameter, so the app can't ask
it for "62.50 ms" as a knob turns (querying every click made the knobs jump).
Instead, as gen_definitions.py does for mono2k, this records Surge's own words
ahead of time: each control-range is set to 101 points from its min to its
max (each whole value for an int parameter) and Surge asked what it shows,
in the mode the control appears in (Twist's engine, Nimbus' mode, ...).

The tables are keyed by definition, group and address, and shared when
equal; modes/device_definitions.py hands them to the controls as
"value_table". A parameter whose words depend on a modifier the page can
toggle (a delay time's tempo sync) gets none: Surge doesn't report modifiers,
so pushpin couldn't tell which words apply.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, ROOT)

import surge_snapshot  # noqa: E402

OUT = os.path.join(ROOT, "definitions", "surge_value_labels.json")
FLOAT_SAMPLES = 101          # 0.00, 0.01, ... 1.00: every value a knob can reach
TOP = ""                     # (the group key of controls outside any switch)
# Surge's longer unit names, shortened for an eighth of the Push display
SHORT_UNITS = {" semitones": " st", " semitone": " st", " octaves": " oct", " octave": " oct"}


def shorten(word: str) -> str:
    for long, short in SHORT_UNITS.items():
        if word.endswith(long) or f"{long} " in word:
            word = word.replace(long, short)
    return word


class Surge(surge_snapshot.Surge):
    """Waits for the answer instead of a fixed time: ~100k queries."""

    def __init__(self) -> None:
        self.arrived = threading.Event()
        super().__init__()

    def _received(self, address, *args) -> None:
        super()._received(address, *args)
        self.arrived.set()

    def shown(self, address: str, value: float) -> str | None:
        """What Surge shows for ``address`` at ``value``. Waits for an answer
        that carries the value: Surge smooths some parameters (the macros) and
        answers with the value on its way there."""
        self.client.send_message(address, float(value))
        for _ in range(40):
            self.drain()
            self.arrived.clear()
            self.client.send_message("/q" + address, [])
            deadline = time.monotonic() + 0.3
            while time.monotonic() < deadline:
                self.arrived.wait(0.05)
                self.arrived.clear()
                for received, args in self.drain():
                    if received == address and len(args) > 1:
                        if abs(float(args[0]) - float(value)) < 1e-4:
                            return str(args[1])
                        time.sleep(0.01)
                        deadline = 0.0          # (ask again)
        return None


def samples(kind: str, lo: float, hi: float) -> list[float]:
    if kind in ("int", "bool"):
        return [float(v) for v in range(int(lo), int(hi) + 1)]
    return [round(lo + (hi - lo) * i / (FLOAT_SAMPLES - 1), 6) for i in range(FLOAT_SAMPLES)]


# Modifiers that change how a value reads (1/4 note instead of ms, a wider
# range); enable/deform don't
WORD_MODIFIERS = ("/tempo_sync+", "/extend+", "/abs+")


def toggled_modifiers(definition: dict) -> set[str]:
    """Parameters whose words a menu on the page changes (".../tempo_sync+")."""
    out = set()
    def visit(controls):
        for control in controls:
            for item in control.get("items", []):
                address = item.get("onselect", {}).get("address", "")
                if address.endswith(WORD_MODIFIERS):
                    out.add(address.rsplit("/", 1)[0])
            for group in control.get("groups", []):
                visit(group["controls"])
    visit(definition["controls"])
    return out


def record(surge: Surge, definition: dict) -> dict:
    """{group label: {address: [words]}} for one definition."""
    surge.client.send_message("/patch/load", surge_snapshot.INIT_PATCH)
    time.sleep(0.6)
    for message in definition.get("init", []):
        surge.send(message["address"], float(message["value"]), wait=0.1)
    time.sleep(0.3)
    skip = toggled_modifiers(definition)
    out: dict = {}

    def table_for(control: dict, params: dict, values: dict) -> list[str] | None:
        address = control["address"]
        doc = params.get(address)
        if address in skip or doc is None or doc[1] not in ("float", "int", "bool"):
            return None
        kind = doc[1]
        words = [surge.shown(address, v) for v in samples(kind, float(control["min"]), float(control["max"]))]
        if address in values:
            surge.client.send_message(address, float(values[address]))   # (as it was)
        return words if all(w is not None for w in words) else None

    def visit(controls: list, group: str, params: dict, values: dict) -> None:
        for control in controls:
            kind = control["$type"]
            if kind == "control-range":
                table = table_for(control, params, values)
                if table:
                    out.setdefault(group, {})[control["address"]] = table
            elif kind == "control-switch":
                for g in control["groups"]:
                    if g.get("onselect"):
                        surge.send(g["onselect"]["address"], float(g["onselect"]["value"]), wait=0.1)
                    else:
                        first = g["controls"][0] if g["controls"] else None
                        if first and first["$type"] == "control-menu" and first["items"]:
                            value = surge_snapshot.value_of(first["items"][0])
                            if value is not None:
                                surge.send(first["items"][0]["onselect"]["address"], float(value), wait=0.1)
                    time.sleep(0.2)
                    group_params, group_values = surge.dump()
                    visit(g["controls"], g["label"], group_params, group_values)

    params, values = surge.dump()
    visit(definition["controls"], TOP, params, values)
    return out


def main() -> None:
    surge = Surge()
    time.sleep(0.2)
    if surge.query("/param/a/osc/1/type") is None:
        sys.exit("No reply from surge-xt-cli: start it first (see this file's docstring)")
    surge_snapshot.check_audio_running(surge)
    only = {os.path.normpath(arg) for arg in sys.argv[1:]}
    tables: dict[str, list[str]] = {}
    devices: dict = {}
    if only and os.path.exists(OUT):
        with open(OUT) as f:
            old = json.load(f)
        tables, devices = old["tables"], old["devices"]
    for folder in surge_snapshot.FOLDERS:
        for path in sorted(glob.glob(os.path.join(ROOT, folder, "*.json"))):
            rel = os.path.relpath(path, ROOT)
            if rel in surge_snapshot.SKIP or (only and rel not in only):
                continue
            with open(path) as f:
                definition = json.load(f)
            print(rel, flush=True)
            stem = os.path.splitext(os.path.basename(rel))[0]
            devices[stem] = {}
            for group, by_address in record(surge, definition).items():
                for address, words in by_address.items():
                    words = [shorten(w) for w in words]
                    key = hashlib.sha1(json.dumps(words).encode()).hexdigest()[:10]
                    tables[key] = words
                    devices[stem].setdefault(group, {})[address] = key
    used = {key for groups in devices.values() for by in groups.values() for key in by.values()}
    tables = {key: words for key, words in tables.items() if key in used}
    with open(OUT, "w") as f:
        json.dump({"tables": tables, "devices": devices}, f, indent=1, sort_keys=True, ensure_ascii=False)
        f.write("\n")
    print("wrote", OUT, len(tables), "tables")


if __name__ == "__main__":
    main()
