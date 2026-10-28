from datetime import date
from decimal import Decimal

from django import forms
from django.test import TestCase

from re_sharing.agreements.fields import add_detail_fields
from re_sharing.agreements.fields import detail_items
from re_sharing.agreements.fields import form_field_for
from re_sharing.agreements.fields import to_json
from re_sharing.agreements.fields import to_python
from re_sharing.agreements.models import AgreementKindField
from re_sharing.agreements.tests.factories import AgreementFactory
from re_sharing.agreements.tests.factories import AgreementKindFactory
from re_sharing.agreements.tests.factories import AgreementKindFieldFactory
from re_sharing.agreements.tests.factories import CoworkingKindFactory

FieldType = AgreementKindField.FieldType


def _definition(**kwargs):
    defaults = {"key": "x", "label": "X", "field_type": FieldType.TEXT}
    return AgreementKindField(**{**defaults, **kwargs})


class FormFieldForTest(TestCase):
    def test_field_class_per_type(self):
        expected = {
            FieldType.TEXT: forms.CharField,
            FieldType.INTEGER: forms.IntegerField,
            FieldType.DECIMAL: forms.DecimalField,
            FieldType.DATE: forms.DateField,
            FieldType.CHOICE: forms.ChoiceField,
        }
        for field_type, field_class in expected.items():
            field = form_field_for(_definition(field_type=field_type, choices="a"))
            assert isinstance(field, field_class), field_type

    def test_label_help_and_required(self):
        field = form_field_for(
            _definition(label="Room", help_text="As on the door", required=False)
        )

        assert field.label == "Room"
        assert field.help_text == "As on the door"
        assert not field.required

    def test_minimum(self):
        integer = form_field_for(
            _definition(field_type=FieldType.INTEGER, min_value=Decimal(1))
        )
        decimal = form_field_for(
            _definition(field_type=FieldType.DECIMAL, min_value=Decimal("0.5"))
        )

        assert integer.min_value == 1
        assert decimal.min_value == Decimal("0.5")

    def test_choices_with_stored_answer(self):
        definition = _definition(field_type=FieldType.CHOICE, choices="a\n\n b \n")

        assert [value for value, _ in form_field_for(definition).choices] == [
            "",
            "a",
            "b",
        ]
        kept = form_field_for(definition, stored="old")
        assert [value for value, _ in kept.choices] == ["", "a", "b", "old"]


class AddDetailFieldsTest(TestCase):
    def test_active_fields_in_order(self):
        kind = AgreementKindFactory()
        AgreementKindFieldFactory(kind=kind, key="second", order=2)
        AgreementKindFieldFactory(kind=kind, key="first", order=1)
        AgreementKindFieldFactory(kind=kind, key="old", order=0, is_active=False)
        form = forms.Form()

        names = add_detail_fields(form, kind, details={"first": "value"})

        assert names == ["first", "second"]
        assert form.fields["first"].initial == "value"
        assert "old" not in form.fields


class ConversionTest(TestCase):
    def test_to_json(self):
        assert to_json(_definition(field_type=FieldType.DECIMAL), Decimal("1.5")) == (
            "1.5"
        )
        assert to_json(_definition(field_type=FieldType.DATE), date(2027, 3, 1)) == (
            "2027-03-01"
        )
        assert to_json(_definition(field_type=FieldType.INTEGER), 3) == 3  # noqa: PLR2004
        assert to_json(_definition(), "text") == "text"
        assert to_json(_definition(), None) is None

    def test_to_python(self):
        assert to_python(_definition(field_type=FieldType.DECIMAL), "1.5") == Decimal(
            "1.5"
        )
        assert to_python(_definition(field_type=FieldType.DATE), "2027-03-01") == date(
            2027, 3, 1
        )
        assert to_python(_definition(), "") == ""

    def test_to_python_keeps_values_that_do_not_fit(self):
        assert to_python(_definition(field_type=FieldType.DATE), "soon") == "soon"
        assert to_python(_definition(field_type=FieldType.DECIMAL), "many") == "many"


class DetailItemsTest(TestCase):
    def test_active_fields_with_labels(self):
        agreement = AgreementFactory(
            kind=CoworkingKindFactory(), details={"desks": 2, "hours_per_week": 10}
        )

        assert detail_items(agreement) == [("Desks", 2), ("Hours per week", 10)]

    def test_inactive_and_unknown_answers_follow(self):
        kind = AgreementKindFactory()
        AgreementKindFieldFactory(kind=kind, key="room", label="Room", order=1)
        AgreementKindFieldFactory(
            kind=kind, key="floor", label="Floor", order=0, is_active=False
        )
        agreement = AgreementFactory(
            kind=kind, details={"legacy": "x", "floor": "2", "room": "2.01"}
        )

        assert detail_items(agreement) == [
            ("Room", "2.01"),
            ("Floor", "2"),
            ("legacy", "x"),
        ]

    def test_missing_answers_skipped(self):
        agreement = AgreementFactory(kind=CoworkingKindFactory(), details={})

        assert detail_items(agreement) == []
