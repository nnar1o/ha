FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y gammu && \
    pip install paho-mqtt requests && \
    rm -rf /var/lib/apt/lists/*

COPY rootfs /

CMD ["python", "/app/gammu_mqtt.py"]