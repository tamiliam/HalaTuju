# Platform Sprint 3a — bind every existing B40 STAFF admin to BrightPath (org #1).
# The access-control boundary for scholarship applications is
# PartnerAdmin.owning_organisation (NOT the referral `org`). On prod today every
# admin/reviewer/qc works the single BrightPath programme, so they all bind to it;
# `super` (global) and `partner` (no B40 access) stay NULL. Behaviourally invisible:
# with one org, org == org for every staff/application pair, so the Sprint-3a fence
# returns exactly today's rows. Idempotent + safe if BrightPath isn't seeded yet
# (then it no-ops and leaves NULLs — the deploy applies 0098's seed first anyway).
from django.db import migrations

_STAFF_ROLES = ('admin', 'reviewer', 'qc')


def bind_staff_to_brightpath(apps, schema_editor):
    PartnerAdmin = apps.get_model('courses', 'PartnerAdmin')
    PartnerOrganisation = apps.get_model('courses', 'PartnerOrganisation')
    org = PartnerOrganisation.objects.filter(code='brightpath').first()
    if org is None:
        return  # seed (0098) not applied in this DB — nothing to bind
    # Bind active B40 staff who aren't super. is_super_admin (legacy super) stays global
    # even if their role string is something else, so exclude it explicitly.
    (PartnerAdmin.objects
     .filter(role__in=_STAFF_ROLES, is_active=True, is_super_admin=False,
             owning_organisation__isnull=True)
     .update(owning_organisation=org))


def unbind_staff(apps, schema_editor):
    PartnerAdmin = apps.get_model('courses', 'PartnerAdmin')
    PartnerOrganisation = apps.get_model('courses', 'PartnerOrganisation')
    org = PartnerOrganisation.objects.filter(code='brightpath').first()
    if org is not None:
        PartnerAdmin.objects.filter(owning_organisation=org).update(owning_organisation=None)


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0062_partneradmin_owning_organisation'),
        ('scholarship', '0098_seed_brightpath_organisation'),
    ]

    operations = [
        migrations.RunPython(bind_staff_to_brightpath, unbind_staff),
    ]
