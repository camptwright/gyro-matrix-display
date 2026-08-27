# gyro-matrix-display Agent Instructions

## What this repo is

A Raspberry Pi 4B-driven RGB LED matrix display that shows sports scores,
weather, stocks/crypto, and Spotify now-playing, navigated via its web UI —
mode switching and in-mode navigation used to come from a BLE gyroscope
controller (ESP32/Arduino, `arduino_controller.ino`); that hardware is
retired and its control now lives in `web_config.py`'s "Remote Control"
panel (`/api/control/*`). It runs as a single host-native systemd service
on the Pi (`matrix-display.service`, running `web_config.py`, a Flask app
on `:5000` that both edits config and owns the live `DisplayController`) —
not in Docker or K3s. Per ADR 0003 in the parent homelab-master repo, this
is deliberate: the display depends on GPIO/SPI hardware access that doesn't
cleanly cross into Kubernetes, so it stays outside the cluster scheduler
even after the Pi joins K3s as a tainted agent for unrelated lightweight
workloads. (ADR 0003's original rationale also cited BLE; that's no longer
a factor now that the remote is gone, but GPIO/SPI for the LED matrix
itself still is — the ADR lives in the parent repo and hasn't been
revisited here.)

## Hard rules for agents

1. **Never commit `config/config.json` or `config/config_secrets.json`.**
   Both are gitignored; only the `.template.json` versions belong in git.
   The application reads secrets from `config/config_secrets.json`; the live
   systemd units do not inline them. Keep that file mode `0600` and do not add
   unused `EnvironmentFile` plumbing unless the application is first changed
   to consume it.
2. **This repo does not run in Docker/K3s, and must not be moved there.**
   ADR 0003 (`homelab-master/docs/decisions/0003-pi-matrix-display-host-native.md`)
   is the authoritative reason: GPIO/SPI access for the LED matrix (BLE was
   also cited originally but is no longer relevant now that the gyro remote
   is gone). Treat any request to containerize `matrix-display.service` as
   a decision that needs a new ADR, not a routine change.
3. **The Pi is not yet joined to K3s.** Per `docs/network/inventory.md` in
   the parent repo, `pi-matrix` (192.168.8.126) is online with no cluster
   role today; do not assume K3s-specific tooling (kubelet, taints) exists
   on the host yet — `PI-PREP.md`'s K3s prerequisites section is explicitly
   "do after Flint 2 cutover," not done.
4. **The web UI (`:5000`) is not exposed publicly.** It is only meant to be
   reachable once Cloudflare Tunnel + Access is configured for it, same
   pattern as other admin surfaces in the stack — this now includes live
   display control (`/api/control/*`), not just config editing, so the
   stakes of exposing it are higher than before. Do not add port forwarding
   or bind it to `0.0.0.0` as a "fix" for remote access (it already binds
   `0.0.0.0` for LAN reachability; the rule is about not exposing it beyond
   the LAN, not about that bind address).

## Agents must not

- Commit real API keys (OpenWeatherMap, Spotify) or Spotify/YTM token caches
  (`*.cache`, `token.json`, `token.pickle` — already gitignored, keep it that way).
- Add a `/healthz`-less service file — `PI-PREP.md` calls out that
  `web_config.py` needs a liveness endpoint for Uptime Kuma/future K3s
  probes; don't regress that once added.
- Assume a virtualenv — `matrix-display.service` currently `ExecStart`s
  against `/usr/bin/python3` directly with `pip3 install --break-system-packages`;
  don't silently switch to a venv path without updating the `.service` file.
- Claim `RestartSec=30` is live before the installed unit has been updated
  and verified; the 2026-08-16 audit still found 10 seconds.
- Assume the live Pi already runs the merged single-service setup this repo
  now describes — as of this refactor it still runs the old two-service/BLE
  setup until someone deploys and reconciles it (see README's "Pending
  deployment gap" note and `PI-PREP.md`).
