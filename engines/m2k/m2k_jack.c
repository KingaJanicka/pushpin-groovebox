/* SPDX-License-Identifier: GPL-3.0-only */
/*
 * m2k-jack: the MONO2K synth core (https://github.com/InigoHernandez/mono2k) as an
 * eight-track JACK synth for pushpin. One process serves every pushpin track:
 * pushpin track n plays MONO2K track n.
 *
 * This file is GPL-3.0-only because it compiles the GPL-3.0-only MONO2K core
 * into itself. It is a separate program that pushpin talks to over MIDI only, so
 * pushpin (MIT) never links against it.
 *
 * Ports (client NAME, default "M2K"):
 *   trackN_midi      MIDI in for track N (1-8); the channel is ignored
 *   trackN_L/_R      track N's own sound: its machine, chain (AMP, FILT, FX, DSTR) and its delay
 *   fx_L / fx_R      the shared bus: the reverb the tracks send to (VERB), then tape, crunch and
 *                    drive on that return. The tracks themselves don't go through the bus.
 * A track's out is its share of MONO2K's own mix: the outs and the return add up to what the stock
 * core plays, as long as the bus's tape, crunch and drive are off (they work on the whole mix there).
 *
 * MIDI, per track:
 *   Notes        note on / note off (velocity is ignored, as on the Monomachine)
 *   CC 3         mute (0 = heard)
 *   CC 7         level
 *   CC 48-55     SYN A-H (the machine's own page)
 *   CC 56-63     AMP: ATK HOLD DEC REL DIST VOL PAN PORT
 *   CC 72-79     FILT: BASE WDTH HPQ LPQ FATK FDEC BOF WOF
 *   CC 80-87     FX: EQF EQG SRR DTIM DSND DFB DBAS DWID
 *   CC 88/104/112 + 0..7  LFO 1/2/3: TRCK DEST WAVE TRIG MULT SPD PHAS DPTH
 *   pushpin's own additions:
 *   CC 9         track on (64-127) / off (0-63): an off track ignores notes and falls silent, so a
 *                pushpin track playing Surge can stay connected
 *   CC 14        machine (its number from --list-machines); loads the machine's INIT sound
 *   CC 16-20     DSTR: BITS FOLD XOR, reverb send (VERB), track pitch (PTCH)
 *   CC 120, 123  all sound off / all notes off
 *   NRPN 0:<cc>  (CC 99 = 0, CC 98 = the parameter's CC number, then CC 6 = value, CC 38 = fine): the same
 *                parameter at 14 bits. The core keeps 1/256 of a step, so 7 of those bits reach the sound.
 *   LFO TRCK     (CC 88/104/112, or NRPN): 0 = the track's own, 1-8 = track 1-8 (pushpin's encoding;
 *                MONO2K's own reaches tracks 7-8 only past 127). The arp's MODE is always OFF: pushpin
 *                sequences, and MONO2K's arp would run on its own clock.
 *   NRPN 1:<p>   (CC 99 = 1, CC 98 = MONO2K's parameter number p, 0-70): any track parameter, the ones no CC
 *                reaches too (the MOD effect, the wave bank, the arp, gate). pushpin saves and restores whole
 *                sounds with it.
 *   Clock, start, stop and other system messages are dropped: pushpin sequences,
 *   MONO2K's own sequencer stays stopped.
 *
 * The core runs at 44.1 kHz; the outputs are resampled (linear) to the JACK rate.
 *
 * Parameters glide to a new value over --glide-ms (one pole, default 20 ms), at the core's 1/256 of a step
 * (a patch adds trk_t.fine to the core's P8()), so a knob turned through MONO2K's 1/8-octave filter steps
 * sweeps instead of stepping. A change that lands within --snap-ms (default 10 ms) of a note-on on its
 * track, as pushpin's p-locks do, is set at once. Choices (waves, modes, LFO destinations) always snap.
 *
 * Usage:
 *   m2k-jack [--name NAME] [--machine N] [--midi-connect TRACK=SUBSTR ...] [--enable LIST]
 *            [--no-audio-connect] [--glide-ms MS] [--snap-ms MS]
 *   m2k-jack --render OUT.wav [--rate HZ] [--seconds S] [--machine N] [--script FILE]
 *            [--stems PREFIX] [--stock] [--trace-param P]
 *   m2k-jack --list-machines
 *   m2k-jack --describe          every machine's parameters and INIT sound as JSON
 *                                (engines/m2k/gen_definitions.py builds pushpin's pages from it)
 *
 * --enable takes track numbers ("1,3,8") or "none"; without it every track is on.
 * --render plays a short phrase (or the --script: lines "seconds status d1 d2", decimal; the
 * channel picks the track) through the same MIDI handling and resampler, and writes the tracks and
 * the return summed as a 16-bit WAV; --stems also writes PREFIX_t1.wav ... PREFIX_t8.wav and
 * PREFIX_fx.wav. --stock renders with the core's own m2k_render instead (its mix), to compare.
 * It needs no JACK, so it is what CI and macOS use.
 */
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <math.h>

#include "m2k_core.c"

#ifdef M2K_WITH_JACK
#include <jack/jack.h>
#include <jack/midiport.h>
#endif

_Static_assert(M2K_TRACKS == 8, "m2k-jack is built with -DM2K_TRACKS=8: a track for each of pushpin's");

#define NT M2K_TRACKS
#define NCH (2 * NT + 2)                 /* the tracks' pairs, then the return's */
#define CC_MACHINE 14
#define CC_ENABLE 9

