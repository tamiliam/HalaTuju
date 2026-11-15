"""TD-613 (2026-11-15): a case whose holder can no longer review it may change hands.

Under R5 an awarded case no longer stops its reviewer leaving Reviewers, being suspended or being
archived, and `assigned_to` is kept. When the case comes back OPEN (a reopen, or an award that falls
through and is diverted to AWAITING QC) nobody could work it: the reopen was refused
(`reviewer_cannot_review`) and the revert landed at `interviewed`, outside ASSIGNABLE_STATUSES.

Now the case derives `services.needs_new_holder` and may go to a NEW holder at any open status. Every
assign rule still holds (the door, Reviewers, signed in, never yourself, never across organisations,
QC separation), an unassign stays refused from Awaiting QC on, and a closed case never moves. Review
round: outside ASSIGNABLE_STATUSES a suspension alone strands only a reopened case (F1, owner
approved 2026-11-15). Fixtures: the factory, and synthetic names only.
"""
from decimal import Decimal
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import PartnerAdmin
from apps.scholarship import sponsorship as sponsorship_svc
from apps.scholarship import staff_work
from apps.scholarship.models import AssignmentEvent, InterviewSession, Sponsor, Sponsorship
from apps.scholarship.services import (
    assign_reviewer, holder_can_review, is_assignable, may_unassign, needs_new_holder, unassign_refusal,
)
from apps.scholarship.services.errors import AssignmentError
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, answered_findings, authed_client, make_admin, make_application, make_cohort,
    make_org, make_student, unique_suffix,
)

BASE = '/api/v1/admin/scholarship/applications'
#: Every other requirement cleared, so the verdict turns only on the "Born in" rule (TD-376 suite).
ONLY_BIRTH = dict(min_spm_a_count=None, min_spm_bplus_count=None, min_spm_credit_count=None,
                  min_stpm_pngk=None, min_merit_score=None, income_ceiling=None,
                  per_capita_ceiling=None)
SABAH_IC, SELANGOR_IC = '080505-12-1234', '080505-10-1234'
DECLINE = {'identity': 'pass', 'academic': 'pass', 'income': 'pass', 'pathway': 'pass',
           'overall': 'decline'}


def archive(admin):
    """What `staff_archive` writes (is_active off, archived_at, the login cleared)."""
    PartnerAdmin.objects.filter(pk=admin.pk).update(
        is_active=False, archived_at=timezone.now(), supabase_user_id=None)
    admin.refresh_from_db()


def suspend(admin):
    PartnerAdmin.objects.filter(pk=admin.pk).update(is_active=False)
    admin.refresh_from_db()


def no_group(admin):
    """The end state of the Removes (M2c): a `member` with no keys."""
    PartnerAdmin.objects.filter(pk=admin.pk).update(role=PartnerAdmin.MEMBER_ROLE, permissions=None)
    admin.refresh_from_db()


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _Base(TestCase):
    def setUp(self):
        self.cohort = make_cohort()
        self.org = self.cohort.owning_organisation
        self.super = make_admin('super', super_admin=True, first_seen_at=timezone.now())
        self.lead = make_admin('org_admin', owning_org=self.org, first_seen_at=timezone.now())
        self.old = make_admin('reviewer', owning_org=self.org, first_seen_at=timezone.now())
        self.new = make_admin('reviewer', owning_org=self.org, first_seen_at=timezone.now())

    def assign(self, caller, app, reviewer_id):
        return authed_client(caller).post(f'{BASE}/{app.pk}/assign/', {'reviewer_id': reviewer_id},
                                          format='json')

    def detail(self, caller, app):
        r = authed_client(caller).get(f'{BASE}/{app.pk}/')
        self.assertEqual(r.status_code, 200, r.content[:300])
        return r.json()

    def recommended(self, **kw):
        app = make_application('recommended', cohort=self.cohort, reviewer=self.old, **kw)
        InterviewSession.objects.create(application=app, status='submitted', submitted_at=timezone.now(),
                                        interviewer=self.old, findings=answered_findings(app))
        return app


