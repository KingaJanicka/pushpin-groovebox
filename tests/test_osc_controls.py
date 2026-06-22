from osc_controls import (
    OSCControl,
    ControlSpacer,
    OSCControlMacro,
    OSCGroup,
    OSCControlSwitch,
    OSCControlMenu,
    OSCMenuItem,
    scale_value,
)


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
    assert control.value == 0.0, "Controls default to 0.0 in the scaled model"

    # Self-population was moved out of __init__ into an explicit query() method.
    control.query()
    mock_send_osc_func.assert_called_with("/q/test", None)

    # set_state stores the incoming OSC value verbatim.
    control.set_state("/test", 99.0)
    assert control.value == 99.0, "Control should set state"

    # update_value() adds a *scaled* increment (scale_value), not the raw step.
    control.set_state("/test", 0.0)
    control.update_value(1)
    assert control.value == scale_value(
        1, test_min, test_max
    ), "Control should update by a scaled amount"

    # Respects max / min bounds.
    control.set_state("/test", test_max)
    control.update_value(1)
    assert control.value == test_max, "Control should respect max"

    control.set_state("/test", test_min)
    control.update_value(-1)
    assert control.value == test_min, "Control should respect min"


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
    assert control.value == 0.0, "Macro should start at the scaled default (0.0)"

    control.update_value(1)

    # OSCControlMacro.update_value() sends the macro's own value to every linked
    # param (it does not scale per-param), so both addresses receive control.value.
    # (Previously this referenced an undefined `scale_knob_value`, raising NameError.)
    mock_send_osc_func.assert_any_call("/param/a/...", float(control.value))
    mock_send_osc_func.assert_any_call("/param/b/...", float(control.value))


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

    # OSCControlSwitch now requires a dispatcher (it raises otherwise).
    dispatcher = mocker.MagicMock(name="dispatcher")
    control = OSCControlSwitch(
        config, mock_get_color_func, mock_send_osc_func, dispatcher=dispatcher
    )

    active_group = control.get_active_group()
    assert active_group is not None
    assert control.value == 0, "Initial value should be 0"
    assert active_group.label == "group 1", "Initialises with the first group"
    assert control.size == 5, "Group size should be the max of all children (+1)"

    # Constructing the switch selects the active group, which queries the
    # addresses of its child controls ("/q<address>", None).
    mock_send_osc_func.assert_any_call("/q/param/a/osc/1/param2", None)

    # update_value() adds a scaled increment; a large step is needed to advance
    # the integer group index (twitchy-knob mitigation).
    control.update_value(64)
    active_group = control.get_active_group()
    assert active_group is not None

    assert int(control.value) == 1, "Value should advance to the second group"
    assert active_group.label == "group 2", "Active group should update"
    assert control.size == 5, "Group size should stay the same"

    # exercise get_control, OSCControls
    assert all(
        isinstance(c, OSCControl) for c in active_group.controls
    ), "Active group should contain only controls"
    assert (
        active_group.get_control(0).label == "Waveshaper"
    ), "Child controls behave expectedly"
    assert (
        active_group.get_control("Waveshaper").value == 0.0
    ), "Uninitialised controls default to 0.0"


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

    # NOTE: the menu seeds its index from the top-level onselect message's
    # `value` (1 here), not 0 -- so it starts on the *second* item. This looks
    # like a bug (onselect value conflated with menu index); flagged in the
    # tests README as a candidate for the bug-density phase. Asserting current
    # behavior per the "update tests to match code" decision.
    assert control.value == 1, "Menu index is seeded from onselect.value"
    assert control.message == {
        "$type": "message",
        "address": "init",
        "value": 1,
    }, "Should set initial message"

    # A single click moves the index only fractionally (scaled step), so to
    # navigate deterministically we use large increments that saturate.
    control.update_value(127)
    assert control.value == len(control.items) - 1, "CW saturates at last item"
    mock_send_osc_func.assert_any_call("/param/a/waveshaper/type", 41.0)

    control.update_value(-127)
    assert control.value == 0, "CCW saturates at first item"
    mock_send_osc_func.assert_any_call("/param/a/waveshaper/type", 1.0)

    # A single click moves only a fraction of one item.
    control.update_value(1)
    assert 0 < control.value < 1, "A single click moves the menu fractionally"