/* every CC that sets a track parameter: the Monomachine's map, then pushpin's additions */
typedef struct { uint8_t cc, param; const char *page; } pp_ccmap_t;
static const pp_ccmap_t PP_CC[] = {
#define PP_ROW(cc0, p0, pg) {cc0, p0, pg}, {cc0 + 1, p0 + 1, pg}, {cc0 + 2, p0 + 2, pg}, {cc0 + 3, p0 + 3, pg}, \
                            {cc0 + 4, p0 + 4, pg}, {cc0 + 5, p0 + 5, pg}, {cc0 + 6, p0 + 6, pg}, {cc0 + 7, p0 + 7, pg}
    PP_ROW(48, P_SYN, "SYN"), PP_ROW(56, P_ATK, "AMP"), PP_ROW(72, P_BASE, "FILT"), PP_ROW(80, P_EQF, "FX"),
    PP_ROW(88, P_LFO, "LFO1"), PP_ROW(104, P_LFO + 8, "LFO2"), PP_ROW(112, P_LFO + 16, "LFO3"),
#undef PP_ROW
    {16, P_BITS, "DSTR"}, {17, P_FOLD, "DSTR"}, {18, P_XOR, "DSTR"}, {19, P_SPU, "DSTR"}, {20, P_PTCH, "DSTR"},
    {7, P_LEVL, "DSTR"},
};
#define PP_NCC ((int)(sizeof PP_CC / sizeof PP_CC[0]))

static int pp_param_of_cc(int cc)
{
    for (int i = 0; i < PP_NCC; i++)
        if (PP_CC[i].cc == cc) return PP_CC[i].param;
    return -1;
}

/* ------------------------------------------------------- parameters, smoothed */

/* each parameter of each track as 0..127*256 (the core's P8 scale): where it is going and where it is heard.
 * The kit keeps the whole part of the target (a note-on copies the kit into eff), trk_t.fine carries the rest
 * and the glide */
static int32_t pp_target[NT][P_COUNT], pp_cur[NT][P_COUNT];
static uint8_t pp_moving[NT][P_COUNT];
static uint32_t pp_set_at[NT][P_COUNT], pp_note_at[NT];
static uint8_t pp_have_note[NT];
static uint8_t pp_enabled[NT];
static int32_t pp_glide_k = 0;          /* per 16-sample block, Q16; 0: no glide */
static uint32_t pp_snap = M2K_SR / 100;

static void pp_set_glide(double ms)
{
    if (ms <= 0) { pp_glide_k = 0; return; }
    const double k = 1.0 - exp(-(double)M2K_SUB / (ms * 0.001 * M2K_SR));
    pp_glide_k = (int32_t)(k * 65536.0 + 0.5);
    if (pp_glide_k < 1) pp_glide_k = 1;
}

static void pp_params_reset(int t)
{
    const uint8_t *kit = PAT(cur_pat)->kit[t];
    for (int p = 0; p < P_COUNT; p++) {
        pp_target[t][p] = pp_cur[t][p] = kit[p] * 256;
        pp_moving[t][p] = 0;
        trk[t].fine[p] = 0;
    }
}

/* a choice (a wave, a mode, a destination): never through the values between */
static int pp_discrete(int t, int param)
{
    const int kind = pinfo(t, param)->kind;
    return kind_choices(kind) != 0 || kind == K_DEST || kind == K_TRK || kind == K_WBNK;
}

static void pp_apply(int t, int param)
{
    trk[t].fine[param] = pp_cur[t][param] - trk[t].eff[param] * 256;
}

static void pp_snap_param(int t, int param)
{
    pp_cur[t][param] = pp_target[t][param];
    pp_moving[t][param] = 0;
    pp_apply(t, param);
}

static int pp_is_trck(int param)
{
    return param == P_LFO + L_TRCK || param == P_LFO + 8 + L_TRCK || param == P_LFO + 16 + L_TRCK;
}

/* an LFO's TRCK as pushpin sends it (0: track t's own, 1-8: track 1-8) in MONO2K's encoding */
static uint8_t pp_trck_value(int t, int sel)
{
    int track = sel <= 0 ? t : sel - 1;
    if (track >= NT) track = NT - 1;
    return track < M2K_TRACKS6 ? trck_enc(track) : (uint8_t)(TRCK_PAST + track - M2K_TRACKS6);
}

/* a parameter as pushpin knows it: TRCK the track's own, the arp off (the --describe export) */
static int pp_export(int param, int v)
{
    return pp_is_trck(param) || param == P_AMOD ? 0 : v;
}

static void pp_set_param(int t, int param, int32_t q8)
{
    if (pp_is_trck(param)) {               /* (its own encoding; not glided) */
        const uint8_t v = pp_trck_value(t, q8 >> 8);
        PAT(cur_pat)->kit[t][param] = v;
        trk[t].eff[param] = v;
        pp_target[t][param] = pp_cur[t][param] = v * 256;
        pp_moving[t][param] = 0;
        trk[t].fine[param] = 0;
        return;
    }
    if (param == P_AMOD) q8 = 0;           /* the arp stays off */
    const int32_t top = (param == P_LFO + L_DEST || param == P_LFO + 8 + L_DEST || param == P_LFO + 16 + L_DEST)
                            ? P_COUNT * 256 : 127 * 256;
    q8 = CLAMP(q8, 0, top);
    if (pp_discrete(t, param)) q8 &= ~255;
    const uint8_t whole = (uint8_t)(q8 >> 8);
    PAT(cur_pat)->kit[t][param] = whole;
    trk[t].eff[param] = whole;
    pp_target[t][param] = q8;
    pp_set_at[t][param] = m2k_samples();
    if (!pp_glide_k || pp_discrete(t, param) || (pp_have_note[t] && m2k_samples() - pp_note_at[t] <= pp_snap))
        pp_snap_param(t, param);
    else {
        pp_moving[t][param] = 1;
        pp_apply(t, param);             /* (eff moved under it: heard where it was) */
    }
}

