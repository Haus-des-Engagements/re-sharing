import uuid
from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.db.models import CharField
from django.db.models import EmailField
from django.db.models import ManyToManyField
from django.db.models import UUIDField
from django.db.models.functions import Lower
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django_extensions.db.fields import AutoSlugField

from re_sharing.organizations.models import BookingPermission
from re_sharing.organizations.models import Organization
from re_sharing.providers.models import Manager
from re_sharing.resources.models import Resource
from re_sharing.users.managers import UserManager
from re_sharing.utils.models import TimeStampedModel


class User(AbstractUser, TimeStampedModel):
    """
    Default custom user model for Re-Sharing.
    If adding fields that need to be filled at user signup,
    check forms.SignupForm and forms.SocialSignupForms accordingly.
    """

    # First and last name do not cover name patterns around the globe
    uuid = UUIDField(default=uuid.uuid4, editable=False)
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
        ordering = [Lower("first_name"), Lower("last_name")]

    def __str__(self):
        return self.first_name + " " + self.last_name

    def get_absolute_url(self) -> str:
        """Get URL for user's detail view.

        Returns:
            str: URL for user detail.

        """
        return reverse("users:detail", kwargs={"slug": self.slug})

    def get_organizations_of_user(self):
        return (
            Organization.objects.filter(
                organization_of_bookingpermission__user=self,
                organization_of_bookingpermission__status=BookingPermission.Status.CONFIRMED,
            )
            .select_related()
            .prefetch_related("organization_groups")
        )

    def get_resources(self):
        from django.db.models import Q

        if self.is_authenticated:
            # Get all organization groups the user is part of in a single query
            user_org_groups = self.get_organizations_of_user().values_list(
                "organization_groups", flat=True
            )

            # Single optimized query combining all resource access
            # patterns
            resources = (
                Resource.objects.filter(
                    Q(is_private=False)  # Public resources
                    | Q(
                        bookableprivateressource_of_organizationgroup__in=user_org_groups
                    )  # Bookable private
                    | Q(
                        autoconfirmedresource_of_organizationgroup__in=user_org_groups
                    )  # Auto-confirmed private
                )
                .select_related()
                .distinct()
            )
        else:
            # For unauthenticated users, only return public resources
            resources = Resource.objects.filter(is_private=False).select_related()

        return resources

    def is_manager(self):
        try:
            Manager.objects.get(user=self)
        except Manager.DoesNotExist:
            return False
        else:
            return True

    def get_manager(self):
        if self.is_manager():
            return Manager.objects.get(user=self)
        return None
