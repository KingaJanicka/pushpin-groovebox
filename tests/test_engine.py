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
