ARG BUILD_FROM
FROM ${BUILD_FROM}

ENV LANG=C.UTF-8

RUN apk add --no-cache gammu gammu-dev gcc musl-dev python3-dev
RUN pip3 install --no-cache-dir paho-mqtt python-gammu

COPY rootfs /
WORKDIR /app

RUN echo "1.0.6" > /app/version.txt && \
    chmod +x /etc/services.d/sms-gateway/run