class TestTheReopenPath(_Base):
    """Stuck path (a): a reopen whose holder has gone. It succeeds, the case is offered, it goes to a
    valid reviewer, and the new holder works it."""

    def test_an_archived_holder_reopen_reassign_and_the_new_holder_decides(self):
        app = self.recommended()
        archive(self.old)
        r = authed_client(self.super).post(f'{BASE}/{app.pk}/reopen-decision/',
                                           {'reason': 'Income mis-read.'}, format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewed')
        self.assertTrue(needs_new_holder(app))
        body = self.detail(self.lead, app)
        self.assertEqual((body['assignable'], body['needs_new_holder']), (True, True))

        r = self.assign(self.lead, app, self.new.pk)
        self.assertEqual(r.status_code, 200, r.content[:300])
        app.refresh_from_db()
        self.assertEqual(app.assigned_to_id, self.new.pk)
        self.assertFalse(needs_new_holder(app))
        self.assertFalse(is_assignable(app))           # back to the ordinary window: interviewed
        event = AssignmentEvent.objects.get(application=app)
        self.assertEqual((event.from_admin_id, event.to_admin_id), (self.old.pk, self.new.pk))

        r = authed_client(self.new).post(f'{BASE}/{app.pk}/record-verdict/',
                                         {'officer_verdict': DECLINE, 'reason': 'private college'},
                                         format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])
        app.refresh_from_db()
        self.assertEqual(app.verdict_decided_by, self.new.email)

    def test_a_suspended_holder_of_a_sent_decline_reopens_and_hands_on(self):
        app = make_application('rejected', cohort=self.cohort, reviewer=self.old,
                               decline_due_at=None, pending_rejection_category='',
                               decline_email_sent_at=timezone.now())
        InterviewSession.objects.create(application=app, status='submitted', submitted_at=timezone.now(),
                                        interviewer=self.old, findings=answered_findings(app))
        suspend(self.old)
        r = authed_client(self.super).post(f'{BASE}/{app.pk}/reopen-decision/',
                                           {'reason': 'Should be accepted.'}, format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])
        app.refresh_from_db()
        self.assertEqual(app.status, 'rejected')
        self.assertTrue(is_assignable(app))
        # The list serves the same answer, so its dropdown offers the change.
        rows = authed_client(self.lead).get(f'{BASE}/').json()
        rows = rows.get('results', rows.get('applications', rows)) if isinstance(rows, dict) else rows
        row = next(x for x in rows if x['id'] == app.pk)
        self.assertEqual((row['assignable'], row['needs_new_holder']), (True, True))
        # Never back to nobody.
        self.assertEqual(self.assign(self.lead, app, None).json()['code'], 'not_assignable')
        self.assertEqual(self.assign(self.lead, app, self.new.pk).status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.assigned_to_id, self.new.pk)
        self.assertTrue(holder_can_review(app.assigned_to))


class TestTheRevertPath(_Base):
    """Stuck path (b): an award falls through, the IC was unlocked, so the case is diverted to
    AWAITING QC with its old holder, who has left Reviewers."""

    def _awarded(self):
        cohort = make_cohort(owning_organisation=self.org, **ONLY_BIRTH, allowed_birth_states=['sabah'])
        app = make_application('awarded', cohort=cohort, reviewer=self.old,
                               student=make_student(nric=SABAH_IC), award_amount=Decimal('3000'))
        sponsor = Sponsor.objects.create(
            supabase_user_id=unique_suffix('td613-sp-'), name='Test Sponsor',
            email=f'{unique_suffix("td613")}@example.test', phone='0', source='friend',
            consent_at=timezone.now(), status='approved')
        offer = Sponsorship.objects.create(application=app, sponsor=sponsor, amount=Decimal('3000'),
                                           status='offered')
        return app, offer

    def test_a_diverted_revert_reassign_and_the_new_holder_verify_accepts(self):
        app, offer = self._awarded()
        self.assertFalse(is_assignable(app))           # awarded: closed, and it stays put
        no_group(self.old)
        self.assertFalse(needs_new_holder(app))        # a closed case never needs a holder
        app.profile.nric, app.profile.nric_verified = SELANGOR_IC, False
        app.profile.save(update_fields=['nric', 'nric_verified'])
        sponsorship_svc.cancel_offer(offer.sponsor, offer.id)
        app.refresh_from_db()
        self.assertEqual((app.status, app.assigned_to_id), ('interviewed', self.old.pk))
        self.assertTrue(needs_new_holder(app))
        self.assertEqual(staff_work.unfinished(self.old)['reviewers']['open_cases'], 1)

        self.assertEqual(self.assign(self.lead, app, None).json()['code'], 'findings_submitted')
        self.assertEqual(self.assign(self.lead, app, self.new.pk).status_code, 200)
        # (c) the No-group holder holds nothing now, so a Delete is no longer refused for this case.
        self.assertEqual(staff_work.unfinished(self.old)['reviewers']['open_cases'], 0)

        with mock.patch('apps.scholarship.views_admin.applications.application_completeness',
                        return_value={'complete': True}):
            r = authed_client(self.new).post(f'{BASE}/{app.pk}/verify-accept/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewed')
        self.assertTrue(app.profile.nric_verified)


