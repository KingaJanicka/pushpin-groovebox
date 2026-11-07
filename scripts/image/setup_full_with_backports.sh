#!/bin/bash

SSID="<SSID>"
PSK="<PSK>"

# Log file path
LOG_FILE_PATH="/var/log/sdm_image_setup.log"

# Installation paths

USER_NAME="pushpin"
echo USER_NAME=$USER_NAME
USER_HOME_PATH="/home/${USER_NAME}"
echo USER_HOME_PATH=$USER_HOME_PATH
INSTALL_PATH="${USER_HOME_PATH}/s/music_devices"
echo INSTALL_PATH=$INSTALL_PATH
PUSHPIN_SOURCE_PATH="${INSTALL_PATH}"
echo PUSHPIN_SOURCE_PATH=$PUSHPIN_SOURCE_PATH
OVERWITCH_SOURCE_PATH="${INSTALL_PATH}/interop_services"
echo OVERWITCH_SOURCE_PATH=$OVERWITCH_SOURCE_PATH
PYTHON_ENVIRONMENT_PATH="${INSTALL_PATH}/environments"
echo PYTHON_ENVIRONMENT_PATH=$PYTHON_ENVIRONMENT_PATH
PIPEWIRE_CONFIGURATION_PATH="${USER_HOME_PATH}/.config/pipewire/pipewire.conf.d"
echo PIPEWIRE_CONFIGURATION_PATH=$PIPEWIRE_CONFIGURATION_PATH
OVERWITCH_FOLDER_NAME="overwitch"
echo OVERWITCH_FOLDER_NAME=$OVERWITCH_FOLDER_NAME

# Git ref (tag or branch) of pushpin-groovebox to install. create-image-with-backports.sh
# prepends PUSHPIN_REF/PUSHPIN_REPO to a generated copy of this script, because sdm
# runs it in a clean environment where the caller's variables are not visible.
PUSHPIN_REPO="${PUSHPIN_REPO:-https://github.com/kingajanicka/pushpin-groovebox}"
PUSHPIN_REF="${PUSHPIN_REF:-dev}"
echo PUSHPIN_REPO=$PUSHPIN_REPO
echo PUSHPIN_REF=$PUSHPIN_REF


# Start logging
exec > >(tee -a "$LOG_FILE_PATH") 2>&1

echo "---------------------------------------------"
echo "Script started at: $(date)"
echo "---------------------------------------------"

echo "Setting up folder structure"
mkdir -p "$PUSHPIN_SOURCE_PATH" "$OVERWITCH_SOURCE_PATH" "$PYTHON_ENVIRONMENT_PATH" "$PUSHPIN_SOURCE_PATH" "$PIPEWIRE_CONFIGURATION_PATH"

echo "Upgrading Pipewire"
echo "deb http://deb.debian.org/debian bookworm-backports main contrib non-free" >> /etc/apt/sources.list

apt update

echo "Adding Bookworm backports"
apt install -y pipewire/bookworm-backports pipewire-pulse/bookworm-backports pipewire-alsa/bookworm-backports libpipewire-0.3-modules/bookworm-backports pipewire-bin/bookworm-backports pipewire-jack/bookworm-backports wireplumber/bookworm-backports

echo "Adding initial packages"
# No desktop on this Lite image: raspberrypi-ui-mods pulled in lightdm and a
# full desktop, which fights the console auto-login on tty1, and nothing needs
# libgtk-4-dev (Overwitch is built CLI_ONLY, so its GTK 4 GUI isn't built).
# Overwitch needs json-glib (device file), and overwitch-service also needs
# libsystemd and glib-2.0.
apt install -y python3-brlapi libjson-glib-dev libglib2.0-dev
apt install -y libusb-dev libsystemd-dev
# Session D-Bus for the lingering pushpin user manager (overwitch-service needs it)
apt install -y dbus-user-session
apt install -y autopoint gettext
apt install -y libasound2-dev libjack-dev libsamplerate0-dev libsndfile1-dev
apt install -y python3-dev python3-venv libcairo2-dev
apt install -y git automake libtool

