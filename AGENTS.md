# AGENTS.md

Guidance for AI agents working in **pushpin-groovebox** — a Python app that
turns an Ableton Push 2 into a standalone groovebox / sequencer driving Surge XT
(and other synths) over OSC and MIDI.

---

## Project purpose

The app runs on a Raspberry Pi (target) and a developer Mac (dev). It owns the
Push 2 as a hardware controller, drives Surge XT synthesiser instances over OSC,
and sequences them with a custom MIDI/step sequencer. The user interacts
exclusively through the Push 2 pads, buttons, and encoders; the Push 2 display
is the only screen.

---

## Repository layout

```
app.py                  PyshaApp — the host / event loop
definitions.py          Shared constants, path strings, PyshaMode base class
osc_controls.py         OSC control widgets (knobs, switches, menus, macros)
engine.py               SurgeXTEngine — spawns and manages a surge-xt-cli process
modes/                  One file per Mode class (see below)
  instrument.py         Instrument — per-synth OSC client/server + device slots
  osc_device.py         OSCDevice — a panel of OSC controls for one synth slot
  osc_mode.py           OSCMode — routes OSC messages to the right instrument
  preset_selection_mode.py  Preset browser and slot management
  metro_sequencer_mode.py   Main step sequencer
  clip_selection_mode.py    Clip / pattern management
  melodic_mode.py       Base for melodic/rhythmic/slice pad layouts
  ...
user_interface/
  display_utils.py      Cairo text/graphic helpers
  display_process.py    Subprocess that renders frames without blocking the GIL
  recording_context.py  Audio recording helpers
tests/                  pytest suite — see Tests section below
definitions/
  device_definitions/   JSON config files, one per synth device type
controllers/
  push2_constants.py    Push 2 button/encoder name constants
```

---

## Branch and PR rules

- **`dev`** is the integration branch. All PRs target `dev`, never `main`.
- `main` is the stable release branch; merges from `dev` are batched.
- Always open PRs against `dev`. If you accidentally target `main`, close and
  re-open.

---

## Environment

This repo uses **pyenv**. The correct virtualenv is `pushpin` (Python 3.11).

```bash
pyenv local pushpin          # pin the directory, or:
pyenv activate pushpin

python -m pytest             # run the test suite
python -m pytest --cov --cov-report=term-missing
```

Always invoke through `python -m` — do not rely on a bare `pytest` shim.

Cairo (via `pycairo`) must be importable even in tests. Install system deps if
needed:

```bash
brew install cairo pkg-config libusb   # macOS
# apt install libcairo2-dev libusb-1-dev  # Debian/Pi
```

---

## Architecture

### PyshaApp (`app.py`)

The host object. It:

- Owns `self.push` (a `push2_python` wrapper for the hardware)
- Creates all Mode instances in `init_modes()`
- Runs an `asyncio` event loop; hardware callbacks arrive on the main thread
- Maintains `self.queue: list` — a list of coroutines that are
  `asyncio.create_task`'d each loop tick (see below)
- Maintains `self.instruments: dict[str, Instrument]` keyed by short name

### PyshaMode (`definitions.py`)

Base class for every mode. Key interface:

| Method | Called when |
|--------|-------------|
| `initialize(settings)` | App startup — do disk I/O and heavy setup here |
| `activate()` | Mode becomes the active mode — set button/pad lights |
| `deactivate()` | Mode is switched away from — clean up lights |
| `update_display(ctx, w, h)` | Each display frame — draw with Cairo |
| `update_pads()` | Pads need a colour refresh |
| `update_buttons()` | Buttons need a colour refresh |
| `on_pad_pressed(pad_n, pad_ij, velocity)` | Pad pressed |
| `on_pad_released(pad_n, pad_ij, velocity)` | Pad released |
| `on_button_pressed(button_name)` | Button pressed |
| `on_button_released(button_name)` | Button released |
| `on_encoder_rotated(encoder_name, increment)` | Encoder turned |

