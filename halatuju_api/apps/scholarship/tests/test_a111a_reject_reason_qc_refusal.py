"""Sprint A1.11a part 2 — TD-227 (a decline at `/reject/` needs a reason, and the record says when it was
not the assigned reviewer's) and TD-483 (the detail read tells the cockpit whether the QC door would
refuse THIS viewer, from the same separation rule, so the web never shows a QC panel the server refuses).

- `RejectNeedsAReason`  — no / blank / non-text reason: 400 `comments_required`, nothing moves, no email,
                          no activity row; a reason is stored verbatim (trimmed) on the case.
- `WhoDeclined`         — `rejected_by_unassigned` is True for the organisation admin and a super, False
                          for the assignee, None for a QC-upheld decline (no reason on the record) and for a
                          case that is not declined.
- `QcRefusalOnDetail`   — `qc_refusal` on the detail read: the door's code for a QC who was assigned before,
                          interviewed, or recorded the verdict; None for a clean QC, a super, a viewer without
                          `qc`, and a case that is not awaiting QC. It always agrees with `qc_separation.refusal`.
"""
from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings

from apps.scholarship import qc_separation
from apps.scholarship.models import AssignmentEvent, InterviewSession, StaffActivity
from apps.scholarship.services import admin_reject
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort,
)

APPS = '/api/v1/admin/scholarship/applications/'
API = dict(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET, DECLINE_COOLOFF_DAYS=0)


def _reject(who, app, body):
    return authed_client(who).post(f'{APPS}{app.pk}/reject/', body, format='json')


def _detail(who, app):
    r = authed_client(who).get(f'{APPS}{app.pk}/')
    assert r.status_code == 200, r.content[:300]
    return r.json()


