"""Carga masiva de datos de demostración: operadores, productos, dispositivos y sensores.

Uso:
    python manage.py seed_demo_data
    python manage.py seed_demo_data --users 20 --products 15 --seed 2026

Pensado como el mecanismo de referencia para la carga masiva del proyecto:
reproducible (semilla fija), parametrizable en cantidad, y seguro de re-correr
(los nombres de usuario/slugs se resuelven contra lo que ya exista en la BD en
vez de asumir una base vacía). Genera además una serie histórica de lecturas
por sensor para que el dashboard y el mapa no se vean vacíos tras el primer
`docker compose up`.
"""
import random
import unicodedata
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from monitoring.models import Device, Product, ProductType, Profile, Sensor, SensorReading

FIRST_NAMES = [
    "Javiera", "Camila", "Matías", "Sebastián", "Fernanda", "Ignacio", "Valentina", "Diego",
    "Catalina", "Felipe", "Antonia", "Cristóbal", "Josefa", "Benjamín", "Constanza", "Vicente",
    "Trinidad", "Tomás", "Florencia", "Martín", "Isidora", "Gabriel", "Amanda", "Joaquín", "Daniela",
]
LAST_NAMES = [
    "González", "Muñoz", "Rojas", "Díaz", "Pérez", "Soto", "Contreras", "Silva", "Martínez",
    "Sepúlveda", "Morales", "Rodríguez", "López", "Fuentes", "Hernández", "Torres", "Araya",
    "Flores", "Espinoza", "Reyes", "Tapia", "Vega", "Castillo", "Bravo", "Núñez",
]

# (nombre, lat, lng) — comunas de la Región de La Araucanía, para ubicar la demo
# alrededor de Temuco en un mapa real.
COMUNAS = [
    ("Temuco", -38.7359, -72.5904),
    ("Padre Las Casas", -38.7833, -72.6000),
    ("Vilcún", -38.6667, -72.2333),
    ("Lautaro", -38.5333, -72.4333),
    ("Freire", -38.9500, -72.6167),
    ("Nueva Imperial", -38.7444, -72.9525),
    ("Gorbea", -39.1167, -72.6667),
    ("Pitrufquén", -38.9833, -72.6500),
    ("Villarrica", -39.2833, -72.2167),
    ("Angol", -37.8000, -72.7167),
    ("Victoria", -38.2333, -72.3333),
    ("Loncoche", -39.3667, -72.6333),
]

PRODUCT_TYPE_SLUGS = ["electroiman-activo", "malla-a-tierra", "barra-copperweld"]

PRODUCT_NAME_TEMPLATES = {
    "electroiman-activo": "Electroimán activo {comuna}",
    "malla-a-tierra": "Malla a tierra {comuna}",
    "barra-copperweld": "Barra Copperweld {comuna}",
}

# variable -> (unidad, valor mínimo, valor máximo, valor típico "en norma")
SENSOR_POOL_BY_TYPE = {
    "electroiman-activo": [("resistencia_tierra", "Ω", 1.0, 30.0, 6.0), ("voltaje", "V", 210.0, 230.0, 220.0)],
    "malla-a-tierra": [("resistencia_tierra", "Ω", 0.5, 20.0, 4.0)],
    "barra-copperweld": [("resistencia_tierra", "Ω", 1.0, 25.0, 8.0)],
}

READINGS_PER_SENSOR = 30
READINGS_INTERVAL_MINUTES = 20


def slugify_ascii(text):
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return "-".join(normalized.lower().split())