class TestTheRulesStillHold(_Base):
    """The adversarial angle: a funded case changing hands must not let anyone decide their own case,
    reach another organisation's, skip QC, or move a closed case."""

    def _stranded(self):
        app = self.recommended()
        app.status = 'interviewed'
        app.save(update_fields=['status'])
        archive(self.old)
        self.assertTrue(needs_new_holder(app))
        return app

    def test_nobody_hands_it_to_themselves(self):
        app = self._stranded()
        reviewing_lead = make_admin('org_admin', owning_org=self.org, first_seen_at=timezone.now(),
                                    permissions=['review'])
        self.assertEqual(self.assign(reviewing_lead, app, reviewing_lead.pk).json()['code'], 'self_assign')
        self.assertEqual(self.assign(self.super, app, self.super.pk).json()['code'], 'self_assign')

    def test_never_across_organisations(self):
        app = self._stranded()
        other_lead = make_admin('org_admin', owning_org=make_org(), first_seen_at=timezone.now())
        self.assertEqual(self.assign(other_lead, app, self.new.pk).status_code, 404)
        stranger = make_admin('reviewer', owning_org=make_org(), first_seen_at=timezone.now())
        self.assertEqual(self.assign(self.lead, app, stranger.pk).json()['code'], 'bad_assignee')
        app.refresh_from_db()
        self.assertEqual(app.assigned_to_id, self.old.pk)

    def test_the_door_reviewers_and_sign_in_still_gate_the_target(self):
        app = self._stranded()
        self.assertEqual(self.assign(self.new, app, self.lead.pk).status_code, 403)   # no assign door
        not_reviewer = make_admin('admin', owning_org=self.org, first_seen_at=timezone.now())
        self.assertEqual(self.assign(self.lead, app, not_reviewer.pk).json()['code'], 'bad_assignee')
        never_in = make_admin('reviewer', owning_org=self.org)
        self.assertEqual(self.assign(self.lead, app, never_in.pk).json()['code'], 'not_signed_in')

    def test_qc_separation_is_unchanged(self):
        app = self._stranded()
        qc = make_admin('qc', owning_org=self.org, first_seen_at=timezone.now())
        self.assertEqual(self.assign(self.lead, app, qc.pk).status_code, 200)
        r = authed_client(qc).post(f'{BASE}/{app.pk}/qc-decision/', {'decision': 'accept'}, format='json')
        self.assertEqual((r.status_code, r.json()['code']), (403, 'self_qc_forbidden'))

    def test_a_former_holder_who_handed_it_on_may_not_qc_it(self):
        # An org admin who joined Reviewers, held the case, then left Reviewers (still qc by role).
        lead = make_admin('org_admin', owning_org=self.org, first_seen_at=timezone.now())
        app = self.recommended()
        app.assigned_to = lead
        app.status = 'interviewed'
        app.save(update_fields=['assigned_to', 'status'])
        self.assertTrue(needs_new_holder(app))
        self.assertEqual(self.assign(lead, app, self.new.pk).status_code, 200)
        r = authed_client(lead).post(f'{BASE}/{app.pk}/qc-decision/', {'decision': 'accept'}, format='json')
        self.assertEqual((r.status_code, r.json()['code']), (403, 'self_assigned_qc_forbidden'))

    def test_a_closed_case_never_moves(self):
        for stage in ('awarded', 'active', 'closed'):
            with self.subTest(stage=stage):
                holder = make_admin('reviewer', owning_org=self.org, first_seen_at=timezone.now())
                app = make_application(stage, cohort=self.cohort, reviewer=holder)
                archive(holder)
                self.assertFalse(needs_new_holder(app))
                r = self.assign(self.super, app, self.new.pk)
                self.assertEqual((r.status_code, r.json()['code']), (400, 'not_assignable'))
        withdrawn = make_application('interviewing', cohort=self.cohort, reviewer=self.old)
        withdrawn.status = 'withdrawn'
        withdrawn.save(update_fields=['status'])
        archive(self.old)
        self.assertFalse(needs_new_holder(withdrawn))
        with self.assertRaises(AssignmentError) as e:
            assign_reviewer(withdrawn, reviewer=self.new, by_admin=self.super)
        self.assertEqual(e.exception.code, 'not_assignable')

    def test_a_holder_who_can_still_work_it_keeps_the_ordinary_window(self):
        app = self.recommended()
        app.status = 'interviewed'
        app.save(update_fields=['status'])
        PartnerAdmin.objects.filter(pk=self.old.pk).update(paused_at=timezone.now())   # pause: no NEW work
        app.refresh_from_db()
        self.assertFalse(needs_new_holder(app))
        self.assertEqual(self.assign(self.lead, app, self.new.pk).json()['code'], 'not_assignable')
        app.assigned_to = self.super
        app.save(update_fields=['assigned_to'])
        self.assertFalse(needs_new_holder(app))        # a super can always work it


