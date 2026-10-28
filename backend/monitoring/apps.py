from django.apps import AppConfig


class MonitoringConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "monitoring"

    def ready(self):
        from django.contrib.auth import get_user_model
        from django.db.models.signals import post_save

        from .permissions import get_profile

        def _ensure_profile(sender, instance, created, **kwargs):
            # Garantiza que todo User (incluido el superusuario de bootstrap
            # creado por `createsuperuser --noinput`) tenga su Profile desde
            # el momento en que se crea, en vez de esperar su primer login
            # (get_profile ya hacía get_or_create de forma perezosa; esto solo
            # adelanta el mismo default para que comandos como seed_demo_data
            # puedan encontrar un Global inmediatamente tras el arranque).
            if created:
                get_profile(instance)

        post_save.connect(_ensure_profile, sender=get_user_model(), weak=False)
