# Pi Prep Checklist

> **Status:** Pi is currently OFFLINE. Complete this list before connecting it to the
> new network. Do NOT join it to K3s until after the Flint 2 cutover and DHCP
> reservation are confirmed.

## Before connecting to the network

```
[ ] Record Pi MAC address:
      eth0 MAC: ___________________  (from `ip link show eth0` or Pi sticker)
      wlan0 MAC: __________________ (optional, prefer wired)

[ ] Create Flint 2 DHCP reservation: 10.51.24.20 → pi-matrix (MAC above)
    See docs/network/flint2-reservations.md

[ ] Back up the current matrix configuration:
      scp pi:/home/raspberrypi/matrix-display/config/config.json ./config/config.backup.json
      scp pi:/home/raspberrypi/matrix-display/config/config_secrets.json (store securely, NOT in git)

[ ] Confirm config_secrets.json is in the Pi's .gitignore and NOT committed to this repo.
```

## Systemd service hardening

The two systemd services (`matrix-display.service`, `web-config.service`) currently
inline their configuration. When the Pi comes online:

```
[ ] Create /home/raspberrypi/matrix-display/matrix-display.env with API keys:
      OPENWEATHERMAP_API_KEY=...
      (other secrets from config_secrets.json)

[ ] Update matrix-display.service and web-config.service to use:
      EnvironmentFile=/home/raspberrypi/matrix-display/matrix-display.env
    instead of inlining secrets in the service file.

[ ] Set permissions: chmod 600 matrix-display.env

[ ] Set RestartSec to a more conservative value for production:
      RestartSec=30
    to avoid fast restart loops on hardware faults.

[ ] Consider adding:
      StandardInput=null
    to prevent any accidental stdin consumption.
```

## Add /healthz endpoint to web_config.py

The matrix web configurator needs a `/healthz` endpoint for monitoring
(Uptime Kuma probe, future K3s readiness/liveness).

Minimal implementation to add to web_config.py:

```python
@app.route('/healthz')
def healthz():
    """Liveness check — always returns 200 if the process is running."""
    return {'status': 'ok'}, 200
```

After adding: `systemctl restart matrix-web-config` and verify:
```bash
curl http://pi-matrix:5000/healthz
# Expected: {"status": "ok"}
```

## K3s prerequisites (do after Flint 2 cutover)

```
[ ] Update Pi OS: sudo apt update && sudo apt full-upgrade -y
[ ] Verify arch: uname -m  (expected: aarch64)
[ ] Set hostname: sudo hostnamectl set-hostname k3s-pi-01
[ ] Disable swap: sudo dphys-swapfile swapoff && sudo systemctl disable dphys-swapfile
[ ] Enable cgroups: add to /boot/firmware/cmdline.txt:
      cgroup_enable=cpuset cgroup_memory=1 cgroup_enable=memory
[ ] Reboot and verify: cat /proc/cgroups | grep memory
```

## What NOT to do yet

- Do not join the Pi to K3s until the matrix display is verified working on the new network.
- Do not expose the web configurator publicly until Cloudflare Tunnel + Access is configured.
- Do not store secrets in this repo or in the systemd service files.
