/* SPDX-License-Identifier: GPL-3.0-only */
/*
 * m2k-jack: the MONO2K synth core (https://github.com/InigoHernandez/mono2k) as a
 * one-voice JACK synth for pushpin, launched the same way surge-xt-cli is.
 *
 * This file is GPL-3.0-only because it compiles the GPL-3.0-only MONO2K core
 * into itself. It is a separate program that pushpin talks to over MIDI only, so
 * pushpin (MIT) never links against it.
 *
 * One process plays one MONO2K track (track 1). Every MIDI channel is folded
 * onto that track, so pushpin can send on whatever channel its instrument uses.
 *
 *   Notes        note on / note off (velocity is ignored, as on the Monomachine)
 *   CC 3         mute (0 = heard)
 *   CC 7         level
 *   CC 48-55     SYN A-H (the machine's own page)
 *   CC 56-63     AMP: ATK HOLD DEC REL DIST VOL PAN PORT
 *   CC 72-79     FILT: BASE WDTH HPQ LPQ FATK FDEC BOF WOF
 *   CC 80-87     FX: EQF EQG SRR DTIM DSND DFB DBAS DWID
 *   CC 88/104/112 + 0..7  LFO 1/2/3: TRCK DEST WAVE TRIG MULT SPD PHAS DPTH
 *   pushpin's own additions:
 *   CC 14        machine (its number from --list-machines); loads the machine's INIT sound
 *   CC 16-20     DSTR: BITS FOLD XOR, reverb send (VERB), track pitch (PTCH)
 *   CC 120, 123  all sound off / all notes off
 *   NRPN 0:<cc>  (CC 99 = 0, CC 98 = the parameter's CC number, then CC 6 = value, CC 38 = fine): the same
 *                parameter at 14 bits. The core keeps 1/256 of a step, so 7 of those bits reach the sound.
 *   Clock, start, stop and other system messages are dropped: pushpin sequences,
 *   MONO2K's own sequencer stays stopped.
 *
 * The core runs at 44.1 kHz; the output is resampled (linear) to the JACK rate.
 *
 * Parameters glide to a new value over --glide-ms (one pole, default 20 ms), at the core's 1/256 of a step
 * (a patch adds trk_t.fine to the core's P8()), so a knob turned through MONO2K's 1/8-octave filter steps
 * sweeps instead of stepping. A change that lands within --snap-ms (default 10 ms) of a note-on, as
 * pushpin's p-locks do, is set at once. Choices (waves, modes, LFO destinations) always snap.
 *
 * Usage:
 *   m2k-jack [--name NAME] [--machine N] [--midi-connect SUBSTR] [--no-audio-connect] [--glide-ms MS] [--snap-ms MS]
 *   m2k-jack --render OUT.wav [--rate HZ] [--machine N] [--script FILE]
 *   m2k-jack --list-machines
 *   m2k-jack --describe          every machine's parameters and INIT sound as JSON
 *                                (engines/m2k/gen_definitions.py builds pushpin's pages from it)
 *
 * --render plays a short phrase (or the --script: lines "seconds status d1 d2",
 * decimal) through the same MIDI handling and resampler and writes a 16-bit WAV.
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

#define TRACK 0
#define CC_MACHINE 14

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

/* ------------------------------------------------------- parameters, smoothed */

/* each parameter as 0..127*256 (the core's P8 scale): where it is going and where it is heard. The kit keeps the
 * whole part of the target (a note-on copies the kit into eff), trk_t.fine carries the rest and the glide */
static int32_t pp_target[P_COUNT], pp_cur[P_COUNT];
static uint8_t pp_moving[P_COUNT];
static uint32_t pp_set_at[P_COUNT], pp_note_at;
static int pp_have_note;
static int32_t pp_glide_k = 0;          /* per 16-sample block, Q16; 0: no glide */
static uint32_t pp_snap = M2K_SR / 100;

