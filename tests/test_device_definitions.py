"""Every device definition (definitions/*_definitions/*.json) sends what it says.

Three layers, none of which needs Surge or hardware:

* the JSON on its own: well-formed, addresses that belong to the device's slot,
  menus with one address, _1/_2/_global twins that only differ by slot;
* the JSON built into the real OSCDevice with a recording OSC client: turning
  every control end to end sends exactly the messages the JSON lists;
* tests/fixtures/surge_snapshot.json, what a real Surge XT did with each
  definition (captured by tools/surge_snapshot.py): every address exists,
  every value is in range and lands, every label matches what Surge shows.
"""
from __future__ import annotations

import glob
import json
import os
import re
from unittest.mock import MagicMock

import pytest
from pythonosc.dispatcher import Dispatcher

import engine
import wavetables
from modes.audio_in_device import AudioInDevice
from modes.osc_device import OSCDevice
from osc_controls import OSCControl, OSCControlMenu, OSCControlSwitch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDERS = ["definitions/device_definitions", "definitions/effect_definitions", "definitions/modulation_definitions"]
# Built in code (ModMatrixDevice); its JSON isn't read
NOT_DEFINITIONS = {"definitions/modulation_definitions/mod_matrix.json"}
FILES = sorted(
    os.path.relpath(path, ROOT)
    for folder in FOLDERS
    for path in glob.glob(os.path.join(ROOT, folder, "*.json"))
    if os.path.relpath(path, ROOT) not in NOT_DEFINITIONS
)
SNAPSHOT_PATH = os.path.join(ROOT, "tests", "fixtures", "surge_snapshot.json")
SNAPSHOT: dict = {"wavetables": {}, "files": {}}
if os.path.exists(SNAPSHOT_PATH):
    with open(SNAPSHOT_PATH) as f:
        SNAPSHOT = json.load(f)

CONTROL_TYPES = {"control-range", "control-menu", "control-switch", "control-spacer",
                 "control-spacer-address", "control-macro"}


def load(rel: str) -> dict:
    with open(os.path.join(ROOT, rel)) as f:
        return json.load(f)


def walk(controls: list, path: str = "controls"):
    """(path, control) for every control, groups' controls included."""
    for i, control in enumerate(controls):
        here = f"{path}[{i}]"
        yield here, control
        for j, group in enumerate(control.get("groups", [])):
            yield from walk(group["controls"], f"{here}.groups[{j}].controls")


def messages(definition: dict):
    """(path, label, message) for every message a control can send."""
    for path, control in walk(definition["controls"]):
        for j, item in enumerate(control.get("items", [])):
            if item.get("onselect"):
                yield f"{path}.items[{j}]", item.get("label"), item["onselect"]
        for j, group in enumerate(control.get("groups", [])):
            if group.get("onselect"):
                yield f"{path}.groups[{j}].onselect", group.get("label"), group["onselect"]


def addresses(definition: dict):
    for message in definition.get("init", []):
        yield "init", message["address"]
    for path, control in walk(definition["controls"]):
        if control.get("address"):
            yield path, control["address"]
        for k, param in enumerate(control.get("params", [])):
            yield f"{path}.params[{k}]", param["address"]
    for path, _, message in messages(definition):
        yield path, message["address"]


# ---------------------------------------------------------------- the JSON

@pytest.mark.parametrize("rel", FILES)
def test_definition_is_well_formed(rel):
    definition = load(rel)
    assert isinstance(definition["name"], str) and definition["name"]
    assert definition["slot"] in range(16)
    for message in definition["init"]:
        assert message["$type"] == "message"
        assert isinstance(message["value"], (int, float))
    for path, control in walk(definition["controls"]):
        assert control["$type"] in CONTROL_TYPES, path
        if control["$type"] == "control-range":
            assert control.get("label"), path
            assert control["min"] < control["max"], path
        if control["$type"] == "control-menu":
            assert control["items"], path
            for item in control["items"]:
                assert item["$type"] == "menu-item", path
                assert isinstance(item["onselect"]["value"], (int, float)), path
        if control["$type"] == "control-switch":
            assert control["groups"], path
            for group in control["groups"]:
                assert group["$type"] == "group" and group.get("label"), path


@pytest.mark.parametrize("rel", FILES)
def test_addresses_are_well_formed(rel):
    """No empty path segments (a stray "//param" or "/1//param1" is a different,
    non-existent address to Surge)."""
    bad = [(path, a) for path, a in addresses(load(rel)) if not re.fullmatch(r"(/[A-Za-z0-9_]+)+\+?", a)]
    assert bad == []


