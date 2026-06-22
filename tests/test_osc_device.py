from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from modes.osc_device import OSCDevice
from osc_controls import scale_value
from pythonosc.udp_client import SimpleUDPClient
from pythonosc.dispatcher import Dispatcher
import push2_python

nested_switch_groups_menu_fixture = {
    "device_name": "Filter B",
    "init": [],
    "controls": [
        {
            "$type": "control-range",
            "label": "Shape R",
            "address": "/param/a/feg/release_shape",
            "min": 0,
            "max": 2,
        },
        {"$type": "control-spacer"},
        {
            "$type": "control-switch",
            "groups": [
                {
                    "$type": "group",
                    "label": "Sh. Cat",
                    "controls": [
                        {
                            "$type": "control-menu",
                            "items": [
                                {
                                    "$type": "menu-item",
                                    "label": "Off",
                                    "onselect": {
                                        "$type": "message",
                                        "$comment": "Off",
                                        "address": "/param/a/waveshaper/type",
                                        "value": 0,
                                    },
                                }
                            ],
                        },
                        {
                            "$type": "control-menu",
                            "items": [
                                {
                                    "$type": "menu-item",
                                    "label": "Soft",
                                    "onselect": {
                                        "$type": "message",
                                        "$comment": "Soft",
                                        "address": "/param/a/waveshaper/type",
                                        "value": 1,
                                    },
                                },
                                {
                                    "$type": "menu-item",
                                    "label": "Med",
                                    "onselect": {
                                        "$type": "message",
                                        "$comment": "Med",
                                        "address": "/param/a/waveshaper/type",
                                        "value": 40,
                                    },
                                },
                                {
                                    "$type": "menu-item",
                                    "label": "Hard",
                                    "onselect": {
                                        "$type": "message",
                                        "$comment": "Hard",
                                        "address": "/param/a/waveshaper/type",
                                        "value": 2,
                                    },
                                },
                                {
                                    "$type": "menu-item",
                                    "label": "Asymm.",
                                    "onselect": {
                                        "$type": "message",
                                        "$comment": "Asymm.",
                                        "address": "/param/a/waveshaper/type",
                                        "value": 3,
                                    },
                                },
                                {
                                    "$type": "menu-item",
                                    "label": "OJD",
                                    "onselect": {
                                        "$type": "message",
                                        "$comment": "OJD",
                                        "address": "/param/a/waveshaper/type",
                                        "value": 41,
                                    },
                                },
                            ],
                        },
                    ],
                },
                {
                    "$type": "group",
                    "controls": [
                        {
                            "$type": "control-menu",
                            "items": [
                                {
                                    "$type": "menu-item",
                                    "label": "Sine",
                                    "onselect": {
                                        "$type": "message",
                                        "$comment": "Sine",
                                        "address": "/param/a/waveshaper/type",
                                        "value": 4,
                                    },
                                },
                                {
                                    "$type": "menu-item",
                                    "label": "Digital",
                                    "onselect": {
                                        "$type": "message",
                                        "$comment": "Digital",
                                        "address": "/param/a/waveshaper/type",
                                        "value": 5,
                                    },
                                },
                            ],
                        },
                    ],
                },
            ],
        },
    ],
}


