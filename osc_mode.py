import definitions
import push2_python
import json
import os
import asyncio

from pythonosc.udp_client import SimpleUDPClient
from pythonosc.osc_server import AsyncIOOSCUDPServer
from pythonosc.dispatcher import Dispatcher

from definitions import PyshaMode, OFF_BTN_COLOR
from display_utils import show_text
from glob import glob
from pathlib import Path
from osc_device import OSCDevice

class OSCMode(PyshaMode):
    upper_row_button_names = [
        push2_python.constants.BUTTON_UPPER_ROW_1,
        push2_python.constants.BUTTON_UPPER_ROW_2,
        push2_python.constants.BUTTON_UPPER_ROW_3,
        push2_python.constants.BUTTON_UPPER_ROW_4,
        push2_python.constants.BUTTON_UPPER_ROW_5,
        push2_python.constants.BUTTON_UPPER_ROW_6,
        push2_python.constants.BUTTON_UPPER_ROW_7,
        push2_python.constants.BUTTON_UPPER_ROW_8
    ]
    instrument_devices = {}
    visible_controls = [] # TODO FIX move to OSCDevice?
    current_device_and_page = {}
    transports = []
    
    def initialize(self, settings=None):
        device_names = [Path(device_file).stem for device_file in glob('./device_definitions/*.json')]
        device_definitions = {}
        
        for device_name in device_names:
            try:
                device_definitions[device_name] = json.load(open(os.path.join(definitions.DEVICE_DEFINITION_FOLDER, '{}.json'.format(device_name))))
            except FileNotFoundError:
                device_definitions[device_name] = {}

        for instrument_short_name in self.get_all_distinct_instrument_short_names_helper():
            try:
                inst = json.load(open(os.path.join(definitions.INSTRUMENT_DEFINITION_FOLDER, '{}.json'.format(instrument_short_name))))
            except FileNotFoundError:
                inst = {}

            osc_in_port = inst.get('osc_in_port', None)
            osc_out_port = inst.get('osc_out_port', None)
            client = None
            server = None
            dispatcher = Dispatcher()

            if (osc_in_port): 
                client = SimpleUDPClient("127.0.0.1", osc_in_port)

            if (osc_out_port):
                loop = asyncio.get_event_loop()
                server = AsyncIOOSCUDPServer(("127.0.0.1", osc_out_port), dispatcher, loop)
                loop.run_until_complete(self.init_server(server))
                
            osc = {"client": client, "server": server, "dispatcher": dispatcher}
            self.app.osc_clients[instrument_short_name] = osc

            # Create OSC mappings for instruments with definitions
            self.instrument_devices[instrument_short_name] = []

            for device_name in device_definitions:
                device = OSCDevice(device_name, device_definitions[device_name], osc, get_color=self.get_current_track_color_helper)
                self.instrument_devices[instrument_short_name].append(device)
                
            # call the all_params endpoint to populate device controls
            if (client):
                print(f'Populating {instrument_short_name}')
                # client.send_message('/q/all_params', None) 

            print('Loaded {0} devices for instrument {1}'.format(len(self.instrument_devices[instrument_short_name]), instrument_short_name))

        # Fill in current page and device variables
        for instrument_short_name in self.instrument_devices:
            self.current_device_and_page[instrument_short_name] = (device, 0)

    """
    Initialise OSC servers and add to transport array so they can be gracefully closed
    """    
    async def init_server(self, server):
        transport, protocol = await server.create_serve_endpoint()  # Create datagram endpoint and start serving
        self.transports.append(transport)
         
        
    """
    Close transports on ctrl+c
    """
    def close_transports(self):
        for transport in self.transports:
            transport.close()

    def get_all_distinct_instrument_short_names_helper(self):
        return self.app.track_selection_mode.get_all_distinct_instrument_short_names()

    def get_current_track_color_helper(self):
        return self.app.track_selection_mode.get_current_track_color()

    def get_current_track_instrument_short_name_helper(self):
        return self.app.track_selection_mode.get_current_track_instrument_short_name()

    def get_current_instrument_devices(self):
        return self.instrument_devices.get(self.get_current_track_instrument_short_name_helper(), {})

    def get_current_instrument_device_controls(self):
        return self.get_current_instrument_devices().controls

    def get_current_instrument_device_labels(self):
        return [device.label for device in self.get_current_instrument_devices_controls()]
    
    def get_current_instrument_devices_control_ids(self):
        return [control.id for control in self.get_current_instrument_devices_controls()]

    def get_current_instrument_devices_control_labels(self):
        return [control.label for control in self.get_current_instrument_devices_controls()]
    
    def get_current_instrument_device(self):
        device, __ = self.get_current_instrument_device_and_page()
        return device

    def get_current_instrument_device_and_page(self):
        return self.current_device_and_page[self.get_current_track_instrument_short_name_helper()]

    def get_controls_for_current_device(self):
        device, _ = self.get_current_instrument_device_and_page()
        return device.controls

    # TODO make page indexing consistent between instruments
    def get_controls_for_current_device_and_page(self):
        all_device_controls = self.get_controls_for_current_device()
        # print(all_device_controls)
        _, page = self.get_current_instrument_device_and_page()
        try:
            # TODO FIX
            return all_device_controls[page * 8:(page+1) * 8]
        except IndexError:
            return []

    def update_current_device_page(self, new_device=None, new_page=None):
        current_device, current_page = self.get_current_instrument_device_and_page()
        result = [current_device, current_page]
        if new_device is not None:
            result[0] = new_device
        if new_page is not None:
            result[1] = new_page
        self.current_device_and_page[self.get_current_track_instrument_short_name_helper()] = result
        self.visible_controls = self.get_controls_for_current_device_and_page()
        self.app.buttons_need_update = True

    def get_next_prev_pages_for_device(self):
        all_device_controls = self.get_controls_for_current_device()
        _, page = self.get_current_instrument_device_and_page()
        show_prev = False
        if page > 0:
            show_prev = True
        show_next = False
        if (page + 1) * 8 < len(all_device_controls): #TODO FIX
            show_next = True
        return show_prev, show_next

    def new_track_selected(self):
        self.visible_controls = self.get_controls_for_current_device_and_page()

    def activate(self):
        self.update_buttons()

    def deactivate(self):
        for button_name in self.upper_row_button_names + [push2_python.constants.BUTTON_PAGE_LEFT, push2_python.constants.BUTTON_PAGE_RIGHT]:
            self.push.buttons.set_button_color(button_name, definitions.BLACK)

    def update_buttons(self):
        for count, name in enumerate(self.upper_row_button_names):
            if count < len(self.get_controls_for_current_device()):
                self.push.buttons.set_button_color(name, definitions.WHITE)
            else:
                self.push.buttons.set_button_color(name, definitions.BLACK)

        show_prev, show_next = self.get_next_prev_pages_for_device()
        if show_prev:
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_PAGE_LEFT, definitions.WHITE)
        else:
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_PAGE_LEFT, definitions.BLACK)
        if show_next:
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_PAGE_RIGHT, definitions.WHITE)
        else:
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_PAGE_RIGHT, definitions.BLACK)

    def update_display(self, ctx, w, h):
        """
        If settings mode is active, don't draw the upper parts of the screen
        because settings page will "cover them"
        """
        if not self.app.is_mode_active(self.app.settings_mode):
            # Draw OSCDevice names
            devices = self.get_current_instrument_devices()[0:8]
            if devices:
                height = 20
                for i, device in enumerate(devices):
                    show_text(ctx, i, 0, device.label, background_color=definitions.RED)
                    
                    is_selected = False
                    selected_device, _ = self.get_current_instrument_device_and_page()
                    if selected_device == device.id:
                        is_selected = True

                    current_track_color = self.get_current_track_color_helper()
                    if is_selected:
                        background_color = current_track_color
                        font_color = definitions.BLACK
                    else:
                        background_color = definitions.BLACK
                        font_color = current_track_color
                    show_text(ctx, i, 0, device.label, height=height,
                            font_color=font_color, background_color=background_color)

            # Draw OSCControls
            device = self.get_current_instrument_device()
            if device:
                device.draw(ctx)
 
    
    def on_button_pressed(self, button_name):
        selected_device, _ = self.get_current_instrument_device_and_page()
        show_prev, show_next = self.get_next_prev_pages_for_device()
        _, current_page = self.get_current_instrument_device_and_page()
    
        if  button_name in self.upper_row_button_names:
            current_track_devices = self.get_current_track_device_ids()
            idx = self.upper_row_button_names.index(button_name)
            if idx < len(current_track_devices):
                new_device = current_track_devices[idx]
                new_page = 0 if new_device != selected_device else current_page -1 if show_prev else current_page +1 if show_next else 0
                self.update_current_device_page(new_device=new_device, new_page=new_page)
            return True

        elif button_name in [push2_python.constants.BUTTON_PAGE_LEFT, push2_python.constants.BUTTON_PAGE_RIGHT]:
            if button_name == push2_python.constants.BUTTON_PAGE_LEFT and show_prev:
                self.update_current_device_page(new_page=current_page - 1)
            elif button_name == push2_python.constants.BUTTON_PAGE_RIGHT and show_next:
                self.update_current_device_page(new_page=current_page + 1)
            return True

# TODO pass update to device, not control
    def on_encoder_rotated(self, encoder_name, increment):
        try:
            encoder_num = [
                push2_python.constants.ENCODER_TRACK1_ENCODER,
                push2_python.constants.ENCODER_TRACK2_ENCODER,
                push2_python.constants.ENCODER_TRACK3_ENCODER,
                push2_python.constants.ENCODER_TRACK4_ENCODER,
                push2_python.constants.ENCODER_TRACK5_ENCODER,
                push2_python.constants.ENCODER_TRACK6_ENCODER,
                push2_python.constants.ENCODER_TRACK7_ENCODER,
                push2_python.constants.ENCODER_TRACK8_ENCODER,
            ].index(encoder_name)
            if self.visible_controls:
                self.visible_controls[encoder_num].update_value(increment)
        except ValueError: 
            pass  # Encoder not in list 
        return True  # Always return True because encoder should not be used in any other mode if this is first active
