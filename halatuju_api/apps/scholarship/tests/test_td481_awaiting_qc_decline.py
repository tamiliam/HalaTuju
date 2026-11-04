"""TD-481 (owner ruling 2026-11-04) — a case AWAITING QC is declined only through the QC gate.

`POST .../<pk>/reject/ {category: 'interview'}` (`AdminRejectView`) is gated by `_require_app_write`, which
admits the assignee and every `qc` holder (they write org-wide). `services.decline.admin_reject` allows the
`interview` bucket FROM 'interviewed' (AWAITING QC) because the QC decision declines through it. So this door
used to let the assignee or any QC decline an awaiting-QC case directly: a QC outcome with no `_require_qc`,
no separation guard and no QC record. The door now refuses `interview` at 'interviewed' for EVERYONE, super
included (400 `awaiting_qc`); the case does not move.

- `TheDoorRefuses`      — the assignee, an unrelated `qc` holder, the organisation admin and a super, on a
                          decline verdict AND a recommend verdict awaiting QC: 400 awaiting_qc, nothing written
                          (status, decline stamps, email, activity rows, reopen rows all as they were).
- `TheQcGateDeclines`   — the same case declined through `qc-decision` by an unrelated QC and by a super (the
                          super loses nothing: `_require_qc` admits them, exempt from separation).
- `EverythingElseAsBefore` — `/reject/` still declines from 'interviewing' (incl. a case QC reopened) and from
                          'shortlisted'; `contractual` is unchanged (and at 'interviewed' still answers bad_status).
"""
from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings

from apps.scholarship.models import DecisionReopen, ScholarshipApplication, StaffActivity
from apps.scholarship.services import INTERVIEW_REJECT_FROM
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort,
)

APPS = '/api/v1/admin/scholarship/applications/'

# A decline would email the student AT ONCE with no hold, so "no email" below is a real assertion.
API = dict(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET, DECLINE_COOLOFF_DAYS=0)


def _reject(who, app, category='interview'):
    return authed_client(who).post(f'{APPS}{app.pk}/reject/', {'category': category}, format='json')


def _qc(who, app, decision, comments=''):
    body = {'decision': decision, **({'comments': comments} if comments else {})}
    return authed_client(who).post(f'{APPS}{app.pk}/qc-decision/', body, format='json')


def _activity(app):
    return StaffActivity.objects.filter(subject_type='application', subject_id=app.pk)


