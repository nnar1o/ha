# Home Assistant Add-ons Repository - AI Agent Instructions

## Project Overview
This is a Home Assistant add-ons repository containing the **SMS Gateway** add-on, which enables SMS messaging through Huawei USB modems. The add-on runs as a containerized service within Home Assistant OS.

## Architecture & Key Components

### Add-on Structure (Home Assistant Specific)
- `config.yaml`: Add-on manifest defining version, slug, architecture support, API permissions, and configuration schema
- `build.yaml`: Multi-architecture Docker build configuration using Home Assistant base images
- `Dockerfile`: Alpine-based container with gammu, usb-modeswitch, and Python dependencies
- `rootfs/`: Container filesystem overlay (copied directly into container at `/`)
- `rootfs/etc/services.d/sms-gateway/run`: s6-overlay service script (starts with bashio)

### Core Application Modules (`rootfs/app/`)
1. **`gammu_mqtt.py`**: Main service orchestrating SMS operations
   - Connects to gammu (modem library) and paho-mqtt
   - Publishes/subscribes to MQTT topics (`sms-gateway/inbox`, `sms-gateway/outbox`)
   - Creates Home Assistant entities via Home Assistant API
   - Implements retry logic (5 attempts, 5s delay) for modem connection
   - Fetches MQTT credentials from Home Assistant Supervisor API (via environment variables)

2. **`usb_switcher.py`**: Automatic USB mode switching for Huawei modems
   - Detects Huawei devices in storage mode using `lsusb` and `pyudev`
   - Switches to modem mode via `usb_modeswitch` (handles VID:PID `12d1:1506`, `12d1:1f01`, etc.)
   - Intelligent device selection: prefers Huawei devices when multiple serial devices present
   - Saves detected devices to `/data/available_usb.json`
   - Exports `DEVICE` environment variable for `gammu_mqtt.py`

3. **`gammu_probe.py`**: Connection diagnostics module
   - Tests multiple gammu connection types (`at115200`, `at9600`, `at`) in priority order
   - Generates temporary `gammurc` files for testing
   - Saves diagnostics to `/data/sms_gateway_diagnostics.json`
   - Creates `/etc/gammurc` with working connection configuration

4. **`logger.py`**: Custom logging with ANSI colors
   - Colored console output (DEBUG=cyan, INFO=green, WARNING=yellow, ERROR=red)
   - Plain-text file logging for compatibility
   - UTC timestamps in format `YYYY-MM-DD HH:MM:SS UTC`

### Service Startup Sequence (from `run` script)
1. Fetch MQTT credentials from Home Assistant using `bashio::services`
2. Export MQTT configuration as environment variables
3. Run `usb_switcher.py` to detect/switch modem and set `DEVICE` env var
4. Run `gammu_probe.py` to test connections and generate `/etc/gammurc`
5. Start `gammu_mqtt.py` main service

## Critical Patterns & Conventions

### Version Management
- Version is defined in THREE places (must sync manually):
  - `config.yaml` (line 2)
  - `Dockerfile` (echo to `/app/version.txt`)
  - `VERSION` file (optional reference)
- `gammu_mqtt.py` reads version from `/app/version.txt` or hardcoded `VERSION = "1.0.15"`

### Configuration Priority (Environment Over Files)
Environment variables take precedence over `options.json`:
```python
DEVICE = os.getenv('DEVICE') or options.get('device', '/dev/ttyUSB0')
MQTT_HOST = os.getenv('MQTT_HOST') or options.get('mqtt', {}).get('broker', 'core-mosquitto')
```
This allows `usb_switcher.py` to override device selection and `bashio::services` to inject MQTT config.

### Home Assistant API Integration
- Requires `auth_api: true` and `homeassistant_api: true` in `config.yaml`
- Uses `SUPERVISOR_TOKEN` environment variable for authentication
- Endpoint: `http://supervisor/core/api`
- Creates entities via POST to `/states/{entity_id}` with JSON body containing `state` and `attributes`

### MQTT Topics Convention
- **Outbox** (`sms-gateway/outbox`): JSON with `{"number": "+123", "message": "text"}`
- **Inbox** (`sms-gateway/inbox`): Published on SMS receive with sender/message/timestamp
- **Diagnostics** (`sms-gateway/diagnostics`): Published on errors with retain flag

### Error Handling & Retry Patterns
- Modem connection: 5 retries with 5-second delays
- On final failure: publishes diagnostics to MQTT and writes to `/tmp/gammu.log`
- Graceful degradation: service continues running even if modem unavailable (polls for reconnection)

### Logging Standards
- All timestamps in UTC: `datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')`
- Log files typically in `/tmp/` (e.g., `/tmp/gammu.log`)
- Diagnostic JSON files in `/data/` (persisted across restarts)
- Use custom logger from `logger.py` for colored output

### Device Detection Logic (Multi-Device Scenarios)
Priority order in `usb_switcher.py`:
1. User-configured device in `options.json` (always respected)
2. By-id paths containing 'HUAWEI' (case-insensitive)
3. Vendor ID `12d1` (Huawei)
4. Manufacturer field matching 'Huawei'
5. Product/model strings matching patterns (E3276, E3131, E3372, etc.)

## Development Workflows

### Building the Add-on
Home Assistant add-ons are built automatically by Home Assistant Supervisor. For local testing:
```bash
docker build --build-arg BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.11-alpine3.18 -t sms-gateway .
```

### Testing Changes
1. Edit files in `rootfs/app/` or configuration files
2. Increment version in `config.yaml`, `Dockerfile`, and `VERSION`
3. Rebuild and restart add-on in Home Assistant UI
4. Check logs via Home Assistant add-on logs tab or `docker logs <container>`

### Debugging
- View logs: Home Assistant UI → Add-ons → SMS Gateway → Logs
- Enable debug: Set `debug: true` in add-on configuration
- Check diagnostics: `/data/sms_gateway_diagnostics.json` in container
- Test gammu manually: `docker exec -it addon_<slug> gammu --identify`
- View USB devices: `/data/available_usb.json`

### Common Issues
- **Device not found**: Check USB passthrough with `lsusb` in container, verify `uart: true` and `usb: true` in `config.yaml`
- **MQTT connection fails**: Ensure Home Assistant MQTT integration is configured and add-on has `auth_api: true`
- **Modem in storage mode**: `usb_switcher.py` should auto-switch; check logs for VID:PID detection

## Key Files Reference
- **Configuration**: `sms-gateway/config.yaml` (add-on manifest)
- **Main service**: `sms-gateway/rootfs/app/gammu_mqtt.py`
- **USB detection**: `sms-gateway/rootfs/app/usb_switcher.py`
- **Connection testing**: `sms-gateway/rootfs/app/gammu_probe.py`
- **Startup script**: `sms-gateway/rootfs/etc/services.d/sms-gateway/run`
- **Documentation**: `sms-gateway/DOCS.md` (user-facing), `sms-gateway/README.md` (developer-facing)

## Integration Points
- **Home Assistant Supervisor API**: Fetches MQTT credentials via `bashio::services`
- **Home Assistant Core API**: Creates/updates entities (sensors, binary_sensors, events)
- **MQTT Broker**: Typically `core-mosquitto` add-on running in same Home Assistant instance
- **Gammu Library**: C library wrapped by `python-gammu` for AT command communication with modem
- **USB Subsystem**: Direct device access via `/dev/ttyUSB*` (requires `usb: true` permission)
