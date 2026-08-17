"""A closed case takes no more review writes — 2026-08-18.

`_require_app_write` has no status gate, and the five review-track endpoints below were the
only per-application writes that needed one. On an application that expired, or was rejected
by an org admin before anybody reviewed it, every one of them answered 200:

  * `record-verdict` stamped `verdict_decided_at`, `officer_verdict` and — on accept — an
    `award_amount`, onto a rejected file. That is the defect the 2026-07-30 sprint fixed from
    the decline side ("a rejected application no longer holds an award amount"), reachable
    here through a door nobody had closed. `verify-accept` refuses on status, but it runs
    SECOND: the writes had already landed by the time it 400s.
  * `interview/` and `interview/submit/` created and submitted a real InterviewSession.
  * `suggest-gaps/` spent a billable Gemini call.

44 production applications were showing the controls that reach these (24 expired, 20 rejected
with no verdict); none had ever held an interview, so nothing had been written yet.

⚠ THE NEGATIVE HALF IS THE POINT OF THIS FILE, not decoration. A guard that refuses everything
passes every "it refuses" test ever written, and would strand the entire live review queue. Two
classes below exist solely to prove the guard is narrow: the live stages still accept each
endpoint, and a REOPENED rejected case does too.
"""
import re
from pathlib import Path

import jwt
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient
from django.utils import timezone

from apps.courses.models import PartnerAdmin, PartnerOrganisation, StudentProfile
from apps.scholarship.models import InterviewSession, ScholarshipApplication, ScholarshipCohort
from apps.scholarship.services import CASE_CLOSED_STATES, review_writes_closed

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
SUPER = 'cc-su'

# Every endpoint that writes into the review track, with a body it would otherwise accept.
# Adding a sixth review-track write means adding it here, or its refusal is untested.
REVIEW_WRITES = (
    ('suggest-gaps/', {}),
    ('interview/', {'findings': {}, 'rubric': {}, 'overall_note': 'A finding.'}),
    ('interview/submit/', {}),
    ('interview/reopen/', {}),
    ('record-verdict/', {
        'officer_verdict': {'identity': 'pass', 'academic': 'pass', 'pathway': 'pass',
                            'income': 'pass', 'overall': 'accept'},
        'reason': 'A recorded justification.',
    }),
)


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


