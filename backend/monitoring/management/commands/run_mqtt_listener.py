import json
import logging
import secrets

import paho.mqtt.client as mqtt
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from monitoring.models import Device, Sensor, SensorReading, UnregisteredReading

logger = logging.getLogger(__name__)

DEFAULT_UNITS = {
    "resistencia_tierra": "Ω",
    "voltaje": "V",
    "continuidad": "Ω",
    "temperatura": "°C",
    "humedad": "%",
    "presion": "hPa",
    "gas": "kΩ",
    "nivel": "%",
    "setpoint_nivel": "%",
    "frecuencia": "Hz",
    "velocidad_ref": "Hz",
}


class Command(BaseCommand):
    help = "Subscribes to the MQTT broker and persists incoming sensor readings."

    def handle(self, *args, **options):
        topic_filter = f"{settings.MQTT_TOPIC_PREFIX}/+/+"

        client = mqtt.Client()
        if settings.MQTT_USERNAME:
            client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)

        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                self.stdout.write(self.style.SUCCESS(
                    f"Connected to MQTT broker at {settings.MQTT_BROKER_HOST}:{settings.MQTT_BROKER_PORT}"
                ))
                client.subscribe(topic_filter, qos=1)
                self.stdout.write(f"Subscribed to {topic_filter}")
            else:
                self.stdout.write(self.style.ERROR(f"MQTT connect failed with rc={rc}"))

        def on_disconnect(client, userdata, rc):
            logger.warning("Disconnected from MQTT broker (rc=%s), will auto-reconnect", rc)

        def on_message(client, userdata, msg):
            try:
                _handle_message(msg.topic, msg.payload)
            except Exception:
                logger.exception("Failed to process MQTT message on topic %s", msg.topic)

        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
        client.on_message = on_message

        client.reconnect_delay_set(min_delay=1, max_delay=30)
        client.connect(settings.MQTT_BROKER_HOST, settings.MQTT_BROKER_PORT, keepalive=60)
        client.loop_forever()


def _handle_message(topic, payload):
    parts = topic.split("/")
    if len(parts) != 3:
        logger.warning("Ignoring message on unexpected topic shape: %s", topic)
        return

    _, device_slug, variable = parts

    device = Device.objects.filter(slug=device_slug).first()
    if device is None:
        UnregisteredReading.objects.create(
            topic=topic,
            raw_payload=payload.decode("utf-8", errors="replace"),
            reason=UnregisteredReading.REASON_UNKNOWN_DEVICE,
        )
        logger.info("Quarantined reading for unregistered device slug %r", device_slug)
        return

    try:
        data = json.loads(payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.warning("Ignoring non-JSON payload on topic %s", topic)
        return

    token = str(data.get("token", ""))
    if not secrets.compare_digest(token, device.auth_token):
        UnregisteredReading.objects.create(
            topic=topic,
            raw_payload=payload.decode("utf-8", errors="replace"),
            reason=UnregisteredReading.REASON_INVALID_TOKEN,
        )
        logger.warning("Rejected message for device %r: invalid or missing token", device_slug)
        return

    value = data.get("value")
    if not isinstance(value, (int, float)):
        logger.warning("Ignoring payload with non-numeric value on topic %s: %r", topic, value)
        return

    ts = None
    raw_ts = data.get("timestamp")
    if raw_ts:
        ts = parse_datetime(raw_ts)
    if ts is None:
        ts = timezone.now()
    elif timezone.is_naive(ts):
        ts = timezone.make_aware(ts, timezone.utc)

    sensor, created = Sensor.objects.get_or_create(
        device=device,
        variable=variable,
        defaults={"unit": DEFAULT_UNITS.get(variable, "")},
    )

    if not created and not sensor.unit:
        default_unit = DEFAULT_UNITS.get(variable)
        if default_unit:
            sensor.unit = default_unit
            sensor.save(update_fields=["unit"])

    SensorReading.objects.create(sensor=sensor, value=float(value), timestamp=ts)
    Device.objects.filter(pk=device.pk).update(last_seen_at=timezone.now())
