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
import logging

logger = logging.getLogger("osc_device")


class OSCMode(PyshaMode):
    upper_row_button_names = [
        push2_python.constants.BUTTON_UPPER_ROW_1,
        push2_python.constants.BUTTON_UPPER_ROW_2,
        push2_python.constants.BUTTON_UPPER_ROW_3,
        push2_python.constants.BUTTON_UPPER_ROW_4,
        push2_python.constants.BUTTON_UPPER_ROW_5,
        push2_python.constants.BUTTON_UPPER_ROW_6,
        push2_python.constants.BUTTON_UPPER_ROW_7,
        push2_python.constants.BUTTON_UPPER_ROW_8,
    ]

    lower_row_button_names = [
        push2_python.constants.BUTTON_LOWER_ROW_1,
        push2_python.constants.BUTTON_LOWER_ROW_2,
        push2_python.constants.BUTTON_LOWER_ROW_3,
        push2_python.constants.BUTTON_LOWER_ROW_4,
        push2_python.constants.BUTTON_LOWER_ROW_5,
        push2_python.constants.BUTTON_LOWER_ROW_6,
        push2_python.constants.BUTTON_LOWER_ROW_7,
        push2_python.constants.BUTTON_LOWER_ROW_8,
    ]

    instrument_devices = {}
    current_device_index_and_page = [0, 0]
    transports = []
    slots = [
        {"address": "/param/a/osc/1/type", "value": 0},
        {"address": "/param/a/osc/2/type", "value": 0},
        None,
        None,
        None,
        {"address": "/param/fx/a/1/type", "value": 0},
        {"address": "/param/fx/a/2/type", "value": 0},
        {"address": "/param/fx/global/1/type", "value": 0},
    ]

    def initialize(self, settings=None):
        device_names = [
            Path(device_file).stem
            for device_file in glob("./device_definitions/*.json")
        ]
        device_definitions = {}

        for device_name in device_names:
            try:
                device_definitions[device_name] = json.load(
                    open(
                        os.path.join(
                            definitions.DEVICE_DEFINITION_FOLDER,
                            "{}.json".format(device_name),
                        )
                    )
                )
            except FileNotFoundError:
                device_definitions[device_name] = {}

        for (
            instrument_short_name
        ) in self.get_all_distinct_instrument_short_names_helper():
            try:
                print(
                    os.path.join(
                        definitions.INSTRUMENT_DEFINITION_FOLDER,
                        "{}.json".format(instrument_short_name),
                    )
                )
                inst = json.load(
                    open(
                        os.path.join(
                            definitions.INSTRUMENT_DEFINITION_FOLDER,
                            "{}.json".format(instrument_short_name),
                        )
                    )
                )
            except FileNotFoundError:
                inst = {}
            osc_in_port = inst.get("osc_in_port", None)
            osc_out_port = inst.get("osc_out_port", None)
            log_in = logger.getChild(f"in-{osc_in_port}")
            log_out = logger.getChild(f"out-{osc_out_port}")
            client = None
            server = None
            dispatcher = Dispatcher()
            dispatcher.set_default_handler(lambda *message: log_in.debug(message))

            if osc_in_port:
                client = SimpleUDPClient("127.0.0.1", osc_in_port)

            if osc_out_port:
                loop = asyncio.get_event_loop()
                server = AsyncIOOSCUDPServer(
                    ("127.0.0.1", osc_out_port), dispatcher, loop
                )
                loop.run_until_complete(self.init_server(server))

            osc = {"client": client, "server": server, "dispatcher": dispatcher}
            self.app.osc_clients[instrument_short_name] = osc

            # populate slot values
            for slot_idx, slot in enumerate(self.slots):
                if slot:
                    dispatcher.map(
                        slot["address"],
                        lambda *resp: self.set_slot_state(slot_idx, resp),
                    )

            # Create OSC mappings for instruments with definitions
            self.instrument_devices[instrument_short_name] = []
            for x in range(8):
                self.instrument_devices[instrument_short_name].append([])

            instrument_slots = self.instrument_devices[instrument_short_name]
            for device_name in device_definitions:
                device = OSCDevice(
                    device_definitions[device_name],
                    osc,
                    get_color=self.get_current_track_color_helper,
                )
                slot_idx = device_definitions[device_name]["slot"]
                instrument_slots[slot_idx].append(device)

            # # call the all_params endpoint to populate device controls
            if client:
                print(f"Populating {instrument_short_name}")
                for slot in self.slots:
                    if slot:
                        log_out.debug("/q" + slot["address"])
                        client.send_message("/q" + slot["address"], 1.0)

            print(
                "Loaded {0} devices for instrument {1}".format(
                    sum(
                        [
                            len(slot)
                            for slot in self.instrument_devices[instrument_short_name]
                        ]
                    ),
                    instrument_short_name,
                )
            )

    """
    Initialise OSC servers and add to transport array so they can be gracefully closed
    """

    def set_slot_state(self, slot, resp):
        address, *payload = resp
        value, *rest = payload
        self.slots[slot]["value"] = int(value)

    async def init_server(self, server):
        transport, protocol = (
            await server.create_serve_endpoint()
        )  # Create datagram endpoint and start serving
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
        slots = self.instrument_devices.get(
            self.get_current_track_instrument_short_name_helper(), []
        )
        devices = []

        for slot_idx, slot in enumerate(slots):
            for device in slot:
                if slot_idx == 2 or slot_idx == 3 or slot_idx == 4:
                    devices.append(device)
                else:
                    for init in device.init:
                        if init["address"] == self.slots[slot_idx]["address"] and int(
                            init["value"]
                        ) == int(self.slots[slot_idx]["value"]):
                            devices.append(device)

        return devices

    def get_current_instrument_device(self):
        device, __ = self.get_current_instrument_device_and_page()
        return device

    def get_current_instrument_device_and_page(self):
        device_idx, page = self.current_device_index_and_page
        current_device = self.get_current_instrument_devices()[device_idx]
        return (current_device, page)

    def update_current_device_page(self, new_device=None, new_page=None):
        current_device_idx, current_page = self.current_device_index_and_page
        result = [current_device_idx, current_page]

        # resets page if device is swapepd
        if new_device != current_device_idx:
            result[1] = 0

        if new_device != None:
            result[0] = new_device

        if new_page != None:
            result[1] = new_page

        self.current_device_index_and_page = result
        new_current_device = self.get_current_instrument_device()
        print("new page", new_page)
        new_current_device.set_page(new_page)
        self.app.buttons_need_update = True

    # TODO populate display when new instrument selected
    def new_instrument_selected(self):
        pass

    def activate(self):
        self.update_buttons()

    def deactivate(self):
        for button_name in self.upper_row_button_names + [
            push2_python.constants.BUTTON_PAGE_LEFT,
            push2_python.constants.BUTTON_PAGE_RIGHT,
        ]:
            self.push.buttons.set_button_color(button_name, definitions.BLACK)

    def update_buttons(self):
        current_device = self.get_current_instrument_device()
        for count, name in enumerate(self.upper_row_button_names):
            if count < current_device.size:
                self.push.buttons.set_button_color(name, definitions.WHITE)
            else:
                self.push.buttons.set_button_color(name, definitions.BLACK)

        show_prev, show_next = current_device.get_next_prev_pages()
        if show_prev:
            self.push.buttons.set_button_color(
                push2_python.constants.BUTTON_PAGE_LEFT, definitions.WHITE
            )
        else:
            self.push.buttons.set_button_color(
                push2_python.constants.BUTTON_PAGE_LEFT, definitions.BLACK
            )
        if show_next:
            self.push.buttons.set_button_color(
                push2_python.constants.BUTTON_PAGE_RIGHT, definitions.WHITE
            )
        else:
            self.push.buttons.set_button_color(
                push2_python.constants.BUTTON_PAGE_RIGHT, definitions.BLACK
            )

    def update_display(self, ctx, w, h):
        """
        If settings mode is active, don't draw the upper parts of the screen
        because settings page will "cover them"
        """
        if not self.app.is_mode_active(self.app.settings_mode):
            # Draw OSCDevice names
            devices = self.get_current_instrument_devices()
            if devices:
                height = 20
                for i, device in enumerate(devices):
                    show_text(ctx, i, 0, device.label, background_color=definitions.RED)

                    is_selected = False
                    selected_device, _ = self.get_current_instrument_device_and_page()
                    if selected_device == device:
                        is_selected = True

                    current_track_color = self.get_current_track_color_helper()
                    if is_selected:
                        background_color = current_track_color
                        font_color = definitions.BLACK
                    else:
                        background_color = definitions.BLACK
                        font_color = current_track_color
                    show_text(
                        ctx,
                        i,
                        0,
                        device.label,
                        height=height,
                        font_color=font_color,
                        background_color=background_color,
                    )

            # Draw OSCControls
            device = self.get_current_instrument_device()
            if device:
                device.draw(ctx)

    def on_button_pressed(self, button_name):
        selected_device, _ = self.get_current_instrument_device_and_page()
        show_prev, show_next = selected_device.get_next_prev_pages()
        _, current_page = self.get_current_instrument_device_and_page()

        if button_name in self.upper_row_button_names:
            current_track_devices = self.get_current_instrument_devices()
            _, current_page = self.get_current_instrument_device_and_page()

            idx = self.upper_row_button_names.index(button_name)
            if idx < len(current_track_devices):
                new_device = current_track_devices[idx]
                # Stay on the same device page if new instrument, otherwise go to next page

                new_page = (
                    0
                    if new_device != selected_device
                    else (
                        current_page - 1
                        if show_prev
                        else current_page + 1 if show_next else 0
                    )
                )

                self.update_current_device_page(idx, new_page=new_page)
            return True
        elif button_name in self.lower_row_button_names:
            self.update_current_device_page(new_page=0)  # Reset page on new instrument
        elif button_name in [
            push2_python.constants.BUTTON_PAGE_LEFT,
            push2_python.constants.BUTTON_PAGE_RIGHT,
        ]:
            if button_name == push2_python.constants.BUTTON_PAGE_LEFT and show_prev:
                self.update_current_device_page(new_page=current_page - 1)
            elif button_name == push2_python.constants.BUTTON_PAGE_RIGHT and show_next:
                self.update_current_device_page(new_page=current_page + 1)
            return True

        elif button_name in [push2_python.constants.BUTTON_ADD_DEVICE]:
            print("ADD DEVICE PRESSED")

    def on_encoder_rotated(self, encoder_name, increment):
        try:
            current_device = self.get_current_instrument_device()
            current_device.on_encoder_rotated(encoder_name, increment)
        except Exception:
            pass  # Encoder not in list

        return True  # Always return True because encoder should not be used in any other mode if this is first active
