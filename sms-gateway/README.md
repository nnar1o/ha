# SMS Gateway Add-on for Home Assistant

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)

![Supports aarch64 Architecture][aarch64-shield]
![Supports amd64 Architecture][amd64-shield]
![Supports armhf Architecture][armhf-shield]
![Supports armv7 Architecture][armv7-shield]
![Supports i386 Architecture][i386-shield]

## About / O dodatku

**English:**

The SMS Gateway add-on enables Home Assistant to send and receive SMS messages through a Huawei USB modem (ID 12d1:1506). It provides seamless integration with Home Assistant's automation system via MQTT, allowing you to:

- Send SMS notifications for alerts and events
- Receive SMS messages and trigger automations
- Control Home Assistant via SMS commands
- Get status updates via SMS

**Polski:**

Dodatek SMS Gateway umożliwia Home Assistant wysyłanie i odbieranie wiadomości SMS przez modem USB Huawei (ID 12d1:1506). Zapewnia płynną integrację z systemem automatyzacji Home Assistant poprzez MQTT, umożliwiając:

- Wysyłanie powiadomień SMS o alertach i zdarzeniach
- Odbieranie wiadomości SMS i wyzwalanie automatyzacji
- Sterowanie Home Assistant za pomocą poleceń SMS
- Otrzymywanie aktualizacji statusu przez SMS

## Features / Funkcje

- ✅ Send SMS messages via MQTT
- ✅ Receive SMS messages and publish to MQTT
- ✅ Automatic device detection with udev rules
- ✅ Message queue for reliable delivery
- ✅ Comprehensive error handling and logging
- ✅ JSON message format with timestamps
- ✅ Specific support for Huawei modem (12d1:1506)
- ✅ Based on Alpine Linux for minimal footprint
- ✅ Uses gammu for robust modem communication

## Hardware Requirements / Wymagania sprzętowe

- Huawei USB modem with ID 12d1:1506 (e.g., Huawei E173)
- USB port available on the Home Assistant host
- Active SIM card with SMS capability
- USB passthrough configured in Home Assistant (Supervisor → System → Hardware)

## Installation / Instalacja

### Method 1: Add Repository / Metoda 1: Dodaj repozytorium

1. Navigate to **Supervisor** → **Add-on Store** in Home Assistant
2. Click on the menu (⋮) in the top right corner
3. Select **Repositories**
4. Add this repository URL: `https://github.com/nnar1o/ha`
5. Find **SMS Gateway** in the add-on list
6. Click **INSTALL**

### Method 2: Manual / Metoda 2: Ręczna

If you're running Home Assistant in a development environment, you can install manually by copying the `sms-gateway` folder to your add-ons directory.

## Configuration / Konfiguracja

Example configuration:

```yaml
mqtt_host: core-mosquitto
mqtt_port: 1883
mqtt_user: "homeassistant"
mqtt_password: "your_password"
serial_device: /dev/ttyUSB0
log_level: INFO
```

**Note:** Make sure to configure USB passthrough in Home Assistant to make the modem accessible to the add-on.

For detailed configuration options, see [DOCS.md](DOCS.md).

## Usage / Użycie

### Sending SMS / Wysyłanie SMS

Publish a JSON message to the `sms-gateway/outbox` topic:

```json
{
  "number": "+48123456789",
  "text": "Hello from Home Assistant!"
}
```

Example automation:

```yaml
automation:
  - alias: "Send SMS on alarm"
    trigger:
      - platform: state
        entity_id: alarm_control_panel.home
        to: "triggered"
    action:
      - service: mqtt.publish
        data:
          topic: "sms-gateway/outbox"
          payload: '{"number": "+48123456789", "text": "ALARM triggered!"}'
```

### Receiving SMS / Odbieranie SMS

Subscribe to the `sms-gateway/inbox` topic to receive incoming messages:

```yaml
automation:
  - alias: "Process incoming SMS"
    trigger:
      - platform: mqtt
        topic: "sms-gateway/inbox"
    action:
      - service: notify.persistent_notification
        data:
          title: "SMS from {{ trigger.payload_json.number }}"
          message: "{{ trigger.payload_json.text }}"
```

## MQTT Topics / Tematy MQTT

- `sms-gateway/outbox` - Publish here to send SMS
- `sms-gateway/inbox` - Subscribe here to receive SMS
- `sms-gateway/status` - Add-on status (online/offline)
- `sms-gateway/status/send` - Send status notifications

## Documentation / Dokumentacja

For complete documentation including troubleshooting and advanced features, see [DOCS.md](DOCS.md).

## Support / Wsparcie

For issues, questions, or contributions:
- GitHub Issues: https://github.com/nnar1o/ha/issues
- Repository: https://github.com/nnar1o/ha

## License / Licencja

MIT License - see LICENSE file for details

[releases-shield]: https://img.shields.io/github/release/nnar1o/ha.svg
[releases]: https://github.com/nnar1o/ha/releases
[license-shield]: https://img.shields.io/github/license/nnar1o/ha.svg
[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
[armhf-shield]: https://img.shields.io/badge/armhf-yes-green.svg
[armv7-shield]: https://img.shields.io/badge/armv7-yes-green.svg
[i386-shield]: https://img.shields.io/badge/i386-yes-green.svg
