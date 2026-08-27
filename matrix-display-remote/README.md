# Matrix Display Remote

Mobile-friendly web app to control your LED matrix display **without needing the IP address**.

## Quick Start

1. **Set up mDNS hostname** (one-time, on your Raspberry Pi):
   ```bash
   sudo hostnamectl set-hostname matrix-display
   ```
   Or use the default `raspberrypi` hostname.

2. **Deploy**: this folder is part of the main repo checkout, so a normal
   `git pull` on the Pi brings it along with `web_config.py` — no separate
   copy step. `web_config.py` serves it directly at `/remote` and
   `/manifest.json`.

3. **Open on your phone/computer** (must be on the same WiFi):
   - **matrix-display.local:5000/remote** (if you set the hostname)
   - **raspberrypi.local:5000/remote** (default Pi hostname)

4. **Add to Home Screen** (phone): Use your browser’s “Add to Home Screen” for an app-like shortcut.

## How It Works

- **mDNS** lets you use `matrix-display.local` instead of an IP address.
- The remote app is served by the Pi's single `matrix-display.service` (which
  runs `web_config.py` — it owns both the config UI and the live display
  controller) at `/remote`.
- All API calls use the same origin, so no CORS setup is needed.

## Deployment

After a `git pull` on the Pi, restart the service:

```bash
sudo systemctl restart matrix-display.service
```

## URLs

| URL | Use |
|-----|-----|
| `matrix-display.local:5000/remote` | Mobile remote (mode, brightness, nav) |
| `matrix-display.local:5000/` | Full configuration page |

## Troubleshooting

**Can’t reach matrix-display.local**
- Ensure the Pi and your device are on the same WiFi.
- Try `raspberrypi.local:5000/remote` if you didn’t change the hostname.
- Check that Avahi is running: `sudo systemctl status avahi-daemon`

**Connection shows “Disconnected”**
- Confirm the service is running: `sudo systemctl status matrix-display.service`
- Check its logs: `sudo journalctl -u matrix-display -f`
