"""Request #75 (analysis 172, 2026-11-16): reject a student before interview.

Pinned here, one test per rule the organisation approved:
  * WHO: an org admin, a holder of the QC permission key, and a platform super. A reviewer never
    (403); another organisation's admin gets a 404.
  * WHERE: only at Awaiting review (`profile_complete`) with no reviewer; the server refuses every
    other stage (`bad_status`) and a case with a reviewer (`has_reviewer`).
  * WHAT: the main reason and the note are required (the note at most 2,000 characters); the
    decline is recorded at once as its own kind, `pre_interview`, with both on the file.
  * THE EMAIL: held for the organisation's QC decline hold, the same markers and release cron as a
    QC decline; until it goes the student still sees Awaiting review; cancel puts the student back at
    Awaiting review with no reviewer and nothing is sent. The reason and note never reach the student.
  * It never counts against a reviewer, and the Programme overview counts it, by reason.
"""
from datetime import timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.services import cancel_pending_decline, release_pending_declines
from apps.scholarship.services.pre_interview import REASONS, counts, reject_before_interview
from apps.scholarship.student_status import student_facing_status
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
)

NOTE = 'ZQX-pre-interview-note: the payslip shows a household income above the band.'


def _url(pk):
    return f'/api/v1/admin/scholarship/applications/{pk}/reject-before-interview/'


@override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _Base(TestCase):
    def setUp(self):
        self.org = make_org()
        self.cohort = make_cohort(owning_organisation=self.org)
        self.org_admin = make_admin('org_admin', owning_org=self.org)
        self.app = make_application('profile_complete', cohort=self.cohort)
        mail.outbox = []

    def _post(self, who, app=None, reason='not_b40', comments=NOTE):
        return authed_client(who).post(_url((app or self.app).pk),
                                       {'reason': reason, 'comments': comments}, format='json')


class WhoMayRejectTest(_Base):
    def test_org_admin_rejects(self):
        r = self._post(self.org_admin)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['status'], 'rejected')
        self.assertEqual(r.data['rejection_category'], 'pre_interview')

    def test_a_qc_key_holder_rejects(self):
        self.assertEqual(self._post(make_admin('qc', owning_org=self.org)).status_code, 200)

    def test_super_rejects(self):
        self.assertEqual(self._post(make_admin('reviewer', super_admin=True)).status_code, 200)

    def test_a_reviewer_is_refused(self):
        r = self._post(make_admin('reviewer', owning_org=self.org))
        self.assertIn(r.status_code, (403, 404))
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'profile_complete')

    def test_view_only_admin_and_finance_are_refused(self):
        for role in ('admin', 'finance'):
            with self.subTest(role):
                r = self._post(make_admin(role, owning_org=self.org))
                self.assertIn(r.status_code, (403, 404))
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'profile_complete')

    def test_another_organisation_gets_404(self):
        other = make_admin('org_admin', owning_org=make_org())
        self.assertEqual(self._post(other).status_code, 404)
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'profile_complete')

    def test_the_detail_offers_it_to_a_key_holder_and_never_to_a_reviewer(self):
        url = f'/api/v1/admin/scholarship/applications/{self.app.pk}/'
        body = authed_client(self.org_admin).get(url).data
        self.assertIsNotNone(body['pre_interview'])
        self.assertEqual(body['pre_interview']['hold_hours'], 24)
        reviewer = make_admin('reviewer', owning_org=self.org)
        assigned = make_application('assigned', cohort=self.cohort, reviewer=reviewer)
        r = authed_client(reviewer).get(f'/api/v1/admin/scholarship/applications/{assigned.pk}/')
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.data['pre_interview'])

    def test_not_offered_at_other_stages(self):
        app = make_application('interviewing', cohort=self.cohort,
                               reviewer=make_admin('reviewer', owning_org=self.org))
        body = authed_client(self.org_admin).get(
            f'/api/v1/admin/scholarship/applications/{app.pk}/').data
        self.assertIsNone(body['pre_interview'])


