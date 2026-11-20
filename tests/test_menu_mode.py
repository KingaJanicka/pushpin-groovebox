"""Tests for MenuMode - the device/menu selection grid."""

from controllers import push2_constants
import push2_python.constants

from modes.menu_mode import MenuMode


def make_mode(app, devices=None):
    mode = MenuMode(app, settings=None, send_osc_func=app.send_osc)
    # Navigation reads len() of the slot's device list, so give it a real list.
    app.osc_mode.get_current_slot_devices.return_value = devices or []
    return mode


def test_should_be_enabled():
    # Pure method, no app interaction needed.
    mode = MenuMode.__new__(MenuMode)
    assert mode.should_be_enabled() is True


def test_get_should_show_next_prev(app):
    mode = make_mode(app)
    mode.page_n = 0
    assert mode.get_should_show_next_prev() == (False, True)
    mode.page_n = 1
    assert mode.get_should_show_next_prev() == (True, False)


def test_left_button_decrements_selection(app):
    mode = make_mode(app, devices=["a", "b", "c"])
    mode.selected_menu_item_index = 2
    mode.on_button_pressed(push2_constants.BUTTON_LEFT)
    assert mode.selected_menu_item_index == 1


def test_left_button_clamps_at_zero(app):
    mode = make_mode(app, devices=["a", "b", "c"])
    mode.selected_menu_item_index = 0
    mode.on_button_pressed(push2_constants.BUTTON_LEFT)
    assert mode.selected_menu_item_index == 0


def test_right_button_increments_within_bounds(app):
    mode = make_mode(app, devices=["a", "b", "c"])
    mode.selected_menu_item_index = 0
    mode.on_button_pressed(push2_constants.BUTTON_RIGHT)
    assert mode.selected_menu_item_index == 1


def test_right_button_clamps_at_last_device(app):
    mode = make_mode(app, devices=["a", "b"])
    mode.selected_menu_item_index = 1
    mode.on_button_pressed(push2_constants.BUTTON_RIGHT)
    assert mode.selected_menu_item_index == 1


def test_page_right_advances_page(app):
    mode = make_mode(app, devices=["a"])
    mode.page_n = 0
    assert mode.on_button_pressed(push2_python.constants.BUTTON_PAGE_RIGHT) is True
    assert mode.page_n == 1
    assert app.buttons_need_update is True


def test_page_left_returns_to_first_page(app):
    mode = make_mode(app, devices=["a"])
    mode.page_n = 1
    assert mode.on_button_pressed(push2_python.constants.BUTTON_PAGE_LEFT) is True
    assert mode.page_n == 0


def test_display_lays_out_rows_of_eight_and_never_passes_column_seven(app, mocker):
    """Rows of eight at y 20, 45, 70, 95; a fifth row (items 33-40) used to go to
    columns 8-15, which show_text refuses."""
    from types import SimpleNamespace

    drawn = mocker.patch("modes.menu_mode.show_text")
    devices = [SimpleNamespace(label=f"D{i}") for i in range(40)]
    mode = make_mode(app, devices=devices)
    mode.update_display(mocker.MagicMock(), 960, 160)
    placed = {call.args[3]: (call.args[1], call.args[2]) for call in drawn.call_args_list}
    assert placed["D0"] == (0, 20)
    assert placed["D9"] == (1, 45)
    assert placed["D26"] == (2, 95)
    assert all(0 <= column < 8 for column, _ in placed.values())
    assert placed["D32"][0] == 0
