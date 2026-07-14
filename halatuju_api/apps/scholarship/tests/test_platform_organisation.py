"""Platform Sprint 1 — Organisation record + BrightPath as org #1.

Everything here is INVISIBLE behaviour: the new columns/FK are written and seeded
but not read anywhere yet. These tests pin (a) the seed, (b) the defaults that keep
the referral role unaffected, and (c) the ownership FK semantics the later fencing
sprints build on.
"""
import pytest
from django.apps import apps as live_apps
from django.db.models.deletion import ProtectedError

from apps.courses.models import PartnerOrganisation
from apps.scholarship.models import ScholarshipCohort

pytestmark = pytest.mark.django_db


def _seed(apps=live_apps):
    """Run the 0098 seed function against the live registry (idempotent)."""
    from importlib import import_module
    mod = import_module('apps.scholarship.migrations.0098_seed_brightpath_organisation')
    mod.seed_brightpath(apps, None)
    return mod


class TestBrightPathSeed:
    def test_brightpath_org_seeded_by_migration(self):
        """The test DB is built by running migrations, so org #1 must exist."""
        org = PartnerOrganisation.objects.get(code='brightpath')
        assert org.name == 'BrightPath Bursary'
        assert org.programme_name_en == 'BrightPath Bursary'
        assert org.programme_name_ms == 'Bursari BrightPath'
        assert org.programme_name_ta == 'BrightPath Bursary'
        assert org.persona_name_en == 'Cikgu Gopal'
        assert org.brand_colour == '#137fec'
        assert org.email_support == 'help@halatuju.xyz'
        assert org.frontend_url == 'https://halatuju.xyz'
        assert org.is_active is True
        # Module flags mirror today's global env flags (unenforced until Sprint 10)
        assert org.module_scholarship is True
        assert org.module_sponsor_pool is True
        assert org.module_comms_whatsapp is True
        assert org.module_payout is False

    def test_seed_is_idempotent(self):
        _seed()
        _seed()
        assert PartnerOrganisation.objects.filter(code='brightpath').count() == 1

    def test_seed_backfills_unowned_cohorts_only(self):
        org = PartnerOrganisation.objects.get(code='brightpath')
        other = PartnerOrganisation.objects.create(code='fixture-org-2', name='Fixture Org 2')
        unowned = ScholarshipCohort.objects.create(code='c-unowned', name='U', year=2026)
        owned = ScholarshipCohort.objects.create(
            code='c-owned', name='O', year=2026, owning_organisation=other,
        )
        _seed()
        unowned.refresh_from_db()
        owned.refresh_from_db()
        assert unowned.owning_organisation_id == org.id     # NULL → backfilled to org #1
        assert owned.owning_organisation_id == other.id     # already owned → untouched


class TestReferralRoleUnaffected:
    def test_new_referral_org_gets_neutral_defaults(self):
        """A plain referral partner (the original role) must not look like a tenant."""
        org = PartnerOrganisation.objects.create(code='roadshow-x', name='Roadshow X')
        assert org.programme_name_en == ''
        assert org.brand_colour == ''
        assert org.email_from == ''
        assert org.module_scholarship is False
        assert org.module_sponsor_pool is False
        assert org.module_comms_whatsapp is False
        assert org.module_payout is False


class TestCohortOwnership:
    def test_cohort_ownership_settable_and_related_name(self):
        org = PartnerOrganisation.objects.get(code='brightpath')
        cohort = ScholarshipCohort.objects.create(
            code='b40-test', name='Test', year=2026, owning_organisation=org,
        )
        assert cohort in org.owned_cohorts.all()

    def test_owning_org_is_delete_protected(self):
        """PROTECT: a tenant with cohorts can never be deleted (D-5 suspend-not-delete)."""
        org = PartnerOrganisation.objects.create(code='tenant-y', name='Tenant Y')
        ScholarshipCohort.objects.create(
            code='c-y', name='Y', year=2026, owning_organisation=org,
        )
        with pytest.raises(ProtectedError):
            org.delete()