@override_settings(STUDENT_ASSIGNMENT_EMAIL_ENABLED=True)
class TestTheHandoverEmails(_Base):
    def test_the_student_hears_nothing_after_the_interview_the_reviewer_does(self):
        from apps.scholarship import assign_notify
        app = self.recommended()
        app.status = 'interviewed'
        app.save(update_fields=['status'])
        archive(self.old)
        self.assertEqual(self.assign(self.lead, app, self.new.pk).status_code, 200)
        event = AssignmentEvent.objects.get(application=app)
        with mock.patch('apps.scholarship.emails.send_reviewer_assigned_email') as to_reviewer, \
                mock.patch('apps.scholarship.emails.send_student_assigned_reviewer_email') as to_student:
            assign_notify.send_assignment_emails(event)
        to_reviewer.assert_called_once()
        to_student.assert_not_called()
        # The control: the same event before the interview still tells the student.
        app.status = 'interviewing'
        app.save(update_fields=['status'])
        event.refresh_from_db()
        with mock.patch('apps.scholarship.emails.send_student_assigned_reviewer_email') as to_student, \
                mock.patch('apps.scholarship.emails.send_reviewer_assigned_email'):
            assign_notify.send_assignment_emails(event)
        to_student.assert_called_once()


def _road(stage):
    """The factory's Awaiting QC needs its road named; the recommend road (verify-accept)."""
    return {'outcome': 'recommend'} if stage == 'awaiting_qc' else {}


