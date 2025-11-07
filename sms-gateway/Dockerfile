FROM homeassistant/amd64-base-python:3.11-alpine3.18
ENV LANG C.UTF-8

# Install required packages
RUN apk add --no-cache \
    gammu \
    gammu-dev \
    gcc \
    musl-dev \
    python3-dev

# Install Python packages
RUN pip3 install --no-cache-dir \
    paho-mqtt \
    python-gammu \
    requests

COPY rootfs /
WORKDIR /app

# Set version in version.txt
RUN echo "1.0.1" > /app/version.txt