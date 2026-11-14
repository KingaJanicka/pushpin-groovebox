"""wavetables.py: Surge's wavetable ids, worked out from its folder."""
from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_message_builder import OscMessageBuilder

import wavetables
from modes.osc_device import OSCDevice
from osc_controls import OSCControlMenu, OSCMenuItem


def make_folder(root, layout):
    for category, names in layout.items():
        os.makedirs(root / category, exist_ok=True)
        for name in names:
            (root / category / name).write_bytes(b"")


def test_scan_lists_each_folders_wavetables_as_category_slash_name(tmp_path):
    make_folder(tmp_path, {"Basic": ["Sine.wt", "Saw.wav"], "Waldorf": ["Beat.wt"]})
    names = wavetables.scan_wavetables(str(tmp_path))
    assert sorted(names) == ["Basic/Saw", "Basic/Sine", "Waldorf/Beat"]


def test_scan_skips_other_files(tmp_path):
    make_folder(tmp_path, {"Basic": ["Sine.wt", "README.txt", ".DS_Store"]})
    (tmp_path / "WT fileformat.txt").write_text("")
    assert wavetables.scan_wavetables(str(tmp_path)) == ["Basic/Sine"]


def test_scan_follows_directory_order_not_alphabetical(tmp_path, monkeypatch):
    """Surge numbers wavetables in readdir order; so must we."""
    make_folder(tmp_path, {"A": ["a1.wt", "a2.wt"], "B": ["b1.wt"]})
    real_scandir = os.scandir

    class Reversed:
        def __init__(self, path):
            self.entries = sorted(real_scandir(path), key=lambda e: e.name, reverse=True)

        def __enter__(self):
            return iter(self.entries)

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(wavetables.os, "scandir", Reversed)
    assert wavetables.scan_wavetables(str(tmp_path)) == ["B/b1", "A/a2", "A/a1"]


def test_scan_takes_each_folder_before_its_files_and_nested_folders_by_path(tmp_path):
    make_folder(tmp_path, {"Emu": ["e.wt"], "Emu/Percussion": ["p.wt"]})
    assert wavetables.scan_wavetables(str(tmp_path)) == ["Emu/e", "Emu/Percussion/p"]


def test_ids_are_positions_in_the_scan(tmp_path, monkeypatch):
    make_folder(tmp_path, {"Basic": ["Sine.wt", "Saw.wt"]})
    monkeypatch.setattr(wavetables, "FACTORY_FOLDERS", (str(tmp_path / "missing"), str(tmp_path)))
    wavetables.wavetable_ids.cache_clear()
    try:
        order = wavetables.scan_wavetables(str(tmp_path))
        assert wavetables.wavetable_ids() == {name: i for i, name in enumerate(order)}
        assert wavetables.wavetable_id(order[1]) == 1
        assert wavetables.wavetable_id("Basic/Nope") is None
    finally:
        wavetables.wavetable_ids.cache_clear()


def test_no_surge_folder_means_no_ids(tmp_path, monkeypatch):
    monkeypatch.setattr(wavetables, "FACTORY_FOLDERS", (str(tmp_path / "missing"),))
    wavetables.wavetable_ids.cache_clear()
    try:
        assert wavetables.wavetable_ids() == {}
    finally:
        wavetables.wavetable_ids.cache_clear()


def wavetable_item(name, osc=1):
    return {"$type": "menu-item", "label": name.rpartition("/")[2], "wavetable": name,
            "onselect": {"$type": "message", "address": f"/wavetable/a/osc/{osc}/id", "value": -1}}


@pytest.fixture
def ids(monkeypatch):
    table = {"Basic/Sine": 7, "Basic/Saw": 3}
    monkeypatch.setattr(wavetables, "wavetable_ids", lambda: table)
    return table


def test_menu_item_sends_the_looked_up_id_not_the_placeholder(ids):
    send = MagicMock()
    item = OSCMenuItem(wavetable_item("Basic/Sine"), send_osc_func=send)
    assert item.value == 7
    item.select()
    send.assert_called_once_with("/wavetable/a/osc/1/id", 7.0)


def test_unknown_wavetable_item_sends_nothing(ids):
    send = MagicMock()
    item = OSCMenuItem(wavetable_item("Basic/Gone"), send_osc_func=send)
    assert item.value is None
    item.select()
    send.assert_not_called()


def test_menu_of_unknown_wavetables_ignores_surges_echo(ids):
    """No item has an id (Surge's folder missing): an echo mustn't crash it."""
    menu = OSCControlMenu({"$type": "control-menu", "items": [wavetable_item("X/a"), wavetable_item("X/b")]})
    menu.set_state("/wavetable/a/osc/1/id", 12.0, "Whatever")
    assert menu.value == 0


def picker_device(ids):
    config = {
        "name": "Wavetable", "slot": 0, "init": [],
        "controls": [{
            "$type": "control-switch", "select_by_value": True,
            "groups": [
                {"$type": "group", "label": "Basic", "controls": [
                    {"$type": "control-menu", "items": [wavetable_item("Basic/Saw"), wavetable_item("Basic/Sine")]}]},
                {"$type": "group", "label": "Waldorf", "controls": [
                    {"$type": "control-menu", "items": [wavetable_item("Waldorf/Beat")]}]},
            ],
        }],
    }
    ids["Waldorf/Beat"] = 40
    dispatcher = Dispatcher()
    client = MagicMock()
    device = OSCDevice(config, {"client": client, "dispatcher": dispatcher}, app=MagicMock(),
                       osc_in_port=1, osc_out_port=2)
    return device, dispatcher, client


def surge_says(dispatcher, address, *args):
    builder = OscMessageBuilder(address=address)
    for arg in args:
        builder.add_arg(arg)
    dispatcher.call_handlers_for_packet(builder.build().dgram, ("127.0.0.1", 0))


def test_surge_reporting_a_wavetable_moves_the_picker_to_its_category(ids):
    """After a preset load Surge answers the id query: the picker must show
    that table's category and the table itself."""
    device, dispatcher, _ = picker_device(ids)
    switch = device.controls[0]
    surge_says(dispatcher, "/wavetable/a/osc/1/id", 40.0, "Beat")
    assert switch.get_active_group().label == "Waldorf"
    surge_says(dispatcher, "/wavetable/a/osc/1/id", 7.0, "Sine")
    assert switch.get_active_group().label == "Basic"
    assert switch.get_active_group().controls[0].label == "Sine"


def test_turning_the_picker_to_a_category_selects_its_first_table(ids):
    device, _, client = picker_device(ids)
    switch = device.controls[0]
    client.reset_mock()
    switch.update_value(127)
    client.send_message.assert_any_call("/wavetable/a/osc/1/id", 40.0)
