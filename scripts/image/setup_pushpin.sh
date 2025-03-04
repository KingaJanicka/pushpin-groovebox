# Log file path
LOG_FILE_PATH="/var/log/sdm_image_setup.log"

# Installation paths

USER_NAME="ladmin"
USER_HOME_PATH="/home/${USER_NAME}"
INSTALL_PATH="${USER_HOME_PATH}/s/music_devices"
PUSHPIN_SOURCE_PATH="${INSTALL_PATH}"
OVERWITCH_SOURCE_PATH="${INSTALL_PATH}/interop_services"
PYTHON_ENVIRONMENT_PATH="${INSTALL_PATH}/environments"
PIPEWIRE_CONFIGURATION_PATH="${USER_HOME_PATH}/.config/pipewire/pipewire.conf.d"
OVERWITCH_FOLDER_NAME="overwitch"

# Start logging
exec > >(tee -a "$LOG_FILE_PATH") 2>&1

echo "---------------------------------------------"
echo "Script started at: $(date)"
echo "---------------------------------------------"

echo "Setting up folder structure"
mkdir -p "$PUSHPIN_SOURCE_PATH" "$OVERWITCH_SOURCE_PATH" "$PYTHON_ENVIRONMENT_PATH" "$PUSHPIN_SOURCE_PATH" "$PIPEWIRE_CONFIGURATION_PATH"

apt update

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
autoreconf --install
./configure  CLI_ONLY=yes
make
make install
ldconfig

cat > /etc/sdm/0piboot/010-update-overwitch-udev.sh <<EOF
#!/bin/bash
# This script runs as root during the first boot of the system
cd $OVERWITCH_SOURCE_PATH/$OVERWITCH_FOLDER_NAME/udev
make install
EOF

# Change ownership of Overwitch installed files to ladmin
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
git clone https://github.com/kingajanicka/pushpin-groovebox $PUSHPIN_SOURCE_PATH/pushpin-groovebox
ln -s $PUSHPIN_SOURCE_PATH/pushpin-groovebox/pushpin_groovebox.conf $PIPEWIRE_CONFIGURATION_PATH/pushpin_groovebox.conf

echo "Installing Pushpin deps"
python -m venv $PYTHON_ENVIRONMENT_PATH/venv_pushpin_groovebox

. $PYTHON_ENVIRONMENT_PATH/venv_pushpin_groovebox/bin/activate
cd $PUSHPIN_SOURCE_PATH/pushpin-groovebox

pip install -r requirements.txt
pip install ratelimit
pip install pytest
pip install pytest-asyncio

chown -R $USER_NAME:audio $USER_HOME_PATH 
chmod -R 755 $USER_HOME_PATH

# Add or update audio settings
update_limits_conf() {
    local file=$1
    local match=$2
    local replace=$3

    # If the match exists, replace it; otherwise, append the replacement
    if grep -q "^${match}" "$file"; then
        sed -i "s|^${match}.*|${replace}|g" "$file"
    else
        echo "$replace" >> "$file"
    fi
}

update_limits_conf "$LIMITS_CONF_FILE" "@audio - rtprio" "@audio - rtprio 95"
update_limits_conf "$LIMITS_CONF_FILE" "@audio - memlock" "@audio - memlock unlimited"

echo "Configuration of /etc/security/limits.conf completed."


echo "Creating startup file"
cat <<EOF >> $USER_HOME_PATH/start_pushpin.sh
#!/bin/bash
# Path to your virtual environment
VENV_PATH="$PYTHON_ENVIRONMENT_PATH/venv_pushpin_groovebox"
PUSHPIN_PATH="$INSTALL_PATH/pushpin-groovebox"

# Activate the virtual environment
if [ -f "$PYTHON_ENVIRONMENT_PATH/venv_pushpin_groovebox/bin/activate" ]; then
    source "$PYTHON_ENVIRONMENT_PATH/venv_pushpin_groovebox/bin/activate"
    echo "Virtual environment activated: $(which python)"
else
    echo "Error: Virtual environment not found at $PYTHON_ENVIRONMENT_PATH/venv_pushpin_groovebox"
    exit 1
fi

# Run Python commands or scripts within the virtual environment
python --version
cd "$INSTALL_PATH/pushpin-groovebox"
./run.sh

EOF

chown $USER_NAME:audio $USER_HOME_PATH/start_pushpin.sh
chmod +x $USER_HOME_PATH/start_pushpin.sh

echo "---------------------------------------------"
echo "Script completed at: $(date)"
echo "---------------------------------------------"

echo "DONE"