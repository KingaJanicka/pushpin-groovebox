"""Record what a real Surge XT does with every device definition.

    "/Applications/Surge XT.app/Contents/MacOS/surge-xt-cli" \\
        --osc-in-port=19030 --osc-out-port=19040 --no-stdin &
    python tools/surge_snapshot.py            # writes tests/fixtures/surge_snapshot.json
    python tools/surge_snapshot.py definitions/device_definitions/window_1.json ...
                                              # re-records only those files

For each definition it loads Init Saw, sends the init block, and then sends
every menu item's and group's message and asks Surge what it now shows. It
also records the name, type and range Surge gives every address a control
uses, in the mode the control is shown in (Twist's and Nimbus' parameters are
renamed per engine/mode). tests/test_device_definitions.py checks the
definitions against this snapshot, offline: rerun this after changing a
definition (it takes about 15 minutes).

Wavetable menu items are resolved by name the way the app does
(wavetables.py), so the snapshot also checks that lookup against Surge.
"""
from __future__ import annotations

import glob
import json
import os
import sys
import threading
import time

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import wavetables  # noqa: E402

IN_PORT, OUT_PORT = 19030, 19040
INIT_PATCH = "/Library/Application Support/Surge XT/patches_factory/Templates/Init Saw"
FOLDERS = ["definitions/device_definitions", "definitions/effect_definitions", "definitions/modulation_definitions"]
SKIP = {"definitions/modulation_definitions/mod_matrix.json"}   # (built in code, not from its JSON)
OUT = os.path.join(ROOT, "tests", "fixtures", "surge_snapshot.json")


class Surge:
    def __init__(self) -> None:
        self.client = SimpleUDPClient("127.0.0.1", IN_PORT)
        self.messages: list = []
        self.lock = threading.Lock()
        dispatcher = Dispatcher()
        dispatcher.set_default_handler(self._received)
        server = ThreadingOSCUDPServer(("127.0.0.1", OUT_PORT), dispatcher)
        threading.Thread(target=server.serve_forever, daemon=True).start()

    def _received(self, address, *args) -> None:
        with self.lock:
            self.messages.append((address, args))

    def drain(self) -> list:
        with self.lock:
            messages, self.messages = self.messages, []
        return messages

    def send(self, address: str, value, wait: float = 0.05) -> None:
        self.client.send_message(address, [] if value is None else value)
        time.sleep(wait)

    def query(self, address: str) -> tuple | None:
        for _ in range(3):
            self.drain()
            self.send("/q" + address, None, wait=0.08)
            for received, args in self.drain():
                if received == address:
                    return args
        return None

    def dump(self) -> tuple[dict, dict]:
        """Every parameter as it is now: ({address: [name, type, min, max]},
        {address: value}). Values include modifiers ("/deform+" etc.), which
        Surge only reports here, not when queried one by one."""
        self.drain()
        self.send("/q/all_params", None, wait=1.2)
        docs, values = {}, {}
        for address, args in self.drain():
            if address.startswith("/doc/"):
                if address.endswith("/ext"):
                    docs.setdefault("ext", {})[address[len("/doc"):-len("/ext")]] = list(args)
                elif len(args) == 4:
                    docs[address[len("/doc"):]] = list(args)
            elif args:
                values[address] = args[0]
        ext = docs.pop("ext", {})
        for address, value in values.items():
            if address not in docs and not address.endswith("+"):
                docs[address] = ["", "float", "0", "1"]   # (Surge documents no macro)
        for address, names in ext.items():
            for name in names:
                docs[f"{address}/{name}+"] = [name, "modifier", None, None]
        return docs, values

    def params(self) -> dict:
        return self.dump()[0]


def check_audio_running(surge: Surge) -> None:
    """Surge changes an oscillator's parameters (Twist's names) on its audio
    thread: with no audio running (an output device that went away) types
    change but nothing else does, and every recording would be wrong."""
    surge.client.send_message("/patch/load", INIT_PATCH)
    time.sleep(0.6)
    surge.send("/param/a/osc/1/type", 10.0, wait=0.3)
    if surge.params().get("/param/a/osc/1/param6", [None])[0] != "LPG Response":
        sys.exit("Surge isn't applying changes (is its audio output running? try --audio-interface=0.0)")


def value_of(item: dict):
    if "wavetable" in item:
        return wavetables.wavetable_id(item["wavetable"])
    return item["onselect"]["value"]