class WhereItWorksTest(_Base):
    def test_refused_with_a_reviewer(self):
        app = make_application('assigned', cohort=self.cohort,
                               reviewer=make_admin('reviewer', owning_org=self.org))
        r = self._post(self.org_admin, app=app)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'has_reviewer')
        app.refresh_from_db()
        self.assertEqual(app.status, 'profile_complete')

    def test_refused_at_every_other_stage(self):
        reviewer = make_admin('reviewer', owning_org=self.org)
        for stage in ('submitted', 'shortlisted', 'interviewing'):
            with self.subTest(stage):
                kw = {'reviewer': reviewer} if stage == 'interviewing' else {}
                app = make_application(stage, cohort=self.cohort, **kw)
                was = app.status
                r = self._post(self.org_admin, app=app)
                self.assertEqual(r.status_code, 400)
                self.assertEqual(r.data['code'], 'bad_status')
                app.refresh_from_db()
                self.assertEqual(app.status, was)

    def test_refused_twice(self):
        self.assertEqual(self._post(self.org_admin).status_code, 200)
        r = self._post(self.org_admin)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'bad_status')


class WhatIsRequiredTest(_Base):
    def _refused(self, code, **kw):
        r = self._post(self.org_admin, **kw)
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(r.data['code'], code)
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'profile_complete')

    def test_the_reason_is_required_and_from_the_list(self):
        self._refused('reason_required', reason='')
        self._refused('reason_required', reason='made_up')
        self._refused('reason_required', reason=None)

    def test_the_note_is_required(self):
        self._refused('comments_required', comments='   ')
        self._refused('comments_required', comments=None)

    def test_the_note_is_at_most_2000_characters(self):
        self._refused('comments_too_long', comments='x' * 2001)
        self.assertEqual(self._post(self.org_admin, comments='x' * 2000).status_code, 200)

    def test_every_listed_reason_is_accepted(self):
        self.assertEqual(REASONS, ('not_b40', 'not_government_institution', 'results_too_low',
                                   'programme_requirements', 'not_responsive', 'other'))
        for reason in REASONS:
            with self.subTest(reason):
                app = make_application('profile_complete', cohort=self.cohort)
                self.assertEqual(self._post(self.org_admin, app=app, reason=reason).status_code, 200)
                app.refresh_from_db()
                self.assertEqual(app.rejection_reason, reason)


class WhatIsRecordedTest(_Base):
    def test_recorded_at_once_as_its_own_kind_with_the_reason_and_note(self):
        self._post(self.org_admin, reason='results_too_low', comments=f'  {NOTE}  ')
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'rejected')
        self.assertEqual(self.app.rejection_category, 'pre_interview')
        self.assertEqual(self.app.rejection_reason, 'results_too_low')
        self.assertEqual(self.app.rejection_comments, NOTE)   # stripped
        self.assertEqual(self.app.rejected_by, self.org_admin.email)
        self.assertIsNotNone(self.app.rejected_at)
        self.assertEqual(self.app.pre_decline_status, 'profile_complete')
        self.assertIsNone(self.app.assigned_to_id)

    def test_the_old_reject_door_cannot_reach_this_kind(self):
        """`/reject/` is open to an assignee; it must keep refusing this bucket."""
        r = authed_client(self.org_admin).post(
            f'/api/v1/admin/scholarship/applications/{self.app.pk}/reject/',
            {'category': 'pre_interview', 'comments': NOTE}, format='json')
        self.assertNotEqual(r.status_code, 200)
        self.app.refresh_from_db()
        self.assertNotEqual(self.app.rejection_category, 'pre_interview')


