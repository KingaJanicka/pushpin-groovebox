# Pi diagnostics

Two scripts:

- **`pushpin-diag.sh`** is installed on every image as `/usr/local/bin/pushpin-diag`.
  It's a read-only health report: a `SUMMARY` of `OK` / `WARN` / `FAIL` checks
  (one `app.py`, the user services, Push 2 on USB, under-voltage, HDMI, tty1,
  leftover `rc.local` / desktop, Overwitch in PipeWire), followed by the full
  report (service status, processes, USB/audio, OSC ports, PipeWire, logs).
- **`diagnose.sh`** runs on your computer. It connects over SSH with a
  dedicated key and runs `pushpin-diag` (or any one command) on the Pi.

## Diagnostics mode

A diagnostics image is a normal image plus:

- your diagnostics public key in `/home/pushpin/.ssh/authorized_keys`
- SSH enabled, hostname `pushpin`, reachable as `pushpin.local` (avahi)
- the `pushpin` user in `adm` and `systemd-journal`, so it can read system and
  kernel logs. No sudo rights are added.
- an `/etc/pushpin-diagnostics` marker

Release images (the CI workflow) never set the key, so they don't get any of this.

## Setup

1. On your computer, create the key once:

   ```bash
   scripts/diagnostics/diagnose.sh keygen
   ```

   This writes `~/.ssh/pushpin_diag` and `~/.ssh/pushpin_diag.pub`. The private
   key has no passphrase so diagnostics can run unattended. Copy only the
   `.pub` file to the build machine.

2. Build the image on a Debian/Ubuntu/Raspberry Pi OS machine (sdm needs Linux),
   from `scripts/image`:

   ```bash
   PUSHPIN_REF=<branch or tag> PUSHPIN_DIAG_PUBKEY=/path/to/pushpin_diag.pub bash create-image-with-backports.sh
   ```

   The build refuses a private key or a file that isn't an SSH public key.

3. Flash it. If you use Raspberry Pi Imager's settings (hostname, SSH), leave
   the hostname as `pushpin` or set `PUSHPIN_HOST` below.

## Use

```bash
scripts/diagnostics/diagnose.sh forget    # after every new burn (new host keys)
scripts/diagnostics/diagnose.sh check
scripts/diagnostics/diagnose.sh summary
scripts/diagnostics/diagnose.sh report    # saved under diagnostics-output/
scripts/diagnostics/diagnose.sh run systemctl --user status pushpin
```

`PUSHPIN_HOST=192.168.1.50 scripts/diagnostics/diagnose.sh ...` targets an IP
address if mDNS doesn't resolve on your network.
