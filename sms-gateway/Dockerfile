FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y gammu && \
    pip install paho-mqtt && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY gammu_mqtt.py /app/gammu_mqtt.py

CMD ["python", "/app/gammu_mqtt.py"]