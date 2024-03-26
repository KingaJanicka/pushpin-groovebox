from osc_controls import (
    OSCControl,
    OSCControlMacro,
    ControlSpacer,
    OSCControlSwitch,
    OSCControlMenu,
    OSCGroup,
)

import push2_python
import logging

logger = logging.getLogger("osc_device")
# logger.setLevel(level=logging.DEBUG)
log_in = logger.getChild("in")
log_out = logger.getChild("out")
log = logger.getChild("DEBUGGER")

# logging.basicConfig(level=logging.DEBUG)
# logging.getLogger().setLevel(level=logging.DEBUG)


class OSCDevice(object):
    @property
    def size(self):
        i = 0
        for control in self.controls:
            i += control.size

        return i

    @property
    def pages(self):
        pages = [[]]
        idx = 0
        for control in self.controls:
            current_page = pages[idx]

            # If control won't fit
            if len(current_page) + control.size > 8:
                # Fill remaining page with spacers
                for x in range(8 - len(current_page)):
                    current_page.append(ControlSpacer())

                # Create a new page and make it current
                pages.append([])
                idx += 1
                current_page = pages[idx]

            current_page.append(control)
            if isinstance(control, OSCControlSwitch):
                active_group: OSCGroup = control.get_active_group()
                for c in active_group.controls:
                    current_page.append(c)
        return pages

    def __init__(
        self, config, osc={"client": {}, "server": {}, "dispatcher": {}}, **kwargs
    ):
        self.label = ""
        self.definition = {}
        self.controls = []
        self.page = 0
        self.slot = None
        self.definition = config
        self.osc = osc
        self.label = config.get("name", "Device")
        self.dispatcher = osc.get("dispatcher", None)
        self.slot = config.get("slot", None)
        self.dispatcher.map("*", lambda *message: log_in.debug(message))
        self.init = config.get("init", [])
        get_color = kwargs.get("get_color")
        control_definitions = config.get("controls", [])

        if self.osc["client"] and len(self.init) > 0:
            for cmd in self.init:
                self.send_message(cmd["address"], float(cmd["value"]))

        # Configure controls
        if len(control_definitions) > 0:
            for control_def in control_definitions:
                match control_def["$type"]:
                    case "control-spacer":
                        self.controls.append(ControlSpacer())
                    case "control-macro":
                        self.controls.append(
                            OSCControlMacro(control_def, get_color, self.send_message)
                        )
                        for param in control_def["params"]:
                            self.dispatcher.map(param.address, control.set_state)
                    case "control-range":
                        control = OSCControl(control_def, get_color, self.send_message)
                        self.dispatcher.map(control_def["address"], control.set_state)
                        self.controls.append(control)
                    case "control-switch":
                        try:
                            control = OSCControlSwitch(
                                control_def,
                                get_color,
                                self.send_message,
                            )
                            for group in control.groups:
                                for child in group.controls:
                                    if isinstance(child, OSCControl):
                                        self.dispatcher.map(
                                            child.address,
                                            lambda *x: control.set_state(*x)
                                            and child.set_state(*x),
                                        )
                                    elif isinstance(child, OSCControlMacro):
                                        for param in child.params:
                                            self.dispatcher.map(
                                                param["address"],
                                                lambda *x: control.set_state(*x)
                                                and child.set_state(*x),
                                            )
                                    elif isinstance(child, OSCControlMenu):
                                        if child.message is not None:
                                            self.dispatcher.map(
                                                child.message["address"],
                                                lambda *x: control.set_state(*x)
                                                and child.set_state(*x),
                                            )
                                        for item in child.items:
                                            if item.message is not None:
                                                self.dispatcher.map(
                                                    item.message["address"],
                                                    lambda *x: control.set_state(*x)
                                                    and child.set_state(*x),
                                                )

                            self.controls.append(control)
                        except Exception as e:
                            print("EXCEPT", e)
                            # print(control_def)

                    case "control-menu":
                        control = OSCControlMenu(
                            control_def, get_color, self.send_message
                        )
                        if control.message:
                            self.dispatcher.map(
                                control.message["address"], control.set_state
                            )
                        for item in control.items:
                            if item.message and item.message["address"]:
                                self.dispatcher.map(
                                    item.message["address"], control.set_state
                                )
                            else:
                                raise Exception(
                                    f"{item} has no message.address property"
                                )
                        self.controls.append(control)
                    case _:
                        Exception(
                            f"Invalid parameter: {control_def}; did you forget $type?"
                        )

    def send_message(self, *args):
        log_out.debug(args)
        return self.osc["client"].send_message(*args)

    def draw(self, ctx):
        visible_controls = self.get_visible_controls()

        offset = 0
        for control in visible_controls:
            if offset + 1 <= 8:
                control.draw(ctx, offset)
                offset += 1

    def get_next_prev_pages(self):
        show_prev = False
        if self.page > 0:
            show_prev = True

        show_next = False
        if (self.page + 1) < len(self.pages):
            show_next = True

        return show_prev, show_next

    def set_page(self, page):
        self.page = page
        # print("PAGE: ", self.page)
        # print(*self.pages[self.page], sep="\n")

    def get_visible_controls(self):
        return self.pages[self.page]

    def on_encoder_rotated(self, encoder_name, increment):
        try:
            encoder_idx = [
                push2_python.constants.ENCODER_TRACK1_ENCODER,
                push2_python.constants.ENCODER_TRACK2_ENCODER,
                push2_python.constants.ENCODER_TRACK3_ENCODER,
                push2_python.constants.ENCODER_TRACK4_ENCODER,
                push2_python.constants.ENCODER_TRACK5_ENCODER,
                push2_python.constants.ENCODER_TRACK6_ENCODER,
                push2_python.constants.ENCODER_TRACK7_ENCODER,
                push2_python.constants.ENCODER_TRACK8_ENCODER,
            ].index(encoder_name)

            visible_controls = self.get_visible_controls()
            control = visible_controls[encoder_idx]
            control.update_value(increment)
        except ValueError:
            pass  # Encoder not in list
