"""Tests for the Audio In device's routing (``modes/audio_in_device.py``).

A Surge track whose oscillator is "Audio In" gets its own Pd passthrough node
(the "duplex" node, ``puredata_nodes/passthrough_N.pd``). Its 8 stereo columns
each take one source (another track, or an Overwitch port) into the duplex
input; every duplex output is linked to Surge's audio input once, when the node
starts (``SurgeXTEngine.connect_links_to_duplex_node``). Page 2 of the device
holds a source switch per column: slot 0's device drives columns 0-3, slot 1's
columns 4-7. The "In N Gain" knobs set each column's level over OSC.

PipeWire is never touched: the link helpers are patched to record their calls,
and ``app.pipewire`` is a hand-built ``pw-dump``.
"""

import asyncio
import os
import re
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import push2_python.constants as C
import pytest

import engine
from engine import SurgeXTEngine
from modes import audio_in_device
from modes.audio_in_device import AudioInDevice

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACK_ENCODERS = [getattr(C, f"ENCODER_TRACK{n}_ENCODER") for n in range(1, 9)]


# ------------------------------------------------------------------ fixtures


def definition(index, engine_name="surge-xt-cli"):
    return {
        "instrument_name": f"Pushpin {index}",
        "instrument_short_name": f"Pushpin {index}",
        "instrument_index": index,
        "osc_in_port": 1030 + index,
        "osc_out_port": 1040 + index,
        "duplex_osc_port": 1050 + index,
        "engine": engine_name,
    }


def port(port_id, path, alias=None, name=None):
    props = {"object.path": path, "port.name": name or path.split(":")[-1]}
    if alias:
        props["port.alias"] = alias
    return {"id": port_id, "type": "PipeWire:Interface:Port", "info": {"props": props}}


def surge_track(app, index, pid):
    """A track playing Surge, its output ports already found by configure_pipewire."""
    eng = SurgeXTEngine(app, midi_device_idx=0, instrument_definition=definition(index))
    eng.PID = pid
    base = 100 * (index + 1)
    eng.pw_ports["output"] = [port(base, "Surge XT:output_0"), port(base + 1, "Surge XT:output_1")]
    eng.pw_ports["input"] = [port(base + 2, "Surge XT:input_0"), port(base + 3, "Surge XT:input_1")]
    return SimpleNamespace(name=f"Pushpin {index}", engine=eng)


def m2k_track(app, index, pid):
    """A track playing mono2k: one shared m2k-jack process (so one PID for every
    mono2k track), ports named by PipeWire by index, the JACK name in the alias."""
    eng = engine.create_engine(app, definition(index, "mono2k"), midi_device_idx=0)
    eng.PID = pid
    base = 100 * (index + 1)
    eng.pw_ports["output"] = [
        port(base, f"M2K:output_{2 * index}", alias=f"M2K:track{index + 1}_L"),
        port(base + 1, f"M2K:output_{2 * index + 1}", alias=f"M2K:track{index + 1}_R"),
    ]
    return SimpleNamespace(name=f"Pushpin {index}", engine=eng)


def overwitch(pid=None, ports=("Main L", "Main R", "Track 1")):
    eng = SimpleNamespace(PID=pid, pw_ports={"output": [], "input": []})
    for i, name in enumerate(ports):
        eng.pw_ports["output"].append(
            {"id": 900 + i, "type": "PipeWire:Interface:Port",
             "info": {"props": {"port.name": name, "object.path": f"Overwitch:{name}"}}}
        )
    return SimpleNamespace(name="Overwitch", engine=eng)


def wire_duplex_ports(eng, base=5000):
    """The track's duplex node is up: give its 16 inputs/outputs port ids.
    Column c: input L/R = base + 4c, +1; output L/R = base + 4c + 2, +3."""
    for c in range(8):
        eng.duplex_ports["inputs"][f"Input {c}"] = {"L": {"id": base + 4 * c}, "R": {"id": base + 4 * c + 1}}
        eng.duplex_ports["outputs"][f"Output {c}"] = {"L": {"id": base + 4 * c + 2}, "R": {"id": base + 4 * c + 3}}
    eng.duplex_node = {"id": 77}


def duplex_in(c):
    return 5000 + 4 * c, 5000 + 4 * c + 1


