# m2k-jack (spike)

The [MONO2K](https://github.com/InigoHernandez/mono2k) synth core, Monomachine-style
machines written from scratch in integer C, wrapped as an eight-track JACK synth.
pushpin starts one m2k-jack for all its mono2k tracks: pushpin track *n* plays
MONO2K track *n*, out of that track's own outputs.

**Licence:** `m2k_jack.c` compiles MONO2K's GPL-3.0-only core into itself, so this
directory is **GPL-3.0-only**, unlike the rest of pushpin (MIT). pushpin only
talks to the built binary over MIDI and never links it. MONO2K's source is
fetched at build time into `vendor/`, which is not committed.

## Build

```bash
engines/m2k/build.sh                       # fetches MONO2K at the pinned commit
M2K_SRC=~/src/mono2k engines/m2k/build.sh  # or build against a local checkout
```

`build.sh` copies the source into `build/mono2k/`, applies `patches/*.patch`
there (so neither `vendor/` nor `M2K_SRC` is changed) and builds with
`-DM2K_TRACKS=8`. If `pkg-config` finds `jack`, the build includes JACK support
(on the Pi: `sudo apt install libjack-jackd2-dev`, or pipewire-jack's dev
package). Otherwise it builds a binary that can only render offline, which is
enough to test the sound on macOS. With `M2K_REQUIRE_JACK=1`, a missing JACK
is an error instead.

**On the Pi image** this happens automatically: the image setup scripts
(`scripts/image/setup_full_with_backports.sh`, which CI's release images use,
and the older variants) run `build.sh` with `M2K_REQUIRE_JACK=1` after installing
pushpin's Python deps and check the binary runs. A flashed Pi can play
Monomachine straight away, and an image whose m2k-jack didn't build fails to
build rather than shipping without it. Build the image from a ref that has
`engines/m2k` (`PUSHPIN_REF=spike/m2k-jack` until it's merged).
`pushpin-diag --summary` reports whether m2k-jack is built, running, and routed.

## Run

```bash
pw-jack engines/m2k/build/m2k-jack --enable 1,3 --midi-connect "1=Pushpin 0" --midi-connect "3=Pushpin 2"
engines/m2k/build/m2k-jack --list-machines
engines/m2k/build/m2k-jack --render /tmp/demo.wav                 # a short test phrase, no JACK
engines/m2k/build/m2k-jack --render /tmp/x.wav --script s.txt     # lines: seconds status d1 d2
engines/m2k/build/m2k-jack --render /tmp/x.wav --stems /tmp/x     # also /tmp/x_t1.wav ... _t8, _fx
```

## Ports and outputs

The JACK client is `M2K` (`--name`). Per track *n* = 1–8:

- `trackN_midi`: MIDI in. The channel is ignored. `--midi-connect N=TEXT`
  connects it to every JACK MIDI output port whose name contains TEXT.
- `trackN_L`, `trackN_R`: the track's own sound, i.e. its machine, its chain
  (AMP, FILT, FX, DSTR) and its own delay.

And one shared pair:

- `fx_L`, `fx_R`: the return of MONO2K's bus, i.e. the reverb the tracks send
  to (VERB, CC 19), then the bus's tape, ADPCM crunch and drive applied to that
  return. The tracks themselves don't pass through the bus.

A track's output is exactly its share of MONO2K's own mix (the same master and
drive gain, one block of latency, aligned with the return). Rendered against the
stock core (`--stock`), the tracks plus the return match the stock mix to within
1 LSB wherever the stock mix is below its soft limiter. The only differences are
where that limiter squashes the summed mix; the per-track outputs are float and
keep that headroom. The bus's tape, crunch and drive differ by design: in the
stock core they work on the whole mix, here only on the return.

Every pair connects to the first two physical playback ports when the process
starts, as Surge's do (`--no-audio-connect` to skip). pushpin then moves each
of its mono2k tracks onto its volume node input. The return stays on the
physical outputs.

`--enable 1,3` (or `none`) turns tracks on; without it all eight are on. An
off track ignores notes and falls silent (CC 9 turns it on and off later), so
a pushpin track that plays Surge can stay connected to its MONO2K track.

## MIDI (per track)

| Message | Effect |
|---|---|
| Note on/off | plays the track. Velocity is MONO2K's **accent**: over 100 the note plays accented (VOL raised by the pattern's ACNT, 60: about +3.3 dB), any other velocity at the same level. On pushpin's metro sequencer that's the top two velocity rows (111, 127). MONO2K's own MIDI path plays every note at 100; pushpin's addition passes the velocity on, to notes with no amp trig too (they accent the sounding note, as MONO2K's sequencer does) |
| Note on over a held note | MONO2K's **slide** (pushpin's addition): the pitch glides to the new note at AMP's PORT (PORT 0: a quick fixed glide), and the amp, filter envelope and LFOs go on without restarting. pushpin's gate-track **Tie** overlaps a note with the next one, so a tied step slides; pads played legato slide too. The slid-from note's note-off is ignored. The same note again over itself is a tie: the note goes on to its last note-off. Every track works alike (the core's own path for its keys' track, track 1 by default, isn't used) |
| CC 48–55 | SYN A–H (the machine's page) |
| CC 56–63 | AMP: ATK HOLD DEC REL DIST VOL PAN PORT |
| CC 72–79 | FILT: BASE (high-pass) WDTH HPQ LPQ FATK FDEC BOF WOF |
| CC 80–87 | FX: EQF EQG SRR DTIM DSND DFB DBAS DWID |
| CC 88/104/112 +0..7 | LFO 1/2/3: TRCK DEST WAVE TRIG MULT SPD PHAS DPTH |
| CC 7 / CC 3 | level / mute |
| **CC 9** | track on (64–127) / off (pushpin's addition) |
| **CC 14** | machine, value = number from `--list-machines`; loads that machine's INIT sound (pushpin's addition) |
| **CC 16–20** | DSTR: BITS FOLD XOR, reverb send, track pitch (pushpin's addition) |
| **CC 21 / 22 / 23** | trig types: 64–127 keeps the next notes from restarting the amp / the filter's envelope / the LFOs, 0–63 lets them again (MONO2K's step trig types; pushpin p-locks them on a step). A note with no amp trig moves the pitch and hears the step's locks, the sounding note's amp and gate go on, and its own note-off is ignored (pushpin's addition) |
| CC 120, 123 | all sound off / all notes off |
| NRPN 0:*n* | the parameter on CC *n* at 14 bits: CC 99 = 0, CC 98 = *n*, CC 6 = whole value, CC 38 = fraction × 128 (pushpin sends this) |
| NRPN 1:*p* | any of MONO2K's 71 track parameters by number *p*, including the 9 no CC reaches (arp, gate, MOD effect, wave bank); pushpin saves and loads whole sounds with it |
| **NRPN 1:71–78** | the Monomachine's ASSIGN > VEL (71–74) and KEY (75–78), pushpin's addition: two rows each of DEST (the parameter's number + 1, 0 off, as an LFO's DEST) and ADD (bipolar about 64). A note adds (ADD − 64) × *s* / 127 steps to DEST on its own track, *s* its velocity (VEL) or its note number (KEY), from its note-on to the next one (through the release too). A machine's INIT turns the rows off |
| **NRPN 1:79 / 80** | KEY's HPF / LPF: 64–127 the high-pass / low-pass follows the note, as MONO2K's always does; 0–63 it stays where note 60 puts it (`patches/0003-filter-tracking-switches.patch`). A machine's INIT turns both off: pushpin's default, so a sound keeps its filter wherever it's played |
| **NRPN 1:81–83** | FEEDBACK (81) and its EQ's EQF and EQG (82, 83), pushpin's addition: the track's own output, after everything on it (its chain and its delay), goes back into its chain where the machine's sound goes in, before DIST and the filters, one sample later. FEEDBACK is bipolar about 64: above it the signal goes back in phase, below it inverted; the gain is ((FEEDBACK − 64) / 64)², up to 2 at the ends, so the loop can drive itself into DIST's clip. The EQ is a band like FX's EQ at half its depth in dB (about +18 / −15.5 dB at the ends; gain 64: flat), since a boost in the loop is heard again on every pass. Last on the way back in, after the EQ and the gain, a fixed tanh soft-clips the feedback at about −8.7 dB of full scale: gentle feedback passes almost unchanged, and a screaming loop is held down (not a control). The amp's envelope is inside the loop, so the feedback dies with the note (`patches/0004-track-input-hook.patch`). A machine's INIT turns it off. (See 85–87 for where else it can come from and go; every route comes back one sample later, see "One sample at a time".) |
| **NRPN 1:85 / 86** | the feedback's SOURCE and DEST, pushpin's addition: SOURCE (a quarter of 0–127 each) takes the feedback after the machine (**OSC**), after the filters (**FILT**), after the amp (**AMP**) or from the track's whole out, its delay too (**OUT**, the INIT's: the loop as above). DEST 0 sends it back into the chain before DIST (**AMP IN**, the INIT's); any other value is the number + 1 of a parameter, as an LFO's DEST, and the feedback moves it instead of going back in: each sample of the tap (after the EQ and FEEDBACK's gain, no tanh) moves it for the next, 64 steps either way from a full-scale tap at gain 1, so FEEDBACK is its depth, at audio rate. The OSC, FILT and AMP taps are taken only while the track sounds, so the feedback still dies with the note (`patches/0006-track-tap-hook.patch` adds the FILT and AMP taps). A machine's INIT sets OUT and AMP IN |
| **NRPN 1:86 = 72** | the feedback's DEST past MONO2K's 71 parameters, pushpin's addition: **OSC FM**, phase modulation of the machine's oscillators by the feedback (`patches/0007`'s `m2k_phase_add`, a phase offset each oscillator adds where it reads its wave, every sample): 9.4 rad from a full-scale tap at FEEDBACK's gain 1, 19 rad at its top |
| **NRPN 1:88** | the feedback's EQ switch, pushpin's addition: 64–127 on (the INIT's; flat at EQG 64 anyway, so a sound saved before the switch keeps its EQ), 0–63 off: bypassed, EQF and EQG kept |
| **NRPN 1:87** | the feedback's TRACK, pushpin's addition: the track it's taken from (SOURCE is where on it), 0 the track's own (the INIT's), 1–8 track 1–8, as pushpin sends an LFO's TRCK. DEST stays this track's AMP IN, parameter or OSC FM, so a track's FEEDBACK page says what comes into it, and any number of tracks can take from one. It comes back one sample later, whatever order the tracks render in, so two tracks can feed each other. Into AMP IN it goes through this track's own chain and amp, so it's heard only while this track plays a note; OSC, FILT and AMP are only taken while the track they're taken from plays |
| **NRPN 1:84** | FX-FM's CARRIER, pushpin's addition (`patches/0005-fx-fm-machine.patch`): 0–63 the carrier on the track's own note, 64–127 on the track before's pitch (its note, glide and PTCH, plus this track's PTCH, the carrier's interval to the modulator). A machine's INIT sets it to the track's own note |
| clock | the tempo MONO2K times its LFOs (SPD), delays (DTIM) and AMP HOLD by: averaged over up to four beats, changed only past 0.25 % (pushpin's clock jitters; a moving delay time glides); a jump over 2 % starts the average over from the last beat. On any track's port, the first that sends it. MONO2K's sequencer stays stopped |
| start, continue | the LFOs on FREE back to their PHAS, so they line up with PLAY (the others restart on notes) |
| stop | ignored (the last tempo stays) |

In `--render` scripts the MIDI channel picks the track (channel 1 = track 1).

## One sample at a time

MONO2K works a 16-sample block at a time: envelopes, LFOs and parameters are
set once a block, and each stage of a track (its machine, its chain, MOD, VOL,
the pan, its delay) runs over the whole block before the next. A feedback loop
through that could only come back a block (0.36 ms) late, so it rang at
multiples of 2.76 kHz whatever was played, and a parameter moved by audio was
stepped at 2.76 kHz. `patches/0007-sample-slices.patch` lets every stage render
any slice of a block (`m2k_s0`, `m2k_s1`), and m2k-jack renders the tracks a
feedback joins one sample at a time, all of them in step, so **every feedback
route comes back one sample later**: from any tap (OSC, FILT, AMP, OUT), into
AMP IN or a parameter, on the track's own sound or another's.

- **What stays once a block:** the envelopes, the LFOs, pushpin's VEL/KEY rows,
  the glides and the machines' own sweeps. A parameter, though, is read again
  every sample, so a feedback into one moves it at audio rate (a filter's cutoff,
  a machine's pitch or depth, VOL, PAN). What is only read once a block (an
  envelope's times, an LFO's own settings) hears the feedback's first sample.
- **Which tracks:** a feedback's source and destination, and any FX machine that
  carries one's sound to the other. Every other track still renders whole blocks,
  before them, or after them if it hears one of them through an FX machine.
- **The same to the bit:** what changes once a block happens in the first slice
  (when the block goes on to use it) or the last (when only the next does), and
  what a later slice needs of the block's start is kept. So a track rendered a
  sample at a time with no feedback sounds exactly as a whole block does:
  `m2k-jack --render ... --sample-step` renders every track that way, and
  `tests/test_m2k_feedback.py` checks it to the bit on every machine, with DIST,
  EQ, FOLD, XOR, MOD and the delay on. Two exceptions: FX-DYN's compressor sets
  its gain from its whole block's peak, so one sample at a time it uses the block
  before's (within a dB); and a delay whose track sends it a whole block of exact
  silence while its line is already silent goes to sleep in a whole block, but
  one sample at a time can't know the block will stay silent and runs on (a few
  LSB in a silent delay's filters).
- **Cost**, measured on a Mac (20 s, eight held SWAV-SAW notes, FILT tap, EQ on):
  feedback on one track 1.18 times the original engine, on all eight 2.15 times,
  still 21 times faster than real time there. The engine without feedback is as
  fast as before. Not yet measured on the Pi.

## Resolution and smoothing

MONO2K stores every parameter as 0–127, and one step of FILT BASE or WDTH moves
the cutoff 1/8 octave (1.5 semitones). On its own the core applies a new value
at the next 16-sample block with no smoothing, so a knob turned through the
filter is heard as steps. m2k-jack fixes that:

- **Finer values.** `patches/0001-fine-parameter-offset.patch` adds a `fine`
  offset to each parameter, which the core's `P8()` adds in 1/256 of a step
  (the resolution its LFOs already use). NRPN values reach the sound at 1/128
  of a step.
- **Glide.** A new value is approached with a one-pole glide, `--glide-ms`
  (default 20; 0 turns it off), updated every block. Measured on a WDTH sweep
  sent one step every 30 ms, the largest cutoff change per 16-sample block went
  from 150 cents to 3.5 cents.
- **P-locks stay sharp.** A value that arrives within `--snap-ms` (default 10)
  of a note-on on its track, before or after it, is set at once, so pushpin's
  p-locks are heard on their note and not glided into.
- **Choices never glide.** Waves, modes, LFO destinations and other choices
  jump straight to the new choice.
- `--render ... --trace-param P` writes track 1's parameter P as the DSP reads
  it, once per block, to stderr (P is MONO2K's parameter number, e.g. 17 = WDTH).

On the pushpin side, `MidiCCClient` sends mono2k parameters as NRPN, so a
control's fractional value isn't rounded, and the filter and EQ frequency
controls (BASE, WDTH, EQF, DBAS) move half a step per encoder click (`"step"`
in their definitions).

## Using it for a pushpin track

Every track can play Surge XT or mono2k, chosen on the Push the way ADD DEVICE
picks a device: press **ADD TRACK** (the menu opens on the track's engine), move
the highlight with **Left/Right**, and press **ADD TRACK** again to switch to the
highlighted engine and close the menu (on the track's own engine it just
closes). The choice is saved in
`track_engines.json` (in pushpin's working directory) and used at the next start;
a track with no saved choice starts on its instrument JSON's `"engine"`
(`"surge-xt-cli"` or `"mono2k"`, default Surge XT).

How it works:

- Each track (`Instrument`) has a **voice** per engine: its own engine, device
  pages, slots and transport (OSC for Surge, `MidiCCClient` for mono2k). The
  track's `engine`, `osc`, `devices`, `slots` and `midi_out_device` are the
  active voice's.
- **Both engines run all the time** and both are routed through the volume node.
  Surge listens to the track's MIDI port (`Pushpin N`); mono2k to a second one,
  `Pushpin N m2k`. The sequencer and the pads only play the active engine's port,
  so the other one is silent. (Muting the inactive engine's PipeWire node doesn't
  work: a `pw-jack` client's output ignores node mute, measured on the Pi.)
- **Switching** sends all-notes-off to the old engine, initialises the new one's
  pages on its first use (for mono2k: its machine and INIT sound), clears the
  track's p-locks (they are stored by page position) and saves the choice.
- Surge's patch commands (`/patch/...`) always go to the track's Surge, so
  presets still load into it while the track plays mono2k; the mono2k pages
  are left alone.
- Without `engines/m2k/build/m2k-jack` (or `PUSHPIN_M2K_BIN`) there is no mono2k
  voice: the menu shows Monomachine dimmed and every track plays Surge.

pushpin starts one `pw-jack m2k-jack --name M2K --enable 1,…,8 --midi-connect
N="Pushpin N-1 m2k" …` for all tracks. A track's `instrument_index` (0–7) is
its MONO2K track. The log goes to `m2k.log` in pushpin's log directory.

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
- **FX-FM** (machine 19, pushpin's addition: `patches/0005-fx-fm-machine.patch`):
  FM with the track before as the modulator, the way FX-CHORUS and FX-RING
  hear it (after its amp and filter, before its VOL, so its VOL or LEVL at 0
  silences it and the FM goes on; track 1 has no track before, and plays the
  plain carrier). The carrier is one of MONO2K's 32 waves (DIGI-WAV's M2K
  bank) on this track's own note, so the FX track needs notes of its own; the
  modulator's amp envelope becomes the FM index's. SYN A–H: **WAVE** the
  carrier's wave, a knob named as DIGI-WAV's on M2K (SINE, the INIT, to NOIZ;
  four values a wave, and it plays the wave it names, never a blend of two; it
  ignores BANK, so FX-FM has none), **DEP** the depth on FM+'s law at 4/3 its
  depth (about 19 rad at 127 from a full-scale modulator; the INIT's 68 is
  about 3 rad off GND-SIN's INIT), **DEC** the depth falling from the trig (127 held, 0
  quickest), **MIX** (0 the modulator as it came in, 127 the carrier alone),
  **FB** the carrier's own feedback (FM+STAT's), **TONE** a lowpass on the
  modulator (127 open), **TUNE** ±2 semitones, **INP** the modulator's level
  (100 unity). The second page has **CARRIER** at knob 1 (where DIGI-WAV has
  BANK): **OWN NOTE** (the INIT) puts the carrier on FX-FM's own note;
  **PREV TRK** puts it on the track before's pitch (its note, glide and PTCH),
  so FX-FM's **PTCH** (knob 2) is the carrier's interval to the modulator
  whatever it plays (+12: ratio 2), and FX-FM's own notes only start and stop
  the sound. It's m2k-jack's own parameter 84 on the machine's slot, so it
  p-locks with the machine page. `tests/test_m2k_fxfm.py` renders it and
  checks the sidebands against Bessel functions.
- **DSTR**: BITS, FOLD, XOR and the reverb send (VERB), then MONO2K's MOD effect:
  TYPE (a menu: CHOR, FLNG, PHAS; four clicks an item), RATE, DPTH and MIX. The
  MOD parameters have no CC; the page sends them as NRPN 1:66–69.
- **AMP, FILT, FX, DSTR, LFO 1–3**: the other seven upper-row buttons, all on
  the first page. Each device has a device slot of its own (machine 0, AMP 1,
  FILT 2, FX 3, DSTR 4, LFO 1–3 5–7; `M2KEngine.always_shown_slots`), because
  p-locks are stored by slot: two devices in one slot would share their locks.
- **LFO 1–3**: knob 1 (DEVICE) picks the device to modulate (OFF, SYN, AMP,
  FILT, FX, DSTR, LFO 1–3) and knob 2 (DEST) the parameter on it, like Surge's
  filter-type pages (a switch whose groups each hold a menu); four clicks an
  entry. SYN's entries take the current machine's own names. They set MONO2K's
  DEST (the parameter's number + 1). Then WAVE TRIG MULT SPD PHAS and DPTH,
  which is bipolar and shown as -64..+63 (0: no modulation).
  The second page (Right) has TRCK: the track the LFO modulates, OWN (its own
  track, the default) or TRK 1–8 (the Push's tracks, Pushpin 0–7 inside). m2k-jack turns that into MONO2K's own TRCK
  encoding, which a CC can't reach for tracks 7–8.
- **VELOCITY and KEY TRACK** (the second instrument page: **Right** arrow;
  **Left** goes back): the Monomachine's ASSIGN > VEL and KEY. Two rows of four
  knobs each: DEVICE and DEST pick the parameter to move (the same menus as an
  LFO's), ADD how far a note moves it at full velocity (VEL) or at note 127
  (KEY), bipolar, shown -64..+63; a softer or lower note moves it in
  proportion. The metro sequencer's velocity rows send 15, 31 … 127, so the
  lowest row still moves it an eighth of ADD. KEY TRACK's rows end on **HPF**
  and **LPF**: ON, the filter follows the note (MONO2K's own way); OFF (the
  default on every machine's INIT, a factory sound and an old save), it
  stays where note 60 would put it, so a high note isn't brighter. Each page
  has its own slot (8, 9), so they p-lock like the other pages. m2k-jack keeps
  them beside MONO2K's parameters (NRPN 1:71–80); `patches/0002` makes room in
  the core's modulation queue for their four rows (three LFOs a track before)
  and `patches/0003` adds the filters' switches.
- **FEEDBACK** (the second instrument page, after VELOCITY and KEY TRACK), what
  comes into the track: **DEVICE** and **DEST** at knobs 1–2, where it goes on
  this track: **AMP IN** (back into the chain before DIST, ahead of the filters),
  any parameter an LFO reaches, from the LFOs' own menus, or **OSC FM**, at the
  end of SYN's menu: phase modulation, as the FM machines' own (FM+, FX-FM): the
  feedback added to the phase every oscillator of the machine reads its wave at,
  a sample at a time (sub-oscillators an octave or two down a half or a quarter
  of it, so they stay locked). A full-scale tap is 9.4 rad at FEEDBACK's gain 1
  and 19 rad at its top, FX-FM's deepest. GND-PERC's noise, GND-NOIS, FX-CHORUS
  and FX-DYN have no oscillator to bend: there it does nothing; **FEEDBACK SOURCE**
  (OSC, FILT, AMP, OUT) at knob 3, where it's taken from, on **FROM TRACK** at
  knob 4 (**OWN**, the default, or **TRK 1–8**, the Push's tracks); **FEEDBACK
  EQ** (EQ ON, the default, or EQ OFF), **FEEDBACK EQ FREQ** and **FEEDBACK EQ
  GAIN** at knobs 5–7; **FEEDBACK**, how much, at knob 8. FEEDBACK is bipolar
  (shown −64..+63, negative goes back inverted; 0 is none); the EQ reads and
  steps like FX's EQ (half a step a click on the frequency), with half its
  boost and cut in dB, and switched off it's bypassed whatever its frequency
  and gain.
  It's m2k-jack's own parameters 81–83 and 85–88, in a slot of its own (10), so
  it p-locks like the other pages. (It used to be FILT's second page, which is
  FILTER TRIG alone again: p-locks a sequence saved then on FEEDBACK land on
  nothing now.)
- **Second pages**: every machine has PTCH (pitch in semitones, bipolar, shown
  -64..+63) at knob 2 of its second page; DIGI-WAV also has BANK (M2K or M64,
  NRPN 1:70) at knob 1.
- **Not on any page**: the arp, which m2k-jack keeps OFF whatever arrives (and
  never exports as on), and LEVL. Every machine's INIT and every sound sets
  LEVL (CC 7), so a track always starts at its sound's own level; the track's
  **Master** encoder scales it on the way out (dB taper, MONO2K's LEVL is
  square-law), so loading a sound keeps the Master setting and saving one
  keeps the sound's own LEVL. The Swing encoder's post-synth fader is PipeWire's.
- **Values in MONO2K's own words**: `m2k-jack --describe` exports what the
  FM-1's screen shows for every value of every parameter (m2k_ui.c's `fmt()`),
  and the generator uses it. A choice (the waves, LFO TRIG and MULT, SID MOD and
  MSRC, the on/off switches, FM+'s 24 ratios, VOX-6's CONS, CLAP, MOD TYPE) or a
  parameter with few distinct values (BITS) is a menu; each item owns its run of
  values, so a value from a sound or a p-lock shows the right item. A quantity
  (SRR, DTIM, EQF, DBAS, envelope times, BASE and WDTH in octaves, TUNE in
  cents, PAN, LFO DPTH in %, MOD RATE in Hz) stays a knob that shows the words.
  DIGI-WAV's WAVE names follow its BANK and an LFO's SPD (bars, beats, a note)
  its MULT. AMP's HOLD stays a number: MONO2K shows it in ms at the tempo.

Every control's address is `/cc/<n>`. On a mono2k track the instrument's
`MidiCCClient` (`cc_client.py`) turns those into MIDI CCs on the track's MIDI
port, and sends each value back through the instrument's OSC dispatcher, the
way Surge echoes values. That way the display, the device slot that selects
the machine, and sequencer p-locks work as they do for Surge.

## Saving sounds (the preset browser)

On a track playing Monomachine, BROWSE works as it does for Surge, with
mono2k's own sounds:

- **Slots.** Each track has 8 slots (the pad rows). A slot keeps a whole sound:
  the machine and all 89 parameters (MONO2K's 71, then VEL's 4, KEY TRACK's 6, the feedback's 3, FX-FM's CARRIER and the feedback's SOURCE, DEST, TRACK and EQ switch), in
  `~/.local/share/pushpin/m2k_state/<track>_<slot>.json`. Switching slots saves
  the one being left and plays the new one; an empty slot starts on its
  machine's INIT (the track's `m2k_machine`, else GND-SIN). The current slot is
  also saved when you leave the browser or switch the track's engine, and every
  5 seconds while it changes, so a power cut loses at most that much. At startup
  each mono2k track gets its current slot back.
- **Browsing.** Hold a slot's pad for half a second (or hold SELECT and press
  the pad, which opens it at once), keep the pad held and turn the encoders (one
  per level of the tree). Opened by a long press, releasing the pad loads a
  sound only if you turned an encoder, so holding a pad and letting go never
  replaces the slot's sound. The tree is **Factory**
  (MONO2K's 96-sound library, by category: KICK SNARE HATS PERC BASS LEAD PAD FX),
  **Machines** (each machine's INIT) and **User**. Releasing the pad loads the
  highlighted sound into the slot; the slot's name is kept in `m2k_presets.json`.
- **Saving.** In the browser, upper button 1, **Save to Current**, saves the
  sound into the slot; upper button 2, **Save to New**, saves it as a new user
  preset (`~/.local/share/pushpin/m2k_presets/<MACHINE> <n>.json`) and names the
  slot after it. Upper button 7 names the slot after the browsed sound.
- **Renaming.** Upper button 3, **Rename**, opens a name editor for the slot's
  user preset: Left/Right move the cursor (Right past the end adds a letter),
  Up/Down change the letter, DELETE removes it, SELECT saves, button 3 again
  cancels. Holding SHIFT shows a keyboard (every letter, digit and symbol in a
  grid): the arrows move around it while SHIFT is held, and letting go of SHIFT
  types the highlighted character and moves the cursor to the next position. The preset file is renamed and every slot using it follows. Factory
  sounds can't be renamed (Save to New first). On Surge tracks the same button
  renames Surge user patches (the `.fxp` in Surge's user patch folder).

How: the voice's `MidiCCClient` keeps the last value it sent for every address,
and a machine's init sets every parameter, so its cache is the track's sound
(`m2k_state.capture`). Loading sends the machine, then every parameter, through
the same client (`m2k_state.apply`), so the pages follow. Parameters a page
reaches go as their CC, the others as NRPN 1:*p*. `sounds.json`
(`gen_definitions.py`) holds which is which, the machines' INITs and the library.

## Known limits of the spike

- The JACK path builds only where JACK headers exist (the Pi; on macOS only
  `--render` builds). It has been played on a Pi 5 through PipeWire's JACK.
- Both engines of every track run all the time (8 Surge instances, one
  m2k-jack), so a track on mono2k still has its idle Surge using some CPU.
- Switching a track clears its p-locks, in the sequence that's loaded; other
  clips saved for the track keep theirs, which then land on the other engine's
  parameters if loaded.
- The core runs at 44.1 kHz and is resampled linearly to the JACK rate (48 kHz on
  the Pi), which loses a little treble.
- The bus (reverb decay, tape, crunch, drive) has no CC; it runs with the blank
  pattern's settings. Only each track's reverb send (CC 19) is controllable.
- The snap window can misfire: a knob move that happens within 10 ms of a
  sequenced note is set at once rather than glided.
- Choosing a machine always loads its INIT sound (AMP, FILT, FX and LFOs too),
  because pushpin can't read values back from m2k-jack and needs to know them.
- DIGI-WAV's WAVE stays a knob (showing the wave's name): its waves change
  with BANK (32 or 64), so no one menu holds both. AMP HOLD stays a number:
  MONO2K shows it in ms at the tempo.
- Before the first PLAY there's no clock, so m2k-jack runs at 120 BPM; while
  stopped it keeps the last tempo it heard.

## Tempo

pushpin's global timeline sends MIDI clock to every Surge port and to one
mono2k port (the first track with a mono2k voice: `mono2k_clock_port` in
modes/instrument.py), since one m2k-jack plays every track. PLAY sends Start,
STOP sends Stop and the clock stops; m2k-jack keeps the last tempo meanwhile.
Without a clock (before the first PLAY) it runs at 120 BPM.
`tests/test_m2k_clock.py` renders a 1/4-note delay at 90 and 140 BPM, and at
100 BPM with a jittery clock, through the built binary.
