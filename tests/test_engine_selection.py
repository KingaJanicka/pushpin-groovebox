"""Switching a track between Surge XT and mono2k (ADD TRACK).

An Instrument owns a voice per available engine; these tests build real
Instruments (MIDI ports mocked, see test_cc_client.make_instrument) and the
EngineSelectionMode that switches them.
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
import push2_python.constants

import engine
from cc_client import MidiCCClient
from modes.engine_selection_mode import (
    EngineSelectionMode,
    load_track_engines,
    save_track_engine,
)
from modes.main_controls_mode import MainControlsMode
from pythonosc.udp_client import SimpleUDPClient
from sequencer.sequencer_metro import SequencerMetro
from tests.test_cc_client import M2K_INSTRUMENT, make_instrument

SURGE = engine.DEFAULT_ENGINE
M2K = engine.MONO2K_ENGINE


def surge_definition():
    d = dict(M2K_INSTRUMENT)
    d.pop("engine")
    return d


# ------------------------------------------------------------------ voices


def test_instrument_has_both_voices_and_starts_on_its_definitions_engine(app):
    instrument, ports = make_instrument(app)
    assert instrument.available_engines() == [SURGE, M2K]
    assert instrument.active_engine_name == M2K
    assert set(ports) == {"Pushpin 2", "Pushpin 2 m2k"}


def test_without_m2k_jack_built_a_track_plays_surge(app):
    instrument, ports = make_instrument(app, m2k_built=False)
    assert instrument.available_engines() == [SURGE]
    assert instrument.active_engine_name == SURGE   # though its definition says mono2k
    assert set(ports) == {"Pushpin 2"}


def test_saved_choice_overrides_the_definition(app):
    instrument, _ = make_instrument(app, initial_engine=SURGE)
    assert instrument.active_engine_name == SURGE
    instrument, _ = make_instrument(app, definition=surge_definition(), initial_engine=M2K)
    assert instrument.active_engine_name == M2K


def test_instrument_attributes_follow_the_active_voice(app):
    instrument, ports = make_instrument(app)
    assert instrument.midi_out_device is ports["Pushpin 2 m2k"]
    assert isinstance(instrument.osc["client"], MidiCCClient)
    assert instrument.engine is instrument.voices[M2K].engine
    assert [d.label for d in instrument.current_devices] == [
        "GND-SIN", "AMP", "FILT", "FX", "DSTR", "LFO 1", "LFO 2", "LFO 3"]
    # the clock and Surge always use the track's own port
    assert instrument.surge_midi_out_device is ports["Pushpin 2"]

    assert instrument.set_active_engine(SURGE) is True
    assert instrument.midi_out_device is ports["Pushpin 2"]
    assert isinstance(instrument.osc["client"], SimpleUDPClient)
    assert instrument.engine is instrument.voices[SURGE].engine
    assert instrument.current_devices == []          # this test gives Surge no pages


# --------------------------------------------------------------- switching


def test_switching_stops_the_old_engines_notes(app):
    instrument, ports = make_instrument(app)
    instrument.set_active_engine(SURGE)
    ports["Pushpin 2 m2k"].control.assert_any_call(123, 0, 2)
    ports["Pushpin 2"].control.reset_mock()
    instrument.set_active_engine(M2K)
    ports["Pushpin 2"].control.assert_any_call(123, 0, 2)


def test_switching_to_the_same_or_a_missing_engine_does_nothing(app):
    instrument, ports = make_instrument(app)
    assert instrument.set_active_engine(M2K) is False
    assert instrument.set_active_engine("moog") is False
    ports["Pushpin 2 m2k"].control.assert_not_called()


def machine_selects(port):
    return [c.args for c in port.control.call_args_list if c.args[0] == 14]


def test_a_voice_is_initialised_on_its_first_use_only(app):
    instrument, ports = make_instrument(app, definition=surge_definition())
    m2k_port = ports["Pushpin 2 m2k"]
    assert machine_selects(m2k_port) == []

    instrument.set_active_engine(M2K)               # first use: its machine and INIT sound
    assert machine_selects(m2k_port) == [(14, 0, 2)]

    instrument.set_active_engine(SURGE)
    instrument.set_active_engine(M2K)               # back again: keeps what was there
    assert machine_selects(m2k_port) == [(14, 0, 2)]


def test_switching_clears_the_tracks_p_locks(app):
    seq = MagicMock()
    app.metro_sequencer_mode.instrument_sequencers = {"Pushpin 2": seq}
    instrument, _ = make_instrument(app)
    instrument.set_active_engine(SURGE)
    seq.clear_all_locks.assert_called_once()


def test_sequencer_clear_all_locks_empties_every_step():
    seq = SequencerMetro.__new__(SequencerMetro)
    seq.locks = [[[1.0, None, 3.0] for _ in range(17)] for _ in range(64)]
    seq.clear_all_locks()
    assert all(v is None for step in seq.locks for device in step for v in device)


def test_patch_commands_always_go_to_surge(app):
    instrument, ports = make_instrument(app)
    surge_client = MagicMock(name="surge client")
    instrument.voices[SURGE].osc["client"] = surge_client
    instrument.send_message("/patch/load", "/some/preset.fxp")
    surge_client.send_message.assert_called_once_with("/patch/load", "/some/preset.fxp")
    instrument.send_message("/cc/72", 10.0)          # the rest goes to the active voice
    assert surge_client.send_message.call_count == 1
    ports["Pushpin 2 m2k"].control.assert_called()


def test_query_slots_asks_every_voice(app):
    instrument, _ = make_instrument(app)
    surge_client = MagicMock(name="surge client")
    instrument.voices[SURGE].osc["client"] = surge_client
    instrument.query_slots()
    asked = [c.args[0] for c in surge_client.send_message.call_args_list]
    assert "/q/param/a/osc/1/type" in asked


def test_surge_slot_echo_while_inactive_updates_surges_slots_only(app):
    instrument, _ = make_instrument(app)
    before = [d.label for d in instrument.current_devices]
    dispatcher = instrument.voices[SURGE].osc["dispatcher"]
    for handler in dispatcher.handlers_for_address("/param/a/osc/1/type"):
        handler.callback("/param/a/osc/1/type", 3.0)
    assert instrument.voices[SURGE].slots[0]["value"] == 3.0
    assert [d.label for d in instrument.current_devices] == before


def test_failed_m2k_routing_drops_the_voice_and_falls_back_to_surge(app):
    instrument, _ = make_instrument(app)
    instrument.voices[SURGE].engine.configure_pipewire = AsyncMock()
    instrument.voices[M2K].engine.configure_pipewire = AsyncMock(side_effect=IndexError("no ports"))
    asyncio.run(instrument.configure_pipewire())
    assert instrument.available_engines() == [SURGE]
    assert instrument.active_engine_name == SURGE


def test_failed_surge_routing_still_raises(app):
    instrument, _ = make_instrument(app)
    instrument.voices[SURGE].engine.configure_pipewire = AsyncMock(side_effect=IndexError("no ports"))
    with pytest.raises(IndexError):
        asyncio.run(instrument.configure_pipewire())


# ------------------------------------------------------------- saved choice


def test_track_engines_round_trip(tmp_path):
    path = str(tmp_path / "track_engines.json")
    assert load_track_engines(path) == {}
    save_track_engine("Pushpin 1", M2K, path)
    save_track_engine("Pushpin 3", SURGE, path)
    assert load_track_engines(path) == {"Pushpin 1": M2K, "Pushpin 3": SURGE}


def test_track_engines_ignores_unknown_engines_and_bad_files(tmp_path):
    path = tmp_path / "track_engines.json"
    path.write_text(json.dumps({"Pushpin 1": "moog", "Pushpin 2": M2K}))
    assert load_track_engines(str(path)) == {"Pushpin 2": M2K}
    path.write_text("{not json")
    assert load_track_engines(str(path)) == {}


# ------------------------------------------------------------------ the menu


@pytest.fixture
def menu(app, tmp_path):
    instrument, ports = make_instrument(app, definition=surge_definition())
    app.instruments = {"Pushpin 2": instrument}
    app.instrument_selection_mode.get_current_instrument_short_name.return_value = "Pushpin 2"
    mode = EngineSelectionMode(app, settings=None)
    mode.track_engines_filename = str(tmp_path / "track_engines.json")
    return mode, instrument, ports


def test_menu_lists_the_engines_with_availability(menu):
    mode, _, _ = menu
    assert mode.options() == [(SURGE, "Surge XT", True), (M2K, "Monomachine", True)]


B = push2_python.constants


def test_menu_opens_on_the_tracks_engine(menu):
    mode, instrument, _ = menu
    mode.activate()
    assert mode.selected_index == 0                  # Surge XT
    instrument.set_active_engine(M2K)
    mode.activate()
    assert mode.selected_index == 1                  # Monomachine


def test_arrows_move_the_highlight_and_stop_at_the_ends(menu):
    mode, instrument, _ = menu
    mode.activate()
    assert mode.on_button_pressed(B.BUTTON_LEFT) is True
    assert mode.selected_index == 0
    assert mode.on_button_pressed(B.BUTTON_RIGHT) is True
    assert mode.selected_index == 1
    mode.on_button_pressed(B.BUTTON_RIGHT)
    assert mode.selected_index == 1
    assert instrument.active_engine_name == SURGE    # moving the highlight changes nothing yet


def test_add_track_switches_to_the_highlighted_engine_saves_and_closes(menu, app):
    mode, instrument, _ = menu
    app.is_mode_active.return_value = True
    mode.activate()
    mode.on_button_pressed(B.BUTTON_RIGHT)
    assert mode.on_button_pressed(B.BUTTON_ADD_TRACK) is True
    assert instrument.active_engine_name == M2K
    assert load_track_engines(mode.track_engines_filename) == {"Pushpin 2": M2K}
    app.add_display_notification.assert_called_with("Pushpin 2: Monomachine")
    assert app.osc_mode.current_device_index_and_page == [0, 0]
    app.toggle_engine_selection_mode.assert_called_once()


def test_add_track_on_the_tracks_own_engine_just_closes(menu, app):
    mode, instrument, _ = menu
    app.is_mode_active.return_value = True
    mode.activate()
    mode.on_button_pressed(B.BUTTON_ADD_TRACK)
    assert instrument.active_engine_name == SURGE
    assert load_track_engines(mode.track_engines_filename) == {}
    app.toggle_engine_selection_mode.assert_called_once()


def test_add_track_on_an_unavailable_engine_explains_and_stays_open(app, tmp_path):
    instrument, _ = make_instrument(app, definition=surge_definition(), m2k_built=False)
    app.instruments = {"Pushpin 2": instrument}
    app.instrument_selection_mode.get_current_instrument_short_name.return_value = "Pushpin 2"
    mode = EngineSelectionMode(app, settings=None)
    mode.track_engines_filename = str(tmp_path / "track_engines.json")
    mode.activate()
    assert mode.options()[1] == (M2K, "Monomachine", False)
    mode.on_button_pressed(B.BUTTON_RIGHT)
    mode.on_button_pressed(B.BUTTON_ADD_TRACK)
    assert instrument.active_engine_name == SURGE
    app.add_display_notification.assert_called_with("Monomachine isn't available (build engines/m2k)")
    app.toggle_engine_selection_mode.assert_not_called()


def test_menu_blocks_encoders_and_passes_other_buttons(menu):
    mode, _, _ = menu
    assert mode.on_encoder_rotated(B.ENCODER_TRACK1_ENCODER, 1) is True
    assert mode.on_button_pressed(B.BUTTON_PLAY) is None
    assert mode.on_button_pressed(B.BUTTON_UPPER_ROW_2) is None   # like ADD DEVICE: arrows, not the upper row


def test_menu_lights_the_arrows_it_can_move(menu, push):
    mode, _, _ = menu
    import definitions
    mode.activate()                                  # on Surge XT, the first
    colors = {c.args[0]: c.args[1] for c in push.buttons.set_button_color.call_args_list}
    assert colors[B.BUTTON_LEFT] == definitions.BLACK
    assert colors[B.BUTTON_RIGHT] == definitions.WHITE
    push.buttons.set_button_color.reset_mock()
    mode.on_button_pressed(B.BUTTON_RIGHT)
    colors = {c.args[0]: c.args[1] for c in push.buttons.set_button_color.call_args_list}
    assert colors[B.BUTTON_LEFT] == definitions.WHITE
    assert colors[B.BUTTON_RIGHT] == definitions.BLACK


def test_menu_draws_the_highlight_yellow(menu):
    from unittest.mock import patch
    import definitions
    mode, _, _ = menu
    mode.activate()
    mode.on_button_pressed(B.BUTTON_RIGHT)
    with patch("modes.engine_selection_mode.show_text") as show:
        mode.update_display(MagicMock(), 960, 160)
    boxes = {c.args[3]: c.kwargs.get("background_color") for c in show.call_args_list if c.kwargs.get("background_color")}
    assert boxes == {"Surge XT": definitions.GRAY_LIGHT, "Monomachine": definitions.YELLOW}


def test_add_track_button_toggles_the_menu(app):
    mode = MainControlsMode(app, settings=None)
    assert mode.on_button_pressed(push2_python.constants.BUTTON_ADD_TRACK) is True
    app.toggle_engine_selection_mode.assert_called_once()


def test_returning_to_a_voice_requeries_its_controls(app):
    instrument, ports = make_instrument(app, definition=surge_definition())
    instrument.init_devices_sync()                    # Surge set up at startup
    surge_client = MagicMock(name="surge client")
    instrument.voices[SURGE].osc["client"] = surge_client
    instrument.set_active_engine(M2K)
    surge_client.reset_mock()
    instrument.set_active_engine(SURGE)
    asked = [c.args[0] for c in surge_client.send_message.call_args_list]
    assert "/q/param/a/osc/1/type" in asked


def test_preset_refresh_leaves_a_mono2k_tracks_pages_alone(app):
    from modes.preset_selection_mode import PresetSelectionMode
    instrument, ports = make_instrument(app)          # playing mono2k
    app.instruments = {"Pushpin 2": instrument}
    mode = PresetSelectionMode.__new__(PresetSelectionMode)
    mode.app = app
    before = len(ports["Pushpin 2 m2k"].control.call_args_list)
    asyncio.run(mode._refresh_devices_after_preset_load("Pushpin 2"))
    assert len(ports["Pushpin 2 m2k"].control.call_args_list) == before   # no machine INIT resent


# ------------------------------------------------- mono2k's page layout


def test_mono2k_devices_each_have_their_own_slot(app):
    instrument, _ = make_instrument(app)
    slots = [d.slot for slot in instrument.devices for d in slot if d.slot != 0]
    assert sorted(slots) == [1, 2, 3, 4, 5, 6, 7]                # FX and DSTR no longer share one
    assert [d.label for d in instrument.devices[3]] == ["FX"]
    assert [d.label for d in instrument.devices[4]] == ["DSTR"]


def test_surge_keeps_slots_2_to_4_always_shown(app):
    instrument, _ = make_instrument(app, initial_engine=SURGE)
    assert instrument.engine.always_shown_slots == (2, 3, 4)
    assert instrument.voices[M2K].engine.always_shown_slots == (1, 2, 3, 4, 5, 6, 7)


def test_p_locks_on_mono2k_fx_dont_play_on_dstr(app):
    """A lock on FX's first control (slot 3) must not reach DSTR's first (slot 4)."""
    from sequencer.sequencer_metro import SequencerMetro

    instrument, _ = make_instrument(app)
    app.instruments = {"Pushpin 2": instrument}
    sent = []
    app.send_osc = lambda address, value, name: sent.append((address, value))
    seq = SequencerMetro.__new__(SequencerMetro)
    seq.app = app
    seq.name = "Pushpin 2"
    seq.locks = [[[None] * 18 for _ in range(17)] for _ in range(64)]
    seq.lock_scale = [7] * 64
    seq.step_index = 0
    seq.gate = ["Off"] * 64
    seq.controls_to_reset = []
    seq.params = MagicMock(gate_track_active=False)
    seq.locks[0][3][0] = 99.0                                   # FX page, first control (EQF, CC 80)
    seq.evaluate_and_play_notes()
    assert sent == [("/cc/80", 99.0)]


def test_right_arrow_stays_on_page_1_without_a_modulation_page(app):
    from modes.osc_mode import OSCMode
    instrument, _ = make_instrument(app)
    mode = OSCMode.__new__(OSCMode)
    mode.app = app
    mode.instrument_page = 0
    mode.get_current_instrument = lambda: instrument
    mode.query_all_instrument_page_params = lambda: None
    app.is_mode_active.return_value = False
    mode.update_current_instrument_page(new_instrument_page=1)
    assert mode.instrument_page == 0
