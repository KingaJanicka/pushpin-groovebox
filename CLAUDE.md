# CLAUDE.md

Guidance for working in **pushpin-groovebox** — a Python app that turns an
Ableton Push 2 into a standalone groovebox / sequencer driving Surge XT (and
other synths) over OSC and MIDI.

## Project goal (current focus)

In priority order:

1. **Improve test coverage and code quality.**
2. **Reduce bug density.**

A unit-test suite was recently established (see below). The next phase is
acting on the bugs/quirks it surfaced (listed at the bottom of this file).

## Architecture, in brief

- `pysha.py` / `PyshaApp` is the host. It wires up the hardware (`self.push`,
  a `push2_python` wrapper) and a stack of **Mode** objects created in
  `PyshaApp.init_modes()`.
- Modes live in `modes/` and subclass `definitions.PyshaMode`
  (`__init__(self, app, settings=None)`; `self.push` is a **property**
  returning `self.app.push`). Note/sequencer modes subclass
  `modes/melodic_mode.py::MelodicMode`, whose `__init__` adds a
  `send_osc_func` arg.
- Controls shown on the Push display are `osc_controls.py` objects
  (`OSCControl`, `OSCControlMacro`, `OSCControlSwitch`, `OSCControlMenu`,
  `OSCGroup`, `ControlSpacer`). Devices are `modes/osc_device.py::OSCDevice`.
- `definitions.py` holds shared constants: `TRACK_NAMES`, `TRACK_NAMES_METRO`,
  colors, layout names, and patch-folder paths.

## Environment / running

This repo uses **pyenv**. Use the `pushpin` virtualenv (Python 3.11), which has
the app dependencies installed (`push2_python` from git, `isobar`, `mido`,
`pycairo`, `pyusb`, `python-osc`, …). `requirements.txt` is the source of truth
and already includes the test deps (`pytest`, `pytest-mock`, `pytest-cov`).

Invoke tools through `python -m` so the run never depends on a `pip`/`pytest`
shim being on PATH:

```bash
cd ~/Projects/pushpin-groovebox
pyenv local pushpin                  # or: pyenv activate pushpin
python -m pytest                     # run the suite
python -m pytest --cov --cov-report=term-missing
```

Importing any mode pulls in `cairo` via `user_interface/display_utils.py`, so
the cairo system lib must be present (`brew install cairo pkg-config libusb`).
The tests never actually render or touch hardware, but the import must succeed.

## Test suite layout

Config: `pytest.ini` (`pythonpath = .`, `testpaths = tests`,
`python_files = test_*.py`) and `.coveragerc`. Stray `tests/test.py` and
`tests/isobar-test.py` are NOT collected (they don't match `test_*.py`).

`tests/conftest.py` provides the shared harness:

- **`push`** fixture — a `MagicMock` for the Push 2 hardware wrapper.
- **`app`** fixture — a `MagicMock` `PyshaApp` with `app.push` wired to the
  `push` fixture (important: `Mode.push` *is* `app.push`), plus the most-used
  sub-mode return values pre-set (`instrument_selection_mode`, transport flags,
  `steps_held`, etc.).
- **`reset_mode_state`** (autouse) — clears class-level mutable state between
  tests.

Key testing patterns (see `tests/README.md` for the full map):

- Modes whose `initialize()` does disk I/O or builds heavy objects
  (`OSCMode`, `SequencerMode`, `MetroSequencerMode`, `PresetSelectionMode`,
  `ClipSelectionMode`, `TrigEditMode`, `InstrumentSelectionMode`) have
  `initialize`/`create_instruments` patched out; tests then set the minimal
  state each method needs.
- Many modes keep **mutable state at class scope**, so per-test fixtures reset
  those class attributes before constructing the mode.
- All 16 mode classes from `init_modes()` have coverage, plus the pre-existing
  `test_osc_controls.py` and `test_osc_device.py`.

## Known bugs / quirks found while writing tests

Candidates for the "reduce bug density" phase. The tests currently assert
**actual** behavior (a deliberate choice), so changing the code will require
updating the corresponding test.

1. **Class-level mutable state shared across instances.** e.g.
   `MelodicMode.notes_being_played`, `MuteMode.tracks_active`,
   `TrigEditMode.controls`/`state`, `InstrumentSelectionMode.instruments_info`,
   and the `instrument_sequencers` dicts. These accumulate across
   instances/re-inits. Likely should be instance attributes set in
   `initialize()`.

2. **`OSCControlMenu` seeds its index from `onselect.value`.** In
   `osc_controls.py`, `self.value = self.message["value"]` means a menu with a
   top-level `onselect` starts on a non-zero item (conflates "init OSC value"
   with "menu index"). Suspected bug — see `test_OSCControlMenu`.

3. **Substring `in` checks on button names.** In `preset_selection_mode.py` and
   `clip_selection_mode.py`: `elif button_name in push2_python.constants.BUTTON_UPPER_ROW_7:`
   does a string-substring match, not equality. Works by luck for current
   button names; should be `==`.

4. **Control value model is fractional/"twitchy."** `OSCControl`/menu/switch
   `update_value()` add `scale_value(increment, …)` (increment / 127 × range),
   so a single encoder click nudges values by a tiny fraction; advancing a
   menu/switch integer index takes a large increment. Intentional mitigation,
   but worth revisiting for UX.

5. **Stale-test drift is real.** `OSCDevice` config now uses the `"controls"`
   key (was `"osc"`) and requires `app`, `osc_in_port`, `osc_out_port` kwargs;
   control self-population moved from `__init__` to `query()`; control defaults
   are `0.0` (were `64`). The pre-existing osc tests were updated to match.

## Conventions

- Don't introduce hardware/USB/cairo dependencies into unit tests — keep them
  mockable.
- When you change a control's value model or a mode's `initialize()`, expect to
  update the matching test and re-run `python -m pytest`.
