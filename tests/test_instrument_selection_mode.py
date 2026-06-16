"""Tests for InstrumentSelectionMode - instrument metadata + selection logic.

create_instruments() reads JSON definitions off disk and appends to a
*class-level* list, so it's patched out here; tests set ``instruments_info`` on
the instance directly to exercise the pure getters and selection logic.
"""

import push2_python.constants

import definitions
from modes.instrument_selection_mode import InstrumentSelectionMode


def make_info(short_name, color):
    return {
        "instrument_name": short_name,
        "instrument_short_name": short_name,
        "midi_channel": 1,
        "osc_in_port": 7000,
        "osc_out_port": 7001,
        "color": color,
        "n_banks": 1,
        "bank_names": None,
        "default_layout": definitions.LAYOUT_MELODIC,
        "illuminate_local_notes": True,
        "instrument_index": 0,
    }


def make_mode(app, mocker, infos):
    mocker.patch.object(InstrumentSelectionMode, "create_instruments")
    mode = InstrumentSelectionMode(app, settings=None)
    mode.instruments_info = infos
    return mode


def test_getters_reflect_selected_instrument(app, mocker):
    infos = [make_info("BASS", definitions.RED), make_info("LEAD", definitions.CYAN)]
    mode = make_mode(app, mocker, infos)

    mode.selected_instrument = 1
    assert mode.get_current_instrument_short_name() == "LEAD"
    assert mode.get_current_instrument_color() == definitions.CYAN
    assert mode.get_current_instrument_osc_out_port() == 7001
    assert mode.get_current_instrument_osc_in_port() == 7000


def test_get_instrument_color_by_index(app, mocker):
    infos = [make_info("BASS", definitions.RED), make_info("LEAD", definitions.CYAN)]
    mode = make_mode(app, mocker, infos)
    assert mode.get_instrument_color(0) == definitions.RED


def test_distinct_short_names_are_sorted_and_unique(app, mocker):
    infos = [
        make_info("LEAD", definitions.CYAN),
        make_info("BASS", definitions.RED),
        make_info("LEAD", definitions.CYAN),
    ]
    mode = make_mode(app, mocker, infos)
    assert mode.get_all_distinct_instrument_short_names() == ["BASS", "LEAD"]


def test_select_instrument_updates_index_and_notifies(app, mocker):
    infos = [make_info("BASS", definitions.RED), make_info("LEAD", definitions.CYAN)]
    mode = make_mode(app, mocker, infos)

    mode.select_instrument(1)
    assert mode.selected_instrument == 1
    assert app.steps_held == []
    app.osc_mode.new_instrument_selected.assert_called_once()


def test_button_press_selects_corresponding_instrument(app, mocker):
    infos = [make_info(f"I{i}", definitions.CYAN) for i in range(8)]
    mode = make_mode(app, mocker, infos)

    result = mode.on_button_pressed(push2_python.constants.BUTTON_LOWER_ROW_3)
    assert result is True
    assert mode.selected_instrument == 2
    assert app.pads_need_update is True
    assert app.buttons_need_update is True
