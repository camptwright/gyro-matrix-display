# Gyro Matrix Display

Host-native Raspberry Pi 4B software for an RGB LED matrix showing sports,
weather, stocks/crypto, Spotify now-playing, and a clock. A BLE gyroscope
controller can change modes. The Flask configurator and health endpoint listen
on port 5000.

## Live deployment

| Item | Current state (verified 2026-08-16) |
|---|---|
| Host | `raspberrypi` at `192.168.8.126`, user `reekpi`, aarch64 |
| Path | `/home/reekpi/matrix-display` |
| Services | `matrix-display.service` and `web-config.service`, active and enabled |
| Health | `http://192.168.8.126:5000/healthz` |
| Runtime | Host-native Python/systemd; deliberately not containerized |
| K3s | Not installed; swap remains enabled |

The live checkout tracks `git@github.com:reek4/gyro-matrix-display.git`, while
this workspace tracks `git@github.com:camptwright/gyro-matrix-display.git`.
The Pi also contains substantial uncommitted changes. Reconcile ownership and
diffs before treating either remote as deployment authority; do not copy this
checkout over the live tree wholesale.

## Development setup

```bash
git clone git@github.com:camptwright/gyro-matrix-display.git
cd gyro-matrix-display
pip3 install -r requirements.txt --break-system-packages
cp config/config.template.json config/config.json
cp config/config_secrets.template.json config/config_secrets.json
```

Keep both local configuration files untracked. `config_secrets.json` contains
the OpenWeatherMap/Spotify credentials and must be mode `0600` on the Pi.
Authenticate Spotify with `python3 src/authenticate_spotify.py` when music mode
is used.

The committed systemd unit files are examples, not an assertion that their
paths match the live Pi. Compare their `User`, `WorkingDirectory`, `ExecStart`,
and restart policy with the live units before installation.

## Operation

- Web configuration: `http://<PI_IP>:5000`
- Mobile-friendly remote control: `http://<PI_IP>:5000/remote` (installable PWA)
- Liveness: `GET /healthz` returns `{"status":"ok"}`
- Logs: `sudo journalctl -u matrix-display -u web-config -f`
- State: `systemctl status matrix-display web-config`

Additional display modes beyond clock/weather/stocks: music playback controls,
favorite-sports-teams tracking, and an image/GIF display mode with NCAA/NFL
team logo assets.

The web configurator is LAN-only. Do not expose it with router port forwarding;
any remote administrative exposure must use the reviewed Cloudflare Access or
Tailscale design.

See [`PI-PREP.md`](PI-PREP.md) for the audited host state and remaining work.
