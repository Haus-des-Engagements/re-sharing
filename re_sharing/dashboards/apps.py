from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DashboardsConfig(AppConfig):
    name = "re_sharing.dashboards"
    verbose_name = _("Dashboards")
    default_auto_field = "django.db.models.BigAutoField"
