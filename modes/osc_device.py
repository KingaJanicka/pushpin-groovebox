from osc_controls import (
    OSCControl,
    OSCControlMacro,
    ControlSpacer,
    OSCSpacerAddress,
    OSCControlSwitch,
    OSCControlMenu,
    OSCGroup,
)
import asyncio
import push2_python
import logging
from definitions import PyshaMode
from ratelimit import limits

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
        self, config, osc={"client": {}, "server": {}, "dispatcher": {}}, engine=None, **kwargs
    ):
        self.app = kwargs["app"]
        self.engine = engine
        self.label = ""
        self.definition = {}
        self.controls = []
        self.page = 0
        self.slot = None
        self.definition = config
        self.modmatrix = config.get("modmatrix", True)
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
                    # print(f'ControlSwitch address: {control.address}, label: {control.label}')
                    
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
        # for control in self.get_visible_controls():
        #     if hasattr(control, "select"):
        #         control.select()

    def select_sync(self):
        for cmd in self.init:
            self.send_message(cmd["address"], float(cmd["value"]))

    async def select(self):

        instrument_shortname = await self.app.osc_mode.get_current_instrument_short_name_helper()
        instrument = self.app.instruments[instrument_shortname]

        await asyncio.sleep(0.1)
        for cmd in self.init:
            self.send_message(cmd["address"], float(cmd["value"]))
            # instrument.set_slot_state(cmd["address"], float(cmd["value"]))
            await asyncio.sleep(0.1)
    


    def send_message(self, *args):
        self.log_out.debug(args)
        return self.osc["client"].send_message(*args)

    async def query(self):
        for control in self.get_visible_controls():
            await control.query()

    async def query_all(self):
        print("device q all")
        for control in self.controls:
            await control.query()

    async def draw(self, ctx):
        visible_controls = await self.get_visible_controls()
        instrument_name = await self.app.metro_sequencer_mode.get_current_instrument_short_name_helper()
        
        seq = self.app.metro_sequencer_mode.instrument_sequencers[instrument_name]
        draw_lock = False
        step = None
        state = None
        if len(self.app.steps_held) != 0:
            draw_lock = True
            step = self.app.steps_held[0]

        
        all_controls = self.pages
        offset = 0
        
        # TODO: Those are broken, subpage does not draw correctly
        other_page = (self.page + 1) % 2
        for control in all_controls[self.page]:
            if offset + 1 <= 8:
                
                # Draw the lock but only if the lock value is not None and pad is pressed
                if step != None and await seq.get_lock_state(step, offset + self.page * 8) != None:
                    lock_value = await seq.get_lock_state(step, offset + self.page * 8)
                    await control.draw(ctx, offset, draw_lock=draw_lock, lock_value=lock_value)
                else:
                    await control.draw(ctx, offset)
                offset += 1
        offset = 0
        try:
            for control in all_controls[other_page]:
                if offset + 1 <= 8:
                
                    # Draw the lock but only if the lock value is not None and pad is pressed
                    if step != None and await seq.get_lock_state(step, offset+ other_page*8) != None:
                        lock_value = await seq.get_lock_state(step, offset+other_page*8)
                        await control.draw_submenu(ctx, offset, draw_lock=draw_lock, lock_value=lock_value)
                    else:
                        await control.draw_submenu(ctx, offset)
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
        try:
            all_controls = self.pages[0] + self.pages[1]
        except:
            all_controls = self.pages[0]
        return all_controls


    async def on_encoder_rotated(self, encoder_name, increment):
        try:
            #This if statement is for setting post-synth volume levels
            if encoder_name == push2_python.constants.ENCODER_SWING_ENCODER:
                instrument = await self.app.osc_mode.get_current_instrument()
                all_volumes = self.app.volumes
                instrument_idx = instrument.osc_in_port % 10
                track_L_volume = all_volumes[instrument_idx * 2]
                track_R_volume = all_volumes[instrument_idx * 2 +1]
                #This specific wording of elif is needed
                # to ensure we can reach max/min values
                if track_L_volume + increment*0.01 <= 0:
                    track_L_volume = 0
                    track_R_volume = 0
                elif track_L_volume + increment*0.01 >=1:
                    track_L_volume = 1
                    track_R_volume = 1
                else:
                    track_L_volume = track_L_volume + increment*0.01
                    track_R_volume = track_R_volume + increment*0.01
                all_volumes[instrument_idx*2] = track_L_volume
                all_volumes[instrument_idx*2 +1] = track_R_volume
                self.app.volumes = all_volumes
                await self.app.set_main_volumes()
            else: 
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
                if self.app.sequencer_mode.disable_controls == False and self.app.metro_sequencer_mode.disable_controls == False:
                    visible_controls = self.get_visible_controls()
                    control = visible_controls[encoder_idx]
                    control.update_value(increment)
                    
                    # Update state with current control value
                    # instrument_shortname = self.app.osc_mode.get_current_instrument_short_name_helper()
                    # state = self.app.osc_mode.state 
                    # if len(state) == 0:
                        # self.app.osc_mode.load_state()
                    # state[instrument_shortname][self.slot][encoder_idx] = control.value


        except ValueError:
            pass  # Encoder not in list

        