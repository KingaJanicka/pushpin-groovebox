import definitions
from display_utils import show_text

from display_utils import show_text
from osc_control.osc_control_menu import OSCControlMenu
from osc_control.osc_control_macro import OSCControlMacro
from osc_control.control_spacer import ControlSpacer
from osc_control.osc_control import OSCControl


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
