from django.apps import AppConfig


class HotellappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hotellapp'

    def ready(self):
        # Import signal handlers
        from . import signals  # noqa: F401
