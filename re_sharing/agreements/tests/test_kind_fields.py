import importlib
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from re_sharing.agreements.models import AgreementKindField
from re_sharing.agreements.tests.factories import AgreementKindFactory
from re_sharing.agreements.tests.factories import AgreementKindFieldFactory

FieldType = AgreementKindField.FieldType
migration = importlib.import_module(
    "re_sharing.agreements.migrations.0003_fields_from_form_type"
)


class AgreementKindFieldModelTest(TestCase):
    def _field(self, **kwargs):
        defaults = {
            "kind": AgreementKindFactory(),
            "key": "room",
            "label": "Room",
            "field_type": FieldType.TEXT,
        }
        return AgreementKindField(**{**defaults, **kwargs})

    def test_valid_text_field(self):
        self._field().full_clean()

    def test_key_unique_per_kind(self):
        field = AgreementKindFieldFactory(key="room")
        AgreementKindFieldFactory(key="room")  # another kind is fine

        with pytest.raises(IntegrityError):
            AgreementKindFieldFactory(kind=field.kind, key="room")

    def test_reserved_key(self):
        with pytest.raises(ValidationError) as error:
            self._field(key="amount").full_clean()
        assert "key" in error.value.message_dict

    def test_choice_needs_choices(self):
        with pytest.raises(ValidationError) as error:
            self._field(field_type=FieldType.CHOICE, choices=" \n").full_clean()
        assert "choices" in error.value.message_dict

        self._field(field_type=FieldType.CHOICE, choices="a\nb").full_clean()

    def test_choices_only_for_choice_fields(self):
        with pytest.raises(ValidationError) as error:
            self._field(choices="a").full_clean()
        assert "choices" in error.value.message_dict

    def test_minimum_only_for_numbers(self):
        with pytest.raises(ValidationError) as error:
            self._field(min_value=Decimal(1)).full_clean()
        assert "min_value" in error.value.message_dict

        self._field(field_type=FieldType.DECIMAL, min_value=Decimal("0.5")).full_clean()

    def test_integer_minimum_must_be_whole(self):
        with pytest.raises(ValidationError) as error:
            self._field(
                field_type=FieldType.INTEGER, min_value=Decimal("1.5")
            ).full_clean()
        assert "min_value" in error.value.message_dict

    def test_ordering_and_active_fields(self):
        kind = AgreementKindFactory()
        second = AgreementKindFieldFactory(kind=kind, order=2)
        first = AgreementKindFieldFactory(kind=kind, order=1)
        AgreementKindFieldFactory(kind=kind, order=0, is_active=False)

        assert kind.active_fields == [first, second]

    def test_str_and_choice_list(self):
        field = self._field(label="Size", choices=" small \n\nlarge")

        assert str(field) == f"{field.kind} - Size"
        assert field.choice_list == ["small", "large"]


class FormTypeMigrationTest(TestCase):
    def test_fields_per_form_type(self):
        keys = {
            form_type: [
                field["key"] for field in migration.fields_for_form_type(form_type)
            ]
            for form_type in ["membership", "coworking", "office", "cellar", "other"]
        }

        assert keys == {
            "membership": [],
            "coworking": ["desks", "hours_per_week"],
            "office": ["room"],
            "cellar": ["area_m2"],
            "other": [],
        }

    def test_create_fields(self):
        coworking = AgreementKindFactory()
        coworking.form_type = "coworking"
        cellar = AgreementKindFactory()
        cellar.form_type = "cellar"
        kinds = SimpleNamespace(
            objects=SimpleNamespace(all=lambda: [coworking, cellar])
        )
        models = {"AgreementKind": kinds, "AgreementKindField": AgreementKindField}
        apps = SimpleNamespace(get_model=lambda app, name: models[name])

        migration.create_fields(apps, None)
        migration.create_fields(apps, None)  # idempotent

        desks, hours = coworking.fields_of_kind.all()
        assert (desks.key, desks.field_type, desks.min_value) == (
            "desks",
            FieldType.INTEGER,
            Decimal(1),
        )
        assert (desks.order, hours.order) == (0, 1)
        assert desks.required
        area = cellar.fields_of_kind.get()
        assert (area.key, area.field_type) == ("area_m2", FieldType.DECIMAL)
