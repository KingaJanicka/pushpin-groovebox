"""Tests for the MIDI CC transport used by mono2k tracks (``cc_client.py``) and
its wiring into instruments, device pages and the generated m2k definitions."""

import importlib.util
import json
import os
from glob import glob
from unittest.mock import MagicMock, patch

import pytest
from pythonosc.dispatcher import Dispatcher

import definitions
import engine
from cc_client import MidiCCClient, cc_number, cc_value, nrpn_value
from modes.osc_device import OSCDevice
from modes.osc_mode import OSCMode, load_device_definitions
from osc_controls import OSCControl

M2K_DIR = definitions.M2K_DEFINITION_FOLDER


# ------------------------------------------------------------------- helpers


def test_cc_number_parses_only_cc_addresses():
    assert cc_number("/cc/0") == 0
    assert cc_number("/cc/72") == 72
    assert cc_number("/cc/127") == 127
    assert cc_number("/cc/128") is None
    assert cc_number("/q/cc/72") is None
    assert cc_number("/param/a/osc/1/pitch") is None
    assert cc_number("/cc/72/x") is None


@pytest.mark.parametrize("value, expected", [(0.0, 0), (63.4, 63), (63.6, 64), (-5, 0), (200.0, 127), (127, 127)])
def test_cc_value_rounds_and_clamps(value, expected):
    assert cc_value(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [(0.0, (0, 0)), (10.5, (10, 64)), (10.25, (10, 32)), (63.999, (64, 0)), (126.9, (126, 115)),
     (127.0, (127, 0)), (200, (127, 0)), (-3, (0, 0))],
)
def test_nrpn_value_splits_whole_and_fraction(value, expected):
    assert nrpn_value(value) == expected


# -------------------------------------------------------------------- client


@pytest.fixture
def midi_out():
    return MagicMock(name="midi_out")


@pytest.fixture
def dispatcher():
    return Dispatcher()


@pytest.fixture
def client(midi_out, dispatcher):
    return MidiCCClient(midi_out, dispatcher, channel=3)


def test_send_sends_control_change_on_channel(client, midi_out):
    client.send_message("/cc/72", 40.6)
    midi_out.control.assert_called_once_with(72, 41, 3)


def test_send_echoes_to_mapped_handlers(client, dispatcher):
    seen = []
    dispatcher.map("/cc/72", lambda address, value: seen.append((address, value)))
    client.send_message("/cc/72", 40.5)
    assert seen == [("/cc/72", 40.5)]


def test_echo_passes_mapped_args(client, dispatcher):
    seen = []
    dispatcher.map("/cc/7", lambda address, args, value: seen.append((address, args, value)), "extra")
    client.send_message("/cc/7", 100)
    assert seen == [("/cc/7", ["extra"], 100.0)]


def test_query_replays_last_value(client, dispatcher, midi_out):
    client.send_message("/cc/56", 12)
    seen = []
    dispatcher.map("/cc/56", lambda address, value: seen.append(value))
    client.send_message("/q/cc/56", None)
    assert seen == [12.0]
    assert midi_out.control.call_count == 1  # a query sends nothing to the synth


def test_query_for_unsent_cc_is_silent(client, dispatcher):
    seen = []
    dispatcher.map("/cc/56", lambda address, value: seen.append(value))
    client.send_message("/q/cc/56", None)
    assert seen == []


def test_surge_addresses_are_ignored(client, midi_out):
    client.send_message("/patch/load", "/some/patch.fxp")
    client.send_message("/q/param/a/osc/1/type", None)
    client.send_message("/param/a/amp/gain", 0.5)
    midi_out.control.assert_not_called()


def test_none_value_sends_nothing(client, midi_out):
    client.send_message("/cc/72", None)
    midi_out.control.assert_not_called()


def test_failing_handler_does_not_break_the_send(client, dispatcher, midi_out):
    def boom(*args):
        raise RuntimeError("bad handler")

    dispatcher.map("/cc/72", boom)
    client.send_message("/cc/72", 10)
    midi_out.control.assert_called_once_with(72, 10, 3)


def test_channel_is_clamped(midi_out, dispatcher):
    MidiCCClient(midi_out, dispatcher, channel=-1).send_message("/cc/1", 1)
    MidiCCClient(midi_out, dispatcher, channel=99).send_message("/cc/1", 1)
    assert [c.args[2] for c in midi_out.control.call_args_list] == [0, 15]


def nrpn_client(midi_out, dispatcher):
    return MidiCCClient(midi_out, dispatcher, channel=1, nrpn=True, plain_ccs={14})


def test_nrpn_sends_parameter_and_14_bit_value(midi_out, dispatcher):
    nrpn_client(midi_out, dispatcher).send_message("/cc/73", 40.5)
    assert [c.args for c in midi_out.control.call_args_list] == [(99, 0, 1), (98, 73, 1), (6, 40, 1), (38, 64, 1)]


