"""Saving and loading mono2k sounds (m2k_state.py) and the preset browser's
mono2k slots (PresetSelectionMode on a track playing mono2k)."""
import json
import os
from glob import glob
from unittest.mock import MagicMock

import pytest
import push2_python.constants as B
from pythonosc.dispatcher import Dispatcher

import m2k_state
from cc_client import MidiCCClient, param_number
from m2k_state import M2KSounds, Sound
from modes.engine_selection_mode import EngineSelectionMode
from modes.preset_selection_mode import PresetSelectionMode
from tests.test_cc_client import M2K_DIR, M2K_INSTRUMENT, make_instrument

CATALOGUE = M2KSounds.load()


def nrpns(midi_out):
    """The (msb, lsb, whole, fraction) NRPNs sent on a mocked port, in order."""
    calls = [c.args for c in midi_out.control.call_args_list]
    out, i = [], 0
    while i + 3 < len(calls):
        if calls[i][0] == 99 and calls[i + 1][0] == 98 and calls[i + 2][0] == 6 and calls[i + 3][0] == 38:
            out.append((calls[i][1], calls[i + 1][1], calls[i + 2][1], calls[i + 3][1]))
            i += 4
        else:
            i += 1
    return out


@pytest.fixture
def client():
    return MidiCCClient(MagicMock(name="port"), Dispatcher(), channel=0, nrpn=True, plain_ccs={3, 9, 14, 120, 123})


# --------------------------------------------------------------- the client


def test_param_addresses_go_as_nrpn_1(client):
    client.send_message("/m2k/param/69", 90.5)
    assert nrpns(client.midi_out) == [(1, 69, 90, 64)]
    assert client.values["/m2k/param/69"] == 90.5


def test_param_addresses_need_nrpn():
    plain = MidiCCClient(MagicMock(), Dispatcher(), channel=0)
    plain.send_message("/m2k/param/69", 90.0)
    plain.midi_out.control.assert_not_called()


def test_param_number_parses_only_param_addresses():
    assert param_number("/m2k/param/0") == 0
    assert param_number("/m2k/param/70") == 70
    assert param_number("/cc/70") is None
    assert param_number("/m2k/param/x") is None


# ------------------------------------------------------- the generated data


def test_sounds_json_has_every_parameter_machine_and_library_sound():
    assert CATALOGUE is not None
    assert CATALOGUE.param_count == 71
    assert len(CATALOGUE.machines) == 19 and all(len(m["kit"]) == 71 for m in CATALOGUE.machines)
    assert len(CATALOGUE.library) == 96 and all(len(s["kit"]) == 71 for s in CATALOGUE.library)
    assert CATALOGUE.categories == ["KICK", "SNARE", "HATS", "PERC", "BASS", "LEAD", "PAD", "FX"]
    assert CATALOGUE.address(0) == "/cc/48"          # SYN A
    assert CATALOGUE.address(17) == "/cc/73"         # WDTH
    assert CATALOGUE.address(69) == "/m2k/param/69"  # MOD mix: no CC


def test_every_machine_init_sets_all_71_parameters():
    for path in sorted(glob(os.path.join(M2K_DIR, "00_machine_*.json"))):
        device = json.load(open(path))
        set_params = set()
        for message in device["init"][1:]:
            address = message["address"]
            matches = [p for p in range(71) if CATALOGUE.address(p) == address]
            assert matches, (path, address)
            set_params.update(matches)
        assert set_params == set(range(71)), path


# ----------------------------------------------------------- capture/apply


def test_nothing_to_capture_before_a_machine(client):
    assert m2k_state.capture(client, CATALOGUE) is None


def test_apply_then_capture_round_trips_a_library_sound(client):
    sound = CATALOGUE.resolve("Factory/KICK/BOOM808")
    assert sound.machine == 15 and sound.name == "BOOM808"
    m2k_state.apply(sound, client, CATALOGUE)
    assert client.midi_out.control.call_args_list[0].args == (14, 15, 0)     # the machine first
    assert len(nrpns(client.midi_out)) == 71
    captured = m2k_state.capture(client, CATALOGUE)
    assert captured.machine == 15 and captured.params == sound.params


def test_capture_follows_page_edits(client):
    m2k_state.apply(CATALOGUE.machine_sound(5), client, CATALOGUE)
    client.send_message("/cc/73", 40.5)               # WDTH on the FILT page
    client.send_message("/m2k/param/69", 12.0)        # MOD mix
    captured = m2k_state.capture(client, CATALOGUE)
    assert captured.params[17] == 40.5 and captured.params[69] == 12.0


