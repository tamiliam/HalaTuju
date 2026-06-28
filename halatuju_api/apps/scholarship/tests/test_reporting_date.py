"""Reviewer-query S3 — offer reporting-date: normalise + persist + the missing-date clarify."""
import datetime

from django.test import TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship import pathway_engine as pe
from apps.scholarship.check2_queries import sync_check2_queries
from apps.scholarship.models import (
    ApplicantDocument, ScholarshipApplication, ScholarshipCohort,
)


class TestParseReportingDate(TestCase):
    def test_formats(self):
        cases = {
            '8 JUN 2026': datetime.date(2026, 6, 8),
            '08 Jun 2026': datetime.date(2026, 6, 8),
            '08 Jun 2026 (Isnin)': datetime.date(2026, 6, 8),
            '8 HINGGA 9 JUN 2026': datetime.date(2026, 6, 8),
            '22 JUN 2026 (9.00 PAGI - 2.00 PETANG)': datetime.date(2026, 6, 22),
            '20 JULAI 2026': datetime.date(2026, 7, 20),
            '10 OGOS 2026': datetime.date(2026, 8, 10),
            '28 JULAI 2024 2:30 PETANG': datetime.date(2024, 7, 28),
            '10 August 2026': datetime.date(2026, 8, 10),
        }
        for raw, want in cases.items():
            self.assertEqual(pe.parse_reporting_date(raw), want, raw)

    def test_unparseable(self):
        for raw in ('', None, 'to be advised', 'June', '2026', 'soon'):
            self.assertIsNone(pe.parse_reporting_date(raw))


class _OfferBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def _app(self, suffix='1', **kw):
        p = StudentProfile.objects.create(
            supabase_user_id=f'rd-{suffix}', name='Anbu A/L Raj', nric='030101-14-1234',
            household_income=1500, household_size=5)
        defaults = dict(cohort=self.cohort, profile=p, status='shortlisted',
                        profile_completed_at=timezone.now(),
                        father_occupation='gov', mother_occupation='homemaker')
        defaults.update(kw)
        return ScholarshipApplication.objects.create(**defaults)

    def _offer(self, app, reporting_date='8 JUN 2026', read=True, programme='Diploma Kejuruteraan'):
        fields = {'reporting_date': reporting_date, 'candidate_name': 'Anbu A/L Raj',
                  'programme': programme, 'institution': 'Politeknik Test'}
        vf = {'fields': fields}
        if read:
            vf['student_verdict'] = 'ok'           # extracted → name/ic not 'pending'
        return ApplicantDocument.objects.create(
            application=app, doc_type='offer_letter', storage_path='x/offer', vision_fields=vf)


class TestOfferReportingDate(_OfferBase):
    def test_offer_reporting_date_parsed(self):
        app = self._app('a')
        self._offer(app, '20 JULAI 2026')
        self.assertEqual(pe.offer_reporting_date(app), datetime.date(2026, 7, 20))

    def test_unknown_when_no_date_on_readable_offer(self):
        app = self._app('b')
        self._offer(app, reporting_date='')
        self.assertTrue(pe.offer_reporting_date_unknown(app))

    def test_not_unknown_when_date_present(self):
        app = self._app('c')
        self._offer(app, '8 JUN 2026')
        self.assertFalse(pe.offer_reporting_date_unknown(app))

    def test_not_unknown_when_offer_unread(self):
        app = self._app('d')
        self._offer(app, reporting_date='', read=False)   # not extracted yet
        self.assertFalse(pe.offer_reporting_date_unknown(app))

    def test_no_offer_not_unknown(self):
        app = self._app('e')
        self.assertFalse(pe.offer_reporting_date_unknown(app))


class TestAutofillStoresDate(_OfferBase):
    def test_autofill_persists_reporting_date(self):
        from apps.scholarship.services import autofill_pathway_from_offer
        app = self._app('f')
        self._offer(app, '22 JUN 2026')
        autofill_pathway_from_offer(app)
        app.refresh_from_db()
        self.assertEqual(app.reporting_date, datetime.date(2026, 6, 22))


class TestCheck2Clarify(_OfferBase):
    def _codes(self, app):
        return {r.code: r for r in app.resolution_items.filter(source='check2', status='open')}

    def test_missing_date_raises_clarify(self):
        app = self._app('g')
        self._offer(app, reporting_date='')
        sync_check2_queries(app)
        items = self._codes(app)
        self.assertIn('reporting_date_unknown', items)
        self.assertEqual(items['reporting_date_unknown'].kind, 'clarify')

    def test_no_clarify_when_date_present(self):
        app = self._app('h')
        self._offer(app, '8 JUN 2026')
        sync_check2_queries(app)
        self.assertNotIn('reporting_date_unknown', self._codes(app))
