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
        "Gnd-Sin", "Amp", "Filt", "FX", "Dstr", "LFO 1", "LFO 2", "LFO 3"]
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
    assert [d.label for d in instrument.devices[4]] == ["Dstr"]


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


# --------------------------------------------- the DSTR page: MOD effect


def test_dstr_page_is_bits_fold_xor_verb_then_the_mod_effect(app):
    instrument, _ = make_instrument(app)
    dstr = next(d for d in instrument.current_devices if d.label == "Dstr")
    labels = [getattr(c, "menu_label", None) or c.label for c in dstr.controls]
    assert labels == ["Bit Depth", "Wavefold", "XOR Mangle", "Reverb Send", "Mod Type", "Mod Rate", "Mod Depth",
                      "Mod Mix"]
    menu = dstr.controls[4]
    assert [(i.label, i.address, i.value, i.range) for i in menu.items] == [
        ("Chor", "/m2k/param/66", 21, [0, 42]), ("Flng", "/m2k/param/66", 64, [43, 85]),
        ("Phas", "/m2k/param/66", 107, [86, 127])]
    assert [c.address for c in dstr.controls[5:]] == ["/m2k/param/67", "/m2k/param/68", "/m2k/param/69"]


def test_mod_type_menu_moves_an_item_every_4_clicks_and_sends_nrpn(app):
    instrument, ports = make_instrument(app)
    port = ports["Pushpin 2 m2k"]
    dstr = next(d for d in instrument.current_devices if d.label == "Dstr")
    menu = dstr.controls[4]
    port.control.reset_mock()
    for _ in range(3):
        menu.update_value(1)
    port.control.assert_not_called()                          # still on the same item
    menu.update_value(1)
    sent = [c.args for c in port.control.call_args_list]
    assert sent[:4] == [(99, 1, 2), (98, 66, 2), (6, 64, 2), (38, 0, 2)]   # FLNG, NRPN 1:66


def test_machine_init_sets_the_mod_menu_from_its_value(app):
    instrument, _ = make_instrument(app)
    dstr = next(d for d in instrument.current_devices if d.label == "Dstr")
    instrument.osc["client"].send_message("/m2k/param/66", 106.0)   # as a machine's INIT or a loaded sound does
    assert dstr.controls[4].get_active_menu_item().label == "Phas"


def test_menu_p_locks_play_the_items_message():
    from types import SimpleNamespace
    from sequencer.sequencer_metro import lock_message
    item = lambda v: SimpleNamespace(address="/m2k/param/66", value=v)
    menu = SimpleNamespace(address="/m2k/param/66", items=[item(21), item(64), item(106)])
    assert lock_message(menu, 1.2) == ("/m2k/param/66", 64.0)       # a lock is an item position
    assert lock_message(menu, 9) == ("/m2k/param/66", 106.0)        # clamped
    rng = SimpleNamespace(address="/cc/72", value=0)
    assert lock_message(rng, 33.5) == ("/cc/72", 33.5)


def test_menu_step_is_optional():
    from osc_controls import OSCControlMenu
    items = [{"$type": "menu-item", "label": str(i), "onselect": {"address": "/x", "value": i}} for i in range(3)]
    slow = OSCControlMenu({"$type": "control-menu", "items": items})
    slow.update_value(1)
    assert slow.value < 0.1                                        # 3/127 of an item, as before
    fast = OSCControlMenu({"$type": "control-menu", "items": items, "step": 0.5})
    fast.update_value(1)
    fast.update_value(1)
    assert fast.get_active_menu_item().label == "1"


# ------------------------------------------- the LFO pages: DEST as menus


def lfo_page(instrument, label="LFO 2"):
    return next(d for d in instrument.current_devices if d.label == label)


def test_lfo_page_starts_with_device_and_destination(app):
    instrument, _ = make_instrument(app)
    visible = lfo_page(instrument).get_visible_controls()
    assert len(visible) == 8
    assert visible[0].name == "Switch" and visible[1].name == "Menu"
    assert [getattr(c, "menu_label", None) or c.label for c in visible[2:]] == [
        "LFO Wave", "LFO Trig Mode", "LFO Multiplier", "LFO Cycle", "Start Phase", "LFO Depth"]
    assert [g.label for g in visible[0].groups] == [
        "Off", "Syn", "Amp", "Filt", "FX", "Dstr", "LFO 1", "LFO 2", "LFO 3"]
    assert visible[0].menu_label == "Device"


