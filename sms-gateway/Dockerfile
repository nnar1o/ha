ARG BUILD_FROM
FROM ${BUILD_FROM}

# Install dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    gammu \
    gammu-dev \
    udev \
    bash \
    && pip3 install --no-cache-dir paho-mqtt

# Set working directory
WORKDIR /app

# Copy application files
COPY gammu_mqtt.py /app/gammu_mqtt.py
COPY gammu-config /app/gammu-config
COPY udev-rules /app/udev-rules
COPY run.sh /app/run.sh

# Make run script executable
RUN chmod +x /app/run.sh

# Set up proper logging directory
RUN mkdir -p /var/log

# Entry point
CMD ["/app/run.sh"]