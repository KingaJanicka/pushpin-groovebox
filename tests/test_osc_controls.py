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


# --- drawing stays inside the control's column (mono2k's 0..127 ranges) ---

import pytest  # noqa: E402
import push2_python as _push2_python  # noqa: E402
from unittest.mock import MagicMock as _MagicMock, patch as _patch  # noqa: E402
from osc_controls import OSCControl as _OSCControl  # noqa: E402


def _drawn_xs(control, x_part, lock_value=None):
    ctx = _MagicMock(name="cairo")
    with _patch("osc_controls.show_text"):
        if lock_value is None:
            control.draw(ctx, x_part)
        else:
            control.draw(ctx, x_part, draw_lock=True, lock_value=lock_value)
    return [c.args[0] for c in ctx.move_to.call_args_list + ctx.line_to.call_args_list]


@pytest.mark.parametrize("bipolar", [False, True])
@pytest.mark.parametrize("lo, hi, value", [(0, 127, 0), (0, 127, 64), (0, 127, 127), (0, 1, 0.5), (0, 71, 30)])
def test_knob_drawing_stays_in_its_column(bipolar, lo, hi, value):
    control = _OSCControl({"$type": "control-range", "label": "PAN", "address": "/cc/62",
                           "min": lo, "max": hi, "bipolar": int(bipolar)})
    control.value = value
    column = _push2_python.constants.DISPLAY_LINE_PIXELS // 8
    x_part = 3
    for x in _drawn_xs(control, x_part) + _drawn_xs(control, x_part, lock_value=value):
        assert column * x_part - 1 <= x <= column * (x_part + 1) + 1, (x, value, hi)


def test_bipolar_line_starts_at_centre_and_follows_the_value():
    control = _OSCControl({"$type": "control-range", "label": "PAN", "address": "/cc/62",
                           "min": 0, "max": 127, "bipolar": 1})
    control.value = 63.5
    ctx = _MagicMock(name="cairo")
    with _patch("osc_controls.show_text"):
        control.draw(ctx, 0)
    # the coloured line: move_to the centre, line_to centre + (fraction - 0.5) * length
    centre_moves = [c.args[0] for c in ctx.move_to.call_args_list]
    lines = [c.args[0] for c in ctx.line_to.call_args_list]
    assert any(abs(m - x) < 1e-9 for m in centre_moves for x in lines)   # zero-length at the centre


def test_fraction_handles_min_and_clamps():
    control = _OSCControl({"$type": "control-range", "label": "X", "address": "/x", "min": -1, "max": 1})
    assert control.fraction(0) == 0.5
    assert control.fraction(5) == 1.0
    assert control.fraction(-5) == 0.0
def _filter_type_menu(send):
    """A filter-type style menu: items share one address, values aren't 0..n."""
    items = [("12db LP", 1.0), ("24db LP", 2.0), ("12db BP", 6.0), ("24db BP", 23.0)]
    config = {
        "$type": "control-menu",
        "items": [
            {
                "$type": "menu-item",
                "label": label,
                "onselect": {"$type": "message", "address": "/param/a/filter/1/type", "value": value},
            }
            for label, value in items
        ],
    }
    return OSCControlMenu(config, send_osc_func=send)


def test_OSCControlMenu_sends_only_when_item_changes():
    sent = []
    control = _filter_type_menu(lambda addr, val: sent.append((addr, val)))
    assert control.value == 0

    control.update_value(1)  # a fraction of one item: still "12db LP"
    assert sent == [], "No OSC while the selected item is unchanged"

    control.update_value(127)  # saturate to the last item
    assert sent == [("/param/a/filter/1/type", 23.0)]


def test_OSCControlMenu_can_advance_despite_surge_echo():
    """Regression: Surge echoes each value back; that used to pin the menu.

    Every send is echoed straight back into set_state, as Surge does. Turning
    the encoder one click at a time must still reach the next item.
    """
    control = None

    def send_and_echo(addr, val):
        control.set_state(addr, val)

    control = _filter_type_menu(send_and_echo)
    for _ in range(60):  # ~26 single clicks per item with 4 items
        control.update_value(1)
    assert control.value >= 1, "Encoder turns past the first item"
    assert control.get_active_menu_item().label != "12db LP"


def test_OSCControlMenu_echo_of_current_item_keeps_fraction():
    control = _filter_type_menu(lambda addr, val: None)
    control.update_value(5)
    fraction = control.value
    assert 0 < fraction < 1
    control.set_state("/param/a/filter/1/type", 1.0)  # Surge reports "12db LP"
    assert control.value == fraction


def test_OSCControlMenu_external_change_still_updates():
    control = _filter_type_menu(lambda addr, val: None)
    control.set_state("/param/a/filter/1/type", 6.0)  # e.g. a preset load
    assert control.value == 2
    assert control.get_active_menu_item().label == "12db BP"


class FakeSurge:
    """Stores params, echoes every set and answers /q queries, like Surge XT."""

    def __init__(self, state):
        self.state = dict(state)
        self.handlers = {}

    # dispatcher API used by the controls
    def map(self, address, handler):
        self.handlers.setdefault(address, []).append(handler)

    # send_osc_func
    def send(self, address, value):
        if address.startswith("/q"):
            address = address[2:]
        elif value is not None:
            self.state[address] = value
        if address in self.state:
            for handler in self.handlers.get(address, []):
                handler(address, float(self.state[address]), "label")


