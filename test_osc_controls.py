from osc_controls import (
    OSCControl,
    ControlSpacer,
    OSCControlMacro,
    OSCGroup,
    OSCControlSwitch,
    OSCControlMenu,
    OSCMenuItem,
)
from osc_utils import scale_knob_value


def test_OSCControl(mocker):
    mock_send_osc_func = mocker.stub(name="send_osc_func")
    mock_get_color_func = mocker.stub(name="get_color_func")
    test_min = -999
    test_max = 999
    control = OSCControl(
        {
            "$type": "control-range",
            "label": "test",
            "address": "/test",
            "min": test_min,
            "max": test_max,
        },
        mock_get_color_func,
        mock_send_osc_func,
    )

    assert control.max == test_max, "Maximum value should match constructor"
    assert control.min == test_min, "Minimum value should match constructor"
    assert control.size == 1, "OSCControl size should always be 1"

    mock_send_osc_func.assert_called_with(
        "/q/test", None
    ), "Control should self-populate"

    control.set_state("/test", "99 random stuff woo")

    assert control.value == 99.0, "Control should set state"

    control.update_value(1)

    assert control.value == 100.0, "Control should update via knobs"

    mock_send_osc_func.assert_called_with(
        "/test", scale_knob_value([100.0, test_min, test_max])
    )

    control.set_state("/test", "127 test")
    control.update_value(1)
    assert control.value == 127.0, "Control should respect vmax"

    control.set_state("/test", "0 test")
    control.update_value(-1)
    assert control.value == 0.0, "Control should respect vmin"


def test_SpacerControl(mocker):
    control = ControlSpacer()

    assert control.size == 1, "SpacerControl size should always be 1"
    assert control.address == None, "Address should match init"
    assert control.draw() == None, "Function should return none"
    assert control.update_value() == None


def test_OSCMacroControl(mocker):
    mock_send_osc_func = mocker.stub(name="send_osc_func")
    mock_get_color_func = mocker.stub(name="get_color_func")
    params = [
        {"$type": "control-range", "address": "/param/a/...", "min": 0.0, "max": 1.0},
        {"$type": "control-range", "address": "/param/b/...", "min": -99, "max": 2.5},
    ]

    control = OSCControlMacro(
        {"$type": "control-macro", "label": "test macro", "params": params},
        mock_get_color_func,
        mock_send_osc_func,
    )

    assert control.size == 1, "OSCMacroControl size should always be 1"
    assert control.value == 64, "Macro should start at default value (64)"

    control.update_value(1)

    mock_send_osc_func.assert_any_call("/param/a/...", scale_knob_value([65, 0.0, 1.0]))
    mock_send_osc_func.assert_any_call("/param/b/...", scale_knob_value([65, -99, 2.5]))


def test_OSCControlMenuItem(mocker):
    mock_send_osc_func = mocker.stub(name="send_osc_func")

    control = OSCMenuItem(
        {
            "$type": "menu-item",
            "label": "Label",
            "onselect": {"address": "address", "value": 99.0},
        },
        send_osc_func=mock_send_osc_func,
    )

    control.select()

    mock_send_osc_func.assert_any_call("address", 99.0)


