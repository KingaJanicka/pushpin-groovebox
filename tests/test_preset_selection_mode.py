"""Tests for PresetSelectionMode - preset/bank paging and pad mapping.

initialize() globs the Surge patch folders off disk and may write presets.json,
so it is patched out; tests set the small amount of state the pure methods need.
"""

import pytest
import push2_python.constants

import definitions
from modes.preset_selection_mode import PresetSelectionMode


@pytest.fixture
def preset(app, mocker):
    mocker.patch.object(PresetSelectionMode, "initialize")
    mode = PresetSelectionMode(app, settings=None)
    mode.current_page = 0
    mode.state = [0] * 8
    return mode


def test_should_be_enabled(preset):
    assert preset.should_be_enabled() is True


def test_bank_and_page_counts_from_instrument_info(preset):
    # Fixture instrument has n_banks == 1.
    assert preset.get_num_banks() == 1
    assert preset.get_num_pages() == 2


def test_pad_ij_to_bank_and_preset_num_page_0(preset):
    preset.current_page = 0
    assert preset.pad_ij_to_bank_and_preset_num((0, 0)) == (0, 0)
    assert preset.pad_ij_to_bank_and_preset_num((1, 2)) == (10, 0)


def test_pad_ij_to_bank_and_preset_num_second_half(preset):
    preset.current_page = 1
    # Second half of bank 0 is offset by 64.
    assert preset.pad_ij_to_bank_and_preset_num((0, 0)) == (64, 0)


def test_has_prev_next_pages(preset):
    preset.current_page = 0
    assert preset.has_prev_next_pages() == (False, True)
    preset.current_page = 1
    assert preset.has_prev_next_pages() == (True, False)


def test_next_page_advances_and_clamps(preset, app):
    preset.current_page = 0
    preset.next_page()
    assert preset.current_page == 1
    assert app.pads_need_update is True
    # Clamps at last page (num_pages - 1).
    preset.next_page()
    assert preset.current_page == 1


def test_prev_page_clamps_at_zero(preset):
    preset.current_page = 1
    preset.prev_page()
    assert preset.current_page == 0
    preset.prev_page()
    assert preset.current_page == 0


def test_get_preset_path_uses_factory_folder_for_state_zero(preset):
    preset.state[0] = 0
    path = preset.get_preset_path("My Patch")
    assert path == f"{definitions.FACTORY_PATCHES_FOLDER}/My Patch"


def test_right_button_navigates_next_page(preset):
    preset.current_page = 0
    assert preset.on_button_pressed(push2_python.constants.BUTTON_RIGHT) is True
    assert preset.current_page == 1


def test_play_button_toggles_transport(preset, app):
    app.metro_sequencer_mode.sequencer_is_playing = False
    preset.on_button_pressed(push2_python.constants.BUTTON_PLAY)
    app.metro_sequencer_mode.start_timeline.assert_called_once()
    assert app.metro_sequencer_mode.sequencer_is_playing is True


def test_new_instrument_selected_resets_page(preset, app):
    preset.current_page = 1
    preset.new_instrument_selected()
    assert preset.current_page == 0
    assert app.pads_need_update is True
