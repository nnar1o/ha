ARG BUILD_FROM
FROM ${BUILD_FROM}

# Fix ENV format
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
    python-gammu

COPY rootfs /
WORKDIR /app

# Set version
RUN echo "1.0.4" > /app/version.txt