static void pp_set_glide(double ms)
{
    if (ms <= 0) { pp_glide_k = 0; return; }
    const double k = 1.0 - exp(-(double)M2K_SUB / (ms * 0.001 * M2K_SR));
    pp_glide_k = (int32_t)(k * 65536.0 + 0.5);
    if (pp_glide_k < 1) pp_glide_k = 1;
}

static void pp_params_reset(void)
{
    const uint8_t *kit = PAT(cur_pat)->kit[TRACK];
    for (int p = 0; p < P_COUNT; p++) {
        pp_target[p] = pp_cur[p] = kit[p] * 256;
        pp_moving[p] = 0;
        trk[TRACK].fine[p] = 0;
    }
}

/* a choice (a wave, a mode, a destination): never through the values between */
static int pp_discrete(int param)
{
    const int kind = pinfo(TRACK, param)->kind;
    return kind_choices(kind) != 0 || kind == K_DEST || kind == K_TRK;
}

static void pp_apply(int param)
{
    trk[TRACK].fine[param] = pp_cur[param] - trk[TRACK].eff[param] * 256;
}

static void pp_snap_param(int param)
{
    pp_cur[param] = pp_target[param];
    pp_moving[param] = 0;
    pp_apply(param);
}

static void pp_set_param(int param, int32_t q8)
{
    const int32_t top = (param == P_LFO + L_DEST || param == P_LFO + 8 + L_DEST || param == P_LFO + 16 + L_DEST)
                            ? P_COUNT * 256 : 127 * 256;
    q8 = CLAMP(q8, 0, top);
    if (pp_discrete(param)) q8 &= ~255;
    const uint8_t whole = (uint8_t)(q8 >> 8);
    PAT(cur_pat)->kit[TRACK][param] = whole;
    trk[TRACK].eff[param] = whole;
    pp_target[param] = q8;
    pp_set_at[param] = m2k_samples();
    if (!pp_glide_k || pp_discrete(param) || (pp_have_note && m2k_samples() - pp_note_at <= pp_snap))
        pp_snap_param(param);
    else {
        pp_moving[param] = 1;
        pp_apply(param);                /* (eff moved under it: heard where it was) */
    }
}

/* a note-on: what was set just before it (a p-lock) is heard on it, not glided into */
static void pp_note_on(void)
{
    const uint32_t now = m2k_samples();
    pp_note_at = now;
    pp_have_note = 1;
    for (int p = 0; p < P_COUNT; p++)
        if (pp_moving[p] && now - pp_set_at[p] <= pp_snap) pp_snap_param(p);
}

/* a note-on copies the kit into eff, so fine is set again after every MIDI message too */
static void pp_glide_block(void)
{
    for (int p = 0; p < P_COUNT; p++) {
        if (!pp_moving[p]) { pp_apply(p); continue; }
        const int32_t d = pp_target[p] - pp_cur[p];
        int32_t step = (int32_t)(((int64_t)d * pp_glide_k) >> 16);
        if (step == 0) step = d > 0 ? 1 : -1;
        if (d > -2 && d < 2) pp_snap_param(p);
        else { pp_cur[p] += step; pp_apply(p); }
    }
}

static int pp_param_of_cc(int cc)
{
    for (int i = 0; i < PP_NCC; i++)
        if (PP_CC[i].cc == cc) return PP_CC[i].param;
    return -1;
}

/* machine m on the track with its whole INIT sound: the same sound whatever was there before, so pushpin,
 * which hears nothing back, knows every parameter's value after a machine change */
static void pp_set_machine(int m)
{
    if (m < 0 || m >= M_COUNT) return;
    m2k_pattern_t *p = PAT(cur_pat);
    kit_init(&pat_tmp, TRACK, m);
    m_cpy(p->kit[TRACK], pat_tmp.kit[TRACK], P_COUNT);
    p->machine[TRACK] = (uint8_t)m;
    m_cpy(trk[TRACK].eff, p->kit[TRACK], P_COUNT);
    track_home(TRACK, mach_home(m));
    pp_params_reset();
}

