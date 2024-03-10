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
    "osc": {
        "controls": [
            ["A", "/a", 0.0, 1.0],
            ["B", "/b", 0.0, 1.0],
            ["C", "/c", 0.0, 1.0],
            ["D", "/d", 0.0, 1.0],
            ["E", "/e", 0.0, 1.0],
            ["F", "/f", 0.0, 1.0],
            ["G", "/g", 0.0, 1.0],
            ["H", "/h", 0.0, 1.0],
            ["I", "/i", 0.0, 1.0],
            ["J", "/j", 0.0, 1.0],
            ["K", "/k", 0.0, 1.0],
            ["L", "/l", 0.0, 1.0],
            ["M", "/m", 0.0, 1.0],
            ["N", "/n", 0.0, 1.0],
            ["O", "/o", 0.0, 1.0],
            ["P", "/p", 0.0, 1.0],
            ["Q", "/q", 0.0, 1.0],
            ["R", "/r", 0.0, 1.0],
            ["S", "/s", 0.0, 1.0],
            ["T", "/t", 0.0, 1.0],
            ["U", "/u", 0.0, 1.0],
            {
                "name": "group",
                "controls": [
                    {
                        "name": "page 1",
                        "controls": [
                            ["AA", "/aa", 0.0, 1.0],
                            ["BB", "/bb", 0.0, 1.0],
                            ["CC", "/cc", 0.0, 1.0],
                        ],
                    },
                    {
                        "name": "page 2",
                        "controls": [
                            ["DD", "/dd", 0.0, 1.0],
                            ["EE", "/ee", 0.0, 1.0],
                            ["FF", "/ff", 0.0, 1.0],
                        ],
                    },
                    {
                        "name": "page 3",
                        "controls": [
                            ["GG", "/gg", 0.0, 1.0],
                            ["HH", "/hh", 0.0, 1.0],
                            ["II", "/ii", 0.0, 1.0],
                        ],
                    },
                ],
            },
            ["V", "/v", 0.0, 1.0],
            ["W", "/w", 0.0, 1.0],
            [],
            ["X", "/x", 0.0, 1.0],
            [],
            ["Y", "/y", 0.0, 1.0],
            [],
            ["Z", "/z", 0.0, 1.0],
        ]
    },
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
        None,
        None,
        None,
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
        None,
        "X",
    ], "Should display groups and spacers"