def nrpn_values(port, lsb):
    calls = [c.args for c in port.control.call_args_list]
    return [calls[i + 2][1] for i in range(len(calls) - 3)
            if calls[i][:2] == (99, 0) and calls[i + 1][:2] == (98, lsb)]


def test_picking_a_device_then_a_parameter_sets_dest(app):
    instrument, ports = make_instrument(app)
    app.metro_sequencer_mode.disable_controls = False                # (encoders reach the page)
    port = ports["Pushpin 2 m2k"]
    page = lfo_page(instrument)
    switch = page.get_visible_controls()[0]
    port.control.reset_mock()
    for _ in range(4):
        page.on_encoder_rotated(B.ENCODER_TRACK1_ENCODER, 1)        # OFF -> SYN
    assert switch.get_active_group().label == "Syn"
    assert nrpn_values(port, 105) == [1]                            # SYN A: parameter 0, DEST 1
    for _ in range(4):
        page.on_encoder_rotated(B.ENCODER_TRACK2_ENCODER, 1)        # SYN A -> SYN B
    assert nrpn_values(port, 105) == [1, 2]
    assert page.get_visible_controls()[1].get_active_menu_item().label == "Sub Level"   # GND-SIN's SYN B


def test_a_dest_value_coming_back_selects_its_device_and_parameter(app):
    instrument, _ = make_instrument(app)
    page = lfo_page(instrument)
    instrument.osc["client"].send_message("/cc/105", 19.0)          # FILT HPQ (parameter 18) + 1
    visible = page.get_visible_controls()
    assert visible[0].get_active_group().label == "Filt"
    assert visible[1].get_active_menu_item().label == "HP Resonance"
    instrument.osc["client"].send_message("/cc/105", 0.0)
    assert page.get_visible_controls()[0].get_active_group().label == "Off"


def test_switch_set_state_takes_a_value_without_a_label():
    from osc_controls import OSCControlSwitch
    from pythonosc.dispatcher import Dispatcher
    item = lambda v: {"$type": "menu-item", "label": str(v), "onselect": {"address": "/x", "value": v}}
    group = lambda label, values: {"$type": "group", "label": label, "controls": [
        {"$type": "control-menu", "items": [item(v) for v in values]}]}
    plain = OSCControlSwitch({"$type": "control-switch", "groups": [group("a", [0, 1]), group("b", [2, 3])]},
                             dispatcher=Dispatcher())
    plain.set_state("/x", 3.0)                                       # no label: no error
    assert plain.get_active_group().label == "a"                     # legacy: only first items move it
    plain.set_state("/x", 2.0, "label")
    assert plain.get_active_group().label == "b"
    by_value = OSCControlSwitch({"$type": "control-switch", "select_by_value": True,
                                 "groups": [group("a", [0, 1]), group("b", [2, 3])]}, dispatcher=Dispatcher())
    by_value.set_state("/x", 3.0)
    assert by_value.get_active_group().label == "b"


def test_lfo_device_switch_shows_the_device_a_value_selected(app):
    instrument, _ = make_instrument(app)
    page = lfo_page(instrument)
    instrument.osc["client"].send_message("/cc/105", 19.0)
    assert page.get_visible_controls()[0].knob_value == 3.0             # FILT, as drawn


# -------------------------------------------- p-locks let go after their step

from unittest.mock import patch as _patch


def sequencer_for(app, instrument):
    from sequencer.sequencer_metro import SequencerMetro
    seq = SequencerMetro.__new__(SequencerMetro)
    seq.app = app
    seq.name = instrument.name
    seq.locks = [[[None] * 18 for _ in range(17)] for _ in range(64)]
    seq.lock_scale = [7] * 64
    seq.gate = ["On"] * 64
    seq.controls_to_reset = []
    seq.params = MagicMock(gate_track_active=True, gate_len=1)
    seq.pitch, seq.octave, seq.velocity, seq.mutes_skips = [0] * 64, [0] * 64, [1] * 64, [False] * 64
    seq.next_step_index = 1
    seq.timeline = MagicMock()
    return seq


