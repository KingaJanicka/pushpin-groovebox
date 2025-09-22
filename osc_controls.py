import definitions
import math
import push2_python
from user_interface.display_utils import show_text
import logging

logger = logging.getLogger("osc_controls")
# logger.setLevel(level=logging.DEBUG)


SCALING_FACTOR = 127  # MIDI-style responsiveness for knobs
DECIMAL_PLACES = 2

"""
scale_value() -> float()
    value float(): value to be scaled
    min_val float(): minimum value, inclusive
    max_val float(): maximum value, exclusive
    decimals int(): number of decimal places
"""


def scale_value(value, min_val, max_val, decimals=DECIMAL_PLACES):
    return round(float(value / SCALING_FACTOR * (max_val - min_val)), decimals)


def closest(lst, K):
    return lst[min(range(len(lst)), key=lambda i: abs(lst[i] - K))]


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
        self.value = 0.0
        self.modmatrix = config.get("modmatrix", True)
        self.string = ""
        self.get_color_func = None
        self.label = config["label"]
        self.address = config["address"]
        self.get_color_func = get_color_func
        self.min = config["min"]
        self.max = config["max"]
        self.log = logger.getChild(f"{self.label}:Range")
        self.bipolar = None
        if "bipolar" in config:
            self.bipolar = config["bipolar"]
        else:
            self.bipolar = False

        if send_osc_func:
            self.send_osc_func = send_osc_func
            # self.send_osc_func(f"/q{self.address}", None)

    def query(self):
        self.send_osc_func("/q" + self.address, None)

    def send_osc_func(self, address, payload):
        pass

    def draw(self, ctx, x_part, draw_lock=False, lock_value=None):
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


    def draw_submenu(self, ctx, x_part, draw_lock=False, lock_value=None):
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

    def set_state(self, address, *args):
        value, *rest = args
        self.log.debug((address, value))
        self.value = value
        # this human readable string doesn't change with knob movements, querry fixes it but makes it glitchy
        # self.string = string

    def update_value(self, increment, **kwargs):
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

    def __init__(self, config, send_osc_func=None):
        if config["$type"] != "control-spacer-address":
            raise Exception("Invalid config passed to new OSCControl")
        self.label = ""
        self.address = config["address"]
        self.log = logger.getChild(f"{self.label}:Range")
        self.modmatrix = False

        if send_osc_func:
            self.send_osc_func = send_osc_func
            # self.send_osc_func(f"/q{self.address}", None)

    def draw(self, *args, **kwargs):
        pass

    def draw_submenu(self, *args, **kwargs):
        pass

    def update_value(self, *args, **kwargs):
        pass

    def query(self):
        self.send_osc_func("/q" + self.address, None)

    def set_state(self, address, *args):
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

    def __init__(self):
        pass

    def draw(self, *args, **kwargs):
        pass

    def draw_submenu(self, *args, **kwargs):
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
        self.value = 0.0
        self.modmatrix = config.get("modmatrix", True)
        self.get_color_func = None
        self.label = config["label"]
        self.get_color_func = get_color_func
        self.params = config["params"]
        self.get_color_func = get_color_func
        self.send_osc_func = send_osc_func
        self.log = logger.getChild("Macro")

    def update_value(self, increment, **kwargs):
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

    def query(self):
        self.send_osc_func("/q" + self.address, None)

    def set_state(self, address, *args):
        value, *rest = args
        self.log.debug((address, value))

        self.value = scale_value(value)
        # Find by index


