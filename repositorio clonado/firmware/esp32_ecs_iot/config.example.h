// Copia este archivo a "config.h" (mismo directorio) y completa tus valores.
// config.h queda ignorado por git (contiene el token del dispositivo) — ver .gitignore.
#pragma once

// --- Identidad del dispositivo (la genera la plataforma al registrar el Device) ---
// Dashboard -> Dispositivos -> "+ Agregar sensor" -> te muestra el ID (slug) y el token.
#define DEVICE_SLUG   "subestacion-01"        // debe coincidir EXACTO con el slug registrado
#define DEVICE_TOKEN  "paste-token-here"      // token único del dispositivo (regenerable desde el dashboard)
#define DEVICE_AP_TAG "subestacion-01-esp32"  // nombre del punto de acceso WiFiManager al aprovisionar

// --- WiFi (opcional): si se define, el sketch intenta conectar directo antes de
// levantar el portal cautivo de WiFiManager. Dejar vacío ("") para forzar siempre el portal
// (recomendado para hardware que se distribuye a clientes finales, ver README raíz).
#define WIFI_SSID     ""
#define WIFI_PASSWORD ""

// --- Broker MQTT ---
// Desarrollo local (docker-compose): usa la IP de tu PC en la red local (no "localhost",
// el ESP32 es otro dispositivo en la red) y el puerto MOSQUITTO_HOST_PORT de tu .env.
// Producción (Railway): usa el host:puerto del TCP Proxy (Mosquitto -> Settings -> Networking -> TCP Proxy).
#define MQTT_BROKER_HOST "192.168.1.100"
#define MQTT_BROKER_PORT 11883
#define MQTT_USERNAME    "ecs"          // MQTT_USERNAME de tu .env
#define MQTT_PASSWORD    "change-me-mqtt-password" // MQTT_PASSWORD de tu .env
#define MQTT_TOPIC_PREFIX "ecs"         // MQTT_TOPIC_PREFIX de tu .env

// --- Sensor de telemetría (dispositivo -> plataforma) ---
#define SENSOR_VARIABLE   "resistencia_tierra" // nombre de la variable (Sensor) tal como aparecerá en el dashboard
#define SENSOR_PIN        34                   // pin ADC del ESP32 (ADC1: 32-39, no requieren desactivar WiFi)
#define SENSOR_RAW_MIN    0                    // lectura ADC cruda mínima esperada (calibrar con tu instrumento real)
#define SENSOR_RAW_MAX    4095
#define SENSOR_VALUE_MIN  0.0f                 // valor físico correspondiente a SENSOR_RAW_MIN (ej. ohms, volts)
#define SENSOR_VALUE_MAX  30.0f                // valor físico correspondiente a SENSOR_RAW_MAX
#define PUBLISH_INTERVAL_MS 5000                // cada cuánto se publica una lectura

// --- Comando (plataforma -> dispositivo), opcional: gadget Botón/Slider ---
// Déjalo definido aunque no uses un relé real; si no se usa el pin, simplemente no tendrá efecto físico.
#define COMMAND_VARIABLE "relay"
#define COMMAND_PIN      2   // LED integrado en muchas placas ESP32 DevKit

// --- NTP (para incluir "timestamp" en cada lectura; opcional, el servidor puede sellar la hora de recepción) ---
#define NTP_SERVER   "pool.ntp.org"
#define GMT_OFFSET_SEC 0
#define DST_OFFSET_SEC 0
