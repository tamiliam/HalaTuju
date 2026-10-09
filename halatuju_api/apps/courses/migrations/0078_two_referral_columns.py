"""Sources and referral partners, Sprint A (owner's model, 2026-10-09): the student record gets TWO
INDEPENDENT referral columns, and the platform's referral partners are marked.

SCHEMA (additive, safe for the image still serving):
- `partner_organisations.is_referral_partner` boolean NOT NULL, DEFAULT false IN THE DATABASE
  (`db_default`), so the old image's Sources POST — which does not know the column — still inserts.
- `api_student_profiles.source_id` nullable FK → `partner_organisations` (the SOURCE column; Sprint B
  repoints it to the new sources table, same ids). Nullable: the old image never names it.

DATA (owner's rulings, 2026-10-09):
1. `mark_referral_partners` — a row is a REFERRAL PARTNER when it carries a `partner`-role login
   (`PartnerAdmin.org`, role `partner`, active or not). Derived, not hard-coded. Production
   (2026-10-09 reading, decisions.md 2026-08-03): exactly ONE row, `cumig`, which carries both
   partner logins. Refuses (RuntimeError) if a TENANT would be marked — a tenant is never a referral
   partner. The cutover SQL asserts the exact set (`cumig` alone) before it goes on.
2. `backfill_two_columns` —
   SOURCE: for each profile with an application, the code its MOST RECENT application (highest id;
   ids follow `submitted_at`) recorded in `intake_snapshot.profile.referral_source`, when that code
   is a SOURCE row (a non-tenant `PartnerOrganisation`, not one of the fixed `halatuju` / `social` /
   `other`); else NULL. A profile with no application: NULL.
   REFERRAL PARTNER (`referred_by_org`): every link to a referral partner is KEPT — including the 13
   bursary applicants who picked CUMIG on the form (owner: "Filled" — both columns CUMIG). Every link
   to a row that is NOT a referral partner (a source-only row or a tenant) is CLEARED: the bursary
   form wrote those, and what they said now lives in the source column.

EXPECTED ON PRODUCTION (production-shaped reasoning from the lead's 2026-10-09 figures; the lead
re-reads every one at the cutover with the read-only SQL in the cutover doc, and tells the owner of
any difference BEFORE applying — lessons.md 2026-10-09):
- referral partners marked: 1 (`cumig`).
- `referred_by_org` → cumig: 254 before (241 course-selector-only students + the 13 applicants who
  picked CUMIG), 254 after. The partner logins' list is unchanged.
- `referred_by_org` → any other row: N before (the applicants whose bursary answer named another
  source, plus any old course-selector link to a non-partner row), 0 after. N is read at cutover.
- `source` set: 0 before (new column); after = the profiles whose latest application named a source
  row — the 13 CUMIG applicants among them. Read at cutover.
The lead's read-only production reading on 2026-10-09 matched: N = 95 (smc 62, pptm 16, ewrf 9,
mhm 6, hyo 1, hss 1 — all applicants); source S = 108 (those 95 + the 13 CUMIG pickers).
The backfill takes a source from any non-tenant, non-fixed row, switched off or not; the live writer
names only `gift_sources.active_sources()` — the same result on production today.

Idempotent: a second run computes the same columns from the same snapshots and clears nothing more.
⚠ The reverse is a documented NO-OP (Django cannot know which links it cleared): the cutover SQL
copies every (profile id, referred_by_org_id) pair it clears into a dated backup table first, and its
rollback restores from there.

⚠ MIGRATE-FIRST via the Supabase MCP before the push, with the ledger row, in ONE transaction:
`docs/scholarship/two-columns-cutover-sql.md` (DDL rendered offline with Django's postgresql schema
editor, the backup table with RLS + a `service_role` policy, the backfill as SQL, pre/post checks).
"""
import django.db.models.deletion
from django.db import migrations, models

