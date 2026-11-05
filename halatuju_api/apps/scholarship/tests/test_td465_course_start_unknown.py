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
from apps.scholarship.services import set_reporting_date_by_officer
from apps.scholarship.tests.factories import (
    RECOMMEND_VERDICT, TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort,
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