static void pp_engine_init(int machine)
{
    m2k_init(0x50555348u);
    /* a blank pattern in place of the factory demo: the default kit, no trigs, no locks */
    m2k_pattern_t *p = PAT(cur_pat);
    pat_init(p, "PUSHPIN");
    lockmap_build();
    for (int t = 0; t < M2K_TRACKS; t++) m_cpy(trk[t].eff, p->kit[t], P_COUNT);
    seq_tempo();
    pp_set_machine(machine < 0 ? 0 : machine);
}

static void pp_json_str(const char *s)
{
    putchar('"');
    for (; *s; s++) {
        if (*s == '"' || *s == '\\') putchar('\\');
        putchar(*s);
    }
    putchar('"');
}

static void pp_json_param(const pi_t *pi)
{
    printf("{\"label\": ");
    pp_json_str(pi->s4);
    printf(", \"name\": ");
    pp_json_str(pi->name);
    printf(", \"max\": %d, \"bipolar\": %s, \"choices\": %d}", kind_max(pi->kind),
           pi->kind == K_BI || pi->kind == K_PAN || pi->kind == K_SEMI ? "true" : "false", kind_choices(pi->kind));
}

/* the data pushpin's device pages are generated from: no audio, nothing but the core's own tables */
static void pp_describe(void)
{
    printf("{\n  \"machine_cc\": %d,\n  \"params\": [\n", CC_MACHINE);
    int first = 1;
    for (int i = 0; i < PP_NCC; i++) {
        if (PP_CC[i].param < 8) continue;                  /* SYN: the machines' own, below */
        printf("%s    {\"cc\": %d, \"page\": \"%s\", \"param\": ", first ? "" : ",\n", PP_CC[i].cc, PP_CC[i].page);
        pp_json_param(pinfo(TRACK, PP_CC[i].param));
        putchar('}');
        first = 0;
    }
    printf("\n  ],\n  \"machines\": [\n");
    for (int m = 0; m < M_COUNT; m++) {
        kit_init(&pat_tmp, TRACK, m);
        printf("    {\"index\": %d, \"name\": ", m);
        pp_json_str(MI[m].name);
        printf(", \"syn\": [");
        for (int k = 0; k < 8; k++) {
            if (k) printf(", ");
            printf("{\"cc\": %d, \"param\": ", 48 + k);
            pp_json_param(&MI[m].syn[k]);
            putchar('}');
        }
        printf("],\n     \"init\": {");
        for (int i = 0; i < PP_NCC; i++)
            printf("%s\"%d\": %d", i ? ", " : "", PP_CC[i].cc, pat_tmp.kit[TRACK][PP_CC[i].param]);
        printf("}}%s\n", m + 1 < M_COUNT ? "," : "");
    }
    printf("  ]\n}\n");
}

static void pp_all_notes_off(void)
{
    for (int i = 0; i < 8 && sq.nkeys[TRACK]; i++) live_off_t(TRACK, sq.keys[TRACK][0]);
    voice_off(TRACK);
}

/* NRPN: the parameter chosen (CC 99, CC 98: 0 and a CC number), its value's coarse part (CC 6) */
static int pp_nrpn_param = -1, pp_nrpn_msb = 0, pp_nrpn_hi = 127;

static void pp_nrpn_cc(int cc, int v)
{
    switch (cc) {
    case 99: pp_nrpn_hi = v; pp_nrpn_param = -1; break;
    case 98: pp_nrpn_param = pp_nrpn_hi == 0 ? pp_param_of_cc(v) : -1; break;
    case 101: case 100: pp_nrpn_param = -1; break;           /* an RPN: not ours */
    case 6:
        pp_nrpn_msb = v;
        if (pp_nrpn_param >= 0) pp_set_param(pp_nrpn_param, v * 256);
        break;
    case 38:
        if (pp_nrpn_param >= 0) pp_set_param(pp_nrpn_param, pp_nrpn_msb * 256 + v * 2);
        break;
    }
}

