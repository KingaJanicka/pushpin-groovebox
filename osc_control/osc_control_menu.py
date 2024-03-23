import definitions
import osc_utils
import math
import push2_python
from display_utils import show_text
from osc_control.osc_menu_item import OSCMenuItem


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
        self.message = None
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
