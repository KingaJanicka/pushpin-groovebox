import definitions
import osc_utils


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
        self.active = False
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