SLOT_ADDRESSES = {
    0: (r"/param/a/osc/1/", r"/param/a/mixer/osc1/", r"/wavetable/a/osc/1/"),
    1: (r"/param/a/osc/2/", r"/param/a/mixer/osc2/", r"/wavetable/a/osc/2/"),
    5: (r"/param/fx/a/1/",),
    6: (r"/param/fx/a/2/",),
    7: (r"/param/fx/global/1/",),
}
SHARED_OSC_ADDRESSES = {"/param/a/osc/fm_routing", "/param/a/osc/fm_depth"}


@pytest.mark.parametrize("rel", FILES)
def test_addresses_belong_to_the_devices_slot(rel):
    """An oscillator device only touches its own oscillator and an FX device its
    own FX unit (copying a device for another slot is how these go wrong)."""
    definition = load(rel)
    prefixes = SLOT_ADDRESSES.get(definition["slot"])
    if prefixes is None:
        pytest.skip("slot not tied to one oscillator or FX unit")
    shared = SHARED_OSC_ADDRESSES if definition["slot"] in (0, 1) else set()
    wrong = [(path, a) for path, a in addresses(definition) if not a.startswith(prefixes) and a not in shared]
    assert wrong == []


@pytest.mark.parametrize("rel", [rel for rel in FILES if re.search(r"/lfo_\d\.json$", rel)])
def test_lfo_pages_only_touch_their_own_lfo(rel):
    n = re.search(r"lfo_(\d)\.json$", rel).group(1)
    wrong = [(path, a) for path, a in addresses(load(rel)) if not a.startswith(f"/param/a/slfo/{n}/")]
    assert wrong == []


@pytest.mark.parametrize("rel", FILES)
def test_menu_items_share_one_address(rel):
    """OSCControlMenu listens on its first item's address only, so an item on
    another address would never show as selected."""
    for path, control in walk(load(rel)["controls"]):
        if control["$type"] == "control-menu":
            assert len({item["onselect"]["address"] for item in control["items"]}) == 1, path


def test_each_slot_value_selects_one_device():
    """Instrument.update_current_devices shows the devices whose init sets the
    slot's address (oscillator/FX type) to its current value: two devices on
    one value would both show, a device without it never would."""
    slots = engine.SurgeXTEngine.initial_slots(MagicMock())
    seen: dict = {}
    for rel in FILES:
        definition = load(rel)
        slot = slots[definition["slot"]]
        if slot is None:
            continue
        values = [m["value"] for m in definition["init"] if m["address"] == slot["address"]]
        assert len(values) == 1, rel
        key = (definition["slot"], values[0])
        assert key not in seen, f"{rel} and {seen.get(key)}"
        seen[key] = rel


TWIN = re.compile(r"(.*)_(1|2|global)\.json$")


def _canonical(definition: dict) -> dict:
    text = json.dumps({k: v for k, v in definition.items() if k != "slot"})
    text = re.sub(r"/osc/[12]/", "/osc/N/", text)
    text = re.sub(r"mixer/osc[12]/", "mixer/oscN/", text)
    text = re.sub(r"/fx/(a/1|a/2|global/1)/", "/fx/N/", text)
    text = re.sub(r"/slfo/[1-6]/", "/slfo/N/", text)
    text = re.sub(r'"\$comment": "[^"]*"', '"$comment": ""', text)
    return json.loads(text)


def _twin_groups():
    groups: dict = {}
    for rel in FILES:
        match = TWIN.match(rel)
        if match:
            groups.setdefault(match.group(1), []).append(rel)
    lfos = [rel for rel in FILES if re.search(r"/lfo_\d\.json$", rel)]
    return [sorted(g) for g in groups.values() if len(g) > 1] + [lfos]


@pytest.mark.parametrize("twins", _twin_groups(), ids=lambda g: os.path.basename(g[0]))
def test_twins_differ_only_by_slot(twins):
    """alias_1/alias_2, nimbus_1/_2/_global, lfo_1..6: one device for several
    slots, so apart from the slot's addresses they must be the same."""
    first = _canonical(load(twins[0]))
    for other in twins[1:]:
        assert _canonical(load(other)) == first, other


# ------------------------------------------------- built into an OSCDevice

@pytest.fixture(autouse=True)
def factory_wavetables(monkeypatch):
    """Wavetable ids as the snapshot's Surge had them (the real lookup reads
    Surge's folder, which a test machine needn't have)."""
    ids = {name: idx for name, (idx, _) in SNAPSHOT["wavetables"].items()}
    monkeypatch.setattr(wavetables, "wavetable_ids", lambda: ids)
    return ids


class Recorder:
    def __init__(self):
        self.sent = []

    def send_message(self, address, value=None):
        self.sent.append((address, value))

    def values(self):
        """What was sent, queries ("/q..." with no value) left out."""
        return [(a, v) for a, v in self.sent if v is not None]


