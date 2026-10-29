# ECS IoT

Plataforma de monitoreo de sensores IoT de **puesta a tierra / protección
eléctrica** vía MQTT (Mosquitto) con backend Django y dashboard en tiempo casi
real (polling) usando Chart.js. Propiedad de **Electrical Services Company
Temuco**.

## Arquitectura

```
sensores/simulador --MQTT--> mosquitto --suscripción--> mqtt_listener (Django mgmt command) --ORM--> PostgreSQL
                                                                                                        ^
                                                                                                        |
                                                                                        web (Django, gunicorn) <-- navegador (polling cada ~2.5s)
```

Servicios (`docker-compose.yml`):

| Servicio        | Rol                                                              |
|-----------------|-------------------------------------------------------------------|
| `mosquitto`     | Broker MQTT, autenticación por usuario/contraseña                |
| `db`            | PostgreSQL                                                        |
| `migrate`       | Job one-shot: migraciones + creación del superusuario Global       |
| `web`           | Django (gunicorn) sirviendo el dashboard y la API JSON            |
| `mqtt_listener` | Suscriptor MQTT que persiste lecturas en PostgreSQL                |
| `simulator`     | Publica datos falsos de sensores de puesta a tierra para probar el sistema |

No hay Redis, Channels ni WebSockets: las gráficas se actualizan por *polling*
HTTP cada ~2.5s desde el navegador, suficiente para variables físicas
(resistencia de puesta a tierra, voltaje, etc.) que no cambian a nivel
sub-segundo. Si en el futuro se necesita push en tiempo real, ver la sección
"Posibles mejoras futuras".

## Requisitos

- Docker Desktop (Windows/Mac/Linux)
- Git

## Primer arranque

### 1. Configurar variables de entorno

```
copy .env.example .env
```

Edita `.env` y cambia todas las contraseñas (`POSTGRES_PASSWORD`, `MQTT_PASSWORD`,
`DJANGO_SUPERUSER_PASSWORD`, `DJANGO_SECRET_KEY`).

> Las URLs de esta guía asumen el puerto por defecto (`8000`). Si cambiaste
> `WEB_HOST_PORT` en tu `.env` (por ejemplo para evitar un choque con otro
> proyecto que ya usa el 8000 en tu máquina), sustituye el puerto en todas las
> URLs siguientes por el que hayas configurado.

### 2. Generar el archivo de contraseñas de Mosquitto

Este paso se hace **una sola vez** (el archivo `mosquitto/config/passwd` no se
regenera automáticamente ni se sube a git). Usa el mismo usuario/contraseña que
pusiste en `.env` como `MQTT_USERNAME` / `MQTT_PASSWORD`:

```
docker run --rm -v "%cd%/mosquitto/config:/mosquitto/config" eclipse-mosquitto:2 sh -c "mosquitto_passwd -b -c /mosquitto/config/passwd ecs change-me-mqtt-password && chmod 644 /mosquitto/config/passwd"
```

(En PowerShell usa `${PWD}` en vez de `%cd%` si `%cd%` no se expande.)

El `chmod 644` es necesario: `mosquitto_passwd -c` crea el archivo con permisos `600`
(solo root), pero el proceso de Mosquitto corre internamente como el usuario
`mosquitto` sin privilegios y no puede leer un archivo `600` — sin el `chmod`,
el contenedor `mosquitto` entra en un bucle de reinicio con el error
`Unable to open pwfile`.

### 3. Levantar todo

```
docker compose up --build
```

Esto construye las imágenes, espera a que `db` y `mosquitto` estén healthy,
corre `migrate` (migraciones + superusuario), y luego levanta `web`,
`mqtt_listener` y `simulator`.

### 4. Registrar un dispositivo desde el dashboard

Inicia sesión en `http://localhost:8000/monitoring/` con el superusuario
definido en `.env` (queda como rol **Global** automáticamente), y haz clic en
**"+ Agregar sensor"** (o ve directo a
`http://localhost:8000/monitoring/devices/add/`). Completa:

- **Nombre** — nombre descriptivo (ej. "Puesta a tierra Subestación Norte").
- **ID del dispositivo** — identificador único que se usará en el topic MQTT
  (ej. `subestacion-01`).
- **Etiqueta** (opcional) — para distinguir el hardware durante su
  aprovisionamiento.
- **Ubicación** (opcional).

