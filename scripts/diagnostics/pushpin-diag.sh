#!/bin/bash
#
# pushpin-diag: read-only health report for a Pushpin Raspberry Pi.
#
# Installed on every image as /usr/local/bin/pushpin-diag. Run it as the
# pushpin user (locally or over SSH); it changes nothing. Each section runs
# independently, so a missing tool or a failing command never stops the report.
#
#   pushpin-diag              full report
#   pushpin-diag --summary    just the one-line checks at the top
#   pushpin-diag --lines N    log lines per log section (default 150)
#
# The SUMMARY block is meant to be read first: every line is "OK", "WARN" or
# "FAIL" followed by what was checked, so problems are easy to grep for.

LINES_PER_LOG=150
SUMMARY_ONLY=0
while [ $# -gt 0 ]; do
    case "$1" in
        --summary) SUMMARY_ONLY=1 ;;
        --lines) shift; LINES_PER_LOG="${1:-150}" ;;
        -h|--help) sed -n '3,15p' "$0"; exit 0 ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
    shift
done

PUSH2_USB_ID="2982:1967"
CHILD_LOG_DIR="${PUSHPIN_LOG_DIR:-$HOME/.local/state/pushpin-groovebox/logs}"
REPO_DIR="$HOME/s/music_devices/pushpin-groovebox"

# A login over SSH normally has these; set them so "systemctl --user" works
# from any context (e.g. "sudo -u pushpin pushpin-diag").
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=$XDG_RUNTIME_DIR/bus}"

have() { command -v "$1" >/dev/null 2>&1; }

section() { printf '\n===== %s =====\n' "$*"; }

# run <command...>: print the command, then its output; never abort.
run() {
    printf -- '--- $ %s\n' "$*"
    if ! have "$1"; then
        echo "(not installed: $1)"
        return 0
    fi
    "$@" 2>&1
    local rc=$?
    [ $rc -ne 0 ] && echo "(exit $rc)"
    return 0
}

check() { printf '%-4s %s\n' "$1" "$2"; }

count_procs() { pgrep -u "$(id -u)" -c -f "$1" 2>/dev/null || echo 0; }

summary() {
    section "SUMMARY"

    local n
    n=$(count_procs '[p]ython.* app\.py')
    if [ "$n" = 1 ]; then check OK "exactly one app.py running"
    elif [ "$n" = 0 ]; then check FAIL "app.py is not running"
    else check FAIL "$n copies of app.py running (expected 1)"; fi

    n=$(count_procs '[s]urge-xt-cli')
    case "$n" in
        8) check OK "8 surge-xt-cli processes" ;;
        *) check WARN "$n surge-xt-cli processes (expected 8)" ;;
    esac
    n=$(count_procs '[p]uredata')
    check "$( [ "$n" -ge 1 ] && [ "$n" -le 9 ] && echo OK || echo WARN )" "$n puredata processes (expected up to 9)"

    for unit in pushpin overwitch pipewire wireplumber; do
        local state
        state=$(systemctl --user is-active "$unit" 2>/dev/null)
        [ "$state" = active ] && check OK "user service $unit is active" \
            || check FAIL "user service $unit is ${state:-unknown}"
    done

    if [ -e "/var/lib/systemd/linger/$(id -un)" ]; then check OK "lingering enabled for $(id -un)"
    else check FAIL "lingering not enabled for $(id -un)"; fi

    if grep -qs 'start_pushpin' "$HOME/.profile"; then check FAIL ".profile still starts the app"
    else check OK ".profile does not start the app"; fi

    if have lsusb && lsusb -d "$PUSH2_USB_ID" >/dev/null 2>&1; then check OK "Push 2 on USB"
    else check FAIL "Push 2 not found on USB ($PUSH2_USB_ID)"; fi

    if have vcgencmd; then
        local t
        t=$(vcgencmd get_throttled 2>/dev/null | cut -d= -f2)
        if [ "$t" = "0x0" ]; then check OK "no under-voltage or throttling since boot"
        else check FAIL "get_throttled=$t (under-voltage/throttling; check the PSU)"; fi
    fi

    local hdmi=""
    for s in /sys/class/drm/card*-HDMI-A-*/status; do
        [ -e "$s" ] && [ "$(cat "$s")" = connected ] && hdmi="$hdmi $(basename "$(dirname "$s")")"
    done
    if [ -n "$hdmi" ]; then check OK "HDMI connected:$hdmi"
    else check WARN "no HDMI connector reports a display"; fi

    if systemctl is-active --quiet getty@tty1 2>/dev/null; then check OK "getty on tty1 is running"
    else check FAIL "getty@tty1 is $(systemctl is-active getty@tty1 2>/dev/null)"; fi

    if [ -f /etc/rc.local ] && grep -qs 'make install' /etc/rc.local; then
        check FAIL "/etc/rc.local still reinstalls udev rules on every boot"
    else check OK "/etc/rc.local has no per-boot make install"; fi

    if systemctl list-unit-files 2>/dev/null | grep -q '^lightdm'; then
        check FAIL "lightdm (desktop) is installed on the console image"
    else check OK "no desktop display manager installed"; fi

    local failed
    failed=$(systemctl --failed --no-legend 2>/dev/null | wc -l | tr -d ' ')
    [ "$failed" = 0 ] && check OK "no failed system units" || check WARN "$failed failed system unit(s)"
    failed=$(systemctl --user --failed --no-legend 2>/dev/null | wc -l | tr -d ' ')
    [ "$failed" = 0 ] && check OK "no failed user units" || check WARN "$failed failed user unit(s)"

    local ow=0
    have pw-dump && ow=$(pw-dump 2>/dev/null | grep -c '"application.name": "overwitch-service"')
    [ "$ow" -gt 0 ] && check OK "overwitch-service is a PipeWire client" \
        || check WARN "overwitch-service not seen in PipeWire (normal with no Elektron device)"
}

