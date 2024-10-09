---
title: "User Guide"
permalink: /user-guide
layout: home
---

> So I have this running, now what?

We've produced a few videos showing some of the things you can do with Pushpin. Please see below:

### Sound design

tktk

### Sequencing using an external MIDI device

tktk

### Routing with Overbridge

tktk

### Adding track insert effects

tktk

## For Developers

To hack on top of Pushpin, it helps to understand what it's doing upon boot because it interacts with several different subsystems.

The Pushpin Linux distribution spawns 8 duplex Pipewire interfaces, each with 16 inputs and outputs. These are loaded on boot using the Pipewire config located in `/home/pushpin/.config/pipewire/pipewire.conf.d/pushpin_groovebox.conf` (which is also a good place to put any bespoke Pipewire changes). Another duplex for controlling instrument volumes is also initialised as `pushpin-volumes`. The `pushpin-n` duplex devices are dynamically connected to using the `audio-in` device in Pushpin and are used to manage track audio inputs, enabling complex routing.

Once the system has booted, it logs into the user `pushpin` (default password: `groovebox`) and runs `/usr/bin/pushpin`, which is ultimately an alias for `/pushpin/run.sh`. This starts Python running `/pushpin/app.py`, the main entry point for the codebase.

Pushpin starts by instantiating eight instances of `surge-xt-cli`, the command-line version of the Surge XT softsynth. It waits for these to load and then spawns `overwitch`, an open source Overbridge client, and waits for it to load.

It then disconnects the Surge instances from the default audio device and connects them to `pushpin-volumes`.

Please see app.py for a full sense of what Pushpin initialisation looks like. Also, try running `qpwgraph` in Wayland to see how the connection pathways work.
