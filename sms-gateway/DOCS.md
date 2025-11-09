# SMS Gateway Add-on Documentation

This add-on allows you to send and receive SMS messages through a Huawei modem using gammu.
Messages are integrated with Home Assistant via MQTT and native Home Assistant entities.

## Features

- Send SMS messages via MQTT or Home Assistant automations
- Receive SMS messages via MQTT with automatic notifications
- Supports Huawei modems (12d1:1506)
- Automatic message polling every 10 seconds
- Native Home Assistant integration with sensors and events
- **Automatic MQTT credential fetching** from Home Assistant's MQTT integration
- Detailed logging with timestamps
- Configurable device path and options
- Binary sensor showing modem connection status
- Sensor showing last received message
- Event triggered on each new SMS

## MQTT Configuration

**Important**: The add-on automatically fetches MQTT credentials from Home Assistant's MQTT integration using the Supervisor API. You do **not** need to manually configure MQTT credentials in the add-on options.

The add-on will:
1. Automatically detect if Home Assistant's MQTT integration is configured
2. Fetch the MQTT broker host, port, username, and password
3. Use these credentials to connect to the MQTT broker

If the MQTT service is not available through the Supervisor API, the add-on will fall back to manual configuration from the options (for backward compatibility).

## Configuration Options

The add-on provides the following configuration options:

### `device` (required)
- **Type**: string
- **Default**: `/dev/ttyUSB0`
- **Description**: Path to the modem device. Change this if your modem is connected to a different USB port (e.g., `/dev/ttyUSB1`, `/dev/ttyUSB2`)

### `debug` (optional)
- **Type**: boolean
- **Default**: `false`
- **Description**: Enable debug logging for troubleshooting. When enabled, additional detailed logs will be written.

### `notification_on_receive` (optional)
- **Type**: boolean
- **Default**: `true`
- **Description**: Automatically create a persistent notification in Home Assistant when a new SMS is received.

### Example Configuration

```yaml
device: "/dev/ttyUSB0"
debug: false
notification_on_receive: true
```

## Home Assistant Integration

### Entities Created

The add-on creates the following entities in Home Assistant:

#### 1. Binary Sensor: `binary_sensor.sms_gateway_modem_connected`
- **State**: `on` (connected) or `off` (disconnected)
- **Attributes**:
  - `friendly_name`: SMS Gateway Modem Connected
  - `device`: The device path being monitored
- **Description**: Shows the real-time connection status of the modem

#### 2. Sensor: `sensor.sms_gateway_last_message`
- **State**: The text of the last received message (truncated to 255 characters)
- **Attributes**:
  - `friendly_name`: SMS Gateway Last Message
  - `from_number`: Phone number of the sender
  - `message`: Full message text
  - `timestamp`: When the message was received (YYYY-MM-DD HH:MM:SS)
- **Description**: Contains the details of the most recently received SMS

#### 3. Event: `sms_gateway_message_received`
- **Event Data**:
  - `number`: Phone number of the sender
  - `message`: Full message text
  - `timestamp`: When the message was received
- **Description**: Fired whenever a new SMS is received. Use this in automations to trigger actions.

## MQTT Topics

The add-on continues to support MQTT for backward compatibility:

### Outbox Topic: `sms-gateway/outbox`
- **Purpose**: Send SMS messages
- **Format**: JSON

### Inbox Topic: `sms-gateway/inbox`
- **Purpose**: Receive SMS messages
- **Format**: JSON

## Usage Examples

### Sending SMS

#### Method 1: Using MQTT (recommended for integrations)

Publish a JSON message to the `sms-gateway/outbox` topic:

```json
{
  "number": "+1234567890",
  "text": "Your message here"
}
```

Example using Home Assistant's MQTT publish service:

```yaml
service: mqtt.publish
data:
  topic: "sms-gateway/outbox"
  payload: '{"number": "+1234567890", "text": "Hello from Home Assistant!"}'
```

#### Method 2: Using Home Assistant Automation

```yaml
automation:
  - alias: "Send SMS on button press"
    trigger:
      - platform: state
        entity_id: input_boolean.send_sms_trigger
        to: "on"
    action:
      - service: mqtt.publish
        data:
          topic: "sms-gateway/outbox"
          payload: '{"number": "+1234567890", "text": "Button was pressed!"}'
```

### Receiving SMS

#### Method 1: Using MQTT Subscription

Subscribe to the `sms-gateway/inbox` topic to receive incoming SMS messages:

```json
{
  "number": "+1234567890",
  "text": "Received message"
}
```

#### Method 2: Using Home Assistant Event (recommended)

Listen for the `sms_gateway_message_received` event in an automation:

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

#### Method 3: Using MQTT in Automation

```yaml
automation:
  - alias: "React to SMS keyword"
    trigger:
      - platform: mqtt
        topic: "sms-gateway/inbox"
    condition:
      - condition: template
        value_template: "{{ 'STATUS' in trigger.payload_json.text }}"
    action:
      - service: mqtt.publish
        data:
          topic: "sms-gateway/outbox"
          payload: >
            {"number": "{{ trigger.payload_json.number }}", 
             "text": "System is operational"}
```