/* a note-on: what was set on its track just before it (a p-lock) is heard on it, not glided into */
static void pp_note_on(int t)
{
    const uint32_t now = m2k_samples();
    pp_note_at[t] = now;
    pp_have_note[t] = 1;
    for (int p = 0; p < P_COUNT; p++)
        if (pp_moving[t][p] && now - pp_set_at[t][p] <= pp_snap) pp_snap_param(t, p);
}

/* every block, before the core renders it (a note-on copies the kit into eff, so fine is set again too) */
static void pp_glide_block(void)
{
    for (int t = 0; t < NT; t++)
        for (int p = 0; p < P_COUNT; p++) {
            if (!pp_moving[t][p]) { pp_apply(t, p); continue; }
            const int32_t d = pp_target[t][p] - pp_cur[t][p];
            int32_t step = (int32_t)(((int64_t)d * pp_glide_k) >> 16);
            if (step == 0) step = d > 0 ? 1 : -1;
            if (d > -2 && d < 2) pp_snap_param(t, p);
            else { pp_cur[t][p] += step; pp_apply(t, p); }
        }
}

/* machine m on track t with its whole INIT sound: the same sound whatever was there before, so pushpin,
 * which hears nothing back, knows every parameter's value after a machine change */
static void pp_set_machine(int t, int m)
{
    if (m < 0 || m >= M_COUNT) return;
    m2k_pattern_t *p = PAT(cur_pat);
    kit_init(&pat_tmp, t, m);
    m_cpy(p->kit[t], pat_tmp.kit[t], P_COUNT);
    p->machine[t] = (uint8_t)m;
    p->kit[t][P_AMOD] = 0;                 /* the arp stays off */
    m_cpy(trk[t].eff, p->kit[t], P_COUNT);
    if (t == ui.trk) track_home(t, mach_home(m));
    pp_params_reset(t);
}

static void pp_engine_init(int machine)
{
    m2k_init(0x50555348u);
    /* a blank pattern in place of the factory demo: the default kit, no trigs, no locks */
    m2k_pattern_t *p = PAT(cur_pat);
    pat_init(p, "PUSHPIN");
    lockmap_build();
    for (int t = 0; t < NT; t++) m_cpy(trk[t].eff, p->kit[t], P_COUNT);
    seq_tempo();
    for (int t = 0; t < NT; t++) pp_set_machine(t, machine < 0 ? 0 : machine);
}

/* ------------------------------------------------------------------ describe */

static void pp_json_str(const char *s)
{
    putchar('"');
    for (; *s; s++) {
        if (*s == '"' || *s == '\\') putchar('\\');
        putchar(*s);
    }
    putchar('"');
}

static void pp_json_values(const pi_t *pi);

static void pp_json_param(const pi_t *pi)
{
    printf("{\"label\": ");
    pp_json_str(pi->s4);
    printf(", \"name\": ");
    pp_json_str(pi->name);
    printf(", \"max\": %d, \"bipolar\": %s, \"choices\": %d", kind_max(pi->kind),
           pi->kind == K_BI || pi->kind == K_PAN || pi->kind == K_SEMI ? "true" : "false", kind_choices(pi->kind));
    pp_json_values(pi);
    putchar('}');
}

/* one table of what the screen shows for each value 0-127: "text" and "unit" as fmt() writes them */
static void pp_json_text_table(const pi_t *pi)
{
    char out[24];
    const char *unit;
    printf("{\"text\": [");
    for (int v = 0; v < 128; v++) {
        fmt(pi, 0, v, out, &unit);
        if (v) putchar(',');
        pp_json_str(out);
    }
    printf("], \"unit\": [");
    for (int v = 0; v < 128; v++) {
        fmt(pi, 0, v, out, &unit);
        if (v) putchar(',');
        pp_json_str(unit);
    }
    printf("]}");
}

/* the screen's names for a parameter's values: its choice for each value (where it's a choice), and
 * the text; WAVE's and an LFO's SPD hang on another parameter (the bank, its MULT): a table for each */
static void pp_json_values(const pi_t *pi)
{
    const int k = pi->kind;
    /* these pushpin shows its own way (TRCK, DEST), or that hang on the tempo (HOLD) */
    if (k == K_TRK || k == K_DEST || k == K_AHLD || k == K_SSEL) return;
    uint8_t *kit = PAT(cur_pat)->kit[0];
    printf(", \"kind\": %d", k);
    if (kind_choices(k)) {
        printf(", \"choice\": [");
        for (int v = 0; v < 128; v++) printf("%s%d", v ? "," : "", choice_of(k, v));
        putchar(']');
    }
    int by = -1, n = 0, step = 0;
    if (k == K_WAVE) { by = P_WBNK; n = 2; step = 64; }
    else if (k == K_LSPD) { by = P_LFO + 8 * ((int)(pi - PI_LFO) >> 3) + L_MULT; n = kind_choices(K_MULT); step = 128 / n; }
    if (by < 0) {
        printf(", \"values\": ");
        pp_json_text_table(pi);
        return;
    }
    const uint8_t keep = kit[by];
    printf(", \"values_by\": {\"param\": %d, \"tables\": [", by);
    for (int c = 0; c < n; c++) {
        kit[by] = (uint8_t)(c * step + step / 2);         /* the middle of choice c */
        if (c) putchar(',');
        pp_json_text_table(pi);
    }
    printf("]}");
    kit[by] = keep;
}