# For Overwitch 
apt install -y libusb-1.0-0-dev
apt install -y qpwgraph

echo "Adding Push2 support"
curl -o /etc/udev/rules.d/99-ableton-push2.rules https://raw.githubusercontent.com/Ardour/ardour/master/tools/udev/50-ableton-push2.rules

echo "Installing Surge-XT"
echo 'deb http://download.opensuse.org/repositories/home:/surge-synth-team/Raspbian_12/ /' | sudo tee /etc/apt/sources.list.d/home:surge-synth-team.list
curl -fsSL https://download.opensuse.org/repositories/home:surge-synth-team/Raspbian_12/Release.key | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/home_surge-synth-team.gpg > /dev/null
apt update
apt install surge-xt-nightly -y

echo "Building Overwitch"
cd $OVERWITCH_SOURCE_PATH
# 2.0+ is needed: the app looks for the "overwitch-service" client, which older
# releases don't build. The service's systemd user unit is written further down
# (see "Installing Overwitch systemd user service").
OVERWITCH_VERSION="2.2"
git clone --branch "$OVERWITCH_VERSION" https://github.com/dagargo/overwitch \
    || { echo "ERROR: could not clone Overwitch $OVERWITCH_VERSION"; exit 1; }
cd $OVERWITCH_FOLDER_NAME
autoreconf --install
./configure  CLI_ONLY=yes
make
make install
ldconfig
cd udev
make install

echo "Installing PureData"
apt install puredata -y

cat > /etc/sdm/0piboot/010-update-overwitch-udev.sh <<EOF
#!/bin/bash
# This script runs as root during the first boot of the system
cd $OVERWITCH_SOURCE_PATH/$OVERWITCH_FOLDER_NAME/udev
make install
EOF

# Change ownership of Overwitch installed files to pushpin
OVERWITCH_INSTALL_PATHS=(
    "/usr/local/share/overwitch"
    "/usr/local/bin/overwitch-record"
    "/usr/local/bin/overwitch-play"
    "/usr/local/bin/overwitch-cli"
    "/usr/local/bin/overwitch-service"
    "/usr/local/include/overwitch.h"
    "/usr/local/lib/liboverwitch.*"
)

echo "Changing ownership of Overwitch files to $USER_NAME"
for path in "${OVERWITCH_INSTALL_PATHS[@]}"; do
    if [ -e $path ]; then
        chown -R "$USER_NAME:audio" "$path"
    else
        echo "Warning: Path $path does not exist"
    fi
done



# The Overwitch udev rules are (re)installed once by the sdm first-boot script
# above. They used to be reinstalled from /etc/rc.local on EVERY boot, which
# held up the tty1 getty (it waits for rc-local) and re-triggered every udev
# device, the Push 2 included.

echo "Installing Pushpin"
cd $PUSHPIN_SOURCE_PATH
git clone --branch "$PUSHPIN_REF" "$PUSHPIN_REPO" "$PUSHPIN_SOURCE_PATH/pushpin-groovebox" \
    || { echo "ERROR: could not clone $PUSHPIN_REPO at $PUSHPIN_REF"; exit 1; }

ln -s $PUSHPIN_SOURCE_PATH/pushpin-groovebox/pushpin_groovebox.conf $PIPEWIRE_CONFIGURATION_PATH/pushpin_groovebox.conf

echo "Installing Pushpin deps"
python3 -m venv $PYTHON_ENVIRONMENT_PATH/venv_pushpin_groovebox

. $PYTHON_ENVIRONMENT_PATH/venv_pushpin_groovebox/bin/activate
cd $PUSHPIN_SOURCE_PATH/pushpin-groovebox

pip install -r requirements.txt
pip install ratelimit
pip install pytest
pip install pytest-asyncio