def _family_switch_config(address="/param/a/filter/1/type"):
    def group(label, *types):
        return {
            "$type": "group",
            "label": label,
            "controls": [
                {
                    "$type": "control-menu",
                    "items": [
                        {"$type": "menu-item", "label": f"{label} {t}",
                         "onselect": {"$type": "message", "address": address, "value": t}}
                        for t in types
                    ],
                }
            ],
        }

    return {"$type": "control-switch",
            "groups": [group("Off", 0), group("Classic", 1, 2), group("OB-Xd", 11, 12)]}


def test_OSCControlSwitch_family_switch_changes_type_despite_echo():
    """Regression: turning the filter family snapped back to the current type.

    Changing group only queried Surge; Surge answered with the old type and
    set_state() moved the switch back. Now the new group's type is sent first.
    """
    surge = FakeSurge({"/param/a/filter/1/type": 1})  # Classic 12db LP
    switch = OSCControlSwitch(_family_switch_config(), send_osc_func=surge.send, dispatcher=surge)
    assert switch.family_address == "/param/a/filter/1/type"
    switch.value = switch.knob_value = 1.0  # showing "Classic", as Surge says

    for _ in range(80):  # one click at a time, ~43 clicks per group here
        switch.update_value(1)

    assert switch.get_active_group().label == "OB-Xd"
    assert surge.state["/param/a/filter/1/type"] == 11, "Surge got the new filter type"


def test_OSCControlSwitch_without_family_keeps_query_only():
    """Switches whose groups have onselect (Twist engine) are unchanged."""
    sent = []
    config = _family_switch_config()
    config["groups"][1]["onselect"] = {"$type": "message", "address": "/engine", "value": 1}
    switch = OSCControlSwitch(config, send_osc_func=lambda a, v: sent.append((a, v)),
                              dispatcher=FakeSurge({}))
    assert switch.family_address is None
    switch.update_value(64)
    assert ("/engine", 1.0) in sent
    assert ("/param/a/filter/1/type", 1.0) not in sent


class LateSurge(FakeSurge):
    """FakeSurge whose echoes and query replies arrive `delay` clicks late."""

    def __init__(self, state, delay):
        super().__init__(state)
        self.delay = delay
        self.queue = []  # (deliver_at_click, address)
        self.click = 0

    def send(self, address, value):
        if address.startswith("/q"):
            address = address[2:]
        elif value is not None:
            self.state[address] = value
        if address in self.state:
            self.queue.append((self.click + self.delay, address, float(self.state[address])))

    def tick(self):
        self.click += 1
        due = [q for q in self.queue if q[0] <= self.click]
        self.queue = [q for q in self.queue if q[0] > self.click]
        for _, address, value in due:
            for handler in self.handlers.get(address, []):
                handler(address, value, "label")


def test_OSCControlSwitch_late_echo_does_not_jump_back():
    """Turning quickly: an echo for an earlier group must not pull the switch back."""
    surge = LateSurge({"/param/a/filter/1/type": 0}, delay=6)
    switch = OSCControlSwitch(_family_switch_config(), send_osc_func=surge.send, dispatcher=surge)
    for _ in range(10):  # the page has loaded: startup query replies have arrived
        surge.tick()
    seen = []
    for _ in range(14):  # ~4 clicks per group at this speed
        switch.update_value(10)
        surge.tick()
        seen.append(int(switch.knob_value))
    for _ in range(10):  # let the late echoes land
        surge.tick()

    assert seen == sorted(seen), f"switch jumped back while turning forward: {seen}"
    assert switch.get_active_group().label == "OB-Xd"
    assert surge.state["/param/a/filter/1/type"] == 11


def test_OSCControlMenu_late_echo_does_not_jump_back():
    surge = LateSurge({"/param/a/filter/1/type": 1}, delay=6)
    menu = _filter_type_menu(surge.send)
    surge.map("/param/a/filter/1/type", menu.set_state)
    seen = []
    for _ in range(14):
        menu.update_value(12)
        surge.tick()
        seen.append(int(menu.value))
    for _ in range(10):
        surge.tick()
    assert seen == sorted(seen), f"menu jumped back while turning forward: {seen}"
    assert menu.get_active_menu_item().label == "24db BP"


def test_RecentSends_forgets_after_window():
    now = [0.0]
    recent = __import__("osc_controls").RecentSends(window=1.0, clock=lambda: now[0])
    recent.add(11)
    assert recent.contains(11.0)
    now[0] = 1.5
    assert not recent.contains(11)


def test_OSCControlSwitch_external_change_still_moves_switch():
    """A type Surge reports that we didn't send (e.g. preset load) still applies."""
    surge = FakeSurge({"/param/a/filter/1/type": 1})
    switch = OSCControlSwitch(_family_switch_config(), send_osc_func=surge.send, dispatcher=surge)
    surge.send("/param/a/filter/1/type", 11)  # preset sets OB-Xd 12db LP
    assert switch.get_active_group().label == "OB-Xd"


def test_OSCControlSwitch_clicks_per_group_sets_speed():
    config = _family_switch_config()
    config["clicks_per_group"] = 25
    switch = OSCControlSwitch(config, send_osc_func=lambda a, v: None, dispatcher=FakeSurge({}))
    for _ in range(24):
        switch.update_value(1)
    assert switch.get_active_group().label == "Off", "24 clicks: not there yet"
    switch.update_value(1)
    assert switch.get_active_group().label == "Classic", "25th click moves one group"


def test_filter_switches_are_slowed_down():
    import json
    d = json.load(open("definitions/device_definitions/filters.json"))
    switches = [c for c in d["controls"] if c["$type"] == "control-switch"]
    assert len(switches) == 2
    assert all(s.get("clicks_per_group") == 25 for s in switches)
