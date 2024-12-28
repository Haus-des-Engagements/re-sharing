from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class OrganizationsConfig(AppConfig):
    name = "re_sharing.organizations"
    verbose_name = _("Organizations")
    default_auto_field = "django.db.models.BigAutoField"