def test_ids_resolve_and_unknown_ids_dont():
    assert CATALOGUE.resolve("Machines/GND-SIN").machine == 0
    assert CATALOGUE.resolve("Machines/GND-SIN").params == [float(v) for v in CATALOGUE.machines[0]["kit"]]
    assert CATALOGUE.resolve("Factory/KICK/NOPE") is None
    assert CATALOGUE.resolve("Surge/whatever") is None
    assert CATALOGUE.resolve(None) is None


def test_tree_lists_the_library_by_category_and_the_machines():
    tree = CATALOGUE.tree()
    assert list(tree) == ["Factory", "Machines"]                  # no User folder yet
    assert list(tree["Factory"]) == CATALOGUE.categories
    assert all(len(sounds) == 12 for sounds in tree["Factory"].values())
    assert tree["Factory"]["KICK"]["BOOM808"] == "Factory/KICK/BOOM808"
    assert len(tree["Machines"]) == 19


def test_files_round_trip_and_short_files_fill_from_init(tmp_path):
    path = str(tmp_path / "s.json")
    sound = CATALOGUE.resolve("Factory/BASS/" + CATALOGUE.tree()["Factory"]["BASS"].__iter__().__next__())
    CATALOGUE.write(path, sound)
    data = json.load(open(path))
    assert data["engine"] == "mono2k" and data["machine_name"] == CATALOGUE.machines[sound.machine]["name"]
    assert CATALOGUE.read(path).params == sound.params
    short = CATALOGUE.sound_from_json({"machine": 3, "params": [1, 2]})
    assert short.params[:2] == [1.0, 2.0] and short.params[2:] == [float(v) for v in CATALOGUE.machines[3]["kit"][2:]]
    assert CATALOGUE.sound_from_json({"machine": 99}) is None
    assert CATALOGUE.read(str(tmp_path / "missing.json")) is None


def test_user_presets_are_numbered_and_browsable(tmp_path):
    catalogue = M2KSounds.load(user_folder=str(tmp_path / "user"))
    first = catalogue.save_user(catalogue.machine_sound(15))
    second = catalogue.save_user(catalogue.machine_sound(15))
    assert (first, second) == ("User/DRM-KICK 1", "User/DRM-KICK 2")
    assert catalogue.tree()["User"] == {"DRM-KICK 1": first, "DRM-KICK 2": second}
    assert catalogue.resolve(first).machine == 15


# ------------------------------------------------------ the preset browser


@pytest.fixture
def browser(app, tmp_path, monkeypatch):
    """The preset browser with one track (Pushpin 2) playing mono2k."""
    instrument, ports = make_instrument(app)          # (before chdir: it loads engines/m2k/definitions)
    monkeypatch.chdir(tmp_path)                       # presets.json and m2k_presets.json land here
    monkeypatch.setattr("modes.preset_selection_mode.glob", lambda *a, **k: [])   # no Surge patch folders
    app.instruments = {"Pushpin 2": instrument}
    ism = app.instrument_selection_mode
    ism.get_all_distinct_instrument_short_names.return_value = ["Pushpin 2"]
    ism.get_current_instrument_short_name.return_value = "Pushpin 2"
    ism.selected_instrument = 0
    ism.instruments_info = [{"instrument_short_name": "Pushpin 2", "color": "green"}]
    app.osc_mode.get_current_instrument_devices.return_value = []
    app.osc_mode.get_current_instrument.return_value = instrument
    mode = PresetSelectionMode(app, settings=None)
    mode.m2k_state_folder = str(tmp_path / "m2k_state")
    mode.m2k_sounds = M2KSounds.load(user_folder=str(tmp_path / "m2k_presets"))
    mode.update_pads = lambda: None                   # paints all 8 tracks' columns; one here
    instrument.init_devices_sync()                    # startup: machine 0's INIT sound
    return mode, instrument, ports["Pushpin 2 m2k"], tmp_path


def slot_file(mode, slot):
    return mode.m2k_slot_path("Pushpin 2", slot)


def test_browser_tree_is_mono2ks_on_a_mono2k_track(browser):
    mode, instrument, _, _ = browser
    assert list(mode.browser_tree()) == ["Factory", "Machines"]
    instrument.set_active_engine("surge-xt-cli")
    assert mode.browser_tree() is mode.patches


def test_switching_slots_keeps_the_old_slot_and_plays_the_new(browser):
    mode, instrument, port, _ = browser
    instrument.osc["client"].send_message("/cc/73", 33.0)            # an edit on slot 0
    mode.on_pad_pressed(None, (1, 0), 100)                            # slot 1 (empty)
    saved = json.load(open(slot_file(mode, 0)))
    assert saved["params"][17] == 33.0
    assert m2k_state.capture(instrument.osc["client"], mode.m2k_sounds).params == mode.m2k_sounds.machine_sound(0).params

    mode.on_pad_pressed(None, (0, 0), 100)                            # back to slot 0: the edit is back
    assert m2k_state.capture(instrument.osc["client"], mode.m2k_sounds).params[17] == 33.0


