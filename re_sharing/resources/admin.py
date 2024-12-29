from django.contrib import admin
from import_export.admin import ImportExportMixin

from .models import Access
from .models import AccessCode
from .models import Compensation
from .models import Resource
from .models import RoomImage


@admin.register(Resource)
class RoomAdmin(ImportExportMixin, admin.ModelAdmin):
    list_display = ["id", "name", "square_meters", "max_persons"]
    search_fields = ["id", "name"]
    ordering = ["id"]


@admin.register(Compensation)
class CompensationAdmin(ImportExportMixin, admin.ModelAdmin):
    list_display = ["id", "name", "conditions", "hourly_rate"]
    search_fields = ["id", "name"]
    ordering = ["id"]


@admin.register(AccessCode)
class AccessCodeAdmin(ImportExportMixin, admin.ModelAdmin):
    list_display = ["id", "access", "code", "validity_start", "organization"]
    search_fields = ["id", "access", "code"]
    list_filter = ["access", "organization"]
    ordering = ["id"]


@admin.register(Access)
class AccessAdmin(ImportExportMixin, admin.ModelAdmin):
    list_display = ["id", "name", "slug"]
    search_fields = ["id", "name", "slug"]
    ordering = ["id"]


admin.site.register(RoomImage)
