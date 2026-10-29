import json
import os
import random
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

MQTT_BROKER_HOST = os.environ.get("MQTT_BROKER_HOST", "mosquitto")
MQTT_BROKER_PORT = int(os.environ.get("MQTT_BROKER_PORT", "1883"))
MQTT_USERNAME = os.environ.get("MQTT_USERNAME", "")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD", "")
MQTT_TOPIC_PREFIX = os.environ.get("MQTT_TOPIC_PREFIX", "ecs")
PUBLISH_INTERVAL_SECONDS = float(os.environ.get("SIMULATOR_INTERVAL_SECONDS", "3"))


def parse_device_tokens(raw):
    """Parses SIMULATOR_DEVICE_TOKENS="slug1:token1,slug2:token2" into a dict."""
    tokens = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair or ":" not in pair:
            continue
        slug, token = pair.split(":", 1)
        tokens[slug.strip()] = token.strip()
    return tokens


DEVICE_TOKENS = parse_device_tokens(os.environ.get("SIMULATOR_DEVICE_TOKENS", ""))

# variable -> (min, max, starting value, max step per tick)
VARIABLE_RANGES = {
    "resistencia_tierra": (0.5, 30.0, 5.0, 0.4),
    "voltaje": (205.0, 235.0, 220.0, 1.5),
}

# device_slug -> list of variables it reports
DEVICES = {
    "subestacion-01": ["resistencia_tierra", "voltaje"],
    "sala-electrica-02": ["resistencia_tierra"],
    "torre-transmision-03": ["resistencia_tierra"],
}


def build_state():
    state = {}
    for slug, variables in DEVICES.items():
        state[slug] = {}
        for variable in variables:
            _, _, start, _ = VARIABLE_RANGES[variable]
            state[slug][variable] = start
    return state


def step_value(variable, current):
    low, high, _, max_step = VARIABLE_RANGES[variable]
    candidate = current + random.uniform(-max_step, max_step)
    return max(low, min(high, candidate))


def main():
    client = mqtt.Client()
    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, keepalive=60)
    client.loop_start()

    state = build_state()
    print(f"Simulator publishing to {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT} every {PUBLISH_INTERVAL_SECONDS}s")
    for slug in DEVICES:
        if slug not in DEVICE_TOKENS:
            print(f"WARNING: no token configured for '{slug}' in SIMULATOR_DEVICE_TOKENS; "
                  f"its readings will be rejected by the listener until you add one.")

    try:
        while True:
            for slug, variables in DEVICES.items():
                for variable in variables:
                    state[slug][variable] = step_value(variable, state[slug][variable])
                    payload = {
                        "value": round(state[slug][variable], 2),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "token": DEVICE_TOKENS.get(slug, ""),
                    }
                    topic = f"{MQTT_TOPIC_PREFIX}/{slug}/{variable}"
                    client.publish(topic, json.dumps(payload), qos=1)
            time.sleep(PUBLISH_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
