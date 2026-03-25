from django.apps import AppConfig

class PiakwebConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'piakweb'

    def ready(self):
        import piakweb.signals

