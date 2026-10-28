from django.db import migrations

# La falla del PLC pasa a mostrarse arriba como luz (verde / roja) en vez de
# como tarjeta. Si la planta no existe todavía, no hace nada.


def feature_falla(apps, schema_editor):
    Widget = apps.get_model("monitoring", "Widget")
    Widget.objects.filter(
        sensor__device__slug="plc-bomba", sensor__variable="falla", widget_type="led"
    ).update(featured=True)


class Migration(migrations.Migration):

    dependencies = [
        ("monitoring", "0007_dashboard_position"),
    ]

    operations = [
        migrations.RunPython(feature_falla, migrations.RunPython.noop),
    ]
