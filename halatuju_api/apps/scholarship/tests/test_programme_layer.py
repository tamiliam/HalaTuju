"""Platform programme layer — the durable gift level (2026-07-26).

Hierarchy: Organisation -> **Programme** -> Year (intake) -> the student's individual
award. The Programme IS the gift and never lapses; cohorts are its annual intakes.

These tests pin the structural half of the layer:
  * the model and its organisation link (PROTECT),
  * ``cohort.programme`` and the application's DENORMALISED copy derived in save(),
  * set-once semantics (a cohort move never silently re-homes existing applications),
  * the safe-NULL bucket for bare fixtures,
  * the seed/backfill migration's mechanism,
  * the drift invariant — an application's programme must belong to the same
    organisation the application is fenced to.

Mirrors ``test_application_owning_org.py``, which pins the same contract one level up.
"""
from django.db.models import F, ProtectedError
from django.test import TestCase

from apps.courses.models import PartnerOrganisation, StudentProfile
from apps.scholarship import services
from apps.scholarship.models import (
    Programme, ScholarshipApplication, ScholarshipCohort,
)


def _org(code='tenant-a'):
    # NB: never 'brightpath' — migration 0098 already seeds that org into the test DB.
    return PartnerOrganisation.objects.create(code=code, name=code.title())


def _programme(org=None, code='p-flagship', **kw):
    return Programme.objects.create(
        organisation=org or _org(), code=code,
        name_en=kw.pop('name_en', 'Test Bursary'), **kw,
    )


def _cohort(org=None, programme=None, code='c-2026', **kw):
    return ScholarshipCohort.objects.create(
        code=code, name='Test Cohort', year=2026,
        owning_organisation=org, programme=programme, **kw,
    )


def _profile(uid='u-1'):
    return StudentProfile.objects.create(supabase_user_id=uid, name='Test Student')


class TestProgrammeModel(TestCase):
    def test_belongs_to_an_organisation(self):
        org = _org()
        prog = _programme(org)
        self.assertEqual(prog.organisation_id, org.id)
        self.assertIn(prog, org.programmes.all())

    def test_code_is_unique(self):
        from django.db import IntegrityError, transaction
        _programme(code='dup')
        with self.assertRaises(IntegrityError), transaction.atomic():
            _programme(code='dup')

    def test_blank_ms_ta_are_allowed(self):
        """A tenant may supply English only; ms/ta fall back at render time."""
        prog = _programme()
        self.assertEqual(prog.name_ms, '')
        self.assertEqual(prog.name_ta, '')

    def test_one_organisation_may_run_several_programmes(self):
        """The BrightPath Sabah case: a sibling gift under the SAME organisation."""
        org = _org()
        flagship = _programme(org, code='bp-flagship', name_en='BrightPath Bursary')
        sabah = _programme(org, code='bp-sabah', name_en='BrightPath Sabah Bursary')
        self.assertEqual(org.programmes.count(), 2)
        self.assertNotEqual(flagship.id, sabah.id)


class TestProgrammeDerivation(TestCase):
    def test_derives_from_cohort_on_direct_create(self):
        org = _org()
        prog = _programme(org)
        app = ScholarshipApplication.objects.create(
            cohort=_cohort(org, prog), profile=_profile(),
        )
        self.assertEqual(app.programme_id, prog.id)

    def test_derives_via_real_service_path(self):
        """The production creator — services.create_application — must set it."""
        org = _org()
        prog = _programme(org)
        cohort = _cohort(org, prog, is_active=True, is_open=True)
        app = services.create_application(
            profile=_profile(), cohort=cohort, validated_data={},
            to_email='student@example.com', lang='en',
        )
        self.assertEqual(app.programme_id, prog.id)

    def test_bare_cohort_stays_none_no_crash(self):
        """A fixture cohort with no programme → app.programme is NULL, no crash."""
        app = ScholarshipApplication.objects.create(
            cohort=_cohort(org=None, programme=None), profile=_profile(),
        )
        self.assertIsNone(app.programme_id)

    def test_derives_when_cohort_relation_not_cached(self):
        """The uncached branch (a single values_list lookup) must set BOTH copies."""
        org = _org()
        prog = _programme(org)
        cohort = _cohort(org, prog)
        app = ScholarshipApplication(cohort_id=cohort.id, profile=_profile())
        self.assertIsNone(app._state.fields_cache.get('cohort'))
        app.save()
        app.refresh_from_db()
        self.assertEqual(app.programme_id, prog.id)
        self.assertEqual(app.owning_organisation_id, org.id)

    def test_org_and_programme_both_derived_together(self):
        """The two denormalised copies are set in one pass — neither is dropped."""
        org = _org()
        prog = _programme(org)
        app = ScholarshipApplication.objects.create(
            cohort=_cohort(org, prog), profile=_profile(),
        )
        self.assertEqual(app.owning_organisation_id, org.id)
        self.assertEqual(app.programme_id, prog.id)

    def test_set_once_not_overwritten_on_resave(self):
        """Once set, a later save never re-derives — a cohort moved to a different
        gift must NOT silently re-home an existing application (its money and its
        sponsor relationships already hang off the original programme)."""
        org = _org()
        prog_a = _programme(org, code='p-a')
        prog_b = _programme(org, code='p-b')
        cohort = _cohort(org, prog_a)
        app = ScholarshipApplication.objects.create(cohort=cohort, profile=_profile())
        self.assertEqual(app.programme_id, prog_a.id)

        cohort.programme = prog_b
        cohort.save(update_fields=['programme'])
        app.save()
        app.refresh_from_db()
        self.assertEqual(app.programme_id, prog_a.id)


