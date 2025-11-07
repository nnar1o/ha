# Home Assistant Add-on: SMS Gateway

## About / O dodatku

**English:**
SMS Gateway is a Home Assistant add-on that enables sending and receiving SMS messages through a Huawei USB modem using the Gammu library. It integrates seamlessly with Home Assistant via MQTT, allowing you to automate SMS notifications and process incoming messages.

**Polski:**
SMS Gateway to dodatek do Home Assistant umożliwiający wysyłanie i odbieranie wiadomości SMS przez modem USB Huawei przy użyciu biblioteki Gammu. Integruje się z Home Assistant przez MQTT, pozwalając na automatyzację powiadomień SMS i przetwarzanie wiadomości przychodzących.

## Features / Funkcje

**English:**
- Send SMS messages via MQTT
- Receive SMS messages and publish them to MQTT
- Automatic USB modem detection
- Support for Huawei USB modems
- Message queue for reliable delivery
- Comprehensive error handling and logging
- JSON message format with timestamps
- Automatic reconnection to MQTT broker
- Device connection retry logic

**Polski:**
- Wysyłanie wiadomości SMS przez MQTT
- Odbieranie wiadomości SMS i publikowanie ich przez MQTT
- Automatyczne wykrywanie modemu USB
- Wsparcie dla modemów USB Huawei
- Kolejka wiadomości dla niezawodnego dostarczania
- Kompleksowa obsługa błędów i logowanie
- Format wiadomości JSON z znacznikami czasu
- Automatyczne ponowne łączenie z brokerem MQTT
- Logika ponawiania połączenia z urządzeniem

## Installation / Instalacja

**English:**
1. Add this repository to your Home Assistant add-on store
2. Install the "SMS Gateway" add-on
3. Connect your Huawei USB modem to your Home Assistant device
4. Configure the add-on (see Configuration section)
5. Start the add-on

**Polski:**
1. Dodaj to repozytorium do sklepu z dodatkami Home Assistant
2. Zainstaluj dodatek "SMS Gateway"
3. Podłącz modem USB Huawei do urządzenia z Home Assistant
4. Skonfiguruj dodatek (zobacz sekcję Konfiguracja)
5. Uruchom dodatek

## Configuration / Konfiguracja

**English:**
Add-on configuration:

```yaml
mqtt_host: core-mosquitto
mqtt_port: 1883
mqtt_user: ""
mqtt_password: ""
serial_device: /dev/ttyUSB0
log_level: info
```

### Options