`self.push` is a **property** returning `self.app.push` — always use it
rather than caching `app.push` in a local.

`self.send_osc(address, value, instrument_shortname=...)` routes an OSC
message to the correct Surge XT instance for the given instrument.

### The async queue

`app.queue` is consumed each loop iteration as `asyncio.create_task`. Append a
coroutine to it from synchronous code to schedule async work without blocking:

```python
self.app.queue.append(self._my_async_method(arg))
```

This is the correct pattern when you need `asyncio.sleep` between OSC sends
(e.g. waiting for Surge replies before reading state). See
`preset_selection_mode.py::_refresh_devices_after_preset_load` for a worked
example.

### Instrument and OSC device model

Each synth instance is an `Instrument` (`modes/instrument.py`):

- `instrument.slots` — list of 16 slot dicts `{"address": "/param/…", "value": float}`;
  updated when Surge replies to `/q` queries. Slots determine which `OSCDevice`
  panels are active.
- `instrument.current_devices` — list of `OSCDevice` objects currently active
  (populated by `update_current_devices()` from `slots`).
- `instrument.query_slots()` — sends `/q<address>` for each slot. **Async** —
  replies arrive via OSC callbacks. Always `await asyncio.sleep(0.5)` before
  reading `slots` after calling this.
- `instrument.update_current_devices()` — rebuilds `current_devices` from
  `slots`. Must be called *after* slot replies have arrived.
- `instrument.init_devices_sync()` — sends fixed init commands from device JSON
  for each active device. Uses current `slots`/`current_devices`, so call after
  `update_current_devices()`.

**OSC timing rule**: never call `query_slots()` and then immediately read
`slots` or call `update_current_devices()`. Insert at least `asyncio.sleep(0.5)`
between them so Surge's UDP replies can arrive. Use the async queue pattern
(above) whenever you need this in synchronous handler code.

### Preset system

- `presets.json` — maps instrument short names to lists of 8 preset paths
  (factory `.fxp` file paths, without extension).
- `surge_state/` folder — per-instrument per-slot `.fxp` files named
  `{instrument}_{index}`, holding the last saved synth state for each pad slot.
- Loading a pad slot: send `/patch/load <surge_state_path>` to Surge.
- Saving a browsed preset to a slot:
  1. `/patch/load <factory_path>` — load the new preset into Surge
  2. `time.sleep(0.5)` — wait for Surge to finish loading
  3. `/patch/save <surge_state_path>` — save it into the slot file
  4. Update `presets.json` via `save_presets()`

### Device definitions (JSON)

`definitions/device_definitions/*.json` configure each synth device panel.
Each file lists controls (`"controls"` key) and init commands (`"init"` key).
The `"slot"` field links the device to a slot index in `Instrument.slots`.

Init commands are sent by `device.select_sync()` / `device.select()` and
determine which OSC device panel is shown for a given slot value. If you add
a new device type, it needs a JSON definition file and a matching entry in the
instrument definition.

---

## OSC controls (`osc_controls.py`)

| Class | Purpose |
|-------|---------|
| `OSCControl` | Single continuous parameter (knob) |
| `OSCControlMacro` | One knob driving multiple OSC addresses |
| `OSCControlSwitch` | Integer-valued toggle that switches between `OSCGroup` pages |
| `OSCControlMenu` | Menu selecting from a list of items |
| `OSCSpacerAddress` | A spacer that also listens to an OSC address |
| `ControlSpacer` | Visual gap, no OSC |
| `OSCGroup` | Named group of controls shown when a switch is active |

Controls are added to an `OSCDevice` from its JSON definition. `update_value(increment)`
scales by `increment / 127 × range` — a single encoder tick produces a small
fractional change, which is intentional.

---

## Tests

