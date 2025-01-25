FROM debian:latest

RUN apt update

RUN apt install -y curl \
    xz-utils \
    sudo \
    curl \
    unzip \
    fdisk \
    dosfstools \
    rsync \
    parted \
    kpartx \
    qemu-utils \
    qemu-user-static \
    qemu-system-arm \
    qemu-efi-aarch64 \
    ipxe-qemu \
    qemu-efi-arm \
    qemu-system-gui \
    systemd-container \
    binfmt-support \
    util-linux \
    xz-utils \
    zip \
    bzip2 \
    file \
    less

RUN rm -rf /var/lib/apt/lists/*

RUN curl -LO https://raw.githubusercontent.com/aendra-rininsland/sdm/master/EZsdmInstaller | bash

WORKDIR /build

COPY ./create-img.sh /build

COPY ./setup.sh /build

ENTRYPOINT service dbus restart && bash