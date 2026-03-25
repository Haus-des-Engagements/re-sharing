"""Forms for resource management."""

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.utils.translation import gettext_lazy as _

from re_sharing.resources.models import Compensation
from re_sharing.resources.models import Resource
from re_sharing.resources.models import ResourceImage


class CompensationEditForm(forms.ModelForm):
    class Meta:
        model = Compensation
        fields = ["name", "conditions", "hourly_rate", "daily_rate", "is_active"]
        widgets = {
            "conditions": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", _("Save")))


class ResourceEditForm(forms.ModelForm):
    class Meta:
        model = Resource
        fields = [
            "name",
            "type",
            "location",
            "is_private",
            "quantity_available",
            "description",
            "accessibility",
            "max_persons",
            "bookable_times",
            "included_equipment",
        ]
        widgets = {
            "included_equipment": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", _("Save")))


class ResourceImageForm(forms.ModelForm):
    class Meta:
        model = ResourceImage
        fields = ["image", "description"]
        labels = {
            "image": _("Image"),
            "description": _("Description"),
        }
