from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _


class EmailLog(models.Model):
    """One email the platform handed to its email backend (ADR 0028)."""

    class Status(models.TextChoices):
        SENT = "sent", _("Sent")
        FAILED = "failed", _("Failed")

    created = models.DateTimeField(_("Created"), auto_now_add=True, db_index=True)
    sent_at = models.DateTimeField(_("Sent at"), null=True, blank=True)
    status = models.CharField(
        _("Status"), max_length=10, choices=Status, default=Status.FAILED
    )
    email_type = models.CharField(_("Type"), max_length=100, blank=True)
    from_email = models.CharField(_("From"), max_length=320, blank=True)
    to = models.JSONField(_("To"), default=list, blank=True)
    cc = models.JSONField(_("Cc"), default=list, blank=True)
    bcc = models.JSONField(_("Bcc"), default=list, blank=True)
    subject = models.TextField(_("Subject"), blank=True)
    body_text = models.TextField(_("Text content"), blank=True)
    body_html = models.TextField(_("HTML content"), blank=True)
    attachment_names = models.JSONField(_("Attachments"), default=list, blank=True)
    error = models.TextField(_("Error"), blank=True)
    attempts = models.PositiveSmallIntegerField(_("Attempts"), default=0)
    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name=_("Organization"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="email_logs_of_organization",
        related_query_name="email_log_of_organization",
    )
    booking = models.ForeignKey(
        "bookings.Booking",
        verbose_name=_("Booking"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="email_logs_of_booking",
        related_query_name="email_log_of_booking",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("User"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="email_logs_of_user",
        related_query_name="email_log_of_user",
    )

    class Meta:
        verbose_name = _("Email")
        verbose_name_plural = _("Email log")
        ordering = ["-created", "-id"]

    def __str__(self):
        return f"{self.recipients_display}: {self.subject}"

    def get_absolute_url(self):
        return reverse("emails:show-email", kwargs={"pk": self.pk})

    @property
    def recipients_display(self) -> str:
        return ", ".join(self.to)

    @property
    def is_failed(self) -> bool:
        return self.status == self.Status.FAILED
