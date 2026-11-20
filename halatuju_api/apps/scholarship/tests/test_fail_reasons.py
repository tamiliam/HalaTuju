"""LL2 (server) - the reason for failing a fact the engine called green.

The code list and filter (`fail_reasons`), `record-verdict` storing it inside `officer_verdict`, the
key reaching the admin detail, and the per-fact counts in the metrics (endpoint and Overview section).
All data is made up; only codes, fact names and counts.
"""
import datetime
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings

from apps.scholarship import audit
from apps.scholarship import fail_reasons as fr
from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
    make_programme,
)

METRICS = '/api/v1/admin/scholarship/verdict-metrics/'
OVERVIEW = '/api/v1/admin/scholarship/programme-overview/'
UTC = datetime.timezone.utc
VIEW = 'apps.scholarship.views_admin.verdict.build_verdict'


def snap(statuses=None):
    statuses = statuses or {}
    return [{'fact': f, 'status': statuses.get(f, 'verified'), 'evidence': [], 'unresolved': []}
            for f in audit.FACTS]


def officer(**kw):
    v = {f: 'pass' for f in audit.FACTS}
    v.update(kw)
    return v


class TestCodesAndFilter(SimpleTestCase):
    def test_the_fixed_list(self):
        self.assertEqual(fr.CODES, ('engine_wrong', 'read_wrong', 'new_information',
                                    'programme_rule', 'other'))

    def test_validate_shapes(self):
        self.assertEqual(fr.validate(None), {})
        self.assertEqual(fr.validate({'income': 'other'}), {'income': 'other'})
        for bad in ([], 'x', 3, {'income': 'nope'}, {'colour': 'other'}, {'income': 3},
                    {'income': None}, {'income': ['other']}):
            with self.subTest(bad=bad), self.assertRaises(fr.BadFailReasons):
                fr.validate(bad)

    def test_keep_only_fail_on_a_verified_fact(self):
        reasons = {'income': 'other', 'identity': 'other', 'academic': 'other'}
        got = fr.keep(reasons, officer(income='fail', academic='fail'), snap({'academic': 'review'}))
        self.assertEqual(got, {'income': 'other'})   # identity passed; academic was not green


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestRecordVerdict(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort()
        cls.reviewer = make_admin('reviewer', owning_org=cls.cohort.owning_organisation)

    def setUp(self):
        self.app = make_application('awaiting_qc', outcome='recommend', cohort=self.cohort,
                                    reviewer=self.reviewer)

    def _post(self, verdict, **extra):
        body = {'officer_verdict': {**officer(), 'overall': 'hold', **verdict}, 'reason': 'Made up.'}
        body.update(extra)
        with mock.patch(VIEW, return_value=snap({'academic': 'review'})):
            return authed_client(self.reviewer).post(
                f'/api/v1/admin/scholarship/applications/{self.app.pk}/record-verdict/',
                body, format='json')

    def _stored(self):
        return ScholarshipApplication.objects.get(pk=self.app.pk).officer_verdict

    def test_a_valid_reason_is_saved_and_reaches_the_detail(self):
        r = self._post({'income': 'fail'}, fail_reasons={'income': 'new_information'})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._stored()['fail_reasons'], {'income': 'new_information'})
        self.assertEqual(r.json()['officer_verdict']['fail_reasons'], {'income': 'new_information'})
        detail = authed_client(self.reviewer).get(
            f'/api/v1/admin/scholarship/applications/{self.app.pk}/')
        self.assertEqual(detail.json()['officer_verdict']['fail_reasons'],
                         {'income': 'new_information'})

    def test_bad_input_is_a_400_and_nothing_is_saved(self):
        before = ScholarshipApplication.objects.get(pk=self.app.pk).verdict_decided_at
        for bad in ({'income': 'nope'}, {'colour': 'other'}, ['income'], 'income', {'income': 3}):
            with self.subTest(bad=bad):
                r = self._post({'income': 'fail'}, fail_reasons=bad)
                self.assertEqual(r.status_code, 400)
                self.assertEqual(r.json()['code'], 'bad_fail_reasons')
                app = ScholarshipApplication.objects.get(pk=self.app.pk)
                self.assertEqual(app.verdict_decided_at, before)
                self.assertNotIn('fail_reasons', app.officer_verdict)

    def test_no_reason_still_saves(self):
        for extra in ({}, {'fail_reasons': {}}, {'fail_reasons': None}):
            with self.subTest(extra=extra):
                r = self._post({'income': 'fail'}, **extra)
                self.assertEqual(r.status_code, 200, r.content)
                self.assertEqual(self._stored()['fail_reasons'], {})
                self.assertEqual(self._stored()['income'], 'fail')

    def test_a_reason_for_a_passed_fact_is_dropped(self):
        r = self._post({'income': 'fail'}, fail_reasons={'income': 'other', 'identity': 'read_wrong'})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._stored()['fail_reasons'], {'income': 'other'})

    def test_a_reason_for_a_fact_the_engine_did_not_call_verified_is_dropped(self):
        r = self._post({'academic': 'fail'}, fail_reasons={'academic': 'engine_wrong'})   # patched: review
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._stored()['academic'], 'fail')
        self.assertEqual(self._stored()['fail_reasons'], {})

    def test_re_recording_replaces_the_reasons(self):
        self._post({'income': 'fail'}, fail_reasons={'income': 'other'})
        self._post({'income': 'pass'}, fail_reasons={'income': 'other'})
        self.assertEqual(self._stored()['fail_reasons'], {})


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestReasonMetrics(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org, cls.other = make_org(), make_org()
        cls.cohort = make_cohort(programme=make_programme(cls.org))
        cls.foreign = make_cohort(programme=make_programme(cls.other))
        cls.lead = make_admin('org_admin', owning_org=cls.org)
        cls.reviewer = make_admin('reviewer', owning_org=cls.org)
        when = datetime.datetime(2026, 5, 10, 4, 0, tzinfo=UTC)

        def decided(cohort, verdict, snapshot=None):
            return make_application('awaiting_qc', outcome='recommend', cohort=cohort,
                                    ai_verdict_snapshot=snapshot or snap(), officer_verdict=verdict,
                                    verdict_decided_by='x@example.test', verdict_decided_at=when,
                                    ai_verdict_engine_version='v1')

        cls.a1 = decided(cls.cohort, officer(income='fail', identity='fail',
                                             fail_reasons={'income': 'new_information',
                                                           'identity': 'read_wrong'}))
        cls.a2 = decided(cls.cohort, officer(income='fail', fail_reasons={'income': 'new_information'}))
        cls.a3 = decided(cls.cohort, officer(income='fail'))   # an OLD row: no key at all
        # academic failed but the engine was not green: never a green -> fail decision
        cls.a4 = decided(cls.cohort, officer(academic='fail', fail_reasons={'academic': 'other'}),
                         snap({'academic': 'review'}))
        cls.f1 = decided(cls.foreign, officer(income='fail', fail_reasons={'income': 'other'}))

    def _get(self, who, url=METRICS):
        return authed_client(who).get(url)

    def test_reason_counts_per_fact_with_not_given(self):
        body = self._get(self.lead).json()
        income = body['fail_reasons']['income']
        self.assertEqual(income['new_information'], 2)
        self.assertEqual(sum(income.values()), 2)
        self.assertEqual(set(income), set(fr.CODES))
        self.assertEqual(body['fail_reasons']['identity']['read_wrong'], 1)
        self.assertEqual(sum(body['fail_reasons']['academic'].values()), 0)   # not green
        self.assertEqual(body['fail_reasons_not_given'],
                         {'identity': 0, 'academic': 0, 'pathway': 0, 'income': 1})
        self.assertEqual(body['fact_counts']['income']['green_failed'], 3)    # 2 given + 1 not given

    def test_the_overview_carries_the_same_object_and_the_fence_holds(self):
        page = self._get(self.lead, OVERVIEW).json()['ai_prediction']
        self.assertEqual(page['fail_reasons'], self._get(self.lead).json()['fail_reasons'])
        self.assertEqual(page['fail_reasons']['income']['other'], 0)   # the other tenant's tap

    def test_a_reviewer_sees_only_their_assigned_applicants(self):
        ScholarshipApplication.objects.filter(pk=self.a2.pk).update(assigned_to=self.reviewer)
        for body in (self._get(self.reviewer).json(), self._get(self.reviewer, OVERVIEW).json()['ai_prediction']):
            self.assertEqual(body['fail_reasons']['income']['new_information'], 1)
            self.assertEqual(body['fail_reasons_not_given']['income'], 0)
            self.assertNotIn('by_reviewer', body)

    def test_an_old_row_without_the_key_counts_as_not_given(self):
        m = audit.override_metrics([(snap(), officer(income='fail'), 'v'),
                                    (snap(), {'income': 'fail', 'fail_reasons': 'garbage'}, 'v'),
                                    (snap(), {'income': 'fail', 'fail_reasons': {'income': 'bogus'}}, 'v')])
        self.assertEqual(m['fail_reasons_not_given']['income'], 3)
        self.assertEqual(sum(m['fail_reasons']['income'].values()), 0)
        self.assertEqual(audit.override_metrics([])['fail_reasons_not_given']['income'], 0)
