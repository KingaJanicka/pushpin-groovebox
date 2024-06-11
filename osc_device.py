from osc_controls import (
    OSCControl,
    OSCControlMacro,
    ControlSpacer,
    OSCSpacerAddress,
    OSCControlSwitch,
    OSCControlMenu,
    OSCGroup,
)

import push2_python
import logging
from definitions import PyshaMode

logger = logging.getLogger("osc_device")
# logger.setLevel(level=logging.DEBUG)


class OSCDevice(PyshaMode):
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
        self.log_in = logger.getChild(f"in-{kwargs['osc_in_port']}")
        self.log_out = logger.getChild(f"out-{kwargs['osc_out_port']}")
        # IMPORTANT: if using query_all_params do not uncomment the following:
        # self.dispatcher.map("*", lambda *message: self.log_in.debug(message))
        self.init = config.get("init", [])
        get_color = kwargs.get("get_color")
        control_definitions = config.get("controls", [])

        # Configure controls
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
                    self.dispatcher.map(control.address, control.set_state)
                    self.controls.append(control)
                case "control-spacer-address":
                    control = OSCSpacerAddress(control_def, self.send_message)
                    self.dispatcher.map(control.address, control.set_state)
                    self.controls.append(control)
                case "control-switch":
                    control = OSCControlSwitch(
                        control_def, get_color, self.send_message, self.dispatcher
                    )
                    if control.address:
                        self.dispatcher.map(control.address, control.set_state)

                    self.controls.append(control)

                case "control-menu":
                    control = OSCControlMenu(control_def, get_color, self.send_message)
                    if control.address:
                        self.dispatcher.map(control.address, control.set_state)

                    # for item in control.items:
                    #     if item.address:
                    #         self.dispatcher.map(item.address, control.set_state)
                    #     else:
                    #         raise Exception(f"{item} has no message.address property")

                    self.controls.append(control)
                case _:
                    Exception(
                        f"Invalid parameter: {control_def}; did you forget $type?"
                    )

        # Call /q endpoints for each control currently displayed
        # self.query_visible_controls()
        # mapped_addresses = self.dispatcher
        # Select if it has a select attribute
        for control in self.get_visible_controls():
            if hasattr(control, "select"):
                control.select()

    def select(self):
        # self.query_visible_controls()
        print("device init______________")
        for cmd in self.init:
            self.send_message(cmd["address"], float(cmd["value"]))

    def send_message(self, *args):
        self.log_out.debug(args)
        return self.osc["client"].send_message(*args)

    def query(self):
        for control in self.get_visible_controls():
            control.query()

    def query_all(self):
        for control in self.controls:
            control.query()

    def draw(self, ctx):
        visible_controls = self.get_visible_controls()
        all_controls = self.pages
        offset = 0
        for control in all_controls[self.page]:
            if offset + 1 <= 8:
                control.draw(ctx, offset)
                offset += 1
        offset = 0
        other_page = (self.page + 1) % 2
        try:
            for control in all_controls[other_page]:
                if offset + 1 <= 8:
                    control.draw_submenu(ctx, offset)
                    offset += 1
        except:
            pass

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
        # self.query_visible_controls()
        # print("PAGE: ", self.page)
        # print(*self.pages[self.page], sep="\n")

    def query_visible_controls(self):
        visible_controls = self.get_visible_controls()
        for control in visible_controls:
            if hasattr(control, "address") and control.address is not None:
                self.send_message("/q" + control.address, None)

    def query_all_controls(self):
        all_controls = self.get_all_controls()
        for control in all_controls:
            if hasattr(control, "address") and control.address is not None:
                self.send_message("/q" + control.address, None)

    def get_visible_controls(self):
        return self.pages[self.page]

    def get_all_controls(self):
        all_controls = self.pages[0] + self.pages[1]
        return all_controls

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