Al guardar, la plataforma te lleva a la página de aprovisionamiento del
dispositivo, que muestra el **ID** y un **token único** — prográmalos en el
firmware del hardware embebido (ver "Contrato MQTT" abajo). Puedes volver a
ver el ID/token de cualquier dispositivo, o regenerar su token, desde
`http://localhost:8000/monitoring/devices/`.

Por seguridad, un `Device` debe registrarse (con su token) antes de que sus
lecturas MQTT se acepten — así, aunque alguien conozca la contraseña
compartida del broker MQTT, no puede inyectar datos como si fuera un
dispositivo tuyo sin también conocer su token. El Admin (`/admin/`) sigue
disponible para gestión avanzada (desactivar dispositivos, revisar lecturas
en cuarentena, etc.).

El simulador (`simulator/simulate.py`) publica datos falsos para tres
dispositivos de ejemplo — regístralos con estos mismos slugs y copia sus
tokens generados a `SIMULATOR_DEVICE_TOKENS` en tu `.env`
(`slug:token,slug:token,...`), luego `docker compose up -d simulator` para
que tome los tokens nuevos:

| slug                    | variables                        |
|-------------------------|-----------------------------------|
| `subestacion-01`        | `resistencia_tierra`, `voltaje`   |
| `sala-electrica-02`     | `resistencia_tierra`              |
| `torre-transmision-03`  | `resistencia_tierra`              |

Si usas sensores reales (telurómetros u otro instrumental con salida
programable) en vez del simulador, registra un `Device` por cada uno con el
`slug` que tú definas y programa su token en el firmware.

Alternativamente, `python manage.py seed_demo_data` (ver más abajo) carga de
golpe operadores, productos, dispositivos y lecturas históricas de
demostración sin depender del simulador.

### 5. Ver el dashboard

```
http://localhost:8000/monitoring/
```

Las gráficas se llenan solas conforme llegan lecturas por MQTT.

### 6. Elegir el gadget de cada sensor

Cada tarjeta de sensor tiene un enlace "⚙" que abre
`/monitoring/sensors/<id>/widget/`, donde eliges cómo se visualiza:

| Gadget              | Tipo         | Descripción                                              |
|---------------------|--------------|-------------------------------------------------------------|
| Gráfico de línea    | Visualización| El de siempre (por defecto para sensores nuevos).            |
| Valor numérico      | Visualización| Solo el último valor, en grande.                              |
| Medidor (barra)     | Visualización| Barra de relleno entre un mínimo y máximo configurables.      |
| Indicador LED       | Visualización| Punto que se enciende cuando el valor supera un umbral (ej. resistencia de puesta a tierra fuera de norma). |
| Botón               | **Control**  | Envía un comando (encender/apagar) al dispositivo.            |
| Slider              | **Control**  | Envía un valor numérico dentro de un rango al dispositivo.    |

Para sensores de `resistencia_tierra`, el **Medidor** o el **Indicador LED**
(con `led_on_threshold` seteado al máximo permitido por la norma eléctrica
aplicable a esa instalación) son los más útiles como indicador de
cumplimiento a simple vista. Cada instalación puede tener su propio umbral —
no está hardcodeado en la plataforma.

## Contrato MQTT

### Telemetría (dispositivo → plataforma)

- **Topic:** `ecs/<device_slug>/<variable>` (ej. `ecs/subestacion-01/resistencia_tierra`)
- **Payload (JSON):**
  ```json
  {"value": 4.8, "timestamp": "2026-07-10T12:00:00Z", "token": "<token del dispositivo>"}
  ```
  (`timestamp` es opcional; si falta, el servidor usa la hora de recepción)
- **QoS:** 1, sin retain.

El `Device` (`device_slug`) debe estar registrado de antemano (vía el
dashboard o el Admin), y cada mensaje debe incluir su `token` — se compara
contra el token generado al registrarlo. El `Sensor` (la variable, ej.
`resistencia_tierra`) sí se crea automáticamente en el primer mensaje válido
para ese dispositivo: no hace falta declarar las variables de antemano.

### Comandos (plataforma → dispositivo) — solo gadgets Botón/Slider

- **Topic:** `ecs/<device_slug>/<variable>/set` (ej. `ecs/subestacion-01/relay/set`)
- **Payload (JSON):** `{"value": 1, "token": "<token del dispositivo>"}`
- **QoS:** 1.

Cuando usas un gadget Botón o Slider, la plataforma publica en este topic al
hacer click / soltar el slider. **Tu firmware debe:**