/* the data pushpin's device pages are generated from: no audio, nothing but the core's own tables */
static void pp_describe(void)
{
    printf("{\n  \"machine_cc\": %d,\n  \"params\": [\n", CC_MACHINE);
    int first = 1;
    for (int i = 0; i < PP_NCC; i++) {
        if (PP_CC[i].param < 8) continue;                  /* SYN: the machines' own, below */
        printf("%s    {\"cc\": %d, \"id\": %d, \"page\": \"%s\", \"param\": ", first ? "" : ",\n", PP_CC[i].cc,
               PP_CC[i].param, PP_CC[i].page);
        pp_json_param(pinfo(0, PP_CC[i].param));
        putchar('}');
        first = 0;
    }
    printf("\n  ],\n  \"machines\": [\n");
    for (int m = 0; m < M_COUNT; m++) {
        kit_init(&pat_tmp, 0, m);
        printf("    {\"index\": %d, \"name\": ", m);
        pp_json_str(MI[m].name);
        printf(", \"syn\": [");
        for (int k = 0; k < 8; k++) {
            if (k) printf(", ");
            printf("{\"cc\": %d, \"id\": %d, \"param\": ", 48 + k, P_SYN + k);
            pp_json_param(&MI[m].syn[k]);
            putchar('}');
        }
        printf("],\n     \"init\": {");
        for (int i = 0; i < PP_NCC; i++)
            printf("%s\"%d\": %d", i ? ", " : "", PP_CC[i].cc, pp_export(PP_CC[i].param, pat_tmp.kit[0][PP_CC[i].param]));
        printf("},\n     \"kit\": [");                /* every parameter of its INIT sound, by parameter number */
        for (int p = 0; p < P_COUNT; p++) printf("%s%d", p ? ", " : "", pp_export(p, pat_tmp.kit[0][p]));
        printf("]}%s\n", m + 1 < M_COUNT ? "," : "");
    }
    printf("  ],\n  \"param_count\": %d,\n  \"params_all\": [\n", P_COUNT);
    for (int p = 0; p < P_COUNT; p++) {                  /* (SYN A-H: the first machine's labels) */
        const pi_t *pi = pinfo(0, p);
        printf("    {\"param\": %d, \"label\": ", p);
        pp_json_str(pi->s4);
        printf(", \"name\": ");
        pp_json_str(pi->name);
        if (p >= 8) pp_json_values(pi);                  /* (the machines' own are with them) */
        printf("}%s\n", p + 1 < P_COUNT ? "," : "");
    }
    /* MONO2K's factory sound library (m2k_lib.c): each sound its machine and every parameter */
    printf("  ],\n  \"categories\": [");
    for (int c = 1; c < CAT_COUNT; c++) { if (c > 1) printf(", "); pp_json_str(CAT_N[c]); }
    printf("],\n  \"library\": [\n");
    for (int i = 0; i < LIB_N; i++) {
        m2k_sound_t d;
        char name[9];
        lib_sound(i, &d);
        m_cpy(name, d.name, 8);
        name[8] = 0;
        printf("    {\"index\": %d, \"name\": ", i);
        pp_json_str(name);
        printf(", \"category\": ");
        pp_json_str(LIB[i].cat > 0 && LIB[i].cat < CAT_COUNT ? CAT_N[LIB[i].cat] : "");
        printf(", \"machine\": %d, \"root\": %d, \"what\": ", d.machine, LIB[i].root);
        pp_json_str(LIB[i].what);
        printf(", \"kit\": [");
        for (int p = 0; p < P_COUNT; p++) printf("%s%d", p ? ", " : "", pp_export(p, d.kit[p]));
        printf("]}%s\n", i + 1 < LIB_N ? "," : "");
    }
    printf("  ]\n}\n");
}

/* ----------------------------------------------------------------------- MIDI */

static void pp_all_notes_off(int t)
{
    for (int i = 0; i < 8 && sq.nkeys[t]; i++) live_off_t(t, sq.keys[t][0]);
    voice_off(t);
}

/* NRPN, per track: the parameter chosen (CC 99, CC 98: 0 and a CC number), its value's coarse part (CC 6) */
static int pp_nrpn_param[NT], pp_nrpn_msb[NT], pp_nrpn_hi[NT];

static void pp_nrpn_cc(int t, int cc, int v)
{
    switch (cc) {
    case 99: pp_nrpn_hi[t] = v; pp_nrpn_param[t] = -1; break;
    case 98:
        pp_nrpn_param[t] = pp_nrpn_hi[t] == 0 ? pp_param_of_cc(v) : pp_nrpn_hi[t] == 1 && v < P_COUNT ? v : -1;
        break;
    case 101: case 100: pp_nrpn_param[t] = -1; break;        /* an RPN: not ours */
    case 6:
        pp_nrpn_msb[t] = v;
        if (pp_nrpn_param[t] >= 0) pp_set_param(t, pp_nrpn_param[t], v * 256);
        break;
    case 38:
        if (pp_nrpn_param[t] >= 0) pp_set_param(t, pp_nrpn_param[t], pp_nrpn_msb[t] * 256 + v * 2);
        break;
    }
}

