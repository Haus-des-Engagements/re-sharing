import datetime

from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from roomsharing.organizations.models import Membership
from roomsharing.organizations.models import Organization
from roomsharing.rooms.models import Room
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


class BookingListForm(forms.Form):
    show_past_bookings = forms.BooleanField(
        initial=False,
        required=False,
        label=_("Show past bookings"),
    )
    status = forms.ChoiceField(
        choices=[("all", _("All")), *BookingStatus.choices],
        required=False,
        label=_("Status"),
    )

    def __init__(self, *args, **kwargs):
        organizations = kwargs.pop("organizations", None)
        super().__init__(*args, **kwargs)
        if organizations:
            organization_choices = [(org.slug, org.name) for org in organizations]
            self.fields["organization"] = forms.ChoiceField(
                choices=[("all", _("All")), *organization_choices],
                label=_("Organizations"),
            )


class BookingForm(forms.Form):
    startdate = forms.DateField(
        label=_("Start Date"),
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    starttime = forms.ChoiceField(label=_("Start Time"))
    enddate = forms.DateField(
        label=_("Start Date"),
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    endtime = forms.ChoiceField(label=_("Start Time"))

    organization = forms.ModelChoiceField(
        queryset=None,
        label=_("Organization"),
    )
    title = forms.CharField(label=_("Title"))
    message = forms.CharField(
        widget=forms.Textarea(attrs={"rows": "5"}),
        required=False,
    )
    room = forms.ModelChoiceField(
        queryset=Room.objects.all(),
        label=_("Room"),
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        organizations = (
            Organization.objects.filter(organization_of_membership__user=user)
            .filter(organization_of_membership__status=Membership.Status.CONFIRMED)
            .distinct()
        )

        self.fields["organization"].queryset = organizations

        if organizations.exists():
            self.fields["organization"].initial = organizations.first()

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
        self.fields["endtime"].choices = self.fields["starttime"].choices

    def clean(self):
        cleaned_data = super().clean()
        room = cleaned_data.get("room")
        startdate = cleaned_data.get("startdate")
        starttime = cleaned_data.get("starttime")
        enddate = cleaned_data.get("enddate")
        endtime = cleaned_data.get("endtime")

        if room and startdate and starttime and enddate and endtime:
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

            endtime_as_datetime = datetime.datetime.strptime(
                endtime,
                "%H:%M",
            ).astimezone(datetime.UTC)

            if endtime_as_datetime.minute not in [0, 30]:
                msg = _("Start time must be selected in 30-minute intervals.")
                self.add_error("starttime", msg)

            end_datetime = timezone.make_aware(
                datetime.datetime.combine(
                    enddate,
                    endtime_as_datetime.time(),
                ),
            )

            booking_overlap = Booking.objects.filter(
                status=BookingStatus.CONFIRMED,
                room=room,
                timespan__overlap=(start_datetime, end_datetime),
            )
            if booking_overlap.exists():
                msg = _("The room is already booked during your selected timeslot.")
                self.add_error("room", msg)

            cleaned_data["timespan"] = (start_datetime, end_datetime)

        return cleaned_data


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
    RECURRENCE_CHOICES = [
        ("count", _("after x times")),
        ("end_date", _("at date")),
        ("none", _("Never")),
    ]
    recurrence_choice = forms.ChoiceField(
        choices=RECURRENCE_CHOICES,
        initial="none",
        label=_("Ends"),
    )
    start_date = forms.DateField(
        label=_("Start Date"),
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    starttime = forms.TimeField()
    frequency = forms.ChoiceField(choices=FREQUENCIES, label="Wiederkehrender ")
    interval = forms.IntegerField(required=False, label="Wiederholen alle", initial=1)

    BYSETPOS_CHOICES = [
        (1, "first"),
        (2, "second"),
        (3, "third"),
        (4, "fourth"),
        (5, "fifth"),
        (-1, "last"),
    ]

    bysetpos = forms.MultipleChoiceField(
        choices=BYSETPOS_CHOICES,
        required=False,
        label="By Set Pos",
    )
    byweekday = forms.MultipleChoiceField(
        choices=WEEKDAYS,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    BYMONTHDAY_CHOICES = [(None, "----")] + [(i, i) for i in range(1, 32)]
    bymonthday = forms.ChoiceField(choices=BYMONTHDAY_CHOICES, required=False)
    end_date = forms.DateField(
        label=_("End Date"),
        widget=forms.DateInput(attrs={"type": "date"}),
        required=False,
    )
    count = forms.IntegerField(required=False)
    room = forms.ModelChoiceField(
        queryset=Room.objects.all(),
        label=_("Room"),
    )
    duration = forms.IntegerField(required=True, label=_("Duration"), initial=90)

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        starttime = cleaned_data.get("starttime")

        starttime = timezone.make_aware(
            datetime.datetime.combine(
                start_date,
                starttime,
            ),
        )
        return cleaned_data