@pytest.fixture
def links(monkeypatch):
    """Record link changes instead of running pw-link: the queue gets tuples."""
    monkeypatch.setattr(audio_in_device, "connectPipewireSourceToPipewireDest", lambda s, d: ("link", s, d))
    monkeypatch.setattr(audio_in_device, "disconnectPipewireSourceFromPipewireDest", lambda s, d: ("unlink", s, d))


@pytest.fixture
def rig(app, links):
    """Track 0 (Surge, Audio In on slot 0) with tracks 1 (Surge) and 2 (Surge) to route from."""
    app.queue = []
    app.metro_sequencer_mode.disable_controls = False
    tracks = [surge_track(app, i, pid=4000 + i) for i in range(3)]
    app.instruments = {t.name: t for t in tracks}
    app.external_instruments = [overwitch()]
    me = tracks[0]
    wire_duplex_ports(me.engine)
    return SimpleNamespace(app=app, tracks=tracks, me=me)


def make_device(app, eng, slot=0):
    return AudioInDevice(
        {"name": "Audio In", "slot": slot, "init": []},
        {"client": MagicMock(), "server": None, "dispatcher": MagicMock()},
        engine=eng,
        app=app,
        osc_in_port=eng.osc_in_port or 1030,
        osc_out_port=eng.osc_out_port or 1040,
        get_color=lambda: "white",
    )


def turn(device, knob, increment):
    device.on_encoder_rotated(TRACK_ENCODERS[knob], increment)


def choose(device, column, source_label):
    """Turn a column's source switch (page 2, encoder 2c+1) to ``source_label``."""
    device.set_page(1)
    switch = device.get_visible_controls()[2 * (column % 4)]
    target = [g.label for g in switch.groups].index(source_label)
    # One twist that lands mid-way into the target group (a full 127-click
    # sweep covers all the groups)
    delta = target + 0.5 - switch.value
    turn(device, 2 * (column % 4), delta * 127 / len(switch.groups))
    assert int(switch.value) == target


@pytest.fixture
def device(rig):
    dev = make_device(rig.app, rig.me.engine)
    dev.update()
    return dev


# ----------------------------------------------------------- page layout


def test_page_1_is_the_gains_and_filters(device):
    labels = [c.label for c in device.pages[0]]
    assert labels == ["Audio Channel", "Audio Gain", "In 1 Gain", "In 2 Gain",
                      "In 3 Gain", "In 4 Gain", "Low Cut", "High Cut"]


def test_page_2_is_a_source_switch_and_its_menu_per_column(device):
    page = device.pages[1]
    assert len(page) == 8
    switches = page[0::2]
    assert all(s.name == "Switch" for s in switches)
    assert [g.label for g in switches[0].groups] == ["None sel.", "Pushpin 0", "Pushpin 1", "Pushpin 2"]


def test_overwitch_is_offered_once_it_is_running(rig):
    rig.app.external_instruments = [overwitch(pid=999)]
    dev = make_device(rig.app, rig.me.engine)
    dev.update()
    switch = dev.pages[1][0]
    assert [g.label for g in switch.groups][-1] == "Overwitch"
    assert [c.label for c in switch.groups[-1].controls[0].items] == ["Main L", "Main R", "Track 1"]


# --------------------------------------------------------- connecting sources


def test_choosing_a_track_links_its_outputs_into_that_columns_duplex_input(rig, device):
    choose(device, 0, "Pushpin 1")
    in_L, in_R = duplex_in(0)
    assert rig.app.queue == [("link", 200, in_L), ("link", 201, in_R)]
    assert rig.me.engine.connections[0]["L"] == 200
    assert rig.me.engine.connections[0]["R"] == 201


@pytest.mark.parametrize("column", [0, 1, 2, 3])
def test_each_switch_routes_its_own_column(rig, device, column):
    choose(device, column, "Pushpin 2")
    in_L, in_R = duplex_in(column)
    assert rig.app.queue == [("link", 300, in_L), ("link", 301, in_R)]


def test_switch_routes_its_own_column_even_right_after_another_knob(rig, device):
    """The column comes from the knob being turned now, not the knob turned before."""
    device.set_page(1)
    turn(device, 7, 1)            # touch column 3's menu first
    rig.app.queue.clear()
    turn(device, 0, 127)          # one full twist of column 0's switch: the last source
    in_L, in_R = duplex_in(0)
    assert rig.app.queue == [("link", 300, in_L), ("link", 301, in_R)]


