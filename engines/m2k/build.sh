#!/bin/sh
# Builds m2k-jack (the MONO2K core as a JACK synth for pushpin) into engines/m2k/build/.
#
#   engines/m2k/build.sh                 fetch MONO2K at the pinned commit, build
#   M2K_SRC=/path/to/mono2k engines/m2k/build.sh   build against a local checkout
#
# JACK is used when pkg-config finds it (the Pi: libjack-jackd2-dev or
# pipewire-jack's headers); otherwise the binary is built for --render only.
set -eu

HERE=$(cd "$(dirname "$0")" && pwd)
M2K_REPO=https://github.com/InigoHernandez/mono2k
M2K_COMMIT=0c674124b76655d95e1bf9a9f3edb1a031930fd5
OUT="$HERE/build"

if [ -z "${M2K_SRC:-}" ]; then
    M2K_SRC="$HERE/vendor/mono2k"
    if [ "$(git -C "$M2K_SRC" rev-parse HEAD 2>/dev/null || true)" != "$M2K_COMMIT" ]; then
        echo "fetching MONO2K $M2K_COMMIT"
        rm -rf "$M2K_SRC"
        mkdir -p "$M2K_SRC"
        git -C "$M2K_SRC" init -q
        git -C "$M2K_SRC" fetch -q --depth 1 "$M2K_REPO" "$M2K_COMMIT"
        git -C "$M2K_SRC" checkout -q FETCH_HEAD
    fi
fi

# pushpin's patches (patches/*.patch) go onto a copy, so neither vendor/ nor a
# local M2K_SRC checkout is changed
mkdir -p "$OUT"
CORE="$OUT/mono2k"
rm -rf "$CORE"
mkdir -p "$CORE/firmware"
cp -R "$M2K_SRC/firmware/src" "$M2K_SRC/firmware/gen" "$CORE/firmware/"
for p in "$HERE"/patches/*.patch; do
    [ -e "$p" ] || continue
    patch -s -p1 -d "$CORE" < "$p"
    echo "applied $(basename "$p")"
done

CC=${CC:-cc}
CFLAGS="-std=gnu11 -O2 -Wall -Wno-unused-function -DM2K_TRACKS=8 -I$CORE/firmware/src -I$CORE/firmware/gen"
LIBS="-lm"

if pkg-config --exists jack 2>/dev/null; then
    CFLAGS="$CFLAGS -DM2K_WITH_JACK $(pkg-config --cflags jack)"
    LIBS="$LIBS $(pkg-config --libs jack)"
    echo "building m2k-jack with JACK"
else
    echo "building m2k-jack without JACK (render only): pkg-config found no jack"
fi

# shellcheck disable=SC2086
$CC $CFLAGS -o "$OUT/m2k-jack" "$HERE/m2k_jack.c" $LIBS
echo "built $OUT/m2k-jack"