/* one MIDI message from pushpin; called from the audio thread only */
static void pp_handle_midi(const uint8_t *m, size_t n)
{
    if (n == 0) return;
    const int status = m[0];
    if (status < 0x80 || status >= 0xF0) return;      /* running status / system: not ours */
    const int cmd = status & 0xF0;
    const int d1 = n > 1 ? m[1] & 127 : 0, d2 = n > 2 ? m[2] & 127 : 0;
    if (cmd == 0xB0) {
        if (d1 == CC_MACHINE) { pp_set_machine(d2); return; }
        if (d1 == 120 || d1 == 123) { pp_all_notes_off(); return; }
        if (d1 == 99 || d1 == 98 || d1 == 101 || d1 == 100 || d1 == 6 || d1 == 38) { pp_nrpn_cc(d1, d2); return; }
        const int param = pp_param_of_cc(d1);
        if (param >= 0) { pp_set_param(param, d2 * 256); return; }
    }
    if (cmd == 0x90 && d2) pp_note_on();
    if (cmd == 0x80 || cmd == 0x90 || cmd == 0xB0)
        m2k_midi(cmd | ((midi_ch() + TRACK) & 15), d1, d2);
    if (cmd == 0x90) for (int p = 0; p < P_COUNT; p++) pp_apply(p);   /* (the note copied the kit into eff) */
}

/* ------------------------------------------------- 44.1 kHz -> host rate */

static int16_t pp_blk[M2K_SUB * 2];
static int pp_trace_param = -1;         /* --trace-param: that parameter as the DSP reads it, a line a block */
static int pp_pos = M2K_SUB;
static float pp_s0[2], pp_s1[2];
static double pp_ph, pp_step;

static void pp_next_in(float out[2])
{
    if (pp_pos >= M2K_SUB) {
        pp_glide_block();
        if (pp_trace_param >= 0) fprintf(stderr, "%u %d\n", m2k_samples(), P8(&trk[TRACK], pp_trace_param));
        m2k_render(pp_blk, M2K_SUB);
        pp_pos = 0;
    }
    out[0] = pp_blk[2 * pp_pos] * (1.0f / 32768.0f);
    out[1] = pp_blk[2 * pp_pos + 1] * (1.0f / 32768.0f);
    pp_pos++;
}

static void pp_resampler_init(unsigned rate)
{
    pp_step = (double)M2K_SR / (double)rate;
    pp_ph = 0.0;
    pp_next_in(pp_s0);
    pp_next_in(pp_s1);
}

static void pp_out_frame(float *l, float *r)
{
    while (pp_ph >= 1.0) {
        pp_ph -= 1.0;
        pp_s0[0] = pp_s1[0]; pp_s0[1] = pp_s1[1];
        pp_next_in(pp_s1);
    }
    const float f = (float)pp_ph;
    *l = pp_s0[0] + (pp_s1[0] - pp_s0[0]) * f;
    *r = pp_s0[1] + (pp_s1[1] - pp_s0[1]) * f;
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
    {2.00, {0xB0, CC_MACHINE, M_SAW}}, {2.00, {0x91, 36, 100}}, {2.60, {0x81, 36, 0}},   /* any channel: track 1 */
    {2.70, {0xF8, 0, 0}}, {2.70, {0xFA, 0, 0}},          /* clock and start: must be ignored */
};

static void pp_put_le(FILE *f, uint32_t v, int bytes)
{
    for (int i = 0; i < bytes; i++) fputc((int)((v >> (8 * i)) & 0xFF), f);
}

