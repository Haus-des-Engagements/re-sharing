import datetime

from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from recurrence.forms import RecurrenceField

from .models import Booking
from .models import RecurrencePattern


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
    recurrence = RecurrenceField(required=False)

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
                room=room,
                timespan__overlap=(start_datetime, end_datetime),
            )
            if booking_overlap.exists():
                msg = _("The room is already booked during your selected timeslot.")
                self.add_error("room", msg)

            cleaned_data["timespan"] = (start_datetime, end_datetime)

            if self.cleaned_data.get("recurrence"):
                recurrence = self.cleaned_data.get("recurrence")
                # Even when no recurrence data is filled in the form,
                # Django-Recurrence returns an instance of
                # dateutil.rrule.rrule instead of None
                if str(recurrence) != "None":
                    recurrence_pattern = RecurrencePattern(
                        start_datetime=start_datetime,
                        duration=int(
                            float(cleaned_data.get("duration")) * 60,
                        ),  # Converting hours to minutes
                        recurrence=recurrence,
                        recurrence_end=None,
                        room=cleaned_data.get("room"),
                        organization=cleaned_data.get("organization"),
                        title=cleaned_data.get("title"),
                    )
                    cleaned_data["recurrence_pattern"] = recurrence_pattern

        return cleaned_data

    def save(self, user):
        booking = super().save(commit=False)
        booking.user = user
        booking.timespan = self.cleaned_data["timespan"]
        if self.cleaned_data.get("recurrence_pattern") is None:
            booking.recurrence_pattern = None
            booking.save()

        else:
            # save the recurrence pattern
            r_pattern = self.cleaned_data.get("recurrence_pattern")
            r_pattern.user = user
            if (
                r_pattern.recurrence.rrules[0].until is not None
                or r_pattern.recurrence.rrules[0].count is not None
            ):
                occurrence = r_pattern.recurrence.occurrences(
                    dtstart=timezone.make_naive(booking.timespan[0]),
                )
                r_pattern.recurrence_end = timezone.make_aware(occurrence[-1])
                end_date = r_pattern.recurrence_end

            else:
                end_date = booking.timespan[1] + datetime.timedelta(weeks=52)
            r_pattern.save()

            for dt in r_pattern.recurrence.between(
                timezone.make_naive(booking.timespan[0]),
                timezone.make_naive(end_date),
                inc=True,
            ):
                start = booking.timespan[0].time()
                start_datetime = dt.replace(hour=start.hour, minute=start.minute)
                end = booking.timespan[1].time()
                end_datetime = dt.replace(hour=end.hour, minute=end.minute)

                Booking.objects.create(
                    timespan=(start_datetime, end_datetime),
                    room=booking.room,
                    title=booking.title,
                    organization=booking.organization,
                    user=user,
                    recurrence_pattern=r_pattern,
                )

    class Meta:
        model = Booking
        fields = ["room", "startdate", "starttime", "duration", "organization", "title"]