1. Suscribirse a `<prefix>/<tu-slug>/<variable>/set`.
2. Validar que `token` coincida con el que tiene programado (mismo modelo
   de confianza que la telemetría: la contraseña del broker MQTT es
   compartida, el token es lo que identifica a *tu* dispositivo).
3. Aplicar el comando (ej. activar un electroimán) y **volver a publicar su
   nuevo estado** en el topic normal de telemetría (sin `/set`) — así el
   botón/slider en el dashboard confirma el cambio real en vez de asumirlo
   a ciegas.

El simulador (`simulator/simulate.py`) no implementa este lado (simula
sensores de solo lectura); para probar el canal de comandos sin hardware
real, puedes escuchar el topic `.../set` con `mosquitto_sub` desde otro
contenedor conectado a la misma red de Docker.

Los mensajes rechazados se guardan en `UnregisteredReading` (visible en el
Admin) con el motivo (`unknown_device` o `invalid_token`) en vez de crear un
dispositivo fantasma o aceptar datos sin autenticar.

### WiFi y aprovisionamiento del hardware

El SSID/contraseña de tu red WiFi y el nombre del punto de acceso de
configuración del propio dispositivo se ingresan **directamente en el
hardware** (ej. vía un portal cautivo tipo WiFiManager en un ESP32/ESP8266) —
la plataforma no los solicita ni los almacena. La página de aprovisionamiento
de cada dispositivo sugiere un nombre para ese punto de acceso
(`<slug>-<etiqueta>`) solo como referencia.

## Roles y usuarios

Todo se gestiona desde el dashboard (`/monitoring/`), no hace falta el Admin
de Django para el uso normal. Tres roles (`monitoring/models.py:Profile`):

| Rol            | Alcance                                                                 |
|----------------|----------------------------------------------------------------------------|
| **Global**     | Ve y administra los dispositivos de **todos** los usuarios, incluido el mapa global y los productos contratados de todos los clientes. |
| **Administrador** | Administra sus propios dispositivos (como Operador) + puede dar de alta/baja cuentas desde `/monitoring/users/`. No puede crear cuentas Global. |
| **Operador**   | La empresa que contrata el servicio. Administra solo los dispositivos y puestas a tierra que él mismo registra. |

El superusuario creado por `DJANGO_SUPERUSER_*` (ver arriba) es **Global**
automáticamente desde el momento en que se crea. Para crear más usuarios,
inicia sesión como Global o Administrador y ve a **Usuarios → + Agregar
usuario**. No hay auto-registro público ni recuperación de contraseña — el
alta la hace siempre un Administrador/Global, asignando la contraseña
inicial directamente.

Desactivar una cuenta (`/monitoring/users/`) no la borra — solo bloquea el
login; se puede reactivar en cualquier momento.

## Productos (electroimán activo, malla a tierra, barra Copperweld, ...)

Un **Producto** (`/monitoring/products/`) agrupa uno o más dispositivos bajo
un nombre y un tipo — ej. "Malla a tierra - Subestación Norte" (tipo Malla a
tierra). Al crearlo:

- Puedes **agregarle un sensor** (`+ Agregar sensor a este producto`) — un
  dispositivo normal, solo que queda vinculado al producto.
- Si **no** le agregas ningún sensor, puedes registrar el estado a mano
  (nota + opcionalmente una variable/valor/unidad, ej. una medición manual
  con telurómetro) desde la misma página del producto.
- Tiene su propia ubicación (`Configurar ubicación`), independiente de la de
  sus dispositivos.

En el **Mapa**, cada producto aparece como **un solo marcador** (aunque
tenga varios dispositivos/sensores) con el ícono de su tipo, y al hacer
click muestra el tipo + todos sus sensores combinados, o sus últimas
entradas manuales si no tiene sensor. Los dispositivos que **no** pertenecen
a ningún producto siguen apareciendo sueltos, con el ícono genérico.

El rol Global gestiona los **tipos de producto** y sus íconos desde
`/monitoring/product-types/` — vienen 3 precargados (**Electroimán activo**,
**Malla a tierra**, **Barra Copperweld**) con el ícono genérico del Mapa por
defecto; se pueden reemplazar las veces que quieras, y el rol Global puede
crear **tipos nuevos** en cualquier momento (ej. uno específico que pida un
cliente) sin tocar código.

## Carga masiva de datos de demostración

