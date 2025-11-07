# Home Assistant Add-on: SMS Gateway

![Supports aarch64 Architecture][aarch64-shield]
![Supports amd64 Architecture][amd64-shield]
![Supports armhf Architecture][armhf-shield]
![Supports armv7 Architecture][armv7-shield]
![Supports i386 Architecture][i386-shield]

## About

SMS Gateway is a Home Assistant add-on that enables sending and receiving SMS messages through a Huawei USB modem using the Gammu library. It provides seamless integration with Home Assistant via MQTT.

**English:**
This add-on allows you to send and receive SMS messages through a Huawei USB modem using Gammu. Messages are integrated with Home Assistant through MQTT (`sms-gateway/inbox` for receiving, `sms-gateway/outbox` for sending).

**Polski:**
Ten dodatek pozwala na wysyłanie i odbieranie wiadomości SMS przez modem Huawei USB za pomocą Gammu. Wiadomości są zintegrowane z Home Assistant przez MQTT (`sms-gateway/inbox` dla odbierania, `sms-gateway/outbox` dla wysyłania).

## Features

- 📱 Send SMS messages via MQTT
- 📬 Receive SMS messages and publish to MQTT
- 🔄 Automatic USB modem detection
- 🔌 Support for Huawei USB modems
- 📊 Message queue for reliable delivery
- 🛡️ Comprehensive error handling and logging
- ⏰ JSON message format with timestamps
- 🔁 Automatic reconnection to MQTT broker
- 🔧 Device connection retry logic

## Installation

1. Add this repository to your Home Assistant add-on store:
   - Navigate to **Supervisor** → **Add-on Store** → **⋮** → **Repositories**
   - Add: `https://github.com/nnar1o/ha`

2. Install the "SMS Gateway" add-on

3. Connect your Huawei USB modem to your Home Assistant device

4. Configure the add-on (see Configuration section)

5. Start the add-on

## Configuration

Example configuration:

```yaml
mqtt_host: core-mosquitto
mqtt_port: 1883
mqtt_user: ""
mqtt_password: ""
serial_device: /dev/ttyUSB0
log_level: info
```

### Options

- **mqtt_host** (required): MQTT broker hostname
- **mqtt_port** (required): MQTT broker port (default: 1883)
- **mqtt_user** (optional): MQTT username
- **mqtt_password** (optional): MQTT password
- **serial_device** (required): Path to USB modem device
- **log_level** (optional): Logging level (debug, info, warning, error)

## Usage

### Sending SMS

Publish to `sms-gateway/outbox`:

```json
{
  "number": "+48123456789",
  "text": "Hello from Home Assistant!"
}
```

### Receiving SMS

Subscribe to `sms-gateway/inbox`:

```json
{
  "number": "+48123456789",
  "text": "Message content",
  "timestamp": "2025-11-07T21:00:00Z"
}
```

## Documentation

For full documentation, including troubleshooting and automation examples, see [DOCS.md](DOCS.md).

## Support

- Issues: https://github.com/nnar1o/ha/issues
- Home Assistant Community Forum
- Add-on logs in Supervisor

## Credits

Built with:
- [Gammu](https://wammu.eu/gammu/) - Mobile Management Utilities
- [Paho MQTT](https://www.eclipse.org/paho/) - MQTT client library

[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
[armhf-shield]: https://img.shields.io/badge/armhf-yes-green.svg
[armv7-shield]: https://img.shields.io/badge/armv7-yes-green.svg
[i386-shield]: https://img.shields.io/badge/i386-yes-green.svg