static int pp_render(const char *path, unsigned rate, double seconds, const char *script)
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

    FILE *f = fopen(path, "wb");
    if (!f) { perror(path); free(ev); return 1; }
    const uint32_t frames = (uint32_t)(seconds * rate);
    fwrite("RIFF", 1, 4, f); pp_put_le(f, 36 + frames * 4, 4);
    fwrite("WAVEfmt ", 1, 8, f); pp_put_le(f, 16, 4); pp_put_le(f, 1, 2); pp_put_le(f, 2, 2);
    pp_put_le(f, rate, 4); pp_put_le(f, rate * 4, 4); pp_put_le(f, 4, 2); pp_put_le(f, 16, 2);
    fwrite("data", 1, 4, f); pp_put_le(f, frames * 4, 4);

    pp_resampler_init(rate);
    size_t next = 0;
    for (uint32_t i = 0; i < frames; i++) {
        const double now = (double)i / rate;
        while (next < nev && ev[next].t <= now) { pp_handle_midi(ev[next].m, 3); next++; }
        float l, r;
        pp_out_frame(&l, &r);
        int32_t li = (int32_t)(l * 32767.0f), ri = (int32_t)(r * 32767.0f);
        li = CLAMP(li, -32767, 32767);
        ri = CLAMP(ri, -32767, 32767);
        pp_put_le(f, (uint32_t)(uint16_t)(int16_t)li, 2);
        pp_put_le(f, (uint32_t)(uint16_t)(int16_t)ri, 2);
    }
    fclose(f);
    free(ev);
    return 0;
}

/* ---------------------------------------------------------------------- JACK */

#ifdef M2K_WITH_JACK
static jack_port_t *midi_in, *out_l, *out_r;
static volatile sig_atomic_t pp_quit;

static int pp_process(jack_nframes_t nframes, void *arg)
{
    (void)arg;
    void *mbuf = jack_port_get_buffer(midi_in, nframes);
    float *l = jack_port_get_buffer(out_l, nframes);
    float *r = jack_port_get_buffer(out_r, nframes);
    const jack_nframes_t nev = jack_midi_get_event_count(mbuf);
    jack_nframes_t ei = 0;
    jack_midi_event_t e;
    int have = nev && jack_midi_event_get(&e, mbuf, 0) == 0;
    for (jack_nframes_t i = 0; i < nframes; i++) {
        while (have && e.time <= i) {
            pp_handle_midi(e.buffer, e.size);
            have = ++ei < nev && jack_midi_event_get(&e, mbuf, ei) == 0;
        }
        pp_out_frame(&l[i], &r[i]);
    }
    while (have) {                                     /* (events stamped past the period: late, not lost) */
        pp_handle_midi(e.buffer, e.size);
        have = ++ei < nev && jack_midi_event_get(&e, mbuf, ei) == 0;
    }
    return 0;
}

static void on_signal(int sig) { (void)sig; pp_quit = 1; }
static void on_shutdown(void *arg) { (void)arg; pp_quit = 1; }

static void connect_midi(jack_client_t *c, const char *substr)
{
    const char **ports = jack_get_ports(c, NULL, JACK_DEFAULT_MIDI_TYPE, JackPortIsOutput);
    int found = 0;
    for (int i = 0; ports && ports[i]; i++) {
        if (!strstr(ports[i], substr)) continue;
        if (jack_connect(c, ports[i], jack_port_name(midi_in)) == 0) {
            fprintf(stderr, "m2k-jack: MIDI from %s\n", ports[i]);
            found = 1;
        }
    }
    if (!found) fprintf(stderr, "m2k-jack: no MIDI output port matches \"%s\"\n", substr);
    jack_free(ports);
}

static void connect_audio(jack_client_t *c)
{
    const char **ports = jack_get_ports(c, NULL, JACK_DEFAULT_AUDIO_TYPE, JackPortIsPhysical | JackPortIsInput);
    if (ports && ports[0]) jack_connect(c, jack_port_name(out_l), ports[0]);
    if (ports && ports[0] && ports[1]) jack_connect(c, jack_port_name(out_r), ports[1]);
    jack_free(ports);
}

