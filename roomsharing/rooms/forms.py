# forms.py
from django import forms
from django.forms.widgets import DateTimeInput


class RoomsListFilter(forms.Form):
    max_persons = forms.IntegerField(required=False)
    name = forms.CharField(required=False)
    start_datetime = forms.DateTimeField(
        required=False,
        widget=DateTimeInput(attrs={"type": "datetime-local"}),
    )
    duration = forms.IntegerField(required=False)
