import definitions
import osc_utils
import math
import push2_python
from display_utils import show_text


class OSCControl(object):
    color = definitions.GRAY_LIGHT
    color_rgb = None
    label = "Unknown"
    address = None
    min = 0.0
    max = 1.0
    value = 64
    vmin = 0
    vmax = 127
    get_color_func = None
    value_labels_map = {}
    size = 1
    active = False

    def __init__(
        self, label, address, min, max, get_color_func=None, send_osc_func=None
    ):
        self.label = label
        self.address = address
        self.get_color_func = get_color_func
        self.min = min
        self.max = max

        if send_osc_func:
            self.send_osc_func = send_osc_func
            self.send_osc_func(f"/q{address}", None)

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
            self.value_labels_map.get(str(self.value), str(self.value)),
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

    def set_state(self, address, raw):
        if not self.active:
            self.active = True
        value, *rest = raw.split(" ")
        self.value = float(value)

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
            self.address, osc_utils.scale_knob_value([self.value, self.min, self.max])
        )


class SpacerControl(OSCControl):
    address = None
    active = True

    def __init__(self):
        pass

    def draw(self, **kwargs):
        return

    def update_value(self, **kwargs):
        return


class OSCMacroControl(OSCControl):
    def __init__(self, label, params, get_color_func=None, send_osc_func=None):
        self.label = label
        self.params = params
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
            address, min, max = param
            # TODO may need to revisit how min/max is set
            self.send_osc_func(
                address, osc_utils.scale_knob_value([self.value, min, max])
            )


class OSCControlGroup(object):
    name = "Control Group"
    controls = []
    value = None
    size = 0
    message = None

    def __init__(self, config, get_color_func=None, send_osc_func=None):
        self.id = id
        self.label = config.get("name", "group")
        self.get_color_func = get_color_func
        self.send_osc_func = send_osc_func
        self.size = self.get_config_depth(config)
        self.message = config.get("value", [])
        self.get_color_func = get_color_func
        self.send_osc_func = send_osc_func
        self.controls = []
        controls = config.get("controls", [])

        self.size = 0

        for item in controls:
            if isinstance(item, dict) and "controls" in item:  # child control group
                child_group = OSCControlGroup(
                    item, get_color_func=get_color_func, send_osc_func=send_osc_func
                )
                self.controls.append(child_group)
            elif isinstance(item, list):  # bottom-level control group
                if len(item) == 4:  # range controls
                    label, address, min_val, max_val = item
                    self.controls.append(
                        OSCControl(
                            label,
                            address,
                            min_val,
                            max_val,
                            get_color_func=get_color_func,
                            send_osc_func=send_osc_func,
                        )
                    )
                elif len(item) == 3:  # menu controls
                    self.controls.append(
                        OSCControlGroupMenuItem(
                            item,
                            send_osc_func=send_osc_func,
                            get_color_func=get_color_func,
                        )
                    )

        if len(self.controls) > 0:
            is_bottom_level_group = all(
                not isinstance(item, OSCControlGroup) for item in self.controls
            )
            self.size = (
                len(self.controls) + 1
                if is_bottom_level_group
                else max([group.size for group in self.controls])
            )
            # Set initial index to 0 here
            self.value = 0

            # If all controls are menu items, send the active value
            if is_bottom_level_group and all(
                isinstance(c, OSCControlGroupMenuItem) for c in self.controls
            ):
                self.controls[self.value].select()

        # Run init logic
        init = config.get("value", None)
        if init:
            a, v = init
            self.send_osc_func(a, v)

    def update_value(self, increment, **kwargs):
        if not self.value:
            pass

        if 0 <= (self.value + increment) < len(self.controls):
            self.value += increment

            active_group = self.get_active_group()
            is_bottom_level_group = all(
                not isinstance(item, OSCControlGroup) for item in self.controls
            )
            if active_group and not is_bottom_level_group:
                a, v = active_group.message
                self.send_osc_func(a, v)

            # If all controls are menu items, send the active value
            if is_bottom_level_group and all(
                isinstance(c, OSCControlGroupMenuItem) for c in self.controls
            ):
                self.controls[self.value].select()

    def get_config_depth(self, dic, level=0):
        if not isinstance(dic, dict) or not dic:
            return level
        return max(self.get_config_depth(dic[key], level + 1) for key in dic)

    def get_active_group(self):
        if all(isinstance(item, OSCControlGroup) for item in self.controls):
            return self.controls[self.value]
        else:
            return None

    def get_control(self, id):
        if isinstance(id, int) and id < len(self.controls):
            return self.controls[id]
        elif isinstance(id, str):
            el = next(x for x in self.controls if x.label == id)
            if el:
                return el


class OSCControlGroupMenuItem(object):
    label = ""
    message = None

    def __init__(self, config, get_color_func=None, send_osc_func=None):
        label, *message = config
        self.label = label
        self.message = message
        self.get_color_func = get_color_func
        self.send_osc_func = send_osc_func

    def select(self):
        a, v = self.message
        self.send_osc_func(a, v)
