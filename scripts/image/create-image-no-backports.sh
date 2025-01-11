#!/bin/bash

#
# Simple script to use sdm with plugins
# Edit the text inside the EOF/EOF as appropriate for your configuration
# ** Suggestion: Copy this file to somewhere in your path and edit your copy
#    (~/bin is a good location)
#

function errexit() {
    echo -e "$1"
    exit 1
}

[ $EUID -eq 0 ] && sudo="" || sudo="sudo"

IMAGE="2024-11-19-raspios-bookworm-arm64-lite.img"

# service dbus start

if ! test -f $IMAGE; then
  curl -O https://downloads.raspberrypi.com/raspios_lite_arm64/images/raspios_lite_arm64-2024-11-19/2024-11-19-raspios-bookworm-arm64-lite.img.xz
  xz -d $IMAGE.xz
fi

[ "$(type -t sdm)" == "" ] && errexit "? sdm is not installed"

assets="."

[ -f $assets/my.plugins ] &&  mv $assets/my.plugins $assets/my.plugins.1

(cat <<EOF
# Plugin List generated $(date +"%Y-%m-%d %H:%M:%S")

# Delete user pi if it exists
# https://github.com/gitbls/sdm/blob/master/Docs/Plugins.md#user
user:deluser=pi

# Add a new user
# https://github.com/gitbls/sdm/blob/master/Docs/Plugins.md#user
user:adduser=ladmin|password=Numark234|addgroup=audio

# Install btwifiset (Control Pi's WiFi from your phone)
# https://github.com/gitbls/sdm/blob/master/Docs/Plugins.md#btwifiset
# btwifiset:country=GB|timeout=30

# Install apps
# https://github.com/gitbls/sdm/blob/master/Docs/Plugins.md#apps
apps:name=pipewire-jack|apps=pipewire-jack
apps:name=ui-development|apps=python3-brlapi raspberrypi-ui-mods libjson-glib-dev libgtk-4-dev 
apps:name=libusb-dev|apps=libusb-dev libsystemd-dev
apps:name=autopoint-gettext|apps=autopoint gettext
apps:name=libasound2-dev|apps=libasound2-dev libjack-dev libsamplerate0-dev libsndfile1-dev
apps:name=python3-dev|apps=python3-dev libcairo2-dev
apps:name=git-automake-libtool|apps=git automake libtool
apps:name=overwitch-dependencies|apps=libusb-1.0-0-dev,qpwgraph

# Configure network
# https://github.com/gitbls/sdm/blob/master/Docs/Plugins.md#network
# network:ctype=wifi|wifi-ssid=ONTOLEDGY_WIFI|wifi-password=PAKI4200|wificountry=GB|autoconnect=true

# This configuration eliminates the need for piwiz so disable it
disables:piwiz

# Uncomment to enable trim on all disks
# https://github.com/gitbls/sdm/blob/master/Docs/Plugins.md#trim-enable
trim-enable

# Enable X11
# https://github.com/gitbls/sdm/blob/master/Docs/Plugins.md#graphics
# graphics:graphics=wayland

# Set Boot to console.
raspiconfig:boot_behavior=B1

# Configure localization settings to the same as this system
# https://github.com/gitbls/sdm/blob/master/Docs/Plugins.md#l10n
L10n:host

# Run config script
#runscript:script=$PWD/setup_pushpin.sh
#runscript:script=$PWD/setup_hifi_berry.sh
runscript:script=$PWD/setup_full_no_backports.sh

EOF
    ) | bash -c "cat >|$assets/my.plugins"
echo $assets/my.plugins

$sudo sdm --customize --plugin @$assets/my.plugins --extend --xmb 4096 --bootscripts --restart --regen-ssh-host-keys  $IMAGE
