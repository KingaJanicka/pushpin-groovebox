# Tests

Unit tests for pushpin-groovebox, focused on the `Mode` classes created in
`PyshaApp.init_modes()`.

## Running

Run with the same Python environment that runs the app (it must already have
`push2_python`, `isobar`, `mido`, etc.). This repo uses pyenv; pin the project
to the right interpreter and invoke tools via `python -m` so the run does not
depend on a `pip`/`pytest` shim being on PATH:

```bash
cd ~/Projects/pushpin-groovebox
pyenv local 3.11.14                          # the env that can import the app deps
python -m pip install pytest pytest-mock pytest-cov
python -m pytest                             # run the suite
python -m pytest --cov --cov-report=term-missing
python -m pytest --cov --cov-report=html     # HTML report in htmlcov/
```

Configuration lives in `pytest.ini` (rootdir/import paths) and `.coveragerc`
(coverage source + omit rules).

## How the Mode tests work

`Mode` classes are tightly coupled to the Push 2 hardware (`self.app.push`) and
to a large `PyshaApp` instance. `conftest.py` provides:

- `app` — a `MagicMock` PyshaApp with the commonly-used sub-modes and flags
  pre-configured (instrument selection, metro transport, etc.).
- `push` — a `MagicMock` for the Push 2 hardware wrapper.
- `reset_mode_state` (autouse) — clears class-level mutable state between tests.

Modes whose `initialize()` reads files off disk or builds heavy objects
(OSC/sequencer/preset/clip) have `initialize` patched out; tests then set the
minimal state each method needs.

## Coverage map (Mode classes)

| Mode | Test file |
|------|-----------|
| MelodicMode / RhythmicMode / SliceNotesMode | test_melodic_mode.py |
| MainControlsMode | test_main_controls_mode.py |
| MenuMode | test_menu_mode.py |
| SettingsMode | test_settings_mode.py |
| InstrumentSelectionMode | test_instrument_selection_mode.py |
| MuteMode | test_mute_mode.py |
| DDRMToneSelectorMode | test_ddrm_tone_selector_mode.py |
| TrigEditMode | test_trig_edit_mode.py |
| PresetSelectionMode | test_preset_selection_mode.py |
| ClipSelectionMode | test_clip_selection_mode.py |
| MIDICCMode | test_midi_cc_mode.py |
| OSCMode | test_osc_mode.py |
| SequencerMode | test_sequencer_mode.py |
| MetroSequencerMode | test_metro_sequencer_mode.py |
| Saving sequences (per clip) and the SCALE page | test_seq_state_saving.py |
| Saving on SIGTERM (systemd stop) | test_shutdown.py |
| Push 2 late plug-in / replug (MIDI reconnect on the main loop) | test_push_connection.py |
| Every Surge device definition (`definitions/*_definitions/*.json`) | test_device_definitions.py |
| Wavetable ids by name (`wavetables.py`) and the wavetable picker | test_wavetables.py |

## Device definitions and the Surge snapshot

`test_device_definitions.py` checks every device/effect/modulation JSON three
ways: the JSON alone (addresses belong to the device's slot, menus use one
address, `_1`/`_2`/`_global` twins match), built into a real `OSCDevice`
(turning each control end to end sends exactly the messages the JSON lists),
and against `fixtures/surge_snapshot.json`: what a real Surge XT did with each
definition (every address is Surge's, every value lands, no two items of a
menu leave Surge in the same state).

The snapshot is captured from a running `surge-xt-cli`; after changing a
definition, regenerate it (about 15 minutes) or the Surge tests report it stale:

```bash
"/Applications/Surge XT.app/Contents/MacOS/surge-xt-cli" --osc-in-port=19030 --osc-out-port=19040 --no-stdin &
python tools/surge_snapshot.py                     # everything, or only what changed:
python tools/surge_snapshot.py definitions/device_definitions/window_1.json
```

Labels aren't compared word for word with Surge's names (they're deliberate
shorthand); the snapshot keeps Surge's names and display strings for reading.

## Open issues found while writing tests

These look like real discrepancies worth a follow-up (candidates for the
"code quality / reduce bug density" phase):

1. **Class-level mutable state.** Several modes declare mutable containers at
   class scope (`MelodicMode.notes_being_played`, `MuteMode.tracks_active`,
   `TrigEditMode.controls/state`, `InstrumentSelectionMode.instruments_info`,
   etc.). These are shared across instances and accumulate on re-init — a latent
   bug the tests work around by resetting them.
2. **Substring `in` checks on button names**, e.g.
   `elif button_name in push2_python.constants.BUTTON_UPPER_ROW_7:` in
   preset/clip modes does a string-substring match rather than equality.
