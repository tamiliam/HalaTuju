"""Owner 2026-11-23 — every rejected case reads "Rejected" plus ONE second chip, served as
`rejection_chip` on the admin list row and the cockpit payload (`apps/scholarship/rejection_chip.py`).

Pinned here: every chip, QC outright reject vs a confirmed decline, the birth-state marker read from
the engine's own reason, the "state" chip on a case that is NOT rejected (owner D), and that the
list asks for the QC rows ONCE for a page, never once per row.
"""
from datetime import timedelta

from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.scholarship import birth_state as bs
from apps.scholarship import rejection_chip as rc
from apps.scholarship.models import StaffActivity
from apps.scholarship.shortlisting import evaluate
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_programme,
    make_student,
)

ONLY_BIRTH = dict(min_spm_a_count=None, min_spm_bplus_count=None, min_spm_credit_count=None,
                  min_stpm_pngk=None, min_merit_score=None, income_ceiling=None,
                  per_capita_ceiling=None)
SABAH_IC, SELANGOR_IC = '080505-12-1234', '080505-10-1234'
STATE_REASON = 'born in Selangor (IC code 10); this intake accepts Sabah'
LIST = '/api/v1/admin/scholarship/applications/'


def _detail(pk):
    return f'/api/v1/admin/scholarship/applications/{pk}/'


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheChip(TestCase):
    def setUp(self):
        self.programme = make_programme()
        self.admin = make_admin('org_admin', owning_org=self.programme.organisation)
        self.cohort = make_cohort(programme=self.programme)
        self.client = authed_client(self.admin)

    def _rejected(self, category, reason='', cohort=None, nric=SABAH_IC):
        return make_application(cohort=cohort or self.cohort, student=make_student(nric=nric),
                                 status='rejected', rejection_category=category,
                                 shortlist_reason=reason)

    def _qc(self, app, decision, minutes_ago=0):
        StaffActivity.objects.create(
            actor=self.admin, organisation=self.programme.organisation, verb='qc_decision',
            subject_type='application', subject_id=app.pk,
            meta={'decision': decision, 'outcome': 'declined'},
            created_at=timezone.now() - timedelta(minutes=minutes_ago))

    def _served(self, app):
        r = self.client.get(_detail(app.pk))
        self.assertEqual(r.status_code, 200)
        return r.data['rejection_chip']

    def _listed(self):
        r = self.client.get(LIST)
        self.assertEqual(r.status_code, 200)
        return {row['id']: row['rejection_chip'] for row in r.data['applications']}

    def test_each_category_has_its_chip_on_the_detail_and_the_list(self):
        cases = {
            'merit': self._rejected('merit'),
            'need': self._rejected('need'),
            'state': self._rejected('ineligible', STATE_REASON),
            'ineligible': self._rejected('ineligible', 'No consent to contact'),
            'shortlisted': self._rejected('incomplete', 'Missing documents'),
            'before_interview': self._rejected('pre_interview', 'Did not answer'),
            'interview': self._rejected('interview'),
            'contractual': self._rejected('contractual'),
            '': self._rejected(''),
        }
        listed = self._listed()
        for want, app in cases.items():
            with self.subTest(chip=want):
                self.assertEqual(self._served(app), want)
                self.assertEqual(listed[app.pk], want)

    def test_qc_outright_reject_reads_qc_and_a_confirmed_decline_reads_interview(self):
        outright, confirmed, old = (self._rejected('interview') for _ in range(3))
        self._qc(outright, 'reject')
        self._qc(confirmed, 'accept')
        # `old` has no QC row at all: an older decline, which reads "interview".
        listed = self._listed()
        for app, want in ((outright, 'qc'), (confirmed, 'interview'), (old, 'interview')):
            with self.subTest(want=want):
                self.assertEqual(self._served(app), want)
                self.assertEqual(listed[app.pk], want)

    def test_the_latest_qc_row_wins(self):
        app = self._rejected('interview')
        self._qc(app, 'reject', minutes_ago=30)
        self._qc(app, 'accept', minutes_ago=5)     # reopened, then QC confirmed the decline
        self.assertEqual(self._served(app), 'interview')
        later = self._rejected('interview')
        self._qc(later, 'accept', minutes_ago=30)
        self._qc(later, 'reject', minutes_ago=5)
        self.assertEqual(self._served(later), 'qc')

    def test_a_qc_reject_on_a_case_not_declined_at_interview_is_ignored(self):
        app = self._rejected('merit')
        self._qc(app, 'reject')
        self.assertEqual(self._served(app), 'merit')

    def test_state_on_a_case_that_is_not_rejected_owner_d(self):
        ruled = make_cohort(programme=self.programme, allowed_birth_states=['sabah'])
        fails = make_application(cohort=ruled, student=make_student(nric=SELANGOR_IC))
        passes = make_application(cohort=ruled, student=make_student(nric=SABAH_IC))
        no_rule = make_application(cohort=self.cohort, student=make_student(nric=SELANGOR_IC))
        listed = self._listed()
        for app, want in ((fails, 'state'), (passes, ''), (no_rule, '')):
            with self.subTest(want=want):
                self.assertEqual(self._served(app), want)
                self.assertEqual(listed[app.pk], want)

    def test_the_list_asks_for_the_qc_rows_once_whatever_the_page_holds(self):
        def queries():
            with CaptureQueriesContext(connection) as ctx:
                self.assertEqual(self.client.get(LIST).status_code, 200)
            return [q['sql'] for q in ctx.captured_queries]

        def qc_reads(sqls):
            return [s for s in sqls if 'staff_activity' in s and 'qc_decision' in s]

        first = self._rejected('interview')
        self._qc(first, 'reject')
        one = queries()
        for _ in range(3):
            self._qc(self._rejected('interview'), 'reject')
        four = queries()
        self.assertEqual(len(four), len(one))
        self.assertEqual(len(qc_reads(four)), 1)
        self.assertEqual(sum(v == 'qc' for v in self._listed().values()), 4)


class TestTheStateMarker(TestCase):
    """The "state" chip reads the engine's STORED reason through the rule's own marker."""

    def test_the_engine_reason_for_a_wrong_birth_state_carries_the_marker(self):
        c = make_cohort(**ONLY_BIRTH, allowed_birth_states=['sabah'])
        a = make_application(cohort=c, student=make_student(nric=SELANGOR_IC))
        r = evaluate(a, c)
        self.assertEqual(r.category, 'ineligible')
        self.assertTrue(rc.fails_state_rule_reason(r.reason))
        a.status, a.rejection_category, a.shortlist_reason = 'rejected', r.category, r.reason
        self.assertEqual(rc.chip(a, set()), 'state')

    def test_every_failing_ic_kind_carries_it(self):
        for nric in (SELANGOR_IC, '080505-71-1234', '080505-82-1234', ''):
            with self.subTest(nric=nric):
                ok, reason = bs.check(nric, ['sabah'])
                self.assertFalse(ok)
                self.assertIn(bs.RULE_REASON_MARK, reason)

    def test_other_ineligible_reasons_do_not(self):
        for reason in ('', 'No consent to contact', 'Not intending tertiary study in 2026',
                       'Private (IPTS) offer'):
            with self.subTest(reason=reason):
                self.assertFalse(rc.fails_state_rule_reason(reason))
