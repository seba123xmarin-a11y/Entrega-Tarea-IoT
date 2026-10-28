import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import monitoring.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductType",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=50, unique=True)),
                ("slug", models.SlugField(unique=True)),
                (
                    "icon",
                    models.ImageField(
                        blank=True,
                        help_text="Ícono usado en los marcadores del Mapa para productos de este tipo.",
                        null=True,
                        upload_to="branding/product_types/",
                        validators=[monitoring.models.validate_image_size],
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="SiteBranding",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "logo",
                    models.ImageField(
                        blank=True,
                        null=True,
                        upload_to="branding/site/",
                        validators=[monitoring.models.validate_image_size],
                    ),
                ),
                (
                    "background_image",
                    models.ImageField(
                        blank=True,
                        null=True,
                        upload_to="branding/site/",
                        validators=[monitoring.models.validate_image_size],
                    ),
                ),
                (
                    "map_icon",
                    models.ImageField(
                        blank=True,
                        help_text="Ícono exclusivo para los marcadores del Mapa. Independiente del logo de login/dashboard.",
                        null=True,
                        upload_to="branding/site/",
                        validators=[monitoring.models.validate_image_size],
                    ),
                ),
            ],
            options={
                "verbose_name": "Marca del sitio",
                "verbose_name_plural": "Marca del sitio",
            },
        ),
        migrations.CreateModel(
            name="UnregisteredReading",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("topic", models.CharField(max_length=255)),
                ("raw_payload", models.TextField()),
                (
                    "reason",
                    models.CharField(
                        choices=[("unknown_device", "Dispositivo desconocido"), ("invalid_token", "Token inválido")],
                        default="unknown_device",
                        max_length=30,
                    ),
                ),
                ("received_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-received_at"],
            },
        ),
        migrations.CreateModel(
            name="Profile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "role",
                    models.CharField(
                        choices=[("global", "Global"), ("admin", "Administrador"), ("owner", "Operador")],
                        default="owner",
                        max_length=10,
                    ),
                ),
                (
                    "project_name",
                    models.CharField(
                        blank=True,
                        help_text="Nombre de tu proyecto/empresa. Se muestra junto a «ECS IoT» en tu dashboard.",
                        max_length=100,
                    ),
                ),
                (
                    "logo",
                    models.ImageField(
                        blank=True,
                        null=True,
                        upload_to="branding/user_logos/",
                        validators=[monitoring.models.validate_image_size],
                    ),
                ),
                (
                    "background_image",
                    models.ImageField(
                        blank=True,
                        null=True,
                        upload_to="branding/user_backgrounds/",
                        validators=[monitoring.models.validate_image_size],
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="profile",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Product",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("latitude", models.FloatField(blank=True, null=True)),
                ("longitude", models.FloatField(blank=True, null=True)),
                (
                    "icon",
                    models.ImageField(
                        blank=True,
                        help_text=(
                            "Ícono exclusivo de este producto para el Mapa (opcional). Si no se define, se usa el "
                            "ícono de su tipo. Solo el rol Global puede editarlo."
                        ),
                        null=True,
                        upload_to="branding/product_icons/",
                        validators=[monitoring.models.validate_image_size],
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="products",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "product_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="products",
                        to="monitoring.producttype",
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="Device",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                (
                    "slug",
                    models.SlugField(
                        help_text="ID del dispositivo. Debe coincidir con el segmento del topic MQTT: ecs/<slug>/<variable>",
                        unique=True,
                    ),
                ),
                (
                    "tag",
                    models.CharField(
                        blank=True,
                        help_text=(
                            "Etiqueta corta para distinguir el hardware durante el aprovisionamiento (ej. nombre "
                            "del AP WiFi de configuración)."
                        ),
                        max_length=50,
                    ),
                ),
                (
                    "auth_token",
                    models.CharField(
                        default=monitoring.models.generate_auth_token,
                        editable=False,
                        help_text=(
                            "Token único que debe programarse en el firmware del dispositivo y enviarse en cada "
                            "mensaje MQTT."
                        ),
                        max_length=64,
                        unique=True,
                    ),
                ),
                ("location", models.CharField(blank=True, max_length=200)),
                ("latitude", models.FloatField(blank=True, null=True)),
                ("longitude", models.FloatField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_seen_at", models.DateTimeField(blank=True, null=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="devices",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        blank=True,
                        help_text="Producto (puesta a tierra) al que pertenece este dispositivo (opcional).",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="devices",
                        to="monitoring.product",
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="ManualEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "note",
                    models.TextField(
                        help_text="Ej. «Medición trimestral con telurómetro: 4.2 Ω, dentro de norma»."
                    ),
                ),
                (
                    "variable",
                    models.CharField(blank=True, help_text="Ej. resistencia_tierra (opcional).", max_length=50),
                ),
                ("value", models.FloatField(blank=True, null=True)),
                ("unit", models.CharField(blank=True, max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="manual_entries",
                        to="monitoring.product",
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "Manual entries",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="Sensor",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("variable", models.CharField(help_text="ej. resistencia_tierra, voltaje, continuidad", max_length=50)),
                ("unit", models.CharField(blank=True, help_text="ej. Ω, V", max_length=20)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "device",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="sensors", to="monitoring.device"
                    ),
                ),
            ],
            options={
                "ordering": ["device__name", "variable"],
                "unique_together": {("device", "variable")},
            },
        ),
        migrations.CreateModel(
            name="SensorReading",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("value", models.FloatField()),
                ("timestamp", models.DateTimeField(db_index=True)),
                (
                    "sensor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="readings", to="monitoring.sensor"
                    ),
                ),
            ],
            options={
                "ordering": ["-timestamp"],
            },
        ),
        migrations.AddIndex(
            model_name="sensorreading",
            index=models.Index(fields=["sensor", "-timestamp"], name="monitoring__sensor__fd56b6_idx"),
        ),
        migrations.CreateModel(
            name="Widget",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "widget_type",
                    models.CharField(
                        choices=[
                            ("line_chart", "Gráfico de línea"),
                            ("numeric", "Valor numérico"),
                            ("meter", "Medidor (barra)"),
                            ("led", "Indicador LED"),
                            ("button", "Botón (control)"),
                            ("slider", "Slider (control)"),
                        ],
                        default="line_chart",
                        max_length=20,
                    ),
                ),
                ("min_value", models.FloatField(default=0, help_text="Usado por Medidor y Slider.")),
                ("max_value", models.FloatField(default=100, help_text="Usado por Medidor y Slider.")),
                (
                    "led_on_threshold",
                    models.FloatField(
                        default=1,
                        help_text=(
                            "Usado por Indicador LED: se enciende cuando el valor es mayor o igual a este umbral "
                            "(ej. resistencia de puesta a tierra por sobre el máximo permitido según la norma "
                            "aplicable)."
                        ),
                    ),
                ),
                (
                    "button_on_value",
                    models.FloatField(default=1, help_text="Usado por Botón: valor que se publica al encender."),
                ),
                (
                    "button_off_value",
                    models.FloatField(default=0, help_text="Usado por Botón: valor que se publica al apagar."),
                ),
                ("slider_step", models.FloatField(default=1, help_text="Usado por Slider.")),
                (
                    "sensor",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE, related_name="widget", to="monitoring.sensor"
                    ),
                ),
            ],
        ),
    ]
