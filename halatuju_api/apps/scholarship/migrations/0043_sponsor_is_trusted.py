from django.db import migrations, models


class Migration(migrations.Migration):
    """Boundary decision (2026-06-07): add Sponsor.is_trusted (default True) so the
    anonymised card can gate institution-level detail to trusted (launch) sponsors.
    Additive + backward-compatible — every existing sponsor becomes trusted."""

    dependencies = [
        ('scholarship', '0042_parents_occupation_textfield'),
    ]

    operations = [
        migrations.AddField(
            model_name='sponsor',
            name='is_trusted',
            field=models.BooleanField(default=True),
        ),
    ]
