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
        pages = [[]]
        idx = 0
        min_idx = self.page * 8
        max_idx = self.page * 8 + 8

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

        return pages[self.page]
        # for idx, control in enumerate(self.controls):
        #     if control.size > 1:
        #         if int((idx + control.size) / 8) > int(idx / 8):
        #             for x in range(idx % 8):
        #                 flat_controls.append(ControlSpacer())

        #     flat_controls.append(control)

        #     if isinstance(control, OSCControlSwitch):
        #         active_group: OSCGroup = control.get_active_group()
        #         max_size = control.size
        #         spacers = max_size - active_group.size
        #         for c in active_group.controls:
        #             flat_controls.append(c)
        #         for x in range(spacers):
        #             flat_controls.append(ControlSpacer())

        return flat_controls[min_idx:max_idx]
        # idx += control.size
        # # print(
        # #     "idx",
        # #     idx,
        # #     "size",
        # #     control.size,
        # #     "min",
        # #     min_idx,
        # #     "max",
        # #     max_idx,
        # #     "if",
        # #     idx > min_idx and idx <= max_idx,
        # #     "else",
        # #     idx > max_idx and (idx - control.size) < max_idx,
        # # )

        # if idx > min_idx and idx <= max_idx:
        #     visible_controls.append(control)

        #     if isinstance(control, OSCControlSwitch):
        #         active_group: OSCGroup = control.get_active_group()
        #         for child in active_group.controls:
        #             visible_controls.append(child)

        #         # If control is being added to a new group
        #         # due to constraints increment again
        #         if idx - control.size < min_idx:
        #             idx += control.size - 1

        # elif idx > max_idx and (idx - control.size) < max_idx:
        #     diff = max_idx - (idx - control.size)

        #     for x in range(diff):
        #         visible_controls.append(ControlSpacer())

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
