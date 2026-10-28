import json
import logging
import os
import secrets
import threading
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from pymodbus.client import ModbusTcpClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("plc_bridge")

MQTT_BROKER_HOST = os.environ.get("MQTT_BROKER_HOST", "mosquitto")
MQTT_BROKER_PORT = int(os.environ.get("MQTT_BROKER_PORT", "1883"))
MQTT_USERNAME = os.environ.get("MQTT_USERNAME", "")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD", "")
MQTT_TOPIC_PREFIX = os.environ.get("MQTT_TOPIC_PREFIX", "ecs")

PLC_HOST = os.environ.get("PLC_HOST", "192.168.0.1")
PLC_PORT = int(os.environ.get("PLC_PORT", "502"))
PLC_UNIT_ID = int(os.environ.get("PLC_UNIT_ID", "1"))
PLC_POLL_SECONDS = float(os.environ.get("PLC_POLL_SECONDS", "0.5"))
PLC_PUBLISH_SECONDS = float(os.environ.get("PLC_PUBLISH_SECONDS", "2"))

PLC_SLUG = os.environ.get("PLC_DEVICE_SLUG", "plc-bomba")
PLC_TOKEN = os.environ.get("PLC_DEVICE_TOKEN", "")
ESP32_SLUG = os.environ.get("ESP32_DEVICE_SLUG", "esp32-estanque")
# Opcional: si se define, solo se reenvía al PLC el nivel firmado con este token.
ESP32_TOKEN = os.environ.get("ESP32_DEVICE_TOKEN", "")

# --- Mapa de registros (holding registers, dirección 0 = 40001) ---
# Escritura Raspberry -> PLC
REG_CMD_MARCHA = 0
REG_CMD_MODO_AUTO = 1
REG_CMD_SETPOINT = 2      # % x10
REG_CMD_VELOCIDAD = 3     # Hz x10
REG_NIVEL = 4             # % x10 (desde el ESP32)
REG_WATCHDOG = 5
# Lectura PLC -> Raspberry (bloque contiguo desde REG_STATE_START)
REG_STATE_START = 10
STATE_VARIABLES = [
    # (variable MQTT, escala)
    ("bomba_marcha", 1),
    ("modo_auto", 1),
    ("setpoint_nivel", 10),
    ("velocidad_ref", 10),
    ("frecuencia", 10),
    ("falla", 1),
]

# variable MQTT del comando -> (registro, escala, mínimo, máximo)
COMMANDS = {
    "bomba_marcha": (REG_CMD_MARCHA, 1, 0, 1),
    "modo_auto": (REG_CMD_MODO_AUTO, 1, 0, 1),
    "setpoint_nivel": (REG_CMD_SETPOINT, 10, 0, 100),
    "velocidad_ref": (REG_CMD_VELOCIDAD, 10, 0, 50),
}


class Bridge:
    def __init__(self):
        self.plc = ModbusTcpClient(PLC_HOST, port=PLC_PORT, timeout=2)
        self.plc_lock = threading.Lock()
        self.mqtt = mqtt.Client()
        if MQTT_USERNAME:
            self.mqtt.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        self.mqtt.on_connect = self.on_connect
        self.mqtt.on_message = self.on_message
        self.nivel = None
        self.watchdog = 0
        self.force_publish = False

    # --- MQTT ---
    def on_connect(self, client, userdata, flags, rc):
        if rc != 0:
            log.error("Falla de conexión MQTT rc=%s", rc)
            return
        log.info("MQTT conectado a %s:%s", MQTT_BROKER_HOST, MQTT_BROKER_PORT)
        client.subscribe(f"{MQTT_TOPIC_PREFIX}/{PLC_SLUG}/+/set", qos=1)
        client.subscribe(f"{MQTT_TOPIC_PREFIX}/{ESP32_SLUG}/nivel", qos=1)

    def on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return
        parts = msg.topic.split("/")
        value = data.get("value")
        if not isinstance(value, (int, float)):
            return

        if len(parts) == 3 and parts[1] == ESP32_SLUG:
            if ESP32_TOKEN and not secrets.compare_digest(str(data.get("token", "")), ESP32_TOKEN):
                log.warning("Nivel con token inválido, se ignora")
                return
            self.nivel = float(value)
            return

        if len(parts) == 4 and parts[3] == "set":
            if not secrets.compare_digest(str(data.get("token", "")), PLC_TOKEN):
                log.warning("Comando con token inválido en %s, se ignora", msg.topic)
                return
            command = COMMANDS.get(parts[2])
            if command is None:
                log.warning("Comando desconocido: %s", parts[2])
                return
            register, scale, low, high = command
            raw = int(round(max(low, min(high, float(value))) * scale))
            if self.write_register(register, raw):
                log.info("Comando %s = %s -> HR%d = %d", parts[2], value, register, raw)
                self.force_publish = True

    def publish(self, variable, value):
        payload = {
            "value": round(float(value), 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "token": PLC_TOKEN,
        }
        self.mqtt.publish(f"{MQTT_TOPIC_PREFIX}/{PLC_SLUG}/{variable}", json.dumps(payload), qos=1)

    # --- Modbus ---
    def write_register(self, register, value):
        with self.plc_lock:
            try:
                if not self.plc.connected:
                    self.plc.connect()
                result = self.plc.write_register(register, value & 0xFFFF, slave=PLC_UNIT_ID)
                if result.isError():
                    log.error("Error escribiendo HR%d: %s", register, result)
                    return False
                return True
            except Exception as exc:
                log.error("PLC no disponible al escribir HR%d: %s", register, exc)
                self.plc.close()
                return False

    def read_state(self):
        with self.plc_lock:
            try:
                if not self.plc.connected:
                    self.plc.connect()
                result = self.plc.read_holding_registers(
                    REG_STATE_START, count=len(STATE_VARIABLES), slave=PLC_UNIT_ID
                )
                if result.isError():
                    log.error("Error leyendo estado del PLC: %s", result)
                    return None
                return {
                    variable: raw / scale
                    for (variable, scale), raw in zip(STATE_VARIABLES, result.registers)
                }
            except Exception as exc:
                log.error("PLC no disponible en %s:%s: %s", PLC_HOST, PLC_PORT, exc)
                self.plc.close()
                return None

    def run(self):
        if not PLC_TOKEN:
            log.warning("PLC_DEVICE_TOKEN vacío: el listener rechazará las lecturas. "
                        "Corre `python manage.py setup_planta` para obtenerlo.")
        self.mqtt.reconnect_delay_set(min_delay=1, max_delay=30)
        self.mqtt.connect_async(MQTT_BROKER_HOST, MQTT_BROKER_PORT, keepalive=60)
        self.mqtt.loop_start()
        log.info("Puente PLC %s:%s (unit %s) <-> MQTT", PLC_HOST, PLC_PORT, PLC_UNIT_ID)

        last_publish = 0.0
        while True:
            self.watchdog = (self.watchdog + 1) % 32768
            self.write_register(REG_WATCHDOG, self.watchdog)
            if self.nivel is not None:
                self.write_register(REG_NIVEL, int(round(self.nivel * 10)))

            now = time.monotonic()
            if self.force_publish or now - last_publish >= PLC_PUBLISH_SECONDS:
                state = self.read_state()
                if state is not None:
                    for variable, value in state.items():
                        self.publish(variable, value)
                    last_publish = now
                    self.force_publish = False
            time.sleep(PLC_POLL_SECONDS)


if __name__ == "__main__":
    Bridge().run()
