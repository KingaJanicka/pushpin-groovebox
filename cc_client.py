"""MIDI CC transport for device pages on engines that don't speak OSC.

Device pages, sequencer p-locks and the preset code all talk to an
instrument through ``instrument.osc["client"].send_message(address, value)``.
For Surge XT that is a ``SimpleUDPClient``, and Surge answers every change and
every ``/q<address>`` query by sending the value back, which is what keeps the
controls on the Push display (and the instrument's slot state) up to date.

``MidiCCClient`` has the same ``send_message`` and gives a MIDI-CC engine the
same behaviour:

* ``/cc/<n>`` with a value sends control change ``n`` on the instrument's MIDI
  port (the value is rounded and clamped to 0..127) and echoes the value back
  through the instrument's dispatcher, as Surge would.
* ``/q/cc/<n>`` replays the last value sent for ``/cc/<n>``, if any.
* Any other address (Surge's ``/patch/...``, ``/q/param/...``) is ignored.
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger("cc_client")

CC_ADDRESS = re.compile(r"^/cc/(\d{1,3})$")
QUERY_PREFIX = "/q"


def cc_number(address: str) -> int | None:
    """The CC number in a ``/cc/<n>`` address, or None for any other address."""
    match = CC_ADDRESS.match(address)
    if not match:
        return None
    n = int(match.group(1))
    return n if n <= 127 else None


def cc_value(value: Any) -> int:
    """A control's float value as a 7-bit CC value."""
    return int(round(min(max(float(value), 0.0), 127.0)))


class MidiCCClient:
    def __init__(self, midi_out: Any, dispatcher: Any, channel: int = 0) -> None:
        """``midi_out`` needs ``control(control, value, channel)`` (isobar's
        MidiOutputDevice has it); ``dispatcher`` is the instrument's
        python-osc Dispatcher, used for the echo."""
        self.midi_out = midi_out
        self.dispatcher = dispatcher
        self.channel = max(0, min(int(channel), 15))
        self.values: dict[str, float] = {}

    def send_message(self, address: str, value: Any) -> None:
        if address.startswith(QUERY_PREFIX + "/"):
            target = address[len(QUERY_PREFIX):]
            if target in self.values:
                self._echo(target, self.values[target])
            return

        cc = cc_number(address)
        if cc is None:
            logger.debug("ignoring %s %r: not a CC address", address, value)
            return
        if value is None:
            return
        self.midi_out.control(cc, cc_value(value), self.channel)
        self.values[address] = float(value)
        self._echo(address, float(value))

    def _echo(self, address: str, value: float) -> None:
        """Hand ``address value`` to the dispatcher's handlers, as an OSC reply would."""
        for handler in self.dispatcher.handlers_for_address(address):
            try:
                if handler.args:
                    handler.callback(address, handler.args, value)
                else:
                    handler.callback(address, value)
            except Exception:
                logger.exception("handler for %s failed", address)
