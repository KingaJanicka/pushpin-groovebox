from osc_controls import OSCControl, OSCMacroControl, SpacerControl, OSCControlGroup
import push2_python


class OSCDevice(object):
    id = None
    label = ""
    definition = {}
    controls = []
    client = None
    page = 0
    osc = {"client": {}, "server": {}, "dispatcher": {}}

    def __init__(self, config, osc, **kwargs):
        self.definition = config
        self.osc = osc
        self.label = config.get("device_name", "Device")
        self.dispatcher = osc.get("dispatcher", None)
        # Uncomment for debugging
        # self.dispatcher.map('*', print)
        client = osc.get("client", None)
        init = config.get("init", [])
        get_color = kwargs.get("get_color")
        control_definitions = config.get("osc", {}).get("controls", [])

        if client and len(init) > 0:
            for cmd in init:
                reversed = list(cmd)
                reversed.reverse()
                val, address, *rest = reversed
                client.send_message(address, val)

        # Configure controls
        if len(control_definitions) > 0:
            for control_def in control_definitions:
                if isinstance(control_def, list):
                    if len(control_def) == 0:  # spacer
                        control = SpacerControl()
                        self.controls.append(control)

                    elif len(control_def) == 2:  # macro
                        item_label, params = control_def
                        control = OSCMacroControl(
                            item_label,
                            params,
                            get_color,
                            client.send_message if client else None,
                        )

                        for param in params:
                            address, min, max = param
                            self.dispatcher.map(address, control.set_state)

                        self.controls.append(control)

                    else:  # individual (normal) control
                        item_label, address, min, max = control_def
                        control = OSCControl(
                            item_label,
                            address,
                            min,
                            max,
                            get_color,
                            client.send_message if client else None,
                        )
                        self.dispatcher.map(address, control.set_state)
                        self.controls.append(control)

                elif isinstance(control_def, dict):  # control group
                    item_label = control_def.get("name", "Control")
                    control = OSCControlGroup(
                        control_def, get_color, client.send_message
                    )
                    # dispatcher?
                    self.controls.append(control)
                else:
                    Exception("Invalid parameter: ", control_def)

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
            if (
                i + control.size > self.page * 8
                and i + control.size <= self.page * 8 + 8
            ):
                visible_controls.append(control)
                if control.size > 1:  # append group controls
                    child = control.get_active_group()
                    visible_controls.append(child)

                    while hasattr(child, "visible"):
                        child = child.visible
                        visible_controls.append(child)
            elif i + control.size > self.page * 8 + 8:
                diff = (self.page * 8 + 8) - i
                for x in range(diff):
                    visible_controls.append(SpacerControl())

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
