"""Renaming presets from the Push: the name editor (modes/rename_mode.py) and
the preset browser's upper button 3 (mono2k user presets, Surge user patches)."""
import json
import os
from unittest.mock import MagicMock, patch

import pytest
import push2_python.constants as B

import definitions
import m2k_state
from modes.rename_mode import CHARSET, NameEditor, RenameMode
from tests.test_m2k_state import browser  # noqa: F401  (fixture)


# ------------------------------------------------------------- the editor


def test_editor_moves_and_changes_letters():
    e = NameEditor("AB")
    e.change(1)
    assert e.text == "BB"
    e.right()
    e.change(-1)
    assert e.text == "BA"
    e.left()
    e.left()                                          # stops at the start
    assert e.cursor == 0


def test_editor_right_past_the_end_adds_a_character():
    e = NameEditor("A")
    e.right()
    assert e.text == "A " and e.cursor == 1
    e.change(1)
    assert e.text == "AA"


def test_editor_drops_an_untouched_trailing_blank_when_going_back():
    e = NameEditor("A")
    e.right()
    e.left()
    assert e.text == "A"


def test_editor_wraps_through_the_charset():
    e = NameEditor(" ")
    e.change(-1)
    assert e.text == CHARSET[-1]
    e.change(1)
    assert e.text == " "


def test_editor_delete_and_limits():
    e = NameEditor("ABC")
    e.right()
    e.delete()
    assert e.text == "AC" and e.cursor == 1
    e.delete()
    e.delete()
    assert e.text == " "                              # never empty underneath
    long = NameEditor("X" * 30)
    assert len(long.text) == 24
    long.cursor = 23
    long.right()
    assert len(long.text) == 24


def test_editor_keeps_characters_it_cant_type():
    e = NameEditor("é1")
    assert e.text == "é1"
    e.change(1)
    assert e.text[0] in CHARSET


# --------------------------------------------------------- the overlay mode


@pytest.fixture
def overlay(app):
    app.active_modes = []
    app.is_mode_active = lambda m: m in app.active_modes
    return RenameMode(app, settings=None)


def test_overlay_edits_and_saves(overlay, app):
    confirmed = []
    overlay.start("Rename", "AB", lambda name: confirmed.append(name), cancel_button=B.BUTTON_UPPER_ROW_3)
    assert overlay in app.active_modes
    for button in (B.BUTTON_RIGHT, B.BUTTON_RIGHT, B.BUTTON_UP, B.BUTTON_UP, B.BUTTON_UP):
        assert overlay.on_button_pressed(button) is True
    overlay.on_button_pressed(B.BUTTON_SELECT)
    assert confirmed == ["ABC"]
    assert overlay not in app.active_modes


def test_overlay_cancel_button_closes_without_saving(overlay, app):
    confirmed = []
    overlay.start("Rename", "AB", lambda name: confirmed.append(name), cancel_button=B.BUTTON_UPPER_ROW_3)
    overlay.on_button_pressed(B.BUTTON_UP)
    overlay.on_button_pressed(B.BUTTON_UPPER_ROW_3)
    assert confirmed == [] and overlay not in app.active_modes


def test_overlay_stays_open_with_the_reason_when_refused(overlay, app):
    overlay.start("Rename", "AB", lambda name: "That name is taken", cancel_button=B.BUTTON_UPPER_ROW_3)
    overlay.on_button_pressed(B.BUTTON_SELECT)
    assert overlay in app.active_modes and overlay.message == "That name is taken"
    overlay.on_button_pressed(B.BUTTON_LEFT)
    assert overlay.message == ""


def test_overlay_refuses_an_empty_name(overlay, app):
    confirmed = []
    overlay.start("Rename", " ", lambda name: confirmed.append(name), cancel_button=B.BUTTON_UPPER_ROW_3)
    overlay.on_button_pressed(B.BUTTON_SELECT)
    assert confirmed == [] and overlay.message


def test_overlay_swallows_everything_else_while_open(overlay):
    overlay.start("Rename", "A", lambda name: None, cancel_button=B.BUTTON_UPPER_ROW_3)
    assert overlay.on_button_pressed(B.BUTTON_PLAY) is True
    assert overlay.on_button_released(B.BUTTON_SELECT) is True
    assert overlay.on_encoder_rotated(B.ENCODER_TRACK1_ENCODER, 1) is True
    assert overlay.on_pad_pressed(0, (0, 0), 100) is True


def test_overlay_draws_title_letters_and_cursor(overlay):
    overlay.start("Rename X", "AB", lambda name: None, cancel_button=B.BUTTON_UPPER_ROW_3)
    ctx = MagicMock()
    overlay.update_display(ctx, 960, 160)
    shown = [c.args[0] for c in ctx.show_text.call_args_list]
    assert shown[:3] == ["Rename X", "A", "B"]


# ------------------------------------------------- renaming in the browser


@pytest.fixture
def renaming(browser, app):  # noqa: F811
    mode, instrument, port, tmp_path = browser
    app.active_modes = []
    app.is_mode_active = lambda m: m in app.active_modes
    app.rename_mode = RenameMode(app, settings=None)
    return mode, instrument, tmp_path


def user_preset_in_slot(mode, instrument):
    sound = m2k_state.capture(instrument.osc["client"], mode.m2k_sounds)
    sound_id = mode.m2k_sounds.save_user(sound)
    mode.m2k_presets["Pushpin 2"][0] = sound_id
    mode.m2k_presets["Pushpin 2"][3] = sound_id               # (another slot using the same preset)
    return sound_id


