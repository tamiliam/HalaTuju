"""TD-292 (2026-09-30): `ApplicantDocument.Meta.ordering` gains `-id` as a tie-breaker.

STATE-ONLY. `AlterModelOptions` on `ordering` emits NO SQL (`sqlmigrate` prints nothing but the
comment) — ordering is applied per query, never stored in the schema. So there is no DDL to run
on production; the deploy only needs the `django_migrations` row (scholarship ledger 161 → 162),
recorded the same way as any other migration.

The order itself lives in ONE place, `document_snapshot.SNAPSHOT_ORDER`; this file freezes its
value as Django's migration state requires.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0161_overview_layout'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='applicantdocument',
            options={'ordering': ['-uploaded_at', '-id']},
        ),
    ]