def play_step(seq, step):
    seq.step_index, seq.next_step_index = step, step + 1
    with _patch("sequencer.sequencer_metro.random.randint", return_value=1):   # (the note always plays)
        seq.evaluate_and_play_notes()


def test_a_p_lock_lets_go_after_its_step(app):
    instrument, _ = make_instrument(app)
    app.instruments = {instrument.name: instrument}
    sent = []

    def send_osc(address, value, name):
        sent.append((address, value))
        instrument.send_message(address, value)                     # (and its echo, as the app does)
    app.send_osc = send_osc
    base = next(d for d in instrument.current_devices if d.label == "Filt").controls[0]
    instrument.osc["client"].send_message("/cc/72", 10.0)           # the knob's own value
    seq = sequencer_for(app, instrument)
    seq.locks[0][2][0] = 99.0                                       # step 0: FILT BASE locked
    seq.locks[1][2][0] = 50.0                                       # step 1: locked again
    play_step(seq, 0)
    assert sent == [("/cc/72", 99.0)]
    sent.clear()
    play_step(seq, 1)
    assert sent == [("/cc/72", 10.0), ("/cc/72", 50.0)]             # back to 10, then the next lock
    sent.clear()
    play_step(seq, 2)
    assert sent == [("/cc/72", 10.0)]                               # and back to its own value
    assert base.value == 10.0


def test_a_scaled_lock_is_measured_from_the_knobs_value(app):
    instrument, _ = make_instrument(app)
    app.instruments = {instrument.name: instrument}
    sent = []
    app.send_osc = lambda address, value, name: (sent.append((address, value)), instrument.send_message(address, value))
    instrument.osc["client"].send_message("/cc/72", 10.0)
    seq = sequencer_for(app, instrument)
    seq.lock_scale = [7] * 64
    seq.lock_scale[1] = 3.5                                          # half way
    seq.locks[0][2][0] = 90.0
    seq.locks[1][2][0] = 90.0
    play_step(seq, 0)
    seq.controls_to_reset_before = list(seq.controls_to_reset)
    seq.params.gate_track_active = False                             # no note on step 1: nothing undone
    sent.clear()
    play_step(seq, 1)
    assert sent == [("/cc/72", 50.0)]                                # 10 + (90 - 10) / 2, not from 90


def test_turning_the_device_switch_past_its_ends_stays_on_them(app):
    """Turning past LFO 3 put the switch one past its last group and drawing it crashed the app."""
    instrument, _ = make_instrument(app)
    app.metro_sequencer_mode.disable_controls = False
    app.steps_held = []
    page = lfo_page(instrument)
    switch = page.get_visible_controls()[0]
    for _ in range(200):
        page.on_encoder_rotated(B.ENCODER_TRACK1_ENCODER, 1)
    assert switch.get_active_group().label == "LFO 3"
    assert switch.value == switch.knob_value == len(switch.groups) - 1
    with _patch("osc_controls.show_text"):
        page.draw(MagicMock())                                       # no IndexError
    for _ in range(200):
        page.on_encoder_rotated(B.ENCODER_TRACK1_ENCODER, -1)
    assert switch.get_active_group().label == "Off" and switch.value == 0.0


def test_switch_draw_survives_an_out_of_range_lock_value():
    from osc_controls import OSCControlSwitch
    from pythonosc.dispatcher import Dispatcher
    groups = [{"$type": "group", "label": l, "controls": []} for l in ("a", "b")]
    switch = OSCControlSwitch({"$type": "control-switch", "groups": groups}, dispatcher=Dispatcher())
    with _patch("osc_controls.show_text"):
        switch.draw(MagicMock(), 0, draw_lock=True, lock_value=7)
        switch.knob_value = 5
        switch.draw(MagicMock(), 0)