def test_nrpn_reselects_the_parameter_every_time(midi_out, dispatcher):
    client = nrpn_client(midi_out, dispatcher)
    client.send_message("/cc/73", 1)
    client.send_message("/cc/73", 2)
    assert [c.args[0] for c in midi_out.control.call_args_list] == [99, 98, 6, 38, 99, 98, 6, 38]


def test_nrpn_keeps_plain_ccs_plain(midi_out, dispatcher):
    nrpn_client(midi_out, dispatcher).send_message("/cc/14", 5)
    midi_out.control.assert_called_once_with(14, 5, 1)


def test_nrpn_echo_keeps_the_fraction(midi_out, dispatcher):
    seen = []
    dispatcher.map("/cc/73", lambda address, value: seen.append(value))
    nrpn_client(midi_out, dispatcher).send_message("/cc/73", 40.5)
    assert seen == [40.5]


def test_osc_control_step_sets_click_size():
    sent = []
    control = OSCControl(
        {"$type": "control-range", "label": "WDTH", "address": "/cc/73", "min": 0, "max": 127, "step": 0.5},
        send_osc_func=lambda address, value: sent.append(value),
    )
    control.update_value(1)
    control.update_value(3)
    control.update_value(-1)
    assert sent == [0.5, 2.0, 1.5]


def test_osc_control_without_step_keeps_scaling():
    control = OSCControl({"$type": "control-range", "label": "X", "address": "/x", "min": 0, "max": 1})
    control.update_value(1)
    assert control.value == round(1 / 127, 2)


def test_osc_control_turn_sends_cc_and_one_click_is_one_step(client, midi_out, dispatcher):
    control = OSCControl(
        {"$type": "control-range", "label": "BASE", "address": "/cc/72", "min": 0, "max": 127},
        send_osc_func=client.send_message,
    )
    dispatcher.map(control.address, control.set_state)
    control.update_value(1)
    control.update_value(1)
    assert [c.args for c in midi_out.control.call_args_list] == [(72, 1, 3), (72, 2, 3)]
    assert control.value == 2.0


# ------------------------------------------------------- generated definitions


def m2k_files():
    return sorted(glob(os.path.join(M2K_DIR, "*.json")))


def test_generated_definitions_exist():
    names = [os.path.basename(p) for p in m2k_files()]
    assert len([n for n in names if n.startswith("00_machine_")]) == 19
    assert {"10_amp.json", "20_filt.json", "30_fx.json", "40_dstr.json"} <= set(names)


def test_generated_controls_only_use_cc_addresses():
    for path in m2k_files():
        device = json.load(open(path))
        assert len(device["controls"]) <= 8, path
        for control in device["controls"]:
            if control["$type"] == "control-spacer":
                continue
            assert control["$type"] == "control-range", path
            assert cc_number(control["address"]) is not None, (path, control)
        for message in device["init"]:
            assert cc_number(message["address"]) is not None, (path, message)


def test_machine_devices_select_their_machine_first():
    for path in m2k_files():
        device = json.load(open(path))
        if device["slot"] != 0:
            continue
        index = int(os.path.basename(path)[len("00_machine_"):-len(".json")])
        assert device["init"][0] == {
            "$type": "message",
            "$comment": "machine",
            "address": engine.M2KEngine.MACHINE_ADDRESS,
            "value": index,
        }


