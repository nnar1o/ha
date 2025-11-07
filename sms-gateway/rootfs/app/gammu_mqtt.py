import os
import paho.mqtt.client as mqtt
import subprocess
import time
import json
import logging
import sys
import requests
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
_LOGGER = logging.getLogger(__name__)

# Environment variables
MQTT_HOST = os.getenv('MQTT_HOST', 'core-mosquitto')
MQTT_PORT = int(os.getenv('MQTT_PORT', '1883'))
MQTT_USER = os.getenv('MQTT_USER', '')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD', '')

# Configuration from add-on options
OPTIONS_PATH = '/data/options.json'
try:
    with open(OPTIONS_PATH) as f:
        options = json.load(f)
        DEVICE = options.get('device', '/dev/ttyUSB0')
        DEBUG = options.get('debug', False)
        NOTIFICATION_ON_RECEIVE = options.get('notification_on_receive', True)
except FileNotFoundError:
    _LOGGER.warning(f"Options file not found at {OPTIONS_PATH}, using defaults")
    DEVICE = os.getenv('SERIAL_DEVICE', '/dev/ttyUSB0')
    DEBUG = False
    NOTIFICATION_ON_RECEIVE = True

# Set debug level if enabled
if DEBUG:
    _LOGGER.setLevel(logging.DEBUG)
    _LOGGER.debug("Debug mode enabled")

# MQTT Topics
INBOX_TOPIC = 'sms-gateway/inbox'
OUTBOX_TOPIC = 'sms-gateway/outbox'

# Home Assistant settings
SUPERVISOR_TOKEN = os.getenv('SUPERVISOR_TOKEN', '')
HA_URL = 'http://supervisor/core/api'

# State tracking
last_message = {"number": "", "text": "", "timestamp": ""}
modem_connected = False

def log_sms_received(number, message):
    """Log detailed information about received SMS"""
    _LOGGER.info(f"SMS Received - From: {number}")
    _LOGGER.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    _LOGGER.info(f"Message: {message}")

