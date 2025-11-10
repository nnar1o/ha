import os
import paho.mqtt.client as mqtt
import subprocess
import time
import json
import sys
import requests
import gammu
import traceback
import logging
from datetime import datetime, timezone

# Import custom logger
try:
    from logger import get_logger, status_modem, status_mqtt
    _LOGGER = get_logger(__name__)
except ImportError:
    # Configure logging with timestamp and proper format
    logging.basicConfig(
        level=logging.DEBUG,  # Always use DEBUG level
        format='%(asctime)s UTC - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    _LOGGER = logging.getLogger(__name__)
    # Fallback status functions if logger module not available
    def status_modem(*args, **kwargs):
        pass
    def status_mqtt(*args, **kwargs):
        pass

VERSION = "1.0.18"

def log_system_info():
    """Log detailed system information"""
    _LOGGER.debug("=" * 60)
    _LOGGER.debug(f"SMS Gateway v{VERSION} starting...")
    _LOGGER.debug(f"Start time (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
    _LOGGER.debug(f"Python version: {sys.version}")
    _LOGGER.debug(f"Current working directory: {os.getcwd()}")
    _LOGGER.debug(f"Script path: {os.path.realpath(__file__)}")
    _LOGGER.debug("Environment variables:")
    for key, value in os.environ.items():
        if not any(secret in key.lower() for secret in ['password', 'token', 'secret']):
            _LOGGER.debug(f"  {key}: {value}")
    _LOGGER.debug("=" * 60)

def log_device_info():
    """Log modem and device information"""
    _LOGGER.debug("=" * 60)
    _LOGGER.debug("Device Information:")
    _LOGGER.debug(f"Device path: {DEVICE}")
    try:
        result = subprocess.run(
            ["gammu", "--identify"],
            capture_output=True,
            text=True,
            timeout=10
        )
        _LOGGER.debug("Gammu identify output:")
        _LOGGER.debug(result.stdout)
    except Exception as e:
        _LOGGER.error(f"Failed to get device info: {e}")
    _LOGGER.debug("=" * 60)

def get_utc_time():
    """Get current UTC time in YYYY-MM-DD HH:MM:SS format"""
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

def get_version():
    """Get version from version.txt file"""
    try:
        with open('/app/version.txt', 'r') as f:
            return f.read().strip()
    except:
        return "unknown"

def log_startup_info():
    """Log startup information"""
    _LOGGER.info(f"SMS Gateway v{VERSION} starting...")
    _LOGGER.info(f"Current time (UTC): {get_utc_time()}")
    _LOGGER.info(f"Python version: {sys.version.split()[0]}")
    try:
        _LOGGER.info(f"Gammu version: {gammu.Version()}")
    except:
        _LOGGER.error("Failed to get Gammu version")

def log_sms_operation(operation_type, number, message, success=True):
    """Log SMS operations with UTC timestamp"""
    status = "Success" if success else "Failed"
    _LOGGER.info(f"Time (UTC): {get_utc_time()}")
    _LOGGER.info(f"Operation: {operation_type}")
    _LOGGER.info(f"Status: {status}")
    _LOGGER.info(f"Number: {number}")
    _LOGGER.info(f"Message: {message}")

# Constants for modem retry logic
MAX_RETRIES = 5
RETRY_DELAY = 5  # seconds

# Configuration from add-on options
OPTIONS_PATH = '/data/options.json'
try:
    with open(OPTIONS_PATH) as f:
        options = json.load(f)
        # Prioritize DEVICE env var (set by usb_switcher.py for auto-detection)
        # Fall back to options, then default
        DEVICE = os.getenv('DEVICE') or options.get('device', '/dev/ttyUSB0')
        DEBUG = options.get('debug', False)
        NOTIFICATION_ON_RECEIVE = options.get('notification_on_receive', True)
        
        # MQTT configuration - prioritize environment variables from bashio::services
        # Fall back to options if env vars are not set
        MQTT_HOST = os.getenv('MQTT_HOST') or options.get('mqtt', {}).get('broker', 'core-mosquitto')
        MQTT_PORT = int(os.getenv('MQTT_PORT') or options.get('mqtt', {}).get('port', 1883))
        MQTT_USER = os.getenv('MQTT_USER') or options.get('mqtt', {}).get('username', '')
        MQTT_PASSWORD = os.getenv('MQTT_PASSWORD') or options.get('mqtt', {}).get('password', '')
except FileNotFoundError:
    _LOGGER.warning(f"Options file not found at {OPTIONS_PATH}, using defaults")
    DEVICE = os.getenv('DEVICE') or os.getenv('SERIAL_DEVICE', '/dev/ttyUSB0')
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
DIAGNOSTICS_TOPIC = 'sms-gateway/diagnostics'

# Home Assistant settings
SUPERVISOR_TOKEN = os.getenv('SUPERVISOR_TOKEN', '')
HA_URL = 'http://supervisor/core/api'

# State tracking
last_message = {"number": "", "text": "", "timestamp": ""}
modem_connected = False

def log_sms_received(number, message):
    """Log detailed information about received SMS"""
    _LOGGER.info(f"SMS Received - From: {number}")
    _LOGGER.info(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
    _LOGGER.info(f"Message: {message}")

def log_sms_sent(number, message, success=True):
    """Log SMS sending attempt with timestamp"""
    status = "Successfully sent" if success else "Failed to send"
    _LOGGER.info(f"SMS {status} - To: {number}")
    _LOGGER.info(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
    _LOGGER.info(f"Message: {message}")

def publish_init_error_diagnostics(error_msg, exception_traceback=None):
    """Publish initialization error diagnostics to MQTT"""
    try:
        import paho.mqtt.client as mqtt
        
        diagnostics = {
            'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
            'error_type': 'modem_init_failure',
            'error_message': error_msg,
            'exception': exception_traceback,
            'device': DEVICE
        }
        
        # Load MQTT config
        mqtt_host = MQTT_HOST
        mqtt_port = MQTT_PORT
        mqtt_user = MQTT_USER
        mqtt_password = MQTT_PASSWORD
        
        if not mqtt_host:
            _LOGGER.warning("MQTT host not configured, skipping error diagnostics publication")
            return
        
        # Create MQTT client and publish
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if mqtt_user:
            client.username_pw_set(mqtt_user, mqtt_password)
        
        _LOGGER.info(f"Publishing init error diagnostics to MQTT: {mqtt_host}:{mqtt_port}")
        client.connect(mqtt_host, mqtt_port, 60)
        client.loop_start()
        
        # Publish with retain flag
        result = client.publish('sms-gateway/diagnostics', json.dumps(diagnostics), retain=True)
        
        # Wait a bit for publish to complete
        time.sleep(1)
        client.loop_stop()
        client.disconnect()
        
        if result.rc == 0:
            _LOGGER.info("Successfully published error diagnostics to MQTT")
        else:
            _LOGGER.warning(f"Failed to publish error diagnostics to MQTT, return code: {result.rc}")
        
    except Exception as e:
        _LOGGER.error(f"Failed to publish error diagnostics to MQTT: {e}")

def get_connection_type_from_config():
    """Get connection type from /etc/gammurc if available"""
    try:
        with open('/etc/gammurc', 'r') as f:
            for line in f:
                if 'connection' in line.lower() and '=' in line:
                    connection_type = line.split('=')[1].strip()
                    _LOGGER.debug(f"Found connection type in /etc/gammurc: {connection_type}")
                    return connection_type
    except FileNotFoundError:
        _LOGGER.debug("/etc/gammurc not found, using default connection type")
    except Exception as e:
        _LOGGER.debug(f"Error reading /etc/gammurc: {e}")
    
    # Default connection type
    return 'at115200'

def connect_modem():
    """Connect to modem with retry logic and enhanced error handling"""
    for attempt in range(MAX_RETRIES):
        try:
            _LOGGER.info(f"Attempting to connect to modem (attempt {attempt + 1}/{MAX_RETRIES})")
            
            # Get connection type (from config file or default)
            connection_type = get_connection_type_from_config()
            
            # Create state machine and set configuration programmatically
            state_machine = gammu.StateMachine()
            
            # Set configuration using SetConfig instead of ReadConfig
            config = {
                'Device': DEVICE,
                'Connection': connection_type,
            }
            _LOGGER.debug(f"Setting gammu config: Device={DEVICE}, Connection={connection_type}")
            state_machine.SetConfig(0, config)
            
            # Detailed logging before Init
            _LOGGER.debug("Calling StateMachine.Init()...")
            
            state_machine.Init()
            
            _LOGGER.info("Successfully connected to modem")
            
            # Use status_modem helper to log success
            try:
                status_modem('connected', device=DEVICE, connection=connection_type)
            except:
                pass  # Don't fail if status helper fails
            
            return state_machine
            
        except gammu.ERR_DEVICENOTEXIST as e:
            error_msg = f"Modem not found at {DEVICE}"
            _LOGGER.warning(f"{error_msg}, will retry in {RETRY_DELAY} seconds...")
            
            # Log to file with full details
            try:
                with open('/tmp/gammu.log', 'a') as f:
                    f.write(f"\n{'=' * 60}\n")
                    f.write(f"Modem Init Error (Attempt {attempt + 1}/{MAX_RETRIES})\n")
                    f.write(f"Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
                    f.write(f"Error: {error_msg}\n")
                    f.write(f"Exception: {str(e)}\n")
                    f.write(f"Traceback:\n{traceback.format_exc()}\n")
                    f.write(f"{'=' * 60}\n")
            except:
                pass
            
            if attempt == MAX_RETRIES - 1:
                # Last attempt failed, publish diagnostics and update status
                publish_init_error_diagnostics(error_msg, traceback.format_exc())
                try:
                    status_modem('error', device=DEVICE, error='device_not_found')
                except:
                    pass
            elif attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
                
        except Exception as e:
            error_msg = f"Error connecting to modem: {e}"
            _LOGGER.warning(f"{error_msg}, will retry in {RETRY_DELAY} seconds...")
            
            # Log to file with full details including stdout/stderr from gammu
            try:
                with open('/tmp/gammu.log', 'a') as f:
                    f.write(f"\n{'=' * 60}\n")
                    f.write(f"Modem Init Error (Attempt {attempt + 1}/{MAX_RETRIES})\n")
                    f.write(f"Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
                    f.write(f"Device: {DEVICE}\n")
                    f.write(f"Error: {error_msg}\n")
                    f.write(f"Exception Type: {type(e).__name__}\n")
                    f.write(f"Exception: {str(e)}\n")
                    f.write(f"Traceback:\n{traceback.format_exc()}\n")
                    
                    # Try to get gammu identify output
                    try:
                        result = subprocess.run(
                            ['gammu', '--identify'],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        f.write(f"\nGammu --identify output:\n")
                        f.write(f"Return code: {result.returncode}\n")
                        f.write(f"stdout:\n{result.stdout}\n")
                        f.write(f"stderr:\n{result.stderr}\n")
                    except Exception as cmd_e:
                        f.write(f"\nFailed to run gammu --identify: {cmd_e}\n")
                    
                    f.write(f"{'=' * 60}\n")
            except Exception as log_e:
                _LOGGER.error(f"Failed to write to /tmp/gammu.log: {log_e}")
            
            if attempt == MAX_RETRIES - 1:
                # Last attempt failed, publish diagnostics and update status
                publish_init_error_diagnostics(error_msg, traceback.format_exc())
                try:
                    status_modem('error', device=DEVICE, error=type(e).__name__)
                except:
                    pass
            elif attempt < MAX_RETRIES - 1:
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
        # Use gammu without --device flag to use /etc/gammurc configuration
        result = subprocess.run(
            ["gammu", "identify"],
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
    """Send SMS with enhanced logging"""
    _LOGGER.debug("=" * 40)
    _LOGGER.debug("Sending SMS:")
    _LOGGER.debug(f"To: {number}")
    _LOGGER.debug(f"Message length: {len(message)}")
    _LOGGER.debug(f"Time (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Use gammu without --device flag to use /etc/gammurc configuration
        result = subprocess.run(
            ["gammu", "sendsms", "TEXT", number, "-text", message],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            _LOGGER.debug("SMS sent successfully")
            _LOGGER.debug(f"Gammu output: {result.stdout}")
        else:
            _LOGGER.error("SMS sending failed")
            _LOGGER.error(f"Return code: {result.returncode}")
            _LOGGER.error(f"Error output: {result.stderr}")
            
        return result.returncode == 0
    except Exception as e:
        _LOGGER.error(f"Exception while sending SMS: {str(e)}")
        return False
    finally:
        _LOGGER.debug("=" * 40)

def on_connect(client, userdata, flags, rc, properties=None):
    """Log MQTT connection status"""
    if rc == 0:
        _LOGGER.info(f"Connected to MQTT broker successfully at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
        client.subscribe(OUTBOX_TOPIC)
        _LOGGER.info(f"Subscribed to {OUTBOX_TOPIC}")
        
        # Use status_mqtt helper to log connection
        try:
            status_mqtt('connected', broker=MQTT_HOST, port=MQTT_PORT, topic=OUTBOX_TOPIC)
        except:
            pass  # Don't fail if status helper fails
    else:
        _LOGGER.error(f"Failed to connect to MQTT broker, return code: {rc}")
        try:
            status_mqtt('error', broker=MQTT_HOST, port=MQTT_PORT, error_code=rc)
        except:
            pass

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
        # Use gammu without --device flag to use /etc/gammurc configuration
        result = subprocess.run(
            ["gammu", "getallsms"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            _LOGGER.debug("No messages or error getting messages")
            return
        
        # Log output for debugging
        if result.stdout.strip():
            _LOGGER.debug(f"getallsms output: {result.stdout[:500]}")
            
        sms_messages = result.stdout.split("SMS message")
        for sms in sms_messages[1:]:
            lines = sms.strip().splitlines()
            number = ""
            text = ""
            location = ""
            
            for line in lines:
                if "Number :" in line:
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        number = parts[1].strip()
                elif "Text :" in line:
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        text = parts[1].strip()
                elif "Location" in line:
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        location = parts[1].strip()
                    
            if number and text:
                # Log the received SMS
                log_sms_received(number, text)
                
                # Publish to MQTT
                message_data = {"number": number, "text": text}
                client.publish(INBOX_TOPIC, json.dumps(message_data))
                
                # Update last message sensor
                timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
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
                        # Use gammu without --device flag to use /etc/gammurc configuration
                        subprocess.run(
                            ["gammu", "deletesms", "1", location],
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
        _LOGGER.debug(f"Traceback: {traceback.format_exc()}")

def register_ha_service():
    """Register the send_sms service with Home Assistant"""
    if not SUPERVISOR_TOKEN:
        _LOGGER.info("No supervisor token available, skipping service registration")
        return
    
    _LOGGER.info("Service registration via API not directly available")
    _LOGGER.info("Users should create automations using MQTT or Node-RED")

def publish_diagnostics_to_mqtt(client, diagnostics_path='/data/sms_gateway_diagnostics.json'):
    """Publish diagnostics to MQTT if diagnostics file exists"""
    if not os.path.exists(diagnostics_path):
        _LOGGER.debug(f"No diagnostics file found at {diagnostics_path}")
        return
    
    try:
        with open(diagnostics_path, 'r') as f:
            diagnostics = json.load(f)
        
        # Check if there were any failures
        if diagnostics.get('all_failed', False):
            _LOGGER.info("Publishing diagnostics to MQTT due to connection failures...")
            client.publish(DIAGNOSTICS_TOPIC, json.dumps(diagnostics), retain=True)
            _LOGGER.info(f"Diagnostics published to {DIAGNOSTICS_TOPIC}")
        else:
            _LOGGER.debug("All connections successful, no need to publish failure diagnostics")
            # Still publish success diagnostics for monitoring
            client.publish(DIAGNOSTICS_TOPIC, json.dumps(diagnostics), retain=True)
            _LOGGER.debug(f"Success diagnostics published to {DIAGNOSTICS_TOPIC}")
    except Exception as e:
        _LOGGER.error(f"Failed to publish diagnostics: {e}")

def main():
    """Main application loop"""
    log_startup_info()
    version = get_version()
    
    # Startup banner
    _LOGGER.info("=" * 60)
    _LOGGER.info(f"SMS Gateway v{version} starting at {get_utc_time()}")
    _LOGGER.info(f"Python version: {sys.version.split()[0]}")
    _LOGGER.info(f"Current time: {get_utc_time()}")
    
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
    
    # Publish diagnostics if available (from usb_switcher.py)
    publish_diagnostics_to_mqtt(client)
    
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