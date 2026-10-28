from django.db import migrations

PRODUCT_TYPES = [
    ("Electroimán activo", "electroiman-activo"),
    ("Malla a tierra", "malla-a-tierra"),
    ("Barra Copperweld", "barra-copperweld"),
]


def seed_product_types(apps, schema_editor):
    ProductType = apps.get_model("monitoring", "ProductType")
    for name, slug in PRODUCT_TYPES:
        ProductType.objects.get_or_create(slug=slug, defaults={"name": name})


def remove_product_types(apps, schema_editor):
    ProductType = apps.get_model("monitoring", "ProductType")
    ProductType.objects.filter(slug__in=[slug for _, slug in PRODUCT_TYPES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("monitoring", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_product_types, remove_product_types),
    ]
