from osc_controls import (
    OSCControl,
    OSCControlMacro,
    ControlSpacer,
    OSCControlSwitch,
    OSCControlMenu,
    OSCGroup,
)
import push2_python


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
        # print(self.controls)
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
        # Uncomment for debugging
        # self.dispatcher.map('*', print)
        client = self.osc.get("client", None)
        init = config.get("init", [])
        get_color = kwargs.get("get_color")
        control_definitions = config.get("controls", [])

        if client and len(init) > 0:
            for cmd in init:
                client.send_message(cmd["address"], cmd["value"])

        # Configure controls
        if len(control_definitions) > 0:
            for control_def in control_definitions:
                match control_def["$type"]:
                    case "control-spacer":
                        self.controls.append(ControlSpacer())
                    case "control-macro":
                        self.controls.append(
                            OSCControlMacro(control_def, get_color, client.send_message)
                        )
                        for param in control_def["params"]:
                            self.dispatcher.map(param.address, control.set_state)
                    case "control-range":
                        control = OSCControl(
                            control_def, get_color, client.send_message
                        )
                        self.dispatcher.map(control_def["address"], control.set_state)
                        self.controls.append(control)
                    case "control-switch":
                        try:
                            control = OSCControlSwitch(
                                control_def,
                                get_color,
                                client.send_message,
                            )

                            self.controls.append(control)
                        except:
                            print(control_def)

                    case "control-menu":
                        control = OSCControlMenu(
                            control_def, get_color, client.send_message
                        )
                        self.controls.append(control)
                    case _:
                        Exception(
                            f"Invalid parameter: {control_def}; did you forget $type?"
                        )

    def draw(self, ctx):
        visible_controls = self.pages[self.page]

        offset = 0
        for control in visible_controls:
            if offset + control.size <= 8:
                control.draw(ctx, offset)
                offset += 1

    def get_next_prev_pages(self):
        show_prev = False
        if self.page > 0:
            show_prev = True

        show_next = False
        if (self.page + 1) * 8 < len(self.controls):  # TODO FIX
            show_next = True

        return show_prev, show_next

    def set_page(self, page):
        self.page = page

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
