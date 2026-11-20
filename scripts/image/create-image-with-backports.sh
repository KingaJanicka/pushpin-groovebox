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

IMAGE="${IMAGE:-pushpin_dev.img}"
# service dbus start

if ! test -f $IMAGE; then
  curl -o $IMAGE.xz https://downloads.raspberrypi.com/raspios_lite_arm64/images/raspios_lite_arm64-2024-11-19/2024-11-19-raspios-bookworm-arm64-lite.img.xz
  xz -d $IMAGE.xz
fi

[ "$(type -t sdm)" == "" ] && errexit "? sdm is not installed"

assets="."

[ -f $assets/my.plugins ] &&  mv $assets/my.plugins $assets/my.plugins.1

# Which pushpin-groovebox ref goes into the image:
#   PUSHPIN_REF if set explicitly, else the tag being released in CI
#   (GITHUB_REF_NAME), else dev for a local dev image.
PUSHPIN_REF="${PUSHPIN_REF:-${GITHUB_REF_NAME:-dev}}"
PUSHPIN_REPO="${PUSHPIN_REPO:-https://github.com/kingajanicka/pushpin-groovebox}"
echo "Building $IMAGE from $PUSHPIN_REPO @ $PUSHPIN_REF"

# Diagnostics mode (opt-in, never used by the release workflow): set
# PUSHPIN_DIAG_PUBKEY to an SSH *public* key file and the image will
# authorize it for the pushpin user, call itself pushpin.local and let pushpin
# read the system journal. See scripts/diagnostics/README.md.
PUSHPIN_DIAG_PUBKEY_TEXT=""
if [ -n "${PUSHPIN_DIAG_PUBKEY:-}" ]; then
  [ -f "$PUSHPIN_DIAG_PUBKEY" ] || errexit "? PUSHPIN_DIAG_PUBKEY: no such file: $PUSHPIN_DIAG_PUBKEY"
  grep -q "PRIVATE KEY" "$PUSHPIN_DIAG_PUBKEY" && errexit "? PUSHPIN_DIAG_PUBKEY is a private key; pass the .pub file"
  PUSHPIN_DIAG_PUBKEY_TEXT="$(head -n 1 "$PUSHPIN_DIAG_PUBKEY")"
  [[ "$PUSHPIN_DIAG_PUBKEY_TEXT" =~ ^(ssh-ed25519|ssh-rsa|ecdsa-sha2-[a-z0-9]+|sk-[a-z0-9@.-]+)\ [A-Za-z0-9+/=]+ ]] \
    || errexit "? PUSHPIN_DIAG_PUBKEY doesn't look like an SSH public key"
  echo "Diagnostics mode: authorizing $(cut -d' ' -f1,3- <<< "$PUSHPIN_DIAG_PUBKEY_TEXT")"
fi

# sdm runs the setup script in a clean environment, so bake the ref into a
# generated copy of it instead of relying on exported variables.
mkdir -p "${PWD}/.build"
script_path="${PWD}/.build/setup_pushpin_image.sh"
{
  echo "#!/bin/bash"
  printf 'PUSHPIN_REF=%q\n' "$PUSHPIN_REF"
  printf 'PUSHPIN_REPO=%q\n' "$PUSHPIN_REPO"
  printf 'PUSHPIN_DIAG_PUBKEY_TEXT=%q\n' "$PUSHPIN_DIAG_PUBKEY_TEXT"
  tail -n +2 "${PWD}/setup_full_with_backports.sh"
} > "$script_path"
chmod +x "$script_path"

(cat <<EOF
# Plugin List generated $(date +"%Y-%m-%d %H:%M:%S")

# Delete user pi if it exists
# https://github.com/gitbls/sdm/blob/master/Docs/Plugins.md#user
user:deluser=pi

# Add a new user
# https://github.com/gitbls/sdm/blob/master/Docs/Plugins.md#user
user:adduser=pushpin|password=pushpin|addgroup=audio

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
raspiconfig:boot_behavior=B2

# Configure localization settings to the same as this system
# https://github.com/gitbls/sdm/blob/master/Docs/Plugins.md#l10n
L10n:host

# Run config script
runscript:script=$script_path

EOF
    ) | bash -c "cat >|$assets/my.plugins"
echo $assets/my.plugins

$sudo sdm --customize --autologin --plugin @$assets/my.plugins --extend --xmb 4096 --bootscripts --restart --regen-ssh-host-keys $IMAGE
