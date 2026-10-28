from django.db import migrations

# Pasa los gadgets de la planta (creados por setup_planta) a la vista nueva:
# estanque con consigna, velocímetro para la frecuencia y fila de indicadores.
# Si la planta no existe todavía, no hace nada.
ESP32_SLUG = "esp32-estanque"
PLC_SLUG = "plc-bomba"
FEATURED = {(ESP32_SLUG, "nivel"), (PLC_SLUG, "frecuencia"), (PLC_SLUG, "bomba_marcha"), (PLC_SLUG, "modo_auto")}


def upgrade_plant_widgets(apps, schema_editor):
    Sensor = apps.get_model("monitoring", "Sensor")
    Widget = apps.get_model("monitoring", "Widget")

    def sensor(slug, variable):
        return Sensor.objects.filter(device__slug=slug, variable=variable).first()

    nivel = sensor(ESP32_SLUG, "nivel")
    if nivel:
        Widget.objects.update_or_create(
            sensor=nivel,
            defaults={
                "widget_type": "tank",
                "min_value": 0,
                "max_value": 100,
                "setpoint_sensor": sensor(PLC_SLUG, "setpoint_nivel"),
            },
        )

    frecuencia = sensor(PLC_SLUG, "frecuencia")
    if frecuencia:
        Widget.objects.update_or_create(sensor=frecuencia, defaults={"widget_type": "gauge"})

    for slug, variable in FEATURED:
        s = sensor(slug, variable)
        if s:
            Widget.objects.update_or_create(sensor=s, defaults={"featured": True})


class Migration(migrations.Migration):

    dependencies = [
        ("monitoring", "0005_widget_tank_gauge_featured"),
    ]

    operations = [
        migrations.RunPython(upgrade_plant_widgets, migrations.RunPython.noop),
    ]