def test_OSCControlSwitch_Group_Range(mocker):
    mock_send_osc_func = mocker.stub(name="send_osc_func")
    mock_get_color_func = mocker.stub(name="get_color_func")

    config = {
        "$type": "control-switch",
        "groups": [
            {
                "$type": "group",
                "label": "group 1",
                "onselect": {
                    "$type": "message",
                    "address": "/param/a/osc/1/param1",
                    "value": 0.0,
                },
                "controls": [
                    {
                        "$type": "control-range",
                        "label": "Detune",
                        "address": "/param/a/osc/1/param2",
                        "min": 0.0,
                        "max": 1.0,
                    },
                    {
                        "$type": "control-range",
                        "label": "Square Sh.",
                        "address": "/param/a/osc/1/param3",
                        "min": 0.0,
                        "max": 1.0,
                    },
                    {
                        "$type": "control-range",
                        "label": "Saw Sh.",
                        "address": "/param/a/osc/1/param4",
                        "min": 0.0,
                        "max": 1.0,
                    },
                    {
                        "$type": "control-range",
                        "label": "Sync Mix",
                        "address": "/param/a/osc/1/param5",
                        "min": 0.0,
                        "max": 1.0,
                    },
                ],
            },
            {
                "$type": "group",
                "label": "group 2",
                "onselect": {
                    "$type": "message",
                    "address": "/param/a/osc/1/param1",
                    "value": 1.0,
                },
                "controls": [
                    {
                        "$type": "control-range",
                        "label": "Waveshaper",
                        "address": "/param/a/osc/1/param2",
                        "min": 0.0,
                        "max": 1.0,
                    },
                    {
                        "$type": "control-range",
                        "label": "Fold",
                        "address": "/param/a/osc/1/param3",
                        "min": 0.0,
                        "max": 1.0,
                    },
                    {
                        "$type": "control-range",
                        "label": "Asymmetry",
                        "address": "/param/a/osc/1/param4",
                        "min": 0.0,
                        "max": 1.0,
                    },
                ],
            },
        ],
    }

    control = OSCControlSwitch(config, mock_get_color_func, mock_send_osc_func)

    active_group = control.get_active_group()
    assert control.value == 0, "Initial value should be 0"
    assert (
        active_group.label == "group 1"
    ), "Group should initialise with first control in list"
    assert control.size == 5, "Group size should be the max of all children"
    mock_send_osc_func.assert_any_call("/param/a/osc/1/param1", 0.0)

    control.update_value(1)
    active_group = control.get_active_group()

    assert control.value == 1, "Value should update"
    assert active_group.label == "group 2", "Active group should update"
    assert control.size == 5, "Group size should stay the same"
    mock_send_osc_func.assert_any_call("/param/a/osc/1/param1", 1.0)

    # exercise get_control, OSCControls
    assert all(
        isinstance(c, OSCControl) for c in active_group.controls
    ), "Active group should contains only controls"
    assert (
        active_group.get_control(0).label == "Waveshaper"
    ), "Child controls behave expectedly"
    assert (
        active_group.get_control("Waveshaper").value == 64
    ), "Uninitialised controls default to 64"


def test_OSCControlMenu(mocker):
    mock_send_osc_func = mocker.stub(name="send_osc_func")
    mock_get_color_func = mocker.stub(name="get_color_func")
    config = {
        "$type": "control-menu",
        "label": "Saturator",
        "onselect": {"$type": "message", "address": "init", "value": 1},
        "items": [
            {
                "$type": "menu-item",
                "label": "Soft",
                "onselect": {
                    "$type": "message",
                    "address": "/param/a/waveshaper/type",
                    "value": 1.0,
                },
            },
            {
                "$type": "menu-item",
                "label": "Med",
                "onselect": {
                    "$type": "message",
                    "address": "/param/a/waveshaper/type",
                    "value": 40.0,
                },
            },
            {
                "$type": "menu-item",
                "label": "Hard",
                "onselect": {
                    "$type": "message",
                    "address": "/param/a/waveshaper/type",
                    "value": 2.0,
                },
            },
            {
                "$type": "menu-item",
                "label": "Asymm.",
                "onselect": {
                    "$type": "message",
                    "address": "/param/a/waveshaper/type",
                    "value": 3.0,
                },
            },
            {
                "$type": "menu-item",
                "label": "OJD",
                "onselect": {
                    "$type": "message",
                    "address": "/param/a/waveshaper/type",
                    "value": 41.0,
                },
            },
        ],
    }

    control = OSCControlMenu(
        config, send_osc_func=mock_send_osc_func, get_color_func=mock_get_color_func
    )

    assert control.value == 0, "Default menu index is 0"
    assert control.message == {
        "$type": "message",
        "address": "init",
        "value": 1,
    }, "Should set initial message"

    # rotate knob one click cw
    control.update_value(1)

    # mock_send_osc_func.assert_any_call("/param/a/waveshaper/type", 1.0)

    assert control.value == 1, "Menu value should now be 1"
    mock_send_osc_func.assert_any_call("/param/a/waveshaper/type", 40.0)

    # rotate knob one click ccw
    control.update_value(-1)
    control.update_value(-1)
    assert control.value == 0, "Menu value should be 0"

    # rotate knob indeterminate amount cw
    control.update_value(1)
    control.update_value(1)
    control.update_value(1)
    control.update_value(1)
    control.update_value(1)
    control.update_value(1)
    control.update_value(1)

    assert control.value == 4, "Menu value should be length - 1 of menu.options"
    mock_send_osc_func.assert_any_call("/param/a/waveshaper/type", 40.0)
    mock_send_osc_func.assert_any_call("/param/a/waveshaper/type", 2.0)
    mock_send_osc_func.assert_any_call("/param/a/waveshaper/type", 3.0)
    mock_send_osc_func.assert_any_call("/param/a/waveshaper/type", 41.0)
