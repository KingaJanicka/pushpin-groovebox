# AGENTS.md

Guidance for AI agents working in **pushpin-groovebox** — a Python app that
turns an Ableton Push 2 into a standalone groovebox / sequencer driving Surge XT
(and other synths) over OSC and MIDI.

This document is a full handover. Read it before touching any code.

---

## What this project is

The app runs on a Raspberry Pi (target hardware) and is developed on macOS.
It has no GUI: the only user-facing interface is the Ableton Push 2 controller.
The Push 2's pads, buttons, and encoders are the entire UX; the Push 2 display
(rendered via Cairo in a subprocess) is the only screen.

The app drives multiple Surge XT synthesiser instances. Each synth instance is
spawned as `surge-xt-cli` and controlled entirely over OSC (UDP). MIDI is used
only for triggering notes (via isobar timelines).

**Everything in the display, all pad colours, all button lights — this code
owns them completely. Nothing is handled by the hardware automatically.**

---

## Repository layout

```
app.py                      PyshaApp — the host object and asyncio event loop
definitions.py              Shared constants, path strings, PyshaMode base class
osc_controls.py             OSC control widgets (knob, switch, menu, macro, spacer)
engine.py                   SurgeXTEngine — spawns and manages a surge-xt-cli process
modes/
  instrument.py             Instrument — per-synth OSC client/server + device slots
  osc_device.py             OSCDevice — a panel of OSC controls for one synth slot
  osc_mode.py               OSCMode — creates instruments, routes OSC, draws device panels
  preset_selection_mode.py  Preset browser and 8-slot pad management per instrument
  metro_sequencer_mode.py   Main step sequencer (the primary playing mode)
  clip_selection_mode.py    Clip / pattern management
  melodic_mode.py           Base for melodic/rhythmic/slice pad layouts
  rhythmic_mode.py          Rhythmic pad layout (subclass of MelodicMode)
  slice_notes_mode.py       Slice pad layout (subclass of MelodicMode)
  instrument_selection_mode.py  Instrument track switcher
  main_controls_mode.py     Global transport buttons (play, record, etc.)
  mute_mode.py              Per-track mute management
  settings_mode.py          App settings panel
  menu_mode.py              Contextual overlay menu
  midi_cc_mode.py           MIDI CC control mode
  trig_edit_mode.py         Step sequencer trigger editing
  mod_matrix_device.py      Modulation matrix OSCDevice subclass
  audio_in_device.py        Audio input routing device
  external_instrument.py    Non-Surge external instrument (e.g. Overwitch)
  ddrm_tone_selector_mode.py  DDRM synth tone selector
user_interface/
  display_utils.py          Cairo text/graphics helpers (show_text, show_notification)
  display_process.py        Subprocess that renders frames without blocking the GIL
  recording_context.py      Audio recording helpers
definitions/
  instrument_listing.json   Ordered list of instrument short names, e.g. ["Pushpin 0", …]
  instrument_definitions/   One JSON per instrument, e.g. "Pushpin 0.json"
  device_definitions/       One JSON per OSC device type (alias_1.json, twist_1.json, …)
  effect_definitions/       One JSON per FX slot device
  modulation_definitions/   One JSON per modulation device
controllers/
  push2_constants.py        Button/encoder name constants (also in push2_python.constants)
tests/                      pytest suite
```

---

## Branch and PR rules

- **`dev`** is the integration branch. **All PRs target `dev`, never `main`.**
- `main` is the stable release branch; merges from `dev` are batched.
- Always open PRs against `dev`. If you accidentally target `main`, close and
  re-open.

### Stacked PRs

A stacked PR is one whose base is another PR's branch instead of `dev`.

- **Don't stack by default.** Branch from `dev` and open the next PR after the
  previous one merges. Stack only when the user asks, or when the work really
  can't be reviewed or tested without the PR below it (e.g. one Pi image built
  from several changes).
- **Why stacks conflict:** "Rebase and merge" and "Squash and merge" put *new
  copies* of the parent's commits on `dev`. The child branch still carries the
  old copies, so GitHub reports conflicts on lines whose content is already
  identical. Only "Create a merge commit" keeps the original commits.
- **Merging a stack:** merge every PR except the top one with **"Create a
  merge commit"**. GitHub retargets the child to `dev` and it stays clean. The
  top PR can use any method.
