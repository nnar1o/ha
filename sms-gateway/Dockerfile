ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache gammu gammu-dev gcc musl-dev python3-dev usb-modeswitch && \
    pip3 install --no-cache-dir paho-mqtt python-gammu requests pyudev

COPY rootfs /
WORKDIR /app

RUN chmod +x /etc/services.d/sms-gateway/run && \
    echo "1.0.20" > /app/version.txt

ENTRYPOINT ["/init"]