echo "Installing pushpin-diag"
# Read-only health report; on every image, diagnostics mode or not.
DIAG_SCRIPT="$PUSHPIN_SOURCE_PATH/pushpin-groovebox/scripts/diagnostics/pushpin-diag.sh"
if [ -f "$DIAG_SCRIPT" ]; then
    install -m 755 "$DIAG_SCRIPT" /usr/local/bin/pushpin-diag
else
    echo "Warning: $DIAG_SCRIPT not in $PUSHPIN_REF; pushpin-diag not installed"
fi

PUSHPIN_DIAG_PUBKEY_TEXT="${PUSHPIN_DIAG_PUBKEY_TEXT:-}"
if [ -n "$PUSHPIN_DIAG_PUBKEY_TEXT" ]; then
    echo "Enabling diagnostics mode"
    # Key-based SSH for the pushpin user, so diagnostics can run unattended.
    mkdir -p "$USER_HOME_PATH/.ssh"
    touch "$USER_HOME_PATH/.ssh/authorized_keys"
    grep -qxF "$PUSHPIN_DIAG_PUBKEY_TEXT" "$USER_HOME_PATH/.ssh/authorized_keys" \
        || echo "$PUSHPIN_DIAG_PUBKEY_TEXT" >> "$USER_HOME_PATH/.ssh/authorized_keys"
    chmod 700 "$USER_HOME_PATH/.ssh"
    chmod 600 "$USER_HOME_PATH/.ssh/authorized_keys"
    systemctl enable ssh

    # Reachable as pushpin.local (Raspberry Pi Imager's own hostname setting,
    # if used when flashing, overrides this).
    apt install -y avahi-daemon
    echo pushpin > /etc/hostname
    sed -i 's/^127\.0\.1\.1.*/127.0.1.1\tpushpin/' /etc/hosts
    grep -q '^127\.0\.1\.1' /etc/hosts || printf '127.0.1.1\tpushpin\n' >> /etc/hosts

    # Read the system journal and kernel log without sudo.
    usermod -aG adm,systemd-journal "$USER_NAME"

    echo "Diagnostics image, built $(date -Is) from $PUSHPIN_REF" > /etc/pushpin-diagnostics
fi



# echo "Configuring /boot/firmware/config.txt for HiFiBerry DAC8x"

# CONFIG_FILE="/boot/firmware/config.txt"

# # Function to safely comment or replace lines in the file
# update_config_file() {
#     local file=$1
#     local match=$2
#     local replace=$3

#     # If the match exists, replace it; otherwise, append the replacement
#     if grep -q "^${match}" "$file"; then
#         sed -i "s|^${match}.*|${replace}|g" "$file"
#     else
#         echo "$replace" >> "$file"
#     fi
# }

# # Ensure the file exists
# if [ ! -f "$CONFIG_FILE" ]; then
#     echo "Error: $CONFIG_FILE does not exist. Exiting."
#     exit 1
# fi

# # Remove or disable onboard audio
# sed -i '/^dtparam=audio=on/d' "$CONFIG_FILE"
# update_config_file "$CONFIG_FILE" "dtoverlay=vc4-kms-v3d" "dtoverlay=vc4-kms-v3d,noaudio"

# # Add HiFiBerry DAC8x overlay
# update_config_file "$CONFIG_FILE" "dtoverlay=hifiberry-dac8x" "dtoverlay=hifiberry-dac8x"

# echo "Configuration of /boot/firmware/config.txt completed."


echo "Creating startup file"
# Overwrite (not append) so re-running this script leaves one valid script.
cat <<EOF > $USER_HOME_PATH/start_pushpin.sh
#!/bin/bash
# Started by the pushpin.service systemd user unit. Run it by hand only after
# "systemctl --user stop pushpin", or two copies will fight over the Push 2
# and OSC ports 1030-1047.
VENV_PATH="$PYTHON_ENVIRONMENT_PATH/venv_pushpin_groovebox"
PUSHPIN_PATH="$INSTALL_PATH/pushpin-groovebox"

