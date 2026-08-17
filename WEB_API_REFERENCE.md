# Matrix Display Web API Reference

## Base URL
`http://localhost:5000` or `http://<raspberry-pi-ip>:5000`

## Instant Response APIs (New - Optimized for <200ms latency)

### Change Display Mode
**Endpoint**: `POST /api/mode/change`

**Description**: Instantly switches the display mode without requiring a full config reload.

**Request Body**:
```json
{
  "mode": "clock"
}
```

**Valid Modes**:
- `clock` - Display world clocks
- `sports` - Display sports scores
- `fantasy` - Display fantasy player stats
- `stocks` - Display stock/crypto prices
- `weather` - Display weather information
- `music` - Display currently playing music
- `images` - Display photos/GIFs
- `brightness` - Enter brightness adjustment mode

**Response**:
```json
{
  "success": true,
  "mode": "clock"
}
```

**Example (curl)**:
```bash
curl -X POST http://localhost:5000/api/mode/change \
  -H "Content-Type: application/json" \
  -d '{"mode":"sports"}'
```

**Example (JavaScript)**:
```javascript
fetch('/api/mode/change', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ mode: 'sports' })
})
.then(res => res.json())
.then(data => console.log('Mode changed:', data));
```

---

### Set Brightness
**Endpoint**: `POST /api/brightness/set`

**Description**: Instantly adjusts the display brightness.

**Request Body**:
```json
{
  "brightness": 75
}
```

**Parameters**:
- `brightness` (integer, required): Brightness level from 0-100

**Response**:
```json
{
  "success": true,
  "brightness": 75
}
```

**Example (curl)**:
```bash
curl -X POST http://localhost:5000/api/brightness/set \
  -H "Content-Type: application/json" \
  -d '{"brightness":50}'
```

**Example (JavaScript)**:
```javascript
fetch('/api/brightness/set', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ brightness: 75 })
})
.then(res => res.json())
.then(data => console.log('Brightness set:', data));
```

---

### Navigate Display
**Endpoint**: `POST /api/navigate`

**Description**: Send navigation commands to control the display (mimics gesture controls).

**Request Body**:
```json
{
  "direction": "up"
}
```

**Valid Directions**:
- `up` - Navigate up (switch sports, toggle stocks/crypto, switch photos/gifs, etc.)
- `down` - Navigate down (switch sports, toggle stocks/crypto, switch photos/gifs, etc.)
- `left` - Navigate left (previous game, previous ticker, previous image, etc.)
- `right` - Navigate right (next game, next ticker, next image, etc.)

**Navigation Behavior by Mode**:

| Mode | Up/Down | Left/Right |
|------|---------|------------|
| **Sports** | Switch between sports | Navigate games within sport |
| **Stocks** | Toggle stocks ↔ crypto | Navigate tickers in list |
| **Images** | Toggle photos ↔ GIFs | Navigate images in list |
| **Fantasy** | Switch sports (NFL/NBA/NHL) | Navigate players in sport |
| **Weather** | Switch weather locations | N/A |
| **Clock** | Switch time zones | N/A |

**Response**:
```json
{
  "success": true,
  "direction": "up"
}
```

**Example (curl)**:
```bash
curl -X POST http://localhost:5000/api/navigate \
  -H "Content-Type: application/json" \
  -d '{"direction":"right"}'
```

**Example (JavaScript)**:
```javascript
fetch('/api/navigate', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ direction: 'right' })
})
.then(res => res.json())
.then(data => console.log('Navigated:', data));
```

---

## Configuration APIs (Existing)

### Get Configuration
**Endpoint**: `GET /api/config`

**Description**: Retrieve the current configuration.

**Response**:
```json
{
  "brightness": 50,
  "timezone": "America/New_York",
  "clock_locations": [...],
  "sports": [...],
  "stocks": [...],
  "crypto": [...],
  ...
}
```

---

### Save Configuration
**Endpoint**: `POST /api/save`

**Description**: Save the full configuration. This triggers a config reload on the display controller (will be detected within 100ms).

**Request Body**: Full config object (same structure as GET response)

**Response**:
```json
{
  "success": true
}
```

**Note**: After saving, the display controller will reload the config within 100ms.

---

## Image Management APIs (Existing)

### List Images
**Endpoint**: `GET /api/images/list`

**Response**:
```json
{
  "photos": ["photo1.jpg", "photo2.png"],
  "gifs": ["animation.gif"]
}
```

---

### Upload Image
**Endpoint**: `POST /api/images/upload`

**Content-Type**: `multipart/form-data`

**Parameters**:
- `file` (file): Image file to upload
- `type` (string): Either "photo" or "gif"

**Response**:
```json
{
  "success": true,
  "filename": "photo1.jpg"
}
```

