import definitions
import push2_python
import time
from controllers import push2_constants

from definitions import PyshaMode
from user_interface.display_utils import show_text


class MenuMode(PyshaMode):

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

    page_n = 0
    selected_menu_item_index = 0
    upper_row_selected = ""
    lower_row_selected = ""
    inter_message_message_min_time_ms = 4  # ms wait time after each message to DDRM
    is_active = False

    def __init__(self, app, settings=None, send_osc_func=None):
        super().__init__(app, settings=settings)
        self.send_osc_func = send_osc_func

    async def should_be_enabled(self):
        return True

    async def get_should_show_next_prev(self):
        show_prev = self.page_n == 1
        show_next = self.page_n == 0
        return show_prev, show_next

    async def activate(self):
        instrument = await self.app.osc_mode.get_current_instrument()
        device = await self.app.osc_mode.get_current_instrument_device()
        devices_in_current_slot = await self.app.osc_mode.get_current_slot_devices()
        for idx, item in enumerate(devices_in_current_slot):
            if item == device:
                self.selected_menu_item_index = idx

        await self.update_buttons()

    async def deactivate(self):
        current_device = await self.app.osc_mode.get_current_instrument_device()
        await current_device.set_page(0)
        self.app.osc_mode.current_device_index_and_page[1] = 0
        instrument = await self.app.osc_mode.get_current_instrument()
        # print("called q slots")
        # TODO: This needs to be revised with state rewrite
        # old: I have no clue why the fricity frick this sleep needs to be here
        # old: But it does and the FX switching will lag behind one selection if not
        
        # TODO: Still a problem and now increase of sleep does not help
        # WELP
        
        asyncio.sleep(0.2)
        await instrument.query_slots()
        await instrument.update_current_devices()
        asyncio.sleep(0.1)
        await current_device.query_all_controls()
        for button_name in (
            self.upper_row_button_names
            + self.lower_row_button_names
            + [
                push2_python.constants.BUTTON_PAGE_LEFT,
                push2_python.constants.BUTTON_PAGE_RIGHT,
            ]
        ):
            self.push.buttons.set_button_color(button_name, definitions.BLACK)

    async def update_display(self, ctx, w, h):
        devices_in_current_slot = await self.app.osc_mode.get_current_slot_devices()
        for idx, device in enumerate(devices_in_current_slot):
            if idx == self.selected_menu_item_index:
                background_color = definitions.YELLOW
            else:
                background_color = definitions.GRAY_LIGHT
            if idx < 8:
                show_text(
                    ctx,
                    idx,
                    20,
                    device.label,
                    height=25,
                    font_color=definitions.BLACK,
                    background_color=background_color,
                    font_size_percentage=0.8,
                    center_vertically=True,
                    center_horizontally=True,
                    rectangle_padding=1,
                )
            elif idx < 16:
                show_text(
                    ctx,
                    idx - 8,
                    45,
                    device.label,
                    height=25,
                    font_color=definitions.BLACK,
                    background_color=background_color,
                    font_size_percentage=0.8,
                    center_vertically=True,
                    center_horizontally=True,
                    rectangle_padding=1,
                )
            elif idx < 24:
                show_text(
                    ctx,
                    idx - 16,
                    70,
                    device.label,
                    height=25,
                    font_color=definitions.BLACK,
                    background_color=background_color,
                    font_size_percentage=0.8,
                    center_vertically=True,
                    center_horizontally=True,
                    rectangle_padding=1,
                )
            elif idx < 32:
                show_text(
                    ctx,
                    idx - 24,
                    95,
                    device.label,
                    height=25,
                    font_color=definitions.BLACK,
                    background_color=background_color,
                    font_size_percentage=0.8,
                    center_vertically=True,
                    center_horizontally=True,
                    rectangle_padding=1,
                )
            elif idx < 40:
                show_text(
                    ctx,
                    idx - 24,
                    110,
                    device.label,
                    height=25,
                    font_color=definitions.BLACK,
                    background_color=background_color,
                    font_size_percentage=0.8,
                    center_vertically=True,
                    center_horizontally=True,
                    rectangle_padding=1,
                )

    async def update_buttons(self):
        pass

    async def on_button_pressed(self, button_name):
        devices_in_current_slot = await self.app.osc_mode.get_current_slot_devices()
        instrument_shortname = (
            await self.app.osc_mode.get_current_instrument_short_name_helper()
        )

        if button_name is push2_constants.BUTTON_LEFT:
            if self.selected_menu_item_index - 1 >= 0:
                self.selected_menu_item_index -= 1
        elif button_name is push2_constants.BUTTON_RIGHT:
            number_of_devices_in_current_slot = len(devices_in_current_slot)
            if (
                0
                <= self.selected_menu_item_index + 1
                < number_of_devices_in_current_slot
            ):
                self.selected_menu_item_index += 1
        elif button_name is push2_constants.BUTTON_UP:
            number_of_devices_in_current_slot = len(devices_in_current_slot)
            if (
                0
                <= self.selected_menu_item_index - 8
                < number_of_devices_in_current_slot
            ):
                self.selected_menu_item_index -= 8
        elif button_name is push2_constants.BUTTON_DOWN:
            number_of_devices_in_current_slot = len(devices_in_current_slot)
            if (
                0
                <= self.selected_menu_item_index + 8
                < number_of_devices_in_current_slot
            ):
                self.selected_menu_item_index += 8

        elif button_name == push2_constants.BUTTON_ADD_DEVICE:
            selected_device = devices_in_current_slot[self.selected_menu_item_index]
            
            try:
                
                # Using the blocking select call here
                # to prevent a data race
                # self.app.queue.append(selected_device.select())
                selected_device.select()
                devices = await self.app.osc_mode.get_current_instrument_devices()
                for device in devices:
                    if device.label == selected_device.label:
                        await device.query_all_controls()
                await self.app.toggle_menu_mode()
                self.app.buttons_need_update = True
            except IndexError:
                # Do nothing because the button has no assigned tone
                pass
            return True

        elif button_name in [
            push2_python.constants.BUTTON_PAGE_LEFT,
            push2_python.constants.BUTTON_PAGE_RIGHT,
        ]:
            show_prev, show_next = await self.get_should_show_next_prev()
            if button_name == push2_python.constants.BUTTON_PAGE_LEFT and show_prev:
                self.page_n = 0
            elif button_name == push2_python.constants.BUTTON_PAGE_RIGHT and show_next:
                self.page_n = 1
            self.app.buttons_need_update = True
            return True
