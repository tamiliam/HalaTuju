"""Reviewer-query automation S2 — stale income doc + sibling-in-tertiary funding.

Two more deterministic auto-queries reviewers raise by hand: ask for a CURRENT salary slip
when every one on file is older than ~3 months, and ask which institution a tertiary sibling
attends + how they're funded. (The high-utility probe was moved to the interview layer (S4) —
the codebase treats high utility as an officer-only signal, never a student query.)
"""
import datetime

from django.test import TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship import income_engine
from apps.scholarship.check2_queries import sync_check2_queries
from apps.scholarship.models import (
    ApplicantDocument, ScholarshipApplication, ScholarshipCohort,
)

TODAY = datetime.date(2026, 6, 29)


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def _app(self, suffix='1', **kw):
        p = StudentProfile.objects.create(
            supabase_user_id=f's2-{suffix}', name='Anbu A/L Raj', nric='030101-14-1234',
            household_income=1500, household_size=5)
        # Default: father earns + mother homemaker so the S1 parent gaps don't fire.
        defaults = dict(cohort=self.cohort, profile=p, status='profile_complete',
                        profile_completed_at=timezone.now(),
                        father_occupation='gov', mother_occupation='homemaker',
                        siblings_in_tertiary=0)
        defaults.update(kw)
        return ScholarshipApplication.objects.create(**defaults)

    def _slip(self, app, period, member='father'):
        return ApplicantDocument.objects.create(
            application=app, doc_type='salary_slip', household_member=member,
            storage_path=f'x/{period}', vision_fields={'fields': {'period': period}})


class TestStaleIncomeProof(_Base):
    def test_stale_when_only_old_slip(self):
        app = self._app('a')
        self._slip(app, 'December 2025')              # ~6 months before TODAY
        self.assertTrue(income_engine.stale_income_proof(app, today=TODAY))

    def test_current_slip_is_not_stale(self):
        app = self._app('b')
        self._slip(app, 'May 2026')                  # 1 month before TODAY
        self.assertFalse(income_engine.stale_income_proof(app, today=TODAY))

    def test_freshest_slip_decides(self):
        app = self._app('c')
        self._slip(app, 'December 2025')
        self._slip(app, 'June 2026')                 # a current one exists → not stale
        self.assertFalse(income_engine.stale_income_proof(app, today=TODAY))

    def test_no_slip_is_not_stale(self):
        app = self._app('d')
        self.assertFalse(income_engine.stale_income_proof(app, today=TODAY))

    def test_unreadable_period_is_not_stale(self):
        app = self._app('e')
        self._slip(app, '')                          # no readable period → don't guess
        self.assertFalse(income_engine.stale_income_proof(app, today=TODAY))


class TestSiblingTertiary(_Base):
    def test_flag_on_tertiary_sibling(self):
        app = self._app('f', siblings_in_tertiary=1)
        self.assertTrue(income_engine.sibling_tertiary_funding_unknown(app))

    def test_no_flag_without_tertiary_sibling(self):
        app = self._app('g', siblings_in_tertiary=0)
        self.assertFalse(income_engine.sibling_tertiary_funding_unknown(app))


class TestCheck2Integration(_Base):
    def _codes(self, app):
        return {r.code: r for r in app.resolution_items.filter(source='check2', status='open')}

    def test_stale_slip_raises_doc(self):
        app = self._app('h')
        self._slip(app, 'December 2025')
        sync_check2_queries(app)
        items = self._codes(app)
        self.assertIn('income_doc_stale', items)
        self.assertEqual(items['income_doc_stale'].kind, 'doc')

    def test_stale_resolves_when_current_slip_arrives(self):
        app = self._app('i')
        self._slip(app, 'December 2025')
        sync_check2_queries(app)
        self.assertIn('income_doc_stale', self._codes(app))
        self._slip(app, 'June 2026')                 # current slip uploaded
        sync_check2_queries(app)
        self.assertNotIn('income_doc_stale', self._codes(app))

    def test_sibling_tertiary_raises_clarify(self):
        app = self._app('j', siblings_in_tertiary=2)
        sync_check2_queries(app)
        items = self._codes(app)
        self.assertIn('sibling_tertiary_funding', items)
        self.assertEqual(items['sibling_tertiary_funding'].kind, 'clarify')

    def test_nothing_when_clean(self):
        app = self._app('k')                         # current household, no tertiary sibling
        self._slip(app, 'June 2026')
        sync_check2_queries(app)
        codes = set(self._codes(app))
        self.assertNotIn('income_doc_stale', codes)
        self.assertNotIn('sibling_tertiary_funding', codes)
