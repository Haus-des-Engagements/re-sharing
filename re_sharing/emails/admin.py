from django.contrib import admin

from re_sharing.emails.models import EmailLog


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    """The log is a record: it can be read here, not changed."""

    list_display = ["created", "status", "email_type", "recipients_display", "subject"]
    list_filter = ["status", "email_type", "created"]
    search_fields = ["to", "cc", "bcc", "subject"]
    date_hierarchy = "created"
    ordering = ["-created", "-id"]
    list_select_related = ["organization"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
