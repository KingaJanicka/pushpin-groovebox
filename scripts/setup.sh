#!/bin/bash

echo "Upgrading Pipewire"
echo "deb http://deb.debian.org/debian bookworm-backports main contrib non-free" >> /etc/apt/sources.list
apt update
apt install -y pipewire/bookworm-backports pipewire-pulse/bookworm-backports pipewire-alsa/bookworm-backports libpipewire-0.3-modules/bookworm-backports pipewire-bin/bookworm-backports pipewire-jack/bookworm-backports wireplumber/bookworm-backports

echo "Adding initial packages"
apt install -y libasound2-dev python3-brlapi git libcairo2-dev python3-dev raspberrypi-ui-mods automake libtool libusb-dev libjack-jackd2-dev libsamplerate0-dev libsndfile1-dev autopoint gettext libjson-glib-dev libgtk-4-dev libsystemd-dev

echo "Adding Push2 support"
curl -o /etc/udev/rules.d/99-ableton-push2.rules https://raw.githubusercontent.com/Ardour/ardour/master/tools/udev/50-ableton-push2.rules

echo "Installing Surge-XT"
echo 'deb http://download.opensuse.org/repositories/home:/surge-synth-team/Raspbian_12/ /' | sudo tee /etc/apt/sources.list.d/home:surge-synth-team.list
curl -fsSL https://download.opensuse.org/repositories/home:surge-synth-team/Raspbian_12/Release.key | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/home_surge-synth-team.gpg > /dev/null
apt update
apt install surge-xt-nightly -y

echo "Building Overwitch"
curl -L https://github.com/dagargo/overwitch/archive/refs/tags/1.2.zip > overwitch.zip
unzip overwitch.zip
cd overwitch-1.2
autoreconf --install
./configure
make
sudo make install
sudo ldconfig
cd udev
make install
cd ..
cd ..

echo "Installing Pushpin"
git clone https://github.com/kingajanicka/pushpin-groovebox /pushpin
chown -R pushpin /pushpin

echo "Installing Pushpin deps"

# pip install -r /pushpin/requirements.txt

echo "DONE"