static void pp_set_enabled(int t, int on)
{
    if (pp_enabled[t] && !on) pp_all_notes_off(t);
    pp_enabled[t] = (uint8_t)(on != 0);
}

/* one MIDI message for track t; called from the audio thread only */
static void pp_handle_midi(int t, const uint8_t *m, size_t n)
{
    if (n == 0 || t < 0 || t >= NT) return;
    const int status = m[0];
    if (status < 0x80 || status >= 0xF0) return;      /* running status / system: not ours */
    const int cmd = status & 0xF0;
    const int d1 = n > 1 ? m[1] & 127 : 0, d2 = n > 2 ? m[2] & 127 : 0;
    if (cmd == 0xB0) {
        if (d1 == CC_ENABLE) { pp_set_enabled(t, d2 >= 64); return; }
        if (d1 == CC_MACHINE) { pp_set_machine(t, d2); return; }
        if (d1 == 120 || d1 == 123) { pp_all_notes_off(t); return; }
        if (d1 == 99 || d1 == 98 || d1 == 101 || d1 == 100 || d1 == 6 || d1 == 38) { pp_nrpn_cc(t, d1, d2); return; }
        const int param = pp_param_of_cc(d1);
        if (param >= 0) { pp_set_param(t, param, d2 * 256); return; }
    }
    if (!pp_enabled[t] && (cmd == 0x90 || cmd == 0x80)) return;   /* (its notes off went out when it was turned off) */
    if (cmd == 0x90 && d2) pp_note_on(t);
    if (cmd == 0x80 || cmd == 0x90 || cmd == 0xB0)
        m2k_midi(cmd | ((midi_ch() + t) & 15), d1, d2);
    if (cmd == 0x90) for (int p = 0; p < P_COUNT; p++) pp_apply(t, p);   /* (the note copied the kit into eff) */
}

/* ------------------------------------------------------------- the render */

/* m2k_render's block (m2k_fx.c), one core, with each track rendered into its own buffer: the tracks come out on
 * their own and the bus hears only their reverb sends. The bus plays a block behind the tracks (it runs on the
 * record of the block before), so the tracks are let out a block late too, in step with it. Off tracks still
 * render: a note let go rings out its release, and the CPU is no concern (eight tracks are a few percent of a
 * Pi's core) */
static int16_t pp_fx16[2 * M2K_SUB];
static float pp_tout[2][NT][2][M2K_SUB];            /* [this block, the one before][track][L, R] */
static int pp_tcur;

static void pp_render_split(void)
{
    static int32_t ds[M2K_SUB], tL[M2K_SUB], tR[M2K_SUB];
    brec_t *rc = &brec[bcur];
    rc->nstep = 0;
    rc->dt = 0;
    seq_block();
    for (int t = 0; t < NT; t++) lfo_block(t);
    mod_apply();
    brec_take(rc);
    m_set(rc->L, 0, sizeof rc->L);
    m_set(rc->R, 0, sizeof rc->R);
    m_set(rc->rs, 0, sizeof rc->rs);
    hold_bpm = ext_bpm ? ext_bpm : 30u + PAT(cur_pat)->glob[G_TMPO];
    dub_snap = bus.dub_t;
    bus_run(&brec[bcur ^ 1], pp_fx16);
    /* what the bus would scale the mix by on its way out (master and drive; its soft limit is the identity
     * below -6 dB), so a track's out is its share of MONO2K's mix */
    const float g = (float)T_MVOL[rc->mvol] * (float)T_DRIV[rc->glob[G_DRIV]] / (256.0f * 32768.0f * 32768.0f);
    pp_tcur ^= 1;
    for (int t = 0; t < NT; t++) {
        m_set(tL, 0, sizeof tL);
        m_set(tR, 0, sizeof tR);
        run_track(t, tL, tR, rc->rs, ds);       /* (L and R stay empty: the bus gets the sends alone) */
        for (int i = 0; i < M2K_SUB; i++) {
            pp_tout[pp_tcur][t][0][i] = tL[i] * g;
            pp_tout[pp_tcur][t][1][i] = tR[i] * g;
        }
    }
    mx_gates_out();
    rc->valid = 1;
    bcur ^= 1;
}

/* ------------------------------------------------- 44.1 kHz -> host rate */

static int pp_stock;                    /* --stock: the core's own render, its mix on the return's channels */
static int pp_trace_param = -1;         /* --trace-param: that parameter of track 1 as the DSP reads it, a line a block */
static int16_t pp_stock16[2 * M2K_SUB];
static int pp_pos = M2K_SUB;
static float pp_s0[NCH], pp_s1[NCH];
static double pp_ph, pp_step;

static void pp_next_in(float out[NCH])
{
    if (pp_pos >= M2K_SUB) {
        pp_glide_block();
        if (pp_trace_param >= 0) fprintf(stderr, "%u %d\n", m2k_samples(), P8(&trk[0], pp_trace_param));
        if (pp_stock) m2k_render(pp_stock16, M2K_SUB);
        else pp_render_split();
        pp_pos = 0;
    }
    const int prev = pp_tcur ^ 1;
    for (int t = 0; t < NT; t++) {
        out[2 * t] = pp_stock ? 0.0f : pp_tout[prev][t][0][pp_pos];
        out[2 * t + 1] = pp_stock ? 0.0f : pp_tout[prev][t][1][pp_pos];
    }
    const int16_t *fx = pp_stock ? pp_stock16 : pp_fx16;
    out[2 * NT] = fx[2 * pp_pos] * (1.0f / 32768.0f);
    out[2 * NT + 1] = fx[2 * pp_pos + 1] * (1.0f / 32768.0f);
    pp_pos++;
}