El mecanismo para poblar el sistema con operadores, productos, dispositivos y
sensores de golpe es el management command `seed_demo_data`
(`backend/monitoring/management/commands/seed_demo_data.py`):

```
docker compose exec web python manage.py seed_demo_data
```

Es reproducible (semilla fija con `--seed`) y parametrizable (`--users`,
`--products`, `--password`). Reutiliza usuarios/slugs existentes en vez de
asumir una base vacía, así que puede volver a correrse sin duplicar lo ya
creado por una corrida anterior con la misma semilla. Además genera una
serie histórica de ~30 lecturas por sensor (últimas horas) para que el
dashboard y el mapa no se vean vacíos tras el primer arranque. Este mismo
patrón (management command idempotente + parámetros) es el que conviene
seguir para cualquier carga masiva futura (ej. importar un CSV real de
dispositivos: se agregaría como una opción `--from-csv` a este mismo command
en vez de un mecanismo aparte).

## Panorama global (solo Global)

`/monitoring/overview/` — foto del estado actual (no historial): total de
usuarios por rol, y por cada usuario cuántos productos tiene de cada tipo,
y cuántos dispositivos/sensores activos e inactivos.

## Geolocalización (Google Maps)

Cualquier usuario puede fijar la ubicación de sus dispositivos sueltos desde
**Dispositivos → Ubicación**, o de sus productos desde
**Productos → Configurar ubicación**, y ver todo geolocalizado en **Mapa**
(un usuario Global ve lo de todos los usuarios ahí mismo).

Requiere una API key de Google Maps en tu `.env`:

