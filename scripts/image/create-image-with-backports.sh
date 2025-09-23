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

# service dbus start

if ! test -f $IMAGE; then
  curl -o $IMAGE.xz https://downloads.raspberrypi.com/raspios_lite_arm64/images/raspios_lite_arm64-2024-11-19/2024-11-19-raspios-bookworm-arm64-lite.img.xz
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
#apps:name=pushpindependencies|apps=libasound2-dev,libjack-dev,python3-brlapi,git,libcairo2-dev,python3-dev,raspberrypi-ui-mods

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
runscript:script=$PWD/setup_full_with_backports.sh

EOF
    ) | bash -c "cat >|$assets/my.plugins"
echo $assets/my.plugins

$sudo sdm --batch --customize --autologin --plugin @$assets/my.plugins --extend --xmb 4096 --bootscripts --restart --regen-ssh-host-keys $IMAGE