### Dashboard Configuration

Create a user-friendly dashboard to monitor and control SMS Gateway:

```yaml
type: entities
title: "SMS Gateway"
entities:
  - entity: binary_sensor.sms_gateway_modem_connected
    name: "Modem Status"
  - entity: sensor.sms_gateway_last_message
    name: "Last Message"
  - type: section
  - entity: script.send_test_sms
    name: "Send Test SMS"
```

Example script for sending SMS from the dashboard:

```yaml
script:
  send_test_sms:
    alias: "Send Test SMS"
    sequence:
      - service: mqtt.publish
        data:
          topic: "sms-gateway/outbox"
          payload: '{"number": "+1234567890", "text": "Test message from HA"}'
```

### Advanced Dashboard with Input Fields

For a more interactive dashboard:

```yaml
# In configuration.yaml
input_text:
  sms_phone_number:
    name: "Phone Number"
    initial: "+1234567890"
  sms_message:
    name: "Message"
    max: 160

script:
  send_custom_sms:
    alias: "Send SMS"
    sequence:
      - service: mqtt.publish
        data:
          topic: "sms-gateway/outbox"
          payload: >
            {"number": "{{ states('input_text.sms_phone_number') }}", 
             "text": "{{ states('input_text.sms_message') }}"}
```

Dashboard card:

```yaml
type: vertical-stack
cards:
  - type: entities
    entities:
      - binary_sensor.sms_gateway_modem_connected
      - sensor.sms_gateway_last_message
  - type: entities
    entities:
      - input_text.sms_phone_number
      - input_text.sms_message
      - script.send_custom_sms
```

## Logging

The add-on provides detailed logging for all SMS operations:

### SMS Received Logs
```
INFO - SMS Received - From: +1234567890
INFO - Time: 2025-11-07 22:15:30
INFO - Message: Hello, this is a test message
```

### SMS Sent Logs
```
INFO - SMS Sent Successfully - To: +1234567890
INFO - Time: 2025-11-07 22:16:45
INFO - Message: Response message
```

### Error Logs
```
ERROR - SMS Send Failed - To: +1234567890
ERROR - Time: 2025-11-07 22:17:00
ERROR - Message: Failed to send
ERROR - Gammu error: Device not found
```

To view logs, go to the add-on page in Home Assistant and click on the "Log" tab.

## Troubleshooting

### Modem Not Detected

**Problem**: The binary sensor shows the modem as disconnected, or you see "Device not found" errors.

**Solutions**:
1. Check that your modem is properly connected via USB
2. Verify the device path in the configuration (try `/dev/ttyUSB1` or `/dev/ttyUSB2`)
3. Check the add-on logs for specific error messages
4. Enable debug mode in the configuration for more detailed logs
5. Restart the add-on after making configuration changes

### Messages Not Being Received

**Problem**: Outgoing SMS works, but incoming messages aren't showing up.

**Solutions**:
1. Check that the modem is connected (see binary sensor status)
2. Verify that messages are actually arriving on your SIM card (test with a phone)
3. Check the add-on logs for errors during inbox polling
4. The add-on polls for messages every 10 seconds, so there may be a slight delay
5. Enable debug mode to see detailed polling information

### Messages Not Being Sent

**Problem**: MQTT publish succeeds but SMS is not sent.

**Solutions**:
1. Verify the modem is connected and responsive
2. Check that the phone number format is correct (include country code, e.g., `+1234567890`)
3. Review the add-on logs for gammu errors
4. Check that your SIM card has sufficient credit
5. Ensure the SIM card's PIN is disabled

### MQTT Connection Issues

**Problem**: Add-on can't connect to MQTT broker.

**Solutions**:
1. Verify that the Mosquitto broker add-on is installed and running
2. Ensure Home Assistant's MQTT integration is properly configured
3. Check the add-on logs to see if MQTT credentials were fetched successfully
4. If automatic credential fetching fails, you can manually configure MQTT in the add-on options as a fallback
5. Review the add-on logs for connection errors
6. Ensure the MQTT broker is accessible from the add-on

### Configuration Changes Not Taking Effect

**Problem**: After changing configuration, the add-on still uses old settings.

**Solution**: Always restart the add-on after making configuration changes.

### Debugging Steps

1. **Enable debug mode**: Set `debug: true` in the add-on configuration and restart
2. **Check logs**: View the add-on logs for detailed error messages
3. **Test modem**: The add-on attempts to identify the modem on startup
4. **Test MQTT**: Use MQTT Explorer or similar tool to verify message flow
5. **Check entities**: Verify that sensors are created in Home Assistant Developer Tools > States

## Device Requirements

- Huawei USB modem (tested with 12d1:1506)
- USB connection to Home Assistant host
- SIM card with SMS capability
- SIM card PIN should be disabled for automatic operation

## Support

For issues and feature requests, please use the GitHub repository:
https://github.com/nnar1o/ha

When reporting issues, please include:
1. Add-on version
2. Home Assistant version
3. Modem model
4. Relevant log entries (with debug mode enabled)
5. Configuration (without sensitive data)
