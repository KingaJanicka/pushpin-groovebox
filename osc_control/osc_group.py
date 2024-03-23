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