def build(rel: str):
    definition = load(rel)
    client = Recorder()
    cls = AudioInDevice if os.path.basename(rel).startswith("audio_") else OSCDevice
    device = cls(definition, {"client": client, "server": None, "dispatcher": Dispatcher()},
                 engine=MagicMock(), app=MagicMock(), get_color=lambda: "white", osc_in_port=1, osc_out_port=2)
    client.sent.clear()   # (switches query their first group while being built)
    return definition, device, client


def device_controls(device):
    """Every control object, switches' groups' controls included."""
    def visit(controls):
        for control in controls:
            yield control
            for group in getattr(control, "groups", []):
                yield from visit(group.controls)
    yield from visit(device.controls)


@pytest.mark.parametrize("rel", FILES)
def test_select_sends_the_init_block(rel):
    definition, device, client = build(rel)
    device.select_sync()
    assert client.sent == [(m["address"], float(m["value"])) for m in definition["init"]]


@pytest.mark.parametrize("rel", FILES)
def test_ranges_send_their_address_from_min_to_max(rel):
    _, device, client = build(rel)
    for control in device_controls(device):
        # (Audio In's input gains, made in code, go to Pd: address "None")
        if isinstance(control, OSCControl) and control.address.startswith("/"):
            control.update_value(-10_000)
            assert client.sent[-1] == (control.address, float(control.min))
            control.update_value(10_000)
            assert client.sent[-1] == (control.address, float(control.max))


def sweep(control, limit=20_000):
    """Turn a menu or switch one click at a time to its end and back."""
    for direction in (1, -1):
        for _ in range(limit):
            before = control.value
            control.update_value(direction)
            if control.value == before:
                break


@pytest.mark.parametrize("rel", FILES)
def test_menus_send_every_item_in_order(rel):
    """One click at a time from the first item to the last and back: each item
    sends its own message once, in order, none skipped."""
    _, device, client = build(rel)
    for control in device_controls(device):
        if isinstance(control, OSCControlMenu):
            control.value = 0
            client.sent.clear()
            sweep(control)
            sent = [(item.address, float(item.value)) for item in control.items]
            assert client.values() == sent[1:] + sent[-2::-1]


@pytest.mark.parametrize("rel", FILES)
def test_switches_send_every_group(rel):
    """Turning a switch to each group sends the group's message, or (a type
    family, like the filters or wavetables) its menu's selected item."""
    _, device, client = build(rel)
    for control in device_controls(device):
        if isinstance(control, OSCControlSwitch):
            control.value = 0
            client.sent.clear()
            for _ in range(20_000):
                before = control.value
                control.update_value(1)
                if control.value == before:
                    break
            expected = []
            for group in control.groups[1:]:
                if group.message:
                    expected.append((group.message["address"], float(group.message["value"])))
                elif control.family_address:
                    item = group.controls[0].get_active_menu_item()
                    expected.append((item.address, float(item.value)))
            assert client.values() == expected
            assert control.get_active_group() is control.groups[-1]


@pytest.mark.parametrize("rel", FILES)
def test_pages_fit_the_display_in_every_group(rel):
    """However each switch is set, no page holds more than the 8 encoders."""
    _, device, _ = build(rel)
    switches = [c for c in device.controls if isinstance(c, OSCControlSwitch)]
    for switch in switches:
        for g in range(len(switch.groups)):
            switch.value = float(g)
            assert all(len(page) <= 8 for page in device.pages)


# ------------------------------------------------------- against Surge XT
#
# The snapshot holds Surge's own answers; labels are the definitions' own
# shorthand ("S&H" for "Sample & Hold"), so they aren't compared word for
# word. What must hold: each address is Surge's, each value is one Surge keeps,
# and each item of a menu or switch puts Surge somewhere different.

@pytest.fixture
def snapshot_of():
    def get(rel):
        assert rel in SNAPSHOT["files"], f"{rel} isn't in the Surge snapshot: run tools/surge_snapshot.py"
        return SNAPSHOT["files"][rel]
    return get


def test_wavetable_names_match_surges_ids():
    """wavetables.py's names for each id are what Surge itself calls them."""
    assert len(SNAPSHOT["wavetables"]) > 0
    wrong = {name: shown for name, (_, shown) in SNAPSHOT["wavetables"].items()
             if name.rpartition("/")[2] != shown}
    assert wrong == {}


@pytest.mark.parametrize("rel", FILES)
def test_init_lands_in_surge(rel, snapshot_of):
    snap = snapshot_of(rel)
    definition = load(rel)
    assert [[m["address"], m["value"]] for m in definition["init"]] == [e[:2] for e in snap["init"]], \
        "snapshot is stale: run tools/surge_snapshot.py"
    for address, value, read, known in snap["init"]:
        assert known, f"{address} isn't a Surge parameter"
        assert read is not None and float(read) == pytest.approx(float(value), abs=1e-3), address