static void pp_resampler_init(unsigned rate)
{
    pp_step = (double)M2K_SR / (double)rate;
    pp_ph = 0.0;
    pp_next_in(pp_s0);
    pp_next_in(pp_s1);
}

static void pp_out_frame(float out[NCH])
{
    while (pp_ph >= 1.0) {
        pp_ph -= 1.0;
        memcpy(pp_s0, pp_s1, sizeof pp_s0);
        pp_next_in(pp_s1);
    }
    const float f = (float)pp_ph;
    for (int c = 0; c < NCH; c++) out[c] = pp_s0[c] + (pp_s1[c] - pp_s0[c]) * f;
    pp_ph += pp_step;
}

/* ------------------------------------------------------------ offline render */

typedef struct { double t; uint8_t m[3]; } pp_ev_t;

static const pp_ev_t PP_DEMO[] = {
    {0.00, {0x90, 48, 100}}, {0.40, {0x80, 48, 0}},
    {0.50, {0x90, 55, 100}}, {0.90, {0x80, 55, 0}},
    {1.00, {0xB0, 72, 0}},   {1.00, {0x90, 60, 100}},  /* FILT BASE (the high-pass's): swept up, then back */
    {1.20, {0xB0, 72, 30}},  {1.40, {0xB0, 72, 60}},
    {1.80, {0x80, 60, 0}},   {1.90, {0xB0, 72, 0}},
    {2.00, {0xB1, CC_MACHINE, M_SAW}}, {2.00, {0x91, 36, 100}}, {2.60, {0x81, 36, 0}},   /* track 2 */
    {2.70, {0xF8, 0, 0}}, {2.70, {0xFA, 0, 0}},          /* clock and start: must be ignored */
};

static void pp_put_le(FILE *f, uint32_t v, int bytes)
{
    for (int i = 0; i < bytes; i++) fputc((int)((v >> (8 * i)) & 0xFF), f);
}

static FILE *pp_wav_open(const char *path, unsigned rate, uint32_t frames)
{
    FILE *f = fopen(path, "wb");
    if (!f) { perror(path); return NULL; }
    fwrite("RIFF", 1, 4, f); pp_put_le(f, 36 + frames * 4, 4);
    fwrite("WAVEfmt ", 1, 8, f); pp_put_le(f, 16, 4); pp_put_le(f, 1, 2); pp_put_le(f, 2, 2);
    pp_put_le(f, rate, 4); pp_put_le(f, rate * 4, 4); pp_put_le(f, 4, 2); pp_put_le(f, 16, 2);
    fwrite("data", 1, 4, f); pp_put_le(f, frames * 4, 4);
    return f;
}

static void pp_wav_frame(FILE *f, float l, float r)
{
    int32_t li = (int32_t)lrintf(l * 32767.0f), ri = (int32_t)lrintf(r * 32767.0f);
    li = CLAMP(li, -32767, 32767);
    ri = CLAMP(ri, -32767, 32767);
    pp_put_le(f, (uint32_t)(uint16_t)(int16_t)li, 2);
    pp_put_le(f, (uint32_t)(uint16_t)(int16_t)ri, 2);
}

static int pp_render(const char *path, unsigned rate, double seconds, const char *script, const char *stems)
{
    pp_ev_t *ev = NULL;
    size_t nev = 0;
    if (script) {
        FILE *s = fopen(script, "r");
        if (!s) { perror(script); return 1; }
        double t;
        int a, b, c;
        while (fscanf(s, "%lf %d %d %d", &t, &a, &b, &c) == 4) {
            ev = realloc(ev, (nev + 1) * sizeof *ev);
            ev[nev++] = (pp_ev_t){t, {(uint8_t)a, (uint8_t)b, (uint8_t)c}};
        }
        fclose(s);
    } else {
        nev = sizeof PP_DEMO / sizeof PP_DEMO[0];
        ev = malloc(sizeof PP_DEMO);
        memcpy(ev, PP_DEMO, sizeof PP_DEMO);
    }

    const uint32_t frames = (uint32_t)(seconds * rate);
    FILE *mix = pp_wav_open(path, rate, frames);
    FILE *stem[NT + 1] = {0};
    int ok = mix != NULL;
    if (ok && stems) {
        char p[4096];
        for (int t = 0; t <= NT && ok; t++) {
            if (t < NT) snprintf(p, sizeof p, "%s_t%d.wav", stems, t + 1);
            else snprintf(p, sizeof p, "%s_fx.wav", stems);
            ok = (stem[t] = pp_wav_open(p, rate, frames)) != NULL;
        }
    }
    if (ok) {
        pp_resampler_init(rate);
        size_t next = 0;
        float o[NCH];
        for (uint32_t i = 0; i < frames; i++) {
            const double now = (double)i / rate;
            while (next < nev && ev[next].t <= now) {
                pp_handle_midi(ev[next].m[0] & 15, ev[next].m, 3);   /* (the channel is the track) */
                next++;
            }
            pp_out_frame(o);
            float l = o[2 * NT], r = o[2 * NT + 1];
            for (int t = 0; t < NT; t++) { l += o[2 * t]; r += o[2 * t + 1]; }
            pp_wav_frame(mix, l, r);
            if (stems)
                for (int t = 0; t <= NT; t++) pp_wav_frame(stem[t], o[2 * t], o[2 * t + 1]);
        }
    }
    if (mix) fclose(mix);
    for (int t = 0; t <= NT; t++) if (stem[t]) fclose(stem[t]);
    free(ev);
    return ok ? 0 : 1;
}

