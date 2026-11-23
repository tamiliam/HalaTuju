"""LL1 — the "AI prediction" scoreboard data (server part). F4: the endpoint answers in marks
(`ai_score`), reviewers are refused, and the "For the AI team" fold is the super's only.

Pure counting (`audit`), then the database reads (`prediction_metrics`), the endpoint's gates and the
Programme Overview's `ai_prediction` section: same function, same fence, lead-only `by_reviewer`.
"""
import datetime

from django.test import SimpleTestCase, TestCase, override_settings

from apps.scholarship import audit
from apps.scholarship.models import StaffActivity
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
    make_programme,
)

METRICS = '/api/v1/admin/scholarship/verdict-metrics/'
OVERVIEW = '/api/v1/admin/scholarship/programme-overview/'
UTC = datetime.timezone.utc
GREEN_KEYS = ('green', 'green_failed', 'unsure', 'unsure_passed')


def snap(statuses=None, codes=None):
    """A stored snapshot: every fact `verified` unless named; `codes` = {fact: [unresolved codes]}."""
    statuses, codes = statuses or {}, codes or {}
    return [{'fact': f, 'status': statuses.get(f, 'verified'), 'evidence': [],
             'unresolved': [{'code': c, 'params': {}} for c in codes.get(f, [])]}
            for f in audit.FACTS]


def officer(**kw):
    v = {f: 'pass' for f in audit.FACTS}
    v.update(kw)
    return v


def counts(block):
    return {k: block[k] for k in GREEN_KEYS}


