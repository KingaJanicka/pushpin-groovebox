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
from osc_controls import OSCControl, OSCMacroControl, SpacerControl

class OSCMode(PyshaMode):

    osc_address_button_names = [
        push2_python.constants.BUTTON_UPPER_ROW_1,
        push2_python.constants.BUTTON_UPPER_ROW_2,
        push2_python.constants.BUTTON_UPPER_ROW_3,
        push2_python.constants.BUTTON_UPPER_ROW_4,
        push2_python.constants.BUTTON_UPPER_ROW_5,
        push2_python.constants.BUTTON_UPPER_ROW_6,
        push2_python.constants.BUTTON_UPPER_ROW_7,
        push2_python.constants.BUTTON_UPPER_ROW_8
    ]
    instrument_osc_addresses = {}
    active_osc_addresses = []
    current_selected_section_and_page = {}
    osc_port = None
    transports = []
    devices = {}
    
    def initialize(self, settings=None):
        device_names = [Path(device_file).stem for device_file in glob('./device_definitions/*.json')]

        for device_name in device_names:
            # print(device_name)
            try:
                self.devices[device_name] = json.load(open(os.path.join(definitions.DEVICE_DEFINITION_FOLDER, '{}.json'.format(device_name))))
            except FileNotFoundError:
                self.devices[device_name] = {}
        print("p")
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
                loop.run_until_complete(self.init_server(server, client))

            self.app.osc_clients[instrument_short_name] = {"client": client, "server": server, "dispatcher": dispatcher}

            def param_handler(address, *args):
                print(f"{instrument_short_name} {address}: {args}")

            # uncomment for debug
            # dispatcher.map("/param/*", param_handler)
            
            # Create OSC mappings for instruments with definitions
            self.instrument_osc_addresses[instrument_short_name] = []

            for device_name in self.devices:
                device = self.devices[device_name]
                osc = device.get('osc', None)
                init = device.get('init', [])
                if client and len(init) > 0:
                    for cmd in init:
                        print(cmd)
                        reversed = list(cmd)
                        reversed.reverse()
                        val, address, *rest = reversed
                        client.send_message(address, val)
                    
                if osc is not None:
                    section_label = osc.get('section', 'Device')                    
                    for control_def in osc['controls']:
                        item_label = ''
                        if isinstance(control_def, list):
                            if len(control_def) == 0: # spacer
                                control = SpacerControl(section_label)
                                self.instrument_osc_addresses[instrument_short_name].append(control)
                            elif len(control_def) == 2: # macro
                                item_label, params = control_def
                                control = OSCMacroControl(item_label, params, section_label, self.get_current_track_color_helper, self.app.send_osc)

                                def handle_control_response(self, *args):
                                    value = args
                                    control.update_value(value)
                                
                                for param in params:
                                    address, min, max = param
                                    dispatcher.map(address, handle_control_response)
                                
                                self.instrument_osc_addresses[instrument_short_name].append(control)   
                                
                            else: # individual (normal) control
                                item_label, address, min, max = control_def
                                control = OSCControl(address, item_label, min, max, section_label, self.get_current_track_color_helper, self.app.send_osc)
                                def handle_control_response(self, *args):
                                    value = args
                                    control.update_value(value)
                                    
                                dispatcher.map(address, handle_control_response)
                                self.instrument_osc_addresses[instrument_short_name].append(control)        
                                
                            # control = OSCControl(address, item_label, min, max, section_label, self.get_current_track_color_helper, self.app.send_osc)
                            # if osc.get('control_value_label_maps', {}).get(name, False):
                            #     control.value_labels_map = section['control_value_label_maps'][name]
                            
                            
                                
                        elif isinstance(control_def, dict):
                            # control group
                            print('page')
                        else:
                            Exception('Invalid parameter: ', control_def)
                        

                    print('Loaded {0} OSC address mappings for instrument {1}'.format(len(self.instrument_osc_addresses[instrument_short_name]), instrument_short_name))
                else:
                    # No definition file for instrument exists, or no midi CC were defined for that instrument
                    self.instrument_osc_addresses[instrument_short_name] = []
                    for i in range(0, 128):
                        section_s = (i // 16) * 16
                        section_e = section_s + 15
                        control = OSCControl(i, 'CC {0}'.format(i), 0.0, 1.0, '{0} to {1}'.format(section_s, section_e), self.get_current_track_color_helper, self.app.send_osc)
                        self.instrument_osc_addresses[instrument_short_name].append(control)
                    print('Loaded default OSC address mappings for instrument {0}'.format(instrument_short_name))
        
        # # Fill in current page and section variables
        for instrument_short_name in self.instrument_osc_addresses:
            self.current_selected_section_and_page[instrument_short_name] = (self.instrument_osc_addresses[instrument_short_name][0].section, 0)
                
    """
    Initialise OSC servers and add to transport array so they can be gracefully closed
    """
    async def init_server(self, server, client = None):
        transport, protocol = await server.create_serve_endpoint()  # Create datagram endpoint and start serving
        self.transports.append(transport)
         
        # call the all_params endpoint
        if (client):
            client.send_message('/q/all_params', None) 
         
        
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

    def get_current_track_osc_address_sections(self):
        section_names = []
        for control in self.instrument_osc_addresses.get(self.get_current_track_instrument_short_name_helper(), []):
            section_name = control.section
            if section_name not in section_names:
                section_names.append(section_name)
        return section_names

    def get_currently_selected_osc_address_section_and_page(self):
        return self.current_selected_section_and_page[self.get_current_track_instrument_short_name_helper()]

    def get_osc_address_controls_for_current_track_and_section(self):
        section, _ = self.get_currently_selected_osc_address_section_and_page()
        return [control for control in self.instrument_osc_addresses.get(self.get_current_track_instrument_short_name_helper(), []) if control.section == section]

    def get_osc_address_controls_for_current_track_section_and_page(self):
        all_section_controls = self.get_osc_address_controls_for_current_track_and_section()
        # print(all_section_controls)
        _, page = self.get_currently_selected_osc_address_section_and_page()
        try:
            return all_section_controls[page * 8:(page+1) * 8]
        except IndexError:
            return []

    def update_current_section_page(self, new_section=None, new_page=None):
        current_section, current_page = self.get_currently_selected_osc_address_section_and_page()
        result = [current_section, current_page]
        if new_section is not None:
            result[0] = new_section
        if new_page is not None:
            result[1] = new_page
        self.current_selected_section_and_page[self.get_current_track_instrument_short_name_helper()] = result
        self.active_osc_addresses = self.get_osc_address_controls_for_current_track_section_and_page()
        self.app.buttons_need_update = True

    def get_should_show_osc_address_next_prev_pages_for_section(self):
        all_section_controls = self.get_osc_address_controls_for_current_track_and_section()
        _, page = self.get_currently_selected_osc_address_section_and_page()
        show_prev = False
        if page > 0:
            show_prev = True
        show_next = False
        if (page + 1) * 8 < len(all_section_controls):
            show_next = True
        return show_prev, show_next

    def new_track_selected(self):
        self.active_osc_addresses = self.get_osc_address_controls_for_current_track_section_and_page()

    def activate(self):
        self.update_buttons()

    def deactivate(self):
        for button_name in self.osc_address_button_names + [push2_python.constants.BUTTON_PAGE_LEFT, push2_python.constants.BUTTON_PAGE_RIGHT]:
            self.push.buttons.set_button_color(button_name, definitions.BLACK)

    def update_buttons(self):

        n_osc_address_sections = len(self.get_current_track_osc_address_sections())
        for count, name in enumerate(self.osc_address_button_names):
            if count < n_osc_address_sections:
                self.push.buttons.set_button_color(name, definitions.WHITE)
            else:
                self.push.buttons.set_button_color(name, definitions.BLACK)

        show_prev, show_next = self.get_should_show_osc_address_next_prev_pages_for_section()
        if show_prev:
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_PAGE_LEFT, definitions.WHITE)
        else:
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_PAGE_LEFT, definitions.BLACK)
        if show_next:
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_PAGE_RIGHT, definitions.WHITE)
        else:
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_PAGE_RIGHT, definitions.BLACK)

    def update_display(self, ctx, w, h):

        if not self.app.is_mode_active(self.app.settings_mode):
            # If settings mode is active, don't draw the upper parts of the screen because settings page will
            # "cover them"

            # Draw MIDI CCs section names
            section_names = self.get_current_track_osc_address_sections()[0:8]
            if section_names:
                height = 20
                for i, section_name in enumerate(section_names):
                    show_text(ctx, i, 0, section_name, background_color=definitions.RED)
                    
                    is_selected = False
                    selected_section, _ = self.get_currently_selected_osc_address_section_and_page()
                    if selected_section == section_name:
                        is_selected = True

                    current_track_color = self.get_current_track_color_helper()
                    if is_selected:
                        background_color = current_track_color
                        font_color = definitions.BLACK
                    else:
                        background_color = definitions.BLACK
                        font_color = current_track_color
                    show_text(ctx, i, 0, section_name, height=height,
                            font_color=font_color, background_color=background_color)

            # Draw MIDI CC controls
            if self.active_osc_addresses:
                for i in range(0, min(len(self.active_osc_addresses), 8)):
                    try:
                        self.active_osc_addresses[i].draw(ctx, i)
                    except IndexError:
                        continue
 
    
    def on_button_pressed(self, button_name):
        selected_section, _ = self.get_currently_selected_osc_address_section_and_page()
        show_prev, show_next = self.get_should_show_osc_address_next_prev_pages_for_section()
        _, current_page = self.get_currently_selected_osc_address_section_and_page()
    
        if  button_name in self.osc_address_button_names:
            current_track_sections = self.get_current_track_osc_address_sections()
            n_sections = len(current_track_sections)
            idx = self.osc_address_button_names.index(button_name)
            if idx < n_sections:
                new_section = current_track_sections[idx]
                new_page = 0 if new_section != selected_section else current_page -1 if show_prev else current_page +1 if show_next else 0
                self.update_current_section_page(new_section=new_section, new_page=new_page)
            return True

        elif button_name in [push2_python.constants.BUTTON_PAGE_LEFT, push2_python.constants.BUTTON_PAGE_RIGHT]:
            if button_name == push2_python.constants.BUTTON_PAGE_LEFT and show_prev:
                self.update_current_section_page(new_page=current_page - 1)
            elif button_name == push2_python.constants.BUTTON_PAGE_RIGHT and show_next:
                self.update_current_section_page(new_page=current_page + 1)
            return True


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
            if self.active_osc_addresses:
                self.active_osc_addresses[encoder_num].update_value(increment)
        except ValueError: 
            pass  # Encoder not in list 
        return True  # Always return True because encoder should not be used in any other mode if this is first active