def test_syn_destinations_name_the_current_machines_controls(app):
    instrument, _ = make_instrument(app)
    syn = next(g for g in lfo_page(instrument).get_visible_controls()[0].groups if g.label == "Syn")
    labels = lambda: [i.label for i in syn.controls[0].items]
    assert labels() == ["Sine Fold", "Sub Level", "Noise", "Pitch Drop", "Drop Time", "Click", "2nd Harmonic",
                        "Tune"]                                         # GND-SIN
    kick = next(d for d in instrument.devices[0] if d.label == "Drm-Kick")
    kick.select_sync()
    assert labels() == ["Carrier Wave", "Pitch Sweep", "Sweep Time", "Sweep Curve", "FM Depth", "FM Pitch", "Snap",
                        "Click"]
    perc = next(d for d in instrument.devices[0] if d.label == "Gnd-Perc")
    perc.select_sync()
    assert labels()[-1] == "-"                                       # its SYN H is unused


def test_menu_item_label_falls_back_without_a_source():
    from osc_controls import OSCMenuItem
    item = OSCMenuItem({"$type": "menu-item", "label": "SYN A", "onselect": {"address": "/x", "value": 1}})
    assert item.label == "SYN A"
    item.label_func = lambda: None
    assert item.label == "SYN A"
    item.label_func = lambda: "WAVE"
    assert item.label == "WAVE"


def test_lfo_depth_is_bipolar_and_shown_signed(app):
    """In MONO2K's own words: its swing against full, in %."""
    instrument, _ = make_instrument(app)
    dpth = lfo_page(instrument).get_visible_controls()[-1]
    assert dpth.label == "LFO Depth" and dpth.bipolar
    assert [dpth.display_text(v) for v in (64, 96, 0, 64.5)] == ["0 %", "+25 %", "-100 %", "0 %"]
    amp_vol = next(d for d in instrument.current_devices if d.label == "Amp").controls[5]
    assert amp_vol.display_text(64) == "64"                          # other controls unchanged


def test_titled_switch_draws_level_with_menus():
    from osc_controls import OSCControlSwitch
    from pythonosc.dispatcher import Dispatcher
    groups = [{"$type": "group", "label": l, "controls": []} for l in ("a", "b", "c")]
    plain = OSCControlSwitch({"$type": "control-switch", "groups": groups}, dispatcher=Dispatcher())
    titled = OSCControlSwitch({"$type": "control-switch", "menu_label": "DEVICE", "groups": groups},
                              dispatcher=Dispatcher())
    tops = {}
    for name, sw in (("plain", plain), ("titled", titled)):
        sw.knob_value = 1
        with _patch("osc_controls.show_text") as show:
            sw.draw(MagicMock(), 0)
        tops[name] = {c.args[3]: c.args[2] for c in show.call_args_list}
    assert tops["plain"] == {"a": 30, "b": 45, "c": 70}               # Surge's, as before
    assert tops["titled"] == {"DEVICE": 25, "a": 55, "b": 70, "c": 95} # a titled menu's rows


# ------------------------------- second pages: PTCH, BANK, TRCK; arp and LEVL

import json as _json
import os as _os


def machine_page(instrument, name):
    return next(d for d in instrument.devices[0] if d.label == name)


def test_machine_pages_have_ptch_on_their_second_page(app):
    instrument, _ = make_instrument(app)
    sine = machine_page(instrument, "Gnd-Sin")
    assert len(sine.pages) == 2
    second = sine.pages[1]
    assert second[0].__class__.__name__ == "ControlSpacer" and second[1].label == "Track Pitch"
    assert second[1].address == "/cc/20" and second[1].bipolar and second[1].display_text(70) == "6 Semi"


def test_only_digi_wav_has_bank(app):
    instrument, _ = make_instrument(app)
    second = machine_page(instrument, "Digi-Wav").pages[1]
    bank = second[0]
    assert bank.menu_label == "Wave Bank"
    assert [(i.label, i.address, i.value) for i in bank.items] == [
        ("M2K", "/m2k/param/70", 32), ("M64", "/m2k/param/70", 96)]
    assert second[1].label == "Track Pitch"
    others = [d for d in instrument.devices[0] if d.label != "Digi-Wav"]
    assert all(not hasattr(d.pages[1][0], "items") for d in others)


