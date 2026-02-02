from auditlog.registry import auditlog
from django.db import models
from django.db.models import CASCADE
from django.db.models import BooleanField
from django.db.models import CharField
from django.db.models import Count
from django.db.models import IntegerField
from django.db.models import ManyToManyField
from django.db.models import OneToOneField
from django.db.models import Q
from django.db.models import QuerySet
from django.db.models import TimeField
from django.utils.translation import gettext_lazy as _

from re_sharing.organizations.models import Organization
from re_sharing.resources.models import Resource
from re_sharing.utils.models import TimeStampedModel

# Weekday choices for LendingTimeSlot
WEEKDAY_CHOICES = [
    (0, _("Monday")),
    (1, _("Tuesday")),
    (2, _("Wednesday")),
    (3, _("Thursday")),
    (4, _("Friday")),
    (5, _("Saturday")),
    (6, _("Sunday")),
]


class LendingTimeSlot(TimeStampedModel):
    """Configuration for when lendable items can be picked up or returned."""

    class SlotType(models.TextChoices):
        PICKUP = "pickup", _("Pickup")
        RETURN = "return", _("Return")

    slot_type = CharField(
        _("Slot type"),
        max_length=10,
        choices=SlotType.choices,
    )
    weekday = IntegerField(
        _("Weekday"),
        choices=WEEKDAY_CHOICES,
    )
    start_time = TimeField(_("Start time"))
    end_time = TimeField(_("End time"))
    is_active = BooleanField(_("Active"), default=True)

    class Meta:
        verbose_name = _("Lending time slot")
        verbose_name_plural = _("Lending time slots")
        unique_together = [("slot_type", "weekday")]
        ordering = ["slot_type", "weekday"]

    def __str__(self):
        slot_type = self.get_slot_type_display()
        weekday = self.get_weekday_display()
        time_range = f"{self.start_time:%H:%M}-{self.end_time:%H:%M}"
        return f"{slot_type} - {weekday} ({time_range})"

    def get_weekday_short_name(self):
        """Return short weekday name for display."""
        short_names = {
            0: _("Mon"),
            1: _("Tue"),
            2: _("Wed"),
            3: _("Thu"),
            4: _("Fri"),
            5: _("Sat"),
            6: _("Sun"),
        }
        return short_names.get(self.weekday, "")


class Manager(TimeStampedModel):
    """
    Model for managers who can manage bookings and organizations.
    A manager can be restricted to only manage bookings and organizations
    for specified organization groups.
    """

    user = OneToOneField(
        "users.User",
        verbose_name=_("User"),
        on_delete=CASCADE,
        related_name="manager",
    )
    resources = ManyToManyField(
        Resource,
        verbose_name=_("Resources"),
        related_name="managers_of_resource",
        related_query_name="manager_of_resource",
    )
    organization_groups = ManyToManyField(
        "organizations.OrganizationGroup",
        verbose_name=_("Organization groups"),
        related_name="managers_of_organizationgroup",
        related_query_name="manager_of_organizationgroup",
        blank=True,
        help_text=_(
            "If no organization group is specified, the user can manage"
            " all bookings and organizations."
        ),
    )

    class Meta:
        verbose_name = _("Manager")
        verbose_name_plural = _("Manager")
        ordering = ["id"]

    def __str__(self):
        return f"Manager: {self.user}"

    def can_manage_organization(self, organization):
        """
        Check if this manager can manage the given organization.
        If no organization groups are specified, the manager can manage all
        organizations.Otherwise, the organization must be part of at least
        one of the specified groups.
        """
        # If no organization groups are specified, the manager can
        # manage all organizations
        if not self.organization_groups.exists():
            return True

        # Check if the organization is part of any of the manager's organization groups
        return organization.organization_groups.filter(
            manager_of_organizationgroup=self
        ).exists()

    def can_manage_booking(self, booking):
        """
        Check if this resource manager can manage the given booking.
        The manager must be able to manage the booking's organization and resources.
        """
        # Check if the manager can manage the organization
        if not self.can_manage_organization(booking.organization):
            return False

        # Check if the manager can manage the resource
        return self.resources.filter(id=booking.resource.id).exists()

    def get_organizations(self) -> QuerySet[Organization]:
        """
        Returns all organizations that belong to this manager's organization groups,
        as well as organizations that are not in any organization group.
        If the manager has no organization groups, returns an empty queryset.
        Returns:
            QuerySet[Organization]: A queryset containing all distinct organizations
                                   associated with this manager's organization groups
                                   or organizations with no groups.
        """
        if not self.organization_groups.exists():
            return Organization.objects.none()

        return (
            Organization.objects.annotate(group_count=Count("organization_groups"))
            .filter(
                Q(organization_groups__in=self.organization_groups.all())
                | Q(group_count=0)
            )
            .distinct()
        )

    def get_resources(self) -> QuerySet[Resource]:
        """
        Returns all resources that this manager is responsible for.
        Returns:
            QuerySet[Resource]: A queryset containing all resources this
            manager manages.
        """
        return self.resources.all()

    def get_accessible_access_ids(self) -> QuerySet:
        """
        Get IDs of Access objects that this manager can manage.

        Returns:
            QuerySet: A values_list queryset of Access IDs (deduplicated)
        """
        # Use distinct on the Resource queryset before extracting access_ids
        # to ensure proper deduplication
        return (
            self.get_resources()
            .order_by("access_id")
            .distinct("access_id")
            .values_list("access_id", flat=True)
        )

    def get_accessible_accesses(self) -> QuerySet:
        """
        Get Access objects that this manager can manage based on their resources.

        Returns:
            QuerySet: Queryset of Access objects
        """
        from re_sharing.resources.models import Access

        return Access.objects.filter(id__in=self.get_accessible_access_ids())

    def get_accessible_access_codes(self) -> QuerySet:
        """
        Get AccessCodes that this manager can see based on their resources.

        Returns:
            QuerySet: Queryset of AccessCode objects filtered by manager's access
        """
        from re_sharing.resources.models import AccessCode

        return AccessCode.objects.filter(access_id__in=self.get_accessible_access_ids())


auditlog.register(Manager, exclude_fields=["updated"])