class TestASuspensionAloneStrandsNothing(_Base):
    """Review F1 (owner approved 2026-11-15): suspend → reassign → restore must not let a lead move a
    finished case and have its verdict overwritten. A SUSPENDED holder strands a case outside the
    ordinary window only when it came back by a super's reopen; a holder gone for good always does."""

    def test_suspended_holder_at_awaiting_qc_or_a_recorded_verdict_is_refused(self):
        for stage in ('awaiting_qc', 'recommended'):
            with self.subTest(stage=stage):
                holder = make_admin('reviewer', owning_org=self.org, first_seen_at=timezone.now())
                app = make_application(stage, cohort=self.cohort, reviewer=holder, **_road(stage))
                suspend(holder)
                self.assertFalse(needs_new_holder(app))
                r = self.assign(self.lead, app, self.new.pk)
                self.assertEqual((r.status_code, r.json()['code']), (400, 'not_assignable'))
                app.refresh_from_db()
                self.assertEqual(app.assigned_to_id, holder.pk)

    def test_a_reopened_case_with_a_suspended_holder_hands_on(self):
        app = self.recommended()
        suspend(self.old)
        r = authed_client(self.super).post(f'{BASE}/{app.pk}/reopen-decision/',
                                           {'reason': 'Income mis-read.'}, format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewed')
        self.assertTrue(needs_new_holder(app))
        self.assertEqual(self.assign(self.lead, app, self.new.pk).status_code, 200)

    def test_a_suspended_holder_who_also_left_reviewers_is_gone_for_good(self):
        app = make_application('awaiting_qc', outcome='recommend', cohort=self.cohort, reviewer=self.old)
        no_group(self.old)
        suspend(self.old)
        self.assertTrue(needs_new_holder(app))

    def test_a_suspended_holder_of_a_reverted_award_waits(self):
        # An award revert leaves no stored marker, so a suspension alone does not strand the case:
        # it waits for a Restore or a super's reopen (the ruling's fallback, no migration).
        app, offer = TestTheRevertPath._awarded(self)
        app.profile.nric, app.profile.nric_verified = SELANGOR_IC, False
        app.profile.save(update_fields=['nric', 'nric_verified'])
        suspend(self.old)
        sponsorship_svc.cancel_offer(offer.sponsor, offer.id)
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewed')
        self.assertFalse(needs_new_holder(app))
        self.assertEqual(self.assign(self.lead, app, self.new.pk).json()['code'], 'not_assignable')

    def test_inside_the_ordinary_window_nothing_changes(self):
        app = make_application('interviewing', cohort=self.cohort, reviewer=self.old)
        suspend(self.old)
        self.assertTrue(needs_new_holder(app))
        self.assertTrue(is_assignable(app))


class TestMayUnassignIsServed(_Base):
    """Review F2: the server serves `may_unassign` from `unassign_refusal`, the rule the assign
    endpoint refuses by, so neither picker greys out an unassign the server allows."""

    def test_a_stranded_case_at_interviewing_may_still_be_unassigned(self):
        app = make_application('interviewing', cohort=self.cohort, reviewer=self.old)
        archive(self.old)
        body = self.detail(self.lead, app)
        self.assertEqual((body['needs_new_holder'], body['may_unassign']), (True, True))
        self.assertTrue(may_unassign(app))
        self.assertEqual(self.assign(self.lead, app, None).status_code, 200)
        app.refresh_from_db()
        self.assertIsNone(app.assigned_to_id)

    def test_from_awaiting_qc_on_a_stranded_case_may_not(self):
        app = make_application('awaiting_qc', outcome='recommend', cohort=self.cohort, reviewer=self.old)
        archive(self.old)
        body = self.detail(self.lead, app)
        self.assertEqual((body['needs_new_holder'], body['may_unassign']), (True, False))
        rows = authed_client(self.lead).get(f'{BASE}/').json()
        rows = rows.get('results', rows.get('applications', rows)) if isinstance(rows, dict) else rows
        row = next(x for x in rows if x['id'] == app.pk)
        self.assertEqual((row['needs_new_holder'], row['may_unassign']), (True, False))
        self.assertEqual(self.assign(self.lead, app, None).json()['code'], 'findings_submitted')

    def test_the_flag_and_the_refusal_agree_at_every_stage(self):
        for stage in ('submitted', 'interviewing', 'awaiting_qc', 'recommended', 'rejected', 'awarded'):
            with self.subTest(stage=stage):
                app = make_application(stage, cohort=self.cohort, reviewer=self.old, **_road(stage))
                self.assertEqual(may_unassign(app), unassign_refusal(app) is None)
        nobody = make_application('awaiting_qc', outcome='recommend', cohort=self.cohort)
        nobody.assigned_to = None                      # in memory: re-picking Unassigned is a no-op
        self.assertTrue(may_unassign(nobody))


class TestWhoDeclinedReadsTheHolderAtTheDecline(_Base):
    """Review F3: a rejected case can change hands since TD-613 (reopen, handover, cancel the reopen),
    so "declined by someone other than the assigned reviewer" asks who held it AT the decline."""

    def _declined(self, holder, by, with_event):
        """A sent door decline (a reason, `contractual`) by ``by`` while ``holder`` held the case;
        ``with_event``: an audit row hands it to ``holder`` before the decline (else a pre-F7 case)."""
        if with_event:
            app = make_application('interviewing', cohort=self.cohort, reviewer=self.new)
            assign_reviewer(app, reviewer=holder, by_admin=self.super)
        else:
            app = make_application('interviewing', cohort=self.cohort, reviewer=holder)
        now = timezone.now()
        app.status, app.rejected_at, app.rejected_by = 'rejected', now, by.email
        app.rejection_category, app.rejection_comments = 'contractual', 'Not selected.'
        app.verdict_decided_at, app.decline_email_sent_at = now, now
        app.save()
        return app

    def _hand_on(self, app, holder):
        """Reopen, hand the case from the departed ``holder`` to `self.new`, cancel the reopen."""
        archive(holder)
        client = authed_client(self.super)
        r = client.post(f'{BASE}/{app.pk}/reopen-decision/', {'reason': 'Recheck.'}, format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertEqual(self.assign(self.lead, app, self.new.pk).status_code, 200)
        self.assertEqual(client.post(f'{BASE}/{app.pk}/cancel-reopen/', {}, format='json').status_code, 200)
        app.refresh_from_db()
        self.assertEqual((app.status, app.assigned_to_id), ('rejected', self.new.pk))

    def test_the_decliner_who_held_it_then_is_not_flagged_after_a_handover(self):
        for with_event in (True, False):
            with self.subTest(audit_row_before_the_decline=with_event):
                holder = make_admin('reviewer', owning_org=self.org, first_seen_at=timezone.now())
                app = self._declined(holder, holder, with_event)
                self.assertIs(self.detail(self.super, app)['rejected_by_unassigned'], False)
                self._hand_on(app, holder)
                self.assertIs(self.detail(self.super, app)['rejected_by_unassigned'], False)

    def test_a_decline_by_someone_else_is_still_flagged_after_a_handover(self):
        holder = make_admin('reviewer', owning_org=self.org, first_seen_at=timezone.now())
        app = self._declined(holder, self.lead, True)
        self.assertIs(self.detail(self.super, app)['rejected_by_unassigned'], True)
        self._hand_on(app, holder)
        self.assertIs(self.detail(self.super, app)['rejected_by_unassigned'], True)
