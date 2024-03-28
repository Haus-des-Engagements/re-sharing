from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.db.models import CharField
from django.db.models import EmailField
from django.db.models import ManyToManyField
from django.db.models import Model
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django_extensions.db.fields import AutoSlugField

from .managers import UserManager


class Organization(Model):
    name = CharField(_("Name"), max_length=160)
    slug = AutoSlugField(populate_from="name")
    street = CharField(_("Street"), max_length=56)
    house_number = CharField(_("House Number"), max_length=8)
    zip_code = CharField(_("Zip Code"), max_length=12)
    city = CharField(_("City"), max_length=24)

    class Meta:
        verbose_name = _("Organization")
        verbose_name_plural = _("Organizations")
        ordering = ["name"]

    def __str__(self):
        return self.name


class User(AbstractUser):
    """
    Default custom user model for Roomsharing.
    If adding fields that need to be filled at user signup,
    check forms.SignupForm and forms.SocialSignupForms accordingly.
    """

    # First and last name do not cover name patterns around the globe
    first_name = CharField(_("First Name"))
    last_name = CharField(_("Last Name"))
    email = EmailField(_("email address"), unique=True)
    username = None  # type: ignore[assignment]
    organizations = ManyToManyField(
        Organization,
        verbose_name=_("Organizations"),
        related_name="user_of_organizations",
        related_query_name="users_of_organizations",
        blank=True,
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects: ClassVar[UserManager] = UserManager()

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        ordering = ["email"]

    def get_absolute_url(self) -> str:
        """Get URL for user's detail view.

        Returns:
            str: URL for user detail.

        """
        return reverse("users:detail", kwargs={"pk": self.id})
