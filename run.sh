#!/bin/sh
# exec so systemd stops/signals reach python directly, not a wrapper shell.
PIPEWIRE_PROPS='{ node.group = "pro-audio-4" }' exec python app.py
