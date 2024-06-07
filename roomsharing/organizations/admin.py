from django.contrib import admin

from .models import Organization
from .models import OrganizationMembership

admin.site.register(Organization)
admin.site.register(OrganizationMembership)
