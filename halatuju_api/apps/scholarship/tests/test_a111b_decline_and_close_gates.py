"""Sprint A1.11b: decline and close pass the right checks (owner rulings 2026-11-07).

TD-487 / SEC-19 (option A): `POST .../reject/ {category: 'interview'}` is refused at EVERY status
(400 `interview_decline_needs_qc`; 'interviewed' keeps TD-481's `awaiting_qc`), super included. An
interview decline goes record-verdict -> submit-decline -> QC. 'contractual' and `org-reject` are
unchanged.

- `TheProbes`              the two TD-487 holes: a case QC reopened to 'interviewing', and a case a super
                           reopened to 'interviewing', could be declined at `/reject/` with no QC. Both
                           are refused now, and nothing moves.
- `EveryStageRefuses`      shortlisted / profile_complete / interviewing, for the assignee, the org admin and
                           a super: refused, nothing written, no email.
- `TheDeclineRoadRemains`  the road that is left is open at profile_complete (assigned) and at interviewing:
                           the interview is submitted, the decline verdict recorded, the decline sent to QC
                           (AWAITING QC), and the QC confirms it. Shortlisted keeps `org-reject`; 'contractual'
                           still declines a recommended case at `/reject/`.

TD-488 (close): the rule's own tests are in test_close_stalled.py (stage_not_closeable at the four
declined-not-closed stages, the set identity, the classification). `CloseClassification` here pins the
one sentence the ruling is: before an award, close works at submitted and recommended only.
"""
from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings

from apps.scholarship import closure, reopen, services
from apps.scholarship.models import InterviewSession, StaffActivity
from apps.scholarship.services import apply_gate
from apps.scholarship.tests import factories
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort,
)

APPS = '/api/v1/admin/scholarship/applications/'
API = dict(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET, DECLINE_COOLOFF_DAYS=0)
REFUSED = 'interview_decline_needs_qc'


def _post(who, app, tail, body=None):
    return authed_client(who).post(f'{APPS}{app.pk}/{tail}/', body or {}, format='json')


def _reject_interview(who, app):
    return _post(who, app, 'reject', {'category': 'interview', 'comments': 'Not selected.'})