class TestBackfillMechanism(TestCase):
    """The shape of migration 0119's backfill, exercised against live models."""

    def test_backfill_points_orphan_rows_at_the_org_programme(self):
        org = _org()
        prog = _programme(org)
        cohort = _cohort(org, programme=None)
        app = ScholarshipApplication.objects.create(cohort=cohort, profile=_profile())
        self.assertIsNone(app.programme_id)

        ScholarshipCohort.objects.filter(
            owning_organisation=org, programme__isnull=True,
        ).update(programme=prog)
        cohort_ids = list(
            ScholarshipCohort.objects.filter(programme=prog).values_list('id', flat=True)
        )
        ScholarshipApplication.objects.filter(
            cohort_id__in=cohort_ids, programme__isnull=True,
        ).update(programme=prog)

        app.refresh_from_db()
        cohort.refresh_from_db()
        self.assertEqual(cohort.programme_id, prog.id)
        self.assertEqual(app.programme_id, prog.id)

    def test_backfill_is_idempotent(self):
        """Re-running must not move a row that already has a programme."""
        org = _org()
        prog_a = _programme(org, code='p-a')
        prog_b = _programme(org, code='p-b')
        cohort = _cohort(org, prog_a)
        ScholarshipCohort.objects.filter(
            owning_organisation=org, programme__isnull=True,
        ).update(programme=prog_b)
        cohort.refresh_from_db()
        self.assertEqual(cohort.programme_id, prog_a.id)


class TestDriftInvariant(TestCase):
    def test_application_programme_belongs_to_its_owning_org(self):
        """The invariant the fence depends on: an application's programme must be run
        by the organisation the application is fenced to. There is no DB trigger —
        this test is the guard (same contract as the owning-org drift test)."""
        org = _org()
        prog = _programme(org)
        ScholarshipApplication.objects.create(
            cohort=_cohort(org, prog), profile=_profile(),
        )
        mismatched = (
            ScholarshipApplication.objects
            .filter(programme__isnull=False, owning_organisation__isnull=False)
            .exclude(programme__organisation_id=F('owning_organisation_id'))
        )
        self.assertEqual(list(mismatched), [])

    def test_cohort_programme_belongs_to_its_owning_org(self):
        org = _org()
        prog = _programme(org)
        _cohort(org, prog)
        mismatched = (
            ScholarshipCohort.objects
            .filter(programme__isnull=False, owning_organisation__isnull=False)
            .exclude(programme__organisation_id=F('owning_organisation_id'))
        )
        self.assertEqual(list(mismatched), [])


class TestProtect(TestCase):
    def test_programme_in_use_cannot_be_deleted(self):
        """PROTECT: a gift with intakes beneath it can't be deleted out from under
        them (D-5 suspend-never-delete — deactivate instead)."""
        org = _org()
        prog = _programme(org)
        _cohort(org, prog)
        with self.assertRaises(ProtectedError):
            prog.delete()

    def test_organisation_running_a_programme_cannot_be_deleted(self):
        org = _org()
        _programme(org)
        with self.assertRaises(ProtectedError):
            org.delete()
