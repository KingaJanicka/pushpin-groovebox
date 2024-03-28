import definitions
import osc_utils
import math
import push2_python
from display_utils import show_text


class OSCControl(object):
    name = "Range"
    size = 1

    def __init__(self, config, get_color_func=None, send_osc_func=None):
        if config["$type"] != "control-range":
            raise Exception("Invalid config passed to new OSCControl")
        self.color = definitions.GRAY_LIGHT
        self.color_rgb = None
        self.label = "Unknown"
        self.address = None
        self.min = 0.0
        self.max = 1.0
        self.value = 64
        self.vmin = 0
        self.vmax = 127
        self.get_color_func = None
        self.label = config["label"]
        self.address = config["address"]
        self.get_color_func = get_color_func
        self.min = config["min"]
        self.max = config["max"]

        if send_osc_func:
            self.send_osc_func = send_osc_func
            # self.send_osc_func(f"/q{self.address}", None)

    def send_osc_func(self, address, payload):
        pass

    def draw(self, ctx, x_part):
        margin_top = 25

        # Param name
        name_height = 20
        show_text(
            ctx,
            x_part,
            margin_top,
            self.label,
            height=name_height,
            font_color=definitions.WHITE,
        )

        # Param value
        val_height = 30
        color = self.get_color_func()
        show_text(
            ctx,
            x_part,
            margin_top + name_height,
            str(self.value),
            height=val_height,
            font_color=color,
        )

        # Knob
        ctx.save()

        circle_break_degrees = 80
        height = 55
        radius = height / 2

        display_w = push2_python.constants.DISPLAY_LINE_PIXELS
        x = (display_w // 8) * x_part
        y = margin_top + name_height + val_height + radius + 5

        start_rad = (90 + circle_break_degrees // 2) * (math.pi / 180)
        end_rad = (90 - circle_break_degrees // 2) * (math.pi / 180)
        xc = x + radius + 3
        yc = y

        def get_rad_for_value(value):
            total_degrees = 360 - circle_break_degrees
            return start_rad + total_degrees * (
                (value - self.vmin) / (self.vmax - self.vmin)
            ) * (math.pi / 180)

        # This is needed to prevent showing line from previous position
        ctx.set_source_rgb(0, 0, 0)
        ctx.move_to(xc, yc)
        ctx.stroke()

        # Inner circle
        ctx.arc(xc, yc, radius, start_rad, end_rad)
        ctx.set_source_rgb(*definitions.get_color_rgb_float(definitions.GRAY_LIGHT))
        ctx.set_line_width(1)
        ctx.stroke()

        # Outer circle
        ctx.arc(xc, yc, radius, start_rad, get_rad_for_value(self.value))
        ctx.set_source_rgb(*definitions.get_color_rgb_float(color))
        ctx.set_line_width(3)
        ctx.stroke()

        ctx.restore()

    def set_state(self, address, *args):
        value, *rest = args
        self.value = osc_utils.scale_osc_value(value, self.min, self.max)

    def update_value(self, increment, **kwargs):
        if self.value + increment > self.vmax:
            self.value = self.vmax
        elif self.value + increment < self.vmin:
            self.value = self.vmin
        else:
            self.value += increment
        # print("update value: adress", self.address, "value", self.value)
        # Send cc message, subtract 1 to number because MIDO works from 0 - 127
        # msg = mido.Message('control_change', control=self.address, value=self.value)
        # msg=f'control_change {self.address} {self.value}'
        # print(self.address, osc_utils.scale_knob_value([self.value, self.min, self.max]))
        self.send_osc_func(
            self.address, osc_utils.scale_knob_value(self.value, self.min, self.max)
        )


class ControlSpacer(object):
    name = "Spacer"

    address = None
    label = None
    size = 1
    color = definitions.GRAY_LIGHT
    color_rgb = None
    label = ""
    get_color_func = None

    def __init__(self):
        pass

    def draw(self, *args, **kwargs):
        pass

    def update_value(self, *args, **kwargs):
        pass


class OSCControlMacro(object):
    name = "Macro"
    size = 1

    def __init__(self, config, get_color_func=None, send_osc_func=None):
        if config["$type"] != "control-macro":
            raise Exception("Invalid config passed to new OSCControlMacro")

        self.color = definitions.GRAY_LIGHT
        self.color_rgb = None
        self.label = "Unknown"
        self.address = None
        self.min = 0.0
        self.max = 1.0
        self.value = 64
        self.vmin = 0
        self.vmax = 127
        self.get_color_func = None
        self.label = config["label"]
        self.get_color_func = get_color_func
        self.params = config["params"]
        self.get_color_func = get_color_func
        self.send_osc_func = send_osc_func

    def update_value(self, increment, **kwargs):
        if self.value + increment > self.vmax:
            self.value = self.vmax
        elif self.value + increment < self.vmin:
            self.value = self.vmin
        else:
            self.value += increment
        # print("update value: adress", self.address, "value", self.value)
        # Send cc message, subtract 1 to number because MIDO works from 0 - 127
        # msg = mido.Message('control_change', control=self.address, value=self.value)
        # msg=f'control_change {self.address} {self.value}'
        # print(self.address, osc_utils.scale_knob_value([self.value, self.min, self.max]))
        # self.send_osc_func(self.address, osc_utils.scale_knob_value([self.value, self.min, self.max]))

        for param in self.params:
            # TODO may need to revisit how min/max is set
            self.send_osc_func(
                param["address"],
                osc_utils.scale_knob_value([self.value, param["min"], param["max"]]),
            )

    def set_state(self, address, *args):
        value, *rest = args

        self.value = int(value * 127)
        ###TODO: Find by index


class OSCControlSwitch(object):
    name = "Switch"

    @property
    def visible(self):
        return self.groups[self.value]

    @property
    def size(self):
        return max(group.size for group in self.groups) + 1

    @property
    def label(self):
        active = self.get_active_group()
        if active:
            return active.label

        return None

    def __init__(self, config, get_color_func=None, send_osc_func=None):
        if config["$type"] != "control-switch":
            raise Exception("Invalid config passed to new OSCControlSwitch")
        self.groups = []
        self.value = 0
        self.get_color_func = get_color_func
        self.send_osc_func = send_osc_func
        groups = config.get("groups", [])

        for item in groups:
            self.groups.append(
                OSCGroup(
                    item,
                    get_color_func=get_color_func,
                    send_osc_func=send_osc_func,
                )
            )

        if (
            len(self.groups) > 0
            and self.groups[self.value]
            and hasattr(self.groups[self.value], "select")
        ):
            self.groups[self.value].select()

    def update_value(self, increment, **kwargs):
        if not self.value:
            pass

        if 0 <= (self.value + increment) < len(self.groups):
            self.value += increment
            active_group = self.get_active_group()
            if hasattr(active_group, "select"):
                active_group.select()

    def get_active_group(self):
        if self.value < len(self.groups):
            return self.groups[self.value]

    def set_state(self, address, *args):
        value, *rest = args

        for idx, group in enumerate(self.groups):
            for control in group.controls:
                if isinstance(OSCControl, control) and control.address == address:
                    self.value = idx
                elif isinstance(OSCControlMacro, control) and any(
                    [param for param in control.params if param["address"] == address]
                ):
                    self.value = idx
                elif isinstance(OSCControlMenu, control) and any(
                    [
                        item
                        for item in control.items
                        if item.message["address"] == address
                    ]
                ):
                    self.value = idx

    def draw(self, ctx, offset):
        margin_top = 50
        next_prev_height = 20
        val_height = 30
        next_label = ""
        prev_label = ""

        if len(self.groups) > self.value + 1:
            next_label = self.groups[self.value + 1].label

        if (self.value - 1) >= 0:
            prev_label = self.groups[self.value - 1].label

        # Param name
        show_text(
            ctx,
            offset,
            margin_top,
            prev_label,
            height=next_prev_height,
            font_color=definitions.WHITE,
        )

        # Param value
        color = self.get_color_func()
        show_text(
            ctx,
            offset,
            margin_top + next_prev_height,
            str(self.label),
            height=val_height,
            font_color=color,
        )

        # Param name
        name_height = 20
        show_text(
            ctx,
            offset,
            margin_top + next_prev_height + val_height,
            next_label,
            height=next_prev_height,
            font_color=definitions.WHITE,
        )


class OSCGroup(object):
    name = "Group"

    @property
    def size(self):
        return sum([control.size for control in self.controls])

    def __init__(self, config, get_color_func=None, send_osc_func=None):
        if config["$type"] != "group":
            raise Exception("Invalid type passed to new OSCGroup")
        self.message = None
        self.label = ""
        self.controls = []
        self.message = config.get("onselect", None)
        self.label = config.get("label", "Group")
        self.send_osc_func = send_osc_func
        self.get_color_func = get_color_func

        for item in config["controls"]:
            match item["$type"]:
                case "group":
                    self.controls.append(
                        OSCGroup(
                            item,
                            get_color_func=get_color_func,
                            send_osc_func=send_osc_func,
                        )
                    )
                case "control-range":
                    self.controls.append(
                        OSCControl(
                            item,
                            get_color_func=get_color_func,
                            send_osc_func=send_osc_func,
                        )
                    )
                case "control-menu":
                    self.controls.append(
                        OSCControlMenu(
                            item,
                            get_color_func=get_color_func,
                            send_osc_func=send_osc_func,
                        )
                    )
                case "control-spacer":
                    self.controls.append(ControlSpacer())
                case "control-macro":
                    self.controls.append(
                        OSCControlMacro(
                            item,
                            get_color_func=get_color_func,
                            send_osc_func=send_osc_func,
                        )
                    )

    def get_control(self, id):
        if isinstance(id, int) and id < len(self.controls):
            return self.controls[id]
        elif isinstance(id, str):
            el = next(x for x in self.controls if x.label == id)
            if el:
                return el

    def select(self):
        if self.message:
            self.send_osc_func(self.message["address"], self.message["value"])


class OSCControlMenu(object):
    name = "Menu"

    @property
    def label(self):
        active = self.get_active_menu_item()
        if active:
            return active.label
        return ""

    def __init__(self, config, get_color_func=None, send_osc_func=None):
        if config["$type"] != "control-menu":
            raise Exception("Invalid config passed to new OSCControlMenu")

        self.items = []
        self.value = 0
        self.get_color_func = get_color_func
        self.send_osc_func = send_osc_func
        self.message = config.get("onselect", None)
        self.size = 0

        for item in config.get("items", []):
            self.items.append(
                OSCMenuItem(
                    item, send_osc_func=send_osc_func, get_color_func=get_color_func
                )
            )

        if self.message:
            self.send_osc_func(self.message["address"], self.message["value"])

    def set_state(self, address, *args):
        value, *rest = args
        for idx, item in enumerate(self.items):
            if (
                item.message is not None
                and item.message["address"] == address
                and float(item.message["value"]) == float(value)
            ):
                self.value = idx

    def update_value(self, increment, **kwargs):
        if not self.value:
            pass

        if 0 <= (self.value + increment) < len(self.items):
            self.value += increment
            active_item = self.get_active_menu_item()
            if hasattr(active_item, "select"):
                active_item.select()

    def get_active_menu_item(self):
        if len(self.items) > self.value:
            return self.items[self.value]

    def select(self):
        active_item = self.get_active_menu_item()
        if hasattr(active_item, "select"):
            active_item.select()

    def draw(self, ctx, offset):
        margin_top = 50
        next_prev_height = 20
        val_height = 30
        next_label = ""
        prev_label = ""

        if len(self.items) > self.value + 1:
            next_label = self.items[self.value + 1].label

        if (self.value - 1) >= 0:
            prev_label = self.items[self.value - 1].label

        # Param name
        show_text(
            ctx,
            offset,
            margin_top,
            prev_label,
            height=next_prev_height,
            font_color=definitions.WHITE,
        )

        # Param value
        color = self.get_color_func()
        show_text(
            ctx,
            offset,
            margin_top + next_prev_height,
            str(self.label),
            height=val_height,
            font_color=color,
        )

        # Param name
        name_height = 20
        show_text(
            ctx,
            offset,
            margin_top + next_prev_height + val_height,
            next_label,
            height=next_prev_height,
            font_color=definitions.WHITE,
        )


class OSCMenuItem(object):
    name = "Menu Item"

    def __init__(self, config, get_color_func=None, send_osc_func=None):
        if config.get("$type", None) != "menu-item":
            raise Exception("Invalid config passed to new OSCMenuItem")

        self.label = config.get("label", "")
        self.message = config.get("onselect", None)
        self.get_color_func = get_color_func
        self.send_osc_func = send_osc_func

    def select(self):
        print(self.message["address"], self.message["value"], "MENU ITEM DEBUG")
        self.send_osc_func(self.message["address"], self.message["value"])
