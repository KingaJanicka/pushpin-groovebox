"""Tests for child-process output handling in ``engine.py``.

surge-xt-cli and puredata used to be started with ``stdout=PIPE`` and nobody
read the pipe, so each child blocked once ~64 KB of output had built up. These
tests pin down the replacement: output goes to per-instrument log files.
"""

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import engine
from engine import SurgeXTEngine, open_child_log, spawn_logged


@pytest.fixture
def log_dir(tmp_path, monkeypatch):
    d = tmp_path / "logs"
    monkeypatch.setenv(engine.LOG_DIR_ENV, str(d))
    return d


def make_engine(app, index=3):
    definition = {
        "instrument_name": f"Pushpin {index}",
        "instrument_index": index,
        "osc_in_port": 1030 + index,
        "osc_out_port": 1040 + index,
        "duplex_osc_port": 1050 + index,
    }
    return SurgeXTEngine(app, midi_device_idx=0, instrument_definition=definition)


def fake_exec():
    proc = MagicMock()
    proc.pid = 4242
    return AsyncMock(return_value=proc)


# ---------------------------------------------------------------- log helpers


def test_child_log_dir_defaults_to_xdg_state(monkeypatch):
    monkeypatch.delenv(engine.LOG_DIR_ENV, raising=False)
    assert engine.child_log_dir().endswith(".local/state/pushpin-groovebox/logs")


def test_open_child_log_creates_dir_and_truncates(log_dir):
    (log_dir).mkdir()
    (log_dir / "surge-xt-0.log").write_bytes(b"previous run")

    log = open_child_log("surge-xt-0")
    log.write(b"new run")
    log.close()

    assert (log_dir / "surge-xt-0.log").read_bytes() == b"new run"


def test_open_child_log_falls_back_to_devnull(tmp_path, monkeypatch):
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("")
    monkeypatch.setenv(engine.LOG_DIR_ENV, str(blocker))

    assert open_child_log("surge-xt-0") is asyncio.subprocess.DEVNULL


def test_spawn_logged_child_does_not_stall_on_large_output(log_dir):
    """A child writing far more than a pipe buffer must still run to completion."""
    script = "import sys; sys.stdout.write('x' * 1_000_000); sys.stderr.write('done')"

    async def run():
        proc = await spawn_logged("chatty", sys.executable, "-c", script)
        proc.stdin.close()
        return await asyncio.wait_for(proc.wait(), timeout=10)

    assert asyncio.run(run()) == 0
    content = (log_dir / "chatty.log").read_bytes()
    assert len(content) == 1_000_000 + len("done")
    assert content.endswith(b"done")


# ------------------------------------------------------------ engine wiring


def test_surge_start_sends_output_to_instrument_log(app, log_dir):
    eng = make_engine(app, index=3)
    exec_mock = fake_exec()
    with patch("engine.asyncio.create_subprocess_exec", exec_mock), patch(
        "engine.asyncio.sleep", AsyncMock()
    ):
        asyncio.run(eng.start())

    args, kwargs = exec_mock.call_args
    assert args[:4] == ("pw-jack", "-p", "128", "surge-xt-cli")
    assert "--osc-in-port=1033" in args
    assert kwargs["stdout"] is not asyncio.subprocess.PIPE
    assert kwargs["stderr"] is asyncio.subprocess.STDOUT
    assert kwargs["stdin"] is asyncio.subprocess.PIPE
    assert kwargs["stdout"].closed  # parent's copy is released after spawn
    assert (log_dir / "surge-xt-3.log").exists()
    assert eng.PID == 4242


def test_pd_node_sends_output_to_instrument_log(app, log_dir):
    app.get_pipewire_config = AsyncMock()
    eng = make_engine(app, index=5)
    exec_mock = fake_exec()
    with patch("engine.asyncio.create_subprocess_exec", exec_mock), patch(
        "engine.asyncio.sleep", AsyncMock()
    ), patch.object(SurgeXTEngine, "configure_duplex_node", AsyncMock()):
        asyncio.run(eng.start_pd_node())

    args, kwargs = exec_mock.call_args
    assert "puredata" in args
    assert "./puredata_nodes/passthrough_5.pd" in args
    assert kwargs["stdout"] is not asyncio.subprocess.PIPE
    assert kwargs["stderr"] is asyncio.subprocess.STDOUT
    assert (log_dir / "puredata-5.log").exists()
    assert eng.puredata_process_id == 4242


