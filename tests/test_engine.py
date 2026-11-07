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
from engine import (
    SurgeXTEngine,
    open_child_log,
    parse_surge_midi_devices,
    spawn_logged,
    surge_midi_input_index,
)


@pytest.fixture(autouse=True)
def reset_surge_midi_cache(monkeypatch):
    monkeypatch.setattr(engine, "_surge_midi_devices", None)
    monkeypatch.setattr(engine, "_surge_midi_devices_lock", None)


@pytest.fixture
def log_dir(tmp_path, monkeypatch):
    d = tmp_path / "logs"
    monkeypatch.setenv(engine.LOG_DIR_ENV, str(d))
    return d


def make_engine(app, index=3):
    definition = {
        "instrument_name": f"Pushpin {index}",
        "instrument_short_name": f"Pushpin {index}",
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
    ), patch("engine.surge_midi_input_index", AsyncMock(return_value=3)):
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


# ------------------------------------------------------- Surge MIDI port lookup

# Real `pw-jack surge-xt-cli --list-devices` output from the Pi (MIDI part, plus
# one audio line that must be ignored). mido/rtmidi list Midi Through and the
# Push 2 ports *first* on the same machine, so their index for "Pushpin 0" is 3.
PI_LIST_DEVICES = """\
20:04:25.512 - Input Audio Device: [1.10] : JACK.Midi-Bridge
20:04:25.663 - MIDI Device: [0] : Pushpin 0
20:04:25.663 - MIDI Device: [1] : Pushpin 1
20:04:25.663 - MIDI Device: [2] : Pushpin 2
20:04:25.663 - MIDI Device: [3] : Pushpin 3
20:04:25.663 - MIDI Device: [4] : Pushpin 4
20:04:25.663 - MIDI Device: [5] : Pushpin 5
20:04:25.663 - MIDI Device: [6] : Pushpin 6
20:04:25.663 - MIDI Device: [7] : Pushpin 7
20:04:25.663 - MIDI Device: [8] : Overwitch
20:04:25.663 - MIDI Device: [9] : RtMidi output
20:04:25.663 - MIDI Device: [10] : Midi Through Port-0
20:04:25.663 - MIDI Device: [11] : Ableton Push 2 Live Port
20:04:25.663 - MIDI Device: [12] : Ableton Push 2 User Port
"""


def test_parse_surge_midi_devices_reads_names_and_indices():
    devices = parse_surge_midi_devices(PI_LIST_DEVICES)
    assert devices["Pushpin 0"] == 0
    assert devices["Pushpin 7"] == 7
    assert devices["RtMidi output"] == 9
    assert devices["Ableton Push 2 Live Port"] == 11
    assert len(devices) == 13  # the audio line is not a MIDI device


def test_parse_surge_midi_devices_ignores_noise():
    assert parse_surge_midi_devices("") == {}
    assert parse_surge_midi_devices("MIDI Device: [x] : bad\nrandom text") == {}


def test_surge_midi_input_index_matches_by_exact_name():
    listing = AsyncMock(return_value=parse_surge_midi_devices(PI_LIST_DEVICES))
    with patch("engine.list_surge_midi_devices", listing):
        assert asyncio.run(surge_midi_input_index("Pushpin 0")) == 0
        assert asyncio.run(surge_midi_input_index("Pushpin 6")) == 6
    listing.assert_awaited_once()  # cached across lookups


def test_surge_midi_input_index_lists_once_for_concurrent_starts():
    listing = AsyncMock(return_value=parse_surge_midi_devices(PI_LIST_DEVICES))

    async def run():
        return await asyncio.gather(*(surge_midi_input_index(f"Pushpin {i}") for i in range(8)))

    with patch("engine.list_surge_midi_devices", listing):
        assert asyncio.run(run()) == list(range(8))
    listing.assert_awaited_once()


def test_surge_midi_input_index_relists_when_port_missing():
    first = {"Pushpin 0": 0}
    second = {"Pushpin 0": 0, "Pushpin 1": 1}
    listing = AsyncMock(side_effect=[first, second])
    with patch("engine.list_surge_midi_devices", listing):
        assert asyncio.run(surge_midi_input_index("Pushpin 0")) == 0
        assert asyncio.run(surge_midi_input_index("Pushpin 1")) == 1
    assert listing.await_count == 2


def test_surge_midi_input_index_none_when_absent():
    listing = AsyncMock(return_value={"Pushpin 0": 0})
    with patch("engine.list_surge_midi_devices", listing):
        assert asyncio.run(surge_midi_input_index("Pushpin 5")) is None


def _start_with_listing(app, index, devices):
    eng = make_engine(app, index=index)
    exec_mock = fake_exec()
    with patch("engine.asyncio.create_subprocess_exec", exec_mock), patch(
        "engine.asyncio.sleep", AsyncMock()
    ), patch("engine.list_surge_midi_devices", AsyncMock(return_value=devices)):
        asyncio.run(eng.start())
    return exec_mock.call_args.args


def test_surge_start_uses_surge_index_not_mido_index(app, log_dir):
    """The engine's mido-based midi_device_idx (0 here) must not reach Surge."""
    args = _start_with_listing(app, 6, parse_surge_midi_devices(PI_LIST_DEVICES))
    midi = [a for a in args if a.startswith("--midi-input")]
    assert midi == ["--midi-input=6"]  # "Pushpin 6" in Surge's list, not RtMidi output


def test_surge_start_without_port_has_no_midi_input(app, log_dir):
    args = _start_with_listing(app, 6, {"Pushpin 0": 0})
    assert not [a for a in args if a.startswith("--midi-input")]
    assert "--osc-in-port=1036" in args  # still starts, just without MIDI


def test_list_surge_midi_devices_parses_process_output():
    proc = MagicMock()
    proc.communicate = AsyncMock(return_value=(PI_LIST_DEVICES.encode(), None))
    exec_mock = AsyncMock(return_value=proc)
    with patch("engine.asyncio.create_subprocess_exec", exec_mock):
        devices = asyncio.run(engine.list_surge_midi_devices())
    assert exec_mock.call_args.args == ("pw-jack", "surge-xt-cli", "--list-devices")
    assert devices["Pushpin 3"] == 3
