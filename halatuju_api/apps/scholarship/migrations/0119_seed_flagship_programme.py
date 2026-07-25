# Platform programme layer — seed the flagship Programme and backfill (2026-07-26).
#
# Companion data migration to 0118. Creates Programme #1 ("BrightPath Bursary") under
# the organisation seeded by 0098, then points every orphan cohort and every orphan
# application at the programme its organisation runs.
#
# Behaviourally invisible: nothing reads `programme` yet (the read seams — routing,
# funds, sponsor membership — land in later sprints), and with one organisation and
# one cohort every row lands in the same place.
#
# Naming: the Programme IS the gift (owner ruling, decisions.md "One gift per
# Programme", 2026-07-26). `name_en` is today's live programme name captured verbatim
# from the organisation's own branding columns, so a future branding read seam renders
# byte-identically. The code is 'brightpath-flagship' rather than 'brightpath' — the
# organisation already owns that slug, and BrightPath Sabah will be a SIBLING programme
# under the same organisation.
from django.db import migrations

FLAGSHIP_CODE = 'brightpath-flagship'
PLATFORM_ORG_CODE = 'brightpath'


def seed_flagship_programme(apps, schema_editor):
    PartnerOrganisation = apps.get_model('courses', 'PartnerOrganisation')
    Programme = apps.get_model('scholarship', 'Programme')
    ScholarshipCohort = apps.get_model('scholarship', 'ScholarshipCohort')
    ScholarshipApplication = apps.get_model('scholarship', 'ScholarshipApplication')

    org = PartnerOrganisation.objects.filter(code=PLATFORM_ORG_CODE).first()
    if org is None:
        # No platform organisation (a bare/partial test DB) — nothing to hang a
        # programme off. Leave the tables empty rather than inventing an org.
        return

    programme, _created = Programme.objects.get_or_create(
        code=FLAGSHIP_CODE,
        defaults={
            'organisation': org,
            # Verbatim from the org's seeded branding (0098) so nothing re-words.
            'name_en': org.programme_name_en or 'BrightPath Bursary',
            'name_ms': org.programme_name_ms or '',
            'name_ta': org.programme_name_ta or '',
            'is_active': True,
        },
    )

    # Every cohort already owned by this organisation belongs to its one gift.
    ScholarshipCohort.objects.filter(
        owning_organisation=org, programme__isnull=True,
    ).update(programme=programme)

    # Backfill the denormalised copy on applications. Driven off the COHORT (the source
    # of truth) rather than the application's own owning_organisation, so an application
    # whose org copy ever drifted cannot pull its programme out of alignment.
    cohort_ids = list(
        ScholarshipCohort.objects.filter(programme=programme).values_list('id', flat=True)
    )
    if cohort_ids:
        ScholarshipApplication.objects.filter(
            cohort_id__in=cohort_ids, programme__isnull=True,
        ).update(programme=programme)


def unseed_flagship_programme(apps, schema_editor):
    # Reverse: detach the pointers so the FK PROTECT can't block, then drop the
    # programme row itself (unlike 0098's organisation, this row is new here and
    # nothing outside this layer attributes to it).
    Programme = apps.get_model('scholarship', 'Programme')
    ScholarshipCohort = apps.get_model('scholarship', 'ScholarshipCohort')
    ScholarshipApplication = apps.get_model('scholarship', 'ScholarshipApplication')

    programme = Programme.objects.filter(code=FLAGSHIP_CODE).first()
    if programme is None:
        return
    ScholarshipApplication.objects.filter(programme=programme).update(programme=None)
    ScholarshipCohort.objects.filter(programme=programme).update(programme=None)
    programme.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0118_programme_layer'),
        ('courses', '0066_alter_partneradmin_role'),
    ]

    operations = [
        migrations.RunPython(seed_flagship_programme, unseed_flagship_programme),
    ]
