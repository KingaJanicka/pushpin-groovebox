"""MIDI CC transport for device pages on engines that don't speak OSC.

Device pages, sequencer p-locks and the preset code all talk to an
instrument through ``instrument.osc["client"].send_message(address, value)``.
For Surge XT that is a ``SimpleUDPClient``, and Surge answers every change and
every ``/q<address>`` query by sending the value back, which is what keeps the
controls on the Push display (and the instrument's slot state) up to date.

``MidiCCClient`` has the same ``send_message`` and gives a MIDI-CC engine the
same behaviour:

* ``/cc/<n>`` with a value sends control change ``n`` on the instrument's MIDI
  port and echoes the value back through the instrument's dispatcher, as Surge
  would. With ``nrpn=True`` it goes as a 14-bit NRPN (CC 99 = 0, CC 98 = n,
  CC 6 = whole part, CC 38 = fraction x 128), so a control's fractional value
  reaches the synth; CCs in ``plain_ccs`` (switches, not values) stay plain.
  Without NRPN the value is rounded and clamped to 0..127.
* ``/q/cc/<n>`` replays the last value sent for ``/cc/<n>``, if any.
* ``/mnote [note, velocity]`` and ``/mnote/rel [note, velocity]``, Surge's
  OSC notes, which the Push's pads send (``MelodicMode``), become note-on and
  note-off on the same port. The sequencer plays through that port already.
* Any other address (Surge's ``/patch/...``, ``/q/param/...``) is ignored.
"""
from __future__ import annotations

import logging
import re
import threading
from typing import Any, Iterable

logger = logging.getLogger("cc_client")

CC_ADDRESS = re.compile(r"^/cc/(\d{1,3})$")
QUERY_PREFIX = "/q"
NOTE_ON_ADDRESS = "/mnote"
NOTE_OFF_ADDRESS = "/mnote/rel"


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


def nrpn_value(value: Any) -> tuple[int, int]:
    """A control's float value as NRPN data entry: (whole part, fraction in 1/128)."""
    v = min(max(float(value), 0.0), 127.0)
    whole = int(v)
    fraction = int(round((v - whole) * 128))
    if fraction == 128:
        whole, fraction = whole + 1, 0
    if whole >= 127:
        return 127, 0
    return whole, fraction


class MidiCCClient:
    def __init__(
        self,
        midi_out: Any,
        dispatcher: Any,
        channel: int = 0,
        nrpn: bool = False,
        plain_ccs: Iterable[int] = (),
    ) -> None:
        """``midi_out`` needs ``control(control, value, channel)`` (isobar's
        MidiOutputDevice has it); ``dispatcher`` is the instrument's
        python-osc Dispatcher, used for the echo."""
        self.midi_out = midi_out
        self.dispatcher = dispatcher
        self.channel = max(0, min(int(channel), 15))
        self.nrpn = nrpn
        self.plain_ccs = frozenset(plain_ccs)
        self.values: dict[str, float] = {}
        # An NRPN is four messages; the encoders and the sequencer send from
        # different threads, and interleaved halves would set the wrong parameter.
        self._send_lock = threading.Lock()

    def send_message(self, address: str, value: Any) -> None:
        if address in (NOTE_ON_ADDRESS, NOTE_OFF_ADDRESS):
            self._send_note(address == NOTE_ON_ADDRESS, value)
            return
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
        self._send(cc, value)
        self.values[address] = float(value)
        self._echo(address, float(value))

    def _send_note(self, on: bool, value: Any) -> None:
        try:
            note, velocity = (int(round(float(v))) for v in list(value)[:2])
        except (TypeError, ValueError):
            logger.debug("ignoring note %r: not [note, velocity]", value)
            return
        if not 0 <= note <= 127:
            return
        with self._send_lock:
            if on and velocity > 0:
                self.midi_out.note_on(note, min(velocity, 127), self.channel)
            else:
                self.midi_out.note_off(note, self.channel)

    def _send(self, cc: int, value: Any) -> None:
        if not self.nrpn or cc in self.plain_ccs:
            self.midi_out.control(cc, cc_value(value), self.channel)
            return
        whole, fraction = nrpn_value(value)
        with self._send_lock:
            # The parameter is chosen every time: a restarted synth has forgotten it.
            self.midi_out.control(99, 0, self.channel)
            self.midi_out.control(98, cc, self.channel)
            self.midi_out.control(6, whole, self.channel)
            self.midi_out.control(38, fraction, self.channel)

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
