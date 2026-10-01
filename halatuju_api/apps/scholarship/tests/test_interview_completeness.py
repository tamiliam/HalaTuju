"""TD-253 — an interview with nothing in it must not wake Approve and Decline (owner, 2026-09-18).

*"I want this to be a conscious decision on their part, and I want it to be complete."* Every item
on the cockpit's interview agenda must carry an answer the reviewer chose — a pressed verdict, a
typed answer (however short: "See conclusion" is legitimate), or a delete. Silence is refused, at
BOTH api doors the reviewer uses: submitting the findings, and recording Approve/Decline.

The backward repair is pinned too: the rule binds from the day it ships. A case awaiting QC (#32,
#140 on 2026-09-18) and a case whose decision is already recorded are untouched; a case still in
the reviewer's hands is refused until complete — and its reviewer can reopen and complete it.
"""
import re
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from apps.scholarship.interview_completeness import (
    CHECK2_OWNED_ANOMALIES, agenda_keys, decision_gate_applies, is_answered, missing_agenda_items,
)
from apps.scholarship.models import InterviewSession, ResolutionItem, SponsorProfile
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, answered_findings, authed_client, make_admin, make_application, make_cohort,
)

_SHARED_TSX = (Path(__file__).resolve().parents[4] / 'halatuju-web' / 'src' / 'app' / 'admin'
               / 'scholarship' / '[id]' / 'view' / 'shared.tsx')

_MOTIVATION = 'motivation:motivation_grit'
_ANOMALIES = 'apps.scholarship.views_admin.interviews.detect_anomalies'
_ACCEPT = {'identity': 'pass', 'academic': 'pass', 'income': 'pass', 'pathway': 'pass',
           'overall': 'accept'}
_DECLINE = {**_ACCEPT, 'income': 'fail', 'overall': 'decline'}


class TestTheServerCopyOfTheCheck2MapMatchesTheCockpit(SimpleTestCase):
    """The agenda the server checks must be the agenda the reviewer SEES. The cockpit drops an
    anomaly from the agenda while Check 2 is already asking it (`ANOMALY_CHECK2_OWNER`); if the
    server's copy drifts, a submit is refused over a question nobody can see, or an item she can
    see goes unchecked. Parsed from source and FAILS LOUDLY if the file cannot be read."""

    def test_the_two_maps_are_identical(self):
        self.assertTrue(_SHARED_TSX.exists(), f'{_SHARED_TSX} is missing — the cockpit map moved; '
                        'point this test at its new home, never skip it')
        text = _SHARED_TSX.read_text(encoding='utf-8').replace('\r\n', '\n')
        block = re.search(r'ANOMALY_CHECK2_OWNER[^{]*\{(.*?)\n\}', text, re.S)
        self.assertIsNotNone(block, 'ANOMALY_CHECK2_OWNER is no longer an object literal in '
                             'shared.tsx — re-read it and update this parser')
        web = dict(re.findall(r"(\w+):\s*'(\w+)'", block.group(1)))
        self.assertGreaterEqual(len(web), 4, 'the parser found fewer entries than the 4 it found '
                                'on 2026-10-01 — it is reading less, not the map shrinking')
        self.assertEqual(web, CHECK2_OWNED_ANOMALIES)


