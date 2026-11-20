#!/bin/bash
#
# diagnose.sh: run diagnostics on a Pushpin Pi built in diagnostics mode.
# Runs on your computer (macOS or Linux), not on the Pi.
#
#   diagnose.sh keygen          create the diagnostics key pair (once)
#   diagnose.sh check           test the SSH connection
#   diagnose.sh summary         print pushpin-diag's OK/WARN/FAIL summary
#   diagnose.sh report          save a full pushpin-diag report to
#                               diagnostics-output/ and print its summary
#   diagnose.sh run CMD...      run one command on the Pi as pushpin
#   diagnose.sh forget          drop the Pi's saved host key (after a re-burn)
#
# Environment:
#   PUSHPIN_HOST      Pi address (default pushpin.local)
#   PUSHPIN_DIAG_KEY  private key (default ~/.ssh/pushpin_diag)
#
# Logs in with the key only (BatchMode), never a password. Host keys are kept
# in their own file, ~/.ssh/pushpin_known_hosts, and the first connection to a
# new Pi is accepted; a changed key is refused. Every burn makes new host keys,
# so run "forget" after flashing a new image.

set -u

HOST="${PUSHPIN_HOST:-pushpin.local}"
KEY="${PUSHPIN_DIAG_KEY:-$HOME/.ssh/pushpin_diag}"
KNOWN_HOSTS="$HOME/.ssh/pushpin_known_hosts"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT_DIR="$REPO_ROOT/diagnostics-output"

die() { echo "diagnose.sh: $*" >&2; exit 1; }

# IPv4 by default (PUSHPIN_SSH_FAMILY=any to allow IPv6): pushpin.local also
# resolves to the Pi's IPv6 addresses, which on some home networks give
# "No route to host" from the Mac even though IPv4 works.
pi() {
    [ -f "$KEY" ] || die "no key at $KEY (run: $0 keygen, then build the image with PUSHPIN_DIAG_PUBKEY=$KEY.pub)"
    ssh -i "$KEY" \
        -o IdentitiesOnly=yes \
        -o BatchMode=yes \
        -o ConnectTimeout=10 \
        -o AddressFamily="${PUSHPIN_SSH_FAMILY:-inet}" \
        -o StrictHostKeyChecking=accept-new \
        -o UserKnownHostsFile="$KNOWN_HOSTS" \
        "pushpin@$HOST" "$@"
}

cmd="${1:-report}"
[ $# -gt 0 ] && shift

case "$cmd" in
    keygen)
        [ -f "$KEY" ] && die "$KEY already exists; not overwriting"
        mkdir -p "$(dirname "$KEY")" && chmod 700 "$(dirname "$KEY")"
        # No passphrase, so diagnostics can run unattended. The key only opens
        # diagnostics-mode images, as the unprivileged pushpin user.
        ssh-keygen -q -t ed25519 -N "" -C "pushpin-diagnostics" -f "$KEY" || die "ssh-keygen failed"
        echo "Created $KEY"
        echo "Build the image with: PUSHPIN_DIAG_PUBKEY=$KEY.pub bash create-image-with-backports.sh"
        ;;
    check)
        pi 'echo "connected to $(hostname) as $(id -un)"; command -v pushpin-diag >/dev/null || echo "pushpin-diag is not installed"; cat /etc/pushpin-diagnostics 2>/dev/null || echo "not a diagnostics image"'
        ;;
    summary)
        pi pushpin-diag --summary
        ;;
    report)
        mkdir -p "$OUT_DIR"
        out="$OUT_DIR/${HOST%%.*}-$(date +%Y%m%d-%H%M%S).txt"
        pi pushpin-diag "$@" > "$out" || die "pushpin-diag failed; partial output in $out"
        sed -n '/===== SUMMARY =====/,/^$/p' "$out" | sed '/^$/d'
        echo
        echo "Full report: $out"
        ;;
    run)
        [ $# -gt 0 ] || die "usage: $0 run CMD..."
        pi "$@"
        ;;
    forget)
        ssh-keygen -R "$HOST" -f "$KNOWN_HOSTS" >/dev/null 2>&1
        echo "Forgot host key for $HOST"
        ;;
    -h|--help|help)
        sed -n '3,21p' "$0"
        ;;
    *)
        die "unknown command: $cmd (try: $0 help)"
        ;;
esac
