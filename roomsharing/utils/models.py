from django.db import models
from django.utils.translation import gettext_lazy as _


class TimeStampedModel(models.Model):
    # See https://docs.djangoproject.com/en/3.0/ref/models/fields/#django.db.models
    # .DateField for attributes.
    created = models.DateTimeField(
        verbose_name=_("Created"),
        auto_now_add=True,
        editable=False,
        blank=True,
    )
    updated = models.DateTimeField(
        verbose_name=_("Updated"),
        auto_now=True,
        editable=False,
        blank=True,
    )

    class Meta:
        abstract = True