1. Entra a [Google Cloud Console](https://console.cloud.google.com/), crea o
   selecciona un proyecto.
2. Habilita **Maps JavaScript API**.
3. Crea una API key (Credenciales → Crear credenciales → Clave de API) y
   restríngela por HTTP referrer (tu dominio, o `localhost` en desarrollo) —
   la key viaja al navegador, así que sin esta restricción cualquiera podría
   reusarla.
4. Pégala en `.env` como `GOOGLE_MAPS_API_KEY` y corre `docker compose up -d web`.

Sin la key configurada, esas páginas muestran un aviso con estos mismos
pasos en vez del mapa, pero igual puedes guardar coordenadas manualmente
(campos de latitud/longitud) mientras tanto.

## Identidad visual

Los colores (`backend/monitoring/static/monitoring/css/dashboard.css`,
variables `--brand-primary`/`--brand-accent`) son un **placeholder
genérico** (grafito `#1F2933` + amarillo seguridad `#F2A900`) — no son
necesariamente la marca real de Electrical Services Company Temuco. En
cuanto tengas los hex definitivos, se reemplazan ahí.

El **logo**, la **imagen de fondo** y el **ícono del mapa** son totalmente
configurables desde el dashboard (sin tocar código):

- **Marca del sitio** (`/monitoring/branding/`, solo rol Global) — tres
  campos independientes:
  - **Logo** e **imagen de fondo**: valor por defecto de ECS IoT, usados
    en la pantalla de **login** y en el dashboard de cualquier usuario que
    no haya subido los suyos propios.
  - **Ícono del mapa**: exclusivo para los marcadores de `/monitoring/map/`.
    No tiene relación con el logo de login/dashboard ni con el de "Mi
    proyecto" de ningún usuario — solo el rol Global lo sube/reemplaza, y
    aparece igual para todos los usuarios que vean el mapa.
- **Mi proyecto** (`/monitoring/profile/branding/`, cualquier usuario) — cada
  usuario (operador) puede poner el nombre de su propia empresa (se muestra
  junto a "ECS IoT", que siempre queda como título general) y su propio logo
  e imagen de fondo, que sobrescriben los de Marca del sitio solo en *su*
  dashboard (nunca en el mapa ni en el login).

Las imágenes se guardan en un volumen Docker (`media_data`, servido en
`/media/`) — persisten entre reinicios y rebuilds, pero **no** se
respaldan automáticamente; si migras a otro servidor, copia también ese
volumen. Límite de 5MB por imagen (formatos que entienda Pillow: JPG, PNG,
WEBP, etc.).

## Migración a un servidor Linux

Todo está containerizado y las rutas son relativas al proyecto, así que mover
esto a un servidor Linux es: copiar el repo, copiar/regenerar `.env` y
`mosquitto/config/passwd` con credenciales nuevas para ese entorno, y correr
`docker compose up --build -d`.

## Despliegue en Railway (producción)

La app corre en 4 servicios independientes dentro de un mismo proyecto de
Railway (railway.app), todos conectados al mismo repo de GitHub con
auto-deploy en cada push a `main`.

### 1. Crear el proyecto

1. Crea una cuenta en [railway.app](https://railway.app) (login con GitHub).
2. **New Project → Deploy from GitHub repo** → selecciona `urbanatika/ecs-iot`.
   Railway crea el primer servicio; los siguientes se agregan con
   **+ New → GitHub Repo** (mismo repo, distinto Root Directory) dentro del
   mismo proyecto para que compartan red interna.

### 2. Base de datos

**+ New → Database → PostgreSQL** (plugin administrado de Railway). Railway
expone las variables `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`
automáticamente — mapéalas a las que usa `settings.py` en cada servicio que
las necesite (`POSTGRES_HOST=${{Postgres.PGHOST}}`, etc., usando referencias
de variables de Railway).

### 3. Servicio `web`

- **Root Directory:** `backend`
- Build: detecta el `Dockerfile` automáticamente.
- **Variables** (Settings → Variables): todas las de `.env.example` excepto
  `WEB_HOST_PORT`/`MOSQUITTO_HOST_PORT` (esos son solo para docker-compose
  local). Railway inyecta `PORT` solo — el `Dockerfile` ya escucha en
  `${PORT:-8000}` y corre `migrate` automáticamente antes de `gunicorn`.
- Agrega además:
  - `DJANGO_ALLOWED_HOSTS=<tu-dominio>.up.railway.app`
  - `DJANGO_CSRF_TRUSTED_ORIGINS=https://<tu-dominio>.up.railway.app`
- **Settings → Networking → Generate Domain** para obtener la URL pública.

### 4. Servicio `mqtt_listener`

Mismo repo, **Root Directory:** `backend`, mismas variables que `web` (usa
Postgres y Mosquitto). En **Settings → Deploy → Custom Start Command**:
`python manage.py run_mqtt_listener`.

### 5. Servicio `mosquitto`

- **Root Directory:** `mosquitto` (usa el `Dockerfile` nuevo — genera el
  `passwd` desde variables de entorno en cada arranque, no necesita el bind
  mount que usa docker-compose local).
- **Variables:** `MQTT_USERNAME`, `MQTT_PASSWORD` (los mismos valores que en
  `web`/`mqtt_listener`).
- **Settings → Networking → TCP Proxy** → expón el puerto `1883`. Railway te
  da un host:puerto público (ej. `roundhouse.proxy.rlwy.net:12345`) — ese es
  el endpoint al que deben apuntar los sensores/dispositivos reales para
  publicar por MQTT desde internet.
- En `web`/`mqtt_listener`, `MQTT_BROKER_HOST`/`MQTT_BROKER_PORT` deben
  apuntar al **host interno** de Railway (`mosquitto.railway.internal`,
  puerto `1883`), no al proxy TCP público — la comunicación entre servicios
  del mismo proyecto va por red privada.

### 6. `simulator`

No lo despliegues en producción — solo genera datos falsos y ensuciaría las
lecturas reales. Es solo para desarrollo local vía docker-compose.

### 7. Primer superusuario

El primer deploy de `web` corre `migrate` pero no crea el superusuario (eso
lo hacía el servicio `migrate` de docker-compose, que no existe en Railway).
Créalo una vez desde la pestaña **Shell/Console** de Railway en el servicio
`web`, o desde tu máquina con `railway run python manage.py createsuperuser`
tras `railway link` al proyecto.

## Posibles mejoras futuras

- **Tiempo real vía WebSocket:** si se necesita latencia sub-segundo o muchos
  viewers concurrentes, añadir Django Channels + Redis. El cambio es aditivo:
  `mqtt_listener` gana un `channel_layer.group_send(...)` después de guardar
  cada lectura, y el JS de polling se reemplaza por un `onmessage` de
  WebSocket (el mismo payload JSON sirve para ambos).
- **TimescaleDB:** si el volumen de lecturas crece mucho, cambiar la imagen
  `postgres:16-alpine` por `timescale/timescaledb` y correr
  `SELECT create_hypertable('monitoring_sensorreading', 'timestamp')`.
- **Alertas automáticas:** notificar (email/SMS/webhook) cuando una lectura
  de `resistencia_tierra` supera el umbral configurado en el Widget LED de
  ese sensor, en vez de depender solo de que un operador mire el dashboard.