def test_slot_1_device_drives_columns_4_to_7(rig):
    dev = make_device(rig.app, rig.me.engine, slot=1)
    dev.update()
    choose(dev, 4, "Pushpin 1")
    in_L, in_R = duplex_in(4)
    assert rig.app.queue == [("link", 200, in_L), ("link", 201, in_R)]


def test_changing_source_swaps_only_the_input_links(rig, device):
    """The duplex outputs stay linked to Surge's input: the queue runs its tasks
    concurrently, so unlinking and relinking the same output could leave it unlinked."""
    choose(device, 0, "Pushpin 1")
    rig.app.queue.clear()
    choose(device, 0, "Pushpin 2")
    in_L, in_R = duplex_in(0)
    assert rig.app.queue == [
        ("unlink", 200, in_L), ("unlink", 201, in_R),
        ("link", 300, in_L), ("link", 301, in_R),
    ]


def test_choosing_none_disconnects_the_column(rig, device):
    choose(device, 0, "Pushpin 1")
    rig.app.queue.clear()
    choose(device, 0, "None sel.")
    in_L, in_R = duplex_in(0)
    assert rig.app.queue == [("unlink", 200, in_L), ("unlink", 201, in_R)]
    assert rig.me.engine.connections[0]["L"] is None
    assert rig.me.engine.connections[0]["R"] is None


def test_choosing_none_on_an_empty_column_does_nothing(rig, device):
    choose(device, 0, "Pushpin 1")
    choose(device, 0, "None sel.")
    rig.app.queue.clear()
    choose(device, 0, "Pushpin 0")
    choose(device, 0, "None sel.")
    assert ("unlink", None, duplex_in(0)[0]) not in rig.app.queue
    assert all(None not in entry for entry in rig.app.queue)


def test_reselecting_the_same_source_does_not_relink(rig, device):
    choose(device, 0, "Pushpin 1")
    rig.app.queue.clear()
    device.connect_ports_duplex("/route", device.sources.index(rig.tracks[1]))
    assert rig.app.queue == []


def test_mono2k_tracks_route_their_own_outputs(rig):
    """mono2k tracks share one process (one PID) and their ports aren't called
    "Surge XT:output_N": each must still route its own track's outputs."""
    rig.tracks[1] = m2k_track(rig.app, 1, pid=6000)
    rig.tracks[2] = m2k_track(rig.app, 2, pid=6000)
    rig.app.instruments = {t.name: t for t in rig.tracks}
    dev = make_device(rig.app, rig.me.engine)
    dev.update()
    choose(dev, 0, "Pushpin 2")
    in_L, in_R = duplex_in(0)
    assert rig.app.queue == [("link", 300, in_L), ("link", 301, in_R)]


def test_overwitch_port_feeds_both_sides_of_the_column(rig):
    rig.app.external_instruments = [overwitch(pid=999)]
    dev = make_device(rig.app, rig.me.engine)
    dev.update()
    choose(dev, 1, "Overwitch")
    in_L, in_R = duplex_in(1)
    assert rig.app.queue == [("link", 900, in_L), ("link", 900, in_R)]
    # Its menu picks the port
    rig.app.queue.clear()
    turn(dev, 3, 127)
    assert rig.app.queue[-2:] == [("link", 902, in_L), ("link", 902, in_R)]
    assert ("unlink", 900, in_L) in rig.app.queue


def test_routing_before_the_duplex_node_is_up_is_ignored_not_raised(rig, app, links):
    eng = SurgeXTEngine(app, midi_device_idx=0, instrument_definition=definition(5))
    dev = make_device(app, eng)
    dev.update()
    choose(dev, 0, "Pushpin 1")           # must not raise
    assert app.queue == []
    assert eng.connections[0]["L"] is None


def test_switches_show_the_current_routing_after_reopening(rig, device):
    choose(device, 2, "Pushpin 2")
    device.update()                      # selecting the device again rebuilds the switches
    assert device.pages[1][4].label == "Pushpin 2"
    assert device.pages[1][0].label == "None sel."


# ------------------------------------------------------- Pd node lifecycle


