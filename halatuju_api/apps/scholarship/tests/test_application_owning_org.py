"""Platform Sprint 2 — the application's denormalised owning organisation.

`ScholarshipApplication.owning_organisation` is a copy of `cohort.owning_organisation`
(D-8), derived in `save()` so the Sprint-3a admin fence can partition cheaply. These
tests pin the derivation (real service path + direct create), the safe-NULL semantics
for bare-cohort fixtures, the backfill mechanism, the drift invariant, and PROTECT.
"""
from django.db.models import ProtectedError
from django.test import TestCase

from apps.courses.models import PartnerOrganisation, StudentProfile
from apps.scholarship import services
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort


def _org(code='tenant-a'):
    # NB: never 'brightpath' — migration 0098 already seeds that org into the test DB.
    return PartnerOrganisation.objects.create(code=code, name=code.title())


def _cohort(org=None, code='c-2026', **kw):
    return ScholarshipCohort.objects.create(
        code=code, name='Test Cohort', year=2026, owning_organisation=org, **kw,
    )


def _profile(uid='u-1'):
    return StudentProfile.objects.create(supabase_user_id=uid, name='Test Student')


class TestOwningOrgDerivation(TestCase):
    def test_derives_from_cohort_on_direct_create(self):
        org = _org()
        app = ScholarshipApplication.objects.create(cohort=_cohort(org), profile=_profile())
        self.assertEqual(app.owning_organisation_id, org.id)

    def test_derives_via_real_service_path(self):
        """The production creator — services.create_application — must set it."""
        org = _org()
        cohort = _cohort(org, is_active=True, is_open=True)
        profile = _profile()
        app = services.create_application(
            profile=profile, cohort=cohort, validated_data={},
            to_email='student@example.com', lang='en',
        )
        self.assertEqual(app.owning_organisation_id, org.id)

    def test_bare_cohort_stays_none_no_crash(self):
        """A fixture cohort with no owning_organisation → app.owning_organisation is
        NULL (the safe degenerate bucket the fence treats as its own partition)."""
        app = ScholarshipApplication.objects.create(cohort=_cohort(org=None), profile=_profile())
        self.assertIsNone(app.owning_organisation_id)

    def test_set_once_not_overwritten_on_resave(self):
        """Once set, a later save (e.g. a status change) never re-derives/overwrites."""
        org_a, org_b = _org('a'), _org('b')
        cohort = _cohort(org_a)
        app = ScholarshipApplication.objects.create(cohort=cohort, profile=_profile())
        self.assertEqual(app.owning_organisation_id, org_a.id)
        # Point the cohort at a different org, then save the app again: the app keeps
        # its original owning org (set-once; a real move must cascade explicitly).
        cohort.owning_organisation = org_b
        cohort.save(update_fields=['owning_organisation'])
        app.status = 'shortlisted'
        app.save(update_fields=['status'])
        app.refresh_from_db()
        self.assertEqual(app.owning_organisation_id, org_a.id)

    def test_derivation_uses_no_extra_query_when_cohort_loaded(self):
        """Passing a loaded cohort instance derives from the field cache, not a query."""
        org = _org()
        cohort = _cohort(org)
        profile = _profile()
        with self.assertNumQueries(1):  # the app INSERT only — no cohort re-fetch
            ScholarshipApplication.objects.create(cohort=cohort, profile=profile)


class TestBackfillMechanism(TestCase):
    def test_null_owning_org_heals_on_save(self):
        """The backfill migration relies on re-deriving a NULL from the cohort. Force a
        NULL (as a legacy row would be), then confirm a save re-derives it."""
        org = _org()
        app = ScholarshipApplication.objects.create(cohort=_cohort(org), profile=_profile())
        # Simulate a legacy pre-Sprint-2 row: NULL in the DB, bypassing save().
        ScholarshipApplication.objects.filter(pk=app.pk).update(owning_organisation=None)
        app.refresh_from_db()
        self.assertIsNone(app.owning_organisation_id)
        app.save()  # save() sees None + a cohort → re-derives
        app.refresh_from_db()
        self.assertEqual(app.owning_organisation_id, org.id)

    def test_backfill_query_fills_every_row_with_an_owned_cohort(self):
        """Mirror the migration's own query: every application whose cohort has an org
        ends up owned; a bare-cohort app is left NULL."""
        org = _org()
        owned = ScholarshipApplication.objects.create(cohort=_cohort(org, code='owned'), profile=_profile('u-o'))
        bare = ScholarshipApplication.objects.create(cohort=_cohort(None, code='bare'), profile=_profile('u-b'))
        # Force both to NULL to imitate the pre-migration state.
        ScholarshipApplication.objects.update(owning_organisation=None)
        # Apply the migration's exact backfill logic.
        for a in ScholarshipApplication.objects.filter(
            owning_organisation__isnull=True, cohort__owning_organisation__isnull=False,
        ).select_related('cohort'):
            a.owning_organisation_id = a.cohort.owning_organisation_id
            a.save(update_fields=['owning_organisation'])
        owned.refresh_from_db(); bare.refresh_from_db()
        self.assertEqual(owned.owning_organisation_id, org.id)
        self.assertIsNone(bare.owning_organisation_id)
        # 0 NULLs remain among applications whose cohort carries an org.
        self.assertEqual(
            ScholarshipApplication.objects.filter(
                owning_organisation__isnull=True,
                cohort__owning_organisation__isnull=False,
            ).count(),
            0,
        )


class TestDriftInvariant(TestCase):
    def test_app_org_equals_cohort_org(self):
        """The load-bearing invariant the fence assumes: an application's owning org
        equals its cohort's owning org (unless a move drifted them — guarded here)."""
        org = _org()
        app = ScholarshipApplication.objects.create(cohort=_cohort(org), profile=_profile())
        self.assertEqual(app.owning_organisation_id, app.cohort.owning_organisation_id)

    def test_invariant_holds_after_backfill(self):
        org = _org()
        app = ScholarshipApplication.objects.create(cohort=_cohort(org), profile=_profile())
        ScholarshipApplication.objects.filter(pk=app.pk).update(owning_organisation=None)
        app.refresh_from_db()
        app.save()
        app.refresh_from_db()
        self.assertEqual(app.owning_organisation_id, app.cohort.owning_organisation_id)


class TestProtect(TestCase):
    def test_org_delete_protected_by_owning_application(self):
        """PROTECT: an organisation that owns an application cannot be deleted out from
        under it (mirrors the cohort FK)."""
        org = _org()
        ScholarshipApplication.objects.create(cohort=_cohort(org), profile=_profile())
        with self.assertRaises(ProtectedError):
            org.delete()
