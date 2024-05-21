---
title: "Pushpin: Open Source Groovebox, by Kinga Janicka"
permalink: /
layout: default
---

# About Pushpin

> Pushpin is an open-source groovebox project by improvisational electronic musician [Kinga Janicka][kinga].

Building upon Kinga's experience in the field performing live techno, Pushpin seeks to marry the power of the
award-winning open-source [Surge XT][surge] soft-synth with the form-factor of the Ableton Push 2.

# Features

- Eight fully-featured synth tracks (one instance of Surge XT per track)
- Expressive, performance-driven sequencer
- Designed to be used without a laptop on a Raspberry Pi 5
- Attach a screen to see each Surge instance at a glance (coming soon)
- Customise Pushpin's layout using a simple JSON-based format
- Use any Surge XT preset or patch

# What is it?

Pushpin is a Python application that builds heavily upon [Frederick Font][ffont]'s [Pysha][pysha] project by creating
an interface for communicating with [Surge XT][surge] via the [Open Source Control (OSC)][osc_wiki] standard, using
a standard Ableton Push 2. It controls 8 instances of Surge XT, and sequences them via either external or built-in sequencer
(coming soon).

This allows an enormous degree of creative expression, with Surge's powerful modules accessible in a ergonomic layout
that's optimised for live performance.

# Synth engine (Surge XT) specifications

- Two oscillators, two filters and three insert FX per track
- 12 oscillator types
- 12 filter types
- 29 effect types
- Six assignable LFOs/envelopes per track
- Extensive modulation matrix
- Ability to process external audio or use tracks as sends

[kinga]: https://www.kinga.dev
[surge]: https://surge-synthesizer.github.io/
[ffont]: http://www.github.com/ffont
[pysha]: https://github.com/ffont/pysha
[osc_wiki]: https://en.wikipedia.org/wiki/Open_Sound_Control