class TheEmailTest(_Base):
    def test_held_for_the_qc_hold_and_the_student_still_sees_awaiting_review(self):
        before = timezone.now()
        self._post(self.org_admin)
        self.app.refresh_from_db()
        self.assertEqual(mail.outbox, [])
        self.assertEqual(self.app.pending_rejection_category, 'pre_interview')
        self.assertEqual(self.app.pending_decline_by, self.org_admin.email)
        self.assertIsNotNone(self.app.decline_due_at)
        self.assertGreater(self.app.decline_due_at, before + timedelta(hours=23))
        self.assertIsNone(self.app.decline_email_sent_at)
        self.assertEqual(student_facing_status(self.app), 'profile_complete')

    def test_the_release_cron_sends_the_warm_decline_without_the_reason_or_note(self):
        self._post(self.org_admin)
        self.app.refresh_from_db()
        self.assertEqual(release_pending_declines(now=self.app.decline_due_at + timedelta(minutes=1)), 1)
        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        whole = sent.subject + sent.body + ''.join(str(a[0]) for a in getattr(sent, 'alternatives', []))
        self.assertNotIn('ZQX-pre-interview-note', whole)
        self.assertNotIn('not_b40', whole)
        self.assertNotIn('interview', sent.subject.lower())
        self.app.refresh_from_db()
        self.assertIsNotNone(self.app.decline_email_sent_at)
        self.assertEqual(self.app.pending_rejection_category, '')
        self.assertEqual(student_facing_status(self.app), 'rejected')

    def test_the_detail_shows_the_sent_date(self):
        self._post(self.org_admin)
        self.app.refresh_from_db()
        release_pending_declines(now=self.app.decline_due_at + timedelta(minutes=1))
        body = authed_client(self.org_admin).get(
            f'/api/v1/admin/scholarship/applications/{self.app.pk}/').data
        self.assertIsNotNone(body['decline_email_sent_at'])
        self.assertEqual(body['rejection_reason'], 'not_b40')

    def test_cancel_restores_awaiting_review_with_no_reviewer_and_sends_nothing(self):
        self._post(self.org_admin)
        r = authed_client(self.org_admin).post(
            f'/api/v1/admin/scholarship/applications/{self.app.pk}/cancel-decline/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        # The reply is the full case, so the cockpit offers the door again without a reload.
        self.assertEqual(r.data['status'], 'profile_complete')
        self.assertEqual(r.data['pre_interview']['note_max'], 2000)
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'profile_complete')
        self.assertIsNone(self.app.assigned_to_id)
        self.assertEqual(self.app.rejection_category, '')
        self.assertEqual(self.app.rejection_reason, '')
        self.assertEqual(self.app.rejection_comments, '')
        self.assertIsNone(self.app.decline_due_at)
        self.assertEqual(release_pending_declines(now=timezone.now() + timedelta(days=3)), 0)
        self.assertEqual(mail.outbox, [])
        # And the door is open again.
        self.assertEqual(self._post(self.org_admin).status_code, 200)

    def test_cancel_by_service_is_a_no_op_once_sent(self):
        self._post(self.org_admin)
        self.app.refresh_from_db()
        release_pending_declines(now=self.app.decline_due_at + timedelta(minutes=1))
        self.app.refresh_from_db()
        self.assertFalse(cancel_pending_decline(self.app))
        self.assertEqual(self.app.status, 'rejected')


class CountsTest(_Base):
    def test_never_counts_against_a_reviewer(self):
        """Every reviewer figure reads `assigned_to`; this case has none, so no reviewer's
        workload, decline or overturn band moves."""
        from apps.scholarship.views_admin.reviewers import _reviewer_workloads
        reviewer = make_admin('reviewer', owning_org=self.org)
        before = _reviewer_workloads([reviewer], organisation_id=self.org.pk)[reviewer.pk]
        self._post(self.org_admin)
        after = _reviewer_workloads([reviewer], organisation_id=self.org.pk)[reviewer.pk]
        self.assertEqual(before, after)
        self.assertEqual(after['completed'], 0)
        self.assertEqual(after['declined'], 0)
        self.app.refresh_from_db()
        self.assertIsNone(self.app.assigned_to_id)

    def test_counts_by_reason(self):
        for reason in ('not_b40', 'not_b40', 'results_too_low'):
            app = make_application('profile_complete', cohort=self.cohort)
            reject_before_interview(app, self.org_admin, reason, NOTE)
        scope = ScholarshipApplication.objects.filter(owning_organisation=self.org)
        got = counts(scope)
        self.assertEqual(got['total'], 3)
        self.assertEqual(got['by_reason']['not_b40'], 2)
        self.assertEqual(got['by_reason']['results_too_low'], 1)
        self.assertEqual(set(got['by_reason']), set(REASONS))
        self.assertEqual(got['by_reason']['other'], 0)

    def test_a_cancelled_one_is_not_counted(self):
        reject_before_interview(self.app, self.org_admin, 'other', NOTE)
        cancel_pending_decline(self.app)
        scope = ScholarshipApplication.objects.filter(owning_organisation=self.org)
        self.assertEqual(counts(scope)['total'], 0)

    def test_the_programme_overview_funnel_carries_the_counts(self):
        reject_before_interview(self.app, self.org_admin, 'not_responsive', NOTE)
        code = self.cohort.programme.code if self.cohort.programme_id else ''
        q = f'?programme={code}' if code else ''
        r = authed_client(self.org_admin).get(f'/api/v1/admin/scholarship/programme-overview/{q}')
        self.assertEqual(r.status_code, 200, r.content)
        pre = r.data['funnel']['pre_interview']
        self.assertEqual(pre['total'], 1)
        self.assertEqual(pre['by_reason']['not_responsive'], 1)