def test_lfo_trck_is_on_the_lfos_second_page(app):
    instrument, ports = make_instrument(app)
    lfo = lfo_page(instrument, "LFO 1")
    trck = lfo.pages[1][0]
    assert trck.menu_label == "LFO Track"
    assert [(i.label, i.value) for i in trck.items] == [("Own", 0)] + [(f"Trk {n}", n) for n in range(1, 9)]
    assert all(i.address == "/cc/88" for i in trck.items)


def test_machine_inits_aim_lfos_at_their_own_track_and_keep_the_arp_off():
    from tests.test_cc_client import M2K_DIR
    for name in sorted(_os.listdir(M2K_DIR)):
        if not name.startswith("00_machine_"):
            continue
        init = {m["address"]: m["value"] for m in _json.load(open(_os.path.join(M2K_DIR, name)))["init"]}
        assert init["/cc/88"] == init["/cc/104"] == init["/cc/112"] == 0, name    # OWN, not track 1
        assert init["/m2k/param/38"] == 0, name                                    # arp OFF


def test_sounds_aim_lfos_at_their_own_track_and_keep_the_arp_off():
    from m2k_state import M2KSounds
    sounds = M2KSounds.load()
    for kit in [m["kit"] for m in sounds.machines] + [s["kit"] for s in sounds.library]:
        assert kit[42] == kit[50] == kit[58] == 0 and kit[38] == 0


def test_level_is_always_set_on_init_and_on_load():
    """LEVL isn't on a page: every machine's init and every sound must set it."""
    from m2k_state import M2KSounds, apply
    from tests.test_cc_client import M2K_DIR
    for name in sorted(_os.listdir(M2K_DIR)):
        if name.startswith("00_machine_"):
            init = {m["address"]: m["value"] for m in _json.load(open(_os.path.join(M2K_DIR, name)))["init"]}
            assert 64 <= init["/cc/7"] <= 127, name
    sounds = M2KSounds.load()
    assert all(s["kit"][37] > 0 for s in sounds.library)
    client = MagicMock()
    apply(sounds.resolve("Factory/KICK/BOOM808"), client, sounds)
    assert any(c.args[0] == "/cc/7" for c in client.send_message.call_args_list)


# ------------------------------------------- MONO2K's own words for values (menus, labelled knobs)

def menu_labels(menu):
    return [i.label for i in menu.items]


def test_choices_are_menus_in_mono2ks_own_words(app):
    instrument, _ = make_instrument(app)
    lfo = lfo_page(instrument, "LFO 1")
    wave, trig, mult = lfo.controls[1:4]
    assert (wave.menu_label, menu_labels(wave)) == ("LFO Wave", ["Tri", "Sin", "Sqr", "Saw", "Exp", "Rmp", "Rnd"])
    assert menu_labels(trig) == ["Free", "Trig", "Hold", "One", "Half"]
    assert menu_labels(mult) == ["X1", "X2", "X4", "X8", "X16", "X32", "X64", "X128"]
    assert menu_labels(machine_page(instrument, "Drm-Kick").controls[0]) == ["Sin", "Tri", "Saw", "Sqr"]
    assert menu_labels(machine_page(instrument, "SID-6581").controls[3]) == ["Tri", "Saw", "Puls", "Mix", "Nois"]
    ratios = menu_labels(machine_page(instrument, "FM+Stat").controls[0])
    assert len(ratios) == 24 and ratios[0] == "1/64" and "Ratio" not in " ".join(ratios)
    bits = next(d for d in instrument.current_devices if d.label == "Dstr").controls[0]
    assert bits.menu_label == "Bit Depth" and bits.items[0].label == "16 Bit" and len(bits.items) == 14


def test_a_value_from_a_sound_shows_the_item_whose_range_holds_it(app):
    instrument, _ = make_instrument(app)
    client = instrument.osc["client"]
    wave = lfo_page(instrument, "LFO 1").controls[1]
    for value, label in ((0, "Tri"), (18, "Tri"), (19, "Sin"), (36.9, "Sin"), (37.2, "Sqr"), (127, "Rnd")):
        client.send_message("/cc/90", float(value))
        assert wave.get_active_menu_item().label == label, value


