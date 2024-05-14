import datetime

from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import Booking


class BookingForm(forms.ModelForm):
    startdate = forms.DateField(
        label=_("Start Date"),
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    starttime = forms.ChoiceField(label=_("Start Time"))
    duration = forms.ChoiceField(label=_("Duration"))
    organization = forms.ModelChoiceField(
        queryset=None,
        label=_("Organization"),
    )
    title = forms.CharField(label=_("Title"))

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["organization"].queryset = user.organizations.all()
        self.fields["starttime"].choices = [
            (time.strftime("%H:%M"), time.strftime("%H:%M"))
            for time in (
                datetime.datetime.combine(
                    datetime.datetime.now(tz=datetime.UTC).date(),
                    datetime.time(hour, minute),
                )
                for hour in range(6, 24)
                for minute in (0, 30)
            )
        ]

        # Generate choices for duration dropdown
        self.fields["duration"].choices = [
            (str(mins / 60), f"{mins / 60:.1f} hour(s)") for mins in range(30, 481, 30)
        ]

    def clean(self):
        cleaned_data = super().clean()
        room = cleaned_data.get("room")
        startdate = cleaned_data.get("startdate")
        starttime = cleaned_data.get("starttime")
        duration = cleaned_data.get("duration")

        if room and startdate and starttime:
            starttime_as_datetime = datetime.datetime.strptime(
                starttime,
                "%H:%M",
            ).astimezone(datetime.UTC)

            if starttime_as_datetime.minute not in [0, 30]:
                msg = _("Start time must be selected in 30-minute intervals.")
                self.add_error("starttime", msg)

            start_datetime = timezone.make_aware(
                datetime.datetime.combine(
                    startdate,
                    starttime_as_datetime.time(),
                ),
            )

            duration_float = float(duration)
            if duration_float % 0.5 != 0:
                msg = _("Duration must be selected in 30-minute intervals.")
                self.add_error("duration", msg)

            end_datetime = start_datetime + datetime.timedelta(hours=duration_float)

            booking_overlap = Booking.objects.filter(
                status=Booking.Status.CONFIRMED,
                room=room,
                timespan__overlap=(start_datetime, end_datetime),
            )
            if booking_overlap.exists():
                msg = _("The room is already booked during your selected timeslot.")
                self.add_error("room", msg)

            cleaned_data["timespan"] = (start_datetime, end_datetime)

        return cleaned_data

    def save(self, user):
        booking = super().save(commit=False)
        booking.user = user
        booking.timespan = self.cleaned_data["timespan"]
        booking.status = Booking.Status.PENDING
        booking.save()
        return booking

    class Meta:
        model = Booking
        fields = ["room", "startdate", "starttime", "duration", "organization", "title"]


FREQUENCIES = [
    ("MONTHLY", "Monthly"),
    ("WEEKLY", "Weekly"),
    ("DAILY", "Daily"),
]

WEEKDAYS = [
    ("MO", "Monday"),
    ("TU", "Tuesday"),
    ("WE", "Wednesday"),
    ("TH", "Thursday"),
    ("FR", "Friday"),
    ("SA", "Saturday"),
    ("SU", "Sunday"),
]


class RecurrenceForm(forms.Form):
    start_date = forms.DateField(
        label=_("Start Date"),
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    end_date = forms.DateField(
        label=_("End Date"),
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    frequency = forms.ChoiceField(choices=FREQUENCIES)
    interval = forms.IntegerField(required=False)
    bysetpos = forms.IntegerField(required=False)
    byweekday = forms.MultipleChoiceField(choices=WEEKDAYS, required=False)
    bymonthday = forms.IntegerField(required=False)
