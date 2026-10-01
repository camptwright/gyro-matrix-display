# Gyro Matrix Display

Host-native Raspberry Pi 4B software for an RGB LED matrix showing sports,
weather, stocks/crypto, Spotify now-playing, and a clock. The Flask web UI
(`web_config.py`, port 5000) is both the configurator and the live remote
control — mode switching and in-mode navigation used to come from a BLE
gyroscope remote (retired; see git history for `receiver.py` and
`arduino_controller.ino` if that hardware ever comes back) and now happen
from the "Remote Control" panel on the web UI itself. The health endpoint
also lives on port 5000.

## Live deployment

| Item | Current state (verified 2026-09-30) |
|---|---|
| Host | `raspberrypi` at `192.168.20.11`, user `reekpi`, aarch64 |
| Path | `/home/reekpi/matrix-display` |
| Service | `matrix-display.service` (runs `web_config.py`), active and enabled |
| Health | `http://192.168.20.11:5000/healthz`; live frame at `/api/preview.png` |
| Runtime | Host-native Python/systemd; deliberately not containerized |
| K3s | Not installed; swap remains enabled |

The live checkout's working tree was committed to this repo on
2026-09-30 (branch `fix-scores-fonts-logos`), so the repo and the Pi now
match. Deploy by copying changed files and restarting the service; the Pi's
own `git` checkout is still at an older commit.

Fonts: layouts use native-size bitmap fonts via `pixel_fonts.py` (5x7, 6x9,
4x6 BDF, plus PressStart2P at its native 8px). Don't render PressStart2P
below 8px - it misdraws letters and digits on the panel.

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

- Web configuration + remote control: `http://<PI_IP>:5000`
- Liveness: `GET /healthz` returns `{"status":"ok"}`
- Logs: `sudo journalctl -u matrix-display -f`
- State: `systemctl status matrix-display`

Once deployed, `matrix-display.service` is the only service: it runs
`web_config.py`, which both edits persistent config (favorites, areas,
enabled toggles, image uploads) and owns the live `DisplayController` —
mode switching and in-mode navigation (next/prev game, brightness, etc.)
happen through its "Remote Control" panel, calling `/api/control/*`.

The web UI is LAN-only. Do not expose it with router port forwarding;
any remote administrative exposure must use the reviewed Cloudflare Access or
Tailscale design.

See [`PI-PREP.md`](PI-PREP.md) for the audited host state and remaining work.
