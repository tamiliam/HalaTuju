"""Sources and referral partners, Sprint C (owner's rulings 2026-10-09; built 2026-10-19): each
APPLICATION keeps its own answer to "Who referred you?".

SCHEMA (expand — safe for the image still serving):
- `scholarship_applications.referral_code` varchar(50) NOT NULL, DATABASE default '' (`db_default`),
  indexed — so the old image, which never names the column, still inserts.
- `scholarship_applications.source_id` bigint NULL → `referral_sources` (PROTECT; indexed).

DATA — `fill_from_snapshot`: for every application, `referral_code` = the answer frozen at submit
(`intake_snapshot['profile']['referral_source']`, '' when absent or not a string); `source` = the
source with that code OWNED BY THE APPLICATION'S OWN ORGANISATION (`owning_organisation_id`), NULL
for blank, a fixed choice, or a code that organisation has no source for. Never the profile's
latest answer, never another organisation's source (owner ruling 1, TD-386 a). Idempotent;
re-running writes the same values. Reverse: the columns go (the snapshot still holds the answer).

⚠ MIGRATE-FIRST, BY HAND, with `docs/scholarship/sources-c-cutover-sql.md` (DDL rendered offline
with Django's postgresql schema editor, the backfill as SQL, asserting DO blocks, the ledger row
`('scholarship', '0174_application_source')` in the same transaction).
"""
import django.db.models.deletion
from django.db import migrations, models

#: The three fixed choices on every apply form — a copy, on purpose: a migration must not import app
#: code that may change after it is written (`apps.scholarship.gift_sources.FIXED_CODES`).
FIXED_CODES = ('halatuju', 'social', 'other')


def submitted_answer(snapshot):
    """The code frozen in an intake snapshot, or '' — never raises on an odd shape."""
    profile = snapshot.get('profile') if isinstance(snapshot, dict) else None
    code = profile.get('referral_source') if isinstance(profile, dict) else None
    return code[:50] if isinstance(code, str) else ''


def fill_from_snapshot(apps, schema_editor):
    ScholarshipApplication = apps.get_model('scholarship', 'ScholarshipApplication')
    ReferralSource = apps.get_model('scholarship', 'ReferralSource')
    by_key = {(s.organisation_id, s.code): s.pk for s in ReferralSource.objects.all()}
    for app in ScholarshipApplication.objects.only(
            'pk', 'intake_snapshot', 'owning_organisation_id').iterator():
        code = submitted_answer(app.intake_snapshot)
        source_id = (by_key.get((app.owning_organisation_id, code))
                     if code and code not in FIXED_CODES else None)
        ScholarshipApplication.objects.filter(pk=app.pk).update(
            referral_code=code, source_id=source_id)


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0173_referral_sources'),
    ]

    operations = [
        migrations.AddField(
            model_name='scholarshipapplication',
            name='referral_code',
            field=models.CharField(blank=True, db_default='', db_index=True, default='', max_length=50),
        ),
        migrations.AddField(
            model_name='scholarshipapplication',
            name='source',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='applications', to='scholarship.referralsource'),
        ),
        migrations.RunPython(fill_from_snapshot, migrations.RunPython.noop),
    ]
