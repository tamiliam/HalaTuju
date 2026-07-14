# Platform Sprint 1 — seed BrightPath as organisation #1 and point every existing
# cohort at it. Purely additive/data; nothing reads owning_organisation yet, so this
# is behaviourally invisible (see docs/plans/2026-07-14-platform-roadmap-draft.md).
#
# Seed values are TODAY'S live constants, captured verbatim so the later branding
# extraction (platform Sprint 5/6) can render byte-identically from config:
#   programme names   — halatuju-web/src/messages/{en,ms,ta}.json "b40Heading"
#   persona           — "Cikgu Gopal" (all three locales use the same rendering)
#   team sign-off     — emails.py _REVIEWER_SIGNOFF ('The BrightPath Bursary Team')
#   sender identities — emails.py SUPPORT_EMAIL + settings DEFAULT_FROM_EMAIL
#   brand colour      — halatuju-web/tailwind.config.ts primary
#   module flags      — mirror today's GLOBAL env flags (unenforced until Sprint 10)
from django.db import migrations

BRIGHTPATH = {
    'name': 'BrightPath Bursary',
    'contact_email': 'help@halatuju.xyz',
    'is_active': True,
    'programme_name_en': 'BrightPath Bursary',
    'programme_name_ms': 'Bursari BrightPath',
    'programme_name_ta': 'BrightPath Bursary',
    'brand_colour': '#137fec',
    'persona_name_en': 'Cikgu Gopal',
    'persona_name_ms': 'Cikgu Gopal',
    'persona_name_ta': 'Cikgu Gopal',
    'team_signoff_en': 'The BrightPath Bursary Team',
    'email_from': 'info@halatuju.xyz',
    'email_reply_to': 'help@halatuju.xyz',
    'email_support': 'help@halatuju.xyz',
    'frontend_url': 'https://halatuju.xyz',
    'module_scholarship': True,
    'module_sponsor_pool': True,
    'module_comms_whatsapp': True,
    'module_payout': False,
}


def seed_brightpath(apps, schema_editor):
    PartnerOrganisation = apps.get_model('courses', 'PartnerOrganisation')
    ScholarshipCohort = apps.get_model('scholarship', 'ScholarshipCohort')
    org, _created = PartnerOrganisation.objects.get_or_create(
        code='brightpath', defaults=BRIGHTPATH,
    )
    ScholarshipCohort.objects.filter(owning_organisation__isnull=True).update(
        owning_organisation=org,
    )


def unseed_brightpath(apps, schema_editor):
    # Reverse: detach cohorts so the FK PROTECT can't block anything, but leave
    # the organisation row itself (harmless; deleting it could break referral
    # attribution if anything was pointed at it meanwhile).
    PartnerOrganisation = apps.get_model('courses', 'PartnerOrganisation')
    ScholarshipCohort = apps.get_model('scholarship', 'ScholarshipCohort')
    org = PartnerOrganisation.objects.filter(code='brightpath').first()
    if org is not None:
        ScholarshipCohort.objects.filter(owning_organisation=org).update(
            owning_organisation=None,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0097_scholarshipcohort_owning_organisation'),
        ('courses', '0061_partnerorganisation_brand_colour_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_brightpath, unseed_brightpath),
    ]
