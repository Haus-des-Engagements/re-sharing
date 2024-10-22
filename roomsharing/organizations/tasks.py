# tasks.py
from django.contrib.sites.models import Site
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import translation


def organization_confirmation_email(organization):
    translation.activate("de")
    subject = render_to_string(
        "emails/email_confirm_organization_subject.txt", {"organization": organization}
    )
    current_site = Site.objects.get_current()
    body = render_to_string(
        "emails/email_confirm_organization_body.txt",
        {"organization": organization, "current_site": current_site},
    )

    recipients = list(
        organization.get_confirmed_admins().values_list("email", flat=True)
    )
    recipients += [organization.email]

    send_mail(
        subject.strip(),
        body,
        "raum.app@haus-des-engagements.de",
        recipients,
        fail_silently=False,
    )