---

### Delete Image
**Endpoint**: `DELETE /api/images/delete/<type>/<filename>`

**Parameters**:
- `type` (path): Either "photo" or "gif"
- `filename` (path): Name of file to delete

**Response**:
```json
{
  "success": true
}
```

---

## Error Responses

All endpoints return error responses in this format:

```json
{
  "success": false,
  "error": "Error message description"
}
```

**Common HTTP Status Codes**:
- `200` - Success
- `400` - Bad Request (invalid parameters)
- `404` - Not Found (file doesn't exist)
- `500` - Internal Server Error

---

## Performance Notes

### Response Times (Expected)
- **Instant APIs** (`/api/mode/change`, `/api/brightness/set`, `/api/navigate`): <200ms
- **Config APIs** (`/api/save`): 100-300ms (includes file write + reload)
- **Image APIs**: Depends on file size (typically 100-500ms)

### Optimization Details
- Mode, brightness, and navigation commands are detected every 0.1 seconds by the display controller
- Config changes are also detected every 0.1 seconds (improved from 2 seconds)
- File operations use atomic writes with proper permissions (0o666)
- Temporary files are cleaned up after processing
- Navigation commands update display immediately without config reload

---

## Quick Usage Examples

### Create a Simple Control Panel
```html
<!DOCTYPE html>
<html>
<body>
  <h1>Matrix Display Quick Control</h1>
  
  <div>
    <button onclick="changeMode('clock')">Clock</button>
    <button onclick="changeMode('sports')">Sports</button>
    <button onclick="changeMode('weather')">Weather</button>
  </div>
  
  <div>
    <label>Brightness: <input type="range" min="0" max="100" 
           onchange="setBrightness(this.value)"></label>
  </div>
  
  <div style="margin-top: 20px;">
    <h3>Navigation</h3>
    <div style="display: grid; grid-template-columns: repeat(3, 60px); gap: 5px;">
      <div></div>
      <button onclick="navigate('up')">⬆️</button>
      <div></div>
      <button onclick="navigate('left')">⬅️</button>
      <div></div>
      <button onclick="navigate('right')">➡️</button>
      <div></div>
      <button onclick="navigate('down')">⬇️</button>
      <div></div>
    </div>
  </div>
  
  <script>
    async function changeMode(mode) {
      const res = await fetch('/api/mode/change', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode })
      });
      const data = await res.json();
      alert(data.success ? `Changed to ${mode}` : `Error: ${data.error}`);
    }
    
    async function setBrightness(value) {
      const res = await fetch('/api/brightness/set', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ brightness: parseInt(value) })
      });
      const data = await res.json();
      console.log(data.success ? `Brightness: ${value}%` : `Error: ${data.error}`);
    }
    
    async function navigate(direction) {
      const res = await fetch('/api/navigate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ direction })
      });
      const data = await res.json();
      console.log(data.success ? `Navigated: ${direction}` : `Error: ${data.error}`);
    }
  </script>
</body>
</html>
```

### Python Script Control
```python
import requests

BASE_URL = "http://localhost:5000"

# Change mode
response = requests.post(f"{BASE_URL}/api/mode/change", 
                        json={"mode": "sports"})
print(response.json())

# Set brightness
response = requests.post(f"{BASE_URL}/api/brightness/set", 
                        json={"brightness": 80})
print(response.json())
```

### Home Assistant Integration
```yaml
# configuration.yaml
rest_command:
  matrix_mode_sports:
    url: "http://192.168.1.100:5000/api/mode/change"
    method: POST
    content_type: "application/json"
    payload: '{"mode":"sports"}'
  
  matrix_brightness_high:
    url: "http://192.168.1.100:5000/api/brightness/set"
    method: POST
    content_type: "application/json"
    payload: '{"brightness":90}'
```

---

## Security Considerations

- The web service binds to `0.0.0.0:5000` (all interfaces)
- No authentication is currently implemented
- Recommended: Use firewall rules to restrict access to trusted networks
- File operations use `secure_filename()` to prevent directory traversal
- Brightness and mode values are validated before processing

---

## Troubleshooting

### Mode/brightness changes not working
1. Check that the display controller service is running
2. Verify `/tmp/matrix_display_mode` and `/tmp/matrix_display_brightness` files can be created
3. Check display controller logs: `journalctl -u matrix-display.service -f`

### High latency (>500ms)
1. Check system load: `top` or `htop`
2. Verify network latency if accessing remotely: `ping <pi-ip>`
3. Check if display controller is busy with heavy operations

### Permission errors
1. Ensure temporary files have proper permissions (0o666)
2. Check that the display controller user can read `/tmp/matrix_display_*` files
3. Verify web service has write permissions to `/tmp/`
