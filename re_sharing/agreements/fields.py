"""Form fields built from a kind's field definitions, and the conversion of
their answers to and from ``Agreement.details``."""

from datetime import date
from decimal import Decimal
from decimal import InvalidOperation

from django import forms

from .models import AgreementKindField

FieldType = AgreementKindField.FieldType
DATE_INPUT = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
TEXT_MAX_LENGTH = 200


def form_field_for(definition: AgreementKindField, *, stored=None) -> forms.Field:
    """The form field for one definition. ``stored`` is an existing answer,
    kept selectable even if it is no longer one of the choices."""
    common = {
        "label": definition.label,
        "help_text": definition.help_text,
        "required": definition.required,
    }
    minimum = definition.min_value
    if definition.field_type == FieldType.INTEGER:
        return forms.IntegerField(
            min_value=int(minimum) if minimum is not None else None, **common
        )
    if definition.field_type == FieldType.DECIMAL:
        return forms.DecimalField(
            max_digits=12, decimal_places=2, min_value=minimum, **common
        )
    if definition.field_type == FieldType.DATE:
        return forms.DateField(widget=DATE_INPUT, **common)
    if definition.field_type == FieldType.CHOICE:
        options = definition.choice_list
        if stored and stored not in options:
            options = [*options, stored]
        return forms.ChoiceField(
            choices=[("", "---------"), *((option, option) for option in options)],
            **common,
        )
    return forms.CharField(max_length=TEXT_MAX_LENGTH, **common)


def add_detail_fields(form: forms.Form, kind, *, details=None) -> list[str]:
    """Add the kind's active fields to ``form``, prefilled from ``details``.
    Returns the added field names in order."""
    details = details or {}
    names = []
    for definition in kind.active_fields:
        stored = details.get(definition.key)
        field = form_field_for(definition, stored=stored)
        if stored not in (None, ""):
            field.initial = to_python(definition, stored)
        form.fields[definition.key] = field
        names.append(definition.key)
    return names


def to_json(definition: AgreementKindField, value):
    """A cleaned form value as stored in ``details``."""
    if value is None:
        return None
    if definition.field_type == FieldType.DECIMAL:
        return str(value)
    if definition.field_type == FieldType.DATE:
        return value.isoformat()
    return value


def to_python(definition: AgreementKindField, value):
    """A stored answer for display or as form initial. Values that no longer
    fit the type are returned unchanged."""
    if value in (None, ""):
        return value
    try:
        if definition.field_type == FieldType.DECIMAL:
            return Decimal(str(value))
        if definition.field_type == FieldType.DATE:
            return date.fromisoformat(value)
    except (InvalidOperation, TypeError, ValueError):
        return value
    return value


def details_from(form: forms.Form, kind) -> dict:
    """The answers of ``form`` for the kind's active fields."""
    return {
        definition.key: to_json(definition, form.cleaned_data.get(definition.key))
        for definition in kind.active_fields
    }


def detail_items(agreement) -> list[tuple[str, object]]:
    """Answers with their labels: active fields in order, then all others."""
    details = agreement.details or {}
    definitions = list(agreement.kind.fields_of_kind.all())
    by_key = {definition.key: definition for definition in definitions}
    ordered = [d.key for d in definitions if d.is_active]
    ordered += [d.key for d in definitions if not d.is_active]
    ordered += sorted(key for key in details if key not in by_key)

    items = []
    for key in ordered:
        if key not in details:
            continue
        definition = by_key.get(key)
        if definition is None:
            items.append((key, details[key]))
        else:
            items.append((definition.label, to_python(definition, details[key])))
    return items
