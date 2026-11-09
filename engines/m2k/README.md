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
| clock | the tempo MONO2K times its LFOs (SPD), delays (DTIM) and AMP HOLD by: averaged over up to four beats, changed only past 0.25 % (pushpin's clock jitters; a moving delay time glides); a jump over 2 % starts the average over from the last beat. On any track's port, the first that sends it. MONO2K's sequencer stays stopped |
| start, continue | the LFOs on FREE back to their PHAS, so they line up with PLAY (the others restart on notes) |
| stop | ignored (the last tempo stays) |

In `--render` scripts the MIDI channel picks the track (channel 1 = track 1).

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
  track, the default) or TRK 1–8. m2k-jack turns that into MONO2K's own TRCK
  encoding, which a CC can't reach for tracks 7–8.
- **Second pages**: every machine has PTCH (pitch in semitones, bipolar, shown
  -64..+63) at knob 2 of its second page; DIGI-WAV also has BANK (M2K or M64,
  NRPN 1:70) at knob 1.
- **Not on any page**: the arp, which m2k-jack keeps OFF whatever arrives (and
  never exports as on), and LEVL, left to PipeWire for volume. Every machine's
  INIT and every sound still sets LEVL (CC 7), so a track always starts at its
  sound's own level.
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
  the machine and all 71 parameters, in
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
