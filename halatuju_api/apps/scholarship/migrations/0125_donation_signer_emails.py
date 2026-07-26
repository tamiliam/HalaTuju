"""Wallet credit — the signature's IDENTITY key (P4b, 2026-07-26).

Three additive columns on ``sponsor_donations``, one per signature slot, mirroring the
``PaymentRun`` triple (``admin_signed_email`` / ``finance_signed_email`` /
``org_admin_signed_email``).

WHY an email column and not the existing name column: pairwise distinctness — the rule that
stops one person filling two slots in a maker-checker chain — must key on IDENTITY, and a
NAME is not an identity. Prod carries **two active admins both named "Ve. Elanjelian"**
(a super on `tamiliam@gmail.com` and an org_admin on `elanjelian@me.com`, genuinely
different accounts). A name-keyed rule is wrong in BOTH directions there: it would let one
human sign twice under two spellings, and it would refuse two different people who happen to
share a name. The payments chain settled this by keying on email; this brings the credit
chain into line rather than inventing a second, weaker answer.

Existing rows: every current donation is `source='legacy'` / `status='confirmed'` and has
never been through the chain, so all three columns are correctly EMPTY. No data migration,
no balance moves.

MIGRATE-FIRST PROD DDL (hand-written — never `manage.py sqlmigrate`; local is SQLite, prod
is Postgres. See docs/lessons.md):

    ALTER TABLE sponsor_donations
      ADD COLUMN recorded_by_email        varchar(254) NOT NULL DEFAULT '',
      ADD COLUMN finance_checked_by_email varchar(254) NOT NULL DEFAULT '',
      ADD COLUMN confirmed_by_email       varchar(254) NOT NULL DEFAULT '';
    -- Django keeps defaults app-side (the 0061 precedent):
    ALTER TABLE sponsor_donations
      ALTER COLUMN recorded_by_email DROP DEFAULT,
      ALTER COLUMN finance_checked_by_email DROP DEFAULT,
      ALTER COLUMN confirmed_by_email DROP DEFAULT;

Post-check: all three columns empty on every row, and the sum of CONFIRMED donations per
programme is unchanged (this migration must not move a single balance).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0124_donation_credit_chain'),
    ]

    operations = [
        migrations.AddField(
            model_name='donation',
            name='recorded_by_email',
            field=models.CharField(blank=True, default='', max_length=254),
        ),
        migrations.AddField(
            model_name='donation',
            name='finance_checked_by_email',
            field=models.CharField(blank=True, default='', max_length=254),
        ),
        migrations.AddField(
            model_name='donation',
            name='confirmed_by_email',
            field=models.CharField(blank=True, default='', max_length=254),
        ),
    ]