def load_generator():
    spec = importlib.util.spec_from_file_location("gen_definitions", "engines/m2k/gen_definitions.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generator_builds_pages_from_describe():
    gen = load_generator()
    param = lambda label, bipolar=False, mx=127: {"label": label, "name": label, "max": mx, "bipolar": bipolar, "choices": 0}
    describe = {
        "machine_cc": 14,
        "params": [
            {"cc": 56, "page": "AMP", "param": param("ATCK")},
            {"cc": 62, "page": "AMP", "param": param("PAN", bipolar=True)},
            {"cc": 88, "page": "LFO1", "param": param("TRCK")},
            {"cc": 89, "page": "LFO1", "param": param("DEST", mx=71)},
        ],
        "machines": [
            {"index": 3, "name": "FM+STAT", "syn": [{"cc": 48, "param": param("1FRQ")}, {"cc": 49, "param": param("-")}],
             "init": {"48": 61, "56": 0}},
        ],
    }
    files = gen.build(describe)
    machine = files["00_machine_03"]
    assert machine["name"] == "FM+STAT" and machine["slot"] == 0
    assert machine["controls"] == [
        {"$type": "control-range", "label": "1FRQ", "address": "/cc/48", "min": 0, "max": 127},
        {"$type": "control-spacer"},
    ]
    assert [(m["address"], m["value"]) for m in machine["init"]] == [("/cc/14", 3), ("/cc/48", 61), ("/cc/56", 0)]
    assert files["10_amp"]["controls"][1]["bipolar"] == 1
    assert files["50_lfo1"]["controls"] == [
        {"$type": "control-spacer"},
        {"$type": "control-range", "label": "DEST", "address": "/cc/89", "min": 0, "max": 71},
    ]
    assert files["50_lfo1"]["slot"] == 8


def test_generator_gives_filter_frequencies_half_steps():
    gen = load_generator()
    param = {"label": "WDTH", "name": "FILTER WIDTH", "max": 127, "bipolar": False, "choices": 0}
    assert gen.control(73, param, "FILT")["step"] == 0.5
    assert "step" not in gen.control(74, dict(param, label="HPQ"), "FILT")


def test_generated_filter_page_has_fine_steps():
    filt = json.load(open(os.path.join(M2K_DIR, "20_filt.json")))
    steps = {c["label"]: c.get("step") for c in filt["controls"] if c["$type"] == "control-range"}
    assert steps["BASE"] == 0.5 and steps["WDTH"] == 0.5 and steps["LPQ"] is None


# ------------------------------------------------------------- osc_mode choice


def test_device_definitions_for_surge_is_the_shared_set():
    surge = {"sine_1": {}}
    assert OSCMode.device_definitions_for({"instrument_short_name": "Pushpin 0"}, surge) is surge


def test_device_definitions_for_mono2k_load_in_page_order():
    defs = OSCMode.device_definitions_for({"engine": "mono2k"}, {"sine_1": {}})
    assert "sine_1" not in defs
    assert list(defs)[0] == "00_machine_00"
    assert list(defs)[-4:] == ["40_dstr", "50_lfo1", "51_lfo2", "52_lfo3"]


# ------------------------------------------------------ instrument end to end


M2K_INSTRUMENT = {
    "instrument_name": "Pushpin 2",
    "instrument_short_name": "Pushpin 2",
    "midi_channel": 2,
    "osc_in_port": 1032,
    "osc_out_port": 1042,
    "duplex_osc_port": 1052,
    "instrument_index": 2,
    "engine": "mono2k",
}


@pytest.fixture
def m2k_instrument(app):
    """A real Instrument on the mono2k engine, with the MIDI ports mocked out."""
    from modes.instrument import Instrument

    app.tempo = 120
    midi_out = MagicMock(name="midi_out_device")
    with patch("modes.instrument.iso") as iso, patch("modes.instrument.mido") as mido:
        iso.MidiOutputDevice.return_value = midi_out
        iso.get_midi_input_names.return_value = ["Pushpin 2 port"]
        mido.get_input_names.return_value = ["Pushpin 2 port"]
        instrument = Instrument(
            "Pushpin 2",
            M2K_INSTRUMENT,
            load_device_definitions(M2K_DIR),
            get_current_instrument_color_helper=lambda: definitions.CYAN,
            app=app,
        )
    return instrument, midi_out


def device(instrument, label):
    return next(d for slot in instrument.devices for d in slot if d.label == label)


def test_m2k_instrument_uses_cc_client_and_m2k_engine(m2k_instrument):
    instrument, midi_out = m2k_instrument
    assert isinstance(instrument.engine, engine.M2KEngine)
    assert isinstance(instrument.osc["client"], MidiCCClient)
    assert instrument.osc["client"].midi_out is midi_out
    assert instrument.osc["client"].channel == 2
    assert instrument.osc["client"].nrpn is True
    assert instrument.osc["client"].plain_ccs == engine.M2KEngine.PLAIN_CCS


def test_m2k_instrument_shows_machine_then_pages(m2k_instrument):
    instrument, _ = m2k_instrument
    assert [d.label for d in instrument.current_devices] == ["GND-SIN", "AMP", "FILT", "FX", "DSTR"]
    assert [d.label for d in instrument.devices_modulation] == ["LFO 1", "LFO 2", "LFO 3"]


def test_selecting_a_machine_switches_page_and_loads_its_init(m2k_instrument):
    instrument, midi_out = m2k_instrument
    kick = device(instrument, "DRM-KICK")
    kick.select_sync()

    assert midi_out.control.call_args_list[0].args == (14, 15, 2)
    assert instrument.slots[0]["value"] == 15.0
    assert instrument.current_devices[0] is kick

    # The INIT values reach the other pages' controls through the echo
    expected = {m["address"]: m["value"] for m in kick.init}
    amp = device(instrument, "AMP")
    for control in amp.controls:
        assert control.value == expected[control.address], control.label


def test_p_lock_style_send_reaches_synth_and_display(m2k_instrument):
    """The sequencer sends p-locks through instrument.osc["client"] too."""
    instrument, midi_out = m2k_instrument
    instrument.send_message("/cc/72", 90.5)
    assert [c.args for c in midi_out.control.call_args_list] == [(99, 0, 2), (98, 72, 2), (6, 90, 2), (38, 64, 2)]
    base = next(c for c in device(instrument, "FILT").controls if c.address == "/cc/72")
    assert base.value == 90.5