def test_OSCDevice(mocker):
    # prepare
    mocker.patch("pythonosc.udp_client.SimpleUDPClient.send_message")
    mocker.patch("pythonosc.dispatcher.Dispatcher.map")

    client: Any = SimpleUDPClient("127.0.0.1", 9999)
    dispatcher = Dispatcher()
    osc = {"client": client, "server": None, "dispatcher": dispatcher}

    # OSCDevice is now a PyshaMode-style object: it needs an `app` plus the
    # in/out OSC ports as keyword args. Encoder handling is also gated on the
    # sequencer modes' `disable_controls` flags, so those must be False.
    app = MagicMock(name="app")
    app.metro_sequencer_mode.disable_controls = False

    # test
    device = OSCDevice(
        nested_switch_groups_menu_fixture,
        osc,
        app=app,
        osc_in_port=9000,
        osc_out_port=9001,
    )
    switch = device.controls[2]

    # assert
    assert switch.label == "Sh. Cat"
    assert (
        len(device.controls) == 3
    ), "Should spawn 3 controls (1 range, 1 spacer, 1 switch)"

    # First encoder drives the range control. update_value() now adds a *scaled*
    # increment (scale_value), so the value is fractional, not the raw 1.0.
    device.on_encoder_rotated(push2_python.constants.ENCODER_TRACK1_ENCODER, 1)
    client.send_message.assert_any_call(
        "/param/a/feg/release_shape", scale_value(1, 0, 2)
    )

    # Spacer (encoder 2) shouldn't throw when rotated.
    device.on_encoder_rotated(push2_python.constants.ENCODER_TRACK2_ENCODER, -1)

    # The switch is encoder 3. A large increment is needed to advance the
    # integer group index (each click only nudges it fractionally).
    device.on_encoder_rotated(push2_python.constants.ENCODER_TRACK3_ENCODER, 64)
    active_group = switch.get_active_group()
    assert int(switch.value) == 1, "Switch should advance to the second group"
    assert active_group == switch.groups[1], "Can get active group"

    # After switching groups, encoder 4 maps to that group's menu. A large
    # increment saturates it to the last item ("Digital").
    device.on_encoder_rotated(push2_python.constants.ENCODER_TRACK4_ENCODER, 127)
    menu = active_group.controls[0]
    assert menu.label == "Digital", "Menu should take the label of the chosen element"
    client.send_message.assert_any_call("/param/a/waveshaper/type", 5.0)


bonkers_paging_fixture = {
    "device_name": "paging test",
    "init": [],
    "controls": [
        {
            "$type": "control-range",
            "label": "A",
            "address": "/a",
            "min": 0.0,
            "max": 1.0,
        },
        {
            "$type": "control-range",
            "label": "B",
            "address": "/b",
            "min": 0.0,
            "max": 1.0,
        },
        {
            "$type": "control-range",
            "label": "C",
            "address": "/c",
            "min": 0.0,
            "max": 1.0,
        },
        {
            "$type": "control-range",
            "label": "D",
            "address": "/d",
            "min": 0.0,
            "max": 1.0,
        },
        {
            "$type": "control-range",
            "label": "E",
            "address": "/e",
            "min": 0.0,
            "max": 1.0,
        },
        {
            "$type": "control-range",
            "label": "F",
            "address": "/f",
            "min": 0.0,
            "max": 1.0,
        },
        {
            "$type": "control-range",
            "label": "G",
            "address": "/g",
            "min": 0.0,
            "max": 1.0,
        },
        {
            "$type": "control-range",
            "label": "H",
            "address": "/h",
            "min": 0.0,
            "max": 1.0,
        },
        {
            "$type": "control-range",
            "label": "I",
            "address": "/i",
            "min": 0.0,
            "max": 1.0,
        },
        {
            "$type": "control-range",
            "label": "J",
            "address": "/j",
            "min": 0.0,
            "max": 1.0,
        },
        {
            "$type": "control-range",
            "label": "K",
            "address": "/k",
            "min": 0.0,
            "max": 1.0,
        },
        {
            "$type": "control-range",
            "label": "L",
            "address": "/l",
            "min": 0.0,
            "max": 1.0,
        },
        {
            "$type": "control-range",
            "label": "M",
            "address": "/m",
            "min": 0.0,
            "max": 1.0,
        },
        {
            "$type": "control-range",
            "label": "N",
            "address": "/n",
            "min": 0.0,
            "max": 1.0,
        },
        {
            "$type": "control-range",
            "label": "O",
            "address": "/o",
            "min": 0.0,
            "max": 1.0,
        },
        {
            "$type": "control-range",
            "label": "P",
            "address": "/p",
            "min": 0.0,
            "max": 1.0,
        },
        {
            "$type": "control-range",
            "label": "Q",
            "address": "/q",
            "min": 0.0,
            "max": 1.0,
        },
        {
            "$type": "control-range",
            "label": "R",
            "address": "/r",
            "min": 0.0,
            "max": 1.0,
        },
        {
            "$type": "control-range",
            "label": "S",
            "address": "/s",
            "min": 0.0,
            "max": 1.0,
        },
        {
            "$type": "control-range",
            "label": "T",
            "address": "/t",
            "min": 0.0,
            "max": 1.0,
        },
        {
            "$type": "control-range",
            "label": "U",
            "address": "/u",
            "min": 0.0,
            "max": 1.0,
        },
        {
            "$type": "control-switch",
            "groups": [
                {
                    "$type": "group",
                    "label": "page 1",
                    "controls": [
                        {
                            "$type": "control-range",
                            "label": "AA",
                            "address": "/aa",
                            "min": 0.0,
                            "max": 1.0,
                        },
                        {
                            "$type": "control-range",
                            "label": "BB",
                            "address": "/bb",
                            "min": 0.0,
                            "max": 1.0,
                        },
                        {
                            "$type": "control-range",
                            "label": "CC",
                            "address": "/cc",
                            "min": 0.0,
                            "max": 1.0,
                        },
                    ],
                },
                {
                    "$type": "group",
                    "label": "page 2",
                    "controls": [
                        {
                            "$type": "control-range",
                            "label": "DD",
                            "address": "/dd",
                            "min": 0.0,
                            "max": 1.0,
                        },
                        {
                            "$type": "control-range",
                            "label": "EE",
                            "address": "/ee",
                            "min": 0.0,
                            "max": 1.0,
                        },
                        {
                            "$type": "control-range",
                            "label": "FF",
                            "address": "/ff",
                            "min": 0.0,
                            "max": 1.0,
                        },
                    ],
                },
                {
                    "$type": "group",
                    "label": "page 3",
                    "controls": [
                        {
                            "$type": "control-range",
                            "label": "GG",
                            "address": "/gg",
                            "min": 0.0,
                            "max": 1.0,
                        },
                        {
                            "$type": "control-range",
                            "label": "HH",
                            "address": "/hh",
                            "min": 0.0,
                            "max": 1.0,
                        },
                        {
                            "$type": "control-range",
                            "label": "II",
                            "address": "/ii",
                            "min": 0.0,
                            "max": 1.0,
                        },
                    ],
                },
            ],
        },
        {
            "$type": "control-range",
            "label": "V",
            "address": "/v",
            "min": 0.0,
            "max": 1.0,
        },
        {
            "$type": "control-range",
            "label": "W",
            "address": "/w",
            "min": 0.0,
            "max": 1.0,
        },
        {"$type": "control-spacer"},
        {
            "$type": "control-range",
            "label": "X",
            "address": "/x",
            "min": 0.0,
            "max": 1.0,
        },
        {"$type": "control-spacer"},
        {
            "$type": "control-range",
            "label": "Y",
            "address": "/y",
            "min": 0.0,
            "max": 1.0,
        },
        {"$type": "control-spacer"},
        {
            "$type": "control-range",
            "label": "Z",
            "address": "/z",
            "min": 0.0,
            "max": 1.0,
        },
    ],
}


