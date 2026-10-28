from django.db import migrations

# Tipos de producto que traía la plataforma original (puestas a tierra), que
# no aplican a la planta de llenado. Solo se borran si nadie los usa.
LEGACY_SLUGS = ["electroiman-activo", "malla-a-tierra", "barra-copperweld"]


def remove_unused_legacy_types(apps, schema_editor):
    ProductType = apps.get_model("monitoring", "ProductType")
    ProductType.objects.filter(slug__in=LEGACY_SLUGS, products__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("monitoring", "0003_profile_role_viewer"),
    ]

    operations = [
        migrations.RunPython(remove_unused_legacy_types, migrations.RunPython.noop),
    ]
