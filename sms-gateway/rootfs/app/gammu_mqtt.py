import os
import paho.mqtt.client as mqtt
import subprocess
import time
import json

MQTT_HOST = os.getenv('MQTT_HOST', 'core-mosquitto')
MQTT_PORT = int(os.getenv('MQTT_PORT', '1883'))
MQTT_USER = os.getenv('MQTT_USER', '')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD', '')
DEVICE = os.getenv('SERIAL_DEVICE', '/dev/ttyUSB0')

INBOX_TOPIC = 'sms-gateway/inbox'
OUTBOX_TOPIC = 'sms-gateway/outbox'

def on_connect(client, userdata, flags, rc):
    client.subscribe(OUTBOX_TOPIC)

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload)
        number = payload["number"]
        text = payload["text"]
        subprocess.call([
            "gammu", "--device", DEVICE, "sendsms", "TEXT", number, "-text", text
        ])
    except Exception as e:
        print("Error sending SMS:", e)

def check_inbox(client):
    try:
        result = subprocess.run(
            ["gammu", "--device", DEVICE, "getallsms"], capture_output=True, text=True
        )
        sms_messages = result.stdout.split("SMS message")
        for sms in sms_messages[1:]:
            lines = sms.strip().splitlines()
            number = ""
            text = ""
            for line in lines:
                if "Number :" in line:
                    number = line.split(":")[1].strip()
                elif "Text :" in line:
                    text = line.split(":")[1].strip()
            if number and text:
                client.publish(INBOX_TOPIC, json.dumps({"number": number, "text": text}))
    except Exception as e:
        print("Error checking inbox:", e)

def main():
    client = mqtt.Client()
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_start()

    while True:
        check_inbox(client)
        time.sleep(10)

if __name__ == "__main__":
    main()