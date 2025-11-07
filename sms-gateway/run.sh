#!/usr/bin/with-contenv bashio
# ==============================================================================
# Home Assistant Community Add-on: SMS Gateway
# Runs the SMS Gateway service
# ==============================================================================

bashio::log.info "Starting SMS Gateway..."

# Read configuration from Home Assistant
export MQTT_HOST=$(bashio::config 'mqtt_host')
export MQTT_PORT=$(bashio::config 'mqtt_port')
export MQTT_USER=$(bashio::config 'mqtt_user')
export MQTT_PASSWORD=$(bashio::config 'mqtt_password')
export SERIAL_DEVICE=$(bashio::config 'serial_device')
export LOG_LEVEL=$(bashio::config 'log_level' 'info')

bashio::log.info "Configuration loaded:"
bashio::log.info "  MQTT Host: ${MQTT_HOST}"
bashio::log.info "  MQTT Port: ${MQTT_PORT}"
bashio::log.info "  Serial Device: ${SERIAL_DEVICE}"
bashio::log.info "  Log Level: ${LOG_LEVEL}"

# Create Gammu configuration file with the configured device
bashio::log.info "Creating Gammu configuration..."
cat > /etc/gammu-smsdrc << EOF
[gammu]
device = ${SERIAL_DEVICE}
connection = at
EOF

# Wait a moment for the device to be ready
sleep 2

# Check if the device exists
if [ ! -e "${SERIAL_DEVICE}" ]; then
    bashio::log.warning "Device ${SERIAL_DEVICE} not found. Checking for alternative devices..."
    
    # Try to auto-detect USB modem
    for device in /dev/ttyUSB0 /dev/ttyUSB1 /dev/ttyUSB2 /dev/ttyACM0; do
        if [ -e "$device" ]; then
            bashio::log.info "Found alternative device: $device"
            export SERIAL_DEVICE=$device
            cat > /etc/gammu-smsdrc << EOF
[gammu]
device = ${SERIAL_DEVICE}
connection = at
EOF
            break
        fi
    done
    
    if [ ! -e "${SERIAL_DEVICE}" ]; then
        bashio::log.error "No USB modem device found!"
        bashio::log.error "Please ensure your modem is connected and the correct device is configured."
        exit 1
    fi
fi

bashio::log.info "Using device: ${SERIAL_DEVICE}"

# Test Gammu connection
bashio::log.info "Testing Gammu connection to modem..."
if ! gammu identify; then
    bashio::log.warning "Initial Gammu connection failed. The service will retry automatically."
else
    bashio::log.info "Gammu connection successful!"
fi

# Start the Python MQTT bridge
bashio::log.info "Starting SMS Gateway service..."
exec python3 /app/gammu_mqtt.py