def record_message(surge: Surge, params: dict, address: str, value) -> list:
    """[address, value sent, value read back, display, type, min, max]"""
    doc = params.get(address, [None] * 4)
    if address.startswith("/wavetable/"):   # (not a parameter: its ids are the factory list's)
        doc = ["Wavetable", "int", "0", str(len(wavetables.wavetable_ids()) - 1)]
    if value is None:
        return [address, None, None, None, *doc[1:]]
    surge.send(address, float(value))
    if doc[1] == "modifier":
        return [address, value, surge.dump()[1].get(address), None, *doc[1:]]
    reply = surge.query(address)
    read, display = (reply[0], reply[1] if len(reply) > 1 else None) if reply else (None, None)
    return [address, value, read, display, *doc[1:]]


def walk(surge: Surge, params: dict, controls: list, path: str, out: dict) -> None:
    for i, control in enumerate(controls):
        here = f"{path}[{i}]"
        kind = control["$type"]
        if kind in ("control-range", "control-spacer-address"):
            address = control["address"]
            out["controls"][here] = [address, *params.get(address, [None] * 4)]
        elif kind == "control-menu":
            for j, item in enumerate(control.get("items", [])):
                if item.get("onselect"):
                    out["messages"][f"{here}.items[{j}]"] = record_message(
                        surge, params, item["onselect"]["address"], value_of(item))
            # Back to the first item: the menus after it are read in the mode
            # it sets (filter subtypes after a filter type)
            first = control.get("items", [{}])[0]
            if first.get("onselect") and value_of(first) is not None:
                surge.send(first["onselect"]["address"], float(value_of(first)))
        elif kind == "control-switch":
            for j, group in enumerate(control["groups"]):
                group_path = f"{here}.groups[{j}]"
                if group.get("onselect"):
                    message = group["onselect"]
                    out["messages"][f"{group_path}.onselect"] = record_message(
                        surge, params, message["address"], message["value"])
                else:
                    first = group["controls"][0] if group["controls"] else None
                    if first and first["$type"] == "control-menu" and first["items"]:
                        surge.send(first["items"][0]["onselect"]["address"], value_of(first["items"][0]))
                time.sleep(0.2)
                walk(surge, surge.params() or params, group["controls"], f"{group_path}.controls", out)
        elif kind == "control-macro":
            for k, param in enumerate(control["params"]):
                out["controls"][f"{here}.params[{k}]"] = [param["address"], *params.get(param["address"], [None] * 4)]


def snapshot_definition(surge: Surge, definition: dict) -> dict:
    surge.client.send_message("/patch/load", INIT_PATCH)
    time.sleep(0.6)
    for message in definition.get("init", []):
        surge.send(message["address"], float(message["value"]), wait=0.1)
    time.sleep(0.3)
    params, values = surge.dump()
    out: dict = {"init": [], "controls": {}, "messages": {}}
    for message in definition.get("init", []):
        address = message["address"]
        out["init"].append([address, message["value"], values.get(address), address in params])
    walk(surge, params, definition["controls"], "controls", out)
    return out


def snapshot_wavetables(surge: Surge) -> dict:
    """What Surge calls each factory wavetable id, next to wavetables.py's names."""
    names = {}
    for name, idx in sorted(wavetables.wavetable_ids().items(), key=lambda kv: kv[1]):
        surge.send("/wavetable/a/osc/1/id", float(idx), wait=0.1)
        # Surge takes the id at once but loads the table a little later, so
        # an early answer can carry the previous table's name: ask until it
        # says the same twice
        shown, previous = None, object()
        for _ in range(5):
            reply = surge.query("/wavetable/a/osc/1/id")
            shown = reply[1] if reply and int(reply[0]) == idx else None
            if shown == previous:
                break
            previous = shown
            time.sleep(0.05)
        names[name] = [idx, shown]
    return names


def main() -> None:
    surge = Surge()
    time.sleep(0.2)
    if surge.query("/param/a/osc/1/type") is None:
        sys.exit(f"No reply from surge-xt-cli on port {IN_PORT}: start it first (see this file's docstring)")
    check_audio_running(surge)
    only = {os.path.normpath(arg) for arg in sys.argv[1:]}
    if only and os.path.exists(OUT):
        with open(OUT) as f:
            snapshot = json.load(f)
    else:
        snapshot = {"wavetables": snapshot_wavetables(surge), "files": {}}
    for folder in FOLDERS:
        for path in sorted(glob.glob(os.path.join(ROOT, folder, "*.json"))):
            rel = os.path.relpath(path, ROOT)
            if rel in SKIP or (only and rel not in only):
                continue
            with open(path) as f:
                definition = json.load(f)
            print(rel, flush=True)
            snapshot["files"][rel] = snapshot_definition(surge, definition)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(snapshot, f, indent=1, sort_keys=True)
        f.write("\n")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
