#!/bin/sh
set -e

: "${MQTT_USERNAME:?MQTT_USERNAME env var is required}"
: "${MQTT_PASSWORD:?MQTT_PASSWORD env var is required}"

mosquitto_passwd -b -c /mosquitto/config/passwd "$MQTT_USERNAME" "$MQTT_PASSWORD"
chmod 644 /mosquitto/config/passwd

exec mosquitto -c /mosquitto/config/mosquitto.conf
