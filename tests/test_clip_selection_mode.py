"""Tests for ClipSelectionMode - clip grid paging and clip listing.

initialize() globs patch folders and may write presets.json, so it is patched
out; the pure paging/grid methods are exercised with minimal local state.
"""

import pytest
import push2_python.constants

import definitions
from modes.clip_selection_mode import ClipSelectionMode


@pytest.fixture
def clip(app, mocker):
    mocker.patch.object(ClipSelectionMode, "initialize")
    mode = ClipSelectionMode(app, settings=None)
    mode.current_page = 0
    mode.state = [0] * 8
    return mode


def test_should_be_enabled(clip):
    assert clip.should_be_enabled() is True


def test_list_clips_builds_8x8_boolean_grid(clip):
    # Globs the working dir for saved clips; assert only on the grid shape and
    # cell type so the test doesn't depend on stray seq_metro_*.json files.
    clip.list_clips()
    assert len(clip.clips) == 8
    assert all(len(row) == 8 for row in clip.clips)
    assert all(isinstance(cell, bool) for row in clip.clips for cell in row)


def test_num_pages_and_navigation(clip, app):
    assert clip.get_num_pages() == 2
    clip.current_page = 0
    clip.next_page()
    assert clip.current_page == 1
    clip.prev_page()
    assert clip.current_page == 0


def test_pad_ij_to_bank_and_preset_num(clip):
    clip.current_page = 0
    assert clip.pad_ij_to_bank_and_preset_num((2, 3)) == (19, 0)


def test_has_prev_next_pages(clip):
    clip.current_page = 0
    assert clip.has_prev_next_pages() == (False, True)


def test_get_preset_path_factory(clip):
    clip.state[0] = 0
    assert clip.get_preset_path("X") == f"{definitions.FACTORY_PATCHES_FOLDER}/X"


def test_right_button_navigates(clip):
    clip.current_page = 0
    assert clip.on_button_pressed(push2_python.constants.BUTTON_RIGHT) is True
    assert clip.current_page == 1


def test_play_button_toggles_transport(clip, app):
    app.metro_sequencer_mode.sequencer_is_playing = False
    clip.on_button_pressed(push2_python.constants.BUTTON_PLAY)
    app.metro_sequencer_mode.start_timeline.assert_called_once()
    assert app.metro_sequencer_mode.sequencer_is_playing is True
