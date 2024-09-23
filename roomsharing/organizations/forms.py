from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML
from crispy_forms.layout import Column
from crispy_forms.layout import Layout
from crispy_forms.layout import Row
from crispy_forms.layout import Submit
from django import forms
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from .models import Organization


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
            "Of course you can also book rooms if you're not officially charitable!"
        ),
        required=False,
    )
    is_coworking = forms.BooleanField(
        label=_("We are Co-Working at the HdE."),
        help_text=_("Please select only if you have a Co-Working contract."),
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
    entitled = forms.BooleanField(
        label=_(
            "I'm entitled by my organization to create this profile and make booking "
            "requests in its name."
        ),
        required=True,
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
            "is_coworking",
            "email",
            "phone",
            "is_public",
            "website",
            "entitled",
            "values_approval",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        address = _("Address")
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
            HTML("<h3 class='mt-5 mb-3'>Weiteres</h3>"),
            "is_coworking",
            "is_public",
            "values_approval",
            "entitled",
            Submit("submit", _("Save organization")),
        )
