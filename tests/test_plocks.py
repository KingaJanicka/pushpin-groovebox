"""P-locks: which step a held pad records on, which control an encoder locks,
and that playback sends each lock to the control it was recorded on.

Regressions for: a quick tap leaving its step "held" for good (the press ran
from a queue, after its release), the lock step coming from a second list that
mode switches never cleared, the encoder locking the flat control list instead
of the page shown, and playback reading only the page on screen.
"""
import asyncio
from unittest.mock import MagicMock

import push2_python.constants
import pytest

from app import PyshaApp
from definitions import TRACK_NAMES_METRO
from modes.metro_sequencer_mode import MetroSequencerMode
from osc_controls import ControlSpacer
from sequencer.sequencer_metro import SequencerMetro, lockable_controls, LOCKS_PER_DEVICE
from sequencer.sequencer_params import SequencerParams

ENCODER_1 = push2_python.constants.ENCODER_TRACK1_ENCODER
ENCODER_3 = push2_python.constants.ENCODER_TRACK3_ENCODER


def pad_n(column, row_from_bottom=0):
    return 36 + row_from_bottom * 8 + column


def pad_ij(column, row_from_bottom=0):
    return (7 - row_from_bottom, column)


def control(value=0.5, lo=0.0, hi=1.0):
    c = MagicMock(spec=["value", "min", "max", "address", "name"])
    c.value, c.min, c.max, c.address, c.name = value, lo, hi, "/param/x", "Control"
    return c


class FakeSeq:
    """The lock store of SequencerMetro, keyed (step, parameter) for one device."""

    def __init__(self):
        self.locks = {}

    def get_lock_state(self, step, param):
        return self.locks.get((step, param))

    def set_lock_state(self, step, param, value):
        self.locks[(step, param)] = value


@pytest.fixture
def metro(app, mocker):
    mocker.patch.object(MetroSequencerMode, "initialize")
    app.instrument_selection_mode.selected_instrument = 0
    app.queue = []
    app.steps_held = []
    app.active_modes = [MagicMock()]
    mode = MetroSequencerMode(app, settings=None, send_osc_func=app.send_osc)
    mode.get_current_instrument_short_name_helper = lambda: "INST1"
    mode.selected_track = TRACK_NAMES_METRO[3]        # gate
    gate = [[False] * 8 for _ in range(8)]
    mode.metro_seq_pad_state = {"INST1": {TRACK_NAMES_METRO[3]: gate}}
    mode.instrument_sequencers = {"INST1": FakeSeq()}
    mode.pads_press_time = [False] * 64
    mode.steps_held = []
    mode.show_scale_menu = False
    mode.disable_controls = False
    mode.encoder_incr_since_held = [False] * 8
    return mode


def run_queue(app):
    async def drain():
        for coro in app.queue:
            await coro
        app.queue.clear()
    asyncio.run(drain())


def press(metro, column):
    metro.on_pad_pressed(pad_n(column), pad_ij(column), 127)


def release(metro, column):
    metro.on_pad_released(pad_n(column), pad_ij(column), 0)


# --- which step is held ------------------------------------------------------

def test_quick_tap_released_before_its_queued_press_leaves_nothing_held(metro, app):
    press(metro, 5)
    release(metro, 5)            # before the queued press has run
    run_queue(app)
    assert app.steps_held == []
    assert metro.steps_held == []
    assert metro.disable_controls is False


def test_lock_goes_to_the_pad_under_the_finger_after_a_quick_tap(metro, app):
    device = MagicMock(page=0)
    device.get_visible_controls.return_value = [control()]
    app.osc_mode.get_current_instrument_device.return_value = device
    press(metro, 5); release(metro, 5); run_queue(app)     # a quick tap on step 5
    press(metro, 2); run_queue(app)                        # then hold step 2
    metro.on_encoder_rotated(ENCODER_1, 10)
    seq = metro.instrument_sequencers["INST1"]
    assert set(seq.locks) == {(2, 0)}


def test_mode_switch_while_held_does_not_leave_a_stale_step(metro, app):
    device = MagicMock(page=0)
    device.get_visible_controls.return_value = [control()]
    app.osc_mode.get_current_instrument_device.return_value = device
    press(metro, 6); run_queue(app)
    metro.deactivate(); metro.activate()                   # switched away and back
    release(metro, 6)                                      # must not raise
    press(metro, 1); run_queue(app)
    metro.on_encoder_rotated(ENCODER_1, 10)
    assert set(metro.instrument_sequencers["INST1"].locks) == {(1, 0)}


def test_releasing_one_of_two_held_pads_keeps_controls_disabled(metro, app):
    press(metro, 1); press(metro, 2); run_queue(app)
    release(metro, 1)
    assert app.steps_held == [2]
    assert metro.disable_controls is True