def test_restarting_the_duplex_node_forgets_its_old_links(rig, device):
    """Pd's ports are new after a restart. Choosing the same source again must
    link it to them, not be skipped as "already connected"."""
    choose(device, 0, "Pushpin 1")
    asyncio.run(rig.me.engine.kill_pd_node())
    assert rig.me.engine.connections[0] == {"L": None, "R": None} or rig.me.engine.connections[0]["L"] is None
    assert rig.me.engine.duplex_node is None
    assert rig.me.engine.duplex_ports["inputs"]["Input 0"]["L"] is None

    wire_duplex_ports(rig.me.engine)     # the new node comes up
    device.update()
    rig.app.queue.clear()
    choose(device, 0, "Pushpin 1")
    in_L, in_R = duplex_in(0)
    assert rig.app.queue == [("link", 200, in_L), ("link", 201, in_R)]


def test_duplex_node_links_every_output_to_surges_input(app):
    eng = SurgeXTEngine(app, midi_device_idx=0, instrument_definition=definition(0))
    eng.instrument_nodes = [{"id": 10}]
    app.pipewire = [
        {"id": 11, "type": "PipeWire:Interface:Port",
         "info": {"props": {"node.id": 10, "object.path": "Surge XT:input_0"}}},
        {"id": 12, "type": "PipeWire:Interface:Port",
         "info": {"props": {"node.id": 10, "object.path": "Surge XT:input_1"}}},
    ]
    wire_duplex_ports(eng)
    connect = AsyncMock()
    with patch("engine.connectPipewireSourceToPipewireDest", connect):
        asyncio.run(eng.connect_links_to_duplex_node())
    expected = []
    for c in range(8):
        expected += [(5000 + 4 * c + 2, 11), (5000 + 4 * c + 3, 12)]
    assert [call.args for call in connect.call_args_list] == expected


def test_duplex_ports_are_sorted_into_columns_by_pd_port_name(app):
    """Pd names its JACK ports input_1..16 / output_1..16 (from 1)."""
    eng = SurgeXTEngine(app, midi_device_idx=0, instrument_definition=definition(0))
    eng.duplex_node = {"id": 77}
    app.pipewire = []
    for n in range(1, 17):
        for kind, base in (("input", 0), ("output", 100)):
            app.pipewire.append({"id": base + n, "type": "PipeWire:Interface:Port",
                                 "info": {"props": {"node.id": 77, "port.name": f"{kind}_{n}"}}})
    eng.get_duplex_ports()
    for c in range(8):
        assert eng.duplex_ports["inputs"][f"Input {c}"]["L"]["id"] == 2 * c + 1
        assert eng.duplex_ports["inputs"][f"Input {c}"]["R"]["id"] == 2 * c + 2
        assert eng.duplex_ports["outputs"][f"Output {c}"]["L"]["id"] == 100 + 2 * c + 1
        assert eng.duplex_ports["outputs"][f"Output {c}"]["R"]["id"] == 100 + 2 * c + 2


def test_audio_in_osc_type_starts_the_duplex_node_once(app):
    """Surge reporting osc type 4 (Audio In) on a slot starts the track's Pd node;
    leaving it kills the node only when the other slot isn't Audio In too."""
    from modes.instrument import Instrument
    inst = MagicMock(spec=Instrument)
    inst.app = app
    app.queue = []
    app.external_instruments = []
    eng = MagicMock(puredata_process_id=None)
    slots = [{"address": "/param/a/osc/1/type", "value": 0.0},
             {"address": "/param/a/osc/2/type", "value": 0.0}]
    voice = SimpleNamespace(engine=eng, slots=slots)
    inst.active_voice = None

    Instrument._voice_slot_state(inst, voice, "/param/a/osc/1/type", 4.0)
    assert eng.start_pd_node.call_count == 1
    eng.puredata_process_id = 123
    Instrument._voice_slot_state(inst, voice, "/param/a/osc/2/type", 4.0)
    assert eng.start_pd_node.call_count == 1

    Instrument._voice_slot_state(inst, voice, "/param/a/osc/1/type", 0.0)
    assert eng.kill_pd_node.call_count == 0          # slot 2 still listens
    Instrument._voice_slot_state(inst, voice, "/param/a/osc/2/type", 0.0)
    assert eng.kill_pd_node.call_count == 1


# --------------------------------------------------------------- input gains


def gains_sent(eng):
    sent = {}
    for call in eng.duplex_node_osc_client.send_message.call_args_list:
        address, value = call.args
        sent[address] = value
    return sent


@pytest.fixture
def gain_rig(rig):
    slot0 = make_device(rig.app, rig.me.engine, slot=0)
    slot1 = make_device(rig.app, rig.me.engine, slot=1)
    for d in (slot0, slot1):
        d.update()
    rig.app.osc_mode.get_current_instrument_devices.return_value = [slot0, slot1]
    rig.me.engine.duplex_node_osc_client = MagicMock()
    return SimpleNamespace(slot0=slot0, slot1=slot1, eng=rig.me.engine)