full_report() {
    section "SYSTEM"
    run date -Is
    run uptime
    run uname -a
    run cat /etc/os-release
    run cat /proc/device-tree/model
    run vcgencmd get_throttled
    run vcgencmd measure_temp
    run free -h
    run df -h /
    [ -d "$REPO_DIR/.git" ] && run git -C "$REPO_DIR" log -1 --format='%H %d %s'

    section "BOOT AND DISPLAY"
    run systemctl get-default
    run cat /proc/cmdline
    run grep -v '^\s*#' /boot/firmware/config.txt
    for s in /sys/class/drm/card*-*/status; do
        [ -e "$s" ] && echo "$(basename "$(dirname "$s")"): $(cat "$s")"
    done
    run systemctl status --no-pager getty@tty1 rc-local
    run systemd-analyze blame --no-pager
    run systemctl --failed --no-pager

    section "USER SERVICES"
    run loginctl show-user "$(id -un)" -p Linger -p State
    run systemctl --user status --no-pager pushpin overwitch pipewire wireplumber
    run systemctl --user --failed --no-pager

    section "PROCESSES"
    run ps -o pid,ppid,etime,rss,args -u "$(id -u)"

    section "USB AND AUDIO DEVICES"
    run lsusb
    run aplay -l
    run ls -l /etc/udev/rules.d/ /usr/lib/udev/rules.d/ /usr/local/lib/udev/rules.d/

    section "NETWORK PORTS (OSC 1030-1057)"
    if have ss; then
        printf -- '--- $ ss -ulpn | grep 10[3-5]x\n'
        ss -ulpn 2>&1 | grep -E ':10[3-5][0-9]\b' || echo "(no OSC ports open)"
    fi

    section "PIPEWIRE"
    if have pw-dump; then
        printf -- '--- clients (application.name)\n'
        pw-dump 2>/dev/null | grep -o '"application.name": "[^"]*"' | sort | uniq -c
    fi
    run pw-link -l

    section "LOG: pushpin (journal)"
    run journalctl --user -u pushpin -b --no-pager -n "$LINES_PER_LOG"
    section "LOG: overwitch (journal)"
    run journalctl --user -u overwitch -b --no-pager -n "$LINES_PER_LOG"

    section "LOG: child processes ($CHILD_LOG_DIR)"
    if [ -d "$CHILD_LOG_DIR" ]; then
        run ls -l "$CHILD_LOG_DIR"
        for f in "$CHILD_LOG_DIR"/*.log; do
            [ -e "$f" ] || continue
            printf -- '--- tail %s\n' "$f"
            tail -n 40 "$f"
        done
    else
        echo "(missing)"
    fi

    section "LOG: system warnings this boot"
    run journalctl -b -p warning --no-pager -n "$LINES_PER_LOG"
    section "LOG: kernel (USB, DRM/HDMI, audio)"
    if have journalctl; then
        printf -- '--- $ journalctl -k -b | grep usb/drm/vc4/hdmi/snd\n'
        journalctl -k -b --no-pager 2>&1 | grep -iE 'usb|drm|vc4|hdmi|snd|voltage' | tail -n "$LINES_PER_LOG"
    fi

    section "LOG: image build (tail)"
    run tail -n 60 /var/log/sdm_image_setup.log
}

echo "pushpin-diag on $(hostname) as $(id -un)"
[ -f /etc/pushpin-diagnostics ] && cat /etc/pushpin-diagnostics
summary
[ "$SUMMARY_ONLY" = 1 ] || full_report
exit 0
