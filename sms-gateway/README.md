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

## Quick Start

1. **Install the add-on** from the Add-on Store
2. **Configure** the device path (usually `/dev/ttyUSB0`)
3. **Connect** your Huawei modem via USB
4. **Start** the add-on
5. **Check status** using `binary_sensor.sms_gateway_modem_connected`

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
