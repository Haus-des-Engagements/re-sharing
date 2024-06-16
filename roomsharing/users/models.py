from typing import ClassVar

from auditlog.models import AuditlogHistoryField
from auditlog.registry import auditlog
from django.contrib.auth.models import AbstractUser
from django.db.models import CharField
from django.db.models import EmailField
from django.db.models import ManyToManyField
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django_extensions.db.fields import AutoSlugField

from roomsharing.organizations.models import Membership
from roomsharing.organizations.models import Organization
from roomsharing.users.managers import UserManager
from roomsharing.utils.models import TimeStampedModel


class User(AbstractUser, TimeStampedModel):
    """
    Default custom user model for Roomsharing.
    If adding fields that need to be filled at user signup,
    check forms.SignupForm and forms.SocialSignupForms accordingly.
    """

    # First and last name do not cover name patterns around the globe
    history = AuditlogHistoryField()
    first_name = CharField(_("First Name"))
    last_name = CharField(_("Last Name"))
    slug = AutoSlugField(populate_from=["first_name", "last_name"], editable=False)
    email = EmailField(_("email address"), unique=True)
    username = None  # type: ignore[assignment]
    organizations = ManyToManyField(
        Organization,
        through=Membership,
        verbose_name=_("Organizations"),
        related_name="users_of_organization",
        related_query_name="user_of_organization",
        blank=True,
    )
    street = CharField(_("Street"), max_length=56)
    house_number = CharField(_("House Number"), max_length=8, blank=True)
    zip_code = CharField(_("Zip Code"), max_length=12)
    city = CharField(_("City"), max_length=24)
    phone_number = CharField(_("Phone Number"), max_length=20)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = [
        "first_name",
        "last_name",
        "street",
        "city",
        "zip_code",
        "phone_number",
    ]

    objects: ClassVar[UserManager] = UserManager()

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        ordering = ["email"]

    def __str__(self):
        return self.first_name + " " + self.last_name

    def get_absolute_url(self) -> str:
        """Get URL for user's detail view.

        Returns:
            str: URL for user detail.

        """
        return reverse("users:detail", kwargs={"slug": self.slug})


auditlog.register(Organization, exclude_fields=["created, updated"])
