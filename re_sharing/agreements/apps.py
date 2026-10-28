from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AgreementsConfig(AppConfig):
    name = "re_sharing.agreements"
    verbose_name = _("Agreements")
    default_auto_field = "django.db.models.BigAutoField"