def test_in_gain_knob_sends_the_new_level_to_both_sides_of_its_column(gain_rig):
    turn(gain_rig.slot0, 3, 127)                 # "In 2 Gain" all the way up
    sent = gains_sent(gain_rig.eng)
    assert sent["/vol_2"] == pytest.approx(1.0)
    assert sent["/vol_3"] == pytest.approx(1.0)
    assert sent["/vol_0"] == 0.0


def test_in_gain_reaches_zero_when_turned_all_the_way_down(gain_rig):
    turn(gain_rig.slot0, 2, 127)
    turn(gain_rig.slot0, 2, -127)
    sent = gains_sent(gain_rig.eng)
    assert sent["/vol_0"] == 0.0 and sent["/vol_1"] == 0.0


def test_slot_1_gains_are_columns_4_to_7_and_keep_slot_0s(gain_rig):
    turn(gain_rig.slot0, 2, 127)                 # column 0 up
    gain_rig.eng.duplex_node_osc_client.reset_mock()
    turn(gain_rig.slot1, 5, 127)                 # slot 1's "In 4 Gain" -> column 7
    sent = gains_sent(gain_rig.eng)
    assert sent["/vol_14"] == pytest.approx(1.0) and sent["/vol_15"] == pytest.approx(1.0)
    assert sent["/vol_0"] == pytest.approx(1.0)  # column 0 not reset


def test_gains_work_when_only_slot_1_is_audio_in(rig):
    other = SimpleNamespace(label="Classic", slot=0)
    dev = make_device(rig.app, rig.me.engine, slot=1)
    dev.update()
    rig.app.osc_mode.get_current_instrument_devices.return_value = [other, dev]
    rig.me.engine.duplex_node_osc_client = MagicMock()
    turn(dev, 2, 127)
    sent = gains_sent(rig.me.engine)
    assert sent["/vol_8"] == pytest.approx(1.0)
    assert sent["/vol_0"] == 0.0


# --------------------------------------------------------- the Pd patches


def read_patch(n):
    with open(os.path.join(ROOT, "puredata_nodes", f"passthrough_{n}.pd")) as f:
        lines = [line.strip().rstrip(";") for line in f.read().split(";\n")]
    objects = [line for line in lines if line.startswith("#X obj") or line.startswith("#X msg")]
    connects = [tuple(map(int, line.split()[2:6])) for line in lines if line.startswith("#X connect")]
    return objects, connects


@pytest.mark.parametrize("n", range(9))
def test_pd_patch_listens_on_its_tracks_osc_port(n):
    objects, _ = read_patch(n)
    ports = [int(m.group(1)) for o in objects if (m := re.search(r"netreceive -u -b (\d+)", o))]
    assert ports == [1050 + n]


@pytest.mark.parametrize("n", range(8))
def test_instrument_definition_duplex_port_matches_its_patch(n):
    import json
    with open(os.path.join(ROOT, "definitions", "instrument_definitions", f"Pushpin {n}.json")) as f:
        assert json.load(f)["duplex_osc_port"] == 1050 + n


@pytest.mark.parametrize("n", range(9))
def test_pd_patch_vol_k_scales_channel_k_straight_through(n):
    """adc~ channel k goes through one *~ whose level is /vol_k, out to dac~ channel k."""
    objects, connects = read_patch(n)
    idx = {i: o for i, o in enumerate(objects)}
    adc = next(i for i, o in idx.items() if " adc~ " in o)
    dac = next(i for i, o in idx.items() if " dac~ " in o)
    routes = {i: re.search(r"route (vol_\d+)", o).group(1) for i, o in idx.items() if "route vol_" in o}
    mult_of_adc = {outlet: dst for src, outlet, dst, _ in connects if src == adc}
    dac_of_mult = {src: inlet for src, _, dst, inlet in connects if dst == dac}
    vol_of_mult = {dst: routes[src] for src, outlet, dst, inlet in connects
                   if src in routes and outlet == 0 and inlet == 1}
    for k in range(16):
        mult = mult_of_adc[k]
        assert dac_of_mult[mult] == k, f"channel {k} comes out on {dac_of_mult[mult]}"
        assert vol_of_mult[mult] == f"vol_{k}"
