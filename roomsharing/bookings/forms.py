import datetime

from crispy_forms.bootstrap import InlineCheckboxes
from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML
from crispy_forms.layout import Div
from crispy_forms.layout import Field
from crispy_forms.layout import Layout
from crispy_forms.layout import Submit
from django import forms
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from roomsharing.organizations.models import BookingPermission
from roomsharing.organizations.models import Organization
from roomsharing.rooms.models import Compensation
from roomsharing.rooms.models import Room
from roomsharing.utils.dicts import MONTHDATES
from roomsharing.utils.dicts import MONTHDAYS
from roomsharing.utils.dicts import RRULE_DAILY_INTERVAL
from roomsharing.utils.dicts import RRULE_MONTHLY_INTERVAL
from roomsharing.utils.dicts import RRULE_WEEKLY_INTERVAL
from roomsharing.utils.dicts import WEEKDAYS
from roomsharing.utils.models import BookingStatus

from .models import Booking
from .models import BookingMessage


class MessageForm(forms.ModelForm):
    text = forms.CharField(
        widget=forms.Textarea(attrs={"rows": "5"}),
        required=True,
    )

    class Meta:
        model = BookingMessage
        fields = ["text"]


class BookingForm(forms.ModelForm):
    startdate = forms.DateField(
        label=_("Date"),
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    starttime = forms.ChoiceField(label=_("from"))
    endtime = forms.ChoiceField(label=_("until"))

    organization = forms.ModelChoiceField(
        queryset=None,
        label=_("Organization"),
    )
    title = forms.CharField(
        label=_("Booking title"),
        help_text=_("e.g. internal meeting, workshop XY, public talk about ZY..."),
    )
    number_of_attendees = forms.IntegerField(label=_("Number of attendees"))
    message = forms.CharField(
        widget=forms.Textarea(attrs={"rows": "5"}),
        label=_(
            "Please describe shortly what you plan to do and what else you want "
            "us to know:"
        ),
        required=False,
    )
    room = forms.ModelChoiceField(
        queryset=Room.objects.all(),
        label=_("Room"),
        widget=forms.Select(
            attrs={
                "hx-trigger": "change, load",
                "hx-post": reverse_lazy("rooms:get-compensations"),
                "hx-target": "#compensations-container",
                "hx-swap": "outerHTML",
            }
        ),
    )

    class CompensationModelChoiceField(forms.ModelChoiceField):
        def label_from_instance(self, obj):
            conditions = ""
            if obj.conditions:
                conditions = ": " + obj.conditions
            if obj.hourly_rate is None:
                return obj.name + conditions
                hour = _("hour")
            return obj.name + " (" + str(obj.hourly_rate) + " € / " + hour + conditions

    compensation = CompensationModelChoiceField(
        queryset=Compensation.objects.all(),
        label=_("Compensation"),
        widget=forms.RadioSelect,
        required=True,
    )

    differing_billing_address = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"id": "id_billing_address", "class": "form-control textinput"}
        ),
    )

    FREQUENCIES = [
        ("NO_REPETITIONS", _("No repetitions")),
        ("DAILY", _("Daily")),
        ("WEEKLY", _("Weekly")),
        ("MONTHLY_BY_DAY", _("Monthly by weekday")),
        ("MONTHLY_BY_DATE", _("Monthly by date")),
    ]
    rrule_repetitions = forms.ChoiceField(choices=FREQUENCIES, label=_("Repeat"))
    RRULE_ENDS_CHOICES = [
        ("AFTER_TIMES", _("after")),
        ("AT_DATE", _("at")),
        ("NEVER", _("never")),
    ]
    rrule_ends = forms.ChoiceField(
        choices=RRULE_ENDS_CHOICES,
        initial="none",
        label=_("ends"),
        required=False,
    )
    rrule_ends_enddate = forms.DateField(
        label=_("End Date"),
        widget=forms.DateInput(attrs={"type": "date"}),
        required=False,
    )
    rrule_ends_count = forms.IntegerField(
        required=False, max_value=100, min_value=1, initial=5
    )
    rrule_daily_interval = forms.ChoiceField(
        choices=RRULE_DAILY_INTERVAL, label=_("Repetition frequency"), required=False
    )
    rrule_weekly_interval = forms.ChoiceField(
        choices=RRULE_WEEKLY_INTERVAL, label=_("Repetition frequency"), required=False
    )
    rrule_weekly_byday = forms.MultipleChoiceField(
        choices=WEEKDAYS,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label=_("Repeat on these days"),
    )
    rrule_monthly_interval = forms.ChoiceField(
        choices=RRULE_MONTHLY_INTERVAL, label=_("Repetition frequency"), required=False
    )
    rrule_monthly_byday = forms.MultipleChoiceField(
        choices=MONTHDAYS,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label=_("Repeat on these days"),
    )
    rrule_monthly_bydate = forms.MultipleChoiceField(
        choices=MONTHDATES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label=_("Repeat on these days"),
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_id = "inner-booking-form"
        self.helper.add_input(Submit("submit", _("Preview")))
        self.fields["rrule_ends_enddate"].label = False
        self.fields["rrule_ends_count"].label = False
        self.fields["rrule_ends"].label = False
        self.fields["rrule_daily_interval"].label = False
        self.fields["rrule_weekly_byday"].label = False
        self.fields["rrule_weekly_interval"].label = False
        self.fields["rrule_monthly_interval"].label = False
        self.fields["rrule_monthly_byday"].label = False
        self.fields["rrule_monthly_bydate"].label = False
        self.helper.layout = Layout(
            Div(
                Field("title", css_class="form-control", wrapper_class="col-4"),
                Field("organization", css_class="form-control", wrapper_class="col-4"),
                css_class="row g-2",
            ),
            Div(
                Field("room", css_class="form-control", wrapper_class="col-4"),
                Field(
                    "number_of_attendees",
                    css_class="form-control",
                    wrapper_class="col-4",
                ),
                css_class="row g-2",
            ),
            Div(
                Field("startdate", css_class="form-control", wrapper_class="col-2"),
                Field("starttime", css_class="form-control", wrapper_class="col-2"),
                Field("endtime", css_class="form-control", wrapper_class="col-2"),
                css_class="row g-2",
            ),
            Div(
                Field(
                    "rrule_repetitions",
                    css_class="form-control",
                    wrapper_class="col-2",
                ),
                css_class="row g-2",
            ),
            Div(
                Div(
                    Div(
                        HTML(
                            '{% load i18n %}<label class="control-label">'
                            '{% trans "Endet" %}</label>'
                        ),
                        css_class="col-1",
                    ),
                    Field(
                        "rrule_ends",
                        css_class="form-control",
                        wrapper_class="col-2",
                    ),
                    Field(
                        "rrule_ends_enddate",
                        css_class="form-control",
                        wrapper_class="col-2",
                    ),
                    Field(
                        "rrule_ends_count",
                        css_class="form-control",
                        wrapper_class="col-1",
                    ),
                    css_class="row g-2",
                ),
                Div(
                    Div(
                        Div(
                            HTML(
                                '{% load i18n %}<label class="control-label">'
                                '{% trans "Repeat" %}</label>'
                            ),
                            css_class="col-1",
                        ),
                        Field(
                            "rrule_daily_interval",
                            css_class="form-control",
                            wrapper_class="col-2",
                        ),
                        css_class="row g-2",
                    ),
                    css_class="row g-2",
                    css_id="rrule_daily",
                    style="display: none",  # initially hidden
                ),
                Div(
                    Div(
                        Div(
                            HTML(
                                '{% load i18n %}<label class="control-label">'
                                '{% trans "Repeat" %}</label>'
                            ),
                            css_class="col-1",
                        ),
                        Field(
                            "rrule_weekly_interval",
                            css_class="form-control",
                            wrapper_class="col-2",
                        ),
                        InlineCheckboxes(
                            "rrule_weekly_byday",
                            css_class="form-control",
                            wrapper_class="col-8",
                        ),
                        css_class="row g-2",
                    ),
                    css_class="row g-2",
                    css_id="rrule_weekly",
                    style="display: none",  # initially hidden
                ),
                Div(
                    Div(
                        Div(
                            HTML(
                                '{% load i18n %}<label class="control-label">'
                                '{% trans "Repeat" %}</label>'
                            ),
                            css_class="col-1",
                        ),
                        Field(
                            "rrule_monthly_interval",
                            css_class="form-control",
                            wrapper_class="col-2",
                        ),
                        InlineCheckboxes(
                            "rrule_monthly_byday",
                            css_class="form-control",
                            wrapper_class="col-10",
                            css_id="rrule_monthly_bydate",
                        ),
                        InlineCheckboxes(
                            "rrule_monthly_bydate",
                            css_class="form-control",
                            css_id="rrule_monthly_bydate",
                            wrapper_class="col-10",
                        ),
                        css_class="row g-2",
                    ),
                    css_class="row g-2",
                    css_id="rrule_monthly",
                    style="display: none",  # initially hidden
                ),
                css_class="row g-2",
                css_id="rrule_additional_fields",
                style="display: none",  # initially hidden
            ),
            HTML("{% include 'bookings/partials/compensations.html' %}"),
            HTML(
                '{% if form.compensation.errors %}<span id="error_compensations" '
                'class="text-danger"><strong>{% load i18n %}{% trans "Please select a '
                'billing / donation plan" %}</strong></span>{% endif %}'
            ),
            Div(
                Field(
                    "message", css_class="form-control", wrapper_class="col-8", rows="3"
                ),
                css_class="row g-2",
            ),
        )
        if user.is_staff:
            organizations = Organization.objects.all()
        else:
            organizations = (
                Organization.objects.filter(
                    organization_of_bookingpermission__user=user
                )
                .filter(
                    organization_of_bookingpermission__status=BookingPermission.Status.CONFIRMED
                )
                .distinct()
            )

        self.fields["organization"].queryset = organizations

        if organizations.exists():
            self.fields["organization"].initial = organizations.first()

        self.fields["starttime"].choices = [
            (
                datetime.time(hour, minute).strftime("%H:%M"),
                datetime.time(hour, minute).strftime("%H:%M"),
            )
            for hour in range(6, 24)
            for minute in range(0, 60, 30)
        ]
        self.fields["endtime"].choices = self.fields["starttime"].choices

        if "room" in self.initial:
            self.fields["compensation"].queryset = Compensation.objects.filter(
                room=self.initial["room"]
            )

    def clean(self):  # noqa: C901
        cleaned_data = super().clean()
        room = cleaned_data.get("room")
        startdate = cleaned_data.get("startdate")
        starttime = cleaned_data.get("starttime")
        endtime = cleaned_data.get("endtime")
        rrule_repetitions = cleaned_data.get("rrule_repetitions")
        rrule_ends = cleaned_data.get("rrule_ends")
        rrule_ends_count = cleaned_data.get("rrule_ends_count")
        rrule_ends_enddate = cleaned_data.get("rrule_ends_enddate")
        rrule_weekly_byday = cleaned_data.get("rrule_weekly_byday")
        rrule_monthly_byday = cleaned_data.get("rrule_monthly_byday")
        rrule_monthly_bydate = cleaned_data.get("rrule_monthly_bydate")

        def convert_time(time_str):
            time_as_datetime = datetime.datetime.strptime(time_str, "%H:%M")  # noqa: DTZ007
            if time_as_datetime.minute not in [0, 30]:
                raise ValueError(
                    _("Start time must be selected in 30-minute intervals.")
                )
            return time_as_datetime.time()

        try:
            starttime = convert_time(starttime)
            cleaned_data["starttime"] = starttime
            start_datetime = timezone.make_aware(
                datetime.datetime.combine(startdate, starttime)
            )
            endtime = convert_time(endtime)
            cleaned_data["endtime"] = endtime
            end_datetime = timezone.make_aware(
                datetime.datetime.combine(startdate, endtime)
            )
            if start_datetime < timezone.now():
                msg = _("The start must be in the future.")
                for field in ["starttime", "startdate"]:
                    self.add_error(field, msg)
            if end_datetime <= start_datetime:
                msg = _("The end must be after the start.")
                for field in ["endtime", "starttime"]:
                    self.add_error(field, msg)

        except ValueError as e:
            self.add_error("starttime", str(e))

        if startdate > (timezone.now().date() + timezone.timedelta(days=730)):
            msg = _("You can only book for the next 2 years.")
            self.add_error("startdate", msg)

        if rrule_ends_enddate:
            cleaned_data["rrule_ends_enddate"] = timezone.make_aware(
                datetime.datetime.combine(rrule_ends_enddate, endtime)
            )

        cleaned_data["start_datetime"] = start_datetime
        cleaned_data["timespan"] = (start_datetime, end_datetime)

        field_errors = {
            "rrule_ends_count": (
                "Please define the number of ocurrences (between 1 and 100)",
                (rrule_repetitions != "NO REPETITIONS")
                and (rrule_ends == "AFTER_TIMES")
                and not rrule_ends_count,
            ),
            "rrule_ends_enddate": (
                "Please select a date in the future",
                (rrule_repetitions != "NO REPETITIONS")
                and (rrule_ends == "AT_DATE")
                and (
                    not rrule_ends_enddate or rrule_ends_enddate < timezone.now().date()
                ),
            ),
            "rrule_weekly_byday": (
                "Please select the days of the week when the booking should recur.",
                rrule_repetitions == "WEEKLY" and not rrule_weekly_byday,
            ),
            "rrule_monthly_byday": (
                "Please select the days of the month when the booking should recur.",
                rrule_repetitions == "MONTHLY_BY_DAY" and not rrule_monthly_byday,
            ),
            "rrule_monthly_bydate": (
                "Please select the dates of the month when the booking should recur.",
                rrule_repetitions == "MONTHLY_BY_DATE" and not rrule_monthly_bydate,
            ),
        }

        for field, (msg, condition) in field_errors.items():
            if condition:
                self.add_error(field, _(msg))

        if rrule_repetitions == "NO_REPETITIONS" and end_datetime > start_datetime:
            if Booking.objects.filter(
                status=BookingStatus.CONFIRMED,
                room=room,
                timespan__overlap=(start_datetime, end_datetime),
            ).exists():
                msg = _("The room is already booked during your selected timeslot.")
                self.add_error("room", msg)

        return cleaned_data

    class Meta:
        model = Booking
        fields = [
            "title",
            "startdate",
            "starttime",
            "endtime",
            "organization",
            "message",
            "room",
            "number_of_attendees",
            "differing_billing_address",
        ]
