from django.apps import AppConfig


class ResourcesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "resources"
    verbose_name = "软件库"

    def ready(self):
        from . import signals  # noqa: F401
