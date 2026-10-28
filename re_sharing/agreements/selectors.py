"""Read-only queries and permission checks for agreements."""

from datetime import timedelta

from django.db.models import Count
from django.db.models import Q
from django.db.models import QuerySet

from re_sharing.organizations.models import BookingPermission
from re_sharing.organizations.models import Organization

from .models import RETURN_INVOICE_DUE_DAYS
from .models import Agreement
from .models import AgreementKind
from .models import Collection
from .models import CollectionRun
from .models import SepaMandate


def _manager_of(user):
    if not user.is_authenticated:
        return None
    return user.get_manager()


def manager_can_manage_kind(user, kind: AgreementKind) -> bool:
    """Managers without organization groups manage every kind, the others only
    kinds whose group is one of theirs."""
    manager = _manager_of(user)
    if manager is None:
        return False
    groups = manager.organization_groups.all()
    if not groups.exists():
        return True
    return groups.filter(id=kind.organization_group_id).exists()


def manager_can_manage_agreement(user, agreement: Agreement) -> bool:
    return manager_can_manage_kind(user, agreement.kind)


def agreement_can_be_deleted(agreement: Agreement) -> bool:
    """Only submitted agreements on which nothing was collected yet."""
    return (
        agreement.status == Agreement.Status.SUBMITTED
        and not agreement.collections_of_agreement.exists()
    )


def contract_document_available(agreement: Agreement) -> bool:
    return bool(agreement.kind.contract_template) and agreement.status in (
        Agreement.Status.SUBMITTED,
        Agreement.Status.ACTIVE,
    )


def field_has_answers(field) -> bool:
    return Agreement.objects.filter(
        kind=field.kind_id, details__has_key=field.key
    ).exists()


def manager_creatable_kinds(user) -> QuerySet[AgreementKind]:
    return manager_kinds(user).filter(is_active=True)


def is_confirmed_admin(user, organization: Organization) -> bool:
    if not user.is_authenticated:
        return False
    return BookingPermission.objects.filter(
        user=user,
        organization=organization,
        role=BookingPermission.Role.ADMIN,
        status=BookingPermission.Status.CONFIRMED,
    ).exists()


def user_can_view_organization_agreements(user, organization: Organization) -> bool:
    if not user.is_authenticated:
        return False
    if organization.has_confirmed_user(user):
        return True
    manager = _manager_of(user)
    return manager is not None and manager.can_manage_organization(organization)


def user_can_view_agreement(user, agreement: Agreement) -> bool:
    if not user.is_authenticated:
        return False
    return agreement.organization.has_confirmed_user(
        user
    ) or manager_can_manage_agreement(user, agreement)


def user_can_administer_agreement(user, agreement: Agreement) -> bool:
    """Confirmed admins of the organization and managers in scope."""
    return is_confirmed_admin(
        user, agreement.organization
    ) or manager_can_manage_agreement(user, agreement)


def open_kinds_for_organization(organization: Organization) -> QuerySet[AgreementKind]:
    """Kinds the organization may apply for now."""
    taken = Agreement.objects.filter(
        organization=organization,
        status__in=[Agreement.Status.SUBMITTED, Agreement.Status.ACTIVE],
    ).values("kind_id")
    return AgreementKind.objects.filter(
        is_active=True, accepting_applications=True
    ).exclude(id__in=taken)


def organization_agreements(organization: Organization) -> QuerySet[Agreement]:
    return (
        Agreement.objects.filter(organization=organization)
        .select_related("kind")
        .prefetch_related("collections_of_agreement", "mandates_of_agreement")
    )


def manager_kinds(user) -> QuerySet[AgreementKind]:
    manager = _manager_of(user)
    if manager is None:
        return AgreementKind.objects.none()
    groups = manager.organization_groups.all()
    kinds = AgreementKind.objects.all()
    if groups.exists():
        kinds = kinds.filter(organization_group__in=groups)
    return kinds


def manager_agreements(user, *, status=None, kind=None) -> QuerySet[Agreement]:
    agreements = Agreement.objects.filter(kind__in=manager_kinds(user))
    if status:
        agreements = agreements.filter(status=status)
    if kind:
        agreements = agreements.filter(kind__slug=kind)
    return agreements.select_related("organization", "kind").order_by(
        "status", "-created"
    )


def manager_submitted_agreements_count(user) -> int:
    return manager_agreements(user, status=Agreement.Status.SUBMITTED).count()


def manager_mandates(user) -> QuerySet[SepaMandate]:
    return SepaMandate.objects.filter(agreement__kind__in=manager_kinds(user))


def manager_collections(
    user, *, status=None, kind=None, agreement_kind=None
) -> QuerySet[Collection]:
    collections = Collection.objects.filter(agreement__kind__in=manager_kinds(user))
    if status:
        collections = collections.filter(status=status)
    if kind:
        collections = collections.filter(kind=kind)
    if agreement_kind:
        collections = collections.filter(agreement__kind__slug=agreement_kind)
    return collections.select_related(
        "agreement", "agreement__organization", "agreement__kind", "mandate", "run"
    ).order_by("-due_date", "-id")


def manager_attention_collections(user, *, today) -> QuerySet[Collection]:
    """Returned, invoiced past due, and notified without an active mandate."""
    collections = manager_collections(user)
    invoice_due = Q(
        status=Collection.Status.INVOICED,
        invoiced_at__date__lt=today - timedelta(days=RETURN_INVOICE_DUE_DAYS),
    )
    without_mandate = Q(status=Collection.Status.NOTIFIED) & (
        Q(mandate__isnull=True)
        | Q(mandate__revoked_on__isnull=False)
        | Q(mandate__signed_document="")
        | Q(mandate__signed_document__isnull=True)
    )
    return collections.filter(
        Q(status=Collection.Status.RETURNED) | invoice_due | without_mandate
    )


def runs_not_uploaded() -> QuerySet[CollectionRun]:
    return CollectionRun.objects.filter(uploaded_at__isnull=True).order_by(
        "collection_date"
    )


def manager_runs() -> QuerySet[CollectionRun]:
    return CollectionRun.objects.annotate(
        collection_count=Count("collection_of_run")
    ).select_related("created_by", "uploaded_by")
