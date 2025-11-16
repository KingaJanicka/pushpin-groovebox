---
title: "Getting started"
permalink: /getting-started
layout: home
---

To use Pushpin, you need the following things:

- A Raspberry Pi 5
- An Ableton Push 2
- An [audio interface](https://thepihut.com/products/iqaudio-dac) of some variety
- A way to burn disk images to SD card

## 1. Download Pushpin image

Please see [pushpin-images.kinga.dev](https://pushpin-images.kinga.dev)

## 2. Burn to SD card

The Raspberry Pi Foundation has a good tutorial for doing this here:

https://projects.raspberrypi.org/en/projects/raspberry-pi-setting-up/2

During this process, you can also configure network settings, which you'll
need to do if you don't have a keyboard and mouse plugged into the Pi.

## 3. Plug everything in and hit power

Connect everything together; how you do this depends on what sequencer and soundcard you're using.

Insert the SD card into your Raspberry Pi 5 device and hit power; the Linux distribution will boot and
you will automatically be logged in as the user `pushpin` (default password: `pushpin`).

Power on the Ableton Push 2 device if you have not yet done so.

You should hopefully now be running Pushpin!

## 4. Configure MIDI devices

You can optionally connect a MIDI sequencer to sequence instead of using the built-in one. To select this:

1. Press the "Setup" button twice. This will bring you to the MIDI setup page.
2. Twist the first encoder to set your "in" device to your MIDI sequencer.

# Troubleshooting

This is very in-development software so usually the easiest way to resolve an issue is to update the latest version.
You can change the version of Pushpin by navigating to `/s/music_devices/pushpin_groovebox` and typing:

```
$ git stash save && git pull origin main
```

You can also use the "Update to latest version" button in **SETTINGS** on the Push 2.

To check out a different version, type:

```
$ git checkout <version>
```

Pushpin has a Wayland-based graphical user interface you can use if you're connected via a screen and keyboard.

To load it, type:

```
$ wayfire-pi
```

This includes a number of useful tools for hacking on, troubleshooting, and extending Pushpin. Chief amongst these is `qpwgraph`, which you can use to visually troubleshoot Pipewire connectivity.

_"Raspberry Pi" is a trademark of Raspberry Pi Ltd. "Ableton" and "Ableton Push" are trademarks of Ableton AG. "Elektron" is a trademark of Elektron Music Machines MAV AB. All trademarks used with permission. Nothing on this page is intended to imply any association with the aforementioned trademark holders._
