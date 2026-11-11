"""Reconnect path for the Push 2: late plug-in, unplug/replug, silent ports.

No hardware: ``push`` is a MagicMock standing in for push2_python.Push2, with
the few real attributes PushConnection reads (MIDI ports, last active sensing).
"""

from unittest.mock import MagicMock

import pytest

from push_connection import SILENT_PORT_TIMEOUT, PushConnection


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def push():
    p = MagicMock()
    p.midi_in_port = None
    p.midi_out_port = None
    p.last_active_sensing_received = None
    p.midi_is_configured.side_effect = lambda: (
        p.midi_in_port is not None and p.midi_out_port is not None
    )
    return p


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def setup():
    return MagicMock(name="on_midi_push_connection_established")


@pytest.fixture
def conn(push, setup, clock):
    return PushConnection(push, setup, clock=clock)


def plug_in(push):
    """What configure_midi() does once the Push's ports exist."""

    def configure():
        push.midi_in_port = push.midi_in_port or MagicMock(name="in")
        push.midi_out_port = push.midi_out_port or MagicMock(name="out")

    push.configure_midi.side_effect = configure


def hear_from_push(push, conn, clock):
    """push2_python got active sensing and fired on_midi_connected."""
    push.last_active_sensing_received = clock.now
    conn.notify_connected()


def test_no_push_keeps_trying_to_open_ports(push, conn, setup):
    conn.poll()
    conn.poll()
    assert push.configure_midi.call_count == 2
    setup.assert_not_called()


def test_late_plug_in_sets_push_up_on_main_loop(push, conn, setup, clock):
    conn.poll()  # no Push yet
    plug_in(push)
    conn.poll()  # ports open
    assert push.midi_is_configured()

    hear_from_push(push, conn, clock)
    # The MIDI thread only flags it: nothing drawn from that thread
    setup.assert_not_called()

    conn.poll()
    setup.assert_called_once_with()

    conn.poll()
    setup.assert_called_once_with()  # once per connection


def test_setup_failure_does_not_stop_the_main_loop(push, conn, setup, clock):
    plug_in(push)
    conn.poll()
    setup.side_effect = RuntimeError("palette sysex failed")
    hear_from_push(push, conn, clock)
    conn.poll()  # logged, not raised
    setup.assert_called_once()


def test_connected_push_is_left_alone(push, conn, clock):
    plug_in(push)
    conn.poll()
    hear_from_push(push, conn, clock)
    conn.poll()
    in_port, out_port = push.midi_in_port, push.midi_out_port

    for _ in range(10):
        clock.now += SILENT_PORT_TIMEOUT
        push.last_active_sensing_received = clock.now
        conn.poll()

    assert push.midi_in_port is in_port and push.midi_out_port is out_port
    in_port.close.assert_not_called()


def test_ports_that_never_hear_the_push_are_reopened(push, conn, setup, clock):
    # Ports opened while the Push was still booting, and nothing ever arrives
    plug_in(push)
    conn.poll()
    in_port, out_port = push.midi_in_port, push.midi_out_port

    conn.poll()  # silence starts being timed
    clock.now += SILENT_PORT_TIMEOUT - 0.1
    conn.poll()
    assert push.midi_in_port is in_port  # not yet

    clock.now += 0.2
    conn.poll()
    in_port.close.assert_called_once()
    out_port.close.assert_called_once()
    assert push.midi_in_port is None and push.midi_out_port is None

    conn.poll()  # reopened fresh
    assert push.midi_in_port is not None and push.midi_in_port is not in_port

    hear_from_push(push, conn, clock)
    conn.poll()
    setup.assert_called_once()


def test_unplug_then_replug_reopens_ports_and_sets_push_up_again(
    push, conn, setup, clock
):
    plug_in(push)
    conn.poll()
    hear_from_push(push, conn, clock)
    conn.poll()
    old_in = push.midi_in_port

    # Unplugged: push2_python's active-sensing check clears this
    push.last_active_sensing_received = None
    conn.poll()
    clock.now += SILENT_PORT_TIMEOUT
    conn.poll()
    old_in.close.assert_called_once()
    assert not push.midi_is_configured()

    conn.poll()  # replugged: ports reopen
    hear_from_push(push, conn, clock)
    conn.poll()
    assert push.midi_in_port is not old_in
    assert setup.call_count == 2


def test_brief_gap_in_active_sensing_does_not_reopen(push, conn, clock):
    plug_in(push)
    conn.poll()
    hear_from_push(push, conn, clock)
    conn.poll()
    in_port = push.midi_in_port

    push.last_active_sensing_received = None  # a late active sensing
    conn.poll()
    clock.now += 1.0
    push.last_active_sensing_received = clock.now  # it came back
    conn.poll()
    clock.now += SILENT_PORT_TIMEOUT
    conn.poll()

    in_port.close.assert_not_called()


def test_close_midi_ports_resets_state_even_if_close_raises(push, conn):
    bad = MagicMock()
    bad.close.side_effect = OSError("port vanished")
    push.midi_in_port = bad
    push.midi_out_port = MagicMock()
    push.last_active_sensing_received = 5.0
    conn.connect_pending = True

    conn.close_midi_ports()

    assert push.midi_in_port is None and push.midi_out_port is None
    assert push.last_active_sensing_received is None
    assert conn.connect_pending is False
