from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ProvidersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "re_sharing.providers"
    verbose_name = _("Providers")