class OSCControlSwitch(object):
    name = "Switch"
    address = None

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

    def __init__(
        self, config, get_color_func=None, send_osc_func=None, dispatcher=None
    ):
        if config["$type"] != "control-switch":
            raise Exception("Invalid config passed to new OSCControlSwitch")

        if dispatcher == None:
            raise Exception("Switch not given dispatcher")

        self.groups = []
        self.value = 0.0
        self.get_color_func = get_color_func
        self.send_osc_func = send_osc_func
        self.modmatrix = config.get("modmatrix", True)
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
            

    def query(self):
        if self.address:
            self.send_osc_func("/q" + self.address, None)

        active_group = self.get_active_group()
        active_group.query()

    def update_value(self, increment, **kwargs):
        if not self.value:
            pass

        scaled = scale_value(increment, 0, len(self.groups))

        if 0 <= (self.value + scaled) <= len(self.groups):
            self.value += scaled

            active_group = self.get_active_group()
            # if hasattr(active_group, "select"):
            #     active_group.select()

    def get_active_group(self):
        if int(self.value) <= len(self.groups) - 1:
            return self.groups[
                int(self.value)
            ]  
            # TODO: nasty but enables less-twitchy knobs, prob needs fixing

    def set_state(self, address, *args):
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
                    # print(address, value)
                    # TODO: THis is hardcoded needs a fix
                    try:
                        item = group.controls[0].items[0]
                        if int(item.message["value"]) == int(value) and item.address == address:
                            # print(item.label, item.value)
                            self.value = float(idx)
                    except Exception as e:
                        print("Exception in ControlSwitch set state", e)
                    # control.set_state(address, value)

    def draw(self, ctx, offset):
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

    def draw_submenu(self, ctx, offset, draw_lock=False, lock_value=None):
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
    def size(self):
        return sum([control.size for control in self.controls])

    def __init__(
        self, config, get_color_func=None, send_osc_func=None, dispatcher=None, set_parent_state=None
    ):
        if config["$type"] != "group":
            raise Exception("Invalid type passed to new OSCGroup")

        if dispatcher == None:
            raise Exception("No dispatcher provided to OSCGroup")

        self.dispatcher = dispatcher
        self.message = None
        self.label = ""
        self.controls = []
        self.message = config.get("onselect", None)
        self.label = config.get("label", "Group")
        self.send_osc_func = send_osc_func
        self.get_color_func = get_color_func
        self.modmatrix = config.get("modmatrix", True)
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
                    
                    def set_state(*args):
                        control.set_state(*args)
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

    def get_control(self, id):
        if isinstance(id, int) and id < len(self.controls):
            return self.controls[id]
        elif isinstance(id, str):
            el = next(x for x in self.controls if x.label == id)
            if el:
                return el

    def query(self):
        if self.address:
            self.send_osc_func("/q" + self.address, None)

        for control in self.controls:
            if hasattr(control, "query"):
                control.query()

    def select(self):
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

    def __init__(self, config, get_color_func=None, send_osc_func=None):
        if config["$type"] != "control-menu":
            raise Exception("Invalid config passed to new OSCControlMenu")

        self.items = []
        self.get_color_func = get_color_func
        self.send_osc_func = send_osc_func
        self.modmatrix = config.get("modmatrix", True)
        self.menu_label = config.get("menu_label", None)
        self.message = config.get("onselect", None)
        self.address = self.message["address"] if self.message else None
        self.value = self.message["value"] if self.message else None
        self.size = 0
        self.log = logger.getChild(f"{self.label}:Menu")

        for item in config.get("items", []):
            self.items.append(OSCMenuItem(item, send_osc_func=send_osc_func))

        if self.value is None and len(self.items) > 0:
            self.value = 0
        if self.address is None and len(self.items) > 0:
            self.address = self.items[0].address  # assumes all items have same address
        
    def set_state(self, address, value, *args):
        # if address == '/param/a/filter/1/type':
        #     print("EL PROBLEMO")
        self.log.debug((address, value))
        self.value = self.get_closest_idx(value)
        
    def query(self):
        # print("Control menu querry")
        self.send_osc_func("/q" + self.address, None)

    def update_value(self, increment, **kwargs):
        # print("Update val called")
        if not self.value:
            pass

        scaled = scale_value(increment, 0, len(self.items))
        new_value = self.value + scaled

        # print(self.label, min_item_value, max_item_value, scaled, self.value, new_value)
        if 0 <= new_value < len(self.items):
            self.value = new_value
        elif new_value < 0:
            self.value = 0
        elif new_value > len(self.items) - 1:
            self.value = len(self.items) - 1

        active_item = self.get_active_menu_item()
        if hasattr(active_item, "select"):
            active_item.select()

    def get_active_menu_item(self):
        if self.value != None and math.floor(self.value) < len(self.items):
            return self.items[math.floor(self.value)]

    def get_closest_idx(self, value):
        
        closest_value = closest([item.value for item in self.items], value)
        for idx, item in enumerate(self.items ) :
            if item.value == closest_value:
                return idx

    def select(self):
        print("Select called")
        active = self.get_active_menu_item()
        self.log.debug((self.value, active.address, active.value))
        self.send_osc_func(active.address, float(active.value))

    def draw(self, ctx, offset, draw_lock=False, lock_value=None):
        margin_top = 30
        tip_top = 0
        tip_height = 0
        next_prev_height = 15
        val_height = 25
        next_label = ""
        prev_label = ""

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

    def draw_submenu(self, ctx, offset, draw_lock=False, lock_value=None):
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
    def __init__(self, config, get_color_func=None, send_osc_func=None):
        if config.get("$type", None) != "menu-item":
            raise Exception("Invalid config passed to new OSCMenuItem")

        self.label = config.get("label", "")
        self.message = config.get("onselect", None)
        self.modmatrix = config.get("modmatrix", True)
        self.address = self.message["address"] if self.message else None
        self.value = self.message["value"] if self.message else None
        self.send_osc_func = send_osc_func

    def select(self):
        self.send_osc_func(self.address, float(self.value))
