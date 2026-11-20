// Pushpin's interactive manual: a Push 2 drawn in SVG that changes as you
// switch modes, and explains whatever control you point at.
// The words come from manual/manual.json; this file only draws and switches.
(function () {
  "use strict";

  const SVG_NS = "http://www.w3.org/2000/svg";
  const root = document.getElementById("manual");
  if (!root) return;

  // ---- Layout (viewBox units, roughly millimetres x 2.1) -----------------
  // Proportions follow the Push 2 itself: encoders along the top, the upper
  // button row ABOVE the display and the lower row below it, a wide touch
  // strip, pads a little wider than tall, and the diamond arrow keys.
  const W = 800, H = 643;
  const COL_X = (i) => 146 + i * 61;           // the 8 columns over the display and pads
  const PAD_W = 54, PAD_H = 40, PAD_Y = 255, ROW = 46;
  const ENC_Y = 32;

  // [id, label, x, y, w, h, icon]
  const SIDE_BUTTONS = [
    ["tap_tempo", "Tap Tempo", 12, 61, 55, 24], ["metronome", "Metronome", 68, 61, 56, 24],
    ["delete", "Delete", 12, 107, 43, 40], ["undo", "Undo", 12, 148, 43, 42],
    ["mute", "Mute", 12, 213, 36, 24], ["solo", "Solo", 49, 213, 36, 24], ["stop", "Stop Clip", 86, 213, 38, 24],
    ["convert", "Convert", 12, 255, 43, 37], ["double_loop", "Double Loop", 12, 293, 43, 37], ["quantize", "Quantize", 12, 331, 43, 38],
    ["duplicate", "Duplicate", 12, 375, 43, 38], ["new", "New", 12, 414, 43, 38],
    ["fixed_length", "Fixed Length", 12, 463, 43, 36], ["automate", "Automate", 12, 500, 43, 36],
    ["record", "", 12, 538, 43, 38, "record"], ["play", "", 12, 579, 43, 41, "play"],

    ["setup", "Setup", 705, 61, 40, 24], ["user", "User", 746, 61, 40, 24],
    ["add_device", "Add Device", 651, 107, 42, 40], ["add_track", "Add Track", 651, 148, 42, 42],
    ["device", "Device", 705, 107, 40, 40], ["mix", "Mix", 746, 107, 40, 40],
    ["browse", "Browse", 705, 148, 40, 42], ["clip", "Clip", 746, 148, 40, 42],
    ["master", "Master", 651, 213, 42, 24],
    ["repeat", "Repeat", 705, 393, 40, 40], ["accent", "Accent", 746, 393, 40, 40],
    ["scale", "Scale", 705, 434, 40, 36], ["layout", "Layout", 746, 434, 40, 36],
    ["note", "Note", 705, 471, 40, 34], ["session", "Session", 746, 471, 40, 34],
    ["shift", "Shift", 705, 595, 40, 25], ["select", "Select", 746, 595, 40, 25],
  ];
  // The two diamond keys: [x, y, size, [top, right, bottom, left] ids, labels]
  const DIAMONDS = [
    [705, 213, 81, ["up", "right", "down", "left"], ["", "", "", ""]],
    [705, 510, 81, ["octave_up", "page_right", "octave_down", "page_left"], ["Octave", "Page", "Octave", "Page"]],
  ];
  // The scene buttons right of the pads, top to bottom
  const SCENE = ["1_32t", "1_32", "1_16t", "1_16", "1_8t", "1_8", "1_4t", "1_4"];
  const SCENE_LABEL = { "1_4": "1/4", "1_4t": "1/4t", "1_8": "1/8", "1_8t": "1/8t", "1_16": "1/16", "1_16t": "1/16t", "1_32": "1/32", "1_32t": "1/32t" };

  const NAMES = {
    enc_tempo: "Tempo encoder", enc_swing: "Swing encoder", enc_master: "Master encoder",
    touchstrip: "Touch strip", up: "Up", down: "Down", left: "Left", right: "Right",
    octave_up: "Octave Up", octave_down: "Octave Down", page_left: "Page Left", page_right: "Page Right",
  };
  for (let i = 1; i <= 8; i++) {
    NAMES["enc_" + i] = "Encoder " + i;
    NAMES["upper_row_" + i] = "Upper button " + i;
    NAMES["lower_row_" + i] = "Lower button " + i;
  }
  SIDE_BUTTONS.forEach(([id, label]) => { if (!NAMES[id]) NAMES[id] = label; });
  SCENE.forEach((id) => { NAMES[id] = SCENE_LABEL[id]; });

  const DEVICE_CONTROLS = new Set(["upper_row_1", "upper_row_2", "upper_row_3", "upper_row_4", "upper_row_5", "upper_row_6", "upper_row_7", "upper_row_8",
    "page_left", "page_right", "left", "right", "enc_1", "enc_2", "enc_3", "enc_4", "enc_5", "enc_6", "enc_7", "enc_8"]);

  // ---- Demo content the pads show ----------------------------------------
  const LAYER_COLOR = { pitch: "green", octave: "orange", velocity: "yellow", gate: "turquoise", skips: "red", lock_scale: "blue" };
  const DEMO = {
    seqs: [],              // each track's sequencer (MetroSequencerMode.instrument_sequencers), made when first shown
    // ClipSelectionMode: which clips each track has a file for, and the clip it's on
    clipHas: [[0, 1, 2], [0, 1], [0, 1, 2, 3], [0], [0, 1], [0], [0, 1, 2, 3], [0, 1]], clipSel: [0, 1, 2, 0, 1, 0, 3, 0],
    slotSel: [0, 2, 1, 0, 4, 0, 3, 7],      // each track's current slot (last_pad_in_column_pressed)
    muted: { "3,2": 1, "0,5": 1, "4,1": 1, "1,6": 1 },
  };
  // ---- Each track's sequencer, in MetroSequencerMode's own terms ------------
  // Each layer is an 8x8 grid of pad states, row 0 at the top, one column per
  // stage: true (lit), false (dark), and in the gate layer "Off" (a pulse with
  // no gate) and "Tie". Step s of the sequencer is stage s / 8, pulse s % 8
  // counted up from the bottom pad. Parameter locks belong to a whole stage.
  const T = true, O = "Off", I = "Tie";
  // Per track: pad heights per stage (0 = bottom row), each stage's pulses from the
  // bottom up (the stage is as long as the list), chance rows (7 = always), skipped
  // stages, a semitone (stage -> the lower pad), and locks "slot:control" -> value
  const SEQ_DEMOS = [
    { // 1: the first example: a bit of everything
      pitch: [0, 2, 4, 0, 5, 4, 2, 7], semitone: { 6: 2 }, octave: [2, 2, 3, 2, 1, 2, 3, 4], velocity: [6, 3, 5, 3, 7, 2, 5, 4],
      gate: [[T, O, T, T], [T, T], [T, I, T, O], [T], [T, O, T], [T, T, T, T], [T, O], [T, T, O, T, O, T, T, T]],
      chance: [7, 7, 4, 7, 7, 3, 7, 7], skip: [4], lockScale: [7, 7, 5, 7, 7, 3, 7, 7],
      locks: { 2: { "2:0": 0.82, "2:1": 0.6 }, 6: { "4:3": 0.7 } } },
    { // 2: a mono2k bass line, tied notes, the filter opening on two stages
      pitch: [0, 0, 4, 0, 0, 3, 0, 5], octave: [1, 1, 1, 2, 1, 1, 2, 1], velocity: [6, 4, 7, 4, 6, 4, 7, 3],
      gate: [[T, I], [T], [T, O, T], [T, I, I], [T], [T, T], [T, O], [T, I, O, T]],
      chance: [7, 7, 7, 7, 7, 7, 5, 7], skip: [], lockScale: [7, 7, 7, 7, 7, 7, 7, 7],
      locks: { 2: { "2:0": 96 }, 7: { "2:0": 110, "2:3": 70 } } },
    { // 3: hi-hats: long stages of short pulses, some left to chance
      pitch: [0, 0, 0, 0, 0, 0, 0, 0], octave: [3, 3, 3, 3, 3, 3, 3, 3], velocity: [7, 3, 5, 3, 7, 3, 5, 2],
      gate: [[T, O, T, O, T, O, T, O], [T, T, T, T], [T, O, T, O, T, O, T, T], [T, T], [T, O, T, O, T, O, T, O], [T, T, T, T], [T, O, T, T, O, T, T, O], [T, T, T, T, T, T, T, T]],
      chance: [7, 5, 7, 4, 7, 5, 6, 3], skip: [], lockScale: [7, 7, 7, 7, 7, 7, 7, 7],
      locks: { 7: { "4:3": 0.2 } } },
    { // 4: a pad: long notes tied across each stage
      pitch: [0, 2, 4, 5, 4, 2, 0, 4], octave: [3, 3, 3, 3, 3, 3, 3, 3], velocity: [4, 4, 4, 4, 5, 4, 4, 5],
      gate: [[T, I, I, I], [T, I, I, I], [T, I, I, I], [T, I, I, I], [T, I, I, I], [T, I, I, I], [T, I, I, I], [T, I, I, I]],
      chance: [7, 7, 7, 7, 7, 7, 7, 7], skip: [], lockScale: [7, 7, 7, 7, 7, 7, 7, 7],
      locks: { 3: { "2:0": 0.4 }, 7: { "2:0": 0.9 } } },
    { // 5: a lead line with a semitone and one stage skipped
      pitch: [4, 5, 2, 4, 7, 5, 4, 2], semitone: { 1: 4 }, octave: [3, 3, 3, 3, 4, 3, 3, 3], velocity: [6, 5, 6, 5, 7, 5, 6, 4],
      gate: [[T, T], [T, I], [T], [T, O, T], [T, T], [T, I, I], [T, O], [T]],
      chance: [7, 7, 7, 7, 7, 6, 7, 7], skip: [6], lockScale: [7, 7, 7, 4, 7, 7, 7, 7],
      locks: { 3: { "2:1": 0.75 } } },
    { // 6: an arpeggio climbing the scale
      pitch: [0, 1, 2, 3, 4, 5, 6, 7], octave: [2, 2, 2, 2, 3, 3, 3, 3], velocity: [6, 4, 5, 4, 6, 4, 5, 4],
      gate: [[T, T], [T, T], [T, T], [T, T], [T, T], [T, T], [T, T], [T, T]],
      chance: [7, 7, 7, 7, 7, 7, 7, 7], skip: [], lockScale: [7, 7, 7, 7, 7, 7, 7, 7],
      locks: {} },
    { // 7: sparse notes, mostly left to chance
      pitch: [0, 4, 2, 6, 0, 3, 5, 1], octave: [2, 3, 2, 3, 2, 3, 2, 3], velocity: [5, 6, 4, 7, 5, 6, 4, 7],
      gate: [[T], [T, O], [T], [T, O, O], [T], [T, O], [T], [T, O, O, O]],
      chance: [4, 3, 5, 2, 4, 3, 5, 6], skip: [], lockScale: [7, 7, 7, 7, 7, 7, 7, 7],
      locks: { 1: { "4:3": 0.85 } } },
    { // 8: a sub bass, its locks fading in
      pitch: [0, 0, 0, 0, 3, 3, 4, 4], octave: [1, 1, 1, 1, 1, 1, 1, 1], velocity: [7, 6, 7, 6, 7, 6, 7, 6],
      gate: [[T, I, I], [T], [T, I, I], [T], [T, I, I], [T], [T, I, I], [T]],
      chance: [7, 7, 7, 7, 7, 7, 7, 7], skip: [], lockScale: [1, 2, 3, 4, 5, 6, 7, 7],
      locks: { 0: { "2:0": 0.7 }, 2: { "2:0": 0.7 }, 4: { "2:0": 0.7 }, 6: { "2:0": 0.7 } } },
  ];

  function seqDemo(t) {
    const d = SEQ_DEMOS[t % SEQ_DEMOS.length];
    const grid = () => Array.from({ length: 8 }, () => new Array(8).fill(false));
    // one lit pad per stage, given as its height (0 = bottom row)
    const column = (heights) => { const g = grid(); heights.forEach((h, c) => { g[7 - h][c] = true; }); return g; };
    const pitch = column(d.pitch);
    Object.entries(d.semitone || {}).forEach(([c, h]) => {           // two neighbouring pads: the semitone between
      for (let r = 0; r < 8; r++) pitch[r][c] = false;
      pitch[7 - h][c] = true; pitch[7 - (h + 1)][c] = true;
    });
    const gate = grid();
    d.gate.forEach((pulses, c) => pulses.forEach((v, h) => { gate[7 - h][c] = v; }));
    const skips = column(d.chance);
    d.skip.forEach((c) => { skips[7][c] = true; });
    return {
      layers: { pitch: pitch, octave: column(d.octave), velocity: column(d.velocity), gate: gate, skips: skips, lock_scale: column(d.lockScale) },
      // SequencerMetro.locks, a stage at a time: "slot:control index" -> the locked value
      locks: Array.from({ length: 8 }, (_, c) => Object.assign({}, d.locks[c] || {})),
      step: 0,             // SequencerMetro.step_index: there is always exactly one
    };
  }
  // The selected track's sequencer
  Object.defineProperty(DEMO, "seq", { get: () => DEMO.seqs[state.track] || (DEMO.seqs[state.track] = seqDemo(state.track)) });
  // Every track's sequencer, for the clock that moves them all
  const allSeqs = () => { for (let t = 0; t < 8; t++) if (!DEMO.seqs[t]) DEMO.seqs[t] = seqDemo(t); return DEMO.seqs; };

  const hasLocks = (c) => Object.keys(DEMO.seq.locks[c]).length > 0;
  // The stage whose locks show: the pad held down (MetroSequencerMode.held_lock_step)
  const heldStage = () => (state.mode === "seq" && state.heldStep ? state.heldStep.c : null);
  // A device's control by its index across pages (lockable_controls: page * 8 + position)
  const controlAt = (key, index) => (devices.devices[key].pages[Math.floor(index / 8)] || [])[index % 8];

  // SequencerMetro.increment_index: the next step whose gate isn't off-the-stack
  // (false) and whose stage isn't skipped
  function nextStep(sq) {
    let i = sq.step;
    for (let n = 0; n < 64; n++) {
      i = (i + 1) % 64;
      const stage = Math.floor(i / 8), pulse = i % 8;
      if (sq.layers.gate[7 - pulse][stage] !== false && sq.layers.skips[7][stage] !== true) return i;
    }
    return sq.step;
  }

  const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
  const ROOT = 64;                        // MelodicMode's default root note (E)
  const MAJOR = [1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1];
  const padNote = (r, c) => ROOT + (7 - r) * 5 + c;

  // ---- State --------------------------------------------------------------
  const state = {
    mode: "play",          // pad mode: play | seq | clips | mutes | presets
    layer: "gate",         // the sequencer layer
    overlay: null,         // settings | device_menu | engine_menu | scale_menu | rename
    settingsPage: 0,
    track: 0,
    held: { shift: false, select: false },
    playing: false,
    display: true,
    hover: null,
    tracks: [],            // per track: engine, device page, shown devices (see trackState)
    menuIndex: 0,          // the highlight in the device menu
    engineIndex: 0,        // the highlight in the engine menu
  };
  let data = null;
  let devices = null;      // manual/devices.json, written by tools/build_manual_devices.py
  const el = {};           // id -> SVG element (shape) for each control
  const pads = [];         // [row][col] rects

  // ---- Helpers ------------------------------------------------------------
  function svg(tag, attrs, parent) {
    const n = document.createElementNS(SVG_NS, tag);
    for (const k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }
  const color = (name) => (data && data.colors[name]) || name;
  const trackColor = (i) => color(data.tracks[i]);
  // definitions.py's "<colour>_darker1": the HLS lightness times 0.35
  function darker1(hex) {
    const n = parseInt(hex.slice(1), 16);
    let [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => v / 255);
    const mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 2;
    let h = 0, sat = 0;
    if (mx !== mn) {
      const d = mx - mn;
      sat = l <= 0.5 ? d / (mx + mn) : d / (2 - mx - mn);
      h = mx === r ? (g - b) / d / 6 : mx === g ? (2 + (b - r) / d) / 6 : (4 + (r - g) / d) / 6;
      h = ((h % 1) + 1) % 1;
    }
    const L = Math.max(0, Math.min(1, 0.35 * l));
    const v = (m1, m2, hue) => { hue = ((hue % 1) + 1) % 1; if (hue < 1 / 6) return m1 + (m2 - m1) * hue * 6; if (hue < 0.5) return m2; if (hue < 2 / 3) return m1 + (m2 - m1) * (2 / 3 - hue) * 6; return m1; };
    let out = [L, L, L];
    if (sat !== 0) { const m2 = L <= 0.5 ? L * (1 + sat) : L + sat - L * sat, m1 = 2 * L - m2; out = [v(m1, m2, h + 1 / 3), v(m1, m2, h), v(m1, m2, h - 1 / 3)]; }
    return "#" + out.map((x) => Math.round(x * 255).toString(16).padStart(2, "0")).join("");
  }

  function dim(hex, f) {
    const n = parseInt(hex.slice(1), 16);
    const c = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => Math.round(v * f));
    return "#" + c.map((v) => v.toString(16).padStart(2, "0")).join("");
  }
  function modeData() { return data.modes[state.mode]; }

  // Each track keeps its own engine, device page and choice of device in each slot
  function trackState(i) {
    i = i === undefined ? state.track : i;
    if (!state.tracks[i]) {
      const engine = i === 1 ? "mono2k" : "surge";      // track 2 shows mono2k's pages
      state.tracks[i] = { engine: engine, instrPage: 0, device: 0, devPage: {}, shown: {} };
    }
    const t = state.tracks[i];
    if (!t.shown[t.engine]) t.shown[t.engine] = Object.assign({}, devices.engines[t.engine].shown);
    t.shownNow = t.shown[t.engine];          // slot -> the device it holds, for the track's engine
    return t;
  }
  // The device keys on the upper row: one per slot of the instrument page
  function deviceTabs() {
    const t = trackState(), e = devices.engines[t.engine];
    return e.pages[t.instrPage].map((slot) => t.shownNow[slot]);
  }
  // The devices the slot being edited can hold (ADD DEVICE lists them)
  function slotChoices() {
    const t = trackState(), e = devices.engines[t.engine];
    const key = deviceTabs()[t.device];
    return e.slots[String(devices.devices[key].slot)];
  }
  function visibleControls() {
    const t = trackState(), key = deviceTabs()[t.device];
    return devices.devices[key].pages[t.devPage[key] || 0];
  }
  function layerData() { return data.modes.seq.layers[state.layer]; }
  function overlayData() {
    if (!state.overlay) return null;
    const o = data.overlays[state.overlay];
    return state.overlay === "settings" ? Object.assign({}, o, o.pages[state.settingsPage]) : o;
  }

  // What a control does right now
  function helpFor(id) {
    const o = overlayData();
    const held = data.modes.seq.held || {};
    if (!o && heldStage() !== null && held[id]) return held[id];
    if (o && o.controls && o.controls[id]) return o.controls[id];
    if (state.mode === "seq") {
      const l = layerData();
      if (l.controls && l.controls[id]) return l.controls[id];
    }
    const m = modeData();
    if (m.controls && m.controls[id]) return m.controls[id];
    if ((state.mode === "presets" || (o && o.hidesDevices)) && DEVICE_CONTROLS.has(id)) return null;
    return data.global[id] || null;
  }

  // ---- What a sequencer step is, from the same rules SequencerMetro plays by
  const MAJOR_SCALE = [0, 2, 4, 5, 7, 9, 11, 12];        // MetroSequencerMode.major_scale
  const DEGREES = ["root (C)", "2nd (D)", "3rd (E)", "4th (F)", "5th (G)", "6th (A)", "7th (B)", "octave (C)"];
  const noteName = (n) => NOTE_NAMES[((n % 12) + 12) % 12] + (Math.floor(n / 12) - 2);
  function litHeights(grid, c) { const out = []; for (let h = 0; h < 8; h++) if (grid[7 - h][c] === true) out.push(h); return out; }
  function stageFacts(c) {
    const sq = DEMO.seq, L = sq.layers;
    // pitch: one pad is a scale note; two neighbouring pads the semitone above the lower
    const ph = litHeights(L.pitch, c);
    let pitch = 0;
    if (ph.length === 2 && ph[1] - ph[0] === 1) pitch = MAJOR_SCALE[ph[0]] + 1;
    else if (ph.length) pitch = MAJOR_SCALE[ph[ph.length - 1]];
    const octave = litHeights(L.octave, c)[0] || 0;
    const vh = litHeights(L.velocity, c);
    const velocity = ((vh.length ? vh[0] : 0) + 1) * 16 - 1;     // note_for_step
    let chance = 1;                                               // probability_for_step: 1 in 6 unless a row says
    for (let x = 0; x < 7; x++) if (L.skips[6 - x][c] === true) chance = x;
    const lh = litHeights(L.lock_scale, c);
    let length = 0;
    for (let h = 0; h < 8; h++) if (L.gate[7 - h][c] !== false) length = h + 1;
    return { pitch: pitch, octave: octave, note: pitch + octave * 12, velocity: velocity, chance: chance,
      skipped: L.skips[7][c] === true, lockScale: lh.length ? lh[0] / 7 : 0, length: length };
  }
  // probability_for_step: a note plays when a roll of 1 to 6 is at most the chance, x
  const chanceText = (x) => `so it plays ${Math.round((x * 100) / 6)}% of the time (${x}/6)`;
  const pct = (f) => Math.round(f * 100) + " %";

  // The hover text for a sequencer pad: what it is, then what is true of its stage
  function stepHelp(r, c) {
    const sq = DEMO.seq, L = state.layer, v = sq.layers[L][r][c], h = 7 - r, f = stageFacts(c);
    const lines = [];
    let title = "", where = "Stage " + (c + 1);
    const playing = { note: noteName(f.note) + " (MIDI " + f.note + ")" };
    if (L === "gate") {
      where += ", pulse " + (h + 1);
      const step = c * 8 + h;
      if (v === true) {
        title = "Gate";
        if (f.skipped) lines.push(`Set to play ${playing.note}, but the stage is skipped (Skip layer), so the playhead jumps over it and it doesn't play.`);
        else lines.push(`Plays ${playing.note} at velocity ${f.velocity} on this pulse.`);
        const next = nextStep(Object.assign({}, sq, { step: step }));
        const nh = next % 8, nc = Math.floor(next / 8);
        if (sq.layers.gate[7 - nh][nc] === "Tie") lines.push("The next pulse is a tie, so this note is held longer: 0.3 instead of a quarter of Gate Len.");
        else lines.push("Its length is a quarter of Gate Len (timing page, SCALE).");
      } else if (v === "Tie") {
        title = "Tie";
        if (f.skipped) lines.push("The stage is skipped (Skip layer), so the playhead never reaches this tie.");
        else lines.push(`Plays ${playing.note} too. Being a tie, it makes the note before it longer: 0.3 instead of a quarter of Gate Len.`);
      } else if (v === "Off") {
        title = "Rest";
        lines.push("A pulse with no note: the playhead still spends a pulse here, and the stage's locks still play.");
      } else {
        title = "Not part of the stage";
        lines.push(`The stage is ${f.length} pulse${f.length === 1 ? "" : "s"} long, so the playhead never reaches this pad. Hold SELECT and tap it to make the stage ${h + 1} pulses long.`);
      }
      if (sq.step === step) lines.push("The playhead is on this pulse (pink).");
    } else {
      const row = layerData().rows[r];
      if (row) where += ", " + row;
      if (L === "pitch") {
        const ph = litHeights(sq.layers.pitch, c), semi = ph.length === 2;
        title = v ? (semi ? "Semitone" : "Note") : "Not the stage's note";
        if (v && semi) lines.push(`With the pad ${ph[0] === h ? "above" : "below"} it lit too, the stage plays the semitone above the ${DEGREES[ph[0]]}.`);
        else if (v) lines.push(`The stage plays the ${DEGREES[h]} of C major.`);
        else lines.push(`Tap to make the stage play ${noteName(MAJOR_SCALE[h] + f.octave * 12)}, the ${DEGREES[h]} in its octave.`);
        if (v) lines.push(`With the stage's octave (${f.octave}) that is ${playing.note}.`);
      } else if (L === "octave") {
        title = v ? "Octave " + h : "Not the stage's octave";
        lines.push(v ? `Every note of the stage is ${h} octave${h === 1 ? "" : "s"} up: ${playing.note}.`
          : `Tap to move the stage to octave ${h}: ${noteName(f.pitch + h * 12)} (MIDI ${f.pitch + h * 12}).`);
      } else if (L === "velocity") {
        const vel = (h + 1) * 16 - 1;
        title = v ? "Velocity " + vel : "Not the stage's velocity";
        lines.push(v ? `The stage's notes play at velocity ${vel} of 127.` : `Tap to play the stage at velocity ${vel} of 127.`);
      } else if (L === "skips") {
        if (h === 0) {
          title = v ? "Skip" : "Not skipped";
          lines.push(v ? "The playhead jumps over this whole stage, and nothing on it plays." : "Tap to make the playhead jump over the whole stage.");
        } else {
          const x = h - 1;
          title = v ? "Chance" : "Not the stage's chance";
          lines.push(v ? `Each note of the stage rolls 1 to 6 and plays on ${x} or less, ${chanceText(x)}.`
            : `Tap to set the stage's chance here, ${chanceText(x)}.`);
          if (!v && !litHeights(sq.layers.skips, c).some((k) => k > 0)) lines.push(`No chance is set on this stage yet, ${chanceText(1)}.`);
        }
      } else if (L === "lock_scale") {
        title = v ? "Lock amount " + pct(h / 7) : "Not the stage's lock amount";
        lines.push(v ? `The stage's parameter locks play at ${pct(h / 7)} of the way from each knob to its lock.`
          : `Tap to play the stage's locks at ${pct(h / 7)}.`);
      }
      if (v === true && Math.floor(sq.step / 8) === c) lines.push("The playhead is on this stage (pink).");
    }
    // what is true of the whole stage
    if (hasLocks(c)) {
      const named = Object.entries(sq.locks[c]).map(([where, val]) => {
        const [slot, index] = where.split(":").map(Number), key = trackState().shownNow[slot];
        const ctl = key && controlAt(key, index);
        if (!ctl) return `slot ${slot + 1}, control ${index + 1}`;
        const text = ctl.t === "range" ? valueText(ctl, val) : ctl.t === "menu" ? itemLabel(ctl, Math.floor(val)) : (ctl.groups[Math.floor(val)] || {}).label;
        return `${devices.devices[key].label} › ${ctl.label || "Mode"} ${text}`;
      });
      lines.push(`Parameter locks on this stage (white): ${named.join(", ")}. They play at ${pct(f.lockScale)} (Lock amount layer).`);
      if (heldStage() !== c) lines.push("Hold the pad to see them on the screen.");
    }
    if (f.skipped && L !== "skips" && !(L === "gate" && (v === true || v === "Tie"))) lines.push("This stage is skipped (Skip layer): the playhead jumps over it.");
    if (!f.skipped && f.chance < 6 && L !== "skips") lines.push(`The Skip layer gives this stage a chance, ${chanceText(f.chance)}.`);
    return { where: where, title: title, lines: lines };
  }

  // MuteMode's rows, top to bottom: what playback does with the layer on, and muted
  const MUTE_EFFECTS = [
    { on: "Each note's pitch comes from the Pitch layer.",
      muted: "Every note keeps the pitch of the last note that played; octave and velocity still follow their layers. (Before any note has played, each step's own pitch is used.)",
      short: "notes hold the last pitch played." },
    { on: "Each note's octave comes from the Octave layer.",
      muted: "Every note keeps the octave of the last note that played; pitch and velocity still follow their layers.",
      short: "notes hold the last octave played." },
    { on: "Each note's velocity comes from the Velocity layer.",
      muted: "Every note keeps the velocity of the last note that played; pitch and octave still follow their layers.",
      short: "notes hold the last velocity played." },
    { on: "The Gate layer decides which pulses play notes.",
      muted: "The track plays no notes at all. The playhead keeps moving, and the stages' parameter locks still play on every step.",
      short: "the track stops playing notes (locks still play)." },
    { on: "Skipped stages are jumped over, and each note plays with its stage's chance.",
      muted: "Nothing is skipped and every note plays: the Skip layer's skips and chances are ignored.",
      short: "nothing is skipped and every note plays." },
    { on: "Each step plays its stage's locks scaled by the Lock amount layer.",
      muted: "Locks keep the scaling of the last step played before the mute, whatever the Lock amount layer says.",
      short: "locks keep the last scaling used." },
    { on: "A spare layer: playback doesn't use it yet.", muted: "A spare layer: muting it changes nothing.", short: "nothing changes (a spare layer)." },
    { on: "A spare layer: playback doesn't use it yet.", muted: "A spare layer: muting it changes nothing.", short: "nothing changes (a spare layer)." },
  ];

  // PresetSelectionMode.slot_label: a Surge slot is named after the preset it came
  // from (Init Saw unless chosen); a mono2k slot after its sound, or "-"
  function slotNames(t) {
    return trackState(t).engine === "mono2k" ? data.screens.slots_mono2k[t] || data.screens.slots_mono2k[0] : data.screens.slots[t];
  }

  // What a preset slot is and does, for the track's engine
  function slotHelp(r, c) {
    const n = c + 1, on = DEMO.slotSel[c] === r, name = slotNames(c)[r], m2k = trackState(c).engine === "mono2k";
    const lines = [];
    const title = on ? `Track ${n}'s current slot` : `Slot ${r + 1}`;
    if (m2k) {
      lines.push(name === "-" ? "Empty: it plays the machine's INIT sound until you save into it." : `Holds the mono2k sound “${name}”.`);
      if (on) lines.push(`Track ${n} is playing it (white). mono2k slots save themselves: every few seconds while the sound changes, and before you switch away.`);
      else lines.push(`Tap to play it on track ${n}; the slot it's on now (slot ${DEMO.slotSel[c] + 1}) is saved first.`);
    } else {
      lines.push(`A Surge XT patch, named after “${name}”, the preset it was loaded from, with any edits saved into it.`);
      if (on) lines.push(`Track ${n} is playing it (white). Your edits are written into it when you close Presets (BROWSE).`);
      else lines.push(`Tap to load it on track ${n}, as it was last saved. The slot you leave isn't saved first: edits made since Presets was last closed are dropped.`);
    }
    lines.push("Hold it for half a second (or hold SELECT and tap it, or Alt/Option-click to keep it held) to open the browser: turn the encoders to choose a sound, then let go to load it into this slot. Let go without browsing and nothing changes.");
    if (on) lines.push(m2k ? "Save to Current (upper button 1) saves the sound into it now; Save to New (button 2) makes it a user preset; Rename (button 3) renames a user preset."
      : "Rename (upper button 3) renames it if it's a Surge user patch.");
    return { title: title, lines: lines };
  }

  function padHelp(r, c) {
    const m = modeData();
    const track = "Track " + (c + 1);
    if (state.mode === "play") {
      const n = padNote(r, c);
      return { where: NOTE_NAMES[n % 12] + (Math.floor(n / 12) - 2) + " (MIDI note " + n + ")", text: m.pads };
    }
    if (state.mode === "seq") {
      const l = layerData();
      const row = l.rows[r] ? ", " + l.rows[r] : "";
      let text = l.pads;
      if (state.layer === "gate" && state.held.select) text = "SELECT is held: tap to make this stage " + (8 - r) + " pulses long.";
      if (state.layer === "gate" && state.held.shift && !state.held.select) text = "SHIFT is held: tap a pulse to tie it to the next one.";
      const step = stepHelp(r, c);
      return Object.assign(step, { text: text === l.pads ? "" : text, foot: l.pads });
    }
    if (state.mode === "clips") {
      const n = c + 1, on = DEMO.clipSel[c] === r, has = DEMO.clipHas[c].includes(r);
      const lines = [];
      let title;
      if (on && has) {
        title = `Track ${n}'s current clip`;
        lines.push(`Track ${n} is playing this clip (its full colour).`, "DELETE (with the track selected) deletes it and empties the pattern.");
      } else if (on) {
        title = `Track ${n}'s current clip, still empty`;
        lines.push(`Track ${n} is on this clip, but nothing is written in it yet. Write a pattern and it's kept as clip ${r + 1}; leave it empty and it isn't saved.`);
      } else if (has) {
        title = "A saved clip";
        lines.push(`Holds a sequence for track ${n} (the darker shade).`,
          `Tap to switch track ${n} to it: the clip it's on now (clip ${DEMO.clipSel[c] + 1}) is saved first, and the new one carries on from the playhead's next step.`);
      } else {
        title = "Empty";
        lines.push(`Tap to start an empty pattern for track ${n} here; clip ${DEMO.clipSel[c] + 1} is saved first. It becomes a clip once you write something in it.`);
      }
      lines.push("A clip is a track's whole sequence: every layer and the stages' parameter locks. The sound (Presets), the mutes and the timing page aren't part of it.");
      return { where: track + ", clip " + (r + 1), title: title, lines: lines, text: "", foot: m.pads };
    }
    if (state.mode === "mutes") {
      // What the muted layer does to playback (SequencerMetro, via the *_track_active flags)
      const muted = !!DEMO.muted[r + "," + c], what = MUTE_EFFECTS[r];
      return { where: track + ", " + m.rows[r] + " layer", title: muted ? "Muted" : "Playing",
        lines: [muted ? what.muted : what.on, (muted ? "Tap to bring it back." : "Tap to mute it: ") + (muted ? "" : what.short)],
        text: "", foot: m.pads };
    }
    const ph = state.presetHold;
    if (state.mode === "presets" && ph && ph.browser && ph.r === r && ph.c === c) {
      const ch = browserChoice(ph), last = ch.levels.length;
      const lines = [`Encoders 1 to ${last} walk the levels shown, left to right; turning one starts the levels after it over.`];
      lines.push(ph.browsed || !ph.viaLong ? `Let go to load “${ch.leaf}” into this slot.` : "Let go without turning an encoder and nothing changes.");
      if (ph.latched) lines.push("(Held by Alt/Option-click: click the pad again to let go.)");
      return { where: track + ", slot " + (r + 1), title: "Browsing", lines: lines, text: "", foot: m.pads };
    }
    if (state.mode === "presets") {
      const text = state.held.select ? "SELECT is held: tap to open the browser on this slot. Turn the encoders to choose a sound, then let go." : "";
      return Object.assign({ where: track + ", slot " + (r + 1), text: text, foot: m.pads }, slotHelp(r, c));
    }
    return { where: "", text: "" };
  }

  // ---- Drawing the panel --------------------------------------------------
  function buildPanel() {
    const s = svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "push", role: "group", "aria-label": "Push 2 controller" });
    svg("rect", { x: 1, y: 1, width: W - 2, height: H - 2, rx: 10, class: "body" }, s);

    // Encoders: tempo and swing, eight above the display, master
    const encs = [["enc_tempo", 36], ["enc_swing", 99]];
    for (let i = 1; i <= 8; i++) encs.push(["enc_" + i, COL_X(i - 1) + PAD_W / 2]);
    encs.push(["enc_master", 745]);
    encs.forEach(([id, cx]) => control(s, id, (g) => {
      g.addEventListener("wheel", (e) => turn(id, e), { passive: false });
      const k = svg("circle", { cx: cx, cy: ENC_Y, r: 13.5, class: "knob" }, g);
      svg("circle", { cx: cx, cy: ENC_Y, r: 10, class: "knob-top" }, g);
      return k;
    }));
    const mark = svg("text", { x: 672, y: ENC_Y + 3, class: "wordmark" }, s);
    mark.textContent = "PUSHPIN";

    // Display: the bezel, and the screen in its own 960x160 pixels
    svg("rect", { x: 138, y: 105, width: 497, height: 88, rx: 2, class: "bezel" }, s);
    const scr = svg("svg", { x: 142, y: 109, width: 489, height: 80, viewBox: "0 0 960 160", preserveAspectRatio: "none", class: "screen-px" }, s);
    svg("rect", { x: 0, y: 0, width: 960, height: 160, fill: "#000" }, scr);
    el.screen = svg("g", {}, scr);

    // The upper row sits above the display, the lower row below it
    for (let i = 0; i < 8; i++) {
      rowButton(s, "upper_row_" + (i + 1), COL_X(i), 61);
      rowButton(s, "lower_row_" + (i + 1), COL_X(i), 213);
    }

    SIDE_BUTTONS.forEach(([id, label, x, y, w, h, icon]) => button(s, id, label, x, y, w, h, icon));
    DIAMONDS.forEach((dm) => diamond(s, dm));

    // Touch strip
    control(s, "touchstrip", (g) => {
      const r = svg("rect", { x: 77, y: PAD_Y, width: 47, height: 7 * ROW + PAD_H, rx: 2, class: "strip" }, g);
      for (let i = 0; i < 4; i++) svg("circle", { cx: 100.5, cy: PAD_Y + 2.6 * ROW + i * 12, r: 2, class: "strip-led" }, g);
      return r;
    });

    // Pads
    const pg = svg("g", { class: "pads" }, s);
    for (let r = 0; r < 8; r++) {
      pads.push([]);
      for (let c = 0; c < 8; c++) {
        const p = svg("rect", { x: COL_X(c), y: PAD_Y + r * ROW, width: PAD_W, height: PAD_H, rx: 3, class: "pad",
          tabindex: r === 0 && c === 0 ? 0 : -1, role: "button", "aria-label": "Pad, row " + (r + 1) + ", column " + (c + 1) }, pg);
        p.dataset.r = r; p.dataset.c = c;
        p.addEventListener("pointerenter", () => hoverPad(r, c));
        p.addEventListener("focus", () => hoverPad(r, c));
        p.addEventListener("click", () => { if (state.mode !== "seq" && state.mode !== "presets") pressPad(r, c); });
        p.addEventListener("pointerdown", (e) => padDown(e, r, c));
        p.addEventListener("keydown", (e) => padKeys(e, r, c));
        pads[r].push(p);
      }
    }

    // Scene buttons, 1/32t at the top
    SCENE.forEach((id, r) => button(s, id, SCENE_LABEL[id], 651, PAD_Y + r * ROW, 42, PAD_H, "chevron"));

    s.addEventListener("pointerleave", () => { state.hover = null; renderInfo(); });
    return s;
  }

  const labels = {};        // id -> the text or icon that lights up
  const leds = {};          // id -> the LED bar of an upper or lower row button

  function control(parent, id, draw) {
    const g = svg("g", { class: "ctl", tabindex: 0, role: "button", "data-id": id, "aria-label": NAMES[id] || id }, parent);
    el[id] = draw(g);
    g.addEventListener("pointerenter", () => { state.hover = id; renderInfo(); });
    g.addEventListener("focus", () => { state.hover = id; renderInfo(); });
    g.addEventListener("click", () => press(id));
    g.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); press(id); }
    });
    return g;
  }

  // Labels sit top-left, as printed on the Push; long ones wrap
  function printLabel(g, label, x, y, w) {
    const words = label.length * 4.3 > w - 6 ? label.split(" ") : [label];
    const t = svg("text", { x: x + 4, y: y + 10, class: "btn-label" }, g);
    words.forEach((word, i) => {
      const span = svg("tspan", { x: x + 4, dy: i ? 8.5 : 0 }, t);
      span.textContent = word;
    });
    return t;
  }

  function button(parent, id, label, x, y, w, h, icon) {
    control(parent, id, (g) => {
      const r = svg("rect", { x: x, y: y, width: w, height: h, rx: 2, class: "btn" }, g);
      if (icon === "record") labels[id] = svg("circle", { cx: x + w / 2, cy: y + h / 2, r: 8, class: "icon-line" }, g);
      else if (icon === "play") labels[id] = svg("path", { d: `M${x + w / 2 - 6} ${y + h / 2 - 9} L${x + w / 2 + 8} ${y + h / 2} L${x + w / 2 - 6} ${y + h / 2 + 9} Z`, class: "icon-line" }, g);
      else {
        const lab = svg("g", { class: "lab" }, g);
        printLabel(lab, label, x, y, w);
        if (icon === "chevron") {
          const cx = x + w - 13, cy = y + h - 13;
          svg("path", { d: `M${cx} ${cy - 5} L${cx + 5} ${cy} L${cx} ${cy + 5}`, class: "chevron" }, lab);
        }
        labels[id] = lab;
      }
      return r;
    });
  }

  function rowButton(parent, id, x, y) {
    control(parent, id, (g) => {
      const r = svg("rect", { x: x, y: y, width: PAD_W + 2, height: 24, rx: 2, class: "btn" }, g);
      leds[id] = svg("rect", { x: x + 5, y: y + 10.5, width: PAD_W - 8, height: 3, rx: 1.5, class: "led" }, g);
      return r;
    });
  }

  // A square key split corner to corner into four triangles, chevrons pointing out
  function diamond(parent, [x, y, size, ids, words]) {
    const cx = x + size / 2, cy = y + size / 2;
    const corners = [[x, y], [x + size, y], [x + size, y + size], [x, y + size]];
    const chev = [[0, -1], [1, 0], [0, 1], [-1, 0]];
    svg("rect", { x: x, y: y, width: size, height: size, rx: 2, class: "btn diamond-base" }, parent);
    ids.forEach((id, i) => control(parent, id, (g) => {
      const a = corners[i], b = corners[(i + 1) % 4];
      const tri = svg("path", { d: `M${a[0]} ${a[1]} L${b[0]} ${b[1]} L${cx} ${cy} Z`, class: "btn tri" }, g);
      const [dx, dy] = chev[i];
      const px = cx + dx * 12, py = cy + dy * 12;
      const tip = [px + dx * 4, py + dy * 4];
      const side = [-dy * 6, dx * 6];
      const path = `M${px - dx * 2 + side[0]} ${py - dy * 2 + side[1]} L${tip[0]} ${tip[1]} L${px - dx * 2 - side[0]} ${py - dy * 2 - side[1]}`;
      const icon = svg("g", {}, g);
      svg("path", { d: path, class: "chevron" }, icon);
      if (words[i]) {
        const t = svg("text", { x: cx + dx * 29, y: cy + dy * 28 + 2.5, class: "btn-label mid" }, icon);
        t.textContent = words[i];
      }
      labels[id] = icon;
      return tri;
    }));
    svg("path", { d: `M${x} ${y} L${x + size} ${y + size} M${x + size} ${y} L${x} ${y + size}`, class: "diamond-x" }, parent);
  }

  // ---- Pressing things ----------------------------------------------------
  function closeOverlay() { state.overlay = null; }

  function press(id) {
    const o = state.overlay;
    // Overlays first: they take the buttons they use
    if (o === "rename") {
      if (id === "upper_row_3" || id === "select") { closeOverlay(); return render(); }
      if (id === "shift") { state.held.shift = !state.held.shift; return render(); }
      return render();
    }
    if (o === "device_menu") {
      const choices = slotChoices(), step = { left: -1, right: 1, up: -8, down: 8 }[id];
      if (step && state.menuIndex + step >= 0 && state.menuIndex + step < choices.length) { state.menuIndex += step; return render(); }
      if (id === "add_device") {
        // MenuMode: load the highlighted device into the slot and close
        const key = choices[state.menuIndex];
        trackState().shownNow[devices.devices[key].slot] = key;
        trackState().devPage[key] = 0;
        closeOverlay(); return render();
      }
    }
    if (o === "engine_menu") {
      const names = Object.keys(devices.engines);
      const step = { left: -1, right: 1 }[id];
      if (step && state.engineIndex + step >= 0 && state.engineIndex + step < names.length) { state.engineIndex += step; return render(); }
      if (id === "add_track") {
        const t = trackState();
        if (t.engine !== names[state.engineIndex]) { t.engine = names[state.engineIndex]; t.instrPage = 0; t.device = 0; }
        closeOverlay(); return render();
      }
    }
    // Where the device page shows, the upper row, page and arrow buttons work it (OSCMode)
    if (!o && state.mode !== "presets") {
      const t = trackState(), tabs = deviceTabs();
      if (id.startsWith("upper_row_")) {
        const i = +id.slice(-1) - 1;
        if (i < tabs.length) {
          if (i === t.device) {
            // the same device again: its previous page if it has one, else its next
            const key = tabs[i], n = devices.devices[key].pages.length, pg = t.devPage[key] || 0;
            t.devPage[key] = pg > 0 ? pg - 1 : pg + 1 < n ? pg + 1 : 0;
          } else { t.device = i; t.devPage[tabs[i]] = 0; }
        }
        return render();
      }
      if (id === "page_left" || id === "page_right") {
        const key = tabs[t.device], n = devices.devices[key].pages.length, pg = t.devPage[key] || 0;
        const next = pg + (id === "page_left" ? -1 : 1);
        if (next >= 0 && next < n) t.devPage[key] = next;
        return render();
      }
      if (id === "left" || id === "right") {
        const page = id === "left" ? 0 : 1;
        if (devices.engines[t.engine].pages[page].length) { t.instrPage = page; t.device = 0; }
        return render();
      }
    }
    if (o === "scale_menu" && id === "scale") { closeOverlay(); return render(); }

    const tapped = /^enc_(\d)$/.exec(id);
    if (tapped && heldStage() !== null && !state.overlay) {
      // MetroSequencerMode.on_encoder_released: a quick touch with no turn drops the lock
      const t = trackState(), key = deviceTabs()[t.device], dev = devices.devices[key];
      delete DEMO.seq.locks[heldStage()][dev.slot + ":" + ((t.devPage[key] || 0) * 8 + (+tapped[1] - 1))];
      return render();
    }
    if (id === "delete" && state.mode === "clips" && !state.overlay) {
      const t = state.track;                      // ClipSelectionMode: delete_state on the current clip
      DEMO.clipHas[t] = DEMO.clipHas[t].filter((x) => x !== DEMO.clipSel[t]);
      return render();
    }
    if (id === "delete" && heldStage() !== null) {
      DEMO.seq.locks[heldStage()] = {};          // clear_all_locks_for_step
      return render();
    }
    switch (id) {
      case "note":
        closeMenusForPads();
        setMode(state.mode === "play" ? "seq" : state.mode === "seq" ? "play" : "seq");
        break;
      case "session": closeMenusForPads(); setMode(state.mode === "clips" ? "seq" : "clips"); break;
      case "mute": closeMenusForPads(); setMode(state.mode === "mutes" ? "seq" : "mutes"); break;
      case "browse": closeMenusForPads(); setMode(state.mode === "presets" ? "seq" : "presets"); break;
      case "setup":
        if (state.overlay !== "settings") { state.overlay = "settings"; state.settingsPage = 0; }
        else if (state.settingsPage < 2) state.settingsPage++;
        else closeOverlay();
        break;
      case "add_device":
        if (state.mode !== "presets") {
          state.overlay = state.overlay === "device_menu" ? null : "device_menu";
          state.menuIndex = Math.max(0, slotChoices().indexOf(deviceTabs()[trackState().device]));
        }
        break;
      case "add_track":
        state.overlay = state.overlay === "engine_menu" ? null : "engine_menu";
        state.engineIndex = Object.keys(devices.engines).indexOf(trackState().engine);
        break;
      case "scale":
        if (state.mode === "seq") state.overlay = state.overlay === "scale_menu" ? null : "scale_menu";
        break;
      case "user": state.display = !state.display; break;
      case "play": togglePlay(); break;
      case "upper_row_3":
        if (state.mode === "presets" && !state.overlay) state.overlay = "rename";
        break;
      case "shift": case "select":
        if ((state.mode === "seq" && state.layer === "gate") || (state.mode === "presets" && id === "select")) {
          state.held[id] = !state.held[id];
        }
        break;
      default:
        if (id.startsWith("lower_row_")) {
          state.track = +id.slice(-1) - 1;
          state.heldStep = null;                // select_instrument clears steps_held
        }
        const layer = Object.keys(data.modes.seq.layers).find((k) => data.modes.seq.layers[k].button === id);
        if (layer && (state.mode === "seq" || state.mode === "mutes")) {
          state.layer = layer;
          state.held.shift = state.held.select = false;
          if (state.mode === "mutes") setMode("seq");
        }
    }
    render();
  }

  // Turning an encoder (mouse wheel) moves its control on the device page
  function turn(id, e) {
    const m = /^enc_(\d)$/.exec(id);
    const ph = state.presetHold;
    if (m && ph && ph.browser && state.mode === "presets") {
      // PresetSelectionMode.on_encoder_rotated: encoder n moves level n; the levels after it start over
      e.preventDefault();
      const level = +m[1] - 1, lv = browserChoice(ph).levels[level];
      if (!lv) return;
      const next = Math.min(lv.names.length - 1, Math.max(0, lv.sel - Math.sign(e.deltaY)));
      if (next !== lv.sel) { ph.path[level] = next; for (let k = level + 1; k < 8; k++) ph.path[k] = 0; }
      ph.browsed = true;
      if (state.hover && typeof state.hover === "object") hoverPad(state.hover.r, state.hover.c);
      return drawScreen();
    }
    const kind = state.overlay ? overlayData().screen : modeData().screen;
    if (m && kind === "timing") {
      // MetroSequencerMode.on_encoder_rotated on the SCALE page: a hundredth of the
      // range a click (a menu moves in fractions of an item, as on the Push)
      const c = data.screens.timing[+m[1] - 1];
      if (!c) return;
      e.preventDefault();
      const lo = c.t === "menu" ? 0 : c.min, hi = c.t === "menu" ? c.items.length - 0.1 : c.max;
      c.value = Math.min(hi, Math.max(lo, Math.round((c.value - Math.sign(e.deltaY) * (hi - lo) / 100) * 1000) / 1000));
      return drawScreen();
    }
    if (!m || kind !== "device") return;
    const c = visibleControls()[+m[1] - 1];
    if (!c || c.t === "label") return;
    e.preventDefault();
    const dir = -Math.sign(e.deltaY);
    const stage = heldStage();
    if (stage !== null) {
      // MetroSequencerMode.on_encoder_rotated with a step held: a lock, from the knob's value
      const t = trackState(), key = deviceTabs()[t.device], dev = devices.devices[key];
      const where = dev.slot + ":" + ((t.devPage[key] || 0) * 8 + (+m[1] - 1));
      const [lo, hi] = c.t === "switch" ? [0, c.groups.length - 1] : c.t === "menu" ? [0, c.items.length] : [c.min, c.max];
      const locks = DEMO.seq.locks[stage], was = where in locks ? locks[where] : c.value;
      const next = was + dir * (hi - lo) / 100;
      locks[where] = lo <= next && next <= hi ? Math.round(next * 1000) / 1000 : was;
      render();
      return;
    }
    if (c.t === "range") {
      const span = c.max - c.min, stepv = span > 2 ? 1 : span / 50;
      c.value = Math.min(c.max, Math.max(c.min, Math.round((c.value + dir * stepv) * 100) / 100));
    } else {
      const n = c.t === "menu" ? c.items.length : c.groups.length;
      c.value = Math.min(n - 1, Math.max(0, c.value + dir));
    }
    drawScreen();
  }

  // BROWSE (and friends) close the device menu, as the app does
  function closeMenusForPads() { if (state.overlay === "device_menu" || state.overlay === "scale_menu" || state.overlay === "rename") closeOverlay(); }

  function setMode(m) {
    state.mode = m;
    state.held.shift = state.held.select = false;
  }

  function pressPad(r, c) {
    if (state.mode === "clips" || state.mode === "presets") {
      state.track = c;
      // the clip left is saved (if it holds anything) and the tapped one loads, empty or not
      if (state.mode === "clips") DEMO.clipSel[c] = r;
      if (state.mode === "presets") DEMO.slotSel[c] = r;
    } else if (state.mode === "mutes") {
      const k = r + "," + c;
      if (DEMO.muted[k]) delete DEMO.muted[k]; else DEMO.muted[k] = 1;
    } else if (state.mode === "seq") {
      seqUp({ r: r, c: c, pending: seqDown(r, c) }, true);
    }
    hoverPad(r, c);
    render();
  }

  // MetroSequencerMode.async_pad_pressed: what a pad does as it goes down. It
  // returns what a quick release would then do (on_pad_released), if anything.
  function seqDown(i, j) {
    const sq = DEMO.seq, L = state.layer, g = sq.layers[L];
    const clearColumn = () => { for (let x = 0; x < 8; x++) g[x][j] = false; };
    if (L === "pitch") { clearColumn(); g[i][j] = true; return null; }
    if (L === "octave" || L === "velocity" || L === "lock_scale") {
      if (g[i][j] === false) { clearColumn(); g[i][j] = true; }
      return null;
    }
    if (L === "skips") {
      if (g[i][j] === false) {
        if (i !== 7) for (let x = 0; x < 7; x++) g[x][j] = false;   // one chance per stage
        g[i][j] = true;
        return null;
      }
      return i === 7 ? "unskip" : null;                          // a tap takes the skip away
    }
    // gate
    const shift = state.held.shift, select = state.held.select;
    if (select) {
      for (let x = 0; x < 8; x++) {                              // the stage is as long as the pad is high
        if (x < i) g[x][j] = false;
        else if (x === i) g[x][j] = true;
        else if (g[x][j] === false) g[x][j] = "Off";
      }
      return null;
    }
    const v = g[i][j];
    if (v === true && shift) { g[i][j] = "Tie"; return null; }
    if (v === true || v === "Tie") return "rest";                // a tap rests it; a hold keeps it
    if (v === "Off") g[i][j] = shift ? "Tie" : true;
    return null;                                                 // false (above the stage): nothing
  }
  function seqUp(h, quick) {
    if (!quick || !h.pending) return;
    const g = DEMO.seq.layers[state.layer];
    if (h.pending === "rest") g[h.r][h.c] = "Off";
    if (h.pending === "unskip") g[h.r][h.c] = false;
  }

  // Holding a sequencer pad: the press happens on the way down, as on the Push;
  // a quick release (under 0.4 s, pad_quick_press_time) can then take the step
  // away again. Alt/Option-click keeps a pad held until it's clicked again.
  const QUICK_PRESS = 400;
  function padDown(e, r, c) {
    if (e.button !== 0) return;
    if (state.mode === "presets") { e.preventDefault(); return presetDown(e, r, c); }
    if (state.mode !== "seq") return;
    e.preventDefault();
    const h = state.heldStep;
    if (h && h.latched) {                         // a latched pad lets go on the next click
      state.heldStep = null;
      if (h.r === r && h.c === c) { render(); return; }
    }
    state.heldStep = { r: r, c: c, t0: performance.now(), latched: e.altKey, pending: seqDown(r, c) };
    hoverPad(r, c);
    render();
  }
  // PresetSelectionMode: a press loads the slot. Holding it PAD_LONG_PRESS_SECONDS
  // (0.5 s), or pressing it with SELECT held, opens the browser; letting go loads
  // the browsed sound into the slot (browser_choice_wanted) and closes it.
  const PAD_LONG_PRESS = 500;
  function presetDown(e, r, c) {
    const h = state.presetHold;
    if (h && h.latched) { presetRelease(); if (h.r === r && h.c === c) return; }
    state.track = c;
    DEMO.slotSel[c] = r;
    const viaSelect = state.held.select;
    // the browser opens on the slot's own sound (set_knob_postions), else at the top
    const path = findInTree(browserTree(c), slotNames(c)[r]) || [0];
    state.presetHold = { r: r, c: c, latched: e.altKey, browser: viaSelect, viaLong: false, browsed: false, path: path };
    if (!viaSelect) {
      const hold = state.presetHold;
      hold.timer = setTimeout(() => {
        if (state.presetHold !== hold) return;
        hold.browser = true; hold.viaLong = true;
        if (state.hover && typeof state.hover === "object") hoverPad(state.hover.r, state.hover.c);
        render();
      }, PAD_LONG_PRESS);
    }
    hoverPad(r, c);
    render();
  }
  function presetRelease() {
    const h = state.presetHold;
    if (!h) return;
    clearTimeout(h.timer);
    state.presetHold = null;
    const leaf = h.browser ? browserChoice(h).leaf : null;
    if (leaf && (h.browsed || !h.viaLong)) slotNames(h.c)[h.r] = leaf;
    if (state.hover && typeof state.hover === "object") hoverPad(state.hover.r, state.hover.c);
    render();
  }

  // The browser's tree for a track's engine: mono2k's from its sounds, Surge's an example
  function browserTree(c) {
    return trackState(c).engine === "mono2k" ? devices.m2k_browser : data.screens.surge_browser;
  }
  // Where a sound's name sits in a browser tree, as positions at each level
  function findInTree(node, name, path = []) {
    if (Array.isArray(node)) { const i = node.indexOf(name); return i < 0 ? null : path.concat(i); }
    const keys = Object.keys(node || {});
    for (let i = 0; i < keys.length; i++) {
      const hit = findInTree(node[keys[i]], name, path.concat(i));
      if (hit) return hit;
    }
    return null;
  }

  // The columns the browser shows for a hold: each level's names and the one chosen, and the sound at the end
  function browserChoice(h) {
    const levels = [];
    let node = browserTree(h.c), leaf = null;
    for (let level = 0; node && level < 8; level++) {
      const names = Array.isArray(node) ? node : Object.keys(node);
      if (!names.length) break;
      const sel = Math.min(h.path[level] || 0, names.length - 1);
      levels.push({ names: names, sel: sel });
      if (Array.isArray(node)) { leaf = names[sel]; break; }
      node = node[names[sel]];
    }
    return { levels: levels, leaf: leaf };
  }

  function padUp() {
    const p = state.presetHold;
    if (p && !p.latched) presetRelease();
    const h = state.heldStep;
    if (!h || h.latched) return;
    state.heldStep = null;
    seqUp(h, performance.now() - h.t0 <= QUICK_PRESS);
    if (state.hover && typeof state.hover === "object") hoverPad(state.hover.r, state.hover.c);
    render();
  }
  window.addEventListener("pointerup", padUp);
  window.addEventListener("pointercancel", padUp);

  function padKeys(e, r, c) {
    const moves = { ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] };
    if (moves[e.key]) {
      e.preventDefault();
      const nr = Math.min(7, Math.max(0, r + moves[e.key][0]));
      const nc = Math.min(7, Math.max(0, c + moves[e.key][1]));
      pads[r][c].setAttribute("tabindex", -1);
      pads[nr][nc].setAttribute("tabindex", 0);
      pads[nr][nc].focus();
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      pressPad(r, c);
    }
  }

  let timer = null;
  function togglePlay() {
    state.playing = !state.playing;
    clearInterval(timer);
    if (state.playing && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
      timer = setInterval(() => { allSeqs().forEach((sq) => { sq.step = nextStep(sq); }); renderPads(); }, 125);
    }
  }

  function hoverPad(r, c) { state.hover = { r: r, c: c }; renderInfo(); }

  // ---- Rendering ----------------------------------------------------------
  function padColors() {
    const g = [];
    for (let r = 0; r < 8; r++) g.push(new Array(8).fill(color("gray_dark")));
    const set = (r, c, col) => { g[r][c] = col; };

    if (state.mode === "play") {
      for (let r = 0; r < 8; r++) for (let c = 0; c < 8; c++) {
        const rel = (padNote(r, c) - ROOT) % 12;
        set(r, c, rel === 0 ? trackColor(state.track) : MAJOR[rel] ? "#e8e8e8" : "#2a2a2a");
      }
    } else if (state.mode === "seq") {
      // MetroSequencerMode.update_pads, step by step
      const sq = DEMO.seq, L = state.layer, g = sq.layers[L];
      const stage = Math.floor(sq.step / 8);
      for (let r = 0; r < 8; r++) for (let c = 0; c < 8; c++) {
        const v = g[r][c];
        let col = color("gray_dark");
        if (v === true) col = hasLocks(c) ? color("white") : color(LAYER_COLOR[L]);
        if (L !== "gate" && c === stage) col = color("pink");     // the playhead's stage
        if (v === "Off") col = color("gray_dark");
        if (v === "Tie") col = color("green");
        if (v === false) col = "#000000";
        set(r, c, col);
      }
      // in the gate layer the playhead is its one pulse
      if (L === "gate") set(7 - (sq.step % 8), stage, color("pink"));
    } else if (state.mode === "clips") {
      for (let c = 0; c < 8; c++) for (let r = 0; r < 8; r++) {
        // ClipSelectionMode.update_pads: the clip each track is on in its colour,
        // the others it has in its darker1 shade, empty pads black
        if (r === DEMO.clipSel[c]) set(r, c, trackColor(c));
        else if (DEMO.clipHas[c].includes(r)) set(r, c, darker1(trackColor(c)));
        else set(r, c, "#000000");
      }
    } else if (state.mode === "presets") {
      for (let c = 0; c < 8; c++) for (let r = 0; r < 8; r++) {
        // PresetSelectionMode.update_pads: every slot in its track's colour, the current one white
        set(r, c, r === DEMO.slotSel[c] ? color("white") : trackColor(c));
      }
    } else if (state.mode === "mutes") {
      const order = ["pitch", "octave", "velocity", "gate", "skips", "lock_scale", "aux", "aux"];
      for (let r = 0; r < 8; r++) for (let c = 0; c < 8; c++) {
        set(r, c, DEMO.muted[r + "," + c] ? "#000000" : color(LAYER_COLOR[order[r]] || "cyan"));
      }
    }
    return g;
  }

  function renderPads() {
    const g = padColors();
    // an unlit pad (LED off): near black, well apart from gray_dark (a rest, an empty slot)
    for (let r = 0; r < 8; r++) for (let c = 0; c < 8; c++) pads[r][c].style.fill = g[r][c] === "#000000" ? "#060607" : g[r][c];
  }

  function buttonLights() {
    const lit = {};
    const W_ = "on", D_ = "dim";
    for (let i = 1; i <= 8; i++) lit["lower_row_" + i] = trackColor(i - 1);
    lit["lower_row_" + (state.track + 1)] = "sel:" + trackColor(state.track);
    const showsDevices = state.mode !== "presets";
    // OSCMode lights an upper button for each device on the page, the shown one brighter
    if (showsDevices && !state.overlay) {
      const t = trackState();
      const stage = heldStage();
      deviceTabs().forEach((key, i) => {
        const slot = devices.devices[key].slot;
        const locked = stage !== null && Object.keys(DEMO.seq.locks[stage]).some((w) => +w.split(":")[0] === slot);
        lit["upper_row_" + (i + 1)] = locked ? "on" : dim(trackColor(state.track), i === t.device ? 1 : 0.55);
      });
    }
    Object.assign(lit, { note: state.mode === "play" || state.mode === "seq" ? W_ : D_, mute: state.mode === "mutes" ? W_ : D_,
      session: state.mode === "clips" ? W_ : D_, browse: state.mode === "presets" ? W_ : D_, setup: state.overlay === "settings" ? W_ : D_,
      add_device: state.overlay === "device_menu" ? W_ : D_, add_track: state.overlay === "engine_menu" ? W_ : D_,
      user: state.display ? W_ : D_, play: state.playing ? color("green") : D_ });
    if (showsDevices) {
      // Page arrows where the device has another page; Left/Right show the other row of devices
      const t = trackState(), key = deviceTabs()[t.device], pg = t.devPage[key] || 0, n = devices.devices[key].pages.length;
      if (pg > 0) lit.page_left = W_;
      if (pg + 1 < n) lit.page_right = W_;
      if (t.instrPage === 1) lit.left = W_;
      if (t.instrPage === 0 && devices.engines[t.engine].pages[1].length) lit.right = W_;
    }
    if (state.mode === "play") Object.assign(lit, { octave_up: W_, octave_down: W_, accent: D_ });
    if (state.mode === "seq" || state.mode === "mutes") {
      Object.values(data.modes.seq.layers).forEach((l) => { lit[l.button] = D_; });
      if (state.mode === "seq") lit[layerData().button] = W_;
      if (state.mode === "seq") lit.scale = state.overlay === "scale_menu" ? W_ : D_;
      if (state.mode === "seq" && state.layer === "gate") { lit.shift = W_; lit.select = W_; }
    }
    if (state.mode === "presets") Object.assign(lit, { select: W_, left: W_, right: W_ });
    if (state.overlay === "rename" || state.overlay === "device_menu") Object.assign(lit, { left: W_, right: W_, up: W_, down: W_ });
    if (state.overlay === "engine_menu") Object.assign(lit, { left: W_, right: W_ });
    return lit;
  }

  function renderButtons() {
    const lit = buttonLights();
    Object.keys(el).forEach((id) => {
      const shape = el[id];
      if (!shape || !shape.classList || !shape.classList.contains("btn")) return;
      const v = lit[id];
      const held = !!state.held[id];
      shape.classList.toggle("held", held);
      const selected = typeof v === "string" && v.startsWith("sel:");
      const col = v === "on" ? "#ffffff" : v === "dim" ? "#8e8e95" : v ? v.replace("sel:", "") : "";
      if (leds[id]) {
        leds[id].style.fill = col || "";
        leds[id].classList.toggle("selected", selected);
      }
      if (labels[id]) labels[id].style.color = col;   // labels and icons draw in currentColor
    });
  }

  // ---- The Push 2 screen ----------------------------------------------------
  // Drawn in the screen's own 960x160 pixels, the way Pushpin draws it
  // (user_interface/display_utils.py show_text, osc_controls.py draw).
  const SW = 960, SH = 160, PART = 120;
  const GRAY_LIGHT = "#b4b4b4";

  function showText(g, part, top, text, o) {
    o = Object.assign({ height: 20, color: "#ffffff", bg: null, pct: 0.8, centerH: false, marginLeft: 4, pad: 0, centerV: true, font: null }, o || {});
    const x1 = PART * part;
    if (o.bg) svg("rect", { x: x1 + o.pad, y: top + o.pad, width: PART - o.pad * 2, height: o.height - o.pad * 2, fill: o.bg }, g);
    let size = o.font || Math.round(o.height * o.pct);
    const lines = String(text).split("\n");
    const marginTop = o.centerV ? Math.floor((o.height - size * lines.length) / 2) : 4;
    lines.forEach((line, i) => {
      const t = svg("text", { x: o.centerH ? x1 + PART / 2 : x1 + o.marginLeft, y: top + size * (i + 1) + marginTop - 2,
        fill: o.color, "font-size": size, "text-anchor": o.centerH ? "middle" : "start", class: "scr" }, g);
      t.textContent = line;
      // as fitted_font_size: a label wider than its column shrinks, down to 9px
      const avail = PART - 6, wide = t.getComputedTextLength ? t.getComputedTextLength() : 0;
      if (wide > avail && size > 9) t.setAttribute("font-size", Math.max(9, Math.floor(size * avail / wide)));
    });
  }

  function fraction(c, v) { const span = c.max - c.min; return span <= 0 ? 0 : Math.min(1, Math.max(0, (v - c.min) / span)); }
  // OSCControl.display_text: Surge's recorded words (interpolated between its
  // points), mono2k's own words for each whole value, an offset from a centre,
  // or else the number as Python prints round(value, 2)
  const AMOUNT = /^(-?\d+(?:\.(\d+))?)((?:\s|%|\p{L}).*)?$/u;
  function parseAmount(text) {
    const m = AMOUNT.exec(text);
    return m ? [parseFloat(m[1]), (m[2] || "").length, m[3] || ""] : null;
  }
  function tableText(table, c, v) {
    const position = fraction(c, v) * (table.length - 1);
    const below = Math.floor(position), above = Math.min(below + 1, table.length - 1), part = position - below;
    if (part < 1e-9 || below === above) return table[below];
    const a = parseAmount(table[below]), b = parseAmount(table[above]);
    if (!a || !b || a[2] !== b[2]) return part < 0.5 ? table[below] : table[above];
    return (a[0] + (b[0] - a[0]) * part).toFixed(Math.max(a[1], b[1])) + a[2];
  }
  // value_labels_by: the words follow another parameter of the same device
  function labelsTable(c) {
    if (c.labels_by) {
      const src = controlByAddress(c.labels_by.address);
      // the source's value as the synth echoes it: a menu's is what its item sends
      const raw = !src ? 0 : src.t === "menu" ? (src.values[Math.floor(src.value)] || 0) : src.value;
      const v = Math.min(127, Math.max(0, Math.floor(raw)));
      const ids = c.labels_by.tables;
      return devices.tables[ids[Math.min((v * c.labels_by.choices) >> 7, ids.length - 1)]];
    }
    return c.labels ? devices.tables[c.labels] : null;
  }
  // A menu item's label: one named after another device's control (label_from)
  // takes that control's name from whatever device the slot holds now
  function itemLabel(c, n) {
    const from = c.from && c.from[String(n)];
    if (from) {
      const key = trackState().shownNow[from[0]];
      // past the device's last control the app names it "-"
      if (key) return devices.devices[key].names[from[1]] || "-";
    }
    return c.items[n] === undefined ? "" : c.items[n];
  }
  function hasValueWords(c) { return !!(c.table || c.labels || c.labels_by); }
  function valueText(c, v) {
    if (c.table) return tableText(devices.tables[c.table], c, v);
    const words = labelsTable(c);
    if (words) return words[Math.min(Math.max(Math.floor(v), 0), words.length - 1)];
    if (c.center !== undefined) {
      const off = Math.round((v - c.center) * 100) / 100;
      return off === 0 ? "0" : (off > 0 ? "+" : "") + off;
    }
    // values arrive as floats, so a whole one prints as Python's "64.0"
    const r = Math.round(v * 100) / 100;
    return Number.isInteger(r) ? r.toFixed(1) : String(r);
  }
  // A control of the device on screen, by its address (any page, any switch group)
  function controlByAddress(address) {
    const t = trackState(), key = deviceTabs()[t.device];
    const walk = (list) => {
      for (const c of list) {
        if (!c) continue;
        if (c.address === address) return c;
        if (c.groups) for (const grp of c.groups) { const hit = walk(grp.controls); if (hit) return hit; }
      }
      return null;
    };
    for (const page of devices.devices[key].pages) { const hit = walk(page); if (hit) return hit; }
    return null;
  }

  // OSCControl.draw: name, value riding along the slider, slider with its pointer
  // A locked control (draw_lock): a gray_dark box, the name in the track's colour
  // and the lock's value in place of the knob's
  const lockBox = (g, part, y, h) => svg("rect", { x: PART * part, y: y, width: 118, height: h, fill: color("gray_dark") }, g);

  function drawControl(g, part, c, color, lock) {
    const top = 25, locked = lock !== undefined, value = locked ? lock : c.value;
    if (locked) lockBox(g, part, 21, 72);
    showText(g, part, top, c.label, { centerH: true, color: locked ? color : "#ffffff" });
    const f = fraction(c, value);
    // words are centred; a number rides along with the pointer
    showText(g, part, top + 20, valueText(c, value), { color: color, centerH: hasValueWords(c), marginLeft: Math.round(f * 80 + 10) });
    const xc = PART * part + 18, yc = top + 20 + 20 + 15 + 5, len = 80;
    svg("line", { x1: xc, y1: yc, x2: xc + len, y2: yc, stroke: GRAY_LIGHT, "stroke-width": 1 }, g);
    const from = c.bipolar ? xc + len / 2 : xc;
    svg("line", { x1: from, y1: yc, x2: xc + len * f, y2: yc, stroke: color, "stroke-width": 3 }, g);
    const tx = xc + len * f;
    svg("path", { d: `M${tx} ${yc - 3} L${tx - 6} ${yc - 15} L${tx + 6} ${yc - 15} Z`, fill: color }, g);
  }

  // OSCControlMenu.draw: its name, then the items before, at and after its value
  function drawMenu(g, part, c, color, lock) {
    const items = c.items ? c.items.map((_, n) => itemLabel(c, n)) : (c.groups || []).map((x) => x.label);
    const locked = lock !== undefined, font = locked ? color : "#ffffff";
    if (locked) lockBox(g, part, 21, 72);
    const i = Math.min(items.length - 1, Math.max(0, Math.floor(locked ? lock : c.value)));
    const tip = c.label ? 25 : 0;
    if (c.label) showText(g, part, 25, c.label, { centerH: true, color: font });
    const top = 30 + tip;
    if (items[i - 1]) showText(g, part, top, items[i - 1], { height: 15, color: font });
    showText(g, part, top + 15, items[i], { height: 25, color: color });
    if (items[i + 1]) showText(g, part, top + 40, items[i + 1], { height: 15, color: font });
  }

  // draw_submenu: the device's other page, small, under the controls.
  // A knob shows its name, its value and two end marks; a menu or a switch
  // just its current item, in the track's colour.
  function drawSubmenu(g, part, c, color, lock) {
    if (!c || c.t === "label") return;
    const locked = lock !== undefined, value = locked ? lock : c.value;
    if (c.t === "menu" || c.t === "switch") {
      if (locked && c.t === "menu") lockBox(g, part, 95, 25);
      const label = c.t === "menu" ? itemLabel(c, Math.floor(value)) : (c.groups[Math.floor(value)] || {}).label;
      showText(g, part, 110, label || "", { height: 15, color: color });
      return;
    }
    if (locked) lockBox(g, part, 110, 30);
    showText(g, part, 110, c.label, { height: 15, centerH: true, color: locked ? color : "#ffffff" });
    const f = fraction(c, value);
    showText(g, part, 125, valueText(c, value), { height: 15, color: color, centerH: hasValueWords(c), marginLeft: Math.round(f * 80 * 0.75 + 10) });
    const xc = PART * part + 7.5 + 3, yc = 110 + 15 + 6;
    svg("line", { x1: xc - 4, y1: yc - 5, x2: xc - 4, y2: yc + 5, stroke: GRAY_LIGHT, "stroke-width": 1 }, g);
    svg("line", { x1: xc + 4 + 80, y1: yc - 5, x2: xc + 4 + 80, y2: yc + 5, stroke: GRAY_LIGHT, "stroke-width": 1 }, g);
  }

  function drawAny(g, part, c, color, lock) {
    if (!c) return;
    if (c.t === "range") drawControl(g, part, c, color, lock);
    else if (c.t === "label") showText(g, part, 30, c.label, { height: 15, color: color });
    else drawMenu(g, part, c, color, lock);
  }

  // InstrumentSelectionMode: the track bar along the bottom
  function drawTrackBar(g) {
    const S = data.screens;
    for (let i = 0; i < 8; i++) {
      const sel = i === state.track, col = trackColor(i);
      const [vol, glob] = S.track_volumes[i];
      showText(g, i, SH - 20, `Trk ${i + 1}  ${vol} / ${glob}`, { color: sel ? "#000" : col, bg: sel ? col : "#000" });
    }
  }

  function drawDevicePage(g) {
    const t = trackState(), col = trackColor(state.track), tabs = deviceTabs();
    tabs.forEach((key, i) => {
      const sel = i === t.device;
      showText(g, i, 0, devices.devices[key].label, { color: sel ? "#000" : col, bg: sel ? col : "#000" });
    });
    const dev = devices.devices[tabs[t.device]];
    const pg = t.devPage[tabs[t.device]] || 0;
    // with a step held, its stage's locks on this device (OSCDevice.draw)
    const stage = heldStage(), locks = stage === null ? {} : DEMO.seq.locks[stage];
    const lockOf = (page, i) => locks[dev.slot + ":" + (page * 8 + i)];
    dev.pages[pg].forEach((c, i) => drawAny(g, i, c, col, lockOf(pg, i)));
    const other = (pg + 1) % dev.pages.length;
    if (dev.pages.length > 1) dev.pages[other].forEach((c, i) => drawSubmenu(g, i, c, col, lockOf(other, i)));
  }

  function drawScreen() {
    const g = el.screen;
    while (g.firstChild) g.removeChild(g.firstChild);
    if (!state.display) return;
    const S = data.screens, col = trackColor(state.track);
    const o = overlayData();
    const kind = o ? o.screen : modeData().screen;

    if (kind === "settings") {
      const page = state.settingsPage, d = o.display;
      for (let i = 0; i < 8; i++) {
        const x = i * PART + 3;
        if (d.labels[i]) { const t = svg("text", { x: x, y: 20, fill: "#fff", "font-size": 13, class: "scr" }, g); t.textContent = d.labels[i].toUpperCase(); }
        const v = S.settings_values[page][i];
        if (v) { const t = svg("text", { x: x, y: 45, fill: "#fff", "font-size": 20, class: "scr" }, g); t.textContent = v; }
      }
      return;
    }
    if (kind === "engine") {
      Object.values(devices.engines).forEach((e, i) => showText(g, i, 20, e.label, { height: 25, color: "#000", bg: i === state.engineIndex ? color("yellow") : GRAY_LIGHT, pct: 0.7, centerH: true, pad: 1 }));
      showText(g, 0, 60, `Track ${state.track + 1}: ${devices.engines[trackState().engine].label}`, { height: 25 });
      showText(g, 0, 100, "< > choose, ADD TRACK: select", { color: GRAY_LIGHT });
      return;
    }
    if (kind === "rename") {
      const t = svg("text", { x: 12, y: 22, fill: GRAY_LIGHT, "font-size": 14, class: "scr" }, g); t.textContent = S.rename.title;
      [...S.rename.name.padEnd(10, " ")].forEach((ch, i) => {
        const x = 12 + i * 32, cur = i === S.rename.name.length;
        svg("rect", { x: x, y: 40, width: 30, height: 50, fill: cur ? "#fff" : "#1e1e1e" }, g);
        const c = svg("text", { x: x + 15, y: 78, fill: cur ? "#000" : "#fff", "font-size": 34, "text-anchor": "middle", class: "scr mono" }, g);
        c.textContent = ch;
      });
      const h = svg("text", { x: 12, y: 145, fill: GRAY_LIGHT, "font-size": 13, class: "scr" }, g);
      h.textContent = "hold SHIFT keyboard   < > move   Up/Down letter   DELETE remove   SELECT save   red button cancel";
      return;
    }
    if (kind === "presets") {
      const ph = state.presetHold;
      if (ph && ph.browser) {
        // nested_draw: one column per level, two either side of the choice, the choice in yellow
        browserChoice(ph).levels.forEach(({ names, sel }, level) => names.forEach((name, idx) => {
          if (Math.abs(idx - sel) > 2) return;
          showText(g, level, 20 * (idx - sel) + 75, name, { color: idx === sel ? "#000" : "#fff", bg: idx === sel ? color("yellow") : color("green"), pct: 1, centerH: true, pad: 1 });
        }));
        [[0, "Save to Current"], [1, "Save to New"], [2, "Rename"], [6, "Set All to Current"], [7, "Save All to New"]]
          .forEach(([i, t]) => showText(g, i, 15, t, { height: 15 }));
      } else {
        S.slots.forEach((_, t) => slotNames(t).forEach((name, i) => {
          showText(g, t, 15 + 15 * i, name, { height: 15, color: i === DEMO.slotSel[t] ? "#fff" : trackColor(t) });
        }));
      }
      drawTrackBar(g);
      return;
    }
    if (kind === "timing") {
      svg("rect", { x: 0, y: 0, width: SW, height: 135, fill: "#000" }, g);
      S.timing.forEach((c, i) => drawAny(g, i, c, col));
      drawTrackBar(g);
      return;
    }
    // the device page, under the menus that draw over it
    drawDevicePage(g);
    drawTrackBar(g);
    if (kind === "device_menu") {
      // MenuMode.update_display: rows of eight at 20, 45, 70 and 95, a fifth at 110
      const ROWS = [20, 45, 70, 95, 110];
      slotChoices().forEach((key, i) => {
        if (i >= 40) return;
        showText(g, i % 8, ROWS[Math.floor(i / 8)], devices.devices[key].label,
          { height: 25, color: "#000", bg: i === state.menuIndex ? color("yellow") : GRAY_LIGHT, centerH: true, pad: 1 });
      });
    }
  }

  function renderModeBar() {
    const bar = document.getElementById("manual-modes");
    bar.querySelectorAll("button").forEach((b) => {
      const v = b.dataset.go;
      const on = v === state.mode || (v.startsWith("overlay:") && v.slice(8) === state.overlay);
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });
    const layers = document.getElementById("manual-layers");
    layers.hidden = state.mode !== "seq";
    layers.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.layer === state.layer ? "true" : "false"));
  }

  function renderInfo() {
    const m = modeData();
    const o = overlayData();
    let where = m.name;
    if (state.mode === "seq") where += " · " + layerData().name + " layer";
    if (heldStage() !== null) where += " · holding stage " + (heldStage() + 1);
    if (o) where += " · " + o.name;
    document.getElementById("info-mode").textContent = where;
    document.getElementById("info-summary").textContent = o ? o.summary : m.summary;

    const name = document.getElementById("info-control");
    const text = document.getElementById("info-text");
    const h = state.hover;
    if (h === null) {
      name.textContent = "Point at a control";
      text.textContent = "Hover over or tab to any button, pad or encoder to see what it does in this mode. Click to press it.";
    } else if (typeof h === "object") {
      const p = padHelp(h.r, h.c);
      name.textContent = "Pad: " + p.where;
      text.textContent = p.text;
      if (p.title) renderStep(text, p);
    } else {
      name.textContent = NAMES[h] || h;
      const t = helpFor(h);
      text.textContent = t || "Not used by Pushpin in this mode.";
      text.classList.toggle("unused", !t);
    }
    if (typeof h !== "string") text.classList.remove("unused");
  }

  // A sequencer step: what it is, what's true of its stage, then how the layer works
  function renderStep(box, p) {
    const mk = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt) e.textContent = txt; return e; };
    box.textContent = "";
    if (p.text) box.appendChild(mk("p", "step-held", p.text));
    box.appendChild(mk("p", "step-title", p.title));
    const ul = mk("ul", "step-lines");
    p.lines.forEach((line) => ul.appendChild(mk("li", "", line)));
    box.appendChild(ul);
    box.appendChild(mk("p", "step-foot", p.foot));
  }

  function render() {
    renderPads();
    renderButtons();
    drawScreen();
    renderModeBar();
    renderInfo();
  }

  // ---- Mode bar -----------------------------------------------------------
  function buildModeBar() {
    const bar = document.getElementById("manual-modes");
    const items = [["play", "Play", "note"], ["seq", "Sequencer", "note"], ["clips", "Clips", "session"], ["mutes", "Mutes", "mute"],
      ["presets", "Presets", "browse"], ["overlay:settings", "Settings", "setup"], ["overlay:device_menu", "Device menu", "add_device"],
      ["overlay:engine_menu", "Engine menu", "add_track"]];
    items.forEach(([go, label]) => {
      const b = document.createElement("button");
      b.type = "button"; b.dataset.go = go; b.textContent = label;
      b.addEventListener("click", () => {
        if (go.startsWith("overlay:")) {
          const ov = go.slice(8);
          if (ov === "device_menu" && state.mode === "presets") setMode("seq");
          state.overlay = state.overlay === ov ? null : ov;
          state.settingsPage = 0;
        } else { closeOverlay(); setMode(go); }
        render();
      });
      bar.appendChild(b);
    });
    const layers = document.getElementById("manual-layers");
    Object.entries(data.modes.seq.layers).forEach(([k, l]) => {
      const b = document.createElement("button");
      b.type = "button"; b.dataset.layer = k; b.textContent = l.name;
      b.addEventListener("click", () => { state.layer = k; state.held.shift = state.held.select = false; if (state.overlay === "scale_menu") closeOverlay(); render(); });
      layers.appendChild(b);
    });
  }

  // ---- Start --------------------------------------------------------------
  const load = (url) => fetch(url, { cache: "no-cache" }).then((r) => r.json());
  Promise.all([load(root.dataset.src), load(root.dataset.devices)])
    .then(([d, dv]) => {
      data = d;
      devices = dv;
      document.getElementById("manual-panel").appendChild(buildPanel());
      buildModeBar();
      render();
      root.classList.add("ready");
    })
    .catch((e) => {
      document.getElementById("info-text").textContent = "The manual couldn't load its data (" + e.message + "). If you opened this page as a file, serve the docs folder instead: python -m http.server -d docs";
    });
})();
