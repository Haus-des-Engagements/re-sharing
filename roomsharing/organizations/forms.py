from django import forms

from .models import Organization


class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = (
            "name",
            "street",
            "house_number",
            "zip_code",
            "city",
            "legal_form",
            "certificate_of_tax_exemption",
        )


class OrganizationsListFilter(forms.Form):
    name = forms.CharField(required=False)
