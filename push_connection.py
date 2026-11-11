"""Keeps the app's MIDI link to the Push 2 working when the Push comes and goes.

push2_python tells us the Push is there when its first "active sensing" message
arrives, and it calls our handler on its own MIDI input thread. Setting up the
Push from that thread (colour palette, clearing every pad and button,
re-activating every mode) runs alongside the main loop, which is drawing the
same pads and buttons and changing the same mode state. At startup that never
happens (the handler runs before ``app`` exists, so the setup is done on the
main thread), which is why a Push plugged in after startup was the case that
froze.

``PushConnection`` keeps all of that on the main loop:

- ``notify_connected()`` only sets a flag; ``poll()`` (once per frame, on the
  main loop) does the setup.
- ``poll()`` also opens the MIDI ports while they are closed, and closes them
  again when they have been open for ``SILENT_PORT_TIMEOUT`` seconds without a
  word from the Push (ports opened while the Push was still booting, or left
  over from a Push that was unplugged), so the next ``poll()`` reopens them
  fresh.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)

# The Push sends active sensing every ~300 ms. Ports that hear nothing for this
# long are not talking to a Push.
SILENT_PORT_TIMEOUT = 5.0


class PushConnection:
    def __init__(
        self,
        push: Any,
        on_connected: Callable[[], None],
        clock: Callable[[], float] = time.time,
    ):
        self.push = push
        self.on_connected = on_connected
        self.clock = clock
        self.connect_pending = False
        self.silent_since: float | None = None

    def notify_connected(self) -> None:
        """push2_python heard from the Push. Called on its MIDI input thread."""
        self.connect_pending = True

    def poll(self) -> None:
        """Main loop, once per frame."""
        push = self.push

        if self.connect_pending:
            self.connect_pending = False
            try:
                self.on_connected()
            except Exception:
                logger.exception("Setting up the Push 2 failed")

        if not push.midi_is_configured():
            # Rate limited inside push2_python, so cheap to call every frame
            self.silent_since = None
            push.configure_midi()
            return

        if push.last_active_sensing_received is not None:
            self.silent_since = None
            return

        now = self.clock()
        if self.silent_since is None:
            self.silent_since = now
        elif now - self.silent_since >= SILENT_PORT_TIMEOUT:
            logger.warning(
                "No MIDI from the Push 2 for %.0f s, reopening its ports",
                SILENT_PORT_TIMEOUT,
            )
            self.close_midi_ports()

    def close_midi_ports(self) -> None:
        """Drop the Push's MIDI ports so the next poll() opens them again."""
        push = self.push
        for attr in ("midi_in_port", "midi_out_port"):
            port = getattr(push, attr, None)
            setattr(push, attr, None)
            if port is not None:
                try:
                    port.close()
                except Exception as e:
                    logger.warning("Closing Push 2 %s failed: %s", attr, e)
        # The next active sensing then counts as a fresh connection
        push.last_active_sensing_received = None
        self.silent_since = None
        self.connect_pending = False