def test_rename_a_mono2k_user_preset(renaming):
    mode, instrument, tmp_path = renaming
    user_preset_in_slot(mode, instrument)
    assert mode.rename_target("Pushpin 2") == ("mono2k", "GND-SIN 1")
    assert mode.rename_preset("Pushpin 2", "  Sine Drone ") is None
    folder = tmp_path / "m2k_presets"
    assert sorted(os.listdir(folder)) == ["Sine Drone.json"]
    assert json.load(open(folder / "Sine Drone.json"))["name"] == "Sine Drone"
    assert mode.m2k_presets["Pushpin 2"][0] == mode.m2k_presets["Pushpin 2"][3] == "User/Sine Drone"
    assert json.load(open(tmp_path / "m2k_presets.json"))["Pushpin 2"][0] == "User/Sine Drone"
    assert mode.m2k_sounds.resolve("User/Sine Drone").machine == 0
    mode.app.add_display_notification.assert_called_with("Renamed to Sine Drone")


def test_rename_refuses_taken_and_bad_names(renaming):
    mode, instrument, _ = renaming
    user_preset_in_slot(mode, instrument)
    mode.m2k_sounds.save_user(mode.m2k_sounds.machine_sound(0))   # "GND-SIN 2" exists too
    assert mode.rename_preset("Pushpin 2", "GND-SIN 2") == "That name is taken"
    assert mode.rename_preset("Pushpin 2", "a/b") == "That name can't be used"
    assert mode.rename_preset("Pushpin 2", "..") == "That name can't be used"
    assert mode.rename_preset("Pushpin 2", "GND-SIN 1") is None   # unchanged: fine


def test_factory_slots_cant_be_renamed(renaming):
    mode, _, _ = renaming
    mode.m2k_presets["Pushpin 2"][0] = "Factory/KICK/BOOM808"
    assert mode.rename_target("Pushpin 2") is None
    mode.on_button_pressed(B.BUTTON_UPPER_ROW_3)
    mode.app.add_display_notification.assert_called_with(
        "Only user presets can be renamed (Save to New first)")
    assert mode.app.rename_mode not in mode.app.active_modes


def test_upper_button_3_opens_the_editor_and_select_renames(renaming):
    mode, instrument, tmp_path = renaming
    user_preset_in_slot(mode, instrument)
    assert mode.on_button_pressed(B.BUTTON_UPPER_ROW_3) is True
    editor_mode = mode.app.rename_mode
    assert editor_mode in mode.app.active_modes and editor_mode.editor.text == "GND-SIN 1"
    for _ in range(3):
        editor_mode.on_button_pressed(B.BUTTON_DELETE)       # deletes "GND" (cursor at 0)
    editor_mode.on_button_pressed(B.BUTTON_SELECT)
    assert editor_mode not in mode.app.active_modes
    assert mode.m2k_presets["Pushpin 2"][0] == "User/-SIN 1"
    assert os.path.isfile(tmp_path / "m2k_presets" / "-SIN 1.json")


def test_rename_a_surge_user_patch(app, tmp_path, monkeypatch):
    from modes.preset_selection_mode import PresetSelectionMode
    from tests.test_cc_client import M2K_INSTRUMENT, make_instrument

    definition = dict(M2K_INSTRUMENT)
    definition.pop("engine")
    instrument, _ = make_instrument(app, definition=definition)
    user = tmp_path / "Surge User"
    (user / "Basses").mkdir(parents=True)
    (user / "Basses" / "Wob.fxp").write_bytes(b"fxp")
    monkeypatch.setattr(definitions, "USER_PATCHES_FOLDER", str(user))
    monkeypatch.chdir(tmp_path)
    app.instruments = {"Pushpin 2": instrument}
    ism = app.instrument_selection_mode
    ism.get_all_distinct_instrument_short_names.return_value = ["Pushpin 2"]
    ism.get_current_instrument_short_name.return_value = "Pushpin 2"
    with patch("modes.preset_selection_mode.glob", lambda *a, **k: []):
        mode = PresetSelectionMode(app, settings=None)
    old = str(user / "Basses" / "Wob")
    mode.presets["Pushpin 2"][0] = old
    mode.presets["Pushpin 2"][5] = old
    assert mode.rename_target("Pushpin 2") == ("surge", old)
    assert mode.rename_preset("Pushpin 2", "Wobble") is None
    assert os.listdir(user / "Basses") == ["Wobble.fxp"]
    assert mode.presets["Pushpin 2"][0] == mode.presets["Pushpin 2"][5] == str(user / "Basses" / "Wobble")
    assert "Wobble" in mode.patches["User"]["Basses"]
    assert json.load(open(tmp_path / "presets.json"))["Pushpin 2"][0].endswith("Basses/Wobble")


def test_surge_factory_patches_cant_be_renamed(app, tmp_path, monkeypatch):
    from modes.preset_selection_mode import PresetSelectionMode
    monkeypatch.chdir(tmp_path)
    app.instruments = {}
    app.instrument_selection_mode.get_all_distinct_instrument_short_names.return_value = ["Pushpin 2"]
    with patch("modes.preset_selection_mode.glob", lambda *a, **k: []):
        mode = PresetSelectionMode(app, settings=None)
    assert mode.rename_target("Pushpin 2") is None              # "Init Saw", a factory patch
