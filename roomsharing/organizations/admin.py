from django.contrib import admin

from .models import BookingPermission
from .models import DefaultBookingStatus
from .models import Organization

admin.site.register(Organization)
admin.site.register(BookingPermission)
admin.site.register(DefaultBookingStatus)
