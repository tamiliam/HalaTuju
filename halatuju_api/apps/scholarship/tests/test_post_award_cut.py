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
