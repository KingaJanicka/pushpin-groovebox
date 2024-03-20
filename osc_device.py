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
    def __init__(
        self, config, osc={"client": {}, "server": {}, "dispatcher": {}}, **kwargs
    ):
        self.id = None
        self.label = ""
        self.definition = {}
        self.controls = []
        self.client = None
        self.page = 0
        self.slot = None
        self.definition = config
        self.osc = osc
        self.label = config.get("name", "Device")
        self.dispatcher = osc.get("dispatcher", None)
        self.slot = config.get("slot", None)
        # Uncomment for debugging
        # self.dispatcher.map('*', print)
        client = osc.get("client", None)
        init = config.get("init", [])
        get_color = kwargs.get("get_color")
        control_definitions = config.get("osc", [])

        if client and len(init) > 0:
            for cmd in init:
                client.send_message(cmd["address"], cmd["val"])

        # Configure controls
        if len(control_definitions) > 0:
            for control_def in control_definitions:
                match control_def["$type"]:
                    case "control-spacer":
                        self.controls.append(ControlSpacer())
                    case "control-macro":
                        self.controls.append(
                            OSCControlMacro(
                                control_def,
                                get_color,
                                client.send_message if client else None,
                            )
                        )
                        for param in control_def["params"]:
                            self.dispatcher.map(param.address, control.set_state)
                    case "control-range":
                        control = OSCControl(
                            control_def,
                            get_color,
                            client.send_message if client else None,
                        )
                        self.dispatcher.map(control_def["address"], control.set_state)
                        self.controls.append(control)
                    case "control-switch":
                        control = OSCControlSwitch(
                            control_def,
                            get_color,
                            client.send_message,
                        )

                        self.controls.append(control)
                    case "control-menu":
                        control = OSCControlMenu(
                            control_def,
                            get_color,
                            client.send_message,
                        )
                        self.controls.append(control)
                    case _:
                        Exception(
                            f"Invalid parameter: {control_def}; did you forget $type?"
                        )

    def draw(self, ctx):
        active_controls = [
            control for control in filter(lambda x: x.active, self.controls)
        ][0:8]
        offset = 0
        for control in active_controls:
            control.draw(ctx, offset)
            offset += control.size

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
        visible_controls = []
        i = 0
        for control in self.controls:
            print(
                "size",
                control.size,
                "idx",
                i,
                "lower",
                self.page * 8,
                "upper",
                self.page * 8 + 8,
            )

            if (
                i + control.size > self.page * 8
                and i + control.size <= self.page * 8 + 8
            ):
                visible_controls.append(control)

                if isinstance(control, OSCControlSwitch):
                    active_group: OSCGroup = control.get_active_group()
                    for child in active_group.controls:
                        visible_controls.append(child)
            elif i + control.size > self.page * 8 + 8:
                diff = (self.page * 8 + 8) - i
                for x in range(diff):
                    visible_controls.append(ControlSpacer())

            i += control.size

        return visible_controls

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

            i = 0

            # No idea if this works (probably not)
            for control in self.controls:
                if (
                    i >= self.page * 8
                    and i < self.page * 8 + 8
                    and i % 8 == encoder_idx
                ):
                    print("updating ", control.label, " by increment ", increment)
                    control.update_value(increment)

                i += control.size
        except ValueError:
            pass  # Encoder not in list

    @property
    def size(self):
        i = 0
        for control in self.controls:
            i += control.size

        return i