class TestGreenUnsureCounts(SimpleTestCase):
    def test_overall_fact_version_and_doubt_counts(self):
        records = [
            # identity green + fail (green_failed); income unsure (gap, code A) + pass (unsure_passed)
            (snap({'income': 'gap'}, {'income': ['A']}), officer(identity='fail'), 'v1'),
            # income unsure + fail: the doubt was right
            (snap({'income': 'review'}, {'income': ['A', 'B']}), officer(income='fail'), 'v2'),
        ]
        m = audit.override_metrics(records)
        self.assertEqual(counts(m['overall']),
                         {'green': 6, 'green_failed': 1, 'unsure': 2, 'unsure_passed': 1})
        self.assertEqual(counts(m['fact_counts']['identity']),
                         {'green': 2, 'green_failed': 1, 'unsure': 0, 'unsure_passed': 0})
        self.assertEqual(counts(m['fact_counts']['income']),
                         {'green': 0, 'green_failed': 0, 'unsure': 2, 'unsure_passed': 1})
        self.assertEqual(counts(m['by_version']['v1']),
                         {'green': 3, 'green_failed': 1, 'unsure': 1, 'unsure_passed': 1})
        self.assertEqual(counts(m['by_version']['v2']),
                         {'green': 3, 'green_failed': 0, 'unsure': 1, 'unsure_passed': 0})
        self.assertEqual(
            m['doubt_codes'],
            [{'fact': 'income', 'code': 'A', 'passed': 1, 'failed': 1, 'total': 2,
              'pass_rate': 0.5, 'fail_rate': 0.5, 'few': True},
             {'fact': 'income', 'code': 'B', 'passed': 0, 'failed': 1, 'total': 1,
              'pass_rate': 0.0, 'fail_rate': 1.0, 'few': True}])

    def test_an_undecided_fact_is_not_counted(self):
        # The existing convention: a fact the officer left blank is not a decision.
        m = audit.override_metrics([(snap(), {'identity': 'pass'}, 'v1')])
        self.assertEqual(counts(m['overall']),
                         {'green': 1, 'green_failed': 0, 'unsure': 0, 'unsure_passed': 0})

    def test_a_green_fact_has_no_doubt_codes(self):
        m = audit.override_metrics([(snap(codes={'income': ['A']}), officer(), 'v1')])
        self.assertEqual(m['doubt_codes'], [])

    def test_months_are_malaysia_time_oldest_first(self):
        # 31 Mar 17:00 UTC is 1 Apr 01:00 in Kuala Lumpur; 15:59 UTC is still 31 Mar there.
        late = datetime.datetime(2026, 3, 31, 17, 0, tzinfo=UTC)
        early = datetime.datetime(2026, 3, 31, 15, 59, tzinfo=UTC)
        older = datetime.datetime(2026, 1, 15, 3, 0, tzinfo=UTC)
        m = audit.override_metrics([(snap(), officer(), 'v', late), (snap(), officer(), 'v', early),
                                    (snap(), officer(), 'v', older)])
        self.assertEqual(list(m['by_month']), ['2026-01', '2026-03', '2026-04'])
        self.assertEqual(m['by_month']['2026-04']['green'], 4)
        self.assertEqual(m['by_month']['2026-03']['green'], 4)

    def test_few_flips_at_thirty(self):
        def with_n(n):
            return audit.override_metrics([(snap(), officer(), 'v')] * n)['overall']
        # 7 applications x 4 facts = 28 and 8 x 4 = 32; use single-fact records for 29 / 30.
        one = {'identity': 'pass'}
        o29 = audit.override_metrics([(snap(), one, 'v')] * 29)['overall']
        o30 = audit.override_metrics([(snap(), one, 'v')] * 30)['overall']
        self.assertTrue(o29['few_green'] and o29['few'])
        self.assertFalse(o30['few_green'] or o30['few'])
        self.assertTrue(o30['few_unsure'])      # no unsure at all: 0 < 30
        self.assertEqual(with_n(8)['green'], 32)

    def test_agreed_counts_and_rate_are_served(self):
        records = [(snap(), officer(identity='fail'), 'v')] + [(snap(), officer(), 'v')] * 2
        o = audit.override_metrics(records)['overall']
        self.assertEqual((o['green_agreed'], o['green_agree_rate']), (11, round(11 / 12, 4)))
        none = audit.override_metrics([])['overall']
        self.assertEqual((none['green_agreed'], none['green_agree_rate']), (0, 0.0))

    def test_doubt_codes_sort_by_passed_then_total(self):
        records = [
            (snap({'income': 'gap'}, {'income': ['A']}), officer(income='fail'), 'v'),
            (snap({'income': 'gap'}, {'income': ['A']}), officer(income='fail'), 'v'),
            (snap({'income': 'gap'}, {'income': ['B']}), officer(), 'v'),
        ]
        rows = audit.override_metrics(records)['doubt_codes']
        self.assertEqual([(x['code'], x['passed'], x['total']) for x in rows], [('B', 1, 1), ('A', 0, 2)])

    def test_rates_are_rounded_like_override_rate(self):
        records = [(snap(), officer(identity='fail'), 'v')] + [(snap(), officer(), 'v')] * 2
        self.assertEqual(audit.override_metrics(records)['overall']['green_fail_rate'],
                         round(1 / 12, 4))

    def test_old_callers_and_existing_keys_are_unchanged(self):
        pairs = audit.override_metrics([(snap({'income': 'gap'}), officer(identity='fail'))])
        triples = audit.override_metrics([(snap({'income': 'gap'}), officer(identity='fail'), '')])
        for m in (pairs, triples):
            self.assertEqual(m['applications'], 1)
            self.assertEqual(m['fact_decisions'], 4)
            self.assertEqual(m['overrides'], 2)
            self.assertEqual(m['per_fact']['identity'], {'decided': 1, 'overrides': 1})
            self.assertEqual(m['engine_versions'], {'': 1})
        self.assertEqual(pairs['by_month'], {})     # no stamp given: no trend, no crash
        self.assertEqual(audit.override_metrics([])['by_month'], {})


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestPredictionEndpointAndOverview(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.org, cls.other = make_org(), make_org()
        cls.cohort = make_cohort(programme=make_programme(cls.org))
        cls.cohort2 = make_cohort(programme=make_programme(cls.org))
        cls.foreign = make_cohort(programme=make_programme(cls.other))
        cls.lead = make_admin('org_admin', owning_org=cls.org)
        cls.super = make_admin('super', super_admin=True)
        cls.reviewer = make_admin('reviewer', owning_org=cls.org, name='Rita Reviewer')
        cls.qc = make_admin('qc', owning_org=cls.org)
        cls.finance = make_admin('finance', owning_org=cls.org)
        cls.partner = make_admin('partner', owning_org=cls.org)
        cls.stranger = 'stranger@example.test'
        when = datetime.datetime(2026, 5, 10, 4, 0, tzinfo=UTC)

        def decided(cohort, by, **kw):
            return make_application('awaiting_qc', outcome='recommend', cohort=cohort,
                                    ai_verdict_snapshot=snap(), officer_verdict=officer(**kw),
                                    verdict_decided_by=by, verdict_decided_at=when,
                                    ai_verdict_engine_version='v1')

        cls.a1 = decided(cls.cohort, cls.reviewer.email, identity='fail')
        cls.a2 = decided(cls.cohort, cls.reviewer.email)
        cls.a3 = decided(cls.cohort2, cls.stranger)
        cls.f1 = decided(cls.foreign, cls.reviewer.email)

        def qc(app, decision, at):
            StaffActivity.objects.create(
                actor=cls.qc, verb='qc_decision', subject_type='application', subject_id=app.id,
                meta={'decision': decision}, created_at=at)

        qc(cls.a1, 'accept', datetime.datetime(2026, 5, 31, 17, 0, tzinfo=UTC))   # 1 Jun in KL
        qc(cls.a1, 'reopen', datetime.datetime(2026, 5, 20, 3, 0, tzinfo=UTC))
        qc(cls.a2, 'accept', datetime.datetime(2026, 5, 21, 3, 0, tzinfo=UTC))
        qc(cls.a3, 'reject', datetime.datetime(2026, 5, 22, 3, 0, tzinfo=UTC))
        qc(cls.f1, 'accept', datetime.datetime(2026, 5, 23, 3, 0, tzinfo=UTC))   # another tenant

    def get(self, who, url=METRICS):
        return authed_client(who).get(url)

    def _assign(self, admin, *apps):
        from apps.scholarship.models import ScholarshipApplication
        ScholarshipApplication.objects.filter(pk__in=[a.pk for a in apps]).update(assigned_to=admin)

    def _both(self, who):
        return self.get(who).json(), self.get(who, OVERVIEW).json()['ai_prediction']

    # ── F4: who sees what (the server decides) ────────────────────────────────────────────────
    def test_a_reviewer_gets_no_ai_prediction_at_all(self):
        self._assign(self.reviewer, self.a1, self.a2)
        self.assertEqual(self.get(self.reviewer).status_code, 403)
        page = self.get(self.reviewer, OVERVIEW)
        if page.status_code == 200:
            self.assertNotIn('ai_prediction', page.json()['sections'])
            self.assertNotIn('ai_prediction', page.json())

    def test_a_finance_user_granted_review_is_refused_like_a_reviewer(self):
        fin = make_admin('finance', owning_org=self.org, permissions=['review'])
        self._assign(fin, self.a2)
        self.assertEqual(self.get(fin).status_code, 403)

    def test_an_org_admin_gets_score_and_reviewers_but_no_ai_team_fold(self):
        for body in self._both(self.lead):
            self.assertEqual(set(body), {'applications', 'score', 'by_reviewer'})
            self.assertNotIn('by_version', body['score'])

    def test_qc_and_a_view_only_admin_get_the_score_only(self):
        viewer = make_admin('admin', owning_org=self.org)
        for who in (self.qc, viewer):
            for body in self._both(who):
                self.assertEqual(set(body), {'applications', 'score'})
                self.assertEqual(body['applications'], 3)

    def test_the_super_gets_the_ai_team_fold(self):
        for body in self._both(self.super):
            self.assertEqual(set(body), {'applications', 'score', 'by_reviewer', 'ai_team'})
            self.assertEqual(set(body['ai_team']), {'doubt_codes', 'by_version'})
            self.assertEqual([v['version'] for v in body['ai_team']['by_version']], ['v1'])
            self.assertEqual(body['ai_team']['by_version'][0]['facts'], 16)

    # ── the score ─────────────────────────────────────────────────────────────────────────────
    def test_the_score_is_fenced_and_marks_every_decided_fact(self):
        m = self.get(self.lead).json()['score']
        # 3 applications x 4 facts, all Certain; a1 failed identity: 11 x +2, 1 x -10
        self.assertEqual((m['facts'], m['points'], m['best'], m['score_pct'], m['lost']), (12, 12, 24, 50, -10))
        self.assertEqual(m['most_lost'], {'fact': 'identity', 'points': -10})
        self.assertEqual(m['by_fact']['identity']['top_reasons'], [{'key': 'fail:not_given', 'points': -10}])

    def test_a_reject_before_interview_is_never_scored(self):
        """Its facts sit on the case WITHOUT `verdict_decided_at` (and on the `declined` row)."""
        before = self.get(self.lead).json()
        app = make_application('profile_complete', cohort=self.cohort)
        r = authed_client(self.lead).post(
            f'/api/v1/admin/scholarship/applications/{app.pk}/reject-before-interview/',
            {'reason': 'not_b40', 'comments': 'Income above the band.', 'facts': officer(identity='fail'),
             'fail_reasons': {'identity': 'proof_missing'}}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        app.refresh_from_db()
        self.assertEqual(app.status, 'rejected')
        self.assertTrue(app.ai_verdict_snapshot)            # the facts ARE on the case...
        self.assertIsNone(app.verdict_decided_at)           # ...without the reviewer's stamp
        self.assertTrue(StaffActivity.objects.filter(verb='declined', subject_id=app.pk).exists())
        after = self.get(self.lead).json()
        self.assertEqual(after['applications'], before['applications'])
        self.assertEqual(after['score'], before['score'])

    def test_a_super_reads_every_organisation(self):
        self.assertEqual(self.get(self.super).json()['applications'], 4)

    # ── by_reviewer: leads only, never an email ───────────────────────────────────────────────
    def test_by_reviewer_for_the_lead_tier_without_emails(self):
        for who in (self.lead, self.super):
            body = self.get(who).json()
            rows = body['by_reviewer']
            self.assertNotIn('@', str(body))
            named = [r for r in rows if r['id'] == self.reviewer.pk]
            self.assertEqual(len(named), 1)
            self.assertEqual(named[0]['name'], 'Rita Reviewer')
            self.assertEqual(named[0]['label_key'], None)
            self.assertEqual(named[0]['green_failed'], 1)
        rows = self.get(self.lead).json()['by_reviewer']
        self.assertEqual([r['id'] for r in rows], [self.reviewer.pk, None])   # biggest green_failed first
        self.assertEqual(rows[1]['label_key'], 'unmatched_reviewer')
        self.assertEqual(rows[1]['name'], '')

    def test_by_reviewer_counts_qc_accepted_and_sent_back(self):
        rows = {r['id']: r for r in self.get(self.lead).json()['by_reviewer']}
        self.assertEqual((rows[self.reviewer.pk]['qc_accepted'], rows[self.reviewer.pk]['qc_sent_back']), (2, 1))
        self.assertEqual((rows[None]['qc_accepted'], rows[None]['qc_sent_back']), (0, 0))   # a3: a reject only

    def test_by_reviewer_follows_the_cohort_narrowing(self):
        rows = self.get(self.lead, f'{METRICS}?cohort={self.cohort2.id}').json()['by_reviewer']
        self.assertEqual([(r['id'], r['applications']) for r in rows], [(None, 1)])

    # ── the other tenant ──────────────────────────────────────────────────────────────────────
    def test_an_organisation_b_lead_never_receives_organisation_a_data(self):
        lead_b = make_admin('org_admin', owning_org=self.other, name='Bea Lead')
        for body in self._both(lead_b):
            self.assertEqual(body['applications'], 1)
            self.assertEqual(sum(r['qc_accepted'] for r in body['by_reviewer']), 1)   # f1's row only
            self.assertNotIn('Rita Reviewer', str(body))

    def test_the_staff_name_lookup_is_fenced_to_the_organisation(self):
        # a recorder email that is staff ONLY in organisation B, on an organisation A application
        make_admin('reviewer', owning_org=self.other, name='Other Org Namesake',
                   email='b-staff@example.test')
        make_application('awaiting_qc', outcome='recommend', cohort=self.cohort,
                         ai_verdict_snapshot=snap(), officer_verdict=officer(),
                         verdict_decided_by='b-staff@example.test',
                         verdict_decided_at=datetime.datetime(2026, 5, 11, 4, 0, tzinfo=UTC),
                         ai_verdict_engine_version='v1')
        rows = self.get(self.lead).json()['by_reviewer']
        self.assertNotIn('Other Org Namesake', str(rows))
        self.assertEqual(sum(r['applications'] for r in rows if r['label_key'] == 'unmatched_reviewer'), 2)
        # an organisation-less super keeps the unfiltered lookup
        self.assertIn('Other Org Namesake', str(self.get(self.super).json()['by_reviewer']))

    def test_a_reviewer_partner_or_finance_counts_nothing_when_metrics_is_called_directly(self):
        from apps.scholarship.models import ScholarshipApplication
        from apps.scholarship.prediction_metrics import metrics
        self._assign(self.reviewer, self.a1)
        for who in (self.partner, self.finance, self.reviewer):
            body = metrics(ScholarshipApplication.objects.all(), who)
            self.assertEqual(body['applications'], 0)
            self.assertEqual(body['score']['facts'], 0)
            self.assertNotIn('ai_team', body)

    def test_an_organisationless_lead_matches_no_staff_name(self):
        from apps.scholarship.models import ScholarshipApplication
        from apps.scholarship.prediction_metrics import metrics
        orphan = make_admin('org_admin', owning_org=None)
        make_application('awaiting_qc', outcome='recommend', cohort=self.cohort,
                         ai_verdict_snapshot=snap(), officer_verdict=officer(),
                         verdict_decided_by=self.super.email,
                         verdict_decided_at=datetime.datetime(2026, 5, 11, 4, 0, tzinfo=UTC),
                         ai_verdict_engine_version='v1')
        rows = metrics(ScholarshipApplication.objects.all(), orphan)['by_reviewer']
        self.assertTrue(rows)
        self.assertEqual({r['label_key'] for r in rows}, {'unmatched_reviewer'})
        self.assertEqual({r['id'] for r in rows}, {None})

    def test_a_non_numeric_cohort_reads_like_an_unknown_one(self):
        unknown = self.get(self.lead, f'{METRICS}?cohort=999999')
        for value in ('abc', '1x', '-1'):
            r = self.get(self.lead, f'{METRICS}?cohort={value}')
            self.assertEqual(r.status_code, unknown.status_code)
            self.assertEqual(r.json()['applications'], 0)

    def test_a_huge_cohort_value_answers_zero_counts_not_an_overflow(self):
        r = self.get(self.lead, f'{METRICS}?cohort=99999999999999999999')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['applications'], 0)

    # ── the gate ──────────────────────────────────────────────────────────────────────────────
    def test_finance_partner_and_reviewer_are_refused(self):
        for who in (self.finance, self.partner, self.reviewer):
            self.assertEqual(self.get(who).status_code, 403)

    # ── the Overview section ──────────────────────────────────────────────────────────────────
    def test_overview_carries_the_same_answer_for_a_lead(self):
        for who in (self.lead, self.super):
            page = self.get(who, OVERVIEW).json()
            self.assertIn('ai_prediction', page['sections'])
            self.assertEqual(page['ai_prediction'], self.get(who).json())
