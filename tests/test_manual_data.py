"""The website's interactive manual (docs/manual/manual.json) against the code.

Every Push 2 button and encoder a mode reacts to must be explained somewhere in
the manual, and every control the manual explains must be a real Push 2
control. Reads the mode sources with ``ast`` only, so nothing is imported.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANUAL = ROOT / "docs" / "manual" / "manual.json"

# The modes PyshaApp can reach from the Push (the rest of modes/ is unused or
# only switched to from these)
REACHABLE_MODES = [
    "main_controls_mode.py",
    "melodic_mode.py",
    "metro_sequencer_mode.py",
    "mute_mode.py",
    "clip_selection_mode.py",
    "preset_selection_mode.py",
    "osc_mode.py",
    "instrument_selection_mode.py",
    "settings_mode.py",
    "menu_mode.py",
    "engine_selection_mode.py",
    "rename_mode.py",
]

# Controls the panel draws that aren't Push 2 buttons
EXTRA_CONTROLS = {"touchstrip"} | {f"enc_{i}" for i in range(1, 9)} | {"enc_tempo", "enc_swing", "enc_master"}

ENCODER_IDS = {
    "ENCODER_TEMPO_ENCODER": "enc_tempo",
    "ENCODER_SWING_ENCODER": "enc_swing",
    "ENCODER_MASTER_ENCODER": "enc_master",
    **{f"ENCODER_TRACK{i}_ENCODER": f"enc_{i}" for i in range(1, 9)},
}


def control_id(constant: str) -> str | None:
    """``BUTTON_UPPER_ROW_1`` -> ``upper_row_1``; ``ENCODER_TRACK3_ENCODER`` -> ``enc_3``."""
    if constant in ENCODER_IDS:
        return ENCODER_IDS[constant]
    if constant.startswith("BUTTON_") and constant not in ("BUTTON_PRESSED", "BUTTON_RELEASED"):
        return constant[len("BUTTON_"):].lower()
    return None


def push2_controls() -> set[str]:
    source = (ROOT / "controllers" / "push2_constants.py").read_text()
    buttons = {control_id(name) for name in re.findall(r"^(BUTTON_[A-Z0-9_]+)\s*=", source, re.M)}
    return {b for b in buttons if b} | EXTRA_CONTROLS


HANDLERS = {"on_button_pressed", "on_button_released", "on_encoder_rotated"}

# Read by a handler only to be ignored
IGNORED = {"enc_swing"}


def _refs(node: ast.AST) -> set[str]:
    """Every attribute and bare name under ``node``."""
    names = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Attribute):
            names.add(n.attr)
        elif isinstance(n, ast.Name):
            names.add(n.id)
    return names


def handled_controls(filename: str) -> set[str]:
    """Push 2 buttons and encoders a mode's input handlers react to.

    Only the handlers count (a button whose light is merely set doesn't), and a
    module or class constant they use (``NOTE_BUTTON``, ``track_button_names``)
    counts as the buttons it holds.
    """
    tree = ast.parse((ROOT / "modes" / filename).read_text())
    aliases: dict[str, set[str]] = {}
    scopes = [tree.body] + [c.body for c in tree.body if isinstance(c, ast.ClassDef)]
    for body in scopes:
        for stmt in body:
            if isinstance(stmt, ast.Assign):
                held = {cid for cid in map(control_id, _refs(stmt.value)) if cid}
                for target in stmt.targets:
                    if isinstance(target, ast.Name) and held:
                        aliases[target.id] = held
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in HANDLERS:
            for name in _refs(node):
                cid = control_id(name)
                if cid:
                    found.add(cid)
                found |= aliases.get(name, set())
    return found - IGNORED


def documented_controls(manual: dict) -> set[str]:
    found = set(manual["global"])
    for mode in manual["modes"].values():
        found |= set(mode.get("controls", {}))
        found |= set(mode.get("held", {}))
        for layer in mode.get("layers", {}).values():
            found |= set(layer.get("controls", {}))
            found.add(layer["button"])
    for overlay in manual["overlays"].values():
        found |= set(overlay.get("controls", {}))
        for page in overlay.get("pages", []):
            found |= set(page.get("controls", {}))
    return found


def load_manual() -> dict:
    return json.loads(MANUAL.read_text())


def test_manual_is_valid_json_with_every_section():
    manual = load_manual()
    assert {"global", "modes", "overlays", "tracks", "colors"} <= set(manual)
    assert len(manual["tracks"]) == 8
    assert all(c in manual["colors"] for c in manual["tracks"])


def test_every_handled_control_is_in_the_manual():
    documented = documented_controls(load_manual())
    missing = {
        f"{filename}: {cid}"
        for filename in REACHABLE_MODES
        for cid in handled_controls(filename) - documented
    }
    assert sorted(missing) == []


def test_manual_names_only_real_controls():
    real = push2_controls()
    unknown = documented_controls(load_manual()) - real
    assert sorted(unknown) == []


def test_every_mode_explains_its_pads_and_display():
    manual = load_manual()
    for name, mode in manual["modes"].items():
        assert mode["name"] and mode["summary"] and mode["enter"], name
        assert len(mode["display"]["labels"]) == 8, name
        if "layers" in mode:
            for layer in mode["layers"].values():
                assert layer["pads"] and len(layer["rows"]) == 8, layer["name"]
        else:
            assert mode["pads"], name
    for name, overlay in manual["overlays"].items():
        for page in overlay.get("pages", [overlay]):
            assert len(page["display"]["labels"]) == 8, name


def test_sequencer_layer_buttons_match_the_code():
    """The layer buttons are track_button_names in metro_sequencer_mode, in TRACK_NAMES_METRO order."""
    source = (ROOT / "modes" / "metro_sequencer_mode.py").read_text()
    block = re.search(r"track_button_names = \[(.*?)\]", source, re.S).group(1)
    buttons = [control_id(b) for b in re.findall(r"^\s*push2_python\.constants\.(BUTTON_\w+)", block, re.M)]
    layers = load_manual()["modes"]["seq"]["layers"]
    assert [layer["button"] for layer in layers.values()] == buttons


def test_device_pages_are_generated_from_the_current_definitions():
    """docs/manual/devices.json must match what tools/build_manual_devices.py makes
    of definitions/ now; rerun the tool after changing a definition."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("build_manual_devices", ROOT / "tools" / "build_manual_devices.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    current = (ROOT / "docs" / "manual" / "devices.json").read_text()
    assert current == builder.render(), "run: python tools/build_manual_devices.py"


def test_device_pages_cover_both_instrument_pages():
    devices = json.loads((ROOT / "docs" / "manual" / "devices.json").read_text())
    surge = devices["engines"]["surge"]
    assert [len(p) for p in surge["pages"]] == [8, 8]
    for engine in devices["engines"].values():
        for slot, key in engine["shown"].items():
            assert key in engine["slots"][slot]
            for page in devices["devices"][key]["pages"]:
                assert len(page) == 8


def test_device_menu_lists_a_slots_devices_by_name_as_pushpin_does():
    """OSCMode.get_current_slot_devices sorts a slot's devices on their label."""
    devices = json.loads((ROOT / "docs" / "manual" / "devices.json").read_text())
    for engine in devices["engines"].values():
        for keys in engine["slots"].values():
            labels = [devices["devices"][k]["label"] for k in keys]
            assert labels == sorted(labels)