- **mqtt_host** (required): MQTT broker hostname (e.g., `core-mosquitto` for Home Assistant's built-in MQTT broker)
- **mqtt_port** (required): MQTT broker port (default: 1883)
- **mqtt_user** (optional): MQTT username for authentication
- **mqtt_password** (optional): MQTT password for authentication
- **serial_device** (required): Path to the USB modem device (e.g., `/dev/ttyUSB0`)
- **log_level** (optional): Logging level - debug, info, warning, error (default: info)

**Polski:**
Konfiguracja dodatku:

```yaml
mqtt_host: core-mosquitto
mqtt_port: 1883
mqtt_user: ""
mqtt_password: ""
serial_device: /dev/ttyUSB0
log_level: info
```

### Opcje

- **mqtt_host** (wymagane): Nazwa hosta brokera MQTT (np. `core-mosquitto` dla wbudowanego brokera MQTT w Home Assistant)
- **mqtt_port** (wymagane): Port brokera MQTT (domyślnie: 1883)
- **mqtt_user** (opcjonalne): Nazwa użytkownika MQTT do uwierzytelniania
- **mqtt_password** (opcjonalne): Hasło MQTT do uwierzytelniania
- **serial_device** (wymagane): Ścieżka do urządzenia modemu USB (np. `/dev/ttyUSB0`)
- **log_level** (opcjonalne): Poziom logowania - debug, info, warning, error (domyślnie: info)

## Usage / Użytkowanie

**English:**

### Sending SMS Messages

Publish a JSON message to the `sms-gateway/outbox` MQTT topic:

```json
{
  "number": "+48123456789",
  "text": "Hello from Home Assistant!"
}
```

Example automation:

```yaml
automation:
  - alias: "Send SMS Notification"
    trigger:
      - platform: state
        entity_id: binary_sensor.motion_detector
        to: 'on'
    action:
      - service: mqtt.publish
        data:
          topic: "sms-gateway/outbox"
          payload: '{"number": "+48123456789", "text": "Motion detected!"}'
```

### Receiving SMS Messages

Subscribe to the `sms-gateway/inbox` MQTT topic to receive incoming SMS messages. Messages will be published in JSON format:

```json
{
  "number": "+48123456789",
  "text": "Message content",
  "timestamp": "2025-11-07T21:00:00Z"
}
```

Example automation:

```yaml
automation:
  - alias: "Process Incoming SMS"
    trigger:
      - platform: mqtt
        topic: "sms-gateway/inbox"
    action:
      - service: notify.persistent_notification
        data:
          title: "SMS from {{ trigger.payload_json.number }}"
          message: "{{ trigger.payload_json.text }}"
```

**Polski:**

### Wysyłanie wiadomości SMS

Opublikuj wiadomość JSON na temat MQTT `sms-gateway/outbox`:

```json
{
  "number": "+48123456789",
  "text": "Witaj z Home Assistant!"
}
```

Przykładowa automatyzacja:

```yaml
automation:
  - alias: "Wyślij powiadomienie SMS"
    trigger:
      - platform: state
        entity_id: binary_sensor.motion_detector
        to: 'on'
    action:
      - service: mqtt.publish
        data:
          topic: "sms-gateway/outbox"
          payload: '{"number": "+48123456789", "text": "Wykryto ruch!"}'
```

### Odbieranie wiadomości SMS

Subskrybuj temat MQTT `sms-gateway/inbox`, aby odbierać przychodzące wiadomości SMS. Wiadomości będą publikowane w formacie JSON:

```json
{
  "number": "+48123456789",
  "text": "Treść wiadomości",
  "timestamp": "2025-11-07T21:00:00Z"
}
```

Przykładowa automatyzacja:

```yaml
automation:
  - alias: "Przetwórz przychodzący SMS"
    trigger:
      - platform: mqtt
        topic: "sms-gateway/inbox"
    action:
      - service: notify.persistent_notification
        data:
          title: "SMS od {{ trigger.payload_json.number }}"
          message: "{{ trigger.payload_json.text }}"
```

## Troubleshooting / Rozwiązywanie problemów

**English:**

### Common Issues

1. **Modem not detected**
   - Check if the USB modem is properly connected
   - Verify the device path (usually `/dev/ttyUSB0` or `/dev/ttyUSB1`)
   - Check add-on logs for device detection messages
   - Ensure the device is not being used by another service

2. **Cannot connect to MQTT broker**
   - Verify MQTT broker is running
   - Check MQTT credentials if authentication is enabled
   - Ensure the MQTT broker hostname is correct

3. **SMS not sending**
   - Check if the SIM card is properly inserted
   - Verify the SIM card has sufficient credit
   - Check add-on logs for error messages
   - Ensure the phone number format is correct (include country code)

4. **SMS not receiving**
   - Check if the modem can receive SMS (test manually)
   - Verify SIM card is active and can receive messages
   - Check add-on logs for errors

**Polski:**

### Częste problemy

1. **Modem nie został wykryty**
   - Sprawdź, czy modem USB jest prawidłowo podłączony
   - Zweryfikuj ścieżkę urządzenia (zwykle `/dev/ttyUSB0` lub `/dev/ttyUSB1`)
   - Sprawdź logi dodatku dla komunikatów o wykrywaniu urządzenia
   - Upewnij się, że urządzenie nie jest używane przez inną usługę

2. **Nie można połączyć się z brokerem MQTT**
   - Sprawdź, czy broker MQTT jest uruchomiony
   - Sprawdź dane uwierzytelniające MQTT, jeśli uwierzytelnianie jest włączone
   - Upewnij się, że nazwa hosta brokera MQTT jest poprawna

3. **SMS nie jest wysyłany**
   - Sprawdź, czy karta SIM jest prawidłowo włożona
   - Zweryfikuj, czy karta SIM ma wystarczające środki
   - Sprawdź logi dodatku pod kątem komunikatów o błędach
   - Upewnij się, że format numeru telefonu jest poprawny (dodaj kod kraju)

4. **SMS nie jest odbierany**
   - Sprawdź, czy modem może odbierać SMS (przetestuj ręcznie)
   - Zweryfikuj, czy karta SIM jest aktywna i może odbierać wiadomości
   - Sprawdź logi dodatku pod kątem błędów

## Device Compatibility / Kompatybilność urządzeń

**English:**
This add-on is designed to work with Huawei USB modems. It has been tested with:
- Huawei E3131
- Huawei E3372
- Huawei E8372

Other Huawei modems should also work, as well as some other brands that are compatible with Gammu.

**Polski:**
Ten dodatek jest zaprojektowany do pracy z modemami USB Huawei. Został przetestowany z:
- Huawei E3131
- Huawei E3372
- Huawei E8372

Inne modemy Huawei powinny również działać, podobnie jak niektóre inne marki kompatybilne z Gammu.

## Support / Wsparcie

**English:**
- Report issues at: https://github.com/nnar1o/ha/issues
- Home Assistant Community Forum
- Check logs in Home Assistant Supervisor > SMS Gateway > Logs

**Polski:**
- Zgłaszaj problemy na: https://github.com/nnar1o/ha/issues
- Forum społeczności Home Assistant
- Sprawdź logi w Home Assistant Supervisor > SMS Gateway > Logi

## Credits / Podziękowania

**English:**
This add-on uses:
- [Gammu](https://wammu.eu/gammu/) - GNU All Mobile Management Utilities
- [Paho MQTT](https://www.eclipse.org/paho/) - MQTT client library

**Polski:**
Ten dodatek używa:
- [Gammu](https://wammu.eu/gammu/) - GNU All Mobile Management Utilities
- [Paho MQTT](https://www.eclipse.org/paho/) - Biblioteka klienta MQTT
