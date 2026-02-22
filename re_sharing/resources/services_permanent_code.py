"""Service functions for managing permanent codes."""

import random
from datetime import datetime
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from re_sharing.organizations.mails import send_permanent_code_created_email
from re_sharing.organizations.mails import send_permanent_code_renewed_email
from re_sharing.organizations.models import Organization
from re_sharing.resources.models import Access
from re_sharing.resources.models import PermanentCode


def _generate_permanent_code() -> str:
    """Generate a random 6-digit code (no zeros, cannot start with '12')."""
    digits = "123456789"
    while True:
        code = "".join(random.choices(digits, k=6))  # noqa: S311
        if not code.startswith("12"):
            return code


def create_permanent_code_for_organization(
    organization_slug: str, created_by
) -> PermanentCode:
    """Create a new permanent code for an organization.

    Args:
        organization_slug: The organization slug
        created_by: The user creating the code (for audit)

    Returns:
        The created PermanentCode instance

    Raises:
        ValidationError: If organization already has an active permanent code
    """
    organization = get_object_or_404(Organization, slug=organization_slug)

    # Check if organization already has an active permanent code
    existing_code = (
        PermanentCode.objects.filter(organization=organization)
        .filter(validity_start__lte=timezone.now())
        .filter(Q(validity_end__isnull=True) | Q(validity_end__gte=timezone.now()))
        .first()
    )

    if existing_code:
        raise ValidationError(
            _("Organization already has an active permanent code: %(code)s")
            % {"code": existing_code.code}
        )

    # Generate new code
    code = _generate_permanent_code()

    # Get accesses 1, 2, 8
    accesses = Access.objects.filter(id__in=[1, 2, 8])

    # Create permanent code
    permanent_code = PermanentCode.objects.create(
        code=code,
        organization=organization,
        validity_start=timezone.now(),
        validity_end=None,  # No expiration by default
        name=f"Permanent code for {organization.name}",
    )
    permanent_code.accesses.set(accesses)
    permanent_code.save()

    # Send email notification
    send_permanent_code_created_email.enqueue(permanent_code.id)

    return permanent_code


def invalidate_permanent_code(
    permanent_code_id: int, validity_end: datetime, invalidated_by
) -> PermanentCode:
    """Invalidate a permanent code by setting its validity_end.

    Args:
        permanent_code_id: The permanent code ID
        validity_end: When the code should become invalid
        invalidated_by: The user invalidating the code (for audit)

    Returns:
        The updated PermanentCode instance
    """
    permanent_code = get_object_or_404(PermanentCode, id=permanent_code_id)
    permanent_code.validity_end = validity_end
    permanent_code.save()

    # Send email notification
    from re_sharing.organizations.mails import send_permanent_code_invalidated_email

    send_permanent_code_invalidated_email.enqueue(permanent_code.id)

    return permanent_code


def renew_permanent_code(
    permanent_code_id: int, renewed_by
) -> tuple[PermanentCode, PermanentCode]:
    """Renew a permanent code.

    Creates a new code and sets the old one to expire in 1 week.

    Args:
        permanent_code_id: The permanent code ID to renew
        renewed_by: The user renewing the code (for audit)

    Returns:
        Tuple of (old_code, new_code)
    """
    old_code = get_object_or_404(PermanentCode, id=permanent_code_id)

    # Set old code to expire in 1 week
    old_code.validity_end = timezone.now() + timedelta(weeks=1)
    old_code.save()

    # Create new code
    new_code_value = _generate_permanent_code()
    new_code = PermanentCode.objects.create(
        code=new_code_value,
        organization=old_code.organization,
        validity_start=timezone.now(),
        validity_end=None,  # No expiration
        name=f"Renewed permanent code for {old_code.organization.name}",
    )
    new_code.accesses.set(old_code.accesses.all())
    new_code.save()

    # Send email notification
    send_permanent_code_renewed_email.enqueue(new_code.id, old_code.id)

    return old_code, new_code
