"""Did the customer actually get their receipt? (2026-10-29)

The owner asked whether a receipt is emailed. It was not: it was raised, numbered, stored and
shown on the billing page, and the organisation had to come and look for it — while the screen
promised *"we will check it against our account and raise your receipt"*.

- ADDITIVE `invoice_receipts.emailed_at` timestamptz NULL — when the receipt was emailed;
- ADDITIVE `invoice_receipts.emailed_to` jsonb NULL — the inboxes it went to.
NULL on both means NEVER EMAILED, which is true of every receipt that exists today, so nothing is
backfilled. `invoicing.email_receipt` stamps them only when the send succeeded, so the screen can
say plainly that it did not go rather than implying it is on its way.

⚠ DEPLOYING BEFORE MIGRATING IS NOT SURVIVABLE. `_invoice_payload` reads `emailed_at` on every
receipt the billing screen renders, for BOTH audiences, so with no column the owner's invoice
list and the tenant's both 500 the moment a receipt exists. Migrate first.

MIGRATE-FIRST, BY HAND, before the push (scholarship ledger 0184 -> 0185). `sqlmigrate` renders
for the LOCAL backend (SQLite), so this is the Postgres DDL to run, verbatim — rendered offline
with Django's postgresql schema editor from this migration — with the ledger row in the SAME
transaction:

    BEGIN;
    ALTER TABLE "invoice_receipts" ADD COLUMN "emailed_at" timestamp with time zone NULL;
    ALTER TABLE "invoice_receipts" ADD COLUMN "emailed_to" jsonb NULL;
    INSERT INTO django_migrations (app, name, applied) VALUES ('scholarship', '0185_receipt_emailed', now());
    COMMIT;

No new table, so no RLS step and nothing for the Security Advisor to gain.

⚠ `emailed_to` is NULL-defaulted rather than `default=list` deliberately: a JSON default makes
Django adapt the Python value through the live driver to render the backfill, which the offline
Postgres render cannot do — and NULL on both columns says "never emailed" more plainly than an
empty list beside a NULL timestamp. Readers go through `list(... or [])`.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0184_invoice_payment_declaration'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoicereceipt',
            name='emailed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='invoicereceipt',
            name='emailed_to',
            field=models.JSONField(blank=True, default=None, null=True),
        ),
    ]
