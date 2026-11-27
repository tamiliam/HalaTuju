"""#86's promise, end to end (review round 1, 27 Nov 2026): a case QC sends back shows again on the
interviewer's My open, marked "Returned by QC".

The reopen is made by the REAL service (`reopen.reopen_decision`), so the case keeps its verdict stamp
exactly as production does. Checked on both readers of the rule: the Overview's `mine` section and
the list the My-open card opens (`?assigned=me&band=open`). The flag needs the reviewer's turn too:
a reopen left open while the case moved on (resubmitted to QC, or declined) is not "Returned by QC".
The overdue / due-soon bands and the nudges are untouched: a returned or stuck case is never in them.
"""
import datetime

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import reopen
from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.review_sla import clocks as review_clocks
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org, make_programme,
)

LIST = '/api/v1/admin/scholarship/applications/'
OVERVIEW = '/api/v1/admin/scholarship/programme-overview/?programme=rq86-gift'


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class ReturnedByQcOnMyOpen(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.cohort = make_cohort(programme=make_programme(cls.org, code='rq86-gift'))
        cls.rev = make_admin('reviewer', owning_org=cls.org)
        cls.rev_other = make_admin('reviewer', owning_org=cls.org)
        cls.super = make_admin('super', super_admin=True)
        long_ago = timezone.now() - datetime.timedelta(days=review_clocks(cls.org)[0] + 5)

        def sent_back(reviewer):
            app = make_application('awaiting_qc', outcome='decline', cohort=cls.cohort, reviewer=reviewer)
            reopen.reopen_decision(app, by_admin=cls.super, reason='QC sends it back')
            # An old assignment: on the `assigned_at` clock this case would read "overdue".
            ScholarshipApplication.objects.filter(pk=app.pk).update(assigned_at=long_ago)
            app.refresh_from_db()
            return app

        cls.returned = sent_back(cls.rev)
        cls.closed = sent_back(cls.rev)
        reopen.close_reopen_with_change(cls.closed)      # re-decided: the reopen is closed
        cls.theirs = sent_back(cls.rev_other)
        # #81-style: a verdict saved that never reached QC, no reopen, an old assignment.
        cls.stuck = make_application('assigned', cohort=cls.cohort, reviewer=cls.rev)
        ScholarshipApplication.objects.filter(pk=cls.stuck.pk).update(
            verdict_decided_at=timezone.now(), assigned_at=long_ago)

    def _mine(self, who=None):
        r = authed_client(who or self.rev).get(OVERVIEW)
        self.assertEqual(r.status_code, 200, r.content)
        return {c['id']: c for c in r.json()['mine']['cases']}

    def _list(self, query, who=None):
        r = authed_client(who or self.rev).get(LIST + query)
        self.assertEqual(r.status_code, 200, r.content)
        return {a['id']: a for a in r.json()['applications']}

    def test_the_reopen_is_the_real_one(self):
        self.assertEqual(self.returned.status, 'interviewing')
        self.assertIsNotNone(self.returned.verdict_decided_at)     # the stamp a reopen keeps
        self.assertIsNotNone(self.returned.decision_reopened_at)

    def test_a_returned_case_is_on_my_open_marked(self):
        for rows in (self._mine(), self._list('?assigned=me&band=open')):
            self.assertIn(self.returned.pk, rows)
            self.assertIs(rows[self.returned.pk]['returned_by_qc'], True)

    def test_a_closed_reopen_is_on_my_open_unmarked(self):
        for rows in (self._mine(), self._list('?assigned=me&band=open')):
            self.assertIn(self.closed.pk, rows)
            self.assertIs(rows[self.closed.pk]['returned_by_qc'], False)

    def test_another_reviewers_returned_case_is_not_on_mine(self):
        for rows in (self._mine(), self._list('?assigned=me&band=open')):
            self.assertNotIn(self.theirs.pk, rows)
        self.assertIn(self.theirs.pk, self._mine(self.rev_other))

    def test_a_returned_or_stuck_case_has_no_clock_on_mine(self):
        mine = self._mine()
        for app in (self.returned, self.stuck):
            self.assertIsNone(mine[app.pk]['band'])
            self.assertIsNone(mine[app.pk]['due_at'])

    def test_the_overdue_and_due_soon_bands_stay_untouched(self):
        for band in ('overdue', 'due_soon'):
            for who in (self.rev, self.super):
                rows = self._list(f'?band={band}', who)
                for app in (self.returned, self.stuck, self.closed):
                    self.assertNotIn(app.pk, rows, (band, app.pk))

    def test_a_reopen_left_open_after_a_resubmit_is_not_marked(self):
        r = authed_client(self.super).post(
            f'{LIST}{self.returned.pk}/submit-decline/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])
        app = ScholarshipApplication.objects.get(pk=self.returned.pk)
        self.assertEqual(app.status, 'interviewed')                # back at QC
        self.assertIsNotNone(app.decision_reopened_at)             # the reopen is still open
        self.assertIs(self._list('', self.super)[app.pk]['returned_by_qc'], False)
        self.assertNotIn(app.pk, self._mine())

    def test_a_reopen_left_open_on_a_declined_case_is_not_marked(self):
        ScholarshipApplication.objects.filter(pk=self.returned.pk).update(status='rejected')
        self.assertIs(self._list('', self.super)[self.returned.pk]['returned_by_qc'], False)
        self.assertNotIn(self.returned.pk, self._mine())
