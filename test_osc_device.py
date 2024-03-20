from osc_device import OSCDevice
from pythonosc.udp_client import SimpleUDPClient
from pythonosc.dispatcher import Dispatcher
import push2_python
import osc_utils
import pytest

fixture = {
    "device_name": "Filter B",
    "init": [],
    "osc": {
        "controls": [
            ["A", "/param/a/feg/attack", 0.0, 1.0],
            ["Shape R", "/param/a/feg/release_shape", 0.0, 2.0],
            [],
            {
                "name": "Sh. Cat",
                "controls": [
                    {
                        "name": "Off",
                        "controls": [["Off", "/param/a/waveshaper/type", 0.0]],
                    },
                    {
                        "name": "Saturator",
                        "controls": [
                            ["Soft", "/param/a/waveshaper/type", 1.0],
                            ["Med", "/param/a/waveshaper/type", 40.0],
                        ],
                    },
                ],
            },
        ]
    },
}


@pytest.mark.skip
def test_OSCDevice(mocker):
    # prepare
    mocker.patch("pythonosc.udp_client.SimpleUDPClient.send_message")
    mocker.patch("pythonosc.dispatcher.Dispatcher.map")

    client = SimpleUDPClient("127.0.0.1", "9999")
    dispatcher = Dispatcher()
    osc = {"client": client, "server": None, "dispatcher": dispatcher}

    # test
    device = OSCDevice(fixture, osc)

    group = device.controls[3]

    # assert
    assert group.label == "Sh. Cat"
    assert (
        len(device.controls) == 4
    ), "Should spawn 4 controls (2 normal, 1 spacer, 1 group)"

    # Test first encoder/device CW rotate
    device.on_encoder_rotated(push2_python.constants.ENCODER_TRACK1_ENCODER, 1)
    control_under_test = device.get_control_at_index()

    # Test second encoder/device CCW rotate
    device.on_encoder_rotated(push2_python.constants.ENCODER_TRACK2_ENCODER, -1)

    # Spacer shouldn't throw if passed value
    device.on_encoder_rotated(push2_python.constants.ENCODER_TRACK3_ENCODER, 1)

    # Group should update on TRACK4 CW rotate
    device.on_encoder_rotated(push2_python.constants.ENCODER_TRACK4_ENCODER, 1)

    active_group = group.get_active_group()
    assert active_group == group.controls[1], "Can get active group"

    assert active_group.value == 1, "Group value should increment"

    # Group should update on TRACK4 CW rotate
    device.on_encoder_rotated(push2_python.constants.ENCODER_TRACK4_ENCODER, 1)

    client.send_message.assert_any_call(
        "/param/a/feg/attack", osc_utils.scale_knob_value([65.0, 0.0, 1.0])
    )

    client.send_message.assert_any_call(
        "/param/a/feg/release_shape", osc_utils.scale_knob_value([63.0, 0.0, 2.0])
    )

    assert False


bonkers_paging_fixture = {
    "device_name": "paging test",
    "init": [],
    "osc": [
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

    client = SimpleUDPClient("127.0.0.1", "9999")
    dispatcher = Dispatcher()
    osc = {"client": client, "server": None, "dispatcher": dispatcher}

    # test
    device = OSCDevice(bonkers_paging_fixture, osc)

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
