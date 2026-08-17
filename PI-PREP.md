# Pi Prep Checklist

> **Status:** Pi is ONLINE at 192.168.8.126 (real user `reekpi`, not `raspberrypi` as
> originally assumed below). Real deployment path is `/home/reekpi/matrix-display/`,
> a git checkout tracking `git@github.com:reek4/gyro-matrix-display.git` — a
> **different remote** than this local repo checkout
> (`git@github.com:camptwright/gyro-matrix-display.git`). The Pi's checkout also has
> its own uncommitted local modifications (many files). This is a real deployment
> gap: changes made here do not automatically reach the Pi and vice versa. Edits for
> this pass were applied directly to the file on the Pi and mirrored here manually.
> Reconnaissance + hardening pass completed 2026-08-15.

## Before connecting to the network

```
[x] Record Pi MAC address:
      eth0 MAC: 88:a2:9e:4a:f9:93  (confirmed via `ip link show eth0`, matches
        docs/network/inventory.md)
      wlan0 MAC: (not recorded; wired eth0 in use)

[ ] Flint 2 DHCP reservation — desired entry is documented in the parent
    docs/network/flint2-reservations.md, but the router had no MAC-keyed host
    entries during the 2026-08-16 audit.

[x] Back up the current matrix configuration:
      scp reekpi@192.168.8.126:/home/reekpi/matrix-display/config/config.json \
          ./config/config.backup.json
      scp reekpi@192.168.8.126:/home/reekpi/matrix-display/config/config_secrets.json \
          → stored at /Users/camptwright/.secrets/gyro-matrix-display/config_secrets.backup.json
          (chmod 600, NOT in any git repo)

[x] Confirmed config/config_secrets.json and config/config.json are covered by this
    repo's .gitignore (config/config.json, config/config_secrets.json, *.json.bak).
    Not committed anywhere.

[x] Full pre-change backup taken ON the Pi itself before any edits:
      /home/reekpi/matrix-display-pre-hardening-backup-20260815.tar.gz
    (systemd units + entire /home/reekpi/matrix-display tree, ~448MB)
```

## Systemd service hardening

**Correction found during hardening pass:** neither `matrix-display.service` nor
`web-config.service` actually inline any secrets — the only `Environment=` directives
present are `PYTHONUNBUFFERED`, `HOME`, and `USER`. The app does not read secrets
from environment variables at all: `src/config_manager.py` loads
`config/config_secrets.json` directly and passes values as function args (e.g.
`weather_fetcher.fetch_weather(..., api_key=...)`). There is no
`OPENWEATHERMAP_API_KEY` env var anywhere in this app's real code path — the secret
lives under the `weather.api_key` key in `config_secrets.json`.

Given that, creating an `EnvironmentFile=`/`matrix-display.env` would be dead
plumbing the app never reads — skipped as unnecessary risk for a production display.
The actual gap was file permissions, which is fixed:

```
[x] config/config_secrets.json permissions hardened: was 664 (group+world readable),
    now chmod 600 (owner reekpi only; matrix-display.service runs as root so it can
    still read it regardless of file perms).
[x] Confirmed no API keys/secrets inlined as Environment= in either unit file.
[ ] EnvironmentFile= migration — not applicable; app does not consume secrets via
    env vars. Revisit only if the app's secret-loading is refactored.
[ ] Set RestartSec to a more conservative value for production (RestartSec=30) —
    not yet done, still 10s in both units. Low priority, deferred.
[ ] Consider StandardInput=null — not yet done, deferred.
```

## Add /healthz endpoint to web_config.py

The matrix web configurator needs a `/healthz` endpoint for monitoring
(Uptime Kuma probe, future K3s readiness/liveness).

```
[x] Added to /home/reekpi/matrix-display/web_config.py (the file actually running
    on the Pi, ahead of the `/` route) and mirrored into this repo's
    gyro-matrix-display/web_config.py (same insertion point, ahead of `/`) — see
    deployment-gap note above for why both had to be edited by hand.
```

Implementation added:

```python
@app.route('/healthz')
def healthz():
    """Liveness check -- always returns 200 if the process is running."""
    return {'status': 'ok'}, 200
```

Verified after `sudo systemctl restart web-config`:
```bash
curl -fsS http://127.0.0.1:5000/healthz
# {"status":"ok"}
curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:5000/
# 200
```
Both services (`matrix-display`, `web-config`) confirmed `active` after the restart.

## K3s prerequisites (not started)

The 2026-08-16 audit confirmed hostname `raspberrypi`, K3s absent, and swap
enabled. The matrix application remains host-native even if this machine later
becomes a tainted K3s agent for unrelated workloads.

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