# Activate the virtual environment
if [ -f "\${VENV_PATH}/bin/activate" ]; then
    source "\${VENV_PATH}/bin/activate"
    echo "Virtual environment activated: \$(which python)"
else
    echo "Error: Virtual environment not found at \${VENV_PATH}"
    exit 1
fi

python --version
cd "\${PUSHPIN_PATH}"
# Through bash, so a checkout without the executable bit on run.sh still starts.
exec /bin/bash ./run.sh
EOF
chmod 755 $USER_HOME_PATH/start_pushpin.sh

echo "Installing Overwitch systemd user service"
# Written here instead of installing upstream's overwitch/systemd unit:
# - upstream uses Type=notify-reload, which needs systemd 253+; Bookworm has 252
#   (plain notify + ExecReload does the same job: SIGHUP reloads the config)
# - it has to run through pw-jack to reach PipeWire's JACK API
# The app finds Overwitch through PipeWire at startup, so pushpin.service is
# ordered after this one. overwitch-service is a D-Bus service, which is why
# dbus-user-session is installed above.
SYSTEMD_USER_PATH="$USER_HOME_PATH/.config/systemd/user"
mkdir -p "$SYSTEMD_USER_PATH/default.target.wants"
cat <<EOF > "$SYSTEMD_USER_PATH/overwitch.service"
[Unit]
Description=Overwitch service (Elektron Overbridge audio)
Requires=pipewire.service
After=pipewire.service wireplumber.service

[Service]
Type=notify
# "all", in case pw-jack forks instead of exec'ing overwitch-service.
NotifyAccess=all
ExecStart=/usr/bin/pw-jack /usr/local/bin/overwitch-service
ExecReload=/bin/kill -HUP \$MAINPID
Restart=on-failure

[Install]
WantedBy=default.target
EOF
ln -sf ../overwitch.service "$SYSTEMD_USER_PATH/default.target.wants/overwitch.service"

echo "Installing pushpin systemd user service"
# Exactly one copy of the app, started at boot by the pushpin user's systemd
# manager. Previously .profile ran start_pushpin.sh, so every login shell
# (the tty1 auto-login AND each SSH session) started its own copy.
cat <<EOF > "$SYSTEMD_USER_PATH/pushpin.service"
[Unit]
Description=Pushpin groovebox
# Wants, not Requires: the app still runs if Overwitch fails to start.
Wants=pipewire.service wireplumber.service overwitch.service
After=pipewire.service wireplumber.service overwitch.service

[Service]
Type=simple
# Without this Python buffers print() output and the journal stays empty.
Environment=PYTHONUNBUFFERED=1
ExecStart=$USER_HOME_PATH/start_pushpin.sh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF
# Equivalent of "systemctl --user enable pushpin.service", which can't run as
# root inside the sdm build container.
ln -sf ../pushpin.service "$SYSTEMD_USER_PATH/default.target.wants/pushpin.service"

# Equivalent of "loginctl enable-linger pushpin": start the user manager (and so
# pipewire and pushpin.service) at boot without waiting for a login.
mkdir -p /var/lib/systemd/linger
touch /var/lib/systemd/linger/$USER_NAME

# Make sure no older autostart hook is left in .profile.
[ -f $USER_HOME_PATH/.profile ] && sed -i '/start_pushpin\.sh/d' $USER_HOME_PATH/.profile

# Everything under the home folder was created by root; hand it to the user.
# Ownership only: a blanket chmod -R 755 made every file executable and
# opened private files (e.g. ~/.ssh) to other users.
chown -R $USER_NAME:audio $USER_HOME_PATH

echo "---------------------------------------------"
echo "Script completed at: $(date)"
echo "---------------------------------------------"

echo "DONE"
