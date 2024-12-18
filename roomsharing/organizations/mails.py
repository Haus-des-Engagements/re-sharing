import logging

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import EmailMessage
from django.template import Context
from django.template import Template
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from icalendar import Calendar
from icalendar import Event

from roomsharing.organizations.models import EmailTemplate
from roomsharing.rooms.services import get_access_code

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


def get_recipient_rrule(rrule):
    if rrule.organization.send_booking_emails_only_to_organization:
        return [rrule.organization.email]
    return [rrule.user.email]


def booking_ics(booking):
    domain = Site.objects.get_current().domain
    cal = Calendar()
    event = Event()
    event.add("uid", booking.uuid)
    event.add("summary", booking.title)
    event.add("dtstart", booking.timespan.lower)
    event.add("dtend", booking.timespan.upper)
    event.add("dtstamp", timezone.now())
    event.add("location", f"{booking.room.name}, {booking.room.address}")
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

    subject = Template(email_template.subject).render(Context(context))
    body = Template(email_template.body).render(Context(context))

    email = EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL, recipient_list)

    if ical_content:
        ical_filename = f"booking_{context['booking'].slug}.ics"
        email.attach(ical_filename, ical_content, "text/calendar")

    email.send(fail_silently=False)


def booking_confirmation_email(booking):
    access_code = get_access_code(
        booking.room.slug, booking.organization.slug, booking.timespan.lower
    )
    domain = Site.objects.get_current().domain
    context = {"booking": booking, "access_code": access_code, "domain": domain}
    ical_content = booking_ics(booking)

    send_email_with_template(
        EmailTemplate.EmailTypeChoices.BOOKING_CONFIRMATION,
        context,
        get_recipient_booking(booking),
        ical_content,
    )


def booking_reminder_email(booking):
    access_code = get_access_code(
        booking.room.slug, booking.organization.slug, booking.timespan.lower
    )
    domain = Site.objects.get_current().domain
    context = {"booking": booking, "access_code": access_code, "domain": domain}
    ical_content = booking_ics(booking)

    send_email_with_template(
        EmailTemplate.EmailTypeChoices.BOOKING_REMINDER,
        context,
        get_recipient_booking(booking),
        ical_content,
    )


def booking_cancellation_email(booking):
    domain = Site.objects.get_current().domain
    context = {"booking": booking, "domain": domain}

    send_email_with_template(
        EmailTemplate.EmailTypeChoices.BOOKING_CANCELLATION,
        context,
        get_recipient_booking(booking),
    )


def manager_new_booking(booking):
    domain = Site.objects.get_current().domain
    context = {"booking": booking, "domain": domain}

    send_email_with_template(
        EmailTemplate.EmailTypeChoices.MANAGER_NEW_BOOKING,
        context,
        [settings.DEFAULT_MANAGER_EMAIL],
    )


def recurrence_confirmation_email(rrule):
    domain = Site.objects.get_current().domain
    first_booking = rrule.get_first_booking()
    context = {"rrule": rrule, "domain": domain, "first_booking": first_booking}

    send_email_with_template(
        EmailTemplate.EmailTypeChoices.RECURRENCE_CONFIRMATION,
        context,
        get_recipient_rrule(rrule),
    )


def recurrence_cancellation_email(rrule):
    domain = Site.objects.get_current().domain
    first_booking = rrule.get_first_booking()
    context = {"rrule": rrule, "domain": domain, "first_booking": first_booking}

    send_email_with_template(
        EmailTemplate.EmailTypeChoices.RECURRENCE_CANCELLATION,
        context,
        get_recipient_rrule(rrule),
    )


def manager_new_recurrence(rrule):
    domain = Site.objects.get_current().domain
    first_booking = rrule.get_first_booking
    context = {"rrule": rrule, "domain": domain, "first_booking": first_booking}

    send_email_with_template(
        EmailTemplate.EmailTypeChoices.MANAGER_NEW_RECURRENCE,
        context,
        [settings.DEFAULT_MANAGER_EMAIL],
    )


def organization_confirmation_email(organization):
    domain = Site.objects.get_current().domain
    context = {
        "organization": organization,
        "domain": domain,
    }

    send_email_with_template(
        EmailTemplate.EmailTypeChoices.ORGANIZATION_CONFIRMATION,
        context,
        [
            *organization.get_confirmed_admins().values_list("email", flat=True),
            organization.email,
        ],
    )


def organization_cancellation_email(organization):
    domain = Site.objects.get_current().domain
    context = {
        "organization": organization,
        "domain": domain,
    }

    send_email_with_template(
        EmailTemplate.EmailTypeChoices.ORGANIZATION_CANCELLATION,
        context,
        [
            *organization.get_confirmed_admins().values_list("email", flat=True),
            organization.email,
        ],
    )


def manager_new_organization_email(organization):
    domain = Site.objects.get_current().domain
    context = {
        "organization": organization,
        "domain": domain,
    }

    send_email_with_template(
        EmailTemplate.EmailTypeChoices.ORGANIZATION_CONFIRMATION,
        context,
        [settings.DEFAULT_MANAGER_EMAIL],
    )