/* ---------------------------------------------------------------------- JACK */

#ifdef M2K_WITH_JACK
static jack_port_t *pp_midi_in[NT], *pp_out[NCH];
static volatile sig_atomic_t pp_quit;

/* the MIDI of every track, in time order, applied at the frame each falls on */
static int pp_process(jack_nframes_t nframes, void *arg)
{
    (void)arg;
    void *mbuf[NT];
    jack_nframes_t nev[NT], ei[NT];
    jack_midi_event_t ev[NT];
    int have[NT];
    for (int t = 0; t < NT; t++) {
        mbuf[t] = jack_port_get_buffer(pp_midi_in[t], nframes);
        nev[t] = jack_midi_get_event_count(mbuf[t]);
        ei[t] = 0;
        have[t] = nev[t] && jack_midi_event_get(&ev[t], mbuf[t], 0) == 0;
    }
    float *out[NCH];
    for (int c = 0; c < NCH; c++) out[c] = jack_port_get_buffer(pp_out[c], nframes);
    float o[NCH];
    for (jack_nframes_t i = 0; i <= nframes; i++) {
        for (int t = 0; t < NT; t++)
            while (have[t] && (i == nframes || ev[t].time <= i)) {   /* (at the end: those stamped past the period) */
                pp_handle_midi(t, ev[t].buffer, ev[t].size);
                have[t] = ++ei[t] < nev[t] && jack_midi_event_get(&ev[t], mbuf[t], ei[t]) == 0;
            }
        if (i == nframes) break;
        pp_out_frame(o);
        for (int c = 0; c < NCH; c++) out[c][i] = o[c];
    }
    return 0;
}

static void on_signal(int sig) { (void)sig; pp_quit = 1; }
static void on_shutdown(void *arg) { (void)arg; pp_quit = 1; }

static void connect_midi(jack_client_t *c, int t, const char *substr)
{
    const char **ports = jack_get_ports(c, NULL, JACK_DEFAULT_MIDI_TYPE, JackPortIsOutput);
    int found = 0;
    for (int i = 0; ports && ports[i]; i++) {
        if (!strstr(ports[i], substr)) continue;
        if (jack_connect(c, ports[i], jack_port_name(pp_midi_in[t])) == 0) {
            fprintf(stderr, "m2k-jack: track %d MIDI from %s\n", t + 1, ports[i]);
            found = 1;
        }
    }
    if (!found) fprintf(stderr, "m2k-jack: track %d: no MIDI output port matches \"%s\"\n", t + 1, substr);
    jack_free(ports);
}

/* every pair to the first two physical playback ports, as Surge's are: pushpin moves the tracks it uses onto
 * its volume node from there */
static void connect_audio(jack_client_t *c)
{
    const char **ports = jack_get_ports(c, NULL, JACK_DEFAULT_AUDIO_TYPE, JackPortIsPhysical | JackPortIsInput);
    for (int ch = 0; ch < NCH && ports && ports[0]; ch += 2) {
        jack_connect(c, jack_port_name(pp_out[ch]), ports[0]);
        if (ports[1]) jack_connect(c, jack_port_name(pp_out[ch + 1]), ports[1]);
    }
    jack_free(ports);
}

static int run_jack(const char *name, const char *const midi_substr[NT], int audio_connect)
{
    jack_status_t st;
    jack_client_t *c = jack_client_open(name, JackNoStartServer, &st);
    if (!c) { fprintf(stderr, "m2k-jack: no JACK server (status 0x%x)\n", (unsigned)st); return 1; }
    char pn[32];
    for (int t = 0; t < NT; t++) {
        snprintf(pn, sizeof pn, "track%d_midi", t + 1);
        pp_midi_in[t] = jack_port_register(c, pn, JACK_DEFAULT_MIDI_TYPE, JackPortIsInput, 0);
        snprintf(pn, sizeof pn, "track%d_L", t + 1);
        pp_out[2 * t] = jack_port_register(c, pn, JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0);
        snprintf(pn, sizeof pn, "track%d_R", t + 1);
        pp_out[2 * t + 1] = jack_port_register(c, pn, JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0);
    }
    pp_out[2 * NT] = jack_port_register(c, "fx_L", JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0);
    pp_out[2 * NT + 1] = jack_port_register(c, "fx_R", JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0);
    for (int t = 0; t < NT; t++) if (!pp_midi_in[t]) { fprintf(stderr, "m2k-jack: could not register ports\n"); return 1; }
    for (int ch = 0; ch < NCH; ch++) if (!pp_out[ch]) { fprintf(stderr, "m2k-jack: could not register ports\n"); return 1; }
    pp_resampler_init(jack_get_sample_rate(c));
    jack_set_process_callback(c, pp_process, NULL);
    jack_on_shutdown(c, on_shutdown, NULL);
    if (jack_activate(c)) { fprintf(stderr, "m2k-jack: could not activate\n"); return 1; }
    fprintf(stderr, "m2k-jack: \"%s\" at %u Hz (core %d Hz), tracks on:", jack_get_client_name(c),
            (unsigned)jack_get_sample_rate(c), M2K_SR);
    for (int t = 0; t < NT; t++) if (pp_enabled[t]) fprintf(stderr, " %d", t + 1);
    fprintf(stderr, "\n");
    if (audio_connect) connect_audio(c);
    for (int t = 0; t < NT; t++) if (midi_substr[t]) connect_midi(c, t, midi_substr[t]);

    signal(SIGINT, on_signal);
    signal(SIGTERM, on_signal);
    while (!pp_quit) usleep(100000);
    jack_client_close(c);
    return 0;
}
#endif

