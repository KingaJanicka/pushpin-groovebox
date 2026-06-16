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

## Open issues found while writing tests

These look like real discrepancies worth a follow-up (candidates for the
"code quality / reduce bug density" phase):

1. **`test_osc_controls.py` expected `64` defaults.** Controls now initialise
   `self.value = 0.0`, but three existing assertions expect `64`. Either the
   code regressed away from a 64 default, or the tests are stale. Left
   unchanged pending a decision; the undefined `scale_knob_value` reference was
   fixed.
2. **Class-level mutable state.** Several modes declare mutable containers at
   class scope (`MelodicMode.notes_being_played`, `MuteMode.tracks_active`,
   `TrigEditMode.controls/state`, `InstrumentSelectionMode.instruments_info`,
   etc.). These are shared across instances and accumulate on re-init — a latent
   bug the tests work around by resetting them.
3. **Substring `in` checks on button names**, e.g.
   `elif button_name in push2_python.constants.BUTTON_UPPER_ROW_7:` in
   preset/clip modes does a string-substring match rather than equality.