class TestWhatCountsAsAnAnswer(SimpleTestCase):
    def test_a_pressed_verdict_is_an_answer_with_no_words(self):
        for verdict in ('resolved', 'still_unclear', 'new_concern'):
            self.assertTrue(is_answered({'verdict': verdict, 'rationale': ''}), verdict)

    def test_a_short_typed_answer_is_an_answer(self):
        self.assertTrue(is_answered({'verdict': '', 'rationale': 'See conclusion'}))

    def test_silence_is_not(self):
        for finding in (None, {}, {'verdict': '', 'rationale': ''},
                        {'verdict': '', 'rationale': '   '}, 'resolved'):
            self.assertFalse(is_answered(finding), finding)

    #: Review F6. The SAME table is in `interviewCompleteness.test.ts`; both sides must agree on
    #: every row. Invisible characters are silence, whichever side reads them.
    BLANKS = ['\ufeff', '\u200b', '\u200c', '\u200d', '\xa0', '\u3000', '\u2028', '\t\n',
              ' \ufeff\u200b ', '\x1c', '\x85']
    ANSWERS = ['x', '\ufeffok', ' See conclusion\u200b']

    def test_invisible_characters_are_silence(self):
        for text in self.BLANKS:
            self.assertFalse(is_answered({'verdict': '', 'rationale': text}), repr(text))

    def test_a_visible_character_beside_them_is_an_answer(self):
        for text in self.ANSWERS:
            self.assertTrue(is_answered({'verdict': '', 'rationale': text}), repr(text))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheAgendaIsTheCockpitsAgenda(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort()

    def test_the_standing_motivation_section_is_always_owed(self):
        app = make_application('interviewing', cohort=self.cohort)
        self.assertIn(_MOTIVATION, agenda_keys(app))
        self.assertIn(_MOTIVATION, missing_agenda_items(app, {}))

    def test_anomalies_ai_gaps_and_the_suppressions(self):
        app = make_application('interviewing', cohort=self.cohort,
                               interview_gaps=[{'code': 'gap_one', 'question': 'Q?', 'why': 'W'}])
        ResolutionItem.objects.create(application=app, code='device_status_unknown',
                                      source='check2', kind='clarify')
        flags = [{'code': c, 'params': {}} for c in
                 ('household_size_one', 'device_in_funding', 'vision_nric_mismatch',
                  'utility_holder_unknown')]
        with patch(_ANOMALIES, return_value=flags):
            keys = agenda_keys(app)
        self.assertIn('household_size_one', keys)
        self.assertIn('utility_holder_unknown', keys)      # its Check-2 query is NOT open
        self.assertNotIn('device_in_funding', keys)        # Check 2 is already asking it
        self.assertNotIn('vision_nric_mismatch', keys)     # the serializer dedupes it
        self.assertIn('gap_one', keys)                     # the stored AI gap
        self.assertIn(_MOTIVATION, keys)

    def test_a_deleted_item_is_not_owed_an_answer(self):
        app = make_application('interviewing', cohort=self.cohort)
        findings = {k: {'verdict': 'deleted', 'rationale': ''} for k in agenda_keys(app)}
        self.assertEqual(missing_agenda_items(app, findings), [])


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestSubmitRefusesSilence(TestCase):
    """The submit door, for every role that can write into the interview."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort()
        org = cls.cohort.owning_organisation
        cls.roles = {
            'super': make_admin('super', super_admin=True),
            'org_admin': make_admin('org_admin', owning_org=org),
            'qc': make_admin('qc', owning_org=org),
            'admin': make_admin('admin', owning_org=org),
            'reviewer': make_admin('reviewer', owning_org=org),
        }

    def _case(self, assignee, findings):
        app = make_application('interviewing', cohort=self.cohort, reviewer=assignee)
        InterviewSession.objects.create(application=app, status='draft', findings=findings,
                                        started_at=timezone.now())
        return app

    def _submit(self, admin, app):
        return authed_client(admin).post(
            f'/api/v1/admin/scholarship/applications/{app.id}/interview/submit/')

    def test_an_empty_interview_is_refused_for_every_role(self):
        for role, admin in self.roles.items():
            with self.subTest(role=role):
                app = self._case(admin, {})
                r = self._submit(admin, app)
                self.assertEqual(r.status_code, 400, r.content)
                self.assertEqual(r.json()['code'], 'findings_incomplete')
                self.assertIn(_MOTIVATION, r.json()['missing'])
                self.assertFalse(app.interview_sessions.filter(status='submitted').exists())

    def test_one_item_left_blank_is_refused_and_named(self):
        admin = self.roles['reviewer']
        app = make_application('interviewing', cohort=self.cohort, reviewer=admin)
        findings = answered_findings(app)
        findings[_MOTIVATION] = {'verdict': '', 'rationale': ''}
        InterviewSession.objects.create(application=app, status='draft', findings=findings)
        r = self._submit(admin, app)
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(r.json()['missing'], [_MOTIVATION])

    def test_see_conclusion_is_a_legitimate_answer(self):
        admin = self.roles['reviewer']
        app = make_application('interviewing', cohort=self.cohort, reviewer=admin)
        findings = {k: {'verdict': '', 'rationale': 'See conclusion'} for k in agenda_keys(app)}
        InterviewSession.objects.create(application=app, status='draft', findings=findings)
        self.assertEqual(self._submit(admin, app).status_code, 200)

    def test_a_complete_interview_submits_for_every_role(self):
        for role, admin in self.roles.items():
            with self.subTest(role=role):
                app = make_application('interviewing', cohort=self.cohort, reviewer=admin)
                InterviewSession.objects.create(application=app, status='draft',
                                                findings=answered_findings(app))
                self.assertEqual(self._submit(admin, app).status_code, 200)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheDecisionDoorAndTheBackwardRepair(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort()
        org = cls.cohort.owning_organisation
        cls.reviewer = make_admin('reviewer', owning_org=org)
        cls.qc = make_admin('qc', owning_org=org)
        cls.super = make_admin('super', super_admin=True)

    def _url(self, app, tail):
        return f'/api/v1/admin/scholarship/applications/{app.id}/{tail}/'

    def _record(self, admin, app, verdict):
        return authed_client(admin).post(self._url(app, 'record-verdict'),
                                         {'officer_verdict': verdict, 'reason': 'Because.'},
                                         format='json')

    def _empty_submitted(self, app):
        return InterviewSession.objects.create(application=app, status='submitted',
                                               submitted_at=timezone.now(), findings={})

    def test_a_reviewer_stage_case_cannot_be_decided_on_an_empty_interview(self):
        for verdict in (_ACCEPT, _DECLINE):
            with self.subTest(overall=verdict['overall']):
                app = make_application('interviewing', cohort=self.cohort, reviewer=self.reviewer)
                self._empty_submitted(app)
                r = self._record(self.reviewer, app, verdict)
                self.assertEqual(r.status_code, 400, r.content)
                self.assertEqual(r.json()['code'], 'interview_incomplete')
                self.assertIn(_MOTIVATION, r.json()['missing'])
                app.refresh_from_db()
                self.assertIsNone(app.verdict_decided_at)    # nothing was stamped

    def test_no_submitted_interview_at_all_is_refused(self):
        app = make_application('interviewing', cohort=self.cohort, reviewer=self.reviewer)
        r = self._record(self.reviewer, app, _ACCEPT)
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(r.json()['code'], 'interview_not_submitted')

    def test_the_reviewer_can_reopen_complete_and_then_decide(self):
        app = make_application('interviewing', cohort=self.cohort, reviewer=self.reviewer)
        self._empty_submitted(app)
        client = authed_client(self.reviewer)
        self.assertEqual(client.post(self._url(app, 'interview/reopen')).status_code, 200)
        self.assertEqual(client.post(self._url(app, 'interview'),
                                     {'findings': answered_findings(app)},
                                     format='json').status_code, 200)
        self.assertEqual(client.post(self._url(app, 'interview/submit')).status_code, 200)
        self.assertEqual(self._record(self.reviewer, app, _ACCEPT).status_code, 200)

    def test_a_case_awaiting_qc_is_untouched_on_both_roads(self):
        # #32 and #140 on 2026-09-18: an empty submitted interview, past the reviewer's hands.
        for outcome in ('decline', 'recommend'):
            with self.subTest(outcome=outcome):
                app = make_application('awaiting_qc', outcome=outcome, cohort=self.cohort,
                                       reviewer=self.reviewer)
                self._empty_submitted(app)
                self.assertFalse(decision_gate_applies(app))
                SponsorProfile.objects.create(application=app, anon_markdown='A student.',
                                              anon_blurb='A student.')
                with patch('apps.scholarship.views_admin.verdict.build_verdict', return_value=[]):
                    r = authed_client(self.qc).post(self._url(app, 'qc-decision'),
                                                    {'decision': 'accept'}, format='json')
                self.assertEqual(r.status_code, 200, r.content)

    def test_a_recorded_decision_is_untouched(self):
        # Saved but not yet sent on (the app-144 shape): pressing Approve again re-records the
        # verdict, and the gate must not reach back over a decision made before it existed.
        app = make_application('verdict_recorded', outcome='recommend', cohort=self.cohort,
                               reviewer=self.reviewer)
        self._empty_submitted(app)
        self.assertFalse(decision_gate_applies(app))
        self.assertEqual(self._record(self.reviewer, app, _ACCEPT).status_code, 200)

    def test_a_reopened_decision_is_the_reviewers_again(self):
        app = make_application('verdict_recorded', outcome='recommend', cohort=self.cohort,
                               reviewer=self.reviewer, decision_reopened_at=timezone.now())
        self._empty_submitted(app)
        self.assertTrue(decision_gate_applies(app))
        r = self._record(self.reviewer, app, _ACCEPT)
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(r.json()['code'], 'interview_incomplete')

    def test_hold_or_blank_first_does_not_open_a_door_round_the_gate(self):
        # Review F1: `record-verdict` stamps `verdict_decided_at` for ANY outcome. Read as "a
        # decision is recorded", a hold (or a blank) then an accept skipped the gate: 200, 200.
        for first in ('hold', ''):
            with self.subTest(first=first):
                app = make_application('interviewing', cohort=self.cohort, reviewer=self.reviewer)
                self._empty_submitted(app)
                self.assertEqual(self._record(self.reviewer, app, {**_ACCEPT, 'overall': first})
                                 .status_code, 200)
                app.refresh_from_db()
                self.assertIsNotNone(app.verdict_decided_at)     # the stamp the hole rode on
                self.assertTrue(decision_gate_applies(app))
                r = self._record(self.reviewer, app, _ACCEPT)
                self.assertEqual(r.status_code, 400, r.content)
                self.assertEqual(r.json()['code'], 'interview_incomplete')

    def test_a_recorded_DECLINE_is_exempt_too(self):
        app = make_application('verdict_recorded', outcome='decline', cohort=self.cohort,
                               reviewer=self.reviewer)
        self._empty_submitted(app)
        self.assertFalse(decision_gate_applies(app))
        self.assertEqual(self._record(self.reviewer, app, _DECLINE).status_code, 200)

    def test_hold_is_not_a_decision_and_is_not_gated(self):
        app = make_application('interviewing', cohort=self.cohort, reviewer=self.reviewer)
        self._empty_submitted(app)
        self.assertEqual(self._record(self.reviewer, app, {**_ACCEPT, 'overall': 'hold'})
                         .status_code, 200)
