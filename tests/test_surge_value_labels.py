"""Surge's own words for knob values ("62.50 ms") on the Push display."""
from __future__ import annotations

import glob
import json
import os
from unittest.mock import MagicMock

import pytest
from pythonosc.dispatcher import Dispatcher

from modes.device_definitions import SURGE_VALUE_LABELS, apply_value_tables
from modes.osc_device import OSCDevice
from osc_controls import OSCControl, parse_amount

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDERS = ["definitions/device_definitions", "definitions/effect_definitions", "definitions/modulation_definitions"]
FILES = sorted(
    path for folder in FOLDERS for path in glob.glob(os.path.join(ROOT, folder, "*.json"))
    if not path.endswith("mod_matrix.json")
)
with open(SURGE_VALUE_LABELS) as f:
    RECORDED = json.load(f)


def knob(table, lo=0.0, hi=1.0):
    return OSCControl({"$type": "control-range", "label": "K", "address": "/k", "min": lo, "max": hi,
                       "value_table": table})


# ------------------------------------------------------------- the words

def test_parse_amount():
    assert parse_amount("62.50 ms") == (62.5, 2, " ms")
    assert parse_amount("-7 semitones") == (-7.0, 0, " semitones")
    assert parse_amount("440.00 Hz") == (440.0, 2, " Hz")
    assert parse_amount("Off") is None
    assert parse_amount("1/4 note") is None


def test_value_on_a_recorded_point_shows_surges_words():
    k = knob(["0.00 ms", "50.00 ms", "100.00 ms"])
    assert k.display_text(0.0) == "0.00 ms"
    assert k.display_text(0.5) == "50.00 ms"
    assert k.display_text(1.0) == "100.00 ms"


def test_value_between_points_interpolates_the_number():
    k = knob(["0.00 ms", "50.00 ms", "100.00 ms"])
    assert k.display_text(0.25) == "25.00 ms"


def test_words_between_points_take_the_nearer():
    k = knob(["Off", "On"])
    assert k.display_text(0.4) == "Off"
    assert k.display_text(0.6) == "On"


def test_different_units_either_side_take_the_nearer():
    k = knob(["900.00 Hz", "1.10 kHz"])
    assert k.display_text(0.3) == "900.00 Hz"
    assert k.display_text(0.8) == "1.10 kHz"


def test_int_parameter_table_has_a_word_per_value():
    k = knob(["1 voice", "2 voices", "3 voices"], lo=1, hi=3)
    assert [k.display_text(v) for v in (1, 2, 3)] == ["1 voice", "2 voices", "3 voices"]


def test_values_outside_the_range_show_its_ends():
    k = knob(["0 %", "100 %"])
    assert k.display_text(-3) == "0 %"
    assert k.display_text(7) == "100 %"


def test_no_table_keeps_the_plain_number():
    k = OSCControl({"$type": "control-range", "label": "K", "address": "/k", "min": 0, "max": 1})
    assert k.display_text(0.5) == "0.5"
    assert not k.has_value_labels


# ------------------------------------------------- handing them out

def test_tables_go_to_controls_by_group_and_address(tmp_path):
    path = tmp_path / "labels.json"
    path.write_text(json.dumps({
        "tables": {"top": ["a", "b"], "kick": ["c", "d"]},
        "devices": {"twist_1": {"": {"/p1": "top"}, "Kick": {"/p2": "kick"}}},
    }))
    definitions = {"twist_1": {"controls": [
        {"$type": "control-range", "address": "/p1", "min": 0, "max": 1},
        {"$type": "control-switch", "groups": [
            {"$type": "group", "label": "Kick", "controls": [
                {"$type": "control-range", "address": "/p2", "min": 0, "max": 1}]},
            {"$type": "group", "label": "Snare", "controls": [
                {"$type": "control-range", "address": "/p2", "min": 0, "max": 1}]},
        ]},
    ]}}
    apply_value_tables(definitions, str(path))
    controls = definitions["twist_1"]["controls"]
    assert controls[0]["value_table"] == ["a", "b"]
    assert controls[1]["groups"][0]["controls"][0]["value_table"] == ["c", "d"]
    assert "value_table" not in controls[1]["groups"][1]["controls"][0]


def test_missing_recording_changes_nothing(tmp_path):
    definitions = {"x": {"controls": [{"$type": "control-range", "address": "/p", "min": 0, "max": 1}]}}
    apply_value_tables(definitions, str(tmp_path / "missing.json"))
    assert "value_table" not in definitions["x"]["controls"][0]


# ------------------------------------------------ the recording itself

def load_all():
    definitions = {}
    for path in FILES:
        with open(path) as f:
            definitions[os.path.splitext(os.path.basename(path))[0]] = json.load(f)
    apply_value_tables(definitions)
    return definitions


def ranges(controls, group=""):
    for control in controls:
        if control["$type"] == "control-range":
            yield group, control
        for g in control.get("groups", []):
            yield from ranges(g["controls"], g["label"])


def modifier_toggled(definition):
    out = set()
    def visit(controls):
        for control in controls:
            for item in control.get("items", []):
                address = item["onselect"]["address"]
                if address.endswith(("/tempo_sync+", "/extend+", "/abs+")):
                    out.add(address.rsplit("/", 1)[0])
            for g in control.get("groups", []):
                visit(g["controls"])
    visit(definition["controls"])
    return out


@pytest.mark.parametrize("name, definition", sorted(load_all().items()))
def test_every_surge_knob_has_surges_words(name, definition):
    """All but the knobs whose words a modifier menu on the page changes
    (a delay time with tempo sync): Surge doesn't say which applies."""
    skip = modifier_toggled(definition)
    missing = [(group, c["label"]) for group, c in ranges(definition["controls"])
               if "value_table" not in c and c["address"] not in skip]
    assert missing == [], "run tools/surge_value_labels.py"
    for group, control in ranges(definition["controls"]):
        if control["address"] in skip:
            assert "value_table" not in control, control["label"]


@pytest.mark.parametrize("name, definition", sorted(load_all().items()))
def test_tables_cover_the_controls_range(name, definition):
    for _, control in ranges(definition["controls"]):
        table = control.get("value_table")
        if table is None:
            continue
        span = control["max"] - control["min"]
        if len(table) != 101:   # an int parameter: a word per whole value
            assert len(table) == int(span) + 1, control["label"]


def test_device_shows_the_recorded_words():
    definition = load_all()["distortion_1"]
    device = OSCDevice(definition, {"client": MagicMock(), "dispatcher": Dispatcher()},
                       app=MagicMock(), osc_in_port=1, osc_out_port=2)
    bandwidth = next(c for c in device.controls if getattr(c, "address", None) == "/param/fx/a/1/param3")
    assert bandwidth.display_text(bandwidth.min).endswith(" oct")
