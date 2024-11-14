from django.contrib import admin

from .models import BookingPermission
from .models import DefaultBookingStatus
from .models import EmailTemplate
from .models import Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_filter = ("status",)


admin.site.register(BookingPermission)
admin.site.register(DefaultBookingStatus)
admin.site.register(EmailTemplate)