class _People(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort()
        cls.org = cls.cohort.owning_organisation
        cls.reviewer = make_admin('reviewer', owning_org=cls.org)
        cls.other_reviewer = make_admin('reviewer', owning_org=cls.org)
        cls.qc = make_admin('qc', owning_org=cls.org)
        cls.lead = make_admin('org_admin', owning_org=cls.org)
        cls.super = make_admin('super', super_admin=True)

    def setUp(self):
        patcher = mock.patch('apps.scholarship.views_admin.verdict.build_verdict', return_value=[])
        patcher.start()
        self.addCleanup(patcher.stop)

    def _interviewing(self):
        return make_application('interviewing', cohort=self.cohort, reviewer=self.reviewer)


@override_settings(**API)
class RejectNeedsAReason(_People):

    def test_no_reason_is_refused_and_nothing_moves(self):
        for body in ({'category': 'interview'}, {'category': 'interview', 'comments': '   '},
                     {'category': 'interview', 'comments': None},
                     {'category': 'interview', 'comments': ['x']}):
            with self.subTest(body=body):
                app = self._interviewing()
                mail.outbox.clear()
                r = _reject(self.lead, app, body)
                self.assertEqual(r.status_code, 400, r.content[:300])
                self.assertEqual(r.json()['code'], 'comments_required')
                app.refresh_from_db()
                self.assertEqual(app.status, 'interviewing')
                self.assertIsNone(app.rejected_at)
                self.assertEqual((app.rejected_by, app.rejection_comments), ('', ''))
                self.assertEqual(mail.outbox, [])
                self.assertFalse(StaffActivity.objects.filter(
                    subject_type='application', subject_id=app.pk).exists())

    def test_contractual_needs_one_too(self):
        app = make_application('recommended', cohort=self.cohort, reviewer=self.reviewer)
        r = _reject(self.reviewer, app, {'category': 'contractual'})
        self.assertEqual((r.status_code, r.json()['code']), (400, 'comments_required'))
        app.refresh_from_db()
        self.assertEqual(app.status, 'recommended')

    def test_the_reason_is_stored_on_the_case(self):
        app = self._interviewing()
        r = _reject(self.lead, app, {'category': 'interview', 'comments': '  Did not attend twice.  '})
        self.assertEqual(r.status_code, 200, r.content[:300])
        app.refresh_from_db()
        self.assertEqual((app.status, app.rejection_category), ('rejected', 'interview'))
        self.assertEqual(app.rejection_comments, 'Did not attend twice.')
        self.assertEqual(app.rejected_by, self.lead.email)
        self.assertEqual(r.json()['rejection_comments'], 'Did not attend twice.')


@override_settings(**API)
class WhoDeclined(_People):

    def test_someone_other_than_the_assignee_is_named_as_such(self):
        for who in (self.lead, self.super):
            with self.subTest(who=who.role):
                app = self._interviewing()
                r = _reject(who, app, {'category': 'interview', 'comments': 'Not selected.'})
                self.assertEqual(r.status_code, 200, r.content[:300])
                self.assertIs(r.json()['rejected_by_unassigned'], True)
                self.assertIs(_detail(self.super, app)['rejected_by_unassigned'], True)

    def test_the_assignee_is_not(self):
        app = self._interviewing()
        r = _reject(self.reviewer, app, {'category': 'interview', 'comments': 'Not selected.'})
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertIs(r.json()['rejected_by_unassigned'], False)
        self.assertIs(_detail(self.super, app)['rejected_by_unassigned'], False)

    def test_a_qc_upheld_decline_and_a_live_case_say_nothing(self):
        app = make_application('awaiting_qc', outcome='decline', cohort=self.cohort, reviewer=self.reviewer)
        admin_reject(app, self.qc, 'interview', activity=False, defer_email=True)   # the QC path: no reason
        self.assertIsNone(_detail(self.super, app)['rejected_by_unassigned'])
        self.assertIsNone(_detail(self.super, self._interviewing())['rejected_by_unassigned'])


@override_settings(**API)
class QcRefusalOnDetail(_People):

    def _awaiting(self):
        return make_application('awaiting_qc', outcome='decline', cohort=self.cohort, reviewer=self.reviewer)

    def _assert_agrees(self, who, app, expected):
        app.refresh_from_db()
        self.assertEqual(_detail(who, app)['qc_refusal'], expected)
        self.assertEqual(qc_separation.refusal(who, app), expected)

    def test_a_clean_qc_may_decide(self):
        self._assert_agrees(self.qc, self._awaiting(), None)

    def test_a_qc_who_was_assigned_before_is_refused(self):
        app = self._awaiting()
        AssignmentEvent.objects.create(application=app, from_admin=self.qc, to_admin=self.reviewer)
        self._assert_agrees(self.qc, app, qc_separation.SELF_ASSIGNED_BEFORE)

    def test_a_qc_who_interviewed_is_refused(self):
        app = self._awaiting()
        InterviewSession.objects.create(application=app, interviewer=self.qc, status='draft')
        self._assert_agrees(self.qc, app, qc_separation.SELF_INTERVIEW)

    def test_the_organisation_admin_who_recorded_the_verdict_is_refused(self):
        app = self._awaiting()
        app.verdict_decided_by = self.lead.email
        app.save(update_fields=['verdict_decided_by'])
        self._assert_agrees(self.lead, app, qc_separation.SELF_VERDICT)

    def test_a_super_is_exempt(self):
        app = self._awaiting()
        AssignmentEvent.objects.create(application=app, from_admin=self.super, to_admin=self.reviewer)
        self.assertIsNone(_detail(self.super, app)['qc_refusal'])

    def test_no_code_off_the_qc_stage_or_without_qc(self):
        app = self._awaiting()
        # The assignee holds no `qc`: the panel is not theirs to see at all, so no code.
        self.assertIsNone(_detail(self.reviewer, app)['qc_refusal'])
        live = self._interviewing()
        AssignmentEvent.objects.create(application=live, from_admin=self.qc, to_admin=self.reviewer)
        self.assertIsNone(_detail(self.qc, live)['qc_refusal'])
