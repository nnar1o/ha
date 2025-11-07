ARG BUILD_FROM
FROM $BUILD_FROM

# Install requirements for add-on
RUN apk add --no-cache \
    python3 \
    py3-pip \
    gammu \
    bash

# Install Python packages
RUN pip3 install --no-cache-dir \
    paho-mqtt

# Copy data for add-on
COPY run.sh /
COPY gammu_mqtt.py /app/
COPY gammu-config /etc/gammu-smsdrc

RUN chmod a+x /run.sh

WORKDIR /app

CMD [ "/run.sh" ]