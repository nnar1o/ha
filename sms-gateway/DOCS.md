# SMS Gateway Add-on Documentation

This add-on allows you to send and receive SMS messages through a Huawei modem using gammu.
Messages are integrated with Home Assistant via MQTT.

## Features

- Send SMS messages via MQTT
- Receive SMS messages via MQTT
- Supports Huawei modems (12d1:1506)
- Automatic message polling

## MQTT Topics

- `sms-gateway/inbox` - Incoming SMS messages
- `sms-gateway/outbox` - Send SMS messages

## Configuration

The add-on requires USB access to communicate with the modem device at `/dev/ttyUSB0`.

Make sure your Huawei modem is connected and recognized by the system before starting the add-on.

## Usage

### Sending SMS

Publish a JSON message to the `sms-gateway/outbox` topic:

```json
{
  "number": "+1234567890",
  "text": "Your message here"
}
```

### Receiving SMS

Subscribe to the `sms-gateway/inbox` topic to receive incoming SMS messages:

```json
{
  "number": "+1234567890",
  "text": "Received message"
}
```

## Support

For issues and feature requests, please use the GitHub repository:
https://github.com/nnar1o/ha