def test_turning_a_menu_sends_its_items_value(app):
    instrument, ports = make_instrument(app)
    wave = lfo_page(instrument, "LFO 1").controls[1]
    client = instrument.osc["client"]
    client.send_message("/cc/90", 0.0)
    for _ in range(4):                                                # four clicks an item
        wave.update_value(1)
    assert wave.get_active_menu_item().label == "Sin"
    assert client.values["/cc/90"] == wave.get_active_menu_item().value


def test_quantities_show_mono2ks_words_and_center_them(app):
    instrument, _ = make_instrument(app)
    fx = next(d for d in instrument.current_devices if d.label == "FX")
    srr, dtim = fx.controls[2], fx.controls[3]
    assert srr.display_text(0) == "Off" and srr.display_text(16).endswith("kHz")
    assert dtim.display_text(0) == "Comb" and dtim.display_text(16) == "1/16 Note" and dtim.display_text(37) == "37/256"
    assert srr.has_value_labels
    vol = next(d for d in instrument.current_devices if d.label == "Amp").controls[5]
    assert not vol.has_value_labels and vol.display_text(64) == "64"     # plain numbers stay numbers


def test_digi_wav_waves_follow_its_bank(app):
    instrument, _ = make_instrument(app)
    wave = machine_page(instrument, "Digi-Wav").controls[0]
    client = instrument.osc["client"]
    client.send_message("/m2k/param/70", 0.0)                         # M2K: MONO2K's 32
    m2k = [wave.display_text(v) for v in range(0, 128, 4)]
    client.send_message("/m2k/param/70", 127.0)                       # M64: the owner's 64
    m64 = [wave.display_text(v) for v in range(0, 128, 2)]
    assert len(set(m2k)) == 32 and len(set(m64)) == 64 and m2k != m64[:32]


def test_lfo_speed_reads_with_its_own_mult(app):
    instrument, _ = make_instrument(app)
    lfo = lfo_page(instrument, "LFO 2")
    spd = lfo.controls[4]
    client = instrument.osc["client"]
    client.send_message("/cc/108", 0.0)                               # LFO 2's MULT X1
    slow = spd.display_text(64)
    client.send_message("/cc/108", 127.0)                             # X128
    assert spd.display_text(64) != slow and spd.display_text(0).startswith("Stop")


# ------------------------------------------------------------- mono2k's clock

def test_the_clock_goes_to_one_mono2k_port_the_first_tracks(app):
    from modes.instrument import mono2k_clock_port
    first, ports = make_instrument(app)
    surge_only = MagicMock(voices={"surge-xt-cli": MagicMock()})
    assert mono2k_clock_port({"Pushpin 1": surge_only, "Pushpin 2": first}) is ports["Pushpin 2 m2k"]
    assert mono2k_clock_port({"Pushpin 1": surge_only}) is None


def test_fm_envelope_amounts_are_bipolar(app):
    """MONO2K counts them about 64: below it the depth falls, above it rises (DEPTH / DECAY)."""
    instrument, _ = make_instrument(app)
    for machine, labels in (("FM+Stat", ["Depth / Decay 1"]), ("FM+Dyn", ["Depth / Decay 2"]),
                            ("FM+Par", ["Depth / Decay 1", "Depth / Decay 2", "Depth / Decay 3"])):
        controls = {c.label: c for c in machine_page(instrument, machine).controls if hasattr(c, "bipolar")}
        assert all(controls[label].bipolar for label in labels), machine
    assert machine_page(instrument, "FM+Stat").controls[1].bipolar            # 1FIN: a fine tune, about 0 too


# ------------------------------- full names, and units MONO2K's screen leaves out


def test_controls_are_named_in_full(app):
    instrument, _ = make_instrument(app)
    amp = next(d for d in instrument.current_devices if d.label == "Amp")
    assert [c.label for c in amp.controls[:8]] == [
        "Attack", "Hold", "Decay", "Release", "Distortion", "Volume", "Pan", "Portamento"]


def test_hold_is_a_fraction_of_a_note_like_delay_time(app):
    instrument, _ = make_instrument(app)
    hold = next(d for d in instrument.current_devices if d.label == "Amp").controls[1]
    assert hold.has_value_labels
    # v / 32 beat = v / 128 note, simplified as DELAY TIME's 256ths are
    assert [hold.display_text(v) for v in (0, 1, 2, 4, 8, 32, 48, 64, 96, 126, 127)] == [
        "0", "1/128", "1/64 Note", "1/32 Note", "1/16 Note", "1/4 Note", "3/8 Note", "1/2 Note",
        "3/4 Note", "63/64 Note", "Inf"]


