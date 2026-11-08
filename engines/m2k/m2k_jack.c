/* SPDX-License-Identifier: GPL-3.0-only */
/*
 * m2k-jack: the MONO2K synth core (https://github.com/InigoHernandez/mono2k) as a
 * one-voice JACK synth for pushpin, launched the same way surge-xt-cli is.
 *
 * This file is GPL-3.0-only because it compiles the GPL-3.0-only MONO2K core
 * into itself. It is a separate program that pushpin talks to over MIDI only, so
 * pushpin (MIT) never links against it.
 *
 * One pp_process plays one MONO2K track (track 1). Every MIDI channel is folded
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
 *   CC 14        (pushpin's own) machine: the value is the machine's number (--list-machines)
 *   CC 120, 123  all sound off / all notes off
 *   Clock, start, stop and other system messages are dropped: pushpin sequences,
 *   MONO2K's own sequencer stays stopped.
 *
 * The core runs at 44.1 kHz; the output is resampled (linear) to the JACK rate.
 *
 * Usage:
 *   m2k-jack [--name NAME] [--machine N] [--midi-connect SUBSTR] [--no-audio-connect]
 *   m2k-jack --render OUT.wav [--rate HZ] [--machine N] [--script FILE]
 *   m2k-jack --list-machines
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

#include "m2k_core.c"

#ifdef M2K_WITH_JACK
#include <jack/jack.h>
#include <jack/midiport.h>
#endif

#define TRACK 0
#define CC_MACHINE 14

/* ------------------------------------------------------------------ the core */

static void pp_engine_init(int machine)
{
    m2k_init(0x50555348u);
    /* a blank pattern in place of the factory demo: the default kit, no trigs, no locks */
    m2k_pattern_t *p = PAT(cur_pat);
    pat_init(p, "PUSHPIN");
    lockmap_build();
    for (int t = 0; t < M2K_TRACKS; t++) m_cpy(trk[t].eff, p->kit[t], P_COUNT);
    seq_tempo();
    if (machine >= 0 && machine < M_COUNT) machine_to(TRACK, machine);
}

static void pp_all_notes_off(void)
{
    for (int i = 0; i < 8 && sq.nkeys[TRACK]; i++) live_off_t(TRACK, sq.keys[TRACK][0]);
    voice_off(TRACK);
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
        if (d1 == CC_MACHINE) {
            if (d2 < M_COUNT) machine_to(TRACK, d2);
            return;
        }
        if (d1 == 120 || d1 == 123) { pp_all_notes_off(); return; }
    }
    if (cmd == 0x80 || cmd == 0x90 || cmd == 0xB0)
        m2k_midi(cmd | ((midi_ch() + TRACK) & 15), d1, d2);
}

/* ------------------------------------------------- 44.1 kHz -> host rate */

static int16_t pp_blk[M2K_SUB * 2];
static int pp_pos = M2K_SUB;
static float pp_s0[2], pp_s1[2];
static double pp_ph, pp_step;

static void pp_next_in(float out[2])
{
    if (pp_pos >= M2K_SUB) { m2k_render(pp_blk, M2K_SUB); pp_pos = 0; }
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
            "       m2k-jack --render OUT.wav [--rate HZ] [--seconds S] [--machine N] [--script FILE]\n"
            "       m2k-jack --list-machines\n");
}

int main(int argc, char **argv)
{
    const char *name = "m2k", *render_path = NULL, *script = NULL, *midi_substr = NULL;
    unsigned rate = 48000;
    double seconds = 3.0;
    int machine = -1, audio_connect = 1;
    for (int i = 1; i < argc; i++) {
        const char *a = argv[i];
        const int more = i + 1 < argc;
        if (!strcmp(a, "--list-machines")) {
            for (int m = 0; m < M_COUNT; m++) printf("%d\t%s\n", m, MI[m].name);
            return 0;
        } else if (!strcmp(a, "--name") && more) name = argv[++i];
        else if (!strcmp(a, "--machine") && more) machine = atoi(argv[++i]);
        else if (!strcmp(a, "--midi-connect") && more) midi_substr = argv[++i];
        else if (!strcmp(a, "--no-audio-connect")) audio_connect = 0;
        else if (!strcmp(a, "--render") && more) render_path = argv[++i];
        else if (!strcmp(a, "--rate") && more) rate = (unsigned)atoi(argv[++i]);
        else if (!strcmp(a, "--seconds") && more) seconds = atof(argv[++i]);
        else if (!strcmp(a, "--script") && more) script = argv[++i];
        else { pp_usage(); return 2; }
    }
    if (machine >= M_COUNT) { fprintf(stderr, "m2k-jack: machine %d out of range (0-%d)\n", machine, M_COUNT - 1); return 2; }
    if (rate < 8000 || rate > 384000) { fprintf(stderr, "m2k-jack: bad rate %u\n", rate); return 2; }

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
