"""SIGTERM (systemd stopping the service) saves state like Ctrl-C does."""
import os
import signal
import subprocess
import sys
import textwrap
from unittest.mock import MagicMock

import pytest

import shutdown


@pytest.fixture
def restore_sigterm():
    previous = signal.getsignal(signal.SIGTERM)
    yield
    signal.signal(signal.SIGTERM, previous)


# Real signals are only sent to a child process (last test): sent to pytest's
# own process, a broken handler would kill the whole test run.

def test_install_routes_sigterm_to_the_handler(restore_sigterm):
    shutdown.install_sigterm_handler()
    assert signal.getsignal(signal.SIGTERM) is shutdown._raise_keyboard_interrupt


def test_handler_raises_keyboard_interrupt_and_ignores_a_second_sigterm(restore_sigterm):
    shutdown.install_sigterm_handler()
    with pytest.raises(KeyboardInterrupt):
        shutdown._raise_keyboard_interrupt(signal.SIGTERM, None)
    # a second SIGTERM mustn't interrupt the save
    assert signal.getsignal(signal.SIGTERM) is signal.SIG_IGN


def test_save_on_exit_saves_sequences_and_scale_page():
    app = MagicMock()
    shutdown.save_on_exit(app)
    app.metro_sequencer_mode.save_state.assert_called_once_with()


def test_save_on_exit_never_raises():
    app = MagicMock()
    app.metro_sequencer_mode.save_state.side_effect = OSError("disk full")
    shutdown.save_on_exit(app)


def test_sigterm_during_asyncio_run_reaches_the_exit_save(tmp_path):
    """The app's shape: asyncio.run(main()) inside try/except KeyboardInterrupt.
    A SIGTERM must land in that except and save."""
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    marker = tmp_path / "saved"
    script = textwrap.dedent(f"""
        import asyncio, sys
        sys.path.insert(0, {repo!r})
        import shutdown

        class Metro:
            def save_state(self):
                open({str(marker)!r}, "w").write("ok")

        class App:
            metro_sequencer_mode = Metro()

        async def main():
            print("running", flush=True)
            while True:
                await asyncio.sleep(0.05)

        shutdown.install_sigterm_handler()
        try:
            app = App()
            asyncio.run(main())
        except KeyboardInterrupt:
            shutdown.save_on_exit(app)
    """)
    proc = subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE, text=True)
    try:
        assert proc.stdout.readline().strip() == "running"
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=10)
    finally:
        if proc.poll() is None:
            proc.kill()
    assert marker.read_text() == "ok"
