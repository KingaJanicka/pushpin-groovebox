# Log file path
LOG_FILE_PATH="/var/log/sdm_image_setup.log"

exec > >(tee -a "$LOG_FILE_PATH") 2>&1

echo "---------------------------------------------"
echo "Script started at: $(date)"
echo "---------------------------------------------"

echo "Configuring /boot/firmware/config.txt for HiFiBerry DAC8x"

CONFIG_FILE="/boot/firmware/config.txt"

# Function to safely comment or replace lines in the file
update_config_file() {
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

# Ensure the file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: $CONFIG_FILE does not exist. Exiting."
    exit 1
fi

# Remove or disable onboard audio
sed -i '/^dtparam=audio=on/d' "$CONFIG_FILE"
update_config_file "$CONFIG_FILE" "dtoverlay=vc4-kms-v3d" "dtoverlay=vc4-kms-v3d,noaudio"

# Add HiFiBerry DAC8x overlay
update_config_file "$CONFIG_FILE" "dtoverlay=hifiberry-dac8x" "dtoverlay=hifiberry-dac8x"

echo "Configuration of /boot/firmware/config.txt completed."

echo "---------------------------------------------"
echo "Script ended at: $(date)"
echo "---------------------------------------------"