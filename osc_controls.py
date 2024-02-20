import definitions
import osc_utils
import math
import push2_python
from display_utils import show_text

class OSCControl(object):
    color = definitions.GRAY_LIGHT
    color_rgb = None
    name = 'Unknown'
    section = 'unknown'
    address = "/default"
    min = 0.0
    max = 1.0
    value = 64
    vmin = 0
    vmax = 127
    get_color_func = None
    value_labels_map = {}

    def __init__(self, address, name, min, max, section_name, get_color_func, send_osc_func=None):
        self.address = address
        self.name = name
        self.section = section_name
        self.get_color_func = get_color_func
        self.send_osc_func = send_osc_func
        self.min = min
        self.max = max

    def draw(self, ctx, x_part):
        margin_top = 25
        
        # Param name
        name_height = 20
        show_text(ctx, x_part, margin_top, self.name, height=name_height, font_color=definitions.WHITE)

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
    
    def update_value(self, increment, *kwargs): 
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
       
class SpacerControl(object):
    color = definitions.GRAY_LIGHT
    color_rgb = None
    name = 'Spacer'
    section = 'Unknown'
    address = None
    get_color_func = None
    value_labels_map = {}
    
    def __init__(self, section_name):
        self.section = section_name
        
    def draw(self, _, __):
        return
    
    def update_value(self, increment, *kwargs):
        return

class OSCMacroControl(OSCControl):
    def __init__(self, name, params, section_name, get_color_func, send_osc_func=None):
        self.name = name
        self.params = params
        self.section = section_name
        self.get_color_func = get_color_func
        self.send_osc_func = send_osc_func

    def update_value(self, increment, *kwargs): 
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
    value = None
    type = None
    max_depth = 0

    def __init__(self, config, section_name, get_color_func, send_osc_func=None):
        self.name = config['name']
        self.controls = config['controls']
        
        temp = self['controls'].copy()
        self.max_depth = 0

        if temp:
            while True:
                self.max_depth += 1
                has_children = len(temp) > 0 and hasattr(temp[0], 'controls')
                
                if has_children: temp = temp[0]['controls']
                else:
                    if len(temp) > 0:
                        self.type = 'OscRotaryControl' if len(temp[0]) is 4 else 'OscParameterControl' if len(temp[0]) else None
                    break
                

        
        self.section = section_name
        self.get_color_func = get_color_func
        self.send_osc_func = send_osc_func
        
    def update_value(self, increment, *kwargs): 
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
        #     # TODO may need to revisit how min/max is set
        #     self.send_osc_func(address, osc_utils.scale_knob_value([self.value, min, max]))
