"""Crea los dispositivos, variables y gadgets de la planta de llenado de estanque.

Uso:
    python manage.py setup_planta
    python manage.py setup_planta --owner admin

Registra dos dispositivos:

- ``esp32-estanque``: el ESP32 con el sensor ultrasónico de nivel.
- ``plc-bomba``: el S7-1200 + variador D700, publicado por el puente
  Modbus TCP que corre en la Raspberry Pi (``plc_bridge/``).

Además crea el usuario de solo lectura para el profesor (``cliente`` /
``123456`` por defecto, rol Visualizador): solo ve el dashboard.

Es seguro de re-correr: si los dispositivos ya existen, solo actualiza sus
variables y gadgets (los tokens no cambian). Si el usuario de solo lectura ya
existe, no le cambia la contraseña. Al final imprime los tokens y
la línea lista para pegar en ``.env``.
"""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from monitoring.models import Device, Profile, Sensor, Widget

ESP32_SLUG = "esp32-estanque"
PLC_SLUG = "plc-bomba"

# slug -> (nombre, etiqueta, [(variable, unidad, widget_type, opciones del widget)])
PLANT_DEVICES = {
    ESP32_SLUG: (
        "Estanque (ESP32)",
        "esp32",
        [
            ("nivel", "%", Widget.TYPE_TANK, {"min_value": 0, "max_value": 100, "featured": True}),
        ],
    ),
    PLC_SLUG: (
        "Bomba (PLC S7-1200 + VDF D700)",
        "s7-1200",
        [
            ("bomba_marcha", "", Widget.TYPE_BUTTON, {"button_on_value": 1, "button_off_value": 0, "featured": True}),
            ("modo_auto", "", Widget.TYPE_BUTTON, {"button_on_value": 1, "button_off_value": 0, "featured": True}),
            ("setpoint_nivel", "%", Widget.TYPE_SLIDER, {"min_value": 0, "max_value": 100, "slider_step": 5}),
            ("velocidad_ref", "Hz", Widget.TYPE_SLIDER, {"min_value": 0, "max_value": 50, "slider_step": 1}),
            ("frecuencia", "Hz", Widget.TYPE_GAUGE, {"min_value": 0, "max_value": 50, "featured": True}),
            ("falla", "", Widget.TYPE_LED, {"led_on_threshold": 1, "featured": True}),
        ],
    ),
}


class Command(BaseCommand):
    help = "Registra los dispositivos y gadgets de la planta de llenado (ESP32 + PLC/VDF)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--owner",
            help="Usuario dueño de los dispositivos (por defecto, el primer usuario Global activo).",
        )
        parser.add_argument("--viewer-username", default="cliente", help="Usuario de solo lectura.")
        parser.add_argument("--viewer-password", default="123456", help="Contraseña inicial del usuario de solo lectura.")

    @transaction.atomic
    def handle(self, *args, **options):
        owner = self._resolve_owner(options.get("owner"))

        devices = {}
        for slug, (name, tag, variables) in PLANT_DEVICES.items():
            device, created = Device.objects.get_or_create(
                slug=slug, defaults={"owner": owner, "name": name, "tag": tag}
            )
            devices[slug] = device
            self.stdout.write(f"{'Creado' if created else 'Ya existía'}: {device.name} ({slug})")

            for variable, unit, widget_type, widget_options in variables:
                sensor, _ = Sensor.objects.get_or_create(
                    device=device, variable=variable, defaults={"unit": unit}
                )
                if sensor.unit != unit:
                    sensor.unit = unit
                    sensor.save(update_fields=["unit"])
                Widget.objects.update_or_create(
                    sensor=sensor, defaults={"widget_type": widget_type, **widget_options}
                )

        # El estanque dibuja el setpoint del PLC como línea de consigna.
        setpoint = Sensor.objects.get(device=devices[PLC_SLUG], variable="setpoint_nivel")
        Widget.objects.filter(sensor__device=devices[ESP32_SLUG], sensor__variable="nivel").update(
            setpoint_sensor=setpoint
        )

        self._ensure_viewer(options["viewer_username"], options["viewer_password"])

        esp32_token = devices[ESP32_SLUG].auth_token
        plc_token = devices[PLC_SLUG].auth_token
        self.stdout.write(self.style.SUCCESS("\nListo. Pega estas líneas en tu .env:\n"))
        self.stdout.write(f"SIMULATOR_DEVICE_TOKENS={ESP32_SLUG}:{esp32_token},{PLC_SLUG}:{plc_token}")
        self.stdout.write(f"PLC_DEVICE_TOKEN={plc_token}")
        self.stdout.write(f"\nY en firmware/esp32_ecs_iot/config.h:\n#define DEVICE_TOKEN \"{esp32_token}\"")

    def _ensure_viewer(self, username, password):
        viewer, created = User.objects.get_or_create(username=username)
        if created:
            # set_password no pasa por los validadores, así que acepta una clave simple.
            viewer.set_password(password)
            viewer.save()
        Profile.objects.update_or_create(user=viewer, defaults={"role": Profile.ROLE_VIEWER})
        if created:
            self.stdout.write(f"Creado usuario de solo lectura: {username} / {password}")
        else:
            self.stdout.write(f"Usuario de solo lectura {username!r} ya existía (contraseña sin cambios).")

    def _resolve_owner(self, username):
        if username:
            owner = User.objects.filter(username=username).first()
            if owner is None:
                raise CommandError(f"No existe el usuario {username!r}.")
            return owner
        owner = User.objects.filter(profile__role=Profile.ROLE_GLOBAL, is_active=True).order_by("pk").first()
        if owner is None:
            raise CommandError("No hay un usuario Global. Crea el superusuario primero o usa --owner.")
        return owner
