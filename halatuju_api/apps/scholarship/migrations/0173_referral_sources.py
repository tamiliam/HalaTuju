"""Sources and referral partners, Sprint B (owner's model, 2026-10-09; built 2026-10-18): a SOURCE
becomes its own record, owned by the organisation that added it.

SCHEMA (expand — safe for the image still serving):
- NEW table `referral_sources` (`ReferralSource`): organisation FK → `partner_organisations`
  (PROTECT), code, name, contact person / email / phone, show_in_apply, is_active, created_at;
  UNIQUE (organisation, code). RLS on (event trigger) + a `service_role` policy (cutover SQL).
- FOUR foreign keys move from `partner_organisations` to `referral_sources` by a CONSTRAINT SWAP —
  the column, its name and every value stay as they are, because the rows were copied with their
  ids: `programme_referral_sources.source_id`, `scholarship_applications.witness_org_id`,
  `bursary_agreements.witness_org_id`, `partner_email_log.organisation_id`. (The fifth,
  `api_student_profiles.source_id`, is the courses app's — courses 0079, same swap.)

DATA:
1. `copy_sources` — every `partner_organisations` row that is NOT a tenant (the historical spelling
   of `tenants()`: owns an active programme or has an active org_admin) and does not carry one of
   the three fixed form codes is copied, KEEPING ITS ID, and is owned by THE tenant. Derived, never
   a literal: it refuses (RuntimeError) when there are rows to copy and not exactly one tenant —
   two tenants would need a human to say whose each source is. Production (lead, 2026-10-18): one
   tenant, `brightpath`; sources cumig, ewrf, hss, hyo, mhm, pptm, smc, muet, learnifi, pacos,
   rckk, sathya_sai, tara — RE-READ at the cutover. CUMIG is BOTH a source and the referral
   partner: its source row is copied here (owned by BrightPath); its referral-partner row stays on
   `partner_organisations`, unowned, with its two logins, its `?ref=cumig` link and its students.
   On PostgreSQL the id sequence is then set past the highest id of EITHER table, so a source
   created afterwards never takes an id some `partner_organisations` row already has.
2. `refuse_dangling_references` — every value in the five columns above must name a copied row;
   otherwise RuntimeError, naming the column and the ids. Never silently cleared: a witness on a
   house or tenant row is a question for the owner (cutover pre-check 5).

Idempotent: a second run copies nothing new. Reverse: the constraint swaps reverse; the copied
rows go with the table.

⚠ MIGRATE-FIRST, BY HAND, with `docs/scholarship/sources-b-cutover-sql.md` (DDL rendered offline
with Django's postgresql schema editor, `SET CONSTRAINTS ALL IMMEDIATE` after the seed, asserting
DO blocks, the ledger rows for scholarship 0173 AND courses 0079 in the same transaction).
"""
import django.db.models.deletion
from django.db import migrations, models

#: The three fixed choices on every apply form — a copy, on purpose: a migration must not import app
#: code that may change after it is written (`apps.scholarship.gift_sources.FIXED_CODES`).
FIXED_CODES = ('halatuju', 'social', 'other')


def _tenant_ids(apps):
    """`PartnerOrganisation.objects.tenants()`, spelt out for the historical models."""
    Programme = apps.get_model('scholarship', 'Programme')
    PartnerAdmin = apps.get_model('courses', 'PartnerAdmin')
    owners = Programme.objects.filter(is_active=True).values_list('organisation_id', flat=True)
    admins = (PartnerAdmin.objects.filter(role='org_admin', is_active=True)
              .values_list('owning_organisation_id', flat=True))
    return {pk for pk in list(owners) + list(admins) if pk is not None}


#: The fields a source keeps, copied verbatim from its `partner_organisations` row.
COPIED_FIELDS = ('code', 'name', 'contact_person', 'contact_email', 'phone', 'show_in_apply',
                 'is_active', 'created_at')