def test_picking_a_factory_sound_loads_it_into_the_slot(browser):
    mode, instrument, port, tmp_path = browser
    mode.browser_active = True
    mode.current_address = "Factory/KICK/BOOM808"
    assert mode.set_pad_preset_slot((0, 0)) is True
    captured = m2k_state.capture(instrument.osc["client"], mode.m2k_sounds)
    assert captured.machine == 15
    assert instrument.current_devices[0].label == "DRM-KICK"         # the machine page followed
    assert json.load(open(slot_file(mode, 0)))["machine"] == 15
    assert mode.m2k_presets["Pushpin 2"][0] == "Factory/KICK/BOOM808"
    assert json.load(open(tmp_path / "m2k_presets.json"))["Pushpin 2"][0] == "Factory/KICK/BOOM808"
    assert mode.slot_label("Pushpin 2", 0) == "BOOM808"
    assert mode.presets["Pushpin 2"][0] != "Factory/KICK/BOOM808"     # Surge's list untouched


def test_releasing_a_pad_doesnt_reset_the_mono2k_sound(browser):
    mode, instrument, port, _ = browser
    instrument.osc["client"].send_message("/cc/73", 33.0)
    mode.app.steps_held = [0]
    port.control.reset_mock()
    mode.on_pad_released(None, (0, 0), 0)
    assert [c.args for c in port.control.call_args_list if c.args[0] == 14] == []   # no machine INIT resent
    assert m2k_state.capture(instrument.osc["client"], mode.m2k_sounds).params[17] == 33.0


def test_save_to_current_and_save_to_new(browser):
    mode, instrument, _, tmp_path = browser
    instrument.osc["client"].send_message("/cc/72", 7.0)
    assert mode.on_button_pressed(B.BUTTON_UPPER_ROW_1) is True
    assert json.load(open(slot_file(mode, 0)))["params"][16] == 7.0

    assert mode.on_button_pressed(B.BUTTON_UPPER_ROW_2) is True
    assert os.path.isfile(tmp_path / "m2k_presets" / "GND-SIN 1.json")
    assert mode.m2k_presets["Pushpin 2"][0] == "User/GND-SIN 1"
    assert "User" in mode.browser_tree()


def test_autosave_saves_changes_only_and_not_too_often(browser):
    mode, instrument, _, _ = browser
    mode.autosave_m2k(now=100.0)
    assert os.path.isfile(slot_file(mode, 0))                         # first: nothing saved yet
    first = os.path.getmtime(slot_file(mode, 0))
    os.utime(slot_file(mode, 0), (first - 50, first - 50))
    mode.autosave_m2k(now=110.0)
    assert os.path.getmtime(slot_file(mode, 0)) == first - 50         # unchanged: not rewritten
    instrument.osc["client"].send_message("/cc/73", 21.0)
    mode.autosave_m2k(now=111.0)
    assert json.load(open(slot_file(mode, 0)))["params"][17] != 21.0  # too soon
    mode.autosave_m2k(now=120.0)
    assert json.load(open(slot_file(mode, 0)))["params"][17] == 21.0


def test_leaving_the_browser_saves_the_slot(browser):
    mode, instrument, _, _ = browser
    instrument.osc["client"].send_message("/cc/73", 55.0)
    mode.save_all_presets_to_state()
    assert json.load(open(slot_file(mode, 0)))["params"][17] == 55.0


def test_startup_restores_the_slot(browser):
    mode, instrument, _, _ = browser
    mode.m2k_sounds.write(slot_file(mode, 0), mode.m2k_sounds.resolve("Factory/KICK/BOOM808"))
    mode.restore_m2k_slots()
    assert m2k_state.capture(instrument.osc["client"], mode.m2k_sounds).machine == 15


def test_switching_engines_keeps_and_brings_back_the_mono2k_sound(browser, app):
    mode, instrument, _, tmp_path = browser
    app.preset_selection_mode = mode
    engine_menu = EngineSelectionMode(app, settings=None)
    engine_menu.track_engines_filename = str(tmp_path / "track_engines.json")
    instrument.osc["client"].send_message("/cc/73", 66.0)
    assert engine_menu.select("surge-xt-cli") is True
    assert json.load(open(slot_file(mode, 0)))["params"][17] == 66.0    # kept when leaving mono2k

    instrument.voices["mono2k"].osc["client"].values.clear()           # as if m2k-jack had restarted
    assert engine_menu.select("mono2k") is True
    assert m2k_state.capture(instrument.osc["client"], mode.m2k_sounds).params[17] == 66.0


