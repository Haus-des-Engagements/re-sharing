from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML
from crispy_forms.layout import Column
from crispy_forms.layout import Layout
from crispy_forms.layout import Row
from crispy_forms.layout import Submit
from django import forms
from django.forms import ModelMultipleChoiceField
from django.forms.widgets import CheckboxSelectMultiple
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from .models import Organization
from .models import OrganizationGroup
from .models import OrganizationMessage


class OrganizationMessageForm(forms.ModelForm):
    text = forms.CharField(
        widget=forms.Textarea(attrs={"rows": "5"}),
        required=True,
    )

    class Meta:
        model = OrganizationMessage
        fields = ["text"]


class OrganizationForm(forms.ModelForm):
    name = forms.CharField(
        label=_("Name of the organization"),
        required=True,
        help_text=mark_safe(  # noqa: S308
            _(
                "e.g. Accordion Club Gundelfinden e.V. <a href='/organizations'>Please "
                "check here"
                " first</a> if your organization has already been created."
            ),
        ),
    )
    public_name = forms.CharField(
        required=False,
        label=_("Public display name (optional)"),
        help_text=mark_safe(  # noqa: S308
            _(
                "This name will be displayed on the screen inside the HdE (not in "
                "the internet)."
            ),
        ),
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={"rows": "5"}),
        required=True,
        label=_("Description"),
        help_text=_(
            "Describe shortly what your organization is doing and trying to achieve."
        ),
    )
    is_charitable = forms.BooleanField(
        label=_("We are a charitable organization."),
        help_text=_(
            "Please select only if you have a valid certificate of tax exemption. "
            "Of course you can also book resources if you're not officially charitable!"
        ),
        required=False,
    )
    is_public = forms.BooleanField(
        label=_("This organization may be listed publicly on this website."),
        help_text=_(
            "Only organization name, description, city, website and area of activity "
            "will be displayed."
        ),
        required=False,
    )
    email = forms.EmailField(label=_("E-Mail address of the organization"))
    send_booking_emails_only_to_organization = forms.BooleanField(
        label=_("Send all emails to this address."),
        help_text=_("All mails will be send to the organization and not to the user."),
        required=False,
        initial=True,
    )
    monthly_bulk_access_codes = forms.BooleanField(
        label=_("Send all access codes for the next month at once (at the 20th.)."),
        help_text=_("This prevents sending separate emails for all bookings."),
        required=False,
        initial=False,
    )
    values_approval = forms.BooleanField(
        label=mark_safe(  # noqa: S308
            _(
                "I have read <a href='https://haus-des-engagements.de/wp-content/"
                "uploads/2024/08/Unsere-Werte-im-HdE.pdf' target='_blank'>Our Values in"
                " the House of Engagement</a> and the associated <a href='https://"
                "haus-des-engagements.de/wp-content/uploads/2024/08/Ablauf-Werte-im-HdE"
                ".pdf target='_blank'>Procedure</a>. I will inform all members of my "
                "group about them. We agree to the values."
            )
        ),
        required=True,
    )
    area_of_activity = forms.ChoiceField(
        choices=Organization.ActivityArea,
        label=_("In which societal area are you mainly active?"),
    )
    usage_agreement = forms.FileField(
        label=mark_safe(  # noqa: S308
            _(
                "Upload your existing usage agreement or add a <a href='https://"
                "haus-des-engagements.de/wp-content/uploads/2025/07/2025-07-08_"
                "Vereinbarung_Raumnutzung_HdE.pdf' target='_blank'>new one</a> "
                "(or your coworking-contract)."
            )
        ),
        required=True,
        help_text=_("Please upload a single PDF file."),
    )
    usage_agreement_date = forms.DateField(
        label=_("Signing date of the usage agreement"),
        required=True,
        help_text=_("When did you sign the usage agreement?"),
    )
    hde_newsletter = forms.BooleanField(
        required=False,
        label=_(
            "I want to subscribe my organization to the monthly newsletter of"
            "the Haus des Engagements."
        ),
    )
    hde_newsletter_for_actives = forms.BooleanField(
        required=False,
        label=_(
            "I would like to subscribe my organization to the monthly newsletter "
            "for actives (with tips on further training, events, and funding "
            "opportunities in Freiburg and the surrounding area)."
        ),
    )
    organization_groups = ModelMultipleChoiceField(
        queryset=OrganizationGroup.objects.filter(show_on_organization_creation=True),
        widget=CheckboxSelectMultiple,
        required=False,
        label="",
    )

    class Meta:
        model = Organization
        fields = (
            "name",
            "public_name",
            "description",
            "street_and_housenb",
            "area_of_activity",
            "zip_code",
            "city",
            "legal_form",
            "other_legal_form",
            "is_charitable",
            "email",
            "send_booking_emails_only_to_organization",
            "monthly_bulk_access_codes",
            "phone",
            "is_public",
            "website",
            "values_approval",
            "usage_agreement",
            "organization_groups",
            "usage_agreement_date",
        )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["organization_groups"].label_from_instance = (
            lambda organization_group: (
                organization_group.show_on_organization_creation_wording
            )
            or organization_group.name
        )

        is_editing = self.instance.pk is not None

        if user.is_manager():
            manager = user.get_manager()
            organization_groups = (
                OrganizationGroup.objects.filter(show_on_organization_creation=True)
                | manager.organization_groups.all()
            ).distinct()
            self.fields["organization_groups"].queryset = organization_groups
        elif is_editing:
            # Remove the field entirely when editing
            self.fields.pop("organization_groups", None)
        else:
            # For creation, show only groups with show_on_organization_creation
            organization_groups = OrganizationGroup.objects.filter(
                show_on_organization_creation=True
            )
            self.fields["organization_groups"].queryset = organization_groups

        if is_editing:
            # Remove 'hde_newsletter' and 'hde_newsletter_for_actives' for an update
            self.fields.pop("hde_newsletter", None)
            self.fields.pop("hde_newsletter_for_actives", None)

        self.helper = FormHelper()
        address = _("Address")
        consent = _("Consent")
        notifications = _("Notifications")
        affiliation = _("Affiliation")
        affiliation_description = _("An affiliation is not needed to book resources.")

        # Build layout components
        layout_fields = [
            Column("name", css_class="form-group col-md-8 mb-0"),
            Column("public_name", css_class="form-group col-md-8 mb-0"),
            Column("description", css_class="form-group col-md-8 mb-0"),
            Column("area_of_activity", css_class="form-group col-md-8 mb-0"),
            Row(
                Column("legal_form", css_class="form-group col-md-3 mb-0"),
                Column("other_legal_form", css_class="form-group col-md-3 mb-0"),
                css_class="form-row",
            ),
            "is_charitable",
            HTML("<h3 class='mt-5 mb-3'>"),
            HTML(address),
            HTML("</h3>"),
            HTML(
                _(
                    "We need some more information of your organization. If you don't"
                    "have an official address yet, you can also enter your personal "
                    "address."
                )
            ),
            Row(
                Column("street_and_housenb", css_class="form-group col-md-3 mb-0"),
                Column("zip_code", css_class="form-group col-md-2 mb-0"),
                Column("city", css_class="form-group col-md-3 mb-0"),
                css_class="form-row mt-4",
            ),
            Row(
                Column("phone", css_class="form-group col-md-3 mb-0"),
                Column("website", css_class="form-group col-md-3 mb-0"),
                css_class="form-row mt-4",
            ),
            HTML("<h3 class='mt-5 mb-3'>"),
            HTML(notifications),
            HTML("</h3>"),
            Column("email", css_class="form-group col-md-4 mb-0"),
            "send_booking_emails_only_to_organization",
            "monthly_bulk_access_codes",
        ]

        # Only include affiliation section if organization_groups field exists
        if "organization_groups" in self.fields:
            layout_fields.extend(
                [
                    HTML("<h3 class='mt-5 mb-3'>"),
                    HTML(affiliation),
                    HTML("</h3>"),
                    HTML(affiliation_description),
                    "organization_groups",
                ]
            )

        # Continue with consent section
        layout_fields.extend(
            [
                HTML("<h3 class='mt-5 mb-3'>"),
                HTML(consent),
                HTML("</h3>"),
                Row(
                    Column("usage_agreement", css_class="form-group col-md-6 mb-0"),
                    Column(
                        "usage_agreement_date", css_class="form-group col-md-4 mb-0"
                    ),
                ),
                "is_public",
                "values_approval",
            ]
        )

        # Add newsletter fields if they exist (only for creation)
        if "hde_newsletter" in self.fields:
            layout_fields.append("hde_newsletter")
        if "hde_newsletter_for_actives" in self.fields:
            layout_fields.append("hde_newsletter_for_actives")

        # Add submit button
        layout_fields.append(Submit("submit", _("Save organization")))

        self.helper.layout = Layout(*layout_fields)