def test_that_bit_of_logic_in_oscdevice(mocker):
    # prepare
    mocker.patch("pythonosc.udp_client.SimpleUDPClient.send_message")
    mocker.patch("pythonosc.dispatcher.Dispatcher.map")

    client: Any = SimpleUDPClient("127.0.0.1", 9999)
    dispatcher = Dispatcher()
    osc = {"client": client, "server": None, "dispatcher": dispatcher}

    app = MagicMock(name="app")

    # test
    device = OSCDevice(
        bonkers_paging_fixture,
        osc,
        app=app,
        osc_in_port=9000,
        osc_out_port=9001,
    )

    visible = [control.label for control in device.get_visible_controls()]

    assert visible == ["A", "B", "C", "D", "E", "F", "G", "H"], "first page is visible"

    device.set_page(0)

    assert visible == [
        "A",
        "B",
        "C",
        "D",
        "E",
        "F",
        "G",
        "H",
    ], "first page is STILL visible"

    device.set_page(1)
    visible = [control.label for control in device.get_visible_controls()]

    assert visible == ["I", "J", "K", "L", "M", "N", "O", "P"], "second page is visible"

    device.set_page(2)
    visible = [control.label for control in device.get_visible_controls()]

    assert visible == [
        "Q",
        "R",
        "S",
        "T",
        "U",
        "",
        "",
        "",
    ], "third page is visible but too small to accommodate group"

    device.set_page(3)
    visible = [control.label for control in device.get_visible_controls()]

    assert visible == [
        "page 1",
        "AA",
        "BB",
        "CC",
        "V",
        "W",
        "",
        "X",
    ], "Should display groups and spacers"

    device.set_page(4)
    visible = [control.label for control in device.get_visible_controls()]

    assert visible == [
        "",
        "Y",
        "",
        "Z",
    ], "Should display groups and spacers"