- **If a parent was squash- or rebase-merged anyway**, update the child by
  merging `dev` into it. Don't rebase and force-push (agents' auto mode blocks
  force-pushes). First check `git diff <old parent tip> origin/dev` is empty.
  If it is, every conflict resolves to the child's side
  (`git checkout --ours <file>`); confirm the merged tree equals the child's
  old tip (`git diff --cached --stat <old child tip>` shows nothing), then
  push normally. If the diff isn't empty, the parent changed in review:
  resolve the conflicts by hand.
- Say in the PR description that it's stacked and which PR to merge first.

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
missing:

```bash
brew install cairo pkg-config libusb   # macOS
# apt install libcairo2-dev libusb-1-dev  # Debian/Pi
```

---

## Architecture

### PyshaApp (`app.py`)

The host object. It:

- Owns `self.push` — a `push2_python` wrapper for the hardware
- Creates all Mode instances in `init_modes()` and stores them as named
  attributes (`self.preset_selection_mode`, `self.metro_sequencer_mode`, etc.)
- Runs an `asyncio` event loop; hardware callbacks arrive via `push2_python`
  decorators (`@push2_python.on_pad_pressed()`, etc.)
- Maintains `self.active_modes: list` — the stack of currently active modes,
  iterated **in reverse** so the last-appended mode gets first chance to handle
  each event; a mode returning a truthy value stops propagation
- Maintains `self.queue: list` — coroutines appended here are
  `asyncio.create_task`'d each loop tick (see Async queue below)
- Maintains `self.instruments: dict[str, Instrument]` keyed by short name
- Maintains `self.steps_held: list` — columns currently held by the user; modes
  append the column index on pad press and remove it on pad release

**Key flags:**
- `app.pads_need_update = True` — signals the loop to re-call `update_pads()`
  on all active modes
- `app.buttons_need_update = True` — same for `update_buttons()`

### Event propagation

Hardware events walk `active_modes` in **reverse order** (last appended = highest
priority). The first mode that returns a truthy value from its handler consumes
the event; later modes in the list don't see it. Always `return True` from a
handler if you want to prevent lower-priority modes from reacting.

```python
for mode in app.active_modes[::-1]:
    action_performed = mode.on_pad_pressed(pad_n, pad_ij, velocity)
    if action_performed:
        break
```

### PyshaMode (`definitions.py`)

Base class for every mode. `__init__` calls `self.initialize(settings)`, so
constructor side-effects happen there. `self.push` is a **property** returning
`self.app.push` — always use it, never cache `app.push` in a local.

| Method | Called when |
|--------|-------------|
| `initialize(settings)` | App startup — do disk I/O and heavy setup here |
| `activate()` | Mode becomes active — set button/pad lights |
| `deactivate()` | Mode is switched away from — **clear** lights you set |
| `update_display(ctx, w, h)` | Each display frame — draw with Cairo |
| `update_pads()` | Pad colour refresh needed |
| `update_buttons()` | Button colour refresh needed |
| `on_pad_pressed(pad_n, pad_ij, velocity)` | Pad pressed |
| `on_pad_released(pad_n, pad_ij, velocity)` | Pad released |
| `on_button_pressed(button_name)` | Button pressed |
| `on_button_released(button_name)` | Button released |
| `on_encoder_rotated(encoder_name, increment)` | Encoder turned |
| `on_encoder_touched(encoder_name)` | Encoder touched |

`pad_ij` is a `(row, col)` tuple where `row` is 0–7 (top to bottom) and `col`
is 0–7 (left to right). Column index = instrument index in most modes.

### Mode switching (xor_group)

Modes that own the pads declare `xor_group = "pads"`. When
`app.set_mode_for_xor_group(mode)` is called, it deactivates any other mode in
the same xor group first. Direct `active_modes` manipulation (as in
`toggle_preset_selection_mode`) deactivates modes explicitly.

The Toggle functions (`toggle_preset_selection_mode`, `toggle_clip_selection_mode`,
`toggle_menu_mode`, `toggle_ddrm_tone_selector_mode`) are the correct entry
points for mode switching — do not manipulate `active_modes` directly from
mode code.

**When activating or deactivating a mode always call `activate()` / `deactivate()`
explicitly** — adding to `active_modes` alone does not light up buttons.

---

## Instruments

### Naming

