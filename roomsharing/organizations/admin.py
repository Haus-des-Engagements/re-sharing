from django.contrib import admin

from .models import DefaultBookingStatus
from .models import Membership
from .models import Organization

admin.site.register(Organization)
admin.site.register(Membership)
admin.site.register(DefaultBookingStatus)
