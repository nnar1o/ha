# SMS Gateway Add-on Documentation

## Overview / Przegląd

**English:**
The SMS Gateway add-on enables Home Assistant to send and receive SMS messages through a Huawei modem (ID 12d1:1506) using gammu. Messages are integrated with Home Assistant through MQTT topics, allowing automation and notifications via SMS.

**Polski:**
Dodatek SMS Gateway umożliwia Home Assistant wysyłanie i odbieranie wiadomości SMS przez modem Huawei (ID 12d1:1506) przy użyciu gammu. Wiadomości są zintegrowane z Home Assistant poprzez tematy MQTT, umożliwiając automatyzację i powiadomienia przez SMS.

---

## Features / Funkcje

**English:**
- Send SMS messages via MQTT
- Receive SMS messages and publish to MQTT
- Automatic device detection with udev rules
- Message queue for reliable delivery
- Error handling and logging
- JSON message format with timestamp
- Specific support for Huawei modem (12d1:1506)

**Polski:**
- Wysyłanie wiadomości SMS przez MQTT
- Odbieranie wiadomości SMS i publikowanie do MQTT
- Automatyczne wykrywanie urządzenia z regułami udev
- Kolejka wiadomości dla niezawodnego dostarczania
- Obsługa błędów i logowanie
- Format wiadomości JSON z znacznikiem czasu
- Specjalne wsparcie dla modemu Huawei (12d1:1506)

---

## Configuration / Konfiguracja

### Options / Opcje

#### `mqtt_host` (required/wymagane)
**English:** MQTT broker hostname or IP address (e.g., "core-mosquitto" for Home Assistant's built-in broker)

**Polski:** Nazwa hosta lub adres IP brokera MQTT (np. "core-mosquitto" dla wbudowanego brokera Home Assistant)

#### `mqtt_port` (required/wymagane)
**English:** MQTT broker port (default: 1883)

**Polski:** Port brokera MQTT (domyślnie: 1883)

#### `mqtt_user` (optional/opcjonalne)
**English:** MQTT username for authentication (leave empty if not required)

**Polski:** Nazwa użytkownika MQTT do uwierzytelniania (pozostaw puste, jeśli nie jest wymagane)

#### `mqtt_password` (optional/opcjonalne)
**English:** MQTT password for authentication (leave empty if not required)

**Polski:** Hasło MQTT do uwierzytelniania (pozostaw puste, jeśli nie jest wymagane)

#### `serial_device` (required/wymagane)
**English:** Path to the modem device (default: /dev/ttyUSB0)

**Polski:** Ścieżka do urządzenia modemu (domyślnie: /dev/ttyUSB0)

#### `log_level` (optional/opcjonalne)
**English:** Logging level: DEBUG, INFO, WARNING, ERROR (default: INFO)

**Polski:** Poziom logowania: DEBUG, INFO, WARNING, ERROR (domyślnie: INFO)

### Example Configuration / Przykładowa Konfiguracja

```yaml
mqtt_host: core-mosquitto
mqtt_port: 1883
mqtt_user: "homeassistant"
mqtt_password: "your_password"
serial_device: /dev/ttyUSB0
log_level: INFO
```

---

## MQTT Topics / Tematy MQTT

### Sending SMS / Wysyłanie SMS

**Topic:** `sms-gateway/outbox`

**English:** Publish a JSON message to this topic to send an SMS.

**Polski:** Opublikuj wiadomość JSON do tego tematu, aby wysłać SMS.

**Message Format / Format wiadomości:**
```json
{
  "number": "+48123456789",
  "text": "Hello, this is a test message"
}
```

### Receiving SMS / Odbieranie SMS

**Topic:** `sms-gateway/inbox`

**English:** Subscribe to this topic to receive incoming SMS messages.

**Polski:** Subskrybuj ten temat, aby otrzymywać przychodzące wiadomości SMS.

**Message Format / Format wiadomości:**
```json
{
  "number": "+48123456789",
  "text": "Received message content",
  "timestamp": "2025-11-07T21:08:41Z"
}
```

---

## Hardware Requirements / Wymagania sprzętowe

**English:**
- Huawei USB modem with ID 12d1:1506
- USB port available on the Home Assistant host
- Active SIM card with SMS capability

**Polski:**
- Modem USB Huawei z ID 12d1:1506
- Dostępny port USB na hoście Home Assistant
- Aktywna karta SIM z możliwością SMS

---

## Installation / Instalacja

**English:**
1. Add this repository to your Home Assistant add-on store
2. Install the SMS Gateway add-on
3. Connect your Huawei modem to the USB port
4. Configure the add-on with your MQTT settings
5. Start the add-on

**Polski:**
1. Dodaj to repozytorium do sklepu z dodatkami Home Assistant
2. Zainstaluj dodatek SMS Gateway
3. Podłącz modem Huawei do portu USB
4. Skonfiguruj dodatek z ustawieniami MQTT
5. Uruchom dodatek

---

## Automation Examples / Przykłady automatyzacji

### Sending SMS / Wysyłanie SMS

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
          payload: >
            {
              "number": "+48123456789",
              "text": "ALARM! Home security triggered at {{ now().strftime('%H:%M') }}"
            }
```

### Receiving SMS / Odbieranie SMS

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

---

## Troubleshooting / Rozwiązywanie problemów

### Device not found / Urządzenie nie znalezione

**English:**
- Check if the modem is properly connected
- Verify the device path in configuration (usually /dev/ttyUSB0 or /dev/ttyUSB1)
- Check add-on logs for device detection messages
- Ensure udev rules are properly loaded

**Polski:**
- Sprawdź, czy modem jest prawidłowo podłączony
- Zweryfikuj ścieżkę urządzenia w konfiguracji (zwykle /dev/ttyUSB0 lub /dev/ttyUSB1)
- Sprawdź logi dodatku w celu wykrycia komunikatów o urządzeniu
- Upewnij się, że reguły udev są prawidłowo załadowane

### Cannot connect to MQTT / Nie można połączyć się z MQTT

**English:**
- Verify MQTT broker is running
- Check MQTT host and port configuration
- Verify MQTT credentials if authentication is enabled
- Check network connectivity

**Polski:**
- Sprawdź, czy broker MQTT działa
- Sprawdź konfigurację hosta i portu MQTT
- Zweryfikuj dane logowania MQTT, jeśli uwierzytelnianie jest włączone
- Sprawdź łączność sieciową

### Messages not being sent / Wiadomości nie są wysyłane

**English:**
- Check if SIM card has sufficient credit/balance
- Verify phone number format (use international format with +)
- Check add-on logs for error messages
- Ensure modem has network signal

**Polski:**
- Sprawdź, czy karta SIM ma wystarczające środki/saldo
- Zweryfikuj format numeru telefonu (użyj formatu międzynarodowego z +)
- Sprawdź logi dodatku w celu wykrycia komunikatów o błędach
- Upewnij się, że modem ma sygnał sieci

---

## Support / Wsparcie

**English:**
For issues, questions, or contributions, please visit:
https://github.com/nnar1o/ha

**Polski:**
W przypadku problemów, pytań lub wkładów, odwiedź:
https://github.com/nnar1o/ha
