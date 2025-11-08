#!/usr/bin/with-contenv bashio
echo "Starting SMS Gateway v1.0.5 at $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
cd /app
echo "Setting execute permissions for scripts..."
chmod +x /app/gammu_mqtt.py

echo "Starting Python script..."
python3 gammu_mqtt.py
