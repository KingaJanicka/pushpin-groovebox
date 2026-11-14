"""Loading device-page definitions (the JSON files under definitions/ and
engines/*/definitions/)."""
from __future__ import annotations

import json
import os
from glob import glob
from pathlib import Path


def load_device_definitions(folder: str) -> dict[str, dict]:
    """Every ``*.json`` in ``folder`` keyed by file stem, in file-name order (which is page order)."""
    definitions: dict[str, dict] = {}
    for path in sorted(glob(os.path.join(folder, "*.json"))):
        with open(path) as f:
            definitions[Path(path).stem] = json.load(f)
    return definitions


# Surge's words for each knob's values (tools/surge_value_labels.py)
SURGE_VALUE_LABELS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                  "definitions", "surge_value_labels.json")


def apply_value_tables(definitions: dict[str, dict], path: str = SURGE_VALUE_LABELS) -> None:
    """Give each control-range Surge's recorded words for it, as "value_table".

    The recording is keyed by definition (file stem), then by the label of the
    switch group the control is in ("" outside any), then by address: Twist's
    param2 means something else in each engine group.
    """
    if not os.path.exists(path):
        return
    with open(path) as f:
        recorded = json.load(f)
    tables = recorded["tables"]

    def visit(controls: list, group: str, by_group: dict) -> None:
        for control in controls:
            if control.get("$type") == "control-range":
                key = by_group.get(group, {}).get(control.get("address"))
                if key in tables:
                    control["value_table"] = tables[key]
            for child in control.get("groups", []):
                visit(child.get("controls", []), child.get("label", ""), by_group)

    for name, definition in definitions.items():
        by_group = recorded["devices"].get(name)
        if by_group and isinstance(definition, dict):
            visit(definition.get("controls", []), "", by_group)
