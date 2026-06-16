"""Shared pytest fixtures for the pushpin-groovebox test suite.

The ``Mode`` classes are tightly coupled to the hardware (a Push 2 controller
exposed through ``self.app.push``) and to a large ``PyshaApp`` instance passed in
as ``app``.  None of that is available in a unit-test environment, so this module
provides light-weight mock stand-ins:

* ``push``    - a ``MagicMock`` standing in for the Push 2 hardware wrapper.
* ``app``     - a ``MagicMock`` standing in for ``PyshaApp`` with the attributes
                and sub-modes the Mode classes touch most often pre-configured to
                sensible, assertable values.

Tests can freely override any return value, e.g.::

    app.instrument_selection_mode.get_current_instrument_short_name.return_value = "BASS"

Because the real ``Mode`` classes keep a lot of *class-level* mutable state
(e.g. ``MelodicMode.notes_being_played = []``), the ``reset_mode_state`` autouse
fixture clears those between tests so one test can't leak into the next.
"""

import sys
import os
from unittest.mock import MagicMock

import pytest

# Make sure the project root is importable regardless of where pytest is invoked
# from (mirrors the `pythonpath = .` setting in pytest.ini as a belt-and-braces).
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import definitions  # noqa: E402  (import after sys.path tweak)


# A representative instrument-info dict, matching the shape produced by
# InstrumentSelectionMode.create_instruments().
DEFAULT_INSTRUMENT_INFO = {
    "instrument_name": "Test Synth",
    "instrument_short_name": "INST1",
    "midi_channel": 1,
    "osc_in_port": 7000,
    "osc_out_port": 7001,
    "color": definitions.CYAN,
    "n_banks": 1,
    "bank_names": None,
    "default_layout": definitions.LAYOUT_MELODIC,
    "illuminate_local_notes": True,
    "instrument_index": 0,
}


@pytest.fixture
def push():
    """Mock Push 2 hardware wrapper (``app.push``)."""
    return MagicMock(name="push")


@pytest.fixture
def app(push):
    """Mock PyshaApp configured with the attributes the Mode classes use."""
    app = MagicMock(name="app")
    app.push = push

    # Plain flags the modes flip.
    app.pads_need_update = False
    app.buttons_need_update = False
    app.notes_midi_in = None
    app.steps_held = []

    # Instrument selection sub-mode - the most widely consumed dependency.
    ism = app.instrument_selection_mode
    ism.get_current_instrument_color.return_value = definitions.CYAN
    ism.get_current_instrument_info.return_value = dict(DEFAULT_INSTRUMENT_INFO)
    ism.get_current_instrument_short_name.return_value = "INST1"
    ism.get_all_distinct_instrument_short_names.return_value = ["INST1", "INST2"]

    # Metronome sequencer sub-mode (transport state used by PLAY button handlers).
    app.metro_sequencer_mode.sequencer_is_playing = False

    return app


@pytest.fixture(autouse=True)
def reset_mode_state():
    """Reset class-level mutable state on Mode classes between tests.

    Several Mode classes declare mutable containers at *class* scope (a latent
    bug we may address later under "reduce bug density"). Until then, clear them
    so tests are independent.
    """
    yield

    # Imported lazily so that conftest import never fails if a module is absent.
    try:
        from modes.melodic_mode import MelodicMode

        MelodicMode.notes_being_played = []
    except Exception:
        pass