def test_surge_tracks_are_untouched(app, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("modes.preset_selection_mode.glob", lambda *a, **k: [])
    definition = dict(M2K_INSTRUMENT)
    definition.pop("engine")
    instrument, ports = make_instrument(app, definition=definition)
    app.instruments = {"Pushpin 2": instrument}
    app.instrument_selection_mode.get_all_distinct_instrument_short_names.return_value = ["Pushpin 2"]
    app.instrument_selection_mode.get_current_instrument_short_name.return_value = "Pushpin 2"
    mode = PresetSelectionMode(app, settings=None)
    mode.m2k_state_folder = str(tmp_path / "m2k_state")
    mode.autosave_m2k(now=100.0)
    mode.save_all_presets_to_state()
    assert not os.path.exists(mode.m2k_state_folder)
    ports["Pushpin 2 m2k"].control.assert_not_called()


# ------------------------------------------------- long press opens the browser

import time as _time
from modes import preset_selection_mode as _psm


def press_and_hold(mode, slot, seconds):
    mode.app.steps_held = []
    mode.on_pad_pressed(None, (slot, 0), 100)
    mode.check_for_delayed_actions(now=mode._pad_down_at + seconds)


def test_long_press_opens_the_browser_after_half_a_second(browser):
    mode, _, _, _ = browser
    press_and_hold(mode, 0, _psm.PAD_LONG_PRESS_SECONDS - 0.1)
    assert mode.browser_active is False
    mode.check_for_delayed_actions(now=_time.monotonic() + 1)
    assert mode.browser_active is True


def test_long_press_then_release_without_browsing_keeps_the_slot(browser):
    mode, instrument, _, _ = browser
    instrument.osc["client"].send_message("/cc/73", 44.0)            # an edit to keep
    press_and_hold(mode, 0, 1.0)
    mode.current_address = "Factory/KICK/BOOM808"                     # whatever the browser shows
    mode.on_pad_released(None, (0, 0), 0)
    captured = m2k_state.capture(instrument.osc["client"], mode.m2k_sounds)
    assert captured.machine == 0 and captured.params[17] == 44.0
    assert mode.m2k_presets["Pushpin 2"][0] is None
    assert mode.browser_active is False


def test_long_press_browse_and_release_loads_the_sound(browser):
    mode, instrument, _, _ = browser
    press_and_hold(mode, 0, 1.0)
    mode.on_encoder_rotated(B.ENCODER_TRACK3_ENCODER, 1)
    mode.current_address = "Factory/KICK/BOOM808"
    mode.on_pad_released(None, (0, 0), 0)
    assert m2k_state.capture(instrument.osc["client"], mode.m2k_sounds).machine == 15
    assert mode.m2k_presets["Pushpin 2"][0] == "Factory/KICK/BOOM808"


def test_select_and_pad_still_load_on_release(browser):
    mode, instrument, _, _ = browser
    mode.app.steps_held = []
    mode.on_button_pressed(B.BUTTON_SELECT)
    mode.on_pad_pressed(None, (0, 0), 100)
    assert mode.browser_active is True                                # at once, as before
    mode.current_address = "Factory/KICK/BOOM808"
    mode.on_pad_released(None, (0, 0), 0)
    assert m2k_state.capture(instrument.osc["client"], mode.m2k_sounds).machine == 15


def test_a_short_press_never_opens_the_browser(browser):
    mode, _, _, _ = browser
    mode.app.steps_held = []
    mode.on_pad_pressed(None, (1, 0), 100)
    mode.on_pad_released(None, (1, 0), 0)
    mode.check_for_delayed_actions(now=_time.monotonic() + 10)
    assert mode.browser_active is False


def test_long_press_opens_the_browser_on_surge_tracks_too(app, tmp_path, monkeypatch):
    definition = dict(M2K_INSTRUMENT)
    definition.pop("engine")
    instrument, _ = make_instrument(app, definition=definition)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("modes.preset_selection_mode.glob", lambda *a, **k: [])
    app.instruments = {"Pushpin 2": instrument}
    ism = app.instrument_selection_mode
    ism.get_all_distinct_instrument_short_names.return_value = ["Pushpin 2"]
    ism.get_current_instrument_short_name.return_value = "Pushpin 2"
    ism.selected_instrument = 0
    app.osc_mode.get_current_instrument_devices.return_value = []
    mode = PresetSelectionMode(app, settings=None)
    mode.update_pads = lambda: None
    press_and_hold(mode, 0, 1.0)
    assert mode.browser_active is True
    assert mode.browser_tree() is mode.patches
