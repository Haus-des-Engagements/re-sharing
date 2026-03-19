from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("resources", "0018_alter_compensation_daily_rate"),
    ]

    operations = [
        migrations.DeleteModel(
            name="AccessCode",
        ),
    ]
