import uuid
from typing import ClassVar

from auditlog.models import AuditlogHistoryField
from auditlog.registry import auditlog
from django.contrib.auth.models import AbstractUser
from django.db.models import BooleanField
from django.db.models import CharField
from django.db.models import EmailField
from django.db.models import ManyToManyField
from django.db.models import UUIDField
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django_extensions.db.fields import AutoSlugField

from re_sharing.organizations.models import BookingPermission
from re_sharing.organizations.models import Organization
from re_sharing.rooms.models import Room
from re_sharing.users.managers import UserManager
from re_sharing.utils.models import TimeStampedModel


class User(AbstractUser, TimeStampedModel):
    """
    Default custom user model for Roomsharing.
    If adding fields that need to be filled at user signup,
    check forms.SignupForm and forms.SocialSignupForms accordingly.
    """

    # First and last name do not cover name patterns around the globe
    uuid = UUIDField(default=uuid.uuid4, editable=False)
    history = AuditlogHistoryField()
    first_name = CharField(_("First Name"))
    last_name = CharField(_("Last Name"))
    slug = AutoSlugField(populate_from=["first_name", "last_name"], editable=False)
    email = EmailField(_("email address"), unique=True)
    username = None  # type: ignore[assignment]
    organizations = ManyToManyField(
        Organization,
        through=BookingPermission,
        verbose_name=_("Organizations"),
        related_name="users_of_organization",
        related_query_name="user_of_organization",
        blank=True,
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = [
        "first_name",
        "last_name",
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


class UserGroup(TimeStampedModel):
    history = AuditlogHistoryField()
    name = CharField(_("Name"), max_length=160)
    description = CharField(_("Description"), max_length=2048)
    slug = AutoSlugField(populate_from="name", unique=True, editable=False)
    users = ManyToManyField(
        User,
        verbose_name=_("Users"),
        related_name="usergroups_of_user",
        related_query_name="usergroup_of_user",
    )
    auto_confirmed_rooms = ManyToManyField(
        Room,
        verbose_name=_("Auto confirmed rooms"),
        related_name="autoconfirmedrooms_of_usergroup",
        related_query_name="autoconfirmedroom_of_usergroup",
        blank=True,
    )
    auto_confirm_organizations = BooleanField(
        _("Auto confirm organizations on creation"), default=False
    )

    class Meta:
        verbose_name = _("User group")
        verbose_name_plural = _("User groups")
        ordering = ["id"]

    def __str__(self):
        return self.name


auditlog.register(User, exclude_fields=["updated"])
auditlog.register(UserGroup, exclude_fields=["updated"])
