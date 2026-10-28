from decimal import Decimal

from django.db import migrations

# Keys match the answers already stored in Agreement.details.
FIELDS_BY_FORM_TYPE = {
    "membership": [],
    "coworking": [
        {
            "key": "desks",
            "label": "Arbeitsplätze",
            "field_type": "integer",
            "min_value": Decimal(1),
        },
        {
            "key": "hours_per_week",
            "label": "Stunden pro Woche",
            "field_type": "integer",
            "min_value": Decimal(1),
        },
    ],
    "office": [{"key": "room", "label": "Raum", "field_type": "text"}],
    "cellar": [
        {
            "key": "area_m2",
            "label": "Fläche in m²",
            "field_type": "decimal",
            "min_value": Decimal(1),
        },
    ],
}


def fields_for_form_type(form_type):
    return FIELDS_BY_FORM_TYPE.get(form_type, [])


def create_fields(apps, schema_editor):
    agreement_kind = apps.get_model("agreements", "AgreementKind")
    agreement_kind_field = apps.get_model("agreements", "AgreementKindField")
    for kind in agreement_kind.objects.all():
        for order, definition in enumerate(fields_for_form_type(kind.form_type)):
            agreement_kind_field.objects.get_or_create(
                kind=kind,
                key=definition["key"],
                defaults={**definition, "order": order, "required": True},
            )


class Migration(migrations.Migration):
    dependencies = [
        ("agreements", "0002_agreementkindfield"),
    ]

    operations = [
        migrations.RunPython(create_fields, migrations.RunPython.noop),
    ]
