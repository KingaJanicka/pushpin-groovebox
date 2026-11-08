# m2k-jack (spike)

The [MONO2K](https://github.com/InigoHernandez/mono2k) synth core, Monomachine-style
machines written from scratch in integer C, wrapped as a small JACK synth that
pushpin can launch per track in the same way it launches `surge-xt-cli`.

**Licence:** `m2k_jack.c` compiles MONO2K's GPL-3.0-only core into itself, so this
directory is **GPL-3.0-only**, unlike the rest of pushpin (MIT). pushpin only
talks to the built binary over MIDI and never links it. MONO2K's source is
fetched at build time into `vendor/`, which is not committed.

## Build

```bash
engines/m2k/build.sh                       # fetches MONO2K at the pinned commit
M2K_SRC=~/src/mono2k engines/m2k/build.sh  # or build against a local checkout
```

If `pkg-config` finds `jack`, the build includes JACK support (on the Pi:
`sudo apt install libjack-jackd2-dev`, or pipewire-jack's dev package).
Otherwise it builds a binary that can only render offline, which is enough to
test the sound on macOS.

## Run

```bash
pw-jack engines/m2k/build/m2k-jack --name "M2K 0" --machine 5 --midi-connect "Pushpin 0"
engines/m2k/build/m2k-jack --list-machines
engines/m2k/build/m2k-jack --render /tmp/demo.wav            # a short test phrase, no JACK
engines/m2k/build/m2k-jack --render /tmp/x.wav --script s.txt # lines: seconds status d1 d2
```

Ports: `midi_in`, `output_0`, `output_1`. By default the outputs connect to the
first two physical playback ports, as Surge's do. `--midi-connect` links every
JACK MIDI output port whose name contains the given text.

## MIDI

One process plays one MONO2K track. All MIDI channels are folded onto it.

| Message | Effect |
|---|---|
| Note on/off | plays the track (velocity ignored, as on the Monomachine) |
| CC 48–55 | SYN A–H (the machine's page) |
| CC 56–63 | AMP: ATK HOLD DEC REL DIST VOL PAN PORT |
| CC 72–79 | FILT: BASE (high-pass) WDTH HPQ LPQ FATK FDEC BOF WOF |
| CC 80–87 | FX: EQF EQG SRR DTIM DSND DFB DBAS DWID |
| CC 88/104/112 +0..7 | LFO 1/2/3: TRCK DEST WAVE TRIG MULT SPD PHAS DPTH |
| CC 7 / CC 3 | level / mute |
| **CC 14** | machine, value = number from `--list-machines`; loads that machine's INIT sound (pushpin's addition) |
| **CC 16–20** | DSTR: BITS FOLD XOR, reverb send, track pitch (pushpin's addition) |
| CC 120, 123 | all sound off / all notes off |
| NRPN 0:*n* | the parameter on CC *n* at 14 bits: CC 99 = 0, CC 98 = *n*, CC 6 = whole value, CC 38 = fraction × 128 (pushpin sends this) |
| clock, start, stop | ignored (pushpin sequences; MONO2K's sequencer stays stopped) |

## Known limits of the spike

- The core runs at 44.1 kHz and is resampled linearly to the JACK rate (48 kHz on
  the Pi), which loses a little treble.
- MIDI is applied with sample accuracy, but the core only reads parameters every
  16 samples.

## Resolution and smoothing

MONO2K stores every parameter as 0–127, and one step of FILT BASE or WDTH moves
the cutoff 1/8 octave (1.5 semitones). On its own the core applies a new value
at the next 16-sample block with no smoothing, so a knob turned through the
filter is heard as steps. m2k-jack fixes that:

- **Finer values.** `patches/0001-fine-parameter-offset.patch` adds a
  `fine` offset to each parameter, which the core's `P8()` adds in 1/256 of a
  step (the resolution its LFOs already use). `build.sh` applies the patches to
  a copy of the source in `build/mono2k/`, so neither `vendor/` nor `M2K_SRC`
  is changed. NRPN values reach the sound at 1/128 of a step.
- **Glide.** A new value is approached with a one-pole glide, `--glide-ms`
  (default 20; 0 turns it off), updated every block. Measured on a WDTH sweep
  sent one step every 30 ms, the largest cutoff change per 16-sample block went
  from 150 cents to 3.5 cents.
- **P-locks stay sharp.** A value that arrives within `--snap-ms` (default 10)
  of a note-on, before or after it, is set at once, so pushpin's p-locks are
  heard on their note and not glided into.
- **Choices never glide.** Waves, modes, LFO destinations and other choices
  jump straight to the new choice.
- `--render ... --trace-param P` writes parameter P as the DSP reads it, once
  per block, to stderr (P is MONO2K's parameter number, e.g. 17 = WDTH).

On the pushpin side, `MidiCCClient` sends mono2k parameters as NRPN, so a
control's fractional value isn't rounded, and the filter and EQ frequency
controls (BASE, WDTH, EQF, DBAS) move half a step per encoder click (`"step"`
in their definitions).
- MONO2K's lofi bus (reverb, tape) runs inside every process with the factory
  defaults. Only the track's reverb send has a CC (19); the bus itself has none.
- Not yet tested: the JACK path on the Pi. It builds only where JACK headers
  exist; on macOS it was checked against stub headers only.
- Presets don't work on m2k tracks: pushpin's preset code sends Surge's
  `/patch/...` commands, which the CC client ignores.
- The snap window can misfire: a knob move that happens within 10 ms of a
  sequenced note is set at once rather than glided.
- Choosing a machine always loads its INIT sound (AMP, FILT, FX and LFOs too),
  because pushpin can't read values back from m2k-jack and needs to know them.
- Parameters with a few discrete choices (LFO WAVE, SID WAVE, ...) are plain
  0–127 knobs, not menus.

## Using it for a pushpin track

Add `"engine": "mono2k"` (and optionally a starting `"m2k_machine"`) to the
track's file in `definitions/instrument_definitions/`, e.g. `Pushpin 3.json`:

```json
{
  "instrument_name": "Pushpin 3",
  "instrument_short_name": "Pushpin 3",
  "engine": "mono2k",
  "m2k_machine": 5,
  ...
}
```

pushpin then starts `pw-jack m2k-jack --name "M2K 3" --midi-connect "Pushpin 3"`
in place of `surge-xt-cli` and routes its outputs through the volume node, the
same way it routes Surge. The binary path defaults to
`engines/m2k/build/m2k-jack`; set `PUSHPIN_M2K_BIN` to override it. The log
goes to `m2k-3.log` in pushpin's log directory.

## Device pages

The Push's pages for an m2k track come from `engines/m2k/definitions/`, which
`gen_definitions.py` generates from `m2k-jack --describe` (the labels and INIT
sounds are MONO2K's own, so the generated files stay in this GPL directory).
Regenerate them after updating the pinned MONO2K commit:

```bash
engines/m2k/build.sh && python engines/m2k/gen_definitions.py
```

- **Machine device** (first upper-row button): one per machine, picked from the
  device menu like Surge's oscillator types. Shows SYN A–H with that machine's
  own labels. Selecting one sends CC 14 and the machine's whole INIT sound.
- **AMP, FILT, FX, DSTR**: always shown.
- **LFO 1–3**: on the modulation page (Right arrow). TRCK is hidden, because a
  process plays only one track.

Every control's address is `/cc/<n>`. On a mono2k track the instrument's
`MidiCCClient` (`cc_client.py`) turns those into MIDI CCs on the track's MIDI
port, and sends each value back through the instrument's OSC dispatcher, the
way Surge echoes values. That way the display, the device slot that selects
the machine, and sequencer p-locks work as they do for Surge.
