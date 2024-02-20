import definitions
import osc_utils
import math
import push2_python
from display_utils import show_text

class OSCControl(object):
    color = definitions.GRAY_LIGHT
    color_rgb = None
    label = 'Unknown'
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

    def __init__(self, label, address, min, max, get_color_func=None, send_osc_func=None):
        self.label = label
        self.address = address
        self.get_color_func = get_color_func
        self.min = min
        self.max = max
        
        if (send_osc_func):
            self.send_osc_func = send_osc_func
            self.send_osc_func(f"/q{address}", None)
        

    def send_osc_func(self, address, payload):
        pass

    def draw(self, ctx, x_part):
        margin_top = 25
        
        # Param name
        name_height = 20
        show_text(ctx, x_part, margin_top, self.label, height=name_height, font_color=definitions.WHITE)

        # Param value
        val_height = 30
        color = self.get_color_func()
        show_text(ctx, x_part, margin_top + name_height, self.value_labels_map.get(str(self.value), str(self.value)), height=val_height, font_color=color)

        # Knob
        ctx.save()

        circle_break_degrees = 80
        height = 55
        radius = height/2

        display_w = push2_python.constants.DISPLAY_LINE_PIXELS
        x = (display_w // 8) * x_part
        y = margin_top + name_height + val_height + radius + 5
        
        start_rad = (90 + circle_break_degrees // 2) * (math.pi / 180)
        end_rad = (90 - circle_break_degrees // 2) * (math.pi / 180)
        xc = x + radius + 3
        yc = y

        def get_rad_for_value(value):
            total_degrees = 360 - circle_break_degrees
            return start_rad + total_degrees * ((value - self.vmin)/(self.vmax - self.vmin)) * (math.pi / 180)

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
        ctx.set_source_rgb(* definitions.get_color_rgb_float(color))
        ctx.set_line_width(3)
        ctx.stroke()

        ctx.restore()
    
    def set_state(self, address, raw):
        if (not self.active):
            self.active = True
        value, *rest = raw.split(' ')
        self.value = float(value)
    
    def update_value(self, increment, **kwargs):
        if self.value + increment > self.vmax:
            self.value = self.vmax
        elif self.value + increment < self.vmin:
            self.value = self.vmin
        else:
            self.value += increment
        #print("update value: adress", self.address, "value", self.value)
        # Send cc message, subtract 1 to number because MIDO works from 0 - 127
        # msg = mido.Message('control_change', control=self.address, value=self.value)
        # msg=f'control_change {self.address} {self.value}'
        #print(self.address, osc_utils.scale_knob_value([self.value, self.min, self.max]))
        self.send_osc_func(self.address, osc_utils.scale_knob_value([self.value, self.min, self.max]))

class SpacerControl(OSCControl):
    address = None
    active = True

    def __init__(self):
        pass
        
    def draw(self, _, __):
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
        #print("update value: adress", self.address, "value", self.value)
        # Send cc message, subtract 1 to number because MIDO works from 0 - 127
        # msg = mido.Message('control_change', control=self.address, value=self.value)
        # msg=f'control_change {self.address} {self.value}'
        #print(self.address, osc_utils.scale_knob_value([self.value, self.min, self.max]))
        # self.send_osc_func(self.address, osc_utils.scale_knob_value([self.value, self.min, self.max]))
        
        for param in self.params:
            address, min, max = param
            # TODO may need to revisit how min/max is set
            self.send_osc_func(address, osc_utils.scale_knob_value([self.value, min, max]))



class OSCControlGroup(OSCControl):
    name = "Control Group"
    controls = []

    def __init__(self, label, config, get_color_func=None, send_osc_func=None):
        self.id = id
        self.label = label
        self.controls = config.get('controls', [])
        self.get_color_func = get_color_func
        self.send_osc_func = send_osc_func
        self.size = self.get_group_depth(config)
        
    def get_group_depth(self, arr, level=0):
        for item in arr:
            if item['controls']:
                return self.get_group_depth(item['controls'], level + 1)
            else:
                return level

    def update_value(self, increment, **kwargs): 
        pass
        # if self.value + increment > self.vmax:
        #     self.value = self.vmax
        # elif self.value + increment < self.vmin:
        #     self.value = self.vmin
        # else:
        #     self.value += increment
        # #print("update value: adress", self.address, "value", self.value)
        # # Send cc message, subtract 1 to number because MIDO works from 0 - 127
        # # msg = mido.Message('control_change', control=self.address, value=self.value)
        # # msg=f'control_change {self.address} {self.value}'
        # #print(self.address, osc_utils.scale_knob_value([self.value, self.min, self.max]))
        # # self.send_osc_func(self.address, osc_utils.scale_knob_value([self.value, self.min, self.max]))
        
        # for param in self.params:
        #     address, min, max = param
        #     # TODO may need to revisit how min/max is set,
        #     self.send_osc_func(address, osc_utils.scale_knob_value([self.value, min, max]))
        
    