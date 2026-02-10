"""
Email functions for the organizations app.

All email sending functions are implemented as background tasks using django-tasks.
This provides resilience against SMTP failures and allows emails to be processed
asynchronously.

Usage:
    # Enqueue for background processing (recommended)
    send_booking_confirmation_email.enqueue(booking.id)

    # Synchronous call (for testing)
    send_booking_confirmation_email.call(booking.id)
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import EmailMessage
from django.tasks import task
from django.template import Context
from django.template import Template
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from icalendar import Calendar
from icalendar import Event

from re_sharing.organizations.models import EmailTemplate

logger = logging.getLogger(__name__)


# =============================================================================
# Helper functions (not tasks)
# =============================================================================


def get_email_template(email_type):
    try:
        return EmailTemplate.objects.get(email_type=email_type)
    except EmailTemplate.DoesNotExist:
        logger.exception("Email template for type %s does not exist.", email_type)
        return None


def get_recipient_booking(booking):
    if booking.organization.send_booking_emails_only_to_organization:
        return [booking.organization.email]

    confirmed_users = booking.organization.get_confirmed_users()
    if confirmed_users.filter(id=booking.user.id).exists():
        return [booking.user.email]
    return [booking.organization.email]


def get_recipient_booking_series(booking_series):
    if booking_series.organization.send_booking_emails_only_to_organization:
        return [booking_series.organization.email]
    return [booking_series.user.email]


def booking_ics(booking):
    domain = Site.objects.get_current().domain
    cal = Calendar()
    event = Event()
    event.add("uid", booking.uuid)
    event.add("summary", booking.title)
    event.add("dtstart", booking.timespan.lower)
    event.add("dtend", booking.timespan.upper)
    event.add("dtstamp", timezone.now())
    event.add(
        "location",
        f"{booking.resource.name}, {booking.resource.location.address}"
        if booking.resource.location
        else booking.resource.name,
    )
    event["description"] = _("Find all related information here: %s%s") % (
        domain,
        booking.get_absolute_url(),
    )
    cal.add_component(event)
    return cal.to_ical()


def send_email_with_template(email_type, context, recipient_list, ical_content=None):
    email_template = get_email_template(email_type)
    if not email_template:
        return

    if email_template.active is False:
        return

    subject = Template(email_template.subject).render(Context(context))
    body = Template(email_template.body).render(Context(context))
    email = EmailMessage(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipient_list,
        bcc=[settings.DEFAULT_BCC_EMAIL],
    )

    if ical_content:
        ical_filename = f"booking_{context['booking'].slug}.ics"
        email.attach(ical_filename, ical_content, "text/calendar")

    email.send(fail_silently=False)


# =============================================================================
# Booking email tasks
# =============================================================================


@task(queue_name="email")
def send_booking_confirmation_email(booking_id: int) -> dict:
    """Send confirmation email for a booking."""
    from re_sharing.bookings.models import Booking
    from re_sharing.resources.services import get_access_code

    booking = Booking.objects.select_related(
        "resource", "resource__location", "organization", "user"
    ).get(id=booking_id)

    access_code = get_access_code(
        booking.resource.slug, booking.organization.slug, booking.timespan.lower
    )
    send_access_code = False
    dt_in_5_days = timezone.now() + timedelta(days=5)
    dt_in_5_days = dt_in_5_days.replace(hour=0, minute=0, second=0, microsecond=0)
    if booking.timespan.lower < dt_in_5_days:
        send_access_code = True
    domain = Site.objects.get_current().domain
    context = {
        "booking": booking,
        "send_access_code": send_access_code,
        "access_code": access_code,
        "domain": domain,
    }

    send_email_with_template(
        EmailTemplate.EmailTypeChoices.BOOKING_CONFIRMATION,
        context,
        get_recipient_booking(booking),
    )

    return {"booking_id": booking_id, "recipient": get_recipient_booking(booking)}


@task(queue_name="email")
def send_booking_reminder_email(booking_id: int) -> dict:
    """Send reminder email for a single booking."""
    from re_sharing.bookings.models import Booking
    from re_sharing.resources.services import get_access_code

    booking = Booking.objects.select_related("resource", "organization", "user").get(
        id=booking_id
    )

    access_code = get_access_code(
        booking.resource.slug, booking.organization.slug, booking.timespan.lower
    )
    domain = Site.objects.get_current().domain
    context = {"booking": booking, "access_code": access_code, "domain": domain}
    recipient = get_recipient_booking(booking)

    send_email_with_template(
        EmailTemplate.EmailTypeChoices.BOOKING_REMINDER,
        context,
        recipient,
    )

    return {"booking_slug": booking.slug, "recipient": recipient}


@task(queue_name="email")
def send_booking_cancellation_email(booking_id: int) -> dict:
    """Send cancellation email for a booking."""
    from re_sharing.bookings.models import Booking

    booking = Booking.objects.select_related("organization", "user").get(id=booking_id)

    domain = Site.objects.get_current().domain
    context = {"booking": booking, "domain": domain}
    recipient = get_recipient_booking(booking)

    send_email_with_template(
        EmailTemplate.EmailTypeChoices.BOOKING_CANCELLATION,
        context,
        recipient,
    )

    return {"booking_id": booking_id, "recipient": recipient}


@task(queue_name="email")
def send_booking_not_available_email(booking_id: int) -> dict:
    """Send 'not available' email for a booking."""
    from re_sharing.bookings.models import Booking

    booking = Booking.objects.select_related("organization", "user").get(id=booking_id)

    domain = Site.objects.get_current().domain
    context = {"booking": booking, "domain": domain}
    recipient = get_recipient_booking(booking)

    send_email_with_template(
        EmailTemplate.EmailTypeChoices.BOOKING_NOT_AVAILABLE,
        context,
        recipient,
    )

    return {"booking_id": booking_id, "recipient": recipient}


@task(queue_name="email")
def send_manager_new_booking_email(booking_id: int) -> dict:
    """Send notification email to manager about new booking."""
    from re_sharing.bookings.models import Booking

    booking = Booking.objects.select_related("organization", "user").get(id=booking_id)

    domain = Site.objects.get_current().domain
    context = {"booking": booking, "domain": domain}

    send_email_with_template(
        EmailTemplate.EmailTypeChoices.MANAGER_NEW_BOOKING,
        context,
        [settings.DEFAULT_MANAGER_EMAIL],
    )

    return {"booking_id": booking_id}


@task(queue_name="email")
def send_new_booking_message_email(booking_message_id: int) -> dict:
    """Send notification email about a new booking message."""
    from re_sharing.bookings.models import BookingMessage

    booking_message = BookingMessage.objects.select_related(
        "booking", "booking__organization", "user"
    ).get(id=booking_message_id)

    domain = Site.objects.get_current().domain
    context = {"booking": booking_message.booking, "domain": domain}
    confirmed_users = booking_message.booking.organization.get_confirmed_users()
    if confirmed_users.filter(id=booking_message.user.id).exists():
        recipient = [settings.DEFAULT_MANAGER_EMAIL]
    else:
        recipient = get_recipient_booking(booking_message.booking)

    send_email_with_template(
        EmailTemplate.EmailTypeChoices.NEW_BOOKING_MESSAGE, context, recipient
    )

    return {"booking_message_id": booking_message_id, "recipient": recipient}


# =============================================================================
# Booking series email tasks
# =============================================================================


@task(queue_name="email")
def send_booking_series_confirmation_email(booking_series_id: int) -> dict:
    """Send confirmation email for a booking series."""
    from re_sharing.bookings.models import BookingSeries

    booking_series = BookingSeries.objects.select_related("organization", "user").get(
        id=booking_series_id
    )

    domain = Site.objects.get_current().domain
    first_booking = booking_series.get_first_booking()
    context = {
        "booking_series": booking_series,
        "domain": domain,
        "first_booking": first_booking,
    }
    recipient = get_recipient_booking_series(booking_series)

    send_email_with_template(
        EmailTemplate.EmailTypeChoices.BOOKING_SERIES_CONFIRMATION,
        context,
        recipient,
    )

    return {"booking_series_id": booking_series_id, "recipient": recipient}


@task(queue_name="email")
def send_booking_series_cancellation_email(booking_series_id: int) -> dict:
    """Send cancellation email for a booking series."""
    from re_sharing.bookings.models import BookingSeries

    booking_series = BookingSeries.objects.select_related("organization", "user").get(
        id=booking_series_id
    )

    domain = Site.objects.get_current().domain
    first_booking = booking_series.get_first_booking()
    context = {
        "booking_series": booking_series,
        "domain": domain,
        "first_booking": first_booking,
    }
    recipient = get_recipient_booking_series(booking_series)

    send_email_with_template(
        EmailTemplate.EmailTypeChoices.BOOKING_SERIES_CANCELLATION,
        context,
        recipient,
    )

    return {"booking_series_id": booking_series_id, "recipient": recipient}


@task(queue_name="email")
def send_manager_new_booking_series_email(booking_series_id: int) -> dict:
    """Send notification email to manager about new booking series."""
    from re_sharing.bookings.models import BookingSeries

    booking_series = BookingSeries.objects.select_related("organization", "user").get(
        id=booking_series_id
    )

    domain = Site.objects.get_current().domain
    first_booking = booking_series.get_first_booking()
    context = {
        "booking_series": booking_series,
        "domain": domain,
        "first_booking": first_booking,
    }

    send_email_with_template(
        EmailTemplate.EmailTypeChoices.MANAGER_NEW_BOOKING_SERIES,
        context,
        [settings.DEFAULT_MANAGER_EMAIL],
    )

    return {"booking_series_id": booking_series_id}


# =============================================================================
# Organization email tasks
# =============================================================================


@task(queue_name="email")
def organization_confirmation_email(organization_id: int) -> dict:
    """Send confirmation email when organization is approved."""
    from re_sharing.organizations.models import Organization

    organization = Organization.objects.get(id=organization_id)

    domain = Site.objects.get_current().domain
    context = {
        "organization": organization,
        "domain": domain,
    }
    if organization.send_booking_emails_only_to_organization:
        recipient_list = [organization.email]
    else:
        recipient_list = [
            *organization.get_confirmed_admins().values_list("email", flat=True)
        ]

    send_email_with_template(
        EmailTemplate.EmailTypeChoices.ORGANIZATION_CONFIRMATION,
        context,
        recipient_list,
    )

    return {"organization_id": organization_id, "recipient": recipient_list}


@task(queue_name="email")
def organization_cancellation_email(organization_id: int) -> dict:
    """Send cancellation email when organization is cancelled."""
    from re_sharing.organizations.models import Organization

    organization = Organization.objects.get(id=organization_id)

    domain = Site.objects.get_current().domain
    context = {
        "organization": organization,
        "domain": domain,
    }
    if organization.send_booking_emails_only_to_organization:
        recipient_list = [organization.email]
    else:
        recipient_list = [
            *organization.get_confirmed_admins().values_list("email", flat=True)
        ]

    send_email_with_template(
        EmailTemplate.EmailTypeChoices.ORGANIZATION_CANCELLATION,
        context,
        recipient_list,
    )

    return {"organization_id": organization_id, "recipient": recipient_list}


@task(queue_name="email")
def manager_new_organization_email(organization_id: int) -> dict:
    """Send notification email to manager about new organization."""
    from re_sharing.organizations.models import Organization

    organization = Organization.objects.get(id=organization_id)

    domain = Site.objects.get_current().domain
    context = {
        "organization": organization,
        "domain": domain,
    }

    send_email_with_template(
        EmailTemplate.EmailTypeChoices.MANAGER_NEW_ORGANIZATION,
        context,
        [settings.DEFAULT_MANAGER_EMAIL],
    )

    return {"organization_id": organization_id}


@task(queue_name="email")
def send_new_organization_message_email(organization_message_id: int) -> dict:
    """Send notification email about a new organization message."""
    from re_sharing.organizations.models import OrganizationMessage

    organization_message = OrganizationMessage.objects.select_related(
        "organization", "user"
    ).get(id=organization_message_id)

    domain = Site.objects.get_current().domain
    context = {
        "organization": organization_message.organization,
        "domain": domain,
        "messages_url": reverse(
            "organizations:show-organization-messages",
            args=[str(organization_message.organization.slug)],
        ),
    }
    confirmed_users = organization_message.organization.get_confirmed_users()
    if confirmed_users.filter(id=organization_message.user.id).exists():
        recipient_list = [settings.DEFAULT_MANAGER_EMAIL]
        send_email_with_template(
            EmailTemplate.EmailTypeChoices.MANAGER_NEW_ORGANIZATION_MESSAGE,
            context,
            recipient_list,
        )
    else:
        # Send email to all confirmed admins of the organization
        if organization_message.organization.send_booking_emails_only_to_organization:
            recipient_list = [organization_message.organization.email]
        else:
            recipient_list = [
                *organization_message.organization.get_confirmed_admins().values_list(
                    "email", flat=True
                )
            ]
        send_email_with_template(
            EmailTemplate.EmailTypeChoices.NEW_ORGANIZATION_MESSAGE,
            context,
            recipient_list,
        )

    return {
        "organization_message_id": organization_message_id,
        "recipient": recipient_list,
    }


# =============================================================================
# Monthly overview email task (used by management command)
# =============================================================================


@task(queue_name="email")
def send_monthly_overview_email(
    organization_id: int, booking_ids: list[int], next_month_iso: str
) -> dict:
    """Send monthly bookings overview email to a single organization."""
    from re_sharing.bookings.models import Booking
    from re_sharing.organizations.models import Organization

    organization = Organization.objects.get(id=organization_id)
    bookings = list(
        Booking.objects.filter(id__in=booking_ids).select_related("resource")
    )

    # Add access codes to bookings
    for booking in bookings:
        booking.access_code = booking.get_access_code()

    domain = Site.objects.get_current().domain
    next_month = timezone.datetime.fromisoformat(next_month_iso)

    context = {
        "organization": organization,
        "bookings": bookings,
        "next_month": next_month,
        "domain": domain,
    }

    send_email_with_template(
        EmailTemplate.EmailTypeChoices.MONTHLY_BOOKINGS,
        context,
        [organization.email],
    )

    return {
        "organization": organization.name,
        "booking_count": len(bookings),
    }


# =============================================================================
# Custom email function (not a task - admin action with complex arguments)
# =============================================================================


def send_custom_organization_email(
    organizations,
    subject_template,
    body_template,
    filter_context=None,
):
    """
    Send a custom email to multiple organizations.

    This is NOT a task because it takes complex arguments (querysets, templates).
    It's used for admin actions where synchronous feedback is preferred.

    Args:
        organizations: QuerySet or list of Organization objects
        subject_template: String template for email subject
        body_template: String template for email body
        filter_context: Optional dict with filter parameters (min_bookings, months)

    Returns:
        Dictionary with count of emails sent and list of organization names
    """
    domain = Site.objects.get_current().domain
    sent_count = 0
    sent_organizations = []

    for organization in organizations:
        # Build context for template rendering
        context = {
            "organization": organization,
            "domain": domain,
        }

        # Add filter context if provided
        if filter_context:
            context.update(filter_context)
            # Add organization-specific booking statistics if months is provided
            if "months" in filter_context:
                # Check if organization has annotated attributes from queryset
                if hasattr(organization, "booking_count"):
                    context["number_of_bookings"] = organization.booking_count
                    context["total_amount"] = organization.total_amount
                else:
                    # Fallback to selector function if not annotated
                    from re_sharing.organizations.selectors import (
                        get_organization_booking_count,
                    )

                    context["number_of_bookings"] = get_organization_booking_count(
                        organization, filter_context["months"]
                    )
                    # Note: total_amount not available without annotation

        # Render templates
        subject = Template(subject_template).render(Context(context))
        body = Template(body_template).render(Context(context))

        # Send email
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[organization.email],
            bcc=[settings.DEFAULT_BCC_EMAIL],
        )

        try:
            email.send(fail_silently=False)
            sent_count += 1
            sent_organizations.append(organization.name)
        except Exception:
            logger.exception(
                "Failed to send custom email to organization %s", organization.name
            )

    return {
        "sent_count": sent_count,
        "sent_organizations": sent_organizations,
    }
