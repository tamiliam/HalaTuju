"""POST-AWARD-CUT (2026-11-17): who may WRITE on a case once it is no longer open.

Owner rulings (decisions.md 2026-11-17): the reviewer's relationship ends at awarded (R5, 16 Nov);
an assigned reviewer's writes and a QC holder's org-wide writes end once the case is not open
(17 Nov, "yes"; "QCs are reviewers as well, just that they have additional permission"). Past the
open case the writer is a `scholars` holder of the own organisation, or a super. Two doors are
narrower or wider than that, also by owner answer on 17 Nov:
  * a tranche write needs the Scholars file-writer AND `payments.may_prepare` ("Scholars + payments");
  * cancel-decline on a PRE-award decline still embargoed stays with the assignee and QC
    ("Reviewer + QC"): that one door judges it as the open case it returns to.
Reads are unchanged: the assigned reviewer still sees their past students.
"""
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import payments
from apps.scholarship.models import Disbursement
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort,
)

APPS = '/api/v1/admin/scholarship/applications/'
TRANCHES = '/api/v1/admin/scholarship/disbursements/'
#: (factory stage, outcome) for every OPEN status, then every status past the award.
OPEN = (('submitted', None), ('shortlisted', None), ('profile_complete', None),
        ('interviewing', None), ('awaiting_qc', 'recommend'), ('recommended', None))
