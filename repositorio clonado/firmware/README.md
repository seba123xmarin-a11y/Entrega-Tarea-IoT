# Firmware ESP32 — ECS IoT

Sketch de ejemplo para un ESP32 que publica telemetría hacia la plataforma
ECS IoT y opcionalmente recibe comandos (gadget Botón/Slider), siguiendo el
"Contrato MQTT" documentado en el `README.md` raíz del proyecto.

## Requisitos

- [Arduino IDE](https://www.arduino.cc/en/software) 2.x con soporte para
  placas ESP32 instalado (Boards Manager → `esp32` by Espressif Systems).
- Librerías (Sketch → Include Library → Manage Libraries):
  - **WiFiManager** (tzapu)
  - **PubSubClient** (Nick O'Leary)
  - **ArduinoJson** (Benoit Blanchon, v6.x)

## 1. Registra el dispositivo en la plataforma

Antes de tocar el firmware, el `Device` debe existir en el backend (las
lecturas de un dispositivo no registrado, o con token inválido, se
descartan y quedan en cuarentena como `UnregisteredReading`):

1. Entra al dashboard (ver sección "Cómo revisar la plataforma" abajo) e
   inicia sesión.
2. **Dispositivos → + Agregar sensor**, completa nombre, **ID del
   dispositivo** (slug, ej. `subestacion-01`) y opcionalmente etiqueta/ubicación.
3. Al guardar, la plataforma muestra la página de **aprovisionamiento** con
   el **slug** y el **token** único de ese dispositivo. Cópialos.

## 2. Configura el sketch

```
copy config.example.h esp32_ecs_iot\config.h
```

Edita `esp32_ecs_iot/config.h`:

- `DEVICE_SLUG` / `DEVICE_TOKEN` — los del paso 1.
- `MQTT_BROKER_HOST` / `MQTT_BROKER_PORT`:
  - **Local (docker-compose):** la IP de la PC que corre Docker en tu red
    local (el ESP32 es otro dispositivo en la LAN, así que `localhost` no
    sirve) y el puerto `MOSQUITTO_HOST_PORT` de tu `.env`.
  - **Railway (producción):** el host:puerto del **TCP Proxy** del servicio
    `mosquitto` (Settings → Networking → TCP Proxy en Railway).
- `MQTT_USERNAME` / `MQTT_PASSWORD` — igual que `MQTT_USERNAME`/`MQTT_PASSWORD`
  de tu `.env`.
- `SENSOR_VARIABLE`, `SENSOR_PIN`, `SENSOR_RAW_MIN/MAX`, `SENSOR_VALUE_MIN/MAX`
  — calibra según el sensor real que conectes (telurómetro u otro
  instrumental con salida analógica). Los valores por defecto son solo un
  ejemplo para `resistencia_tierra`.

`config.h` está en `.gitignore` (contiene el token del dispositivo) — no se
sube al repo.

## 3. Flashea y prueba

1. Selecciona tu placa ESP32 en Arduino IDE y el puerto correspondiente.
2. Sube `esp32_ecs_iot.ino`.
3. Abre el **Monitor Serie** (115200 baud). Al primer arranque (o si no
   recuerda ninguna red), el ESP32 levanta un punto de acceso WiFi llamado
   como `DEVICE_AP_TAG` — conéctate a él desde tu celular/PC y sigue el
   portal cautivo para darle el SSID/contraseña de tu WiFi real (las
   credenciales de red **no** se programan en el código ni las pide la
   plataforma, se ingresan directo en el hardware, como indica el README raíz).
4. Tras conectar, el sketch se conecta al broker MQTT y empieza a publicar
   en `ecs/<slug>/<variable>` cada `PUBLISH_INTERVAL_MS`. Deberías ver la
   gráfica llenarse en `/monitoring/` en unos segundos.
5. Si agregaste un gadget **Botón** o **Slider** a la variable `relay`
   (`COMMAND_VARIABLE`) desde `/monitoring/sensors/<id>/widget/`, al
   accionarlo en el dashboard el ESP32 debería recibir el comando y prender/
   apagar el pin `COMMAND_PIN` (LED integrado por defecto), y el dashboard
   debe reflejar el estado confirmado.

## Diagnóstico rápido

- **No aparecen lecturas:** revisa el Monitor Serie del ESP32 (¿conectó
  WiFi? ¿conectó MQTT, o reintenta con `rc=...`?) y el Admin de Django
  (`/admin/monitoring/unregisteredreading/`) — si el mensaje llegó pero con
  slug o token incorrecto, aparecerá ahí con el motivo.
- **`rc=5` o falla de conexión MQTT:** usuario/contraseña del broker
  incorrectos (`MQTT_USERNAME`/`MQTT_PASSWORD` en `config.h` vs `.env`).
- **El comando no llega:** confirma que el topic suscrito
  (`ecs/<slug>/relay/set`, visible en el log de arranque) coincide
  exactamente con el que usa la plataforma para ese sensor.
- Puedes espiar el tráfico MQTT sin hardware con `mosquitto_sub` desde otra
  terminal (con el cliente `mosquitto` instalado o el contenedor
  `eclipse-mosquitto:2`):
  ```
  mosquitto_sub -h <broker-host> -p <puerto> -u ecs -P <MQTT_PASSWORD> -t "ecs/#" -v
  ```
