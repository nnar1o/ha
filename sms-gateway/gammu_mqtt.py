#!/usr/bin/env python3
"""
SMS Gateway for Home Assistant
Sends and receives SMS messages via Huawei USB modem using Gammu
Integrates with Home Assistant via MQTT
"""

import os
import sys
import time
import json
import logging
import subprocess
import queue
from datetime import datetime
from threading import Thread
import paho.mqtt.client as mqtt

# Configuration from environment variables
MQTT_HOST = os.getenv('MQTT_HOST', 'core-mosquitto')
MQTT_PORT = int(os.getenv('MQTT_PORT', '1883'))
MQTT_USER = os.getenv('MQTT_USER', '')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD', '')
DEVICE = os.getenv('SERIAL_DEVICE', '/dev/ttyUSB0')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'info').upper()

# MQTT Topics
INBOX_TOPIC = 'sms-gateway/inbox'
OUTBOX_TOPIC = 'sms-gateway/outbox'
STATUS_TOPIC = 'sms-gateway/status'

# Message queue for reliable delivery
message_queue = queue.Queue()

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


def test_gammu_connection():
    """Test connection to the modem using Gammu"""
    try:
        result = subprocess.run(
            ["gammu", "--config", "/etc/gammu-smsdrc", "identify"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            logger.info("Gammu connection successful")
            logger.debug(f"Modem info: {result.stdout}")
            return True
        else:
            logger.error(f"Gammu connection failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        logger.error("Gammu connection timeout")
        return False
    except Exception as e:
        logger.error(f"Error testing Gammu connection: {e}")
        return False


def on_connect(client, userdata, flags, rc):
    """Callback when connected to MQTT broker"""
    if rc == 0:
        logger.info("Connected to MQTT broker successfully")
        client.subscribe(OUTBOX_TOPIC)
        logger.info(f"Subscribed to {OUTBOX_TOPIC}")
        # Publish online status
        client.publish(STATUS_TOPIC, json.dumps({
            "status": "online",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }), retain=True)
    else:
        logger.error(f"Failed to connect to MQTT broker, return code: {rc}")


def on_disconnect(client, userdata, rc):
    """Callback when disconnected from MQTT broker"""
    if rc != 0:
        logger.warning(f"Unexpected disconnection from MQTT broker, code: {rc}")
        logger.info("Will attempt to reconnect...")


def on_message(client, userdata, msg):
    """Callback when message received on subscribed topic"""
    try:
        payload = json.loads(msg.payload)
        logger.info(f"Received message to send: {payload}")
        
        # Validate message format
        if "number" not in payload or "text" not in payload:
            logger.error("Invalid message format: missing 'number' or 'text' field")
            return
        
        number = payload["number"]
        text = payload["text"]
        
        # Add to queue for processing
        message_queue.put((number, text))
        logger.info(f"Added message to queue (queue size: {message_queue.qsize()})")
        
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON message: {e}")
    except Exception as e:
        logger.error(f"Error processing message: {e}")


def send_sms(number, text):
    """Send SMS using Gammu"""
    try:
        logger.info(f"Sending SMS to {number}")
        result = subprocess.run(
            ["gammu", "--config", "/etc/gammu-smsdrc", "sendsms", "TEXT", number, "-text", text],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            logger.info(f"SMS sent successfully to {number}")
            return True
        else:
            logger.error(f"Failed to send SMS: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout sending SMS to {number}")
        return False
    except Exception as e:
        logger.error(f"Error sending SMS: {e}")
        return False


def process_message_queue():
    """Process messages from the queue"""
    logger.info("Message queue processor started")
    while True:
        try:
            # Get message from queue with timeout
            number, text = message_queue.get(timeout=1)
            
            # Try to send SMS
            success = send_sms(number, text)
            
            if not success:
                # Re-queue the message for retry
                logger.warning(f"Retrying message to {number} in 30 seconds")
                time.sleep(30)
                message_queue.put((number, text))
            
            message_queue.task_done()
            
        except queue.Empty:
            # No messages in queue, continue
            continue
        except Exception as e:
            logger.error(f"Error in message queue processor: {e}")
            time.sleep(5)


def check_inbox(client):
    """Check for new SMS messages and publish to MQTT"""
    try:
        result = subprocess.run(
            ["gammu", "--config", "/etc/gammu-smsdrc", "getallsms"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            logger.debug("No messages or error reading messages")
            return
        
        # Parse SMS messages
        sms_messages = result.stdout.split("Location")
        
        for sms_block in sms_messages[1:]:  # Skip first empty split
            try:
                lines = sms_block.strip().splitlines()
                number = None
                text = None
                
                for line in lines:
                    if "Remote number" in line or "Number" in line:
                        parts = line.split(":", 1)
                        if len(parts) == 2:
                            number = parts[1].strip().strip('"')
                    elif line.strip().startswith("Text:") or line.strip().startswith("Text "):
                        parts = line.split(":", 1)
                        if len(parts) == 2:
                            text = parts[1].strip()
                
                if number and text:
                    message_data = {
                        "number": number,
                        "text": text,
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    }
                    
                    logger.info(f"Received SMS from {number}: {text[:50]}...")
                    client.publish(INBOX_TOPIC, json.dumps(message_data))
                    logger.info("Published message to MQTT")
                    
                    # Delete the message after reading
                    # Note: This requires the location number from the message
                    # For now, we'll delete all messages to prevent duplicates
                    
            except Exception as e:
                logger.error(f"Error parsing SMS message: {e}")
                continue
        
        # Delete all read messages to prevent duplicates
        if result.stdout and "Location" in result.stdout:
            try:
                subprocess.run(
                    ["gammu", "--config", "/etc/gammu-smsdrc", "deleteallsms", "1"],
                    capture_output=True,
                    timeout=10
                )
                logger.debug("Deleted read messages")
            except Exception as e:
                logger.warning(f"Could not delete messages: {e}")
                
    except subprocess.TimeoutExpired:
        logger.warning("Timeout checking inbox")
    except Exception as e:
        logger.error(f"Error checking inbox: {e}")


def main():
    """Main function"""
    logger.info("=" * 50)
    logger.info("SMS Gateway for Home Assistant")
    logger.info("=" * 50)
    logger.info(f"MQTT Broker: {MQTT_HOST}:{MQTT_PORT}")
    logger.info(f"Serial Device: {DEVICE}")
    logger.info(f"Log Level: {LOG_LEVEL}")
    logger.info("=" * 50)
    
    # Test Gammu connection
    logger.info("Testing modem connection...")
    retry_count = 0
    max_retries = 5
    
    while retry_count < max_retries:
        if test_gammu_connection():
            break
        retry_count += 1
        if retry_count < max_retries:
            logger.warning(f"Retrying in 10 seconds... (attempt {retry_count}/{max_retries})")
            time.sleep(10)
        else:
            logger.error("Failed to connect to modem after maximum retries")
            logger.error("Service will continue but SMS functionality may not work")
    
    # Set up MQTT client
    logger.info("Setting up MQTT client...")
    client = mqtt.Client(client_id="sms-gateway", clean_session=False)
    
    if MQTT_USER:
        logger.info("Using MQTT authentication")
        client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    
    # Set last will message
    client.will_set(STATUS_TOPIC, json.dumps({
        "status": "offline",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }), retain=True)
    
    # Connect to MQTT broker with retry
    logger.info("Connecting to MQTT broker...")
    connected = False
    retry_count = 0
    
    while not connected and retry_count < max_retries:
        try:
            client.connect(MQTT_HOST, MQTT_PORT, 60)
            connected = True
        except Exception as e:
            retry_count += 1
            logger.error(f"Failed to connect to MQTT broker: {e}")
            if retry_count < max_retries:
                logger.info(f"Retrying in 10 seconds... (attempt {retry_count}/{max_retries})")
                time.sleep(10)
            else:
                logger.error("Failed to connect to MQTT broker after maximum retries")
                sys.exit(1)
    
    # Start MQTT loop in background
    client.loop_start()
    
    # Start message queue processor in separate thread
    queue_thread = Thread(target=process_message_queue, daemon=True)
    queue_thread.start()
    logger.info("Message queue processor started")
    
    # Main loop - check for incoming SMS
    logger.info("Starting main loop...")
    check_interval = 10  # seconds
    last_check = 0
    
    try:
        while True:
            current_time = time.time()
            
            # Check inbox periodically
            if current_time - last_check >= check_interval:
                check_inbox(client)
                last_check = current_time
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Unexpected error in main loop: {e}")
    finally:
        logger.info("Shutting down...")
        # Publish offline status
        client.publish(STATUS_TOPIC, json.dumps({
            "status": "offline",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }), retain=True)
        client.loop_stop()
        client.disconnect()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    main()