class _People(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort()
        cls.org = cls.cohort.owning_organisation
        cls.reviewer = make_admin('reviewer', owning_org=cls.org)
        cls.qc = make_admin('qc', owning_org=cls.org)
        cls.lead = make_admin('org_admin', owning_org=cls.org)
        cls.super = make_admin('super', super_admin=True)

    def setUp(self):
        # The QC decision reads the verdict; these fixtures carry no documents.
        patcher = mock.patch('apps.scholarship.views_admin.verdict.build_verdict', return_value=[])
        patcher.start()
        self.addCleanup(patcher.stop)

    def assertRefusedAndUntouched(self, r, app, was):
        self.assertEqual(r.status_code, 400, r.content[:300])
        self.assertEqual(r.json()['code'], REFUSED)
        self.assertIn('Quality check', r.json()['error'])
        app.refresh_from_db()
        self.assertEqual(app.status, was)
        self.assertIsNone(app.rejected_at)
        self.assertEqual((app.rejected_by, app.rejection_category, app.rejection_comments),
                         ('', '', ''))
        self.assertEqual((app.pending_rejection_category, app.pre_decline_status), ('', ''))
        self.assertEqual(mail.outbox, [])
        self.assertFalse(StaffActivity.objects.filter(
            subject_type='application', subject_id=app.pk, verb='declined').exists())


@override_settings(**API)
class TheProbes(_People):

    def test_qc_reopen_to_interviewing_then_reject_is_refused(self):
        app = make_application('awaiting_qc', outcome='decline', cohort=self.cohort,
                               reviewer=self.reviewer)
        r = _post(self.qc, app, 'qc-decision', {'decision': 'reopen', 'comments': 'Ask again.'})
        self.assertEqual(r.status_code, 200, r.content[:300])
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewing')
        mail.outbox.clear()
        for who in (self.reviewer, self.lead, self.super):
            with self.subTest(who=who.role):
                self.assertRefusedAndUntouched(_reject_interview(who, app), app, 'interviewing')

    def test_super_reopen_decision_then_reject_is_refused(self):
        app = make_application('awaiting_qc', outcome='decline', cohort=self.cohort,
                               reviewer=self.reviewer)
        reopen.reopen_decision(app, by_admin=self.super, reason='The income was misread.')
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewing')
        mail.outbox.clear()
        for who in (self.reviewer, self.super):
            with self.subTest(who=who.role):
                self.assertRefusedAndUntouched(_reject_interview(who, app), app, 'interviewing')
        app.refresh_from_db()
        self.assertIsNotNone(app.decision_reopened_at)          # the reopen is still open


@override_settings(**API)
class EveryStageRefuses(_People):

    def test_shortlisted_profile_complete_and_interviewing(self):
        for stage, status in (('shortlisted', 'shortlisted'), ('assigned', 'profile_complete'),
                              ('interviewing', 'interviewing')):
            for who in (self.reviewer, self.lead, self.super):
                if stage == 'shortlisted' and who is self.reviewer:
                    continue                                        # no assignee yet
                with self.subTest(status=status, who=who.role):
                    app = make_application(stage, cohort=self.cohort,
                                           reviewer=None if stage == 'shortlisted' else self.reviewer)
                    mail.outbox.clear()
                    self.assertRefusedAndUntouched(_reject_interview(who, app), app, status)

    def test_awaiting_qc_keeps_its_own_code(self):
        app = make_application('awaiting_qc', outcome='decline', cohort=self.cohort,
                               reviewer=self.reviewer)
        r = _reject_interview(self.super, app)
        self.assertEqual((r.status_code, r.json()['code']), (400, 'awaiting_qc'))


@override_settings(**API)
class TheDeclineRoadRemains(_People):

    def _submit_interview(self, app):
        services.submit_interview(InterviewSession.objects.create(
            application=app, interviewer=self.reviewer, status='draft',
            findings=factories.answered_findings(app)))
        app.refresh_from_db()

    def _decline_through_qc(self, app):
        r = _post(self.reviewer, app, 'record-verdict', {'officer_verdict': factories.DECLINE_VERDICT})
        self.assertEqual(r.status_code, 200, r.content[:300])
        r = _post(self.reviewer, app, 'submit-decline')
        self.assertEqual(r.status_code, 200, r.content[:300])
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewed')                 # AWAITING QC
        r = _post(self.qc, app, 'qc-decision', {'decision': 'accept'})
        self.assertEqual(r.status_code, 200, r.content[:300])
        app.refresh_from_db()
        self.assertEqual((app.status, app.rejection_category), ('rejected', 'interview'))
        self.assertEqual(app.rejected_by, self.qc.email)

    def test_from_profile_complete(self):
        app = make_application('assigned', cohort=self.cohort, reviewer=self.reviewer)
        self.assertEqual(app.status, 'profile_complete')
        self._submit_interview(app)
        self.assertEqual(app.status, 'interviewing')
        self._decline_through_qc(app)

    def test_from_interviewing(self):
        app = make_application('interviewing', cohort=self.cohort, reviewer=self.reviewer)
        self._submit_interview(app)
        self._decline_through_qc(app)

    def test_shortlisted_keeps_org_reject_and_recommended_keeps_contractual(self):
        app = make_application('shortlisted', cohort=self.cohort)
        r = _post(self.lead, app, 'org-reject', {'comments': 'Never sent the documents.'})
        self.assertEqual(r.status_code, 200, r.content[:300])
        app.refresh_from_db()
        self.assertEqual((app.status, app.rejection_category), ('rejected', 'incomplete'))
        app = make_application('recommended', cohort=self.cohort, reviewer=self.reviewer)
        r = _post(self.reviewer, app, 'reject', {'category': 'contractual', 'comments': 'No reply.'})
        self.assertEqual(r.status_code, 200, r.content[:300])
        app.refresh_from_db()
        self.assertEqual((app.status, app.rejection_category), ('rejected', 'contractual'))


class CloseClassification(TestCase):

    def test_before_an_award_close_works_at_submitted_and_recommended_only(self):
        closeable = {s for s in closure.PRE_AWARD_STATUSES if s in closure.CLOSEABLE_FROM}
        self.assertEqual(closeable, {'submitted', 'recommended'})
        self.assertEqual(closure.PRE_AWARD_STATUSES - closeable,
                         {'shortlisted', 'profile_complete', 'interviewing', 'interviewed'})
        # Every in-play status is pre- or post-award, and every post-award status still closes.
        self.assertEqual(closure.PRE_AWARD_STATUSES | closure.POST_AWARD_STATUSES,
                         apply_gate.IN_PLAY_STATUSES)
        self.assertLessEqual(closure.POST_AWARD_STATUSES, closure.CLOSEABLE_FROM)