@pytest.mark.parametrize("rel", FILES)
def test_controls_use_surge_parameters_and_ranges(rel, snapshot_of):
    snap = snapshot_of(rel)
    for path, control in walk(load(rel)["controls"]):
        if control["$type"] not in ("control-range", "control-spacer-address"):
            continue
        address = control["address"]
        if address.startswith("/wavetable/"):
            continue
        assert snap["controls"].get(path, [None])[0] == address, f"{path}: snapshot is stale"
        _, name, kind, lo, hi = snap["controls"][path]
        assert name is not None, f"{path}: {address} isn't a Surge parameter"
        if control["$type"] != "control-range":
            continue
        if kind in ("int", "bool"):
            # sent as is: the range must be Surge's own
            assert (float(control["min"]), float(control["max"])) == (float(lo), float(hi)), \
                f"{path}: {control['min']}..{control['max']}, Surge's '{name}' is {lo}..{hi}"
        else:
            # floats go over OSC as 0..1 of Surge's range
            assert 0 <= control["min"] < control["max"] <= 1, f"{path}: Surge takes '{name}' as 0..1"
        # Drawn from the middle exactly when the middle is Surge's 0
        centred = float(lo) < 0 and float(lo) == -float(hi)
        assert bool(control.get("bipolar", False)) == centred, \
            f"{path}: '{name}' is {lo}..{hi} in Surge, so bipolar should be {int(centred)}"


def surge_entry(snap, path, message):
    entry = snap["messages"].get(path)
    stale = f"{path}: the definition changed since the Surge snapshot: run tools/surge_snapshot.py"
    assert entry is not None and entry[0] == message["address"], stale
    if not message["address"].startswith("/wavetable/"):    # (ids are looked up by name)
        assert float(entry[1]) == float(message["value"]), stale
    return entry


@pytest.mark.parametrize("rel", FILES)
def test_messages_land_in_surge(rel, snapshot_of):
    """Every menu item's and group's message names a Surge parameter (or a
    modifier it has) and a value Surge keeps rather than clamps."""
    snap = snapshot_of(rel)
    for path, label, message in messages(load(rel)):
        address, value, read, shown, kind, lo, hi = surge_entry(snap, path, message)
        assert kind is not None, f"{path} ('{label}'): {address} isn't a Surge parameter"
        assert value is not None, f"{path}: no wavetable called {label}"
        if kind in ("int", "bool"):
            assert float(lo) <= float(value) <= float(hi), f"{path} ('{label}'): {value} outside {lo}..{hi}"
        elif kind == "float" and not address.startswith("/wavetable/"):
            assert 0 <= float(value) <= 1, f"{path} ('{label}'): {value} outside 0..1"
        if kind != "float":
            assert read is not None and int(round(float(read))) == int(value), \
                f"{path} ('{label}'): sent {value}, Surge kept {read} ({shown})"


@pytest.mark.parametrize("rel", FILES)
def test_each_choice_selects_something_different(rel, snapshot_of):
    """Two items of one menu, or two groups of one switch, that leave Surge in
    the same state are a copy-paste slip (Nimbus' Spectral selected Looping
    Delay, the Amp's Digital selected Analog)."""
    snap = snapshot_of(rel)
    definition = load(rel)
    for path, control in walk(definition["controls"]):
        choices = []
        for j, item in enumerate(control.get("items", [])):
            choices.append((item.get("label"), f"{path}.items[{j}]", item["onselect"]))
        for j, group in enumerate(control.get("groups", [])):
            if group.get("onselect"):
                choices.append((group.get("label"), f"{path}.groups[{j}].onselect", group["onselect"]))
        states: dict = {}
        for label, here, message in choices:
            address, value, read, shown, *_ = surge_entry(snap, here, message)
            state = (address, read, shown)
            assert state not in states, f"{path}: '{label}' and '{states.get(state)}' both give Surge {shown or read}"
            states[state] = label


@pytest.mark.parametrize("rel", FILES)
def test_family_switch_items_are_in_one_group_only(rel):
    """A type-family switch (filters, waveshapers, wavetables) finds the group
    to show from the value Surge reports, so a value must belong to one group."""
    for path, control in walk(load(rel)["controls"]):
        seen: dict = {}
        for j, group in enumerate(control.get("groups", [])):
            first = group["controls"][0] if group["controls"] else {}
            for item in first.get("items", []):
                key = (item["onselect"]["address"], item.get("wavetable", item["onselect"]["value"]))
                assert key not in seen or seen[key] == j, \
                    f"{path}: '{item['label']}' is in '{group['label']}' and group {seen[key]}"
                seen[key] = j
