import os
import paho.mqtt.client as mqtt
import subprocess
import time
import json
import logging
import sys
from datetime import datetime
from queue import Queue, Empty
from threading import Thread

# Configuration from environment variables
MQTT_HOST = os.getenv('MQTT_HOST', 'core-mosquitto')
MQTT_PORT = int(os.getenv('MQTT_PORT', '1883'))
MQTT_USER = os.getenv('MQTT_USER', '')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD', '')
DEVICE = os.getenv('SERIAL_DEVICE', '/dev/ttyUSB0')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# MQTT Topics
INBOX_TOPIC = 'sms-gateway/inbox'
OUTBOX_TOPIC = 'sms-gateway/outbox'
STATUS_TOPIC = 'sms-gateway/status'

# Constants
MAX_LOG_MESSAGE_LENGTH = 100  # Maximum message length to log for privacy

# Message queue for reliable delivery
message_queue = Queue()

# Configure logging
log_level_map = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR
}

logging.basicConfig(
    level=log_level_map.get(LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


def get_timestamp():
    """Get current timestamp in ISO format"""
    return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')


def send_sms(number, text):
    """
    Send SMS message using gammu
    
    Args:
        number: Phone number to send to
        text: Message text
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info(f"Sending SMS to {number}: {text[:50]}...")
        
        result = subprocess.run(
            ["gammu", "--config", "/root/.gammurc", "sendsms", "TEXT", number, "-text", text],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            logger.info(f"SMS sent successfully to {number}")
            return True
        else:
            logger.error(f"Failed to send SMS to {number}: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout while sending SMS to {number}")
        return False
    except Exception as e:
        logger.error(f"Error sending SMS to {number}: {e}")
        return False


def on_connect(client, userdata, flags, rc):
    """MQTT connection callback"""
    if rc == 0:
        logger.info("Connected to MQTT broker")
        client.subscribe(OUTBOX_TOPIC)
        logger.info(f"Subscribed to {OUTBOX_TOPIC}")
        
        # Publish online status
        client.publish(STATUS_TOPIC, json.dumps({
            "status": "online",
            "timestamp": get_timestamp(),
            "device": DEVICE
        }), retain=True)
    else:
        logger.error(f"Failed to connect to MQTT broker, return code: {rc}")


def on_disconnect(client, userdata, rc):
    """MQTT disconnection callback"""
    if rc != 0:
        logger.warning(f"Unexpected disconnection from MQTT broker (code: {rc})")
    else:
        logger.info("Disconnected from MQTT broker")


def on_message(client, userdata, msg):
    """
    MQTT message callback - handles outgoing SMS requests
    
    Expected message format:
    {
        "number": "+48123456789",
        "text": "Message content"
    }
    """
    try:
        logger.debug(f"Received message on {msg.topic}")
        payload = json.loads(msg.payload)
        
        # Validate message format
        if "number" not in payload or "text" not in payload:
            logger.error("Invalid message format: missing 'number' or 'text' field")
            return
        
        number = payload["number"]
        text = payload["text"]
        
        # Validate phone number (basic validation)
        if not number or len(number) < 5:
            logger.error(f"Invalid phone number: {number}")
            return
        
        # Validate message text
        if not text:
            logger.error("Empty message text")
            return
        
        # Add to message queue
        message_queue.put((number, text))
        logger.info(f"Message queued for {number}")
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in message: {e}")
    except Exception as e:
        logger.error(f"Error processing outgoing message: {e}")


def message_sender_worker(client):
    """
    Worker thread that processes the message queue
    Ensures messages are sent sequentially with proper error handling
    """
    logger.info("Message sender worker started")
    
    while True:
        try:
            # Get message from queue (blocking)
            number, text = message_queue.get(timeout=1)
            
            # Attempt to send
            success = send_sms(number, text)
            
            # Publish send status
            status_msg = {
                "number": number,
                "text": text[:MAX_LOG_MESSAGE_LENGTH],  # Truncate for privacy
                "status": "sent" if success else "failed",
                "timestamp": get_timestamp()
            }
            client.publish(f"{STATUS_TOPIC}/send", json.dumps(status_msg))
            
            # Mark task as done
            message_queue.task_done()
            
            # Brief delay between messages
            time.sleep(2)
            
        except Empty:
            # Queue is empty, continue waiting
            continue
        except Exception as e:
            logger.error(f"Error in message sender worker: {e}")
            continue


def check_inbox(client):
    """
    Check for new SMS messages and publish to MQTT
    """
    try:
        logger.debug("Checking inbox for new messages...")
        
        result = subprocess.run(
            ["gammu", "--config", "/root/.gammurc", "getallsms"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            logger.debug(f"No messages or error reading inbox: {result.stderr}")
            return
        
        # Parse SMS messages from gammu output
        sms_messages = result.stdout.split("SMS message")
        messages_processed = False
        
        for sms in sms_messages[1:]:  # Skip first empty element
            lines = sms.strip().splitlines()
            number = None
            text = None
            
            for line in lines:
                if "Number" in line and ":" in line:
                    number = line.split(":", 1)[1].strip().strip('"')
                elif line.strip().startswith("Text") and ":" in line:
                    # Text might span multiple lines, get everything after first colon
                    text = line.split(":", 1)[1].strip()
            
            if number and text:
                logger.info(f"Received SMS from {number}")
                
                # Publish to inbox topic
                message = {
                    "number": number,
                    "text": text,
                    "timestamp": get_timestamp()
                }
                
                client.publish(INBOX_TOPIC, json.dumps(message))
                logger.info(f"Published SMS from {number} to {INBOX_TOPIC}")
                messages_processed = True
        
        # Delete all processed messages after successfully publishing them
        if messages_processed:
            try:
                subprocess.run(
                    ["gammu", "--config", "/root/.gammurc", "deleteallsms", "1"],
                    capture_output=True,
                    timeout=10
                )
                logger.debug("Deleted all processed messages from folder 1")
            except Exception as e:
                logger.warning(f"Could not delete messages: {e}")
                    
    except subprocess.TimeoutExpired:
        logger.warning("Timeout while checking inbox")
    except Exception as e:
        logger.error(f"Error checking inbox: {e}")


def main():
    """Main application loop"""
    logger.info("=" * 60)
    logger.info("SMS Gateway Add-on Starting")
    logger.info("=" * 60)
    logger.info(f"MQTT Host: {MQTT_HOST}:{MQTT_PORT}")
    logger.info(f"Serial Device: {DEVICE}")
    logger.info(f"Log Level: {LOG_LEVEL}")
    logger.info("=" * 60)
    
    # Verify device exists
    if not os.path.exists(DEVICE):
        logger.error(f"Device {DEVICE} not found!")
        logger.error("Please check device path and USB passthrough configuration")
        sys.exit(1)
    
    # Test gammu configuration
    try:
        logger.info("Testing gammu configuration...")
        result = subprocess.run(
            ["gammu", "--config", "/root/.gammurc", "identify"],
            capture_output=True,
            text=True,
            timeout=15
        )
        
        if result.returncode == 0:
            logger.info("Gammu configuration OK")
            logger.info(f"Modem info: {result.stdout.split(os.linesep)[0]}")
        else:
            logger.warning("Could not identify modem, continuing anyway...")
            
    except Exception as e:
        logger.warning(f"Could not test gammu: {e}")
    
    # Set up MQTT client
    logger.info("Connecting to MQTT broker...")
    client = mqtt.Client(client_id="sms-gateway")
    
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    
    # Set will message (published when connection is lost)
    client.will_set(STATUS_TOPIC, json.dumps({
        "status": "offline",
        "timestamp": get_timestamp()
    }), retain=True)
    
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
    except Exception as e:
        logger.error(f"Failed to connect to MQTT broker: {e}")
        sys.exit(1)
    
    # Start MQTT loop in background
    client.loop_start()
    
    # Start message sender worker thread
    sender_thread = Thread(target=message_sender_worker, args=(client,), daemon=True)
    sender_thread.start()
    
    logger.info("SMS Gateway is running")
    logger.info(f"Listening for messages on: {OUTBOX_TOPIC}")
    logger.info(f"Publishing received messages to: {INBOX_TOPIC}")
    
    # Main loop - check inbox periodically
    try:
        while True:
            check_inbox(client)
            time.sleep(10)  # Check every 10 seconds
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        # Publish offline status
        client.publish(STATUS_TOPIC, json.dumps({
            "status": "offline",
            "timestamp": get_timestamp()
        }), retain=True)
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()