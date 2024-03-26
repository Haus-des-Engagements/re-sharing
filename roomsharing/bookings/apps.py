from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class BookingsConfig(AppConfig):
    name = "roomsharing.bookings"
    verbose_name = _("Bookings")
    default_auto_field = "django.db.models.BigAutoField"
