import json
import logging

import paho.mqtt.publish as publish
from django.conf import settings

logger = logging.getLogger(__name__)


def publish_command(device, variable, value):
    """Publishes a command to a device's <variable>/set topic.

    Returns True on success, False if the broker was unreachable or the
    publish otherwise failed. Never raises.
    """
    topic = f"{settings.MQTT_TOPIC_PREFIX}/{device.slug}/{variable}/set"
    payload = json.dumps({"value": value, "token": device.auth_token})

    auth = None
    if settings.MQTT_USERNAME:
        auth = {"username": settings.MQTT_USERNAME, "password": settings.MQTT_PASSWORD}

    try:
        publish.single(
            topic,
            payload=payload,
            qos=1,
            hostname=settings.MQTT_BROKER_HOST,
            port=settings.MQTT_BROKER_PORT,
            auth=auth,
        )
    except Exception:
        logger.exception("Failed to publish command to %s", topic)
        return False
    return True
