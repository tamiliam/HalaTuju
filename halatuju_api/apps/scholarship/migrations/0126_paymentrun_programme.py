"""Payment runs carry their programme (P2b, 2026-07-26) — schema.

One nullable FK on `payment_runs`. Additive-then-read: this migration only creates the column;
`0127` backfills it, and only then does `payments.create_run` require it on NEW runs.

Nullable ON PURPOSE, permanently. A run created before P2b is backfilled from its own items, but
the column stays nullable so a hypothetical itemless legacy run is never forced into a claim it
cannot support. The requirement lives in `create_run` (behaviour), not in a NOT NULL constraint,
because a constraint would also have to refuse the backfill's intermediate state.

⚠ prod holds an OPEN DRAFT run (`PR-2026-08-01`, 30 items) and this is the LIVE payout path.
This migration touches no row.

MIGRATE-FIRST PROD DDL (hand-written — never `manage.py sqlmigrate`; local is SQLite, prod is
Postgres. See docs/lessons.md):

    ALTER TABLE payment_runs ADD COLUMN programme_id bigint NULL
      REFERENCES scholarship_programmes(id) DEFERRABLE INITIALLY DEFERRED;
    CREATE INDEX payment_runs_programme_id_idx ON payment_runs (programme_id);

Post-check: column exists and is NULL on every row (the backfill is `0127`, applied separately so
each step is verifiable on its own).
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0125_donation_signer_emails'),
    ]

    operations = [
        migrations.AddField(
            model_name='paymentrun',
            name='programme',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='payment_runs',
                to='scholarship.programme',
            ),
        ),
    ]
