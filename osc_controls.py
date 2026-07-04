from __future__ import annotations

import definitions
import math
import push2_python
from user_interface.display_utils import show_text
import logging
from typing import Any, Callable

logger = logging.getLogger("osc_controls")
# logger.setLevel(level=logging.DEBUG)

OscSendFunc = Callable[[str, float | None], None]
ColorFunc = Callable[[], str]
ConfigDict = dict[str, Any]


SCALING_FACTOR = 127  # MIDI-style responsiveness for knobs
DECIMAL_PLACES = 2

"""
scale_value() -> float()
    value float(): value to be scaled
    min_val float(): minimum value, inclusive
    max_val float(): maximum value, exclusive
    decimals int(): number of decimal places
"""


def scale_value(value: float, min_val: float, max_val: float, decimals: int = DECIMAL_PLACES) -> float:
    return round(float(value / SCALING_FACTOR * (max_val - min_val)), decimals)


def closest(lst: list[float], K: float) -> float:
    return lst[min(range(len(lst)), key=lambda i: abs(lst[i] - K))]


class OSCControl(object):
    name = "Range"
    size = 1

    def __init__(
        self,
        config: ConfigDict,
        get_color_func: ColorFunc | None = None,
        send_osc_func: OscSendFunc | None = None,
    ) -> None:
        if config["$type"] != "control-range":
            raise Exception("Invalid config passed to new OSCControl")
        self.color: str = definitions.GRAY_LIGHT
        self.color_rgb: list[int] | None = None
        self.label: str = config["label"]
        self.address: str = config["address"]
        self.min: float = config["min"]
        self.max: float = config["max"]
        self.value: float = 0.0
        self.modmatrix: bool = config.get("modmatrix", True)
        self.string: str = ""
        self.get_color_func: ColorFunc = get_color_func or (lambda: definitions.GRAY_LIGHT)
        self.send_osc_func: OscSendFunc = send_osc_func or (lambda addr, val: None)
        self.log = logger.getChild(f"{self.label}:Range")
        self.bipolar: bool = config.get("bipolar", False)

    def query(self) -> None:
        self.send_osc_func("/q" + self.address, None)

    def draw(self, ctx: Any, x_part: int, draw_lock: bool = False, lock_value: float | None = None) -> None:
        font_color = definitions.WHITE        
        value = self.value
        
        
        if draw_lock is not False:
            # font_color = definitions.RED
            font_color = self.get_color_func()
            if lock_value is not None:
                value = lock_value
            else:
                value = float(0.0)
            
            
            display_w = push2_python.constants.DISPLAY_LINE_PIXELS
            x = (display_w // 8) * x_part
            y = 21
            x_witdh = 118
            y_height = 72
            ctx.move_to(x,y)
            ctx.line_to(x + x_witdh,y)
            ctx.line_to(x + x_witdh,y+y_height)
            ctx.line_to(x, y+y_height)
            ctx.close_path()
            ctx.set_source_rgb(*definitions.get_color_rgb_float(definitions.GRAY_DARK))
            ctx.fill()
            # ctx.restore()

        
        
        
        if self.bipolar == True:
            margin_top = 25
            # Param name
            name_height = 20
            show_text(
                ctx,
                x_part,
                margin_top,
                self.label,
                height=name_height,
                font_color=font_color,
                center_horizontally=True,
            )

            # Param value
            val_height = 20
            color = self.get_color_func()
            show_text(
                ctx,
                x_part,
                margin_top + name_height,
                str(round(value, 2)),
                # str(self.string),
                height=val_height,
                font_color=color,
                margin_left=int(value / self.max * 80 + 10),
            )

            # Knob
            ctx.save()

            height = 30
            length = 80
            radius = height / 2
            triangle_padding = 3
            triangle_size = 6

            display_w = push2_python.constants.DISPLAY_LINE_PIXELS
            x = (display_w // 8) * x_part
            y = margin_top + name_height + val_height + radius + 5

            xc = x + radius + 3
            yc = y

            # This is needed to prevent showing line from previous position
            ctx.set_source_rgb(0, 0, 0)
            ctx.move_to(xc, yc)
            ctx.stroke()

            # Inner line
            bipolar_value = value / self.max - 0.5 * self.max
            ctx.move_to(xc, yc)
            ctx.line_to(xc + length, yc)
            ctx.set_source_rgb(*definitions.get_color_rgb_float(definitions.GRAY_LIGHT))
            ctx.set_line_width(1)
            ctx.stroke()

            # Outer line
            ctx.move_to(xc + 0.5 * length, yc)
            ctx.line_to(xc + 0.5 * length + bipolar_value * length, yc)
            ctx.set_source_rgb(*definitions.get_color_rgb_float(color))
            ctx.set_line_width(3)
            ctx.stroke()

            # Triangle indicator
            ctx.move_to(xc + length * value / self.max, yc - triangle_padding)
            ctx.line_to(
                xc + length * value / self.max - triangle_size,
                yc - triangle_padding - 2 * triangle_size,
            )
            ctx.line_to(
                xc + length * value / self.max + triangle_size,
                yc - triangle_padding - 2 * triangle_size,
            )
            ctx.move_to(xc + length * value, yc - triangle_padding)
            ctx.close_path()
            ctx.set_source_rgb(*definitions.get_color_rgb_float(color))
            ctx.fill()
            ctx.restore()

        if self.bipolar == False:
            margin_top = 25

            # Param name
            name_height = 20
            show_text(
                ctx,
                x_part,
                margin_top,
                self.label,
                height=name_height,
                font_color=font_color,
                center_horizontally=True,
            )

            # Param value
            val_height = 20
            color = self.get_color_func()
            show_text(
                ctx,
                x_part,
                margin_top + name_height,
                str(round(value, 2)),
                # str(self.string),
                height=val_height,
                font_color=color,
                margin_left=int(value / self.max * 80 + 10),
            )

            # Knob
            ctx.save()

            height = 30
            length = 80
            radius = height / 2
            triangle_padding = 3
            triangle_size = 6

            display_w = push2_python.constants.DISPLAY_LINE_PIXELS
            x = (display_w // 8) * x_part
            y = margin_top + name_height + val_height + radius + 5

            xc = x + radius + 3
            yc = y

            # This is needed to prevent showing line from previous position
            ctx.set_source_rgb(0, 0, 0)
            ctx.move_to(xc, yc)
            ctx.stroke()

            # Inner line
            ctx.move_to(xc, yc)
            ctx.line_to(xc + length, yc)

            ctx.set_source_rgb(*definitions.get_color_rgb_float(definitions.GRAY_LIGHT))
            ctx.set_line_width(1)
            ctx.stroke()

            # Outer line
            ctx.move_to(xc, yc)
            ctx.line_to(xc + length * value / self.max, yc)
            ctx.set_source_rgb(*definitions.get_color_rgb_float(color))
            ctx.set_line_width(3)
            ctx.stroke()

            # Triangle indicator
            ctx.move_to(xc + length * value / self.max, yc - triangle_padding)
            ctx.line_to(
                xc + length * value / self.max - triangle_size,
                yc - triangle_padding - 2 * triangle_size,
            )
            ctx.line_to(
                xc + length * value / self.max + triangle_size,
                yc - triangle_padding - 2 * triangle_size,
            )
            ctx.move_to(xc + length * value, yc - triangle_padding)
            ctx.close_path()
            ctx.set_source_rgb(*definitions.get_color_rgb_float(color))
            ctx.fill()
            ctx.restore()


    def draw_submenu(self, ctx: Any, x_part: int, draw_lock: bool = False, lock_value: float | None = None) -> None:
        font_color = definitions.WHITE        
        value = self.value
        if draw_lock is not False:
            font_color = self.get_color_func()
            if lock_value is not None:
                value = lock_value
            else:
                value = float(0.0)
        
        
            display_w = push2_python.constants.DISPLAY_LINE_PIXELS
            x = (display_w // 8) * x_part
            y = 110
            x_witdh = 118
            y_height = 30
            ctx.move_to(x,y)
            ctx.line_to(x + x_witdh,y)
            ctx.line_to(x + x_witdh,y+y_height)
            ctx.line_to(x, y+y_height)
            ctx.close_path()
            ctx.set_source_rgb(*definitions.get_color_rgb_float(definitions.GRAY_DARK))
            ctx.fill()
            # ctx.restore()
        
        
        margin_top = 110
        line_padding = 4
        line_width = 80
        # Param name
        name_height = 15
        show_text(
            ctx,
            x_part,
            margin_top,
            self.label,
            height=name_height,
            font_color=font_color,
            center_horizontally=True,
        )

        # Param value
        val_height = 15
        color = self.get_color_func()
        show_text(
            ctx,
            x_part,
            margin_top + name_height,
            str(round(value, 2)),
            height=val_height,
            font_color=color,
            margin_left=int(value / self.max * line_width * 0.75 + 10),
        )

        radius = name_height / 2
        display_w = push2_python.constants.DISPLAY_LINE_PIXELS
        x = (display_w // 8) * x_part
        y = margin_top + val_height + 6
        xc = x + radius + 3
        yc = y

        # Left line
        ctx.move_to(xc - line_padding, yc - 5)
        ctx.line_to(xc - line_padding, yc + 5)

        ctx.set_source_rgb(*definitions.get_color_rgb_float(definitions.GRAY_LIGHT))
        ctx.set_line_width(1)
        ctx.stroke()

        # Right line
        ctx.move_to(xc + line_padding + line_width, yc - 5)
        ctx.line_to(xc + line_padding + line_width, yc + 5)

        ctx.set_source_rgb(*definitions.get_color_rgb_float(definitions.GRAY_LIGHT))
        ctx.set_line_width(1)
        ctx.stroke()

        # Knob
        ctx.save()

    def set_state(self, address: str, *args: Any) -> None:
        value, *rest = args
        self.log.debug((address, value))
        self.value = value
        # this human readable string doesn't change with knob movements, querry fixes it but makes it glitchy
        # self.string = string

    def update_value(self, increment: float, **kwargs: Any) -> None:
        scaled = scale_value(increment, self.min, self.max)
        if self.value + scaled > self.max:
            self.value = self.max
        elif self.value + scaled < self.min:
            self.value = self.min
        else:
            self.value += scaled
        # print("update value: adress", self.address, "value", self.value)
        # Send cc message, subtract 1 to number because MIDO works from 0 - 127
        # msg = mido.Message('control_change', control=self.address, value=self.value)
        # msg=f'control_change {self.address} {self.value}'
        self.send_osc_func(self.address, float(self.value))


class OSCSpacerAddress(object):
    name = "SpacerAddress"
    size = 1

    def __init__(self, config: ConfigDict, send_osc_func: OscSendFunc | None = None) -> None:
        if config["$type"] != "control-spacer-address":
            raise Exception("Invalid config passed to new OSCControl")
        self.label: str = ""
        self.address: str = config["address"]
        self.log = logger.getChild(f"{self.label}:Range")
        self.modmatrix: bool = False
        self.items: list[Any] = []
        self.value: float = 0.0
        self.send_osc_func: OscSendFunc = send_osc_func or (lambda addr, val: None)

    def draw(self, *args: Any, **kwargs: Any) -> None:
        pass

    def draw_submenu(self, *args: Any, **kwargs: Any) -> None:
        pass

    def update_value(self, *args: Any, **kwargs: Any) -> None:
        pass

    def query(self) -> None:
        self.send_osc_func("/q" + self.address, None)

    def set_state(self, address: str, *args: Any) -> None:
        value, *rest = args
        self.log.debug((address, value))
        self.value = value
class ControlSpacer(object):
    name = "Spacer"

    address = None
    label = ""
    size = 1
    color = definitions.GRAY_LIGHT
    color_rgb = None
    label = ""
    get_color_func = None
    modmatrix = False

    def __init__(self) -> None:
        pass

    def draw(self, *args: Any, **kwargs: Any) -> None:
        pass

    def draw_submenu(self, *args: Any, **kwargs: Any) -> None:
        pass

    def update_value(self, *args: Any, **kwargs: Any) -> None:
        pass

    def query(self, *args: Any, **kwargs: Any) -> None:
        pass

class OSCControlMacro(object):
    name = "Macro"
    size = 1

    def __init__(
        self,
        config: ConfigDict,
        get_color_func: ColorFunc | None = None,
        send_osc_func: OscSendFunc | None = None,
    ) -> None:
        if config["$type"] != "control-macro":
            raise Exception("Invalid config passed to new OSCControlMacro")

        self.color: str = definitions.GRAY_LIGHT
        self.color_rgb: list[int] | None = None
        self.label: str = config["label"]
        self.address: str | None = None
        self.min: float = 0.0
        self.max: float = 1.0
        self.value: float = 0.0
        self.modmatrix: bool = config.get("modmatrix", True)
        self.get_color_func: ColorFunc = get_color_func or (lambda: definitions.GRAY_LIGHT)
        self.params: list[ConfigDict] = config["params"]
        self.send_osc_func: OscSendFunc = send_osc_func or (lambda addr, val: None)
        self.log = logger.getChild("Macro")

    def update_value(self, increment: float, **kwargs: Any) -> None:
        scaled = scale_value(increment, self.min, self.max)
        if self.value + scaled > self.max:
            self.value = self.max
        elif self.value + scaled < self.min:
            self.value = self.min
        else:
            self.value += scaled
        # print("update value: adress", self.address, "value", self.value)
        # Send cc message, subtract 1 to number because MIDO works from 0 - 127
        # msg = mido.Message('control_change', control=self.address, value=self.value)
        # msg=f'control_change {self.address} {self.value}'

        for param in self.params:
            self.send_osc_func(param["address"], float(self.value))

    def query(self) -> None:
        if self.address:
            self.send_osc_func("/q" + self.address, None)

    def set_state(self, address: str, *args: Any) -> None:
        value, *rest = args
        self.log.debug((address, value))
        self.value = scale_value(value, self.min, self.max)
        # Find by index


class OSCControlSwitch(object):
    name = "Switch"
    address = None

    @property
    def visible(self) -> OSCGroup:
        return self.groups[int(self.value)]

    @property
    def size(self) -> int:
        return max(group.size for group in self.groups) + 1

    @property
    def label(self) -> str | None:
        active = self.get_active_group()
        if active:
            return active.label
        return None

    def __init__(
        self,
        config: ConfigDict,
        get_color_func: ColorFunc | None = None,
        send_osc_func: OscSendFunc | None = None,
        dispatcher: Any = None,
    ) -> None:
        if config["$type"] != "control-switch":
            raise Exception("Invalid config passed to new OSCControlSwitch")

        if dispatcher == None:
            raise Exception("Switch not given dispatcher")

        self.groups: list[OSCGroup] = []
        self.value: float = 0.0
        self.get_color_func: ColorFunc = get_color_func or (lambda: definitions.GRAY_LIGHT)
        self.send_osc_func: OscSendFunc = send_osc_func or (lambda addr, val: None)
        self.modmatrix: bool = config.get("modmatrix", True)
        self.log = logger.getChild(f"{self.label}:Switch")
        groups = config.get("groups", [])

        for item in groups:
            group_control = OSCGroup(
                item,
                get_color_func=get_color_func,
                send_osc_func=send_osc_func,
                dispatcher=dispatcher,
                set_parent_state=self.set_state
            )

            self.groups.append(group_control)

        if (
            len(self.groups) > 0
            and self.groups[int(self.value)]
            and hasattr(self.groups[int(self.value)], "select")
        ):
            self.groups[int(self.value)].select()
            

    def query(self) -> None:
        if self.address:
            self.send_osc_func("/q" + self.address, None)
        active_group = self.get_active_group()
        if active_group:
            active_group.query()

    def update_value(self, increment: float, **kwargs: Any) -> None:
        prev_idx = int(self.value)
        scaled = scale_value(increment, 0, len(self.groups))
        if 0 <= (self.value + scaled) <= len(self.groups):
            self.value += scaled
        if int(self.value) != prev_idx:
            active = self.get_active_group()
            if active:
                if active.message:
                    self.send_osc_func(
                        active.message["address"], float(active.message["value"])
                    )
                active.select()

    def get_active_group(self) -> OSCGroup | None:
        if int(self.value) <= len(self.groups) - 1:
            return self.groups[int(self.value)]
        return None

    def set_state(self, address: str, *args: Any) -> None:
        # print("Control switch args", args)
        value, label = args
        # print("switch val = ", value)
        self.log.debug((address, args))
        # TODO do we need the following?
        for idx, group in enumerate(self.groups):
            for control in group.controls:
                if isinstance(control, OSCControl) and control.address == address:
                    self.value = float(idx)
                elif isinstance(control, OSCControlMacro) and any(
                    [param for param in control.params if param["address"] == address]
                ):
                    self.value = float(idx)
                elif isinstance(control, OSCControlMenu) and (
                    any([item for item in control.items if item.address == address])
                    or control.address == address
                ):
                    first = group.controls[0] if group.controls else None
                    if (
                        isinstance(first, OSCControlMenu)
                        and first.items
                        and int(first.items[0].message["value"]) == int(value)
                        and first.items[0].address == address
                    ):
                        self.value = float(idx)

    def draw(self, ctx: Any, offset: int) -> None:
        margin_top = 30
        next_prev_height = 15
        val_height = 25
        next_label = ""
        prev_label = ""
        idx = int(self.value)
        if len(self.groups) > idx + 1:
            next_label = self.groups[idx + 1].label

        if (idx - 1) >= 0:
            prev_label = self.groups[idx - 1].label

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

    def draw_submenu(self, ctx: Any, offset: int, draw_lock: bool = False, lock_value: float | None = None) -> None:
        margin_top = 110
        val_height = 15

        # Param value
        color = self.get_color_func()
        show_text(
            ctx,
            offset,
            margin_top,
            str(self.label),
            height=val_height,
            font_color=color,
        )


class OSCGroup(object):
    name = "Group"
    address = None

    @property
    def size(self) -> int:
        return sum([control.size for control in self.controls])

    def __init__(
        self,
        config: ConfigDict,
        get_color_func: ColorFunc | None = None,
        send_osc_func: OscSendFunc | None = None,
        dispatcher: Any = None,
        set_parent_state: Callable[..., Any] | None = None,
    ) -> None:
        if config["$type"] != "group":
            raise Exception("Invalid type passed to new OSCGroup")

        if dispatcher == None:
            raise Exception("No dispatcher provided to OSCGroup")

        self.dispatcher = dispatcher
        self.message: ConfigDict | None = config.get("onselect", None)
        self.label: str = config.get("label", "Group")
        self.controls: list[Any] = []
        self.send_osc_func: OscSendFunc = send_osc_func or (lambda addr, val: None)
        self.get_color_func: ColorFunc = get_color_func or (lambda: definitions.GRAY_LIGHT)
        self.modmatrix: bool = config.get("modmatrix", True)
        self.log = logger.getChild(f"{self.label}:Group")

        for item in config["controls"]:
            match item["$type"]:
                case "group":
                    control = OSCGroup(
                        item,
                        get_color_func=get_color_func,
                        send_osc_func=send_osc_func,
                        dispatcher=dispatcher,
                    )

                    # This might be wrong
                    # if control.address:
                    #     self.dispatcher.map(control.address, control.set_state)

                    self.controls.append(control)
                case "control-range":
                    control = OSCControl(
                        item,
                        get_color_func=get_color_func,
                        send_osc_func=send_osc_func,
                    )

                    if control.address:
                        self.dispatcher.map(control.address, control.set_state)

                    self.controls.append(control)

                case "control-menu":
                    control = OSCControlMenu(
                        item,
                        get_color_func=get_color_func,
                        send_osc_func=send_osc_func,
                    )
                    
                    _menu: OSCControlMenu = control
                    def set_state(*args: Any) -> None:
                        _menu.set_state(*args)
                        if set_parent_state is not None:
                            set_parent_state(*args)

                    if control.address:
                        self.dispatcher.map(control.address, set_state)

                    self.controls.append(control)
                case "control-spacer":
                    self.controls.append(ControlSpacer())
                case "control-spacer-address":
                    control = OSCSpacerAddress(
                        item,
                        send_osc_func=send_osc_func,
                    )

                    if control.address:
                        self.dispatcher.map(control.address, control.set_state)

                    self.controls.append(control)
                case "control-macro":
                    control = OSCControlMacro(
                        item,
                        get_color_func=get_color_func,
                        send_osc_func=send_osc_func,
                    )

                    if control.address:
                        self.dispatcher.map(control.address, control.set_state)

                    self.controls.append(control)

    def get_control(self, id: int | str) -> Any:
        if isinstance(id, int) and id < len(self.controls):
            return self.controls[id]
        elif isinstance(id, str):
            el = next(x for x in self.controls if x.label == id)
            if el:
                return el

    def query(self) -> None:
        if self.address:
            self.send_osc_func("/q" + self.address, None)
        for control in self.controls:
            if hasattr(control, "query"):
                control.query()

    def select(self) -> None:
        unique_addresses = list(set([control.address for control in self.controls]))
        self.log.debug((unique_addresses, "!!!"))
        for address in unique_addresses:
            self.send_osc_func("/q" + address, None)


class OSCControlMenu(object):
    name = "Menu"
    
    @property
    def label(self):
        active = self.get_active_menu_item()
        if active:
            return active.label
        return ""

    def __init__(
        self,
        config: ConfigDict,
        get_color_func: ColorFunc | None = None,
        send_osc_func: OscSendFunc | None = None,
    ) -> None:
        if config["$type"] != "control-menu":
            raise Exception("Invalid config passed to new OSCControlMenu")

        self.items: list[OSCMenuItem] = []
        self.get_color_func: ColorFunc = get_color_func or (lambda: definitions.GRAY_LIGHT)
        self.send_osc_func: OscSendFunc = send_osc_func or (lambda addr, val: None)
        self.modmatrix: bool = config.get("modmatrix", True)
        self.menu_label: str | None = config.get("menu_label", None)
        self.message: ConfigDict | None = config.get("onselect", None)
        self.address: str | None = self.message["address"] if self.message else None
        self.value: float | int | None = self.message["value"] if self.message else None
        self.size: int = 0
        self.log = logger.getChild(f"{self.label}:Menu")

        for item in config.get("items", []):
            self.items.append(OSCMenuItem(item, send_osc_func=send_osc_func))

        if self.value is None and len(self.items) > 0:
            self.value = 0
        if self.address is None and len(self.items) > 0:
            self.address = self.items[0].address  # assumes all items have same address
        
    def set_state(self, address: str, value: float, *args: Any) -> None:
        self.log.debug((address, value))
        self.value = self.get_closest_idx(value)

    def query(self) -> None:
        if self.address:
            self.send_osc_func("/q" + self.address, None)

    def update_value(self, increment: float, **kwargs: Any) -> None:
        scaled = scale_value(increment, 0, len(self.items))
        current = self.value if self.value is not None else 0.0
        new_value = current + scaled

        # print(self.label, min_item_value, max_item_value, scaled, self.value, new_value)
        if 0 <= new_value < len(self.items):
            self.value = new_value
        elif new_value < 0:
            self.value = 0
        elif new_value > len(self.items) - 1:
            self.value = len(self.items) - 1

        active_item = self.get_active_menu_item()
        if active_item is not None:
            active_item.select()

    def get_active_menu_item(self) -> OSCMenuItem | None:
        if self.value is not None and math.floor(self.value) < len(self.items):
            return self.items[math.floor(self.value)]
        return None

    def get_closest_idx(self, value: float) -> int | None:
        closest_value = closest([float(item.value) for item in self.items if item.value is not None], value)
        for idx, item in enumerate(self.items):
            if item.value == closest_value:
                return idx
        return None

    def select(self) -> None:
        print("Select called")
        active = self.get_active_menu_item()
        if active is None:
            return
        if active.address is None or active.value is None:
            return
        self.log.debug((self.value, active.address, active.value))
        self.send_osc_func(active.address, float(active.value))

    def draw(self, ctx: Any, offset: int, draw_lock: bool = False, lock_value: float | None = None) -> None:
        margin_top = 30
        tip_top = 0
        tip_height = 0
        next_prev_height = 15
        val_height = 25
        next_label = ""
        prev_label = ""

        if self.value is None:
            return
        idx = int(math.floor(self.value))

        font_color = definitions.WHITE
        if draw_lock != False:
            # font_color = definitions.RED
            font_color = self.get_color_func()
            if lock_value is not None:
                idx = int(lock_value)
            else:
                idx = int(0.0)
            background_color = definitions.GRAY_DARK
            ctx.save()
            display_w = push2_python.constants.DISPLAY_LINE_PIXELS
            x = (display_w // 8) * offset
            y = 21
            x_witdh = 118
            y_height = 72
            ctx.rectangle(x,y,x_witdh,y_height)
            ctx.set_source_rgb(*definitions.get_color_rgb_float(definitions.GRAY_DARK))
            ctx.fill()
            ctx.restore()

            
        if len(self.items) > idx + 1:
            next_label = self.items[idx + 1].label

        current_label = self.items[idx].label
        
        if (idx - 1) >= 0:
            prev_label = self.items[idx - 1].label

        # If a tip is present
        if self.menu_label != None:
            # Show tip
            tip_top = 25
            tip_height = 20
            show_text(
                ctx,
                offset,
                tip_top,
                self.menu_label,
                height=tip_height,
                font_color=font_color,
                center_horizontally=True,
            )
        
        if prev_label:
            # Last param name
            show_text(
                ctx,
                offset,
                margin_top + tip_top,
                prev_label,
                height=next_prev_height,
                font_color=font_color,
                background_color=None
            )

        # Current param value
        color = self.get_color_func()
        show_text(
            ctx,
            offset,
            margin_top + next_prev_height + tip_top,
            current_label,
            height=val_height,
            font_color=color,
            background_color=None
        )

        # Next param name
        if next_label:
            show_text(
                ctx,
                offset,
                margin_top + next_prev_height + val_height + tip_top,
                next_label,
                height=next_prev_height,
                font_color=font_color,
                background_color=None
            )

    def draw_submenu(self, ctx: Any, offset: int, draw_lock: bool = False, lock_value: float | None = None) -> None:
        margin_top = 110
        val_height = 15
        # TODO: need to add the lock drawing stuff here
        # Current param value
        label = self.label
        if draw_lock != False:
            # font_color = definitions.RED
            if lock_value is not None:
                idx = int(lock_value)
            else:
                idx = int(0.0)
            label = self.items[idx].label
            ctx.save()
            display_w = push2_python.constants.DISPLAY_LINE_PIXELS
            x = (display_w // 8) * offset
            y = 95
            x_witdh = 118
            y_height = 25
            ctx.rectangle(x,y,x_witdh,y_height)
            ctx.set_source_rgb(*definitions.get_color_rgb_float(definitions.GRAY_DARK))
            ctx.fill()
            ctx.restore()
        
        color = self.get_color_func()
        show_text(
            ctx,
            offset,
            margin_top,
            str(label),
            height=val_height,
            font_color=color,
        )


class OSCMenuItem(object):
    name = "Menu Item"
    #TODO This needs to be updated along with state refresh
    def __init__(
        self,
        config: ConfigDict,
        get_color_func: ColorFunc | None = None,
        send_osc_func: OscSendFunc | None = None,
    ) -> None:
        if config.get("$type", None) != "menu-item":
            raise Exception("Invalid config passed to new OSCMenuItem")

        self.label: str = config.get("label", "")
        self.message: ConfigDict | None = config.get("onselect", None)
        self.modmatrix: bool = config.get("modmatrix", True)
        self.address: str | None = self.message["address"] if self.message else None
        self.value: float | int | None = self.message["value"] if self.message else None
        self.send_osc_func: OscSendFunc = send_osc_func or (lambda addr, val: None)

    def select(self) -> None:
        if self.address is not None and self.value is not None:
            self.send_osc_func(self.address, float(self.value))
