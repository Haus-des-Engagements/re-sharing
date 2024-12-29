from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ResourcesConfig(AppConfig):
    name = "re_sharing.resources"
    verbose_name = _("Resources")
    default_auto_field = "django.db.models.BigAutoField"
