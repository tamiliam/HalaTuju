# Platform Sprint 2 — backfill every existing application's owning_organisation
# from its cohort (D-8: the cohort is the source of truth). Purely additive/data;
# nothing reads owning_organisation for authorisation yet (that is Sprint 3a), so
# this is behaviourally invisible. On prod every cohort is owned by BrightPath
# (seeded in 0098), so every application lands on BrightPath — 0 NULLs expected.
# In the test DB, bare-cohort fixtures may legitimately stay NULL (no org on the
# cohort); the Sprint-3a fence treats None as a safe degenerate bucket.
from django.db import migrations


def backfill_owning_org(apps, schema_editor):
    ScholarshipApplication = apps.get_model('scholarship', 'ScholarshipApplication')
    # Copy the FK id straight from the cohort in one UPDATE-per-row loop keyed on
    # the cohort's owning_organisation. select_related avoids an N+1 on the cohort.
    qs = (
        ScholarshipApplication.objects
        .filter(owning_organisation__isnull=True, cohort__owning_organisation__isnull=False)
        .select_related('cohort')
    )
    for app in qs.iterator():
        app.owning_organisation_id = app.cohort.owning_organisation_id
        app.save(update_fields=['owning_organisation'])


def unbackfill_owning_org(apps, schema_editor):
    # Reverse: detach the denormalised copy so the FK PROTECT can't block a
    # rollback of the schema migration. The cohort copy (source of truth) is left.
    ScholarshipApplication = apps.get_model('scholarship', 'ScholarshipApplication')
    ScholarshipApplication.objects.filter(owning_organisation__isnull=False).update(
        owning_organisation=None,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0099_application_owning_organisation'),
    ]

    operations = [
        migrations.RunPython(backfill_owning_org, unbackfill_owning_org),
    ]
