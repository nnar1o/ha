#!/usr/bin/with-contenv bashio
# ==============================================================================
# SMS Gateway Add-on for Home Assistant
# Runs the SMS Gateway service with gammu and MQTT integration
# ==============================================================================

bashio::log.info "Starting SMS Gateway Add-on..."

# Load configuration
export MQTT_HOST=$(bashio::config 'mqtt_host')
export MQTT_PORT=$(bashio::config 'mqtt_port')
export MQTT_USER=$(bashio::config 'mqtt_user')
export MQTT_PASSWORD=$(bashio::config 'mqtt_password')
export SERIAL_DEVICE=$(bashio::config 'serial_device')
export LOG_LEVEL=$(bashio::config 'log_level' 'INFO')

bashio::log.info "Configuration loaded:"
bashio::log.info "  MQTT Host: ${MQTT_HOST}"
bashio::log.info "  MQTT Port: ${MQTT_PORT}"
bashio::log.info "  Serial Device: ${SERIAL_DEVICE}"
bashio::log.info "  Log Level: ${LOG_LEVEL}"

# Copy gammu configuration
bashio::log.info "Setting up gammu configuration..."
cp /app/gammu-config /root/.gammurc

# Update device in gammu config with the configured serial device
sed -i "s|device = /dev/ttyUSB0|device = ${SERIAL_DEVICE}|g" /root/.gammurc

# Install udev rules for Huawei modem
bashio::log.info "Installing udev rules..."
if [ -f /app/udev-rules/99-huawei.rules ]; then
    cp /app/udev-rules/99-huawei.rules /etc/udev/rules.d/
    udevadm control --reload-rules 2>/dev/null || true
    udevadm trigger 2>/dev/null || true
fi

# Wait for device to be ready
bashio::log.info "Waiting for modem device ${SERIAL_DEVICE}..."
WAIT_TIME=0
MAX_WAIT=60
while [ ! -e "${SERIAL_DEVICE}" ] && [ ${WAIT_TIME} -lt ${MAX_WAIT} ]; do
    sleep 2
    WAIT_TIME=$((WAIT_TIME + 2))
    bashio::log.debug "Waiting for device... (${WAIT_TIME}s)"
done

if [ ! -e "${SERIAL_DEVICE}" ]; then
    bashio::log.error "Device ${SERIAL_DEVICE} not found after ${MAX_WAIT} seconds!"
    bashio::log.error "Please check:"
    bashio::log.error "  - Modem is properly connected"
    bashio::log.error "  - Device path is correct in configuration"
    bashio::log.error "  - USB passthrough is configured in Home Assistant"
    exit 1
fi

bashio::log.info "Modem device found: ${SERIAL_DEVICE}"

# Test gammu connection
bashio::log.info "Testing gammu connection..."
if gammu --config /root/.gammurc identify 2>&1 | grep -q "Manufacturer"; then
    bashio::log.info "Gammu connection successful!"
else
    bashio::log.warning "Could not identify modem, but continuing anyway..."
    bashio::log.warning "This might be normal during initialization."
fi

# Start the SMS Gateway service
bashio::log.info "Starting SMS Gateway service..."
exec python3 /app/gammu_mqtt.py