def log_sms_sent(number, message, success=True):
    """Log detailed information about sent SMS"""
    status = "Sent Successfully" if success else "Send Failed"
    level = _LOGGER.info if success else _LOGGER.error
    level(f"SMS {status} - To: {number}")
    level(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    level(f"Message: {message}")

def update_ha_sensor(entity_id, state, attributes=None):
    """Update Home Assistant sensor via API"""
    if not SUPERVISOR_TOKEN:
        _LOGGER.debug("No supervisor token available, skipping HA sensor update")
        return
    
    headers = {
        'Authorization': f'Bearer {SUPERVISOR_TOKEN}',
        'Content-Type': 'application/json',
    }
    
    data = {
        'state': state,
        'attributes': attributes or {}
    }
    
    try:
        response = requests.post(
            f'{HA_URL}/states/{entity_id}',
            headers=headers,
            json=data,
            timeout=5
        )
        if response.status_code == 200 or response.status_code == 201:
            _LOGGER.debug(f"Updated {entity_id} to state: {state}")
        else:
            _LOGGER.warning(f"Failed to update {entity_id}: {response.status_code}")
    except Exception as e:
        _LOGGER.debug(f"Error updating HA sensor {entity_id}: {e}")

def fire_ha_event(event_type, event_data):
    """Fire an event in Home Assistant"""
    if not SUPERVISOR_TOKEN:
        _LOGGER.debug("No supervisor token available, skipping HA event")
        return
    
    headers = {
        'Authorization': f'Bearer {SUPERVISOR_TOKEN}',
        'Content-Type': 'application/json',
    }
    
    try:
        response = requests.post(
            f'{HA_URL}/events/{event_type}',
            headers=headers,
            json=event_data,
            timeout=5
        )
        if response.status_code == 200 or response.status_code == 201:
            _LOGGER.debug(f"Fired event {event_type}")
        else:
            _LOGGER.warning(f"Failed to fire event {event_type}: {response.status_code}")
    except Exception as e:
        _LOGGER.debug(f"Error firing HA event {event_type}: {e}")

def send_ha_notification(title, message):
    """Send a persistent notification in Home Assistant"""
    if not SUPERVISOR_TOKEN:
        _LOGGER.debug("No supervisor token available, skipping notification")
        return
    
    headers = {
        'Authorization': f'Bearer {SUPERVISOR_TOKEN}',
        'Content-Type': 'application/json',
    }
    
    data = {
        'title': title,
        'message': message
    }
    
    try:
        response = requests.post(
            f'{HA_URL}/services/persistent_notification/create',
            headers=headers,
            json=data,
            timeout=5
        )
        if response.status_code == 200 or response.status_code == 201:
            _LOGGER.debug(f"Sent notification: {title}")
    except Exception as e:
        _LOGGER.debug(f"Error sending HA notification: {e}")

def check_modem_status():
    """Check if modem is connected and responsive"""
    global modem_connected
    try:
        result = subprocess.run(
            ["gammu", "--device", DEVICE, "identify"],
            capture_output=True,
            text=True,
            timeout=10
        )
        connected = result.returncode == 0
        
        if connected != modem_connected:
            modem_connected = connected
            status = "connected" if connected else "disconnected"
            _LOGGER.info(f"Modem status changed: {status}")
            update_ha_sensor(
                'binary_sensor.sms_gateway_modem_connected',
                'on' if connected else 'off',
                {'friendly_name': 'SMS Gateway Modem Connected', 'device': DEVICE}
            )
        
        return connected
    except Exception as e:
        if modem_connected:
            modem_connected = False
            _LOGGER.error(f"Error checking modem status: {e}")
            update_ha_sensor(
                'binary_sensor.sms_gateway_modem_connected',
                'off',
                {'friendly_name': 'SMS Gateway Modem Connected', 'device': DEVICE}
            )
        return False

def on_connect(client, userdata, flags, rc):
    """MQTT connection callback"""
    if rc == 0:
        _LOGGER.info("Connected to MQTT broker")
        client.subscribe(OUTBOX_TOPIC)
        _LOGGER.info(f"Subscribed to {OUTBOX_TOPIC}")
    else:
        _LOGGER.error(f"Failed to connect to MQTT broker, return code: {rc}")

def on_message(client, userdata, msg):
    """MQTT message callback for sending SMS"""
    try:
        payload = json.loads(msg.payload)
        number = payload["number"]
        text = payload["text"]
        
        _LOGGER.info(f"Sending SMS to {number}")
        result = subprocess.run(
            ["gammu", "--device", DEVICE, "sendsms", "TEXT", number, "-text", text],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        success = result.returncode == 0
        log_sms_sent(number, text, success)
        
        if not success:
            _LOGGER.error(f"Gammu error: {result.stderr}")
            
    except json.JSONDecodeError as e:
        _LOGGER.error(f"Invalid JSON in MQTT message: {e}")
    except KeyError as e:
        _LOGGER.error(f"Missing required field in MQTT message: {e}")
    except Exception as e:
        _LOGGER.error(f"Error sending SMS: {e}")

def check_inbox(client):
    """Check for incoming SMS messages"""
    global last_message
    
    if not check_modem_status():
        _LOGGER.debug("Modem not connected, skipping inbox check")
        return
    
    try:
        result = subprocess.run(
            ["gammu", "--device", DEVICE, "getallsms"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            _LOGGER.debug("No messages or error getting messages")
            return
            
        sms_messages = result.stdout.split("SMS message")
        for sms in sms_messages[1:]:
            lines = sms.strip().splitlines()
            number = ""
            text = ""
            location = ""
            
            for line in lines:
                if "Number :" in line:
                    number = line.split(":", 1)[1].strip()
                elif "Text :" in line:
                    text = line.split(":", 1)[1].strip()
                elif "Location" in line:
                    location = line.split(":", 1)[1].strip()
                    
            if number and text:
                # Log the received SMS
                log_sms_received(number, text)
                
                # Publish to MQTT
                message_data = {"number": number, "text": text}
                client.publish(INBOX_TOPIC, json.dumps(message_data))
                
                # Update last message sensor
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                last_message = {
                    "number": number,
                    "text": text,
                    "timestamp": timestamp
                }
                
                update_ha_sensor(
                    'sensor.sms_gateway_last_message',
                    text[:255],  # State limited to 255 chars
                    {
                        'friendly_name': 'SMS Gateway Last Message',
                        'from_number': number,
                        'message': text,
                        'timestamp': timestamp
                    }
                )
                
                # Fire event in Home Assistant
                fire_ha_event(
                    'sms_gateway_message_received',
                    {
                        'number': number,
                        'message': text,
                        'timestamp': timestamp
                    }
                )
                
                # Send notification if enabled
                if NOTIFICATION_ON_RECEIVE:
                    send_ha_notification(
                        f"SMS from {number}",
                        text
                    )
                
                # Delete the message after processing
                if location:
                    try:
                        subprocess.run(
                            ["gammu", "--device", DEVICE, "deletesms", "1", location],
                            capture_output=True,
                            timeout=10
                        )
                        _LOGGER.debug(f"Deleted SMS at location {location}")
                    except Exception as e:
                        _LOGGER.warning(f"Error deleting SMS: {e}")
                        
    except subprocess.TimeoutExpired:
        _LOGGER.warning("Timeout while checking inbox")
    except Exception as e:
        _LOGGER.error(f"Error checking inbox: {e}")

def register_ha_service():
    """Register the send_sms service with Home Assistant"""
    if not SUPERVISOR_TOKEN:
        _LOGGER.info("No supervisor token available, skipping service registration")
        return
    
    _LOGGER.info("Service registration via API not directly available")
    _LOGGER.info("Users should create automations using MQTT or Node-RED")

def main():
    """Main application loop"""
    _LOGGER.info(f"Starting SMS Gateway with device: {DEVICE}")
    _LOGGER.info(f"Debug mode: {DEBUG}")
    _LOGGER.info(f"Notifications on receive: {NOTIFICATION_ON_RECEIVE}")
    
    # Initial modem check
    if check_modem_status():
        _LOGGER.info("Modem is connected and ready")
    else:
        _LOGGER.warning("Modem is not responding, will retry...")
    
    # Setup MQTT
    client = mqtt.Client()
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.loop_start()
    except Exception as e:
        _LOGGER.error(f"Failed to connect to MQTT broker: {e}")
        return
    
    # Register HA service (info only)
    register_ha_service()
    
    # Initialize sensors
    update_ha_sensor(
        'binary_sensor.sms_gateway_modem_connected',
        'on' if modem_connected else 'off',
        {'friendly_name': 'SMS Gateway Modem Connected', 'device': DEVICE}
    )
    
    update_ha_sensor(
        'sensor.sms_gateway_last_message',
        'unknown',
        {'friendly_name': 'SMS Gateway Last Message'}
    )
    
    # Main loop
    _LOGGER.info("Starting message polling loop")
    while True:
        check_inbox(client)
        time.sleep(10)

if __name__ == "__main__":
    main()