PAST_AWARD = ('awarded', 'active', 'maintenance', 'closed')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _World(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort()
        org = cls.cohort.owning_organisation
        cls.reviewer = make_admin('reviewer', owning_org=org)
        cls.qc = make_admin('qc', owning_org=org)
        cls.admin = make_admin('admin', owning_org=org)            # the preset: scholars + payments_prepare
        cls.scholars_only = make_admin('admin', owning_org=org, permissions=['scholars'])
        cls.org_admin = make_admin('org_admin', owning_org=org)
        cls.super = make_admin(super_admin=True)
        other = make_cohort()
        cls.other_admin = make_admin('admin', owning_org=other.owning_organisation)

    def case(self, stage, outcome=None, **kw):
        return make_application(stage, outcome=outcome, cohort=self.cohort, reviewer=self.reviewer, **kw)

    def patch(self, who, app):
        return authed_client(who).patch(f'{APPS}{app.id}/', {'mentoring_candidate': True}, format='json')


class TheCaseRule(_World):
    def test_assigned_reviewer_writes_at_every_open_status(self):
        for stage, outcome in OPEN:
            with self.subTest(stage=stage):
                self.assertEqual(self.patch(self.reviewer, self.case(stage, outcome)).status_code, 200)

    def test_assigned_reviewer_is_refused_once_the_case_is_past_the_award(self):
        for stage in PAST_AWARD:
            with self.subTest(stage=stage):
                self.assertEqual(self.patch(self.reviewer, self.case(stage)).status_code, 403)

    def test_a_reopened_decision_is_still_the_assignees(self):
        app = self.case('rejected', decision_reopened_at=timezone.now())
        self.assertEqual(self.patch(self.reviewer, app).status_code, 200)

    def test_qc_writes_while_open_and_not_after_the_award(self):
        self.assertEqual(self.patch(self.qc, self.case('interviewing')).status_code, 200)
        for stage in PAST_AWARD:
            with self.subTest(stage=stage):
                self.assertEqual(self.patch(self.qc, self.case(stage)).status_code, 403)

    def test_a_scholars_holder_writes_after_the_award_in_their_own_organisation(self):
        for who in (self.admin, self.scholars_only, self.org_admin):
            for stage in PAST_AWARD:
                with self.subTest(who=who.role, stage=stage):
                    self.assertEqual(self.patch(who, self.case(stage)).status_code, 200)

    def test_a_scholars_only_holder_gains_nothing_on_an_open_case(self):
        self.assertEqual(self.patch(self.scholars_only, self.case('interviewing')).status_code, 403)

    def test_another_organisations_scholars_holder_gets_404(self):
        self.assertEqual(self.patch(self.other_admin, self.case('active')).status_code, 404)

    def test_super_always_writes(self):
        for stage in ('interviewing', *PAST_AWARD):
            with self.subTest(stage=stage):
                self.assertEqual(self.patch(self.super, self.case(stage)).status_code, 200)

    def test_reads_are_unchanged_for_the_assigned_reviewer(self):
        for stage in PAST_AWARD:
            with self.subTest(stage=stage):
                r = authed_client(self.reviewer).get(f'{APPS}{self.case(stage).id}/')
                self.assertEqual(r.status_code, 200)
                self.assertIs(r.json()['can_write'], False)


class TheServedFlags(_World):
    def get(self, who, app):
        return authed_client(who).get(f'{APPS}{app.id}/').json()

    def test_can_write_is_the_rule_for_each_viewer(self):
        open_case, funded = self.case('interviewing'), self.case('active')
        self.assertIs(self.get(self.reviewer, open_case)['can_write'], True)
        self.assertIs(self.get(self.qc, open_case)['can_write'], True)
        self.assertIs(self.get(self.qc, funded)['can_write'], False)
        self.assertIs(self.get(self.admin, funded)['can_write'], True)
        self.assertIs(self.get(self.super, funded)['can_write'], True)

    def test_a_held_pre_award_decline_serves_its_own_door(self):
        body = self.get(self.reviewer, self.case('rejected'))
        self.assertIs(body['can_write'], False)
        self.assertIs(body['can_cancel_decline'], True)


class CancelDecline(_World):
    def post(self, who, app):
        return authed_client(who).post(f'{APPS}{app.id}/cancel-decline/', {}, format='json')

    def test_a_held_pre_award_decline_stays_with_the_assignee_and_qc(self):
        for who in (self.reviewer, self.qc):
            with self.subTest(who=who.role):
                app = self.case('rejected')
                self.assertEqual(self.post(who, app).status_code, 200)
                app.refresh_from_db()
                self.assertEqual(app.status, 'interviewed')

    def test_a_held_pre_award_decline_is_not_widened_to_the_scholars_key(self):
        self.assertEqual(self.post(self.scholars_only, self.case('rejected')).status_code, 403)

    def test_a_held_decline_of_a_funded_student_is_the_scholars_holders(self):
        def contractual():
            return self.case('rejected', pre_decline_status='active', rejection_category='contractual',
                             pending_rejection_category='contractual')
        self.assertEqual(self.post(self.reviewer, contractual()).status_code, 403)
        self.assertEqual(self.post(self.admin, contractual()).status_code, 200)

    def test_hold_award_in_the_cool_off_is_the_scholars_holders(self):
        url = f'{APPS}{self.case("awarded").id}/hold-award/'
        self.assertEqual(authed_client(self.reviewer).post(url, {}, format='json').status_code, 403)
        self.assertEqual(authed_client(self.admin).post(url, {}, format='json').status_code, 200)


class Tranches(_World):
    """Owner, 17 Nov: "Scholars + payments" — every tranche write, on `payments.may_prepare`."""

    def tranche(self):
        return Disbursement.objects.create(application=self.case('active'), amount=Decimal('500'),
                                           status='scheduled', sequence=1)

    def act(self, who, disb):
        return authed_client(who).post(f'{TRANCHES}{disb.id}/mark_due/', {}, format='json')

    def test_the_payments_key_is_what_the_scholars_only_holder_lacks(self):
        self.assertFalse(payments.may_prepare(self.scholars_only))
        self.assertTrue(payments.may_prepare(self.admin))

    def test_an_action_needs_scholars_and_payments(self):
        for who, code in ((self.reviewer, 403), (self.qc, 403), (self.admin, 200),
                          (self.org_admin, 200), (self.super, 200)):
            with self.subTest(who=who.role):
                self.assertEqual(self.act(who, self.tranche()).status_code, code)
        r = self.act(self.scholars_only, self.tranche())
        self.assertEqual((r.status_code, r.json()['error']), (403, 'tranche_needs_payments'))

    def test_scheduling_needs_scholars_and_payments(self):
        def schedule(who):
            app = self.case('active')
            return authed_client(who).post(f'{APPS}{app.id}/disbursements/', {'amount': '500'}, format='json')
        self.assertEqual(schedule(self.admin).status_code, 200)
        self.assertEqual(schedule(self.reviewer).status_code, 403)
        r = schedule(self.scholars_only)
        self.assertEqual((r.status_code, r.json()['error']), (403, 'tranche_needs_payments'))


class AReopenedFundedCaseIsNotOpen(_World):
    """Review round (18 Nov): `reopen_decision` leaves awarded / active / maintenance where they are
    and sets only `decision_reopened_at`; that must not hand the case back to the reviewer or QC."""

    def funded(self, stage='maintenance'):
        return self.case(stage, decision_reopened_at=timezone.now())

    def test_reviewer_and_qc_are_refused_every_write(self):
        for who in (self.reviewer, self.qc):
            c = authed_client(who)
            app = self.funded()
            disb = Disbursement.objects.create(application=app, amount=Decimal('500'),
                                               status='scheduled', sequence=1)
            awarded = self.funded('awarded')
            for door, r in (
                    ('tranche', c.post(f'{TRANCHES}{disb.id}/mark_due/', {}, format='json')),
                    ('schedule', c.post(f'{APPS}{app.id}/disbursements/', {'amount': '500'}, format='json')),
                    ('patch', self.patch(who, app)),
                    ('close', c.post(f'{APPS}{app.id}/close/', {'closure_reason': 'graduated'}, format='json')),
                    ('hold-award', c.post(f'{APPS}{awarded.id}/hold-award/', {}, format='json'))):
                with self.subTest(who=who.role, door=door):
                    self.assertEqual(r.status_code, 403)

    def test_the_served_flags_are_false_for_them_and_true_for_a_scholars_and_payments_holder(self):
        app = self.funded()
        # (A Scholars-only holder has no B40 read, so never sees this payload: reads are unchanged.)
        no_payments = make_admin('admin', owning_org=self.cohort.owning_organisation,
                                 permissions=['see_all', 'scholars'])
        for who, flags in ((self.reviewer, (False, False)), (self.qc, (False, False)),
                           (no_payments, (True, False)), (self.admin, (True, True)),
                           (self.org_admin, (True, True))):
            with self.subTest(who=who.role):
                body = authed_client(who).get(f'{APPS}{app.id}/').json()
                self.assertEqual((body['can_write'], body['can_tranche']), flags)


class ACaseThatEndedBeforeTheAward(_World):
    """Owner 18 Nov: a case rejected, withdrawn, expired or closed before the award is written by
    "Those with 'Reject or close applications' permissions" — `students.approve` — or a super."""

    def ended(self):
        closed = self.case('recommended')
        closed.status, closed.closure_reason = 'closed', 'stalled'
        withdrawn = self.case('submitted')
        withdrawn.status = 'withdrawn'
        for row in (closed, withdrawn):
            row.save(update_fields=['status', 'closure_reason'])
        return {'rejected': self.case('rejected'), 'expired': self.case('expired'),
                'withdrawn': withdrawn, 'closed': closed}

    def test_only_a_students_approve_holder_or_a_super_writes(self):
        approver = make_admin('reviewer', owning_org=self.cohort.owning_organisation,
                              permissions=['review', 'students.approve'])
        for state, app in self.ended().items():
            for who, code in ((self.reviewer, 403), (self.qc, 403), (self.admin, 403),
                              (self.scholars_only, 403), (self.org_admin, 200), (approver, 200),
                              (self.super, 200), (self.other_admin, 404)):
                with self.subTest(state=state, who=who.role):
                    self.assertEqual(self.patch(who, app).status_code, code)

    def test_can_write_follows_the_same_rule(self):
        app = self.ended()['expired']
        for who, flag in ((self.reviewer, False), (self.qc, False), (self.org_admin, True)):
            with self.subTest(who=who.role):
                self.assertIs(authed_client(who).get(f'{APPS}{app.id}/').json()['can_write'], flag)

    def test_a_close_from_a_funded_file_stays_the_scholars_holders(self):
        funded = self.case('closed')                 # graduated, `active_at` set: a file
        self.assertEqual(self.patch(self.scholars_only, funded).status_code, 200)
        self.assertEqual(self.patch(self.reviewer, funded).status_code, 403)

    def test_reads_are_unchanged_by_the_new_write_rule(self):
        # Reads are not widened (lead brief): `students.approve` brings no B40 read on its own,
        # so a holder without `see_all` or `qc` writes on such a case only by direct call.
        org = self.cohort.owning_organisation
        app = self.ended()['expired']
        for keys, read in ((['review', 'students.approve'], 403), (['students.approve'], 403),
                           (['see_all', 'students.approve'], 200)):
            with self.subTest(keys=keys):
                who = make_admin('admin', owning_org=org, permissions=keys)
                self.assertEqual(authed_client(who).get(f'{APPS}{app.id}/').status_code, read)
                self.assertEqual(self.patch(who, app).status_code, 200)
