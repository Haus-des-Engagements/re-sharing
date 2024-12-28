from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class RoomsConfig(AppConfig):
    name = "re_sharing.rooms"
    verbose_name = _("Rooms")
    default_auto_field = "django.db.models.BigAutoField"
