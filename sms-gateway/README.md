# SMS Gateway Add-on for Home Assistant

Pozwala na wysyłanie i odbieranie SMS-ów przez modem Huawei za pomocą gammu.
Wiadomości trafiają do MQTT (`sms-gateway/inbox` dla odbioru, wysyłka via `sms-gateway/outbox`).

## Konfiguracja

- mqtt_host: adres brokera MQTT (np. core-mosquitto)
- mqtt_port: port brokera (domyślnie 1883)
- mqtt_user, mqtt_password: dane dostępu (opcjonalnie)
- serial_device: ścieżka do modemu (np. /dev/ttyUSB0)

Kod dodatku uruchamia gammu poleceniami CLI, integruje się z Home Assistant przez MQTT.
