from django import forms
from django.utils.translation import gettext_lazy as _

from re_sharing.emails.models import EmailLog
from re_sharing.emails.selectors import get_email_types
from re_sharing.organizations.models import Organization


class EmailLogFilterForm(forms.Form):
    search = forms.CharField(label=_("Recipient or subject"), required=False)
    status = forms.ChoiceField(
        label=_("Status"),
        required=False,
        choices=[("", _("all statuses")), *EmailLog.Status.choices],
    )
    email_type = forms.ChoiceField(label=_("Type"), required=False)
    organization = forms.ModelChoiceField(
        label=_("Organization"),
        required=False,
        queryset=Organization.objects.order_by("name"),
        empty_label=_("all organizations"),
    )
    from_date = forms.DateField(
        label=_("From"),
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    to_date = forms.DateField(
        label=_("To"), required=False, widget=forms.DateInput(attrs={"type": "date"})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email_type"].choices = [
            ("", _("all types")),
            *((email_type, email_type) for email_type in get_email_types()),
        ]
        for name, field in self.fields.items():
            is_select = name in ("status", "email_type", "organization")
            field.widget.attrs["class"] = "form-select" if is_select else "form-control"