/* ---------------------------------------------------------------------- main */

static void pp_usage(void)
{
    fprintf(stderr,
            "usage: m2k-jack [--name NAME] [--machine N] [--midi-connect TRACK=SUBSTR ...] [--enable 1,2,..|none]\n"
            "                [--no-audio-connect] [--glide-ms MS (20)] [--snap-ms MS (10)]\n"
            "       m2k-jack --render OUT.wav [--rate HZ] [--seconds S] [--machine N] [--script FILE]\n"
            "                [--stems PREFIX] [--stock]\n"
            "                [--trace-param P]   (stderr: samples and track 1's parameter P as the DSP reads it, Q8)\n"
            "       m2k-jack --list-machines | --describe\n");
}

/* "1,3,8" or "none" into pp_enabled; 0 when it isn't either */
static int pp_parse_enable(const char *s)
{
    for (int t = 0; t < NT; t++) pp_enabled[t] = 0;
    if (!strcmp(s, "none")) return 1;
    while (*s) {
        char *end;
        long t = strtol(s, &end, 10);
        if (end == s || t < 1 || t > NT) return 0;
        pp_enabled[t - 1] = 1;
        s = *end == ',' ? end + 1 : end;
        if (*end && *end != ',') return 0;
    }
    return 1;
}

int main(int argc, char **argv)
{
    const char *name = "M2K", *render_path = NULL, *script = NULL, *stems = NULL;
    const char *midi_substr[NT] = {0};
    unsigned rate = 48000;
    double seconds = 3.0;
    int machine = -1, audio_connect = 1;
    double glide_ms = 20.0, snap_ms = 10.0;
    for (int t = 0; t < NT; t++) { pp_enabled[t] = 1; pp_nrpn_param[t] = -1; pp_nrpn_hi[t] = 127; }
    for (int i = 1; i < argc; i++) {
        const char *a = argv[i];
        const int more = i + 1 < argc;
        if (!strcmp(a, "--list-machines")) {
            for (int m = 0; m < M_COUNT; m++) printf("%d\t%s\n", m, MI[m].name);
            return 0;
        } else if (!strcmp(a, "--describe")) {
            pp_engine_init(0);
            pp_describe();
            return 0;
        } else if (!strcmp(a, "--name") && more) name = argv[++i];
        else if (!strcmp(a, "--machine") && more) machine = atoi(argv[++i]);
        else if (!strcmp(a, "--midi-connect") && more) {
            const char *v = argv[++i];
            char *end;
            long t = strtol(v, &end, 10);
            if (end == v || *end != '=' || t < 1 || t > NT || !end[1]) {
                fprintf(stderr, "m2k-jack: --midi-connect takes TRACK=SUBSTR, TRACK 1-%d\n", NT);
                return 2;
            }
            midi_substr[t - 1] = end + 1;
        } else if (!strcmp(a, "--enable") && more) {
            if (!pp_parse_enable(argv[++i])) { fprintf(stderr, "m2k-jack: --enable takes 1-%d, comma separated, or none\n", NT); return 2; }
        } else if (!strcmp(a, "--no-audio-connect")) audio_connect = 0;
        else if (!strcmp(a, "--glide-ms") && more) glide_ms = atof(argv[++i]);
        else if (!strcmp(a, "--snap-ms") && more) snap_ms = atof(argv[++i]);
        else if (!strcmp(a, "--render") && more) render_path = argv[++i];
        else if (!strcmp(a, "--rate") && more) rate = (unsigned)atoi(argv[++i]);
        else if (!strcmp(a, "--seconds") && more) seconds = atof(argv[++i]);
        else if (!strcmp(a, "--script") && more) script = argv[++i];
        else if (!strcmp(a, "--stems") && more) stems = argv[++i];
        else if (!strcmp(a, "--stock")) pp_stock = 1;
        else if (!strcmp(a, "--trace-param") && more) pp_trace_param = atoi(argv[++i]);
        else { pp_usage(); return 2; }
    }
    if (machine >= M_COUNT) { fprintf(stderr, "m2k-jack: machine %d out of range (0-%d)\n", machine, M_COUNT - 1); return 2; }
    if (rate < 8000 || rate > 384000) { fprintf(stderr, "m2k-jack: bad rate %u\n", rate); return 2; }
    if (glide_ms < 0 || snap_ms < 0) { fprintf(stderr, "m2k-jack: --glide-ms and --snap-ms are 0 or more\n"); return 2; }
    if (pp_trace_param >= P_COUNT) { fprintf(stderr, "m2k-jack: --trace-param is 0-%d\n", P_COUNT - 1); return 2; }

    pp_set_glide(glide_ms);
    pp_snap = (uint32_t)(snap_ms * 0.001 * M2K_SR);
    pp_engine_init(machine);
    if (render_path) return pp_render(render_path, rate, seconds, script, stems);
#ifdef M2K_WITH_JACK
    return run_jack(name, midi_substr, audio_connect);
#else
    (void)name; (void)midi_substr; (void)audio_connect;
    fprintf(stderr, "m2k-jack: built without JACK; only --render, --list-machines and --describe work\n");
    return 1;
#endif
}