# ------------------------------------------------------------ engine choice


def m2k_definition(index=2, **extra):
    definition = {
        "instrument_name": f"Pushpin {index}",
        "instrument_short_name": f"Pushpin {index}",
        "instrument_index": index,
        "osc_in_port": 1030 + index,
        "osc_out_port": 1040 + index,
        "duplex_osc_port": 1050 + index,
        "engine": "mono2k",
    }
    definition.update(extra)
    return definition


def test_create_engine_defaults_to_surge(app):
    definition = m2k_definition()
    del definition["engine"]
    eng = engine.create_engine(app, definition, midi_device_idx=0)
    assert type(eng) is SurgeXTEngine
    assert eng.jack_client_name == "Surge XT"


def test_create_engine_picks_mono2k(app):
    eng = engine.create_engine(app, m2k_definition(index=2), midi_device_idx=0)
    assert isinstance(eng, engine.M2KEngine)
    assert eng.jack_client_name == "M2K"
    assert eng.output_port_names == ("track3_L", "track3_R")
    assert engine.m2k_shared().tracks == {2: "Pushpin 2"}


def test_create_engine_rejects_unknown_engine(app):
    with pytest.raises(ValueError, match="Unknown engine \"moog\""):
        engine.create_engine(app, m2k_definition(engine="moog"), midi_device_idx=0)


def test_m2k_binary_honours_env(monkeypatch):
    monkeypatch.delenv(engine.M2K_BINARY_ENV, raising=False)
    assert engine.m2k_binary().endswith("engines/m2k/build/m2k-jack")
    monkeypatch.setenv(engine.M2K_BINARY_ENV, "/opt/m2k/m2k-jack")
    assert engine.m2k_binary() == "/opt/m2k/m2k-jack"


def test_m2k_tracks_share_one_m2k_jack(app, log_dir, monkeypatch):
    monkeypatch.setenv(engine.M2K_BINARY_ENV, "/opt/m2k/m2k-jack")
    first = engine.create_engine(app, m2k_definition(index=4, m2k_machine=5), midi_device_idx=0)
    second = engine.create_engine(app, m2k_definition(index=1), midi_device_idx=0)
    exec_mock = fake_exec()
    with patch("engine.asyncio.create_subprocess_exec", exec_mock), patch(
        "engine.asyncio.sleep", AsyncMock()
    ):
        asyncio.run(first.start())
        asyncio.run(second.start())

    exec_mock.assert_called_once()
    args, kwargs = exec_mock.call_args
    assert args == (
        "pw-jack", "-p", "128", "/opt/m2k/m2k-jack",
        "--name", "M2K",
        "--enable", "2,5",
        "--midi-connect", "2=Pushpin 1",
        "--midi-connect", "5=Pushpin 4",
    )
    assert kwargs["stdin"] is asyncio.subprocess.PIPE
    assert (log_dir / "m2k.log").exists()
    assert first.PID == second.PID == 4242


def test_m2k_track_must_be_0_to_7_and_free(app):
    with pytest.raises(ValueError, match="tracks 0-7, not 8"):
        engine.create_engine(app, m2k_definition(index=8), midi_device_idx=0)
    engine.create_engine(app, m2k_definition(index=3), midi_device_idx=0)
    other = m2k_definition(index=3)
    other["instrument_short_name"] = "Other"
    with pytest.raises(ValueError, match="taken by Pushpin 3"):
        engine.create_engine(app, other, midi_device_idx=0)


def test_m2k_shared_args_without_tracks_enable_none():
    assert engine.M2KShared().args(64)[-2:] == ["--enable", "none"]


def _port(node_id, path, port_id):
    return {
        "id": port_id,
        "type": "PipeWire:Interface:Port",
        "info": {"props": {"node.id": node_id, "object.path": path}},
    }


