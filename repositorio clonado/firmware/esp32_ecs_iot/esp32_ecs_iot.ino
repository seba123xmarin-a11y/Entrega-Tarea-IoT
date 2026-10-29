// ECS IoT - firmware de ejemplo para ESP32
//
// Implementa el "Contrato MQTT" del backend (ver README.md del proyecto):
//   - Publica telemetria en   <prefix>/<slug>/<variable>          {value, timestamp, token}
//   - Escucha comandos en     <prefix>/<slug>/<variable>/set      {value, token}
//   - Al aplicar un comando, vuelve a publicar el nuevo estado en el topic de telemetria.
//
// Librerias requeridas (Arduino IDE -> Sketch -> Include Library -> Manage Libraries):
//   - WiFiManager    by tzapu
//   - PubSubClient   by Nick O'Leary
//   - ArduinoJson    by Benoit Blanchon (v6.x)
//
// Antes de compilar: copia config.example.h a config.h y completa tus datos
// (slug, token, broker, credenciales MQTT). config.h NO se sube a git.

#include <WiFi.h>
#include <WiFiManager.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <time.h>

#include "config.h"

WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);

char telemetryTopic[128];
char commandTopic[128];

unsigned long lastPublishAt = 0;

void setupWiFi() {
  if (strlen(WIFI_SSID) > 0) {
    Serial.print("Conectando directo a WiFi ");
    Serial.println(WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    unsigned long start = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
      delay(500);
      Serial.print(".");
    }
    if (WiFi.status() == WL_CONNECTED) {
      Serial.print("\nWiFi conectado, IP: ");
      Serial.println(WiFi.localIP());
      return;
    }
    Serial.println("\nNo se pudo conectar con WIFI_SSID/WIFI_PASSWORD, cae al portal cautivo.");
  }

  WiFiManager wifiManager;
  // Levanta un portal cautivo (AP) si no hay credenciales guardadas o falla la conexion.
  // El usuario final configura su WiFi conectandose a este AP desde el celular/PC.
  if (!wifiManager.autoConnect(DEVICE_AP_TAG)) {
    Serial.println("No se pudo conectar a WiFi, reiniciando...");
    delay(3000);
    ESP.restart();
  }
  Serial.print("WiFi conectado, IP: ");
  Serial.println(WiFi.localIP());
}

String isoTimestampNow() {
  time_t now;
  time(&now);
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo, 100)) {
    return ""; // sin hora sincronizada aun: se omite, el servidor usara la hora de recepcion
  }
  char buf[25];
  strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", &timeinfo);
  return String(buf);
}

void publishTelemetry(const char* variable, float value) {
  StaticJsonDocument<192> doc;
  doc["value"] = value;
  String ts = isoTimestampNow();
  if (ts.length() > 0) {
    doc["timestamp"] = ts;
  }
  doc["token"] = DEVICE_TOKEN;

  char payload[192];
  size_t len = serializeJson(doc, payload);

  char topic[128];
  snprintf(topic, sizeof(topic), "%s/%s/%s", MQTT_TOPIC_PREFIX, DEVICE_SLUG, variable);
  mqttClient.publish(topic, (uint8_t*)payload, len, false);
  // Nota: PubSubClient solo soporta QoS 0 al publicar. El contrato pide QoS 1;
  // si tu instalacion lo requiere estricto, cambia a una libreria con soporte QoS 1
  // (ej. arduino-mqtt de 256dpi) o valida en el listener que toleres QoS 0 del hardware.
  Serial.print("-> ");
  Serial.print(topic);
  Serial.print(" ");
  Serial.println(payload);
}

void readAndPublishSensor() {
  int raw = analogRead(SENSOR_PIN);
  float value = SENSOR_VALUE_MIN +
      (float)(raw - SENSOR_RAW_MIN) * (SENSOR_VALUE_MAX - SENSOR_VALUE_MIN) /
      (float)(SENSOR_RAW_MAX - SENSOR_RAW_MIN);
  publishTelemetry(SENSOR_VARIABLE, value);
}

void handleCommand(char* topic, byte* payload, unsigned int length) {
  StaticJsonDocument<192> doc;
  DeserializationError err = deserializeJson(doc, payload, length);
  if (err) {
    Serial.println("Comando con JSON invalido, se ignora.");
    return;
  }

  const char* token = doc["token"] | "";
  if (strcmp(token, DEVICE_TOKEN) != 0) {
    Serial.println("Comando con token invalido, se ignora.");
    return;
  }

  float value = doc["value"] | 0.0f;
  Serial.print("Comando recibido en ");
  Serial.print(topic);
  Serial.print(" -> value=");
  Serial.println(value);

  // Aplica el comando (ejemplo: relay/LED). Ajusta segun tu actuador real.
  digitalWrite(COMMAND_PIN, value != 0 ? HIGH : LOW);

  // Confirma el nuevo estado real publicando en el topic de telemetria (sin /set).
  publishTelemetry(COMMAND_VARIABLE, value != 0 ? 1.0f : 0.0f);
}

void reconnectMQTT() {
  while (!mqttClient.connected()) {
    Serial.print("Conectando a MQTT ");
    Serial.print(MQTT_BROKER_HOST);
    Serial.print(":");
    Serial.println(MQTT_BROKER_PORT);

    String clientId = String(DEVICE_SLUG) + "-" + String((uint32_t)ESP.getEfuseMac(), HEX);
    if (mqttClient.connect(clientId.c_str(), MQTT_USERNAME, MQTT_PASSWORD)) {
      Serial.println("MQTT conectado.");
      mqttClient.subscribe(commandTopic, 1);
      Serial.print("Suscrito a ");
      Serial.println(commandTopic);
    } else {
      Serial.print("Fallo MQTT, rc=");
      Serial.print(mqttClient.state());
      Serial.println(" reintentando en 5s...");
      delay(5000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  delay(200);

  pinMode(COMMAND_PIN, OUTPUT);
  digitalWrite(COMMAND_PIN, LOW);

  setupWiFi();

  configTime(GMT_OFFSET_SEC, DST_OFFSET_SEC, NTP_SERVER);

  snprintf(telemetryTopic, sizeof(telemetryTopic), "%s/%s/%s", MQTT_TOPIC_PREFIX, DEVICE_SLUG, SENSOR_VARIABLE);
  snprintf(commandTopic, sizeof(commandTopic), "%s/%s/%s/set", MQTT_TOPIC_PREFIX, DEVICE_SLUG, COMMAND_VARIABLE);

  mqttClient.setServer(MQTT_BROKER_HOST, MQTT_BROKER_PORT);
  mqttClient.setCallback(handleCommand);
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    setupWiFi();
  }
  if (!mqttClient.connected()) {
    reconnectMQTT();
  }
  mqttClient.loop();

  unsigned long nowMs = millis();
  if (nowMs - lastPublishAt >= PUBLISH_INTERVAL_MS) {
    lastPublishAt = nowMs;
    readAndPublishSensor();
  }
}