class _People(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort()
        cls.org = cls.cohort.owning_organisation
        cls.reviewer = make_admin('reviewer', owning_org=cls.org)
        cls.qc = make_admin('qc', owning_org=cls.org)              # never touched the case
        cls.lead = make_admin('org_admin', owning_org=cls.org)
        cls.super = make_admin('super', super_admin=True)

    def setUp(self):
        # The QC accept-to-recommend floor reads the verdict; these fixtures carry no documents.
        patcher = mock.patch('apps.scholarship.views_admin.verdict.build_verdict', return_value=[])
        patcher.start()
        self.addCleanup(patcher.stop)

    def _awaiting(self, outcome):
        return make_application('awaiting_qc', outcome=outcome, cohort=self.cohort, reviewer=self.reviewer)


@override_settings(**API)
class TheDoorRefuses(_People):

    def test_the_service_still_allows_it_so_the_rule_is_the_doors(self):
        # The QC decision declines through `admin_reject` from 'interviewed'; the set is unchanged.
        self.assertIn('interviewed', INTERVIEW_REJECT_FROM)

    def test_everyone_is_refused_and_nothing_moves(self):
        for outcome in ('decline', 'recommend'):
            for who in (self.reviewer, self.qc, self.lead, self.super):
                with self.subTest(outcome=outcome, who=who.role):
                    app = self._awaiting(outcome)
                    activity_before = _activity(app).count()
                    mail.outbox.clear()
                    r = _reject(who, app)
                    self.assertEqual(r.status_code, 400, r.content[:300])
                    self.assertEqual(r.json()['code'], 'awaiting_qc')
                    self.assertIn('QC', r.json()['error'])
                    app.refresh_from_db()
                    self.assertEqual(app.status, 'interviewed')                 # still AWAITING QC
                    self.assertIsNone(app.rejected_at)
                    self.assertEqual((app.rejected_by, app.rejection_category), ('', ''))
                    self.assertEqual(app.pre_decline_status, '')
                    self.assertEqual(app.pending_rejection_category, '')
                    self.assertIsNone(app.decline_due_at)
                    self.assertIsNone(app.decline_email_sent_at)
                    self.assertEqual(mail.outbox, [])                           # no email
                    self.assertEqual(_activity(app).count(), activity_before)   # no activity row
                    self.assertFalse(DecisionReopen.objects.filter(application=app).exists())

    def test_a_super_reopened_recommended_case_is_refused_too(self):
        # A super reopening a QC-cleared case sends it back to 'interviewed' (AWAITING QC again):
        # it is declined at the QC gate now (test_decision_reopen walks that road end to end).
        from apps.scholarship import reopen as reopen_service
        app = make_application('recommended', cohort=self.cohort, reviewer=self.reviewer)
        reopen_service.reopen_decision(app, by_admin=self.super, reason='Should be declined.')
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewed')
        r = _reject(self.super, app)
        self.assertEqual((r.status_code, r.json()['code']), (400, 'awaiting_qc'))
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewed')
        self.assertIsNotNone(app.decision_reopened_at)                          # still reopened


@override_settings(**API)
class TheQcGateDeclines(_People):

    def test_an_unrelated_qc_confirms_the_decline(self):
        app = self._awaiting('decline')
        r = _qc(self.qc, app, 'accept')
        self.assertEqual(r.status_code, 200, r.content[:300])
        app.refresh_from_db()
        self.assertEqual((app.status, app.rejection_category), ('rejected', 'interview'))
        self.assertEqual(app.rejected_by, self.qc.email)
        self.assertIsNotNone(app.decline_due_at)                                # the org's QC hold
        self.assertTrue(_activity(app).filter(actor=self.qc, verb='qc_decision').exists())

    def test_a_super_confirms_the_decline(self):
        app = self._awaiting('decline')
        r = _qc(self.super, app, 'accept')
        self.assertEqual(r.status_code, 200, r.content[:300])
        app.refresh_from_db()
        self.assertEqual((app.status, app.rejection_category), ('rejected', 'interview'))

    def test_an_unrelated_qc_and_a_super_reject_a_recommend(self):
        for who in (self.qc, self.super):
            with self.subTest(who=who.role):
                app = self._awaiting('recommend')
                r = _qc(who, app, 'reject', comments='The income evidence does not hold.')
                self.assertEqual(r.status_code, 200, r.content[:300])
                app.refresh_from_db()
                self.assertEqual((app.status, app.rejection_category), ('rejected', 'interview'))
                row = DecisionReopen.objects.get(application=app)                # the QC record
                self.assertEqual(row.reason, 'The income evidence does not hold.')

    def test_the_assignee_is_still_refused_at_the_qc_gate(self):
        r = _qc(self.reviewer, self._awaiting('decline'), 'accept')
        self.assertEqual(r.status_code, 403)                                    # no `qc` key


@override_settings(**API)
class EverythingElseAsBefore(_People):

    def _declined(self, app, category='interview'):
        app.refresh_from_db()
        self.assertEqual((app.status, app.rejection_category), ('rejected', category))

    def test_the_assignee_declines_from_interviewing(self):
        app = make_application('interviewing', cohort=self.cohort, reviewer=self.reviewer)
        r = _reject(self.reviewer, app)
        self.assertEqual(r.status_code, 200, r.content[:300])
        self._declined(app)
        self.assertEqual(len(mail.outbox), 1)                                   # no hold here

    def test_a_case_qc_reopened_is_the_reviewers_again_and_declinable(self):
        app = self._awaiting('decline')
        r = _qc(self.qc, app, 'reopen', comments='Ask for the payslip.')
        self.assertEqual(r.status_code, 200, r.content[:300])
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewing')
        r = _reject(self.reviewer, app)
        self.assertEqual(r.status_code, 200, r.content[:300])
        self._declined(app)

    def test_shortlisted_declines(self):
        app = make_application('shortlisted', cohort=self.cohort)
        r = _reject(self.lead, app)                     # no assignee yet: the organisation admin
        self.assertEqual(r.status_code, 200, r.content[:300])
        self._declined(app)

    def test_contractual_is_unchanged(self):
        app = make_application('recommended', cohort=self.cohort, reviewer=self.reviewer)
        r = _reject(self.reviewer, app, 'contractual')
        self.assertEqual(r.status_code, 200, r.content[:300])
        self._declined(app, 'contractual')
        # At 'interviewed' a contractual decline answers what it always did — not the new code.
        waiting = self._awaiting('recommend')
        r = _reject(self.super, waiting, 'contractual')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'bad_status'))
        self.assertEqual(ScholarshipApplication.objects.get(pk=waiting.pk).status, 'interviewed')