class Command(BaseCommand):
    help = "Carga masiva de demostración: operadores, productos, dispositivos y sensores de puesta a tierra."

    def add_arguments(self, parser):
        parser.add_argument("--users", type=int, default=20, help="Operadores nuevos a crear.")
        parser.add_argument("--products", type=int, default=15, help="Productos nuevos a crear.")
        parser.add_argument("--seed", type=int, default=2026, help="Semilla para aleatoriedad reproducible.")
        parser.add_argument(
            "--password", default="EcsIot2026!", help="Password inicial asignado a los operadores nuevos."
        )

    def handle(self, *args, **options):
        rng = random.Random(options["seed"])
        password = options["password"]
        num_users = options["users"]
        num_products = options["products"]

        admin_user = User.objects.filter(profile__role=Profile.ROLE_GLOBAL, is_active=True).first()
        if admin_user is None:
            self.stderr.write(self.style.ERROR("No hay ningún usuario Global activo; crea uno primero."))
            return

        with transaction.atomic():
            users = self._create_users(rng, num_users, password)
            sensors_created, readings_created = self._create_products(rng, num_products, users)

        self.stdout.write(self.style.SUCCESS(
            f"Listo: {len(users)} operadores nuevos (password inicial: {password}), "
            f"{num_products} productos nuevos, {sensors_created} sensores nuevos, "
            f"{readings_created} lecturas históricas generadas."
        ))

    # -- utilidades ---------------------------------------------------------

    def _unique_username(self, used, first, last):
        base = slugify_ascii(f"{first}.{last}")
        candidate = base
        suffix = 1
        while candidate in used or User.objects.filter(username=candidate).exists():
            suffix += 1
            candidate = f"{base}{suffix}"
        used.add(candidate)
        return candidate

    def _unique_slug(self, used, base):
        candidate = base
        suffix = 1
        while candidate in used or Device.objects.filter(slug=candidate).exists():
            suffix += 1
            candidate = f"{base}-{suffix}"
        used.add(candidate)
        return candidate

    def _jitter(self, lat, lng, rng, spread=0.03):
        return lat + rng.uniform(-spread, spread), lng + rng.uniform(-spread, spread)

    def _seed_readings(self, sensor, rng, low, high, typical):
        now = timezone.now()
        value = typical
        readings = []
        for i in range(READINGS_PER_SENSOR, 0, -1):
            value = max(low, min(high, value + rng.uniform(-0.5, 0.5) * (high - low) * 0.05))
            readings.append(
                SensorReading(
                    sensor=sensor,
                    value=round(value, 2),
                    timestamp=now - timedelta(minutes=READINGS_INTERVAL_MINUTES * i),
                )
            )
        SensorReading.objects.bulk_create(readings)
        return len(readings)

    # -- pasos ----------------------------------------------------------------

    def _create_users(self, rng, num_users, password):
        used_usernames = set()
        users = []
        for _ in range(num_users):
            first = rng.choice(FIRST_NAMES)
            last = rng.choice(LAST_NAMES)
            username = self._unique_username(used_usernames, first, last)
            user = User.objects.create_user(
                username=username,
                email=f"{username}@example.com",
                password=password,
                first_name=first,
                last_name=last,
            )
            Profile.objects.update_or_create(user=user, defaults={"role": Profile.ROLE_OWNER})
            users.append(user)
        return users

    def _create_products(self, rng, num_products, owners_pool):
        product_types = {slug: ProductType.objects.get(slug=slug) for slug in PRODUCT_TYPE_SLUGS}
        used_slugs = set(Device.objects.values_list("slug", flat=True))
        sensors_created = 0
        readings_created = 0

        for i in range(num_products):
            type_slug = rng.choice(PRODUCT_TYPE_SLUGS)
            product_type = product_types[type_slug]
            comuna, lat, lng = rng.choice(COMUNAS)
            owner = owners_pool[i % len(owners_pool)]

            product = Product.objects.create(
                owner=owner,
                product_type=product_type,
                name=PRODUCT_NAME_TEMPLATES[type_slug].format(comuna=comuna),
                latitude=lat,
                longitude=lng,
            )

            device_slug = self._unique_slug(used_slugs, slugify_ascii(f"{type_slug}-{comuna}-{i + 1}"))
            device_lat, device_lng = self._jitter(lat, lng, rng)
            device = Device.objects.create(
                owner=owner,
                product=product,
                name=f"Puesta a tierra {comuna} #{i + 1}",
                slug=device_slug,
                location=comuna,
                latitude=device_lat,
                longitude=device_lng,
            )

            for variable, unit, low, high, typical in SENSOR_POOL_BY_TYPE[type_slug]:
                sensor = Sensor.objects.create(device=device, variable=variable, unit=unit)
                sensors_created += 1
                readings_created += self._seed_readings(sensor, rng, low, high, typical)

        return sensors_created, readings_created
