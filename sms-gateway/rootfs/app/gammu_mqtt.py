import os
import paho.mqtt.client as mqtt
import subprocess
import time
import json
import logging
import sys
import requests
import gammu
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
_LOGGER = logging.getLogger(__name__)

def get_version():
    """Get version from version.txt file"""
    try:
        with open('/app/version.txt', 'r') as f:
            return f.read().strip()
    except:
        return "unknown"

# Constants for modem retry logic
MAX_RETRIES = 5
RETRY_DELAY = 5  # seconds

# Configuration from add-on options
OPTIONS_PATH = '/data/options.json'
try:
    with open(OPTIONS_PATH) as f:
        options = json.load(f)
        DEVICE = options.get('device', '/dev/ttyUSB0')
        DEBUG = options.get('debug', False)
        NOTIFICATION_ON_RECEIVE = options.get('notification_on_receive', True)
        
        # MQTT configuration from options
        mqtt_config = options.get('mqtt', {})
        MQTT_HOST = mqtt_config.get('broker', 'core-mosquitto')
        MQTT_PORT = int(mqtt_config.get('port', 1883))
        MQTT_USER = mqtt_config.get('username', '')
        MQTT_PASSWORD = mqtt_config.get('password', '')
except FileNotFoundError:
    _LOGGER.warning(f"Options file not found at {OPTIONS_PATH}, using defaults")
    DEVICE = os.getenv('SERIAL_DEVICE', '/dev/ttyUSB0')
    DEBUG = False
    NOTIFICATION_ON_RECEIVE = True
    # Fallback to environment variables for MQTT
    MQTT_HOST = os.getenv('MQTT_HOST', 'core-mosquitto')
    MQTT_PORT = int(os.getenv('MQTT_PORT', '1883'))
    MQTT_USER = os.getenv('MQTT_USER', '')
    MQTT_PASSWORD = os.getenv('MQTT_PASSWORD', '')

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
    """Log SMS sending attempt with timestamp"""
    status = "Successfully sent" if success else "Failed to send"
    _LOGGER.info(f"SMS {status} - To: {number}")
    _LOGGER.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    _LOGGER.info(f"Message: {message}")

def connect_modem():
    """Connect to modem with retry logic"""
    for attempt in range(MAX_RETRIES):
        try:
            _LOGGER.info(f"Attempting to connect to modem (attempt {attempt + 1}/{MAX_RETRIES})")
            state_machine = gammu.StateMachine()
            state_machine.ReadConfig(0)
            state_machine.Init()
            _LOGGER.info("Successfully connected to modem")
            return state_machine
        except gammu.ERR_DEVICENOTEXIST:
            _LOGGER.warning(f"Modem not found at {DEVICE}, will retry in {RETRY_DELAY} seconds...")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
        except Exception as e:
            _LOGGER.warning(f"Error connecting to modem: {e}, will retry in {RETRY_DELAY} seconds...")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
    raise Exception("Failed to connect to modem after maximum retries")

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

def send_sms(number, message):
    """Send SMS with proper logging"""
    try:
        _LOGGER.info(f"Attempting to send SMS to {number} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        result = subprocess.run(
            ["gammu", "--device", DEVICE, "sendsms", "TEXT", number, "-text", message],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        success = result.returncode == 0
        log_sms_sent(number, message, success)
        
        if not success:
            _LOGGER.error(f"Failed to send SMS: {result.stderr}")
        
        return success
    except Exception as e:
        _LOGGER.error(f"Failed to send SMS: {str(e)}")
        log_sms_sent(number, message, success=False)
        return False

def on_connect(client, userdata, flags, rc, properties=None):
    """Log MQTT connection status"""
    if rc == 0:
        _LOGGER.info(f"Connected to MQTT broker successfully at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        client.subscribe(OUTBOX_TOPIC)
        _LOGGER.info(f"Subscribed to {OUTBOX_TOPIC}")
    else:
        _LOGGER.error(f"Failed to connect to MQTT broker, return code: {rc}")

def on_message(client, userdata, msg):
    """Log and process incoming MQTT messages"""
    _LOGGER.info(f"MQTT message received on {msg.topic} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    try:
        payload = json.loads(msg.payload.decode())
        number = payload["number"]
        text = payload["text"]
        
        _LOGGER.info(f"Processing message to: {number}")
        send_sms(number, text)
            
    except json.JSONDecodeError as e:
        _LOGGER.error(f"Error processing message: Invalid JSON in MQTT message: {e}")
    except KeyError as e:
        _LOGGER.error(f"Error processing message: Missing required field in MQTT message: {e}")
    except Exception as e:
        _LOGGER.error(f"Error processing message: {str(e)}")

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
    version = get_version()
    
    # Startup banner
    _LOGGER.info("=" * 60)
    _LOGGER.info(f"SMS Gateway v{version} starting...")
    _LOGGER.info(f"Python version: {sys.version.split()[0]}")
    _LOGGER.info(f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        _LOGGER.info(f"Gammu version: {gammu.Version()}")
    except ImportError:
        _LOGGER.error("Failed to import gammu module")
        sys.exit(1)
    
    _LOGGER.info("=" * 60)
    
    _LOGGER.info(f"Device: {DEVICE}")
    _LOGGER.info(f"Debug mode: {DEBUG}")
    _LOGGER.info(f"Notifications on receive: {NOTIFICATION_ON_RECEIVE}")
    _LOGGER.info(f"MQTT Broker: {MQTT_HOST}:{MQTT_PORT}")
    
    # Initial modem check
    if check_modem_status():
        _LOGGER.info("Modem is connected and ready")
    else:
        _LOGGER.warning("Modem is not responding, will retry...")
    
    # Setup MQTT with new API version
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
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