#: The three fixed choices on every apply form — a copy, on purpose: a migration must not import app
#: code that may change after it is written (`apps.scholarship.gift_sources.FIXED_CODES`).
FIXED_CODES = ('halatuju', 'social', 'other')


def _tenant_ids(apps):
    """`PartnerOrganisation.objects.tenants()`, spelt out for the historical models (which carry no
    custom queryset): owns an ACTIVE programme, or has an ACTIVE `org_admin`."""
    Programme = apps.get_model('scholarship', 'Programme')
    PartnerAdmin = apps.get_model('courses', 'PartnerAdmin')
    owners = Programme.objects.filter(is_active=True).values_list('organisation_id', flat=True)
    admins = (PartnerAdmin.objects.filter(role='org_admin', is_active=True)
              .values_list('owning_organisation_id', flat=True))
    return {pk for pk in list(owners) + list(admins) if pk is not None}


def mark_referral_partners(apps, schema_editor):
    PartnerOrganisation = apps.get_model('courses', 'PartnerOrganisation')
    PartnerAdmin = apps.get_model('courses', 'PartnerAdmin')
    ids = set(PartnerAdmin.objects.filter(role='partner', org__isnull=False)
              .values_list('org_id', flat=True))
    clash = ids & _tenant_ids(apps)
    if clash:
        raise RuntimeError(
            f'A tenant organisation carries a partner-role login (ids {sorted(clash)}); a tenant is '
            f'never a referral partner. Look before marking anything.')
    PartnerOrganisation.objects.filter(pk__in=ids).update(is_referral_partner=True)


def _snapshot_code(snapshot):
    profile = snapshot.get('profile') if isinstance(snapshot, dict) else None
    code = profile.get('referral_source') if isinstance(profile, dict) else None
    return code if isinstance(code, str) else ''


def backfill_two_columns(apps, schema_editor):
    PartnerOrganisation = apps.get_model('courses', 'PartnerOrganisation')
    StudentProfile = apps.get_model('courses', 'StudentProfile')
    ScholarshipApplication = apps.get_model('scholarship', 'ScholarshipApplication')

    sources = dict(PartnerOrganisation.objects.exclude(pk__in=_tenant_ids(apps))
                   .exclude(code__in=FIXED_CODES).values_list('code', 'pk'))
    latest = {}
    for profile_id, snapshot in (ScholarshipApplication.objects.filter(profile__isnull=False)
                                 .order_by('profile_id', '-id')
                                 .values_list('profile_id', 'intake_snapshot')):
        if profile_id not in latest:
            latest[profile_id] = sources.get(_snapshot_code(snapshot))
    by_source = {}
    for profile_id, source_id in latest.items():
        by_source.setdefault(source_id, []).append(profile_id)
    for source_id, profile_ids in by_source.items():
        StudentProfile.objects.filter(pk__in=profile_ids).update(source_id=source_id)

    partners = PartnerOrganisation.objects.filter(is_referral_partner=True).values('pk')
    (StudentProfile.objects.filter(referred_by_org__isnull=False)
     .exclude(referred_by_org_id__in=partners).update(referred_by_org=None))


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0077_retire_legacy_referral_codes'),
        ('scholarship', '0172_programme_referral_sources'),
    ]

    operations = [
        migrations.AddField(
            model_name='partnerorganisation',
            name='is_referral_partner',
            field=models.BooleanField(db_default=False, default=False, help_text='A PLATFORM referral partner: its ?ref= link fills a student\'s referred_by_org (owned by no organisation).'),
        ),
        migrations.AddField(
            model_name='studentprofile',
            name='source',
            field=models.ForeignKey(blank=True, help_text='The SOURCE the student named on the bursary form (NULL for a fixed choice). Independent of referred_by_org.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sourced_students', to='courses.partnerorganisation'),
        ),
        migrations.RunPython(mark_referral_partners, migrations.RunPython.noop),
        migrations.RunPython(backfill_two_columns, migrations.RunPython.noop),
    ]
