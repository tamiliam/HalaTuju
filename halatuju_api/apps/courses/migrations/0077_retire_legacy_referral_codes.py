"""Per-gift referral sources, Sprint 2 (owner, 2026-10-08): the two LEGACY individual-coordinator
referral codes leave every form, and every saved profile carrying one moves to `other`.

`pushparani` (Ms. Pushparani, Kapar) and `govind` (Mr. Govind, Melaka) were people, not
organisations, on the old hard-coded list; the owner ruled them off the form. A profile still
holding either would be pre-filled with a code no form offers — the form clears it and the server
refuses it — so the stored value moves to the catch-all `other`, which is what both already
collapsed to on every admin surface (`REFERRAL_SOURCE_ACRONYM`). Production on 2026-10-08:
1 profile with `pushparani`, 0 with `govind`.

DATA ONLY: no schema change. `referred_by_org` is not touched (neither code was ever a
`PartnerOrganisation` row, so no profile carrying one is linked to anything).

⚠ THE REVERSE IS A NO-OP, ON PURPOSE: once moved, a profile's `other` cannot be told apart from
one the student chose, so un-migrating would invent referrals. Reversing this migration leaves the
data as it is.

⚠ MIGRATE-FIRST via Supabase MCP before the push, then record the `django_migrations` row (courses
ledger 0076 → 0077). The SQL — the pre-check count, the UPDATE and the ledger row in one
transaction — is `docs/scholarship/gift-sources-s2-cutover-sql.md`. Order against the deploy is
safe either way: the old image offers both codes and accepts `other`; the new one offers neither.
"""
from django.db import migrations

LEGACY_CODES = ('pushparani', 'govind')


def retire_legacy_codes(apps, schema_editor):
    StudentProfile = apps.get_model('courses', 'StudentProfile')
    StudentProfile.objects.filter(referral_source__in=LEGACY_CODES).update(referral_source='other')


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0076_spm_prereq_selection'),
    ]

    operations = [
        migrations.RunPython(retire_legacy_codes, migrations.RunPython.noop),
    ]
