"""Stopping the app cleanly however it's stopped.

On the Pi, systemd stops the pushpin service with SIGTERM, which Python
otherwise answers by exiting on the spot: none of app.py's exit handling (which
catches KeyboardInterrupt, i.e. Ctrl-C) ran, so sequences and the SCALE page
weren't saved. ``install_sigterm_handler`` makes SIGTERM take that same path.
"""
from __future__ import annotations

import signal


def _raise_keyboard_interrupt(signum, frame):
    # A second SIGTERM while we save would interrupt the save; ignore it
    # (systemd still SIGKILLs after its stop timeout if exiting hangs).
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    raise KeyboardInterrupt


def install_sigterm_handler() -> None:
    """SIGTERM stops the app the way Ctrl-C does. Call from the main thread."""
    signal.signal(signal.SIGTERM, _raise_keyboard_interrupt)


def save_on_exit(app) -> None:
    """Keep each track's sequence (in the clip it's on) and the SCALE page."""
    try:
        app.metro_sequencer_mode.save_state()
    except Exception as e:
        print("Could not save state on exit:", e)