Instruments are named by their **short name** string, which matches both the
key in `app.instruments` and the filename in `definitions/instrument_definitions/`.
Default instruments are `"Pushpin 0"` through `"Pushpin 7"` (note the space —
it's part of the name). These come from `definitions/instrument_listing.json`.

Each instrument definition JSON (e.g. `definitions/instrument_definitions/Pushpin 0.json`):

```json
{
  "instrument_name": "Pushpin 0",
  "instrument_short_name": "Pushpin 0",
  "illuminate_local_notes": true,
  "midi_channel": 0,
  "osc_in_port": 1030,
  "osc_out_port": 1040,
  "duplex_osc_port": 1050,
  "instrument_index": 0,
  "default_layout": "lmelodic"
}
```

OSC **in** port = port the app sends to Surge on. OSC **out** port = port Surge
sends replies back on.

### Instrument helper methods (available on any Mode via OSCMode)

```python
# From a Mode, the common pattern:
instrument = self.app.osc_mode.get_current_instrument()
instrument_shortname = self.app.osc_mode.get_current_instrument_short_name_helper()

# All instrument short names (matches app.instruments keys):
self.get_all_distinct_instrument_short_names_helper()
# → ["Pushpin 0", "Pushpin 1", …]

# Direct dict access:
self.app.instruments["Pushpin 0"]
```

### Instrument class (`modes/instrument.py`)

Each `Instrument` holds:

- `instrument.slots` — list of 16 slot dicts `{"address": "/param/…", "value": float}`.
  Slots 0 and 1 are OSC 1 and OSC 2 type; slots 5–7 are FX slots.
  Updated when Surge replies to `/q` queries via `set_slot_state()` callback.
- `instrument.devices` — list of 16 lists, each containing `OSCDevice` objects
  registered for that slot index.
- `instrument.current_devices` — the currently-active device panels, rebuilt
  by `update_current_devices()` from slot values.
- `instrument.devices_modulation` — modulation devices (slot indices 8–15).

**Key methods:**
- `query_slots()` — sends `/q<address>` for each slot. Fire-and-forget UDP;
  replies arrive asynchronously via OSC dispatcher callback. **Always wait at
  least 500 ms before reading `slots` or calling `update_current_devices()`.**
- `update_current_devices()` — rebuilds `current_devices` from current `slots`.
  Cheap and synchronous. Only accurate after slot replies have arrived.
- `init_devices_sync()` — sends fixed init OSC commands from each active
  device's JSON `"init"` block. Synchronous. Uses current `current_devices`,
  so it must be called after `update_current_devices()`.
- `query_all_controls()` — queries all controls on all devices (expensive).

---

## The async queue

`app.queue` is a plain list. Each iteration of the main loop calls:

```python
for task in self.queue:
    t = asyncio.create_task(task)
    self.queue.remove(task)
```

Append a coroutine to it from synchronous code to schedule async work without
blocking the event loop:

```python
self.app.queue.append(self._my_async_method(arg))
```

**This is the only safe way to use `asyncio.sleep` from synchronous handlers.**
Direct `time.sleep()` in handlers blocks the entire event loop — only use it
in contexts that are already outside the main loop (e.g. inside the synchronous
preset save path in `set_pad_preset_slot` where the brief block is acceptable).

Worked example — refresh devices after a preset load:

```python
async def _refresh_devices_after_preset_load(self, instrument_shortname):
    instrument = self.app.instruments[instrument_shortname]
    instrument.query_slots()
    await asyncio.sleep(0.5)          # wait for Surge's UDP replies
    instrument.update_current_devices()
    await asyncio.sleep(0.5)
    for device in instrument.current_devices:
        await device.select()         # sends init commands with per-command delays
        device.query_all()

def on_pad_released(self, pad_n, pad_ij, velocity):
    # ... do synchronous work ...
    self.app.queue.append(
        self._refresh_devices_after_preset_load(instrument_shortname)
    )
```

---

## OSC

### Sending from a Mode

```python
# Routes to the instrument the user currently has selected:
self.send_osc("/param/a/osc/1/type", 10.0)

# Routes to a specific instrument:
self.send_osc("/patch/load", preset_path, instrument_shortname="Pushpin 0")
```

`send_osc` is defined on `PyshaMode` and delegates to `app.send_osc`, which
looks up the right `Instrument.osc["client"]` by short name.

### Sending from non-Mode code

```python
instrument = self.app.instruments["Pushpin 0"]
instrument.send_message("/patch/load", preset_path)
```

### OSC timing rule (critical)

Surge replies to `/q` queries asynchronously over UDP. Never call
`query_slots()` and immediately read `slots` or call `update_current_devices()`.
**Always insert `await asyncio.sleep(0.5)` between them** (use the async queue
pattern for synchronous handlers). Violating this produces stale device
displays — the original bug that motivated this rule.

### Surge XT OSC address conventions

- `/patch/load <path>` — load a preset file (`.fxp`, pass path without extension)
- `/patch/save <path>` — save current synth state to a file
- `/param/a/osc/1/type` — OSC 1 oscillator type (slot 0)
- `/param/a/osc/2/type` — OSC 2 type (slot 1)
- `/param/fx/a/1/type` — FX slot A1 type (slot 5)
- `/q<address>` — query current value of `<address>`; Surge replies by sending
  back to the out port with the same address and the current float value

---

## Preset system

### Data layout

- `definitions/instrument_listing.json` — ordered list of instrument short names.
- `presets.json` (project root, user data) — maps each instrument short name to
  a list of 8 factory preset paths (absolute paths without `.fxp` extension):
  ```json
  { "Pushpin 0": ["/path/to/patches_factory/Templates/Init Saw", …], … }
  ```
  `null` entries are valid and indicate an unset slot; always pass through
  `_resolve_preset()` before using.
- `surge_state/` folder — per-instrument per-slot `.fxp` files named
  `{instrument_short_name}_{slot_index}` (e.g. `Pushpin 0_3`). These hold the
  last-saved synth state for each pad slot and are what actually gets loaded
  when the user selects a pad. Factory presets in `presets.json` are only
  the browsing source; `surge_state` is the live playing state.

### `_resolve_preset(path)` (PresetSelectionMode)

Always call this before splitting or loading a path from `self.presets`:

```python
preset_path = self._resolve_preset(self.presets[instrument][index])
```

Returns `path` if non-empty/non-null, otherwise `DEFAULT_PRESET`
(`~/.local/share/surge-xt/patches_factory/Templates/Init Saw`).

### Preset selection UX (current implementation)

1. **Short press a pad** — loads the `surge_state` file for that slot into Surge
   immediately. Guard: does not reload if the same pad that is already selected
   is pressed again (prevents accidentally overwriting in-progress sound design).
2. **Hold Select + press a pad** — opens the preset browser overlay.
   `browser_active` flag is set to `True`. The browser stays open even after
   Select is released, as long as the pad is held.
3. **Navigate with encoders while browser is open** — browse factory/third-party/
   user patch folders. `current_address` tracks the highlighted preset path.
4. **Release pad (while browser was active)** — calls `set_pad_preset_slot()`:
   loads the browsed preset into Surge, saves it to the `surge_state` slot file,
   updates `presets.json`. Then queues `_refresh_devices_after_preset_load()` to
   re-sync device panels. `browser_active` is cleared.

### Saving a preset to a slot (the full sequence)

```python
# 1. Load the new factory preset into Surge
self.send_osc("/patch/load", self.current_address, instrument_shortname=shortname)
time.sleep(0.5)   # give Surge time to finish loading

# 2. Save it into the surge_state slot
self.send_osc("/patch/save", surge_state_path, instrument_shortname=shortname)
time.sleep(0.5)

# 3. Record the new source path
self.presets[shortname][preset_number] = self.current_address
self.save_presets()

# 4. Async: re-query slots and refresh devices
self.app.queue.append(self._refresh_devices_after_preset_load(shortname))
```

---

## Device definitions (JSON)

Each file in `definitions/device_definitions/` configures one type of OSC
device panel. Example (`alias_1.json`):

```json
{
  "name": "Alias",
  "slot": 0,
  "init": [
    { "$type": "message", "address": "/param/a/mixer/osc1/mute", "value": 0 },
    { "$type": "message", "address": "/param/a/osc/1/type", "value": 11 }
  ],
  "controls": [
    { "$type": "control-range", "label": "Pitch", "address": "/param/a/osc/1/pitch", "min": 0, "max": 1, "bipolar": 1 },
    { "$type": "control-menu", "menu_label": "Waveform", "items": [ … ] }
  ]
}
```

- `"slot"` — which `Instrument.slots` index this device corresponds to
- `"init"` — OSC commands sent by `device.select_sync()` / `device.select()`.
  The `init` commands uniquely identify the device: `update_current_devices()`
  finds the active device by matching each device's `init[0]` address+value
  against the current slot values.
- `"controls"` — list of control definitions. Valid `$type` values: `control-range`,
  `control-menu`, `control-switch`, `control-macro`, `control-spacer`,
  `control-spacer-address`

Control types: see the OSC controls section below.

Surge takes float parameters over OSC as 0..1 of their range, and int/bool
parameters as their own values (Unison Voices is 1..16, not 0..16). Check new
or changed definitions against Surge with `tools/surge_snapshot.py` (see
`tests/README.md`).

Wavetables are picked by id, and Surge numbers them in the order the
filesystem lists its wavetable folder, so ids differ between machines. Menu
items name the wavetable instead (`"wavetable": "Basic/Sine"`) and
`wavetables.py` looks the id up when the device loads. The Wavetable and
Window devices' picker is generated by `tools/gen_wavetable_picker.py`.

A control-range's `bipolar` (drawn from the middle) is set exactly when
Surge's range is symmetric around 0; the Surge snapshot tests check it.

---

## OSC controls (`osc_controls.py`)

| Class | Purpose |
|-------|---------|
| `OSCControl` | Single continuous parameter (knob). One encoder position. |
| `OSCControlMacro` | One knob driving multiple OSC addresses simultaneously |
| `OSCControlSwitch` | Integer-valued toggle between named `OSCGroup` pages |
| `OSCControlMenu` | Dropdown selecting from a list of items; each item can send an OSC message |
| `OSCSpacerAddress` | A visual gap that also listens to an OSC address |
| `ControlSpacer` | Visual gap, no OSC |
| `OSCGroup` | Named group of controls shown when a switch is active |

**Value scaling:** `update_value(increment)` applies `increment / 127 × range`.
A single encoder tick produces a small fractional change. Reaching an integer
index on a switch/menu takes a large aggregate movement — this is intentional
mitigation, but known to be awkward.

**`OSCDevice.pages`** — a computed property that packs controls into 8-column
pages. `OSCDevice.page` is the current page index. `device.set_page(n)` changes
page. When a step pad is held, switch controls temporarily show their locked
value so the display reflects the locked state.

---

## Button lights

Set button colours from `update_buttons()`:

```python
self.push.buttons.set_button_color(
    push2_python.constants.BUTTON_SELECT, definitions.WHITE
)
```

**Always clear lights you set in `deactivate()`.** Button state is global — if
you set a button in `activate()` and don't clear it in `deactivate()`, it stays
lit when the user switches mode.

Button name constants: `controllers/push2_constants.py` and `push2_python.constants`.
Both are equivalent; `controllers/push2_constants.py` is a local copy. Use
`push2_python.constants.BUTTON_*` for consistency with the rest of the codebase.

Common buttons: `BUTTON_SELECT`, `BUTTON_SHIFT`, `BUTTON_LEFT`, `BUTTON_RIGHT`,
`BUTTON_PLAY`, `BUTTON_SCALE`, `BUTTON_UPPER_ROW_1` through `BUTTON_UPPER_ROW_8`,
`BUTTON_LOWER_ROW_1` through `BUTTON_LOWER_ROW_8`, `BUTTON_1_16`, `BUTTON_DELETE`.

Color constants: `definitions.WHITE`, `definitions.BLACK`, `definitions.GRAY_DARK`,
`definitions.GREEN`, etc. See `definitions.py` for the full palette.

---

## Tests

Config: `pytest.ini` + `.coveragerc`. Do not run `tests/test.py` or
`tests/isobar-test.py` directly — not collected (don't match `test_*.py`).

### Shared fixtures (`tests/conftest.py`)

- **`push`** — `MagicMock` for the Push 2 hardware wrapper.
- **`app`** — `MagicMock` PyshaApp with pre-configured attributes:
  - `app.push` wired to the `push` fixture
  - `app.steps_held = []`
  - `app.pads_need_update = False`, `app.buttons_need_update = False`
  - `app.instrument_selection_mode.get_current_instrument_short_name.return_value = "INST1"`
  - `app.instrument_selection_mode.get_all_distinct_instrument_short_names.return_value = ["INST1", "INST2"]`
  - `app.metro_sequencer_mode.sequencer_is_playing = False`
- **`reset_mode_state`** (autouse) — clears class-level mutable state between
  tests (currently only `MelodicMode.notes_being_played`; add new resets here
  if you add new class-level mutable state).

Override any fixture value inside a test:
```python
app.instrument_selection_mode.get_current_instrument_short_name.return_value = "Pushpin 3"
```

### Key patterns

- **Patch out heavy `initialize()`** — modes that do disk I/O or build
  instruments (`OSCMode`, `MetroSequencerMode`, `PresetSelectionMode`,
  `ClipSelectionMode`, `InstrumentSelectionMode`) have `initialize` patched:
  ```python
  with patch.object(PresetSelectionMode, "initialize"):
      mode = PresetSelectionMode(app)
  mode.presets = {"INST1": [None] * 8}  # set state manually
  ```
- **Reset class-level defaults** — if your mode has class-level mutable state,
  reset it before constructing in a fixture or add it to `reset_mode_state`.
- **Never import hardware** — no USB, no Cairo rendering, no `push2_python`
  hardware paths in tests. Everything is mocked.
- **Assert actual behaviour** — tests document what the code does, not what it
  should ideally do. When you change behaviour, update the test.

### Pre-existing known failure

`tests/test_clip_selection_mode.py::test_get_preset_path_factory` fails because
`ClipSelectionMode.get_preset_path` no longer exists. This is stale, pre-dates
this document, and is not a regression to investigate.

---

## Common tasks

### Adding a new Mode

1. Create `modes/my_mode.py`, subclass `definitions.PyshaMode`.
2. Implement `initialize()`, `activate()`, `deactivate()`, and whichever
   `on_*` / `update_*` methods you need. Clear any lights you set in `deactivate()`.
3. Register it in `PyshaApp.init_modes()` in `app.py`.
4. Add a toggle function in `PyshaApp` if it needs mode-switching.
5. Add `tests/test_my_mode.py` following the conftest patterns.

### Lighting a button while a mode is active

```python
def activate(self):
    self.update_pads()
    self.push.buttons.set_button_color(push2_python.constants.BUTTON_SELECT, definitions.WHITE)

def deactivate(self):
    self.push.buttons.set_button_color(push2_python.constants.BUTTON_SELECT, definitions.BLACK)

def update_buttons(self):
    # Called each frame — keep in sync with mode state
    self.push.buttons.set_button_color(
        push2_python.constants.BUTTON_SELECT, definitions.WHITE
    )
```

### Tracking whether a modifier button is held

The pattern used throughout (e.g. `button_gate_stack` in `MetroSequencerMode`,
`select_button_held` in `PresetSelectionMode`):

```python
# Class-level flag
my_button_held = False

def on_button_pressed(self, button_name):
    if button_name == push2_python.constants.BUTTON_SHIFT:
        self.my_button_held = True
        return True  # consume the event

def on_button_released(self, button_name):
    if button_name == push2_python.constants.BUTTON_SHIFT:
        self.my_button_held = False
        return True
```

### Sending OSC to Surge

```python
# From a Mode (routes to currently selected instrument):
self.send_osc("/param/a/osc/1/type", 10.0)

# From a Mode (routes to a specific instrument):
self.send_osc("/patch/load", preset_path, instrument_shortname="Pushpin 0")

# From non-Mode code:
self.app.instruments["Pushpin 0"].send_message("/patch/load", preset_path)
```

### Queueing async work from a synchronous handler

```python
def on_pad_released(self, pad_n, pad_ij, velocity):
    # synchronous work here ...
    self.app.queue.append(self._do_async_work(instrument_shortname))
    return True

async def _do_async_work(self, instrument_shortname):
    instrument = self.app.instruments[instrument_shortname]
    self.send_osc("/patch/load", path, instrument_shortname=instrument_shortname)
    await asyncio.sleep(0.5)
    instrument.query_slots()
    await asyncio.sleep(0.5)
    instrument.update_current_devices()
    await asyncio.sleep(0.5)
    for device in instrument.current_devices:
        await device.select()
        device.query_all()
```

### Reading from `presets.json` safely

```python
preset_path = self._resolve_preset(self.presets[instrument_shortname][slot_index])
# Never do: self.presets[instrument][index].split("/") — will crash on null entries
```

---

## Diagnosing a Raspberry Pi

A Pi flashed with a **diagnostics-mode** image (see
`scripts/diagnostics/README.md`) can be inspected from the development machine
without a password:

```bash
scripts/diagnostics/diagnose.sh check      # connection test
scripts/diagnostics/diagnose.sh summary    # OK/WARN/FAIL lines: read these first
scripts/diagnostics/diagnose.sh report     # full report saved in diagnostics-output/
scripts/diagnostics/diagnose.sh run <cmd>  # one command on the Pi, as pushpin
```

- Start with `summary`; follow up on each `FAIL` with `report` or a targeted `run`.
- Diagnosis is read-only. Don't restart services, edit files, install packages
  or reboot the Pi unless the user asks for that specific action.
- Host keys change on every burn. If SSH refuses a changed key after a re-flash,
  `diagnose.sh forget` is the fix. Don't disable host-key checking.
- `pushpin` has no sudo rights on these images. Anything that needs root goes
  to the user.

---

## Known bugs / open debt

These are real issues. Fix them properly rather than patching over symptoms:

1. **Class-level mutable state shared across instances** — `MelodicMode.notes_being_played`,
   `MuteMode.tracks_active`, `TrigEditMode.controls/state`,
   `InstrumentSelectionMode.instruments_info`, and `instrument_sequencers` dicts
   are class attributes that accumulate across instances. Should be instance
   attributes set in `initialize()`.

2. **`OSCControlMenu` index seeded from `onselect.value`** — `self.value = self.message["value"]`
   in `osc_controls.py` conflates the initial OSC value with the menu selection
   index. A menu with a non-zero `onselect.value` starts on the wrong item.

3. **Substring `in` checks on button names** — `button_name in push2_python.constants.BUTTON_UPPER_ROW_7`
   is a string substring test, not equality. It works by coincidence for current
   button name strings. Should be `==`.

4. **Control value is fractional/twitchy** — `update_value(increment)` advances
   by `increment / 127 × range`. Reaching an integer index on a switch/menu
   requires a large encoder movement. Intentional but worth revisiting for UX.

5. **`query_all_params()` on Instrument is broken** — marked TODO in `instrument.py`.
   Do not rely on it. Use `query_all_controls()` on individual devices instead.

6. **`init_devices_sync()` on Instrument** — `app.py` line 1359 appends this
   as a coroutine to `app.queue`, but `init_devices_sync` is synchronous, not
   async. This is a latent type error that happens not to crash because the
   queue iteration silently drops non-awaitable objects. Watch out for it.

7. **`SURGE_STATE_FOLDER` path** — currently hardcoded to
   `~/s/music_devices/pushpin-groovebox/surge_state`. This is a developer-local
   path and needs to become configurable for other setups.

---

## Recent work (context for a new agent)

The following changes were made in the most recent development session, all
merged to `dev`:

- **Preset selection rewrite** (`modes/preset_selection_mode.py`): fixed
  `set_pad_preset_slot` which was a stub; added `_resolve_preset()` and
  `DEFAULT_PRESET` to handle `null` entries in `presets.json`; replaced a
  long-press timing mechanism with a **Select+pad** interaction (`select_button_held`
  / `browser_active` flags); fixed stale device display after preset load by
  queuing `_refresh_devices_after_preset_load` via `app.queue` instead of
  calling `update_current_devices()` immediately on stale slot data.

- **Select button light**: `update_buttons()` sets `BUTTON_SELECT` to `WHITE`
  while preset selection mode is active; `deactivate()` clears it.

- **Lock encoder fix** (`modes/osc_device.py` / `modes/metro_sequencer_mode.py`):
  fixed the step lock encoder using flat `device.controls` instead of the
  visible-page layout.

- **OSCControlSwitch onselect** (`osc_controls.py`): sends the `onselect` OSC
  message when the active group changes.

- **Metro sequencer pad state** (`modes/metro_sequencer_mode.py`): two pad
  state bugs fixed.

- **Display rendering** (`user_interface/display_process.py`): Cairo rendering
  moved to a subprocess with shared memory frame transfer to avoid GIL
  starvation.

The active PR branch for the AGENTS.md itself is `docs/agents-md` targeting
`dev`.