def test_filter_envelope_amounts_are_in_octaves_and_lfo_phase_in_degrees(app):
    instrument, _ = make_instrument(app)
    filt = next(d for d in instrument.current_devices if d.label == "Filt")
    base_by_env = filt.controls[6]
    assert base_by_env.label == "Base By Env" and base_by_env.bipolar
    assert [base_by_env.display_text(v) for v in (64, 72, 0, 127)] == ["0 Oct", "+0.2 Oct", "-14 Oct", "+14 Oct"]
    phase = next(c for c in lfo_page(instrument).controls if getattr(c, "label", None) == "Start Phase")
    assert [phase.display_text(v) for v in (0, 32, 64, 127)] == ["0°", "90°", "180°", "357°"]


def test_a_label_wider_than_its_column_shrinks_to_fit():
    from user_interface.display_utils import MIN_FONT_SIZE, fitted_font_size
    ctx = MagicMock()
    ctx.text_extents.side_effect = lambda line: (0, 0, len(line) * 10, 0, 0, 0)   # 10 px a letter at 16
    assert fitted_font_size(ctx, ["Hold"], 16, 114) == 16                          # fits: unchanged
    assert fitted_font_size(ctx, ["LFO Destination"], 16, 114) == 12              # 150 px -> 114
    assert fitted_font_size(ctx, ["X" * 100], 16, 114) == MIN_FONT_SIZE
    assert fitted_font_size(MagicMock(), ["anything"], 16, 114) == 16             # a mocked context


# ------------------------------- trig types: whether a note restarts the amp, the filter, the LFOs


def flat_slots(device):
    return [c for page in device.pages for c in page]


@pytest.mark.parametrize("page, label, cc", [
    ("Amp", "Amp Trig", 21), ("Filt", "Filter Trig", 22),
    ("LFO 1", "LFO Trig", 23), ("LFO 2", "LFO Trig", 23), ("LFO 3", "LFO Trig", 23)])
def test_amp_filter_and_lfo_pages_end_on_their_trig_switch(app, page, label, cc):
    instrument, _ = make_instrument(app)
    device = next(d for d in instrument.current_devices if d.label == page)
    slots = flat_slots(device)
    assert len(slots) == 16
    trig = slots[15]                                                  # the second page's last control
    assert trig.menu_label == label
    assert [(i.label, i.address, i.value) for i in trig.items] == [
        (f"{label} On", f"/cc/{cc}", 0), (f"{label} Off", f"/cc/{cc}", 127)]
    assert trig.get_active_menu_item().label == f"{label} On"        # notes trig it until told otherwise


def test_trig_switches_go_out_as_plain_ccs(app):
    instrument, ports = make_instrument(app)
    port = ports["Pushpin 2 m2k"]
    amp_trig = flat_slots(next(d for d in instrument.current_devices if d.label == "Amp"))[15]
    port.control.reset_mock()
    for _ in range(4):
        amp_trig.update_value(1)                                      # On -> Off
    assert amp_trig.get_active_menu_item().label == "Amp Trig Off"
    assert [c.args[:2] for c in port.control.call_args_list] == [(21, 127)]   # no NRPN: a switch


def test_a_locked_trig_switch_lets_go_after_its_step(app):
    instrument, _ = make_instrument(app)
    app.instruments = {instrument.name: instrument}
    sent = []
    app.send_osc = lambda address, value, name: (sent.append((address, value)), instrument.send_message(address, value))
    amp = next(d for d in instrument.current_devices if d.label == "Amp")
    slot = amp.slot if hasattr(amp, "slot") else 1
    seq = sequencer_for(app, instrument)
    seq.locks[0][slot][15] = 127.0                                    # step 0: a trigless amp
    play_step(seq, 0)
    assert ("/cc/21", 127.0) in sent
    sent.clear()
    play_step(seq, 1)
    assert sent == [("/cc/21", 0.0)]                                  # the next step trigs it again