static int run_jack(const char *name, const char *midi_substr, int audio_connect)
{
    jack_status_t st;
    jack_client_t *c = jack_client_open(name, JackNoStartServer, &st);
    if (!c) { fprintf(stderr, "m2k-jack: no JACK server (status 0x%x)\n", (unsigned)st); return 1; }
    midi_in = jack_port_register(c, "midi_in", JACK_DEFAULT_MIDI_TYPE, JackPortIsInput, 0);
    out_l = jack_port_register(c, "output_0", JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0);
    out_r = jack_port_register(c, "output_1", JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0);
    if (!midi_in || !out_l || !out_r) { fprintf(stderr, "m2k-jack: could not register ports\n"); return 1; }
    pp_resampler_init(jack_get_sample_rate(c));
    jack_set_process_callback(c, pp_process, NULL);
    jack_on_shutdown(c, on_shutdown, NULL);
    if (jack_activate(c)) { fprintf(stderr, "m2k-jack: could not activate\n"); return 1; }
    fprintf(stderr, "m2k-jack: \"%s\" at %u Hz (core %d Hz)\n", jack_get_client_name(c),
            (unsigned)jack_get_sample_rate(c), M2K_SR);
    if (audio_connect) connect_audio(c);
    if (midi_substr) connect_midi(c, midi_substr);

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
            "usage: m2k-jack [--name NAME] [--machine N] [--midi-connect SUBSTR] [--no-audio-connect]\n"
            "                [--glide-ms MS (20)] [--snap-ms MS (10)]\n"
            "       m2k-jack --render OUT.wav [--rate HZ] [--seconds S] [--machine N] [--script FILE]\n"
            "                [--trace-param P]   (stderr: samples and parameter P as the DSP reads it, Q8, per block)\n"
            "       m2k-jack --list-machines | --describe\n");
}

int main(int argc, char **argv)
{
    const char *name = "m2k", *render_path = NULL, *script = NULL, *midi_substr = NULL;
    unsigned rate = 48000;
    double seconds = 3.0;
    int machine = -1, audio_connect = 1;
    double glide_ms = 20.0, snap_ms = 10.0;
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
        else if (!strcmp(a, "--midi-connect") && more) midi_substr = argv[++i];
        else if (!strcmp(a, "--no-audio-connect")) audio_connect = 0;
        else if (!strcmp(a, "--glide-ms") && more) glide_ms = atof(argv[++i]);
        else if (!strcmp(a, "--snap-ms") && more) snap_ms = atof(argv[++i]);
        else if (!strcmp(a, "--render") && more) render_path = argv[++i];
        else if (!strcmp(a, "--rate") && more) rate = (unsigned)atoi(argv[++i]);
        else if (!strcmp(a, "--seconds") && more) seconds = atof(argv[++i]);
        else if (!strcmp(a, "--script") && more) script = argv[++i];
        else if (!strcmp(a, "--trace-param") && more) pp_trace_param = atoi(argv[++i]);
        else { pp_usage(); return 2; }
    }
    if (machine >= M_COUNT) { fprintf(stderr, "m2k-jack: machine %d out of range (0-%d)\n", machine, M_COUNT - 1); return 2; }
    if (rate < 8000 || rate > 384000) { fprintf(stderr, "m2k-jack: bad rate %u\n", rate); return 2; }

    if (glide_ms < 0 || snap_ms < 0) { fprintf(stderr, "m2k-jack: --glide-ms and --snap-ms are 0 or more\n"); return 2; }
    pp_set_glide(glide_ms);
    pp_snap = (uint32_t)(snap_ms * 0.001 * M2K_SR);
    pp_engine_init(machine);
    if (render_path) return pp_render(render_path, rate, seconds, script);
#ifdef M2K_WITH_JACK
    return run_jack(name, midi_substr, audio_connect);
#else
    (void)name; (void)midi_substr; (void)audio_connect;
    fprintf(stderr, "m2k-jack: built without JACK; only --render and --list-machines work\n");
    return 1;
#endif
}
