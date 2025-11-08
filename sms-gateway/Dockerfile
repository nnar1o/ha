ARG BUILD_FROM
FROM ${BUILD_FROM}

ENV LANG=C.UTF-8

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

RUN chmod +x /etc/services.d/sms-gateway/run && \
    echo "1.0.9" > /app/version.txt

ENTRYPOINT ["/init"]