# --- which control the encoder locks -----------------------------------------

def test_encoder_locks_the_control_on_the_page_shown(metro, app):
    flat_first = control(value=0.9)
    shown = control(value=0.2)
    device = MagicMock(page=1)
    device.controls = [flat_first] * 16                    # the flat list: wrong one
    device.get_visible_controls.return_value = [control(), control(), shown]
    app.osc_mode.get_current_instrument_device.return_value = device
    press(metro, 3); run_queue(app)
    metro.on_encoder_rotated(ENCODER_3, 10)
    seq = metro.instrument_sequencers["INST1"]
    # page 1, encoder 3 -> parameter 8 + 2, starting from the shown control's value
    assert seq.locks == {(3, 10): pytest.approx(0.2 + 10 / 100)}


def test_first_turn_of_a_new_lock_moves_the_value(metro, app):
    device = MagicMock(page=0)
    device.get_visible_controls.return_value = [control(value=0.5)]
    app.osc_mode.get_current_instrument_device.return_value = device
    press(metro, 0); run_queue(app)
    metro.on_encoder_rotated(ENCODER_1, -5)
    assert metro.instrument_sequencers["INST1"].locks[(0, 0)] == pytest.approx(0.45)


def test_encoder_past_a_short_page_or_on_a_spacer_locks_nothing(metro, app):
    device = MagicMock(page=0)
    device.get_visible_controls.return_value = [ControlSpacer()]
    app.osc_mode.get_current_instrument_device.return_value = device
    press(metro, 0); run_queue(app)
    metro.on_encoder_rotated(ENCODER_1, 10)
    metro.on_encoder_rotated(ENCODER_3, 10)
    assert metro.instrument_sequencers["INST1"].locks == {}


# --- playback ----------------------------------------------------------------

def paged_device(pages, page_shown=0):
    device = MagicMock()
    device.pages = pages
    device.page = page_shown
    device.get_visible_controls.return_value = pages[page_shown]
    device.init = []
    return device


def test_lockable_controls_index_every_page_by_page_and_position():
    a, b, c = control(), control(), control()
    page0 = [a] + [ControlSpacer() for _ in range(7)]
    device = paged_device([page0, [b, c]])
    indexed = dict((i, ctl) for i, ctl in lockable_controls(device))
    assert indexed[0] is a and indexed[8] is b and indexed[9] is c


def test_lockable_controls_stop_at_the_lock_store_size():
    pages = [[control() for _ in range(8)] for _ in range(3)]
    indices = [i for i, _ in lockable_controls(paged_device(pages))]
    assert max(indices) == LOCKS_PER_DEVICE - 1


@pytest.fixture
def seq(app):
    s = SequencerMetro.__new__(SequencerMetro)
    s.app = app
    s.name = "INST1"
    s.locks = [[[None] * LOCKS_PER_DEVICE for _ in range(17)] for _ in range(64)]
    s.gate = ["Off"] * 64                      # locks still play with the gate off
    s.lock_scale = [7] * 64
    s.mutes_skips = [False] * 64
    s.controls_to_reset = []
    s.next_step_index = 1
    s.step_index = 0
    s.timeline = MagicMock()
    s.params = SequencerParams(sequencer_is_playing=True)
    return s


def test_playback_sends_a_page_two_lock_to_its_control_whatever_page_is_shown(seq, app):
    page0 = [control() for _ in range(8)]
    page1 = [control() for _ in range(8)]
    page0[2].address, page1[2].address = "/page0/c2", "/page1/c2"
    for shown in (0, 1):
        device = paged_device([page0, page1], page_shown=shown)
        instrument = MagicMock(slots=[None, None, None])   # slot 2: always shown
        instrument.devices = {2: [device]}
        instrument.engine = MagicMock(always_shown_slots=(2,))
        app.instruments = {"INST1": instrument}
        seq.locks[0][2] = [None] * LOCKS_PER_DEVICE
        seq.locks[0][2][8 + 2] = 0.9                       # recorded on page 1, encoder 3
        seq.controls_to_reset = []
        app.send_osc.reset_mock()
        seq.evaluate_and_play_notes()
        sent = [c.args[0] for c in app.send_osc.call_args_list]
        assert sent == ["/page1/c2"], f"page {shown} shown"


# --- the app's task queue ----------------------------------------------------

def test_queue_tasks_starts_every_queued_task_in_one_frame():
    app = PyshaApp.__new__(PyshaApp)
    app.queue = []
    app.tasks = set()
    ran = []

    async def job(n):
        ran.append(n)

    async def frame():
        app.queue.extend(job(n) for n in range(5))
        await app.queue_tasks()
        await asyncio.sleep(0)
        return list(app.queue)

    assert asyncio.run(frame()) == []
    assert sorted(ran) == [0, 1, 2, 3, 4]