def copy_sources(apps, schema_editor):
    PartnerOrganisation = apps.get_model('courses', 'PartnerOrganisation')
    ReferralSource = apps.get_model('scholarship', 'ReferralSource')
    tenants = _tenant_ids(apps)
    rows = list(PartnerOrganisation.objects.exclude(pk__in=tenants)
                .exclude(code__in=FIXED_CODES).order_by('pk'))
    if not rows:
        return
    if len(tenants) != 1:
        raise RuntimeError(
            f'{len(rows)} source row(s) to copy but {len(tenants)} tenant organisation(s) '
            f'(ids {sorted(tenants)}): whose is each source? A person must decide — nothing copied.')
    owner_id = next(iter(tenants))
    have = set(ReferralSource.objects.values_list('pk', flat=True))
    ReferralSource.objects.bulk_create([
        ReferralSource(pk=row.pk, organisation_id=owner_id,
                       **{f: getattr(row, f) for f in COPIED_FIELDS})
        for row in rows if row.pk not in have])
    # `created_at` is auto_now_add: bulk_create stamped "now". Put each row's real date back.
    for row in rows:
        ReferralSource.objects.filter(pk=row.pk).update(created_at=row.created_at)
    if schema_editor.connection.vendor == 'postgresql':
        with schema_editor.connection.cursor() as cur:
            cur.execute(
                "SELECT setval(pg_get_serial_sequence('referral_sources', 'id'), GREATEST("
                "(SELECT COALESCE(MAX(id), 1) FROM referral_sources), "
                "(SELECT COALESCE(MAX(id), 1) FROM partner_organisations)))")
            # The seed queued deferred FK checks; adding the constraints below needs them settled.
            cur.execute('SET CONSTRAINTS ALL IMMEDIATE')


#: (app, model, field) — every column that named a source on `partner_organisations`.
REFERENCING = (
    ('scholarship', 'ProgrammeReferralSource', 'source_id'),
    ('scholarship', 'ScholarshipApplication', 'witness_org_id'),
    ('scholarship', 'BursaryAgreement', 'witness_org_id'),
    ('scholarship', 'PartnerEmailLog', 'organisation_id'),
    ('courses', 'StudentProfile', 'source_id'),
)


def refuse_dangling_references(apps, schema_editor):
    copied = set(apps.get_model('scholarship', 'ReferralSource').objects
                 .values_list('pk', flat=True))
    problems = []
    for app_label, model_name, column in REFERENCING:
        model = apps.get_model(app_label, model_name)
        ids = set(model.objects.filter(**{f'{column}__isnull': False})
                  .values_list(column, flat=True).distinct())
        if ids - copied:
            problems.append(f'{model._meta.db_table}.{column} -> {sorted(ids - copied)}')
    if problems:
        raise RuntimeError(
            'These columns name an organisation that is not a source (a tenant, or a row carrying a '
            'fixed code), so it has no row in referral_sources: ' + '; '.join(problems)
            + '. Nothing is cleared silently — ask the owner what each should name.')


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0078_two_referral_columns'),
        ('scholarship', '0172_programme_referral_sources'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReferralSource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(help_text='Slug, unique within the organisation: smc', max_length=50)),
                ('name', models.CharField(max_length=200)),
                ('contact_person', models.CharField(blank=True, default='', max_length=200)),
                ('contact_email', models.EmailField(blank=True, default='', max_length=254)),
                ('phone', models.CharField(blank=True, default='', max_length=30)),
                ('show_in_apply', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('organisation', models.ForeignKey(help_text='The organisation (tenant) that added this source and alone may see or edit it.', on_delete=django.db.models.deletion.PROTECT, related_name='owned_sources', to='courses.partnerorganisation')),
            ],
            options={
                'db_table': 'referral_sources',
                'ordering': ['name'],
                'constraints': [models.UniqueConstraint(fields=('organisation', 'code'), name='uniq_referral_source_org_code')],
            },
        ),
        migrations.RunPython(copy_sources, migrations.RunPython.noop),
        migrations.RunPython(refuse_dangling_references, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='programmereferralsource',
            name='source',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gift_links', to='scholarship.referralsource'),
        ),
        migrations.AlterField(
            model_name='scholarshipapplication',
            name='witness_org',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='scholarship.referralsource'),
        ),
        migrations.AlterField(
            model_name='bursaryagreement',
            name='witness_org',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='scholarship.referralsource'),
        ),
        migrations.AlterField(
            model_name='partneremaillog',
            name='organisation',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='partner_email_log', to='scholarship.referralsource'),
        ),
    ]
