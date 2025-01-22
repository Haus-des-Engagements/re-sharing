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


class OrganizationForm(forms.ModelForm):
    name = forms.CharField(
        label=_("Name of the organization"),
        required=True,
        help_text=_("e.g. Accordion Club Gundelfinden e.V."),
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
    email = forms.EmailField(label=_("E-mail address of the organization"))
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
    # TODO [migration]
    usage_agreement = forms.FileField(
        label=mark_safe(  # noqa: S308
            _(
                "Upload your existing usage agreement or add a <a href='https://haus-"
                "des-engagements.de/wp-content/uploads/2025/01/Vereinbarung_Raumnutzung"
                "_HdE_Formular_2025_reduziert.pdf' target='_blank'>new one</a> "
                "(not needed for Co-Workers)."
            )
        ),
        required=False,
        help_text=_("Please upload a single PDF file."),
    )
    usage_agreement_date = forms.DateField(
        label=_("Signing date of the usage agreement"),
        widget=forms.DateInput(attrs={"type": "date"}),
        required=False,
        help_text=_("When did you sign the usage agreement?"),
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
            "description",
            "street_and_housenb",
            "area_of_activity",
            "zip_code",
            "city",
            "legal_form",
            "other_legal_form",
            "is_charitable",
            "email",
            "phone",
            "is_public",
            "website",
            "values_approval",
            "usage_agreement",
            "organization_groups",
            "usage_agreement_date",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["organization_groups"].label_from_instance = (
            lambda organization_group: (
                organization_group.show_on_organization_creation_wording
            )
            or organization_group.name
        )
        self.helper = FormHelper()
        address = _("Address")
        consent = _("Consent")
        affiliation = _("Affiliation")
        affiliation_description = _("An affiliation is not needed to book resources.")
        self.helper.layout = Layout(
            Column("name", css_class="form-group col-md-8 mb-0"),
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
                Column("email", css_class="form-group col-md-3 mb-0"),
                Column("phone", css_class="form-group col-md-2 mb-0"),
                Column("website", css_class="form-group col-md-3 mb-0"),
                css_class="form-row",
            ),
            HTML("<h3 class='mt-5 mb-3'>"),
            HTML(affiliation),
            HTML("</h3>"),
            HTML(affiliation_description),
            "organization_groups",
            HTML("<h3 class='mt-5 mb-3'>"),
            HTML(consent),
            HTML("</h3>"),
            Row(
                Column("usage_agreement", css_class="form-group col-md-6 mb-0"),
                Column("usage_agreement_date", css_class="form-group col-md-4 mb-0"),
            ),
            "is_public",
            "values_approval",
            Submit("submit", _("Save organization")),
        )

    def save(self, commit=True):  # noqa: FBT002
        instance = super().save(commit=False)

        # Save the instance if commit is True
        if commit:
            instance.save()
        # Many-to-many fields must be added after the instance is saved
        if (
            instance.pk
        ):  # Ensure the instance has been saved before accessing its M2M fields
            instance.organization_groups.set(self.cleaned_data["organization_groups"])

        return instance
