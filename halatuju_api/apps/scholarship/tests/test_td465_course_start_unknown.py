"""TD-465 (money hotfix, 2026-11-05): an STPM case whose course-start year is UNKNOWN is never
given an automatic amount.

The defect: `award.course_start_unknown` existed (the owner's 2026-07-23 absolute stop) but nothing
on the award path asked it, so `proposed_award_amount` fell through to the fresh-entrant RM3,000
and `record-verdict` committed it on an APPROVE. Now the proposal is None (the existing "no
automatic amount" outcome): `award_amount` stays unset, and QC's absolute reporting-date stop
(`reporting_date_required`, no override) refuses the accept until the officer records the date.
A re-recorded verdict then sizes the bursary from the known year.
"""
import datetime
from decimal import Decimal
from unittest import mock

from django.test import TestCase, override_settings

from apps.scholarship import award
from apps.scholarship.serializers_admin import AdminApplicationDetailSerializer
from apps.scholarship.models import InterviewSession
from apps.scholarship.services import set_reporting_date_by_officer, submit_interview
from apps.scholarship.tests.factories import (
    RECOMMEND_VERDICT, TEST_JWT_SECRET, VERIFY_CHECKLIST, answered_findings, authed_client,
    make_admin, make_application, make_cohort,
)


def _url(app, door):
    return f'/api/v1/admin/scholarship/applications/{app.pk}/{door}/'


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestCourseStartUnknownStopsTheAward(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort()   # year 2026
        org = cls.cohort.owning_organisation
        cls.reviewer = make_admin('reviewer', owning_org=org)
        cls.qc = make_admin('qc', owning_org=org)

    def _case(self, pathway='stpm', reporting_date=None):
        """An approved case AWAITING QC whose earlier record produced no amount; no offer letter
        on file, so the start year is the stored reporting date or nothing."""
        return make_application('awaiting_qc', outcome='recommend', cohort=self.cohort,
                                reviewer=self.reviewer, chosen_pathway=pathway,
                                reporting_date=reporting_date, award_amount=None)

    def _record_accept(self, app):
        return authed_client(self.reviewer).post(
            _url(app, 'record-verdict'),
            {'officer_verdict': dict(RECOMMEND_VERDICT), 'reason': 'ok'}, format='json')

    # -- the rule ------------------------------------------------------------------------------
    def test_unknown_start_year_proposes_no_amount(self):
        app = self._case()
        self.assertTrue(award.course_start_unknown(app))
        self.assertIsNone(award.proposed_award_amount(app))
        self.assertIsNone(AdminApplicationDetailSerializer(app).data['proposed_award_amount'])

    # -- the live award path -------------------------------------------------------------------
    def test_accepted_stpm_with_unknown_start_year_gets_no_rm3000(self):
        app = self._case()
        r = self._record_accept(app)
        self.assertEqual(r.status_code, 200, r.content)
        app.refresh_from_db()
        self.assertIsNone(app.award_amount)
        self.assertEqual(app.officer_verdict.get('overall'), 'accept')

    def test_known_fresh_start_year_is_unchanged_rm3000(self):
        app = self._case(reporting_date=datetime.date(2026, 6, 8))
        self.assertEqual(self._record_accept(app).status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.award_amount, Decimal('3000'))

    def test_known_continuing_start_year_is_unchanged_rm1000(self):
        app = self._case(reporting_date=datetime.date(2025, 6, 10))
        self.assertEqual(self._record_accept(app).status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.award_amount, Decimal('1000'))

    def test_another_route_is_unchanged_with_no_date(self):
        # Only STPM prices on the start year; a polytechnic case keeps its RM2,000.
        app = self._case(pathway='poly')
        self.assertFalse(award.course_start_unknown(app))
        self.assertEqual(self._record_accept(app).status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.award_amount, Decimal('2000'))

    # -- the stop, as the existing code expects it -----------------------------------------------
    def test_qc_accept_is_refused_with_the_existing_reason(self):
        app = self._case()
        self._record_accept(app)
        with mock.patch('apps.scholarship.views_admin.verdict.build_verdict', return_value=[]):
            r = authed_client(self.qc).post(
                _url(app, 'qc-decision'),
                {'decision': 'accept', 'override_reason': 'try to pass'}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(r.json()['code'], 'reporting_date_required')
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewed')
        self.assertIsNone(app.award_amount)

    def test_once_the_officer_records_the_date_a_re_record_sizes_it(self):
        app = self._case()
        self._record_accept(app)
        set_reporting_date_by_officer(app, self.reviewer, '2025-06-10')
        self.assertFalse(award.course_start_unknown(app))
        self.assertEqual(self._record_accept(app).status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.award_amount, Decimal('1000'))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestQcRefusesAnApproveWithNoBursary(TestCase):
    """TD-465 review: four routes fill the reporting date WITHOUT re-recording the verdict, so the
    date stop alone let an approve with ``award_amount`` None reach `recommended`. QC's accept now
    refuses it (``award_required``, no override); re-recording the verdict is the remedy."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort()   # year 2026
        org = cls.cohort.owning_organisation
        cls.reviewer = make_admin('reviewer', owning_org=org)
        cls.qc = make_admin('qc', owning_org=org)
        cls.super = make_admin('super', super_admin=True)

    def _post(self, who, app, door, body=None):
        return authed_client(who).post(_url(app, door), body or {}, format='json')

    def _sized_nothing(self):
        """An approve AWAITING QC whose verdict was recorded while the start year was unknown."""
        app = make_application('awaiting_qc', outcome='recommend', cohort=self.cohort,
                               reviewer=self.reviewer, chosen_pathway='stpm',
                               reporting_date=None, award_amount=None)
        r = self._post(self.reviewer, app, 'record-verdict',
                       {'officer_verdict': dict(RECOMMEND_VERDICT), 'reason': 'ok'})
        self.assertEqual(r.status_code, 200, r.content)
        app.refresh_from_db()
        self.assertIsNone(app.award_amount)
        return app

    def _verify_accept(self, app):
        # The completeness gate is not under test (the factory row is not a complete profile).
        with mock.patch('apps.scholarship.views_admin.applications.application_completeness',
                        return_value={'complete': True}):
            return self._post(self.reviewer, app, 'verify-accept',
                              {'checklist': dict(VERIFY_CHECKLIST)})

    def _qc_accept(self, app, **extra):
        with mock.patch('apps.scholarship.views_admin.verdict.build_verdict', return_value=[]):
            return self._post(self.qc, app, 'qc-decision', {'decision': 'accept', **extra})

    def _assert_refused(self, app):
        r = self._qc_accept(app, override_reason='try to pass')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(r.json()['code'], 'award_required')
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewed')
        self.assertIsNone(app.award_amount)

    # -- the four routes that fill the date without a re-record -------------------------------------
    def test_after_an_offer_re_read(self):
        from apps.scholarship import reextract, vision
        from apps.scholarship.models import ApplicantDocument
        app = self._sized_nothing()
        doc = ApplicantDocument.objects.create(
            application=app, doc_type='offer_letter', storage_path='x/offer',
            vision_fields={'student_verdict': 'ok',
                           'fields': {'reporting_date': '10 JUN 2025', 'programme': 'Tingkatan Enam',
                                      'institution': 'SMK Test'}})
        # The paid reads are stubbed; the offer branch (autofill -> sync_reporting_date_from_offer)
        # is the real code.
        with mock.patch.object(vision, 'ocr_document_full', return_value=None), \
                mock.patch.object(vision, 'run_vision_match_for_document'), \
                mock.patch.object(vision, 'run_field_extraction_for_document'):
            self.assertTrue(reextract.reextract_document(doc))
        app.refresh_from_db()
        self.assertEqual(app.reporting_date, datetime.date(2025, 6, 10))
        self._assert_refused(app)

    def test_after_a_cancelled_reopen(self):
        app = self._sized_nothing()
        r = self._post(self.qc, app, 'qc-decision', {'decision': 'reopen', 'comments': 'no date'})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._post(self.reviewer, app, 'reporting-date',
                                    {'date': '2025-06-10'}).status_code, 200)
        r = self._post(self.super, app, 'cancel-reopen')
        self.assertEqual(r.status_code, 200, r.content)
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewed')
        self._assert_refused(app)

    def test_after_a_direct_verify_accept(self):
        app = self._sized_nothing()
        self.assertEqual(self._post(self.reviewer, app, 'reporting-date',
                                    {'date': '2025-06-10'}).status_code, 200)
        r = self._verify_accept(app)
        self.assertEqual(r.status_code, 200, r.content)
        self._assert_refused(app)

    def test_after_the_reporting_date_box_alone(self):
        app = self._sized_nothing()
        self.assertEqual(self._post(self.reviewer, app, 'reporting-date',
                                    {'date': '2025-06-10'}).status_code, 200)
        self._assert_refused(app)

    # -- unaffected ------------------------------------------------------------------------------
    def test_an_approve_with_an_amount_is_accepted_as_before(self):
        app = make_application('awaiting_qc', outcome='recommend', cohort=self.cohort,
                               reviewer=self.reviewer, chosen_pathway='stpm',
                               reporting_date=datetime.date(2025, 6, 10), award_amount=1000)
        r = self._qc_accept(app)
        self.assertEqual(r.status_code, 200, r.content)
        app.refresh_from_db()
        self.assertEqual(app.status, 'recommended')
        self.assertEqual(app.award_amount, Decimal('1000'))

    def test_a_decline_is_unaffected(self):
        app = make_application('awaiting_qc', outcome='decline', cohort=self.cohort,
                               reviewer=self.reviewer, chosen_pathway='stpm')
        self.assertIsNone(app.award_amount)
        r = self._qc_accept(app)
        self.assertEqual(r.status_code, 200, r.content)
        app.refresh_from_db()
        self.assertEqual(app.status, 'rejected')

    # -- the real road ---------------------------------------------------------------------------
    def test_reopen_date_re_record_verify_accept_sizes_and_accepts(self):
        app = self._sized_nothing()
        r = self._post(self.qc, app, 'qc-decision', {'decision': 'reopen', 'comments': 'no date'})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._post(self.reviewer, app, 'reporting-date',
                                    {'date': '2025-06-10'}).status_code, 200)
        # A reopened decision is re-gated on a submitted interview (TD-253).
        submit_interview(InterviewSession.objects.create(
            application=app, interviewer=self.reviewer, status='draft',
            findings=answered_findings(app)))
        r = self._post(self.reviewer, app, 'record-verdict',
                       {'officer_verdict': dict(RECOMMEND_VERDICT), 'reason': 'ok'})
        self.assertEqual(r.status_code, 200, r.content)
        r = self._verify_accept(app)
        self.assertEqual(r.status_code, 200, r.content)
        app.refresh_from_db()
        self.assertEqual(app.award_amount, Decimal('1000'))
        r = self._qc_accept(app)
        self.assertEqual(r.status_code, 200, r.content)
        app.refresh_from_db()
        self.assertEqual(app.status, 'recommended')
        self.assertEqual(app.award_amount, Decimal('1000'))