@pytest.mark.parametrize(
    "engine_name, out_L, out_R",
    [("surge-xt-cli", "Surge XT:output_0", "Surge XT:output_1"), ("mono2k", "M2K:track1_L", "M2K:track1_R")],
)
def test_configure_pipewire_routes_by_port_name(app, engine_name, out_L, out_R):
    """Both engines route their own outputs through the volume node, found by port name."""
    definition = m2k_definition(index=0, engine=engine_name)
    eng = engine.create_engine(app, definition, midi_device_idx=0)
    node = {"id": 10}
    volume_node = {"id": 20}
    app.pipewire = [
        _port(10, out_L, 101),
        _port(10, out_R, 102),
        _port(20, "pure_data:input_0", 201),
        _port(20, "pure_data:input_1", 202),
        _port(20, "pure_data:output_0", 203),
        _port(20, "pure_data:output_1", 204),
        {"id": 301, "type": "PipeWire:Interface:Link",
         "info": {"output-node-id": 10, "output-port-id": 101, "input-port-id": 901}},
        {"id": 302, "type": "PipeWire:Interface:Link",
         "info": {"output-node-id": 10, "output-port-id": 102, "input-port-id": 902}},
    ]
    app.get_volume_node.return_value = volume_node
    connect = AsyncMock()
    disconnect = AsyncMock()
    with patch.object(engine.Engine, "configure_pipewire", AsyncMock()), patch(
        "engine.connectPipewireSourceToPipewireDest", connect
    ), patch("engine.disconnectPipewireLink", disconnect):
        eng.instrument_nodes = [node]
        asyncio.run(eng.configure_pipewire())

    assert [c.args for c in connect.call_args_list] == [(101, 201), (102, 202), (203, 901), (204, 902)]
    assert [c.args for c in disconnect.call_args_list] == [(301,), (302,)]


def test_m2k_track_routing_leaves_the_other_tracks_alone(app):
    """In the shared process, track 2's routing must not touch track 1's or the return's links."""
    eng = engine.create_engine(app, m2k_definition(index=1), midi_device_idx=0)
    link = lambda lid, out_port, in_port: {
        "id": lid, "type": "PipeWire:Interface:Link",
        "info": {"output-node-id": 10, "output-port-id": out_port, "input-port-id": in_port},
    }
    app.pipewire = [
        _port(10, "M2K:track1_L", 101), _port(10, "M2K:track1_R", 102),
        _port(10, "M2K:track2_L", 103), _port(10, "M2K:track2_R", 104),
        _port(10, "M2K:fx_L", 105), _port(10, "M2K:fx_R", 106),
        _port(20, "pure_data:input_2", 202), _port(20, "pure_data:input_3", 203),
        _port(20, "pure_data:output_2", 212), _port(20, "pure_data:output_3", 213),
        link(301, 101, 901), link(302, 102, 902),
        link(303, 103, 901), link(304, 104, 902),
        link(305, 105, 901), link(306, 106, 902),
    ]
    app.get_volume_node.return_value = {"id": 20}
    connect, disconnect = AsyncMock(), AsyncMock()
    with patch.object(engine.Engine, "configure_pipewire", AsyncMock()), patch(
        "engine.connectPipewireSourceToPipewireDest", connect
    ), patch("engine.disconnectPipewireLink", disconnect):
        eng.instrument_nodes = [{"id": 10}]
        asyncio.run(eng.configure_pipewire())

    assert [c.args for c in connect.call_args_list] == [(103, 202), (104, 203), (212, 901), (213, 902)]
    assert [c.args for c in disconnect.call_args_list] == [(303,), (304,)]


def test_surge_initial_slots_are_surges_type_addresses(app):
    eng = engine.create_engine(app, m2k_definition(engine="surge-xt-cli"), midi_device_idx=0)
    slots = eng.initial_slots()
    assert len(slots) == 16
    assert [s["address"] for s in slots if s] == [
        "/param/a/osc/1/type",
        "/param/a/osc/2/type",
        "/param/fx/a/1/type",
        "/param/fx/a/2/type",
        "/param/fx/global/1/type",
    ]
    assert eng.control_transport == "osc"
    assert eng.initial_slots() is not slots  # each instrument gets its own list


def test_m2k_initial_slots_select_machine_by_cc(app):
    eng = engine.create_engine(app, m2k_definition(m2k_machine=7), midi_device_idx=0)
    slots = eng.initial_slots()
    assert slots[0] == {"address": "/cc/14", "value": 7.0}
    assert slots[1:] == [None] * 15
    assert eng.control_transport == "midi-cc"
