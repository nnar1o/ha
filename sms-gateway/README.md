# SMS Gateway Add-on for Home Assistant

Send and receive SMS messages through a Huawei modem with native Home Assistant integration.

## Features

✅ **Send SMS** via MQTT or Home Assistant automations  
✅ **Receive SMS** with automatic notifications  
✅ **Native Integration** with Home Assistant sensors and events  
✅ **Real-time Status** showing modem connection state  
✅ **Detailed Logging** with timestamps for all operations  
✅ **Easy Configuration** through add-on UI  
✅ **Dashboard Ready** with pre-configured entity examples  
✅ **Automatic USB Mode Switching** for Huawei modems (detects and switches from storage mode to modem mode)  
✅ **Intelligent Device Detection** with Huawei modem preference when multiple devices present  
✅ **Auto-Gammurc Generation** with connection testing and diagnostics  
✅ **MQTT Diagnostics** for troubleshooting connection issues

## Quick Start

1. **Install the add-on** from the Add-on Store
2. **Configure** the device path (usually `/dev/ttyUSB0`)
3. **Connect** your Huawei modem via USB
4. **Start** the add-on
5. **Check status** using `binary_sensor.sms_gateway_modem_connected`

## Automatic USB Mode Switching

The add-on automatically detects Huawei modems in storage mode and switches them to modem mode on startup. This eliminates the need for manual `usb_modeswitch` configuration.

**Detected devices are saved to `/data/available_usb.json`** for reference. This file contains:
- Device paths (e.g., `/dev/ttyUSB0`)
- Vendor and product IDs
- Device metadata (manufacturer, model, serial number)

### Intelligent Device Detection

**Single Device**: If exactly one modem is detected, it's automatically selected.  

**Multiple Devices**: When multiple serial devices are detected, the add-on intelligently prefers HUAWEI devices using this priority order:
1. User-configured device in add-on options (always respected, never overridden)
2. By-id paths containing 'HUAWEI' (case-insensitive)
3. Vendor ID matching Huawei (12d1)
4. Manufacturer field containing 'Huawei'
5. Product/model strings matching common Huawei modem patterns (E3276, E3131, E3372, etc.)

If a HUAWEI device is found, it will be auto-selected. Otherwise, configure the `device` option in the add-on settings to specify which device to use.

**No Device Found**: The add-on continues running and will retry modem detection.

**Storage Mode Detection**: The add-on recognizes these Huawei storage mode VID:PID combinations and automatically attempts mode switching:
- 12d1:1506 (E3276 storage mode)
- 12d1:1f01 (Common storage mode)
- 12d1:1038 (Storage mode variant)
- And several other variants

## Automatic Gammu Configuration & Diagnostics

The add-on (v1.0.14+) features intelligent modem detection with automatic gammurc generation and comprehensive diagnostics.

### Intelligent Detection & Auto-Gammurc

When a device is selected (either automatically or via configuration):
1. **Device Detection**: The add-on uses pyudev to gather detailed device information (vendor, product, model, serial, by-id path)
2. **Smart Selection**: For multiple devices, it intelligently prefers Huawei modems based on:
   - by-id paths containing 'HUAWEI'
   - Vendor ID (12d1)
   - Manufacturer field
   - Model/product strings (E3276, E3131, E3372, etc.)
3. **Connection Testing**: Tests multiple connection types with gammu_probe module
4. **Auto-Configuration**: Generates `/etc/gammurc` with the working connection as primary

### Connection Testing

Before starting the main SMS gateway service, the add-on tests multiple connection types in order:
1. **at115200** - High-speed AT command mode (preferred)
2. **at9600** - Standard-speed AT command mode (fallback)
3. **at** - Basic AT command mode (last resort)

Each connection type is tested with both `gammu --identify` (5s timeout) and Python `gammu.StateMachine.Init()` (10s timeout). The first successful connection is used as the primary configuration. If all tests fail, the add-on still starts but logs detailed diagnostics.

### Colored Logs (v1.0.14+)

The add-on now features ANSI-colored console output for easier log reading:
- **DEBUG** messages in cyan
- **INFO** messages in green
- **WARNING** messages in yellow
- **ERROR** messages in red

Log files remain in plain text format for compatibility.

### Diagnostics & Troubleshooting

**Diagnostics File**: `/data/sms_gateway_diagnostics.json` contains:
- Timestamp of connection tests
- Device path and selection reason
- User-configured device (if set)
- List of attempted connections with success/failure status
- Error messages for failed attempts
- Full stdout/stderr from gammu commands (truncated)

**Gammu Log**: `/tmp/gammu.log` contains:
- Full output from gammu --identify for each connection test
- Complete error messages and Python tracebacks
- Used gammurc content for each attempt
- Modem initialization errors with full details
- All diagnostic information in plain text (append mode)

**MQTT Diagnostics Topic**: `sms-gateway/diagnostics`
- Automatically publishes diagnostics on startup
- Published with retain flag for persistence
- Includes all connection test results
- Publishes modem initialization errors from gammu_mqtt.py
- Useful for remote monitoring and troubleshooting

To view diagnostics in Home Assistant:
```yaml
sensor:
  - platform: mqtt
    name: "SMS Gateway Diagnostics"
    state_topic: "sms-gateway/diagnostics"
    value_template: "{{ value_json.successful_connection | default('failed') }}"
    json_attributes_topic: "sms-gateway/diagnostics"
```

### Diagnostic Files Location

- **Diagnostics JSON**: `/data/sms_gateway_diagnostics.json` - Persistent across restarts, contains structured diagnostic data
- **Detailed Logs**: `/tmp/gammu.log` - Verbose logging with full command outputs and tracebacks
- **MQTT Topic**: `sms-gateway/diagnostics` - Real-time diagnostics available via MQTT

## Configuration

```yaml
device: "/dev/ttyUSB0"           # Modem device path
debug: false                      # Enable detailed logging
notification_on_receive: true     # Show notification for new SMS
```

**Note**: MQTT credentials are automatically fetched from Home Assistant's MQTT integration. Manual MQTT configuration in the add-on options is no longer required.

## Home Assistant Entities

The add-on automatically creates:

- **Binary Sensor**: `binary_sensor.sms_gateway_modem_connected` - Modem status
- **Sensor**: `sensor.sms_gateway_last_message` - Last received message with details
- **Event**: `sms_gateway_message_received` - Triggered on new SMS

## Usage

### Send SMS

```yaml
service: mqtt.publish
data:
  topic: "sms-gateway/outbox"
  payload: '{"number": "+1234567890", "text": "Hello!"}'
```

### Receive SMS (Automation)

```yaml
automation:
  - alias: "Handle incoming SMS"
    trigger:
      - platform: event
        event_type: sms_gateway_message_received
    action:
      - service: notify.mobile_app
        data:
          title: "SMS from {{ trigger.event.data.number }}"
          message: "{{ trigger.event.data.message }}"
```

## MQTT Topics

- **Outbox**: `sms-gateway/outbox` - Send SMS
- **Inbox**: `sms-gateway/inbox` - Receive SMS
- **Diagnostics**: `sms-gateway/diagnostics` - Connection diagnostics and troubleshooting information

## Supported Hardware

- Huawei USB modems (tested with 12d1:1506)
- SIM card with SMS capability
- USB connection to Home Assistant host

## Documentation

For detailed documentation, configuration examples, troubleshooting, and dashboard setup, see [DOCS.md](DOCS.md).

## Support

Issues and feature requests: [GitHub Repository](https://github.com/nnar1o/ha)

---

**Note**: Make sure your SIM card's PIN is disabled for automatic operation.
