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
apt install -y python3-brlapi raspberrypi-ui-mods libjson-glib-dev libgtk-4-dev 
apt install -y libusb-dev libsystemd-dev
apt install -y autopoint gettext
apt install -y libasound2-dev libjack-dev libsamplerate0-dev libsndfile1-dev
apt install -y python3-dev libcairo2-dev
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
git clone https://github.com/dagargo/overwitch
cd $OVERWITCH_FOLDER_NAME
git checkout 7e4743a
autoreconf --install
./configure  CLI_ONLY=yes
make
make install
ldconfig
cd udev
make install
cd $OVERWITCH_SOURCE_PATH/systemd
make install
systemctl --user enable overwitch.service
# We need to run it through pw-jack so update service with correct invocation
sed -i "s/overwitch-service/pw-jack overwitch-service/" /etc/systemd/user/overwitch.service



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



# Ensure /etc/rc.local exists and is executable
if [ ! -f /etc/rc.local ]; then
    echo "#!/bin/sh -e" > /etc/rc.local
    echo "exit 0" >> /etc/rc.local
fi
chmod +x /etc/rc.local

# Remove 'exit 0' from /etc/rc.local if it exists
sed -i '/^exit 0$/d' /etc/rc.local

# Append the commands
cat <<EOF >> /etc/rc.local

# Commands to install Overwitch udev rules
cd $OVERWITCH_SOURCE_PATH/$OVERWITCH_FOLDER_NAME/udev
make install

exit 0
EOF

echo "Installing Pushpin"
cd $PUSHPIN_SOURCE_PATH
git clone --branch "$PUSHPIN_REF" "$PUSHPIN_REPO" "$PUSHPIN_SOURCE_PATH/pushpin-groovebox" \
    || { echo "ERROR: could not clone $PUSHPIN_REPO at $PUSHPIN_REF"; exit 1; }

ln -s $PUSHPIN_SOURCE_PATH/pushpin-groovebox/pushpin_groovebox.conf $PIPEWIRE_CONFIGURATION_PATH/pushpin_groovebox.conf

echo "Installing Pushpin deps"
python -m venv $PYTHON_ENVIRONMENT_PATH/venv_pushpin_groovebox

. $PYTHON_ENVIRONMENT_PATH/venv_pushpin_groovebox/bin/activate
cd $PUSHPIN_SOURCE_PATH/pushpin-groovebox

pip install -r requirements.txt
pip install ratelimit
pip install pytest
pip install pytest-asyncio



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
exec ./run.sh
EOF
chmod 755 $USER_HOME_PATH/start_pushpin.sh

echo "Installing pushpin systemd user service"
# Exactly one copy of the app, started at boot by the pushpin user's systemd
# manager. Previously .profile ran start_pushpin.sh, so every login shell
# (the tty1 auto-login AND each SSH session) started its own copy.
SYSTEMD_USER_PATH="$USER_HOME_PATH/.config/systemd/user"
mkdir -p "$SYSTEMD_USER_PATH/default.target.wants"
cat <<EOF > "$SYSTEMD_USER_PATH/pushpin.service"
[Unit]
Description=Pushpin groovebox
Wants=pipewire.service wireplumber.service
After=pipewire.service wireplumber.service

[Service]
Type=simple
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
