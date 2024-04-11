from django import forms

from .models import Booking
from .models import BookingGroup


class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ["timespan", "room"]

    title = forms.CharField(label="Title")

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["organization"] = forms.ModelChoiceField(
            queryset=user.organizations.all(),
            label="Organization",
        )

    def save(self):
        booking = super().save(commit=False)
        booking_group = BookingGroup.objects.create(
            title=self.cleaned_data["title"],
            user=booking.user,
            organization=self.cleaned_data["organization"],
        )
        booking_group.save()
        booking.booking_group = booking_group
        booking.save()
        return booking
