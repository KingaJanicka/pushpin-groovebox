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
| **CC 14** | machine, value = number from `--list-machines` (pushpin's addition) |
| CC 120, 123 | all sound off / all notes off |
| clock, start, stop | ignored (pushpin sequences; MONO2K's sequencer stays stopped) |

## Known limits of the spike

- The core runs at 44.1 kHz and is resampled linearly to the JACK rate (48 kHz on
  the Pi), which loses a little treble.
- MIDI is applied with sample accuracy, but the core only reads parameters every
  16 samples.
- MONO2K's lofi bus (reverb, tape) runs inside every process with the factory
  defaults; there is no CC for it yet.
- Not yet tested: the JACK path on the Pi. It builds only where JACK headers
  exist; on macOS it was checked against stub headers only.
- Not wired into pushpin yet (no `M2KEngine`, no CC-sending device definitions).
