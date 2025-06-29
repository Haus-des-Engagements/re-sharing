import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import EmailMessage
from django.db.models import Q
from django.template import Context
from django.template import Template
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from icalendar import Calendar
from icalendar import Event

from re_sharing.bookings.models import Booking
from re_sharing.organizations.models import EmailTemplate
from re_sharing.resources.services import get_access_code
from re_sharing.utils.models import BookingStatus

logger = logging.getLogger(__name__)


def get_email_template(email_type):
    try:
        return EmailTemplate.objects.get(email_type=email_type)
    except EmailTemplate.DoesNotExist:
        logger.exception("Email template for type %s does not exist.", email_type)
        return None


def get_recipient_booking(booking):
    if booking.organization.send_booking_emails_only_to_organization:
        return [booking.organization.email]
    return [booking.user.email]


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
    event.add("location", f"{booking.resource.name}, {booking.resource.address}")
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


def send_booking_confirmation_email(booking):
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


def send_booking_reminder_emails(days=5):
    bookings = Booking.objects.filter(status=BookingStatus.CONFIRMED)
    dt_in_days = timezone.now() + timedelta(days=days)
    dt_in_days = dt_in_days.replace(hour=0, minute=0, second=0, microsecond=0)
    dt_in_next_day = dt_in_days + timedelta(days=1)
    bookings = bookings.filter(timespan__startswith__gte=dt_in_days)
    bookings = bookings.filter(timespan__startswith__lt=dt_in_next_day)
    bookings = bookings.filter(
        Q(booking_series__isnull=True) | Q(booking_series__reminder_emails=True)
    )

    for booking in bookings:
        access_code = get_access_code(
            booking.resource.slug, booking.organization.slug, booking.timespan.lower
        )
        domain = Site.objects.get_current().domain
        context = {"booking": booking, "access_code": access_code, "domain": domain}

        send_email_with_template(
            EmailTemplate.EmailTypeChoices.BOOKING_REMINDER,
            context,
            get_recipient_booking(booking),
        )
    return list(bookings.values_list("slug", flat=True)), dt_in_days.date()


def send_booking_cancellation_email(booking):
    domain = Site.objects.get_current().domain
    context = {"booking": booking, "domain": domain}

    send_email_with_template(
        EmailTemplate.EmailTypeChoices.BOOKING_CANCELLATION,
        context,
        get_recipient_booking(booking),
    )


def send_manager_new_booking_email(booking):
    domain = Site.objects.get_current().domain
    context = {"booking": booking, "domain": domain}

    send_email_with_template(
        EmailTemplate.EmailTypeChoices.MANAGER_NEW_BOOKING,
        context,
        [settings.DEFAULT_MANAGER_EMAIL],
    )


def send_booking_series_confirmation_email(booking_series):
    domain = Site.objects.get_current().domain
    first_booking = booking_series.get_first_booking()
    context = {
        "booking_series": booking_series,
        "domain": domain,
        "first_booking": first_booking,
    }

    send_email_with_template(
        EmailTemplate.EmailTypeChoices.BOOKING_SERIES_CONFIRMATION,
        context,
        get_recipient_booking_series(booking_series),
    )


def send_booking_series_cancellation_email(booking_series):
    domain = Site.objects.get_current().domain
    first_booking = booking_series.get_first_booking()
    context = {
        "booking_series": booking_series,
        "domain": domain,
        "first_booking": first_booking,
    }

    send_email_with_template(
        EmailTemplate.EmailTypeChoices.BOOKING_SERIES_CANCELLATION,
        context,
        get_recipient_booking_series(booking_series),
    )


def send_manager_new_booking_series_email(booking_series):
    domain = Site.objects.get_current().domain
    first_booking = booking_series.get_first_booking
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


def organization_confirmation_email(organization):
    domain = Site.objects.get_current().domain
    context = {
        "organization": organization,
        "domain": domain,
    }
    recipient_list = [
        *organization.get_confirmed_admins().values_list("email", flat=True)
    ]

    send_email_with_template(
        EmailTemplate.EmailTypeChoices.ORGANIZATION_CONFIRMATION,
        context,
        recipient_list,
    )


def organization_cancellation_email(organization):
    domain = Site.objects.get_current().domain
    context = {
        "organization": organization,
        "domain": domain,
    }
    recipient_list = [
        *organization.get_confirmed_admins().values_list("email", flat=True)
    ]

    send_email_with_template(
        EmailTemplate.EmailTypeChoices.ORGANIZATION_CANCELLATION,
        context,
        recipient_list,
    )


def manager_new_organization_email(organization):
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


def send_new_booking_message_email(booking_message):
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


def send_new_organization_message_email(organization_message):
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
