---
title: "About"
permalink: /
layout: home
---

> **Pushpin** is an open-source groovebox project by improvisational electronic musician [Kinga Janicka][kinga].

Building upon Kinga's experience in the field performing live improvised techno, Pushpin seeks to marry the versatility of the
award-winning open-source [Surge XT][surge] soft-synth with the form-factor of the Ableton® Push® 2, powered as a standalone unit
by [Raspberry Pi® 5][rpi5].

<div style="text-align: center">
    <iframe width="560" height="315" src="https://www.youtube.com/embed/ibr5AQ0NQH8?si=CztI3rN82s1jOuJb&controls=0&rel=0&iv_load_policy=3" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>
</div>

# Features

- Eight fully-featured synth tracks (one instance of Surge XT per track)
- Dynamic instrument routing directly from the Ableton® Push® 2 for longer effect chains, sends and master effects
- [Overwitch support][overwitch] built-in for routing Elektron® Overbridge 2-compatible devices
- Designed to be used without a laptop on a Raspberry Pi® 5
- Attach a screen to see each Surge instance at a glance (coming soon)
- Customise Pushpin's layout using a simple JSON-based format
- Use any Surge XT preset or patch
- Built to be extensible and easily fork-able

# What is it?

Pushpin is a Python application that builds heavily upon [Frederick Font][ffont]'s open source [Pysha][pysha] framework by creating
an interface for communicating with [Surge XT][surge] via the [Open Source Control (OSC)][osc_wiki] standard, using
a standard Ableton® Push® 2. It controls 8 instances of Surge XT, and sequences them via either external or built-in sequencer
(coming soon).

This allows an enormous degree of creative expression, with Surge's powerful modules accessible in a ergonomic layout
that's optimised for live performance.

For the cost of an Ableton® Push® 2, a Raspberry Pi 5 and an audio interface, you can have a fully-featured groovebox with powerful features rivalling the most expensive devices on the market. Even better, with a little bit of Python knowledge you can hack it to do _literally anything you can dream of._

# Surge XT specifications

Pushpin runs a separate instance of Surge XT per instrument track. This means that each instrument track is capable of:

- Two oscillators, two filters and three insert FX per track
- 12 oscillator types
- 12 filter types
- 29 effect types
- Six assignable LFOs/envelopes per track
- Extensive modulation matrix
- Ability to use tracks as sends

_"Raspberry Pi" is a trademark of Raspberry Pi Ltd. "Ableton" and "Ableton Push" are trademarks of Ableton AG. "Elektron" is a trademark of Elektron Music Machines MAV AB. All trademarks used with permission. Nothing on this page is intended to imply any association with the aforementioned trademark holders._

[kinga]: https://soundcloud.com/kingajanicka
[surge]: https://surge-synthesizer.github.io/
[ffont]: http://www.github.com/ffont
[pysha]: https://github.com/ffont/pysha
[osc_wiki]: https://en.wikipedia.org/wiki/Open_Sound_Control
[overwitch]: https://github.com/dagargo/overwitch
[rpi5]: https://www.raspberrypi.com/products/raspberry-pi-5/