class TestReviewWritesClosed(TestCase):
    """The predicate itself, independent of any endpoint."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='cc', name='B40', year=2026)

    _seq = 0

    def _app(self, status, **kw):
        type(self)._seq += 1
        profile = StudentProfile.objects.create(
            supabase_user_id=f'cc-{status}-{type(self)._seq}', name='Priya')
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=profile, status=status, **kw)

    def test_the_three_terminal_off_ramps_are_closed(self):
        for status in CASE_CLOSED_STATES:
            with self.subTest(status=status):
                self.assertTrue(review_writes_closed(self._app(status)))

    def test_every_other_status_stays_open(self):
        # The negative half. Named individually rather than derived from STATUS_CHOICES minus
        # the closed set, so adding a status to the model surfaces here as a decision.
        for status in ('submitted', 'shortlisted', 'profile_complete', 'interviewing',
                       'interviewed', 'recommended', 'awarded', 'active', 'maintenance',
                       'closed'):
            with self.subTest(status=status):
                self.assertFalse(review_writes_closed(self._app(status)))

    def test_closed_is_NOT_treated_as_a_terminal_off_ramp(self):
        """`closed` is the successful end of a FUNDED lifecycle, not a dead review. Its writes
        (disbursement, closure) belong to other endpoints with their own gates, and a sweep for
        "statuses that mean the end" would wrongly add it here."""
        self.assertNotIn('closed', CASE_CLOSED_STATES)

    def test_a_REOPENED_rejected_case_is_open(self):
        """reopen.reopen_decision does not remap 'rejected' — a super who reopens a rejected
        decision leaves the case AT 'rejected' with decision_reopened_at set, and is expected
        to re-record the verdict. Keying on status alone would refuse exactly that write."""
        app = self._app('rejected', decision_reopened_at=timezone.now())
        self.assertFalse(review_writes_closed(app))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestClosedCaseRefusesEveryReviewWrite(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(name='BrightPath', code='bp')
        cls.cohort = ScholarshipCohort.objects.create(
            code='cc-e', name='B40', year=2026, owning_organisation=cls.org)
        PartnerAdmin.objects.create(
            supabase_user_id=SUPER, role='super', is_super_admin=True, is_active=True,
            name='SU', email='su@x.com')

    _seq = 0

    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(SUPER)}')

    def _app(self, status, **kw):
        type(self)._seq += 1
        profile = StudentProfile.objects.create(
            supabase_user_id=f'cce-{status}-{type(self)._seq}', name='Priya')
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=profile, status=status, notify_email='s@x.com', **kw)

    def _post(self, app, suffix, body):
        return self.client.post(
            f'/api/v1/admin/scholarship/applications/{app.id}/{suffix}', body, format='json')

    def test_every_review_write_is_refused_on_every_off_ramp(self):
        for status in CASE_CLOSED_STATES:
            for suffix, body in REVIEW_WRITES:
                with self.subTest(status=status, endpoint=suffix):
                    app = self._app(status)
                    res = self._post(app, suffix, body)
                    self.assertEqual(res.status_code, 400)
                    self.assertEqual(res.json()['code'], 'case_closed')

    def test_the_refusal_names_the_status_so_the_message_can_be_specific(self):
        """A predicate that folds several reasons into one False makes its caller state the
        wrong one (lessons.md, request #10). This one carries the status back."""
        res = self._post(self._app('expired'), 'record-verdict/', REVIEW_WRITES[-1][1])
        self.assertEqual(res.json()['status'], 'expired')

    def test_nothing_is_written_when_a_verdict_post_is_refused(self):
        """The defect in one assertion: the verdict endpoint used to stamp the decision AND an
        award amount before verify-accept could object."""
        app = self._app('rejected')
        self._post(app, 'record-verdict/', REVIEW_WRITES[-1][1])
        app.refresh_from_db()
        self.assertIsNone(app.verdict_decided_at)
        self.assertEqual(app.officer_verdict, {})
        self.assertIsNone(app.award_amount)

    def test_no_interview_session_is_created_when_a_draft_post_is_refused(self):
        app = self._app('expired')
        self._post(app, 'interview/', REVIEW_WRITES[1][1])
        self.assertFalse(InterviewSession.objects.filter(application=app).exists())


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheGuardIsNarrow(TestCase):
    """The negative half at the endpoint level: the guard must not refuse a live case.

    Each endpoint is asked for a response that is NOT `case_closed`. What it answers instead
    varies (a draft save succeeds; reopen refuses with `no_submitted_interview`) and is that
    endpoint's own business — this class asserts only that the new guard did not fire.
    """

    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(name='BrightPath', code='bp')
        cls.cohort = ScholarshipCohort.objects.create(
            code='cc-n', name='B40', year=2026, owning_organisation=cls.org)
        PartnerAdmin.objects.create(
            supabase_user_id=SUPER, role='super', is_super_admin=True, is_active=True,
            name='SU', email='su@x.com')

    _seq = 0

    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(SUPER)}')

    def _app(self, status, **kw):
        type(self)._seq += 1
        profile = StudentProfile.objects.create(
            supabase_user_id=f'ccn-{status}-{type(self)._seq}', name='Priya')
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=profile, status=status, notify_email='s@x.com', **kw)

    def _code(self, app, suffix, body):
        res = self.client.post(
            f'/api/v1/admin/scholarship/applications/{app.id}/{suffix}', body, format='json')
        body = res.json() if res.status_code != 204 else {}
        return body.get('code') if isinstance(body, dict) else None

    def test_the_live_review_stages_still_reach_every_endpoint(self):
        for status in ('profile_complete', 'interviewing', 'interviewed'):
            for suffix, body in REVIEW_WRITES:
                with self.subTest(status=status, endpoint=suffix):
                    app = self._app(status)
                    self.assertNotEqual(self._code(app, suffix, body), 'case_closed')

    def test_a_reopened_rejected_case_can_still_be_re_decided(self):
        """The one write reopen exists to permit. Status reads 'rejected' throughout."""
        app = self._app('rejected', decision_reopened_at=timezone.now())
        self.assertNotEqual(self._code(app, 'record-verdict/', REVIEW_WRITES[-1][1]),
                            'case_closed')

    def test_an_interview_draft_still_SAVES_on_a_live_case(self):
        """Not merely "not refused" — the ordinary path still works end to end."""
        app = self._app('interviewing')
        res = self.client.post(
            f'/api/v1/admin/scholarship/applications/{app.id}/interview/',
            REVIEW_WRITES[1][1], format='json')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(InterviewSession.objects.filter(application=app).exists())


_COCKPIT_TS = (Path(__file__).resolve().parents[4]
               / 'halatuju-web' / 'src' / 'lib' / 'officerCockpit.ts')


class TestTheCockpitMirrorsThisSet(SimpleTestCase):
    """The offer-set and the accept-set are one unit of change (lessons.md, 2026-07-16).

    If the cockpit's `CASE_CLOSED_STATES` drifts from this one, the screen either offers a
    control the endpoint refuses, or hides a control the endpoint would have accepted. Both
    are silent. Parsed from source and FAILS LOUDLY if the file cannot be read — a skipped
    drift test is how the 64-subject drift shipped (see test_subject_drift.py).
    """

    def test_the_two_closed_sets_are_identical(self):
        if not _COCKPIT_TS.exists():
            raise AssertionError(
                f'officerCockpit.ts not found at {_COCKPIT_TS} — this guard needs the monorepo '
                f'layout. Do NOT convert it to a skip.')
        text = _COCKPIT_TS.read_text(encoding='utf-8')
        match = re.search(r'CASE_CLOSED_STATES\s*=\s*new Set<string>\(\[([^\]]*)\]\)', text)
        self.assertIsNotNone(
            match, 'could not find CASE_CLOSED_STATES in officerCockpit.ts — if it was renamed, '
                   'rename it here too rather than deleting this guard')
        self.assertEqual(set(re.findall(r"'([^']+)'", match.group(1))),
                         set(CASE_CLOSED_STATES))
