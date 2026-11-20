"""LL2b (server) - the QC's second look at the facts in doubt.

Which facts are in doubt (`second_look`), the QC decision storing the answers inside `officer_verdict`,
the admin detail serving the list and the answers, and the "checked by the QC" numbers (endpoint and
Overview section). All data is made up; only fact names, statuses, codes and counts.
"""
import datetime
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings

from apps.scholarship import audit
from apps.scholarship import second_look as sl
from apps.scholarship.models import ScholarshipApplication, StaffActivity
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
    make_programme,
)

METRICS = '/api/v1/admin/scholarship/verdict-metrics/'
OVERVIEW = '/api/v1/admin/scholarship/programme-overview/'
UTC = datetime.timezone.utc
VIEW_ENGINE = 'apps.scholarship.views_admin.verdict.build_verdict'


def snap(statuses=None):
    statuses = statuses or {}
    return [{'fact': f, 'status': statuses.get(f, 'verified'), 'evidence': [], 'unresolved': []}
            for f in audit.FACTS]


def officer(overall='accept', **kw):
    v = {f: 'pass' for f in audit.FACTS}
    v.update(kw, overall=overall)
    return v


class TestInDoubt(SimpleTestCase):
    def test_the_two_groups_and_a_fact_in_both_appears_once(self):
        got = sl.in_doubt(snap({'academic': 'review'}),
                          officer(income='fail', academic='fail', fail_reasons={'income': 'read_wrong'}))
        self.assertEqual(got, [
            {'fact': 'academic', 'ai_status': 'review', 'ai_green': False, 'reviewer': 'fail',
             'reason': None, 'groups': [sl.FAILED_BUT_ACCEPTED]},
            {'fact': 'income', 'ai_status': 'verified', 'ai_green': True, 'reviewer': 'fail',
             'reason': 'read_wrong', 'groups': [sl.AI_GREEN_REVIEWER_FAIL, sl.FAILED_BUT_ACCEPTED]},
        ])

    def test_a_decline_shows_only_group_one(self):
        got = sl.in_doubt(snap({'academic': 'gap'}), officer('decline', income='fail', academic='fail'))
        self.assertEqual([(d['fact'], d['groups']) for d in got], [('income', [sl.AI_GREEN_REVIEWER_FAIL])])

    def test_nothing_in_doubt_is_an_empty_list(self):
        self.assertEqual(sl.in_doubt(snap(), officer()), [])                                 # all passed
        self.assertEqual(sl.in_doubt(snap({'income': 'review'}), officer('decline', income='fail')), [])
        self.assertEqual(sl.in_doubt(None, None), [])
        self.assertEqual(sl.in_doubt([], {'income': 'fail', 'overall': 'hold'}), [])         # no snapshot

    def test_validate_shapes(self):
        self.assertIsNone(sl.validate(None))
        self.assertEqual(sl.validate({}), {})
        self.assertEqual(sl.validate({'income': 'disagreed'}), {'income': 'disagreed'})
        for bad in ([], 'x', 3, {'income': 'nope'}, {'colour': 'agreed'}, {'income': None},
                    {'income': ['disagreed']}, {'income': True}):
            with self.subTest(bad=bad), self.assertRaises(sl.BadFactChecks):
                sl.validate(bad)

    def test_answers_accept_send_back_and_drop(self):
        # Review round: an accept keeps only facts in BOTH the payload and the in-doubt set
        # (was: every in-doubt fact 'agreed' unless tapped, which let a stale tab answer unseen facts).
        doubt = [{'fact': 'income'}, {'fact': 'academic'}]
        taps = {'income': 'disagreed', 'identity': 'disagreed', 'academic': 'agreed'}
        self.assertEqual(sl.answers('accept', {}, doubt), {})
        self.assertEqual(sl.answers('accept', {'income': 'agreed'}, doubt), {'income': 'agreed'})
        self.assertEqual(sl.answers('accept', taps, doubt), {'income': 'disagreed', 'academic': 'agreed'})
        for send_back in ('reopen', 'reject'):
            self.assertEqual(sl.answers(send_back, taps, doubt), {'income': 'disagreed'})
            self.assertEqual(sl.answers(send_back, {}, doubt), {})
        self.assertEqual(sl.answers('accept', taps, []), {})

    def test_odd_stored_shapes_never_raise(self):
        for snapshot in ({'income': 'verified'}, 3, 'x', [{'fact': 'income', 'status': ['verified']}]):
            with self.subTest(snapshot=snapshot):
                got = sl.in_doubt(snapshot, officer('decline', income='fail'))
                self.assertEqual(got, [])   # no readable AI status: not green, and a decline has no group 2
        for ov in (['income'], 'fail', 3):
            with self.subTest(ov=ov):
                self.assertEqual(sl.in_doubt(snap(), ov), [])

    def test_a_stored_verdict_that_is_not_a_dict_never_fails_the_qc_decision(self):
        app = mock.Mock(officer_verdict=['income', 'fail'], ai_verdict_snapshot=snap(),
                        verdict_decided_at=datetime.datetime(2026, 5, 10, tzinfo=UTC))
        for decision in ('accept', 'reopen', 'reject'):
            with self.subTest(decision=decision):
                look = sl.record_answers(app, decision, {'income': 'disagreed'})
                self.assertEqual(look, {'qc_agreed': [], 'qc_disagreed': [], 'doubt_ai_green': [],
                                        'doubt_failed_accepted': []})
                self.assertEqual(app.officer_verdict, ['income', 'fail'])   # left untouched
        app.save.assert_not_called()

    def test_the_activity_meta_is_fact_names_and_group_codes(self):
        doubt = sl.in_doubt(snap({'academic': 'review'}), officer(income='fail', academic='fail'))
        self.assertEqual(sl.activity_meta({'income': 'disagreed', 'academic': 'agreed'}, doubt),
                         {'qc_agreed': ['academic'], 'qc_disagreed': ['income'],
                          'doubt_ai_green': ['income'], 'doubt_failed_accepted': ['academic', 'income']})


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestQcDecisionRecordsTheSecondLook(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort()
        org = cls.cohort.owning_organisation
        cls.reviewer = make_admin('reviewer', owning_org=org)
        cls.qc = make_admin('qc', owning_org=org)
        cls.lead = make_admin('org_admin', owning_org=org)
        cls.superadmin = make_admin('super', super_admin=True)

    def setUp(self):
        # income: AI green + reviewer fail (groups 1 and 2); academic: AI unsure + failed on an accept (group 2)
        self.app = self._case(officer(income='fail', academic='fail'))
        patcher = mock.patch(VIEW_ENGINE, return_value=[])   # the accept's gap floor reads a fresh run
        patcher.start()
        self.addCleanup(patcher.stop)

    def _case(self, verdict, outcome='recommend', reviewer=None):
        return make_application('awaiting_qc', outcome=outcome, cohort=self.cohort,
                                reviewer=reviewer or self.reviewer,
                                ai_verdict_snapshot=snap({'academic': 'review'}), officer_verdict=verdict)

    def _qc(self, body, who=None, app=None):
        app = app or self.app
        return authed_client(who or self.qc).post(
            f'/api/v1/admin/scholarship/applications/{app.pk}/qc-decision/', body, format='json')

    def _stored(self, app=None):
        return ScholarshipApplication.objects.get(pk=(app or self.app).pk).officer_verdict

    def test_the_detail_serves_the_list_and_no_answers_before_qc(self):
        body = authed_client(self.qc).get(f'/api/v1/admin/scholarship/applications/{self.app.pk}/').json()
        self.assertEqual([d['fact'] for d in body['second_look']['in_doubt']], ['academic', 'income'])
        self.assertIsNone(body['second_look']['answers'])

    def test_a_silent_accept_records_agreed_for_the_shown_facts_only(self):
        # Review round: the web now sends 'agreed' for each untouched fact it showed (was `{}`).
        want = {'academic': 'agreed', 'income': 'agreed'}
        r = self._qc({'decision': 'accept', 'fact_checks': want})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._stored()[sl.KEY], want)
        self.assertEqual(r.json()['second_look']['answers'], want)
        self.assertEqual(r.json()['officer_verdict'][sl.KEY], want)
        self.assertEqual(ScholarshipApplication.objects.get(pk=self.app.pk).status, 'recommended')

    def test_an_accept_with_an_empty_object_records_nothing(self):
        r = self._qc({'decision': 'accept', 'fact_checks': {}})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._stored()[sl.KEY], {})
        self.assertEqual(ScholarshipApplication.objects.get(pk=self.app.pk).status, 'recommended')

    def test_an_accept_that_misses_an_in_doubt_fact_records_no_answer_for_it(self):
        # a stale tab showed only income; academic became in doubt after it loaded
        r = self._qc({'decision': 'accept', 'fact_checks': {'income': 'agreed'}})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._stored()[sl.KEY], {'income': 'agreed'})

    def test_a_tap_records_disagreed_and_a_fact_outside_the_set_is_dropped(self):
        # Review round: academic is now sent as 'agreed' (was left out and filled in by the server).
        r = self._qc({'decision': 'accept', 'fact_checks': {'income': 'disagreed', 'identity': 'disagreed',
                                                            'academic': 'agreed'}})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._stored()[sl.KEY], {'academic': 'agreed', 'income': 'disagreed'})

    def test_the_qc_activity_row_keeps_the_second_look_after_a_re_record(self):
        self._qc({'decision': 'reopen', 'comments': 'Made up.',
                  'fact_checks': {'income': 'disagreed', 'academic': 'agreed'}})
        row = lambda: StaffActivity.objects.get(verb='qc_decision', subject_id=self.app.pk)   # noqa: E731
        want = {'decision': 'reopen', 'outcome': 'reopened', 'qc_agreed': [], 'qc_disagreed': ['income'],
                'doubt_ai_green': ['income'], 'doubt_failed_accepted': ['academic', 'income']}
        self.assertEqual(row().meta, want)
        body = {'officer_verdict': {**officer('hold'), 'income': 'pass'}, 'reason': 'Made up.'}
        with mock.patch(VIEW_ENGINE, return_value=snap()):
            r = authed_client(self.reviewer).post(
                f'/api/v1/admin/scholarship/applications/{self.app.pk}/record-verdict/', body, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertNotIn(sl.KEY, self._stored())   # the verdict's copy goes, as before
        self.assertEqual(row().meta, want)           # the activity row's copy stays
        # the QC's own activity list serves the same keys (it re-filters to the closed key list)
        items = authed_client(self.qc).get('/api/v1/admin/me/activity/').json()['results']
        self.assertEqual([i['meta'] for i in items if i['verb'] == 'qc_decision'], [want])

    def test_no_key_adds_nothing_to_the_activity_row(self):
        self._qc({'decision': 'accept'})
        meta = StaffActivity.objects.get(verb='qc_decision', subject_id=self.app.pk).meta
        self.assertEqual(meta, {'decision': 'accept', 'outcome': 'recommended'})

    def test_a_send_back_records_only_the_taps(self):
        r = self._qc({'decision': 'reopen', 'comments': 'Made up.',
                      'fact_checks': {'income': 'disagreed', 'academic': 'agreed'}})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._stored()[sl.KEY], {'income': 'disagreed'})
        other = self._case(officer(income='fail'))
        r = self._qc({'decision': 'reject', 'comments': 'Made up.', 'fact_checks': {}}, app=other)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._stored(other)[sl.KEY], {})

    def test_a_qc_confirm_of_a_decline_records_the_group_one_fact(self):
        app = self._case(officer('decline', income='fail', academic='fail'), outcome='decline')
        # Review round: the web sends 'agreed' for the shown fact (was `{}`)
        r = self._qc({'decision': 'accept', 'fact_checks': {'income': 'agreed'}}, app=app)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._stored(app)[sl.KEY], {'income': 'agreed'})   # academic was not green

    def test_a_snapshot_item_whose_fact_is_a_list_or_dict_never_fails_the_qc_decision(self):
        # Gate round: an unhashable `fact` raised TypeError inside the decision's transaction.
        odd = [{'fact': ['income'], 'status': 'verified'}, {'fact': {'f': 'income'}, 'status': 'verified'}]
        app = make_application('awaiting_qc', outcome='recommend', cohort=self.cohort, reviewer=self.reviewer,
                               ai_verdict_snapshot=odd + snap({'academic': 'review'}),
                               officer_verdict=officer(income='fail', academic='fail'))
        want = {'academic': 'agreed', 'income': 'disagreed'}
        r = self._qc({'decision': 'accept', 'fact_checks': want}, app=app)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._stored(app)[sl.KEY], want)   # the odd items are skipped, the good ones read
        self.assertEqual(ScholarshipApplication.objects.get(pk=app.pk).status, 'recommended')

    def test_bad_input_is_a_400_and_the_decision_is_not_saved(self):
        before = self._stored()
        for bad in ({'income': 'nope'}, {'colour': 'agreed'}, ['income'], 'income', {'income': 3}):
            for decision in ('accept', 'reopen'):
                with self.subTest(bad=bad, decision=decision):
                    r = self._qc({'decision': decision, 'comments': 'Made up.', 'fact_checks': bad})
                    self.assertEqual(r.status_code, 400)
                    self.assertEqual(r.json(), {'error': 'bad fact_checks', 'code': 'bad_fact_checks'})
                    app = ScholarshipApplication.objects.get(pk=self.app.pk)
                    self.assertEqual(app.status, 'interviewed')
                    self.assertEqual(app.officer_verdict, before)
                    self.assertIsNone(app.decision_reopened_at)
        self.assertFalse(StaffActivity.objects.filter(verb='qc_decision', subject_id=self.app.pk).exists())

    def test_no_key_is_todays_behaviour_byte_for_byte(self):
        for extra in ({}, {'fact_checks': None}):
            with self.subTest(extra=extra):
                app = self._case(officer(income='fail', academic='fail'))
                before = self._stored(app)
                r = self._qc({'decision': 'accept', **extra}, app=app)
                self.assertEqual(r.status_code, 200, r.content)
                self.assertEqual(self._stored(app), before)
                self.assertNotIn(sl.KEY, self._stored(app))
                self.assertIsNone(r.json()['second_look']['answers'])

    def test_the_separation_rule_still_refuses_a_persons_own_case(self):
        own = self._case(officer(income='fail'), reviewer=self.qc)
        r = self._qc({'decision': 'accept', 'fact_checks': {'income': 'disagreed'}}, app=own)
        self.assertEqual(r.status_code, 403)
        self.assertNotIn(sl.KEY, self._stored(own))

    def test_only_a_qc_or_a_lead_can_record_a_second_look(self):
        r = self._qc({'decision': 'accept', 'fact_checks': {}}, who=self.reviewer)
        self.assertEqual(r.status_code, 403)
        self.assertNotIn(sl.KEY, self._stored())
        for who in (self.qc, self.lead, self.superadmin):
            with self.subTest(role=who.role):
                app = self._case(officer(income='fail'))
                r = self._qc({'decision': 'accept', 'fact_checks': {'income': 'disagreed'}}, who=who, app=app)
                self.assertEqual(r.status_code, 200, r.content)
                self.assertEqual(self._stored(app)[sl.KEY], {'income': 'disagreed'})

    def test_a_second_qc_round_replaces_the_first_answers(self):
        self._qc({'decision': 'reopen', 'comments': 'Made up.', 'fact_checks': {'income': 'disagreed'}})
        self.assertEqual(self._stored()[sl.KEY], {'income': 'disagreed'})
        # back at QC on the SAME reviewer verdict (status only, as a resubmission would leave it)
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(status='interviewed', decision_reopened_at=None)
        # Review round: the web sends 'agreed' for each untouched shown fact (was `{}`)
        r = self._qc({'decision': 'accept', 'fact_checks': {'academic': 'agreed', 'income': 'agreed'}})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._stored()[sl.KEY], {'academic': 'agreed', 'income': 'agreed'})

    def test_a_re_recorded_verdict_drops_the_answers_that_judged_the_old_one(self):
        self._qc({'decision': 'reopen', 'comments': 'Made up.', 'fact_checks': {'income': 'disagreed'}})
        body = {'officer_verdict': {**officer('hold'), 'income': 'pass'}, 'reason': 'Made up.'}
        with mock.patch(VIEW_ENGINE, return_value=snap()):
            r = authed_client(self.reviewer).post(
                f'/api/v1/admin/scholarship/applications/{self.app.pk}/record-verdict/', body, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertNotIn(sl.KEY, self._stored())
        self.assertIsNone(r.json()['second_look']['answers'])


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestCheckedByTheQcNumbers(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org, cls.other = make_org(), make_org()
        cls.cohort = make_cohort(programme=make_programme(cls.org))
        cls.foreign = make_cohort(programme=make_programme(cls.other))
        cls.lead = make_admin('org_admin', owning_org=cls.org)
        cls.qc = make_admin('qc', owning_org=cls.org)
        cls.reviewer = make_admin('reviewer', owning_org=cls.org)
        when = datetime.datetime(2026, 5, 10, 4, 0, tzinfo=UTC)

        def decided(cohort, verdict, snapshot=None):
            return make_application('awaiting_qc', outcome='recommend', cohort=cohort,
                                    ai_verdict_snapshot=snapshot or snap(), officer_verdict=verdict,
                                    verdict_decided_by='x@example.test', verdict_decided_at=when,
                                    ai_verdict_engine_version='v1')

        # group 1 (AI green, reviewer fail): QC agreed -> AI wrong, checked
        cls.a1 = decided(cls.cohort, officer(income='fail', qc_fact_checks={'income': 'agreed'}))
        # group 1 on a decline: QC disagreed -> AI right, reviewer wrong, checked
        cls.a2 = decided(cls.cohort, officer('decline', income='fail', qc_fact_checks={'income': 'disagreed'}))
        # group 2 only (AI unsure, failed on an accept): QC disagreed
        cls.a3 = decided(cls.cohort, officer(academic='fail', qc_fact_checks={'academic': 'disagreed'}),
                         snap({'academic': 'review'}))
        # an OLD QC decision with no stored answers: not checked
        cls.a4 = decided(cls.cohort, officer(income='fail'))
        # the other organisation's QC overturned its reviewer: must never reach this organisation
        cls.f1 = decided(cls.foreign, officer(income='fail', qc_fact_checks={'income': 'disagreed'}))

    def test_the_counts(self):
        body = authed_client(self.lead).get(METRICS).json()['qc_checked']
        total = body['total']
        self.assertEqual({k: total[k] for k in ('in_doubt', 'checked', 'not_checked', 'agreed', 'disagreed',
                                                 'ai_green_checked', 'ai_wrong_checked',
                                                 'ai_right_reviewer_wrong_checked')},
                         {'in_doubt': 4, 'checked': 3, 'not_checked': 1, 'agreed': 1, 'disagreed': 2,
                          'ai_green_checked': 2, 'ai_wrong_checked': 1, 'ai_right_reviewer_wrong_checked': 1})
        self.assertTrue(total['few'])
        self.assertTrue(total['few_ai_green'])
        self.assertEqual(body['facts']['income']['in_doubt'], 3)       # not 4: the other tenant's is fenced out
        self.assertEqual(body['facts']['income']['checked'], 2)
        self.assertEqual(body['facts']['academic']['disagreed'], 1)
        self.assertEqual(body['facts']['academic']['ai_green_checked'], 0)
        self.assertEqual(set(body['facts']), set(audit.FACTS))

    def test_the_overview_carries_the_same_object(self):
        page = authed_client(self.lead).get(OVERVIEW).json()['ai_prediction']
        self.assertEqual(page['qc_checked'], authed_client(self.lead).get(METRICS).json()['qc_checked'])

    def test_by_reviewer_carries_the_qc_counts_for_a_lead_only(self):
        rows = authed_client(self.lead).get(METRICS).json()['by_reviewer']
        self.assertEqual([(r['qc_checked'], r['qc_overturned']) for r in rows], [(3, 2)])
        for who in (self.qc, self.reviewer):
            with self.subTest(role=who.role):
                self.assertNotIn('by_reviewer', authed_client(who).get(METRICS).json())

    def test_a_reviewer_counts_only_their_assigned_applicants(self):
        ScholarshipApplication.objects.filter(pk=self.a2.pk).update(assigned_to=self.reviewer)
        for body in (authed_client(self.reviewer).get(METRICS).json(),
                     authed_client(self.reviewer).get(OVERVIEW).json()['ai_prediction']):
            self.assertEqual(body['qc_checked']['total']['checked'], 1)
            self.assertEqual(body['qc_checked']['total']['ai_right_reviewer_wrong_checked'], 1)

    def test_old_rows_and_bad_stored_values_count_as_not_checked(self):
        m = sl.qc_checked_counts([(snap(), officer(income='fail')),
                       (snap(), officer(income='fail', qc_fact_checks='garbage')),
                       (snap(), officer(income='fail', qc_fact_checks={'income': 'bogus'}))])
        self.assertEqual((m['total']['in_doubt'], m['total']['not_checked'], m['total']['checked']), (3, 3, 0))
        self.assertEqual(sl.qc_checked_counts([])['total']['checked'], 0)
        # an answer for a fact that is not in doubt on its own row is never counted
        m = sl.qc_checked_counts([(snap(), officer(qc_fact_checks={'income': 'disagreed'}))])
        self.assertEqual(m['total']['in_doubt'], 0)
        self.assertEqual(m['total']['checked'], 0)