Config: `pytest.ini` + `.coveragerc`. Do not run `tests/test.py` or
`tests/isobar-test.py` directly — they are not collected (names don't match
`test_*.py`).

### Shared fixtures (`tests/conftest.py`)

- **`push`** — `MagicMock` for the Push 2 hardware wrapper.
- **`app`** — `MagicMock` PyshaApp with pre-configured sub-modes, `steps_held`,
  transport flags, etc. `app.push` is wired to the `push` fixture.
- **`reset_mode_state`** (autouse) — clears class-level mutable state between
  tests.

### Key patterns

- Modes with heavy `initialize()` (disk I/O, instrument setup) have
  `initialize` / `create_instruments` **patched out**. Tests set the minimal
  state the method under test actually needs.
- Class-level mutable defaults must be **reset per test** — the autouse fixture
  handles the known ones, but add new resets if you add new class-level state.
- Never import hardware drivers, USB, or Cairo directly in tests — keep all
  dependencies mockable.
- After changing a mode's behaviour, run `python -m pytest` and update the
  matching test to assert the new behaviour (tests assert actual, not ideal,
  behaviour by design).

### Pre-existing known failure

`tests/test_clip_selection_mode.py::test_get_preset_path_factory` fails because
`ClipSelectionMode.get_preset_path` no longer exists. This is a pre-existing
stale test, not caused by other changes — do not treat it as a regression.

---

## Common tasks

### Adding a new Mode

1. Create `modes/my_mode.py`, subclass `definitions.PyshaMode`.
2. Implement `initialize()`, `activate()`, `deactivate()`, and whichever
   `on_*` / `update_*` methods you need.
3. Register it in `PyshaApp.init_modes()` in `app.py`.
4. Add a test file `tests/test_my_mode.py` following the conftest patterns.

### Changing a button light

Call `self.push.buttons.set_button_color(button_name, color)` from
`update_buttons()`. Always clear the light in `deactivate()` so it doesn't
bleed into the next mode.

Button name constants live in `controllers/push2_constants.py` and also in
`push2_python.constants`.

### Sending OSC to Surge

```python
# From a Mode:
self.send_osc("/param/a/osc/1/type", 10.0, instrument_shortname="tw1")

# From non-Mode code with an Instrument reference:
instrument.send_message("/patch/load", preset_path)
```

### Queueing async work from a synchronous handler

```python
def on_pad_released(self, pad_n, pad_ij, velocity):
    self.app.queue.append(self._do_async_work())

async def _do_async_work(self):
    self.send_osc("/patch/load", path, instrument_shortname=self.instrument)
    await asyncio.sleep(0.5)
    instrument.query_slots()
    await asyncio.sleep(0.5)
    instrument.update_current_devices()
```

### Checking if a preset exists / loading fallback

Use `_resolve_preset(path)` in `PresetSelectionMode` — it returns `path` if
non-empty, otherwise `DEFAULT_PRESET` (`Init Saw`). Apply it wherever you
read from `self.presets[instrument][index]` before splitting or loading.

---

## Known bugs / debt (do not silently work around)

These are open issues; fix them properly rather than patching over symptoms:

1. **Class-level mutable state** — `MelodicMode.notes_being_played`,
   `MuteMode.tracks_active`, `TrigEditMode.controls/state`,
   `InstrumentSelectionMode.instruments_info` are class attributes that
   accumulate across instances. Should be instance attributes set in
   `initialize()`.

2. **`OSCControlMenu` index seeded from `onselect.value`** — conflates the
   initial OSC value with the menu selection index; a menu with a non-zero
   `onselect` value starts on the wrong item.

3. **Substring `in` checks on button names** — `button_name in
   push2_python.constants.BUTTON_UPPER_ROW_7` is a string substring test, not
   equality. Should be `==`.

4. **Control value is fractional** — `update_value()` advances by
   `increment / 127 × range`, so reaching an integer index on a switch/menu
   requires a large encoder movement. Worth revisiting for UX.
