"""Request #39 Sprint 4 — the staff-permission editor (People → a person → "What <name> can do").

`GET / PATCH /api/v1/admin/admins/<id>/permissions/`. The roadmap's Sprint 4 door list, a test each:
the PATCH (each refusal and each consequence), Change role (resets), revoke and restore (the set
survives), delete (the history survives), an assignment racing a `review` removal (the lock and the
re-check), granting `payments_approve` / `payments_check` mid-run (S2's live rules), and the edited
person's cached `/admin/role/` (the server refuses at once). Plus the readers: People's chips on
both lists, and the reviewer page's `pausable`.

The acceptance case is Rohini's — a Reviewer given Spending THROUGH THE ENDPOINT, then every gate
asked as `test_permission_combinations.TestReviewerPlusSpending` asks it.
"""
import datetime

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses import staff_permissions as sp
from apps.courses.models import PartnerAdmin
from apps.scholarship import payments
from apps.scholarship.models import PaymentRun, StaffPermissionChange
from apps.scholarship.services import AssignmentError, assign_reviewer
from apps.scholarship.tests import test_payment_endpoints as pe
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
)
from apps.scholarship.views_admin import _AdminBase

API = dict(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
APPS = '/api/v1/admin/scholarship/applications/'
SPENDING = '/api/v1/admin/scholarship/spending/'
RUNS = '/api/v1/admin/scholarship/payment-runs/'
SEEN = timezone.make_aware(datetime.datetime(2026, 9, 1))


def _url(target):
    return f'/api/v1/admin/admins/{target.pk}/permissions/'


def _patch(who, target, keys, **extra):
    return authed_client(who).patch(_url(target), {'permissions': keys, **extra}, format='json')


def _fresh(admin):
    admin.refresh_from_db()
    return admin


class TestRohiniThroughTheScreen(pe._Base):
    """THE ACCEPTANCE CASE: the org admin gives the Reviewer Spending through the endpoint the screen
    calls; every gate then answers as Sprint 3's combination tests say."""

    def test_reviewer_plus_spending_made_by_the_editor(self):
        self._auth('pe-ap')                                  # the org admin of org A
        dry = self.client.patch(_url(self.reviewer), {'permissions': ['review', 'spending'],
                                                      'dry_run': True}, format='json')
        self.assertEqual(dry.status_code, 200, dry.content[:300])
        self.assertEqual((dry.json()['added'], dry.json()['removed'], dry.json()['consequences']),
                         (['spending'], [], []))
        self.assertIsNone(_fresh(self.reviewer).permissions)          # a dry run writes nothing
        r = self.client.patch(_url(self.reviewer), {'permissions': ['spending', 'review']},
                              format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertEqual((r.json()['permissions'], r.json()['custom'], r.json()['changed']),
                         (['review', 'spending'], True, True))
        rohini = _fresh(self.reviewer)
        self.assertEqual(rohini.permissions, ['review', 'spending'])
        # Every gate, as S3's TestReviewerPlusSpending asks it.
        self._auth('pe-rv')
        self.assertEqual(self.client.get(SPENDING).status_code, 200)
        self.assertEqual(_AdminBase()._b40_scope(rohini), 'assigned')
        self.assertEqual(self.client.get(APPS).json()['applications'], [])
        self.assertEqual(self.client.get(f'{APPS}{self.app_a.id}/').status_code, 403)
        self.assertEqual(self.client.get(RUNS).status_code, 403)
        # Her own /admin/role/ now serves the set (her menu follows on her next load).
        role = self.client.get('/api/v1/admin/role/').json()
        self.assertEqual((role['permissions'], role['custom']), (['review', 'spending'], True))

    def test_her_cached_role_is_not_trusted_the_server_refuses_at_once(self):
        PartnerAdmin.objects.filter(pk=self.reviewer.pk).update(permissions=['review', 'spending'])
        self._auth('pe-rv')
        self.assertEqual(self.client.get(SPENDING).status_code, 200)
        self._auth('pe-ap')
        self.assertEqual(self.client.patch(_url(self.reviewer), {'permissions': ['review']},
                                           format='json').status_code, 200)
        self._auth('pe-rv')                                  # same browser tab, old menu
        self.assertEqual(self.client.get(SPENDING).status_code, 403)
        self.assertIsNone(_fresh(self.reviewer).permissions)  # back on the preset = NULL


@override_settings(**API)
class TestFenceAndRefusals(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org, cls.other = make_org(), make_org()
        cls.org_admin = make_admin('org_admin', owning_org=cls.org)
        cls.colleague = make_admin('org_admin', owning_org=cls.org)
        cls.super = make_admin('super', super_admin=True)
        cls.admin = make_admin('admin', owning_org=cls.org)
        cls.reviewer = make_admin('reviewer', owning_org=cls.org)
        cls.foreign = make_admin('reviewer', owning_org=cls.other)
        cls.partner = make_admin('partner')

    def test_get_serves_the_editor(self):
        r = authed_client(self.org_admin).get(_url(self.reviewer))
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertEqual(r.json()['preset'], ['review'])
        self.assertEqual(r.json()['permissions'], ['review'])
        self.assertFalse(r.json()['custom'])
        self.assertTrue(r.json()['editable'])
        self.assertNotIn('manage_team', r.json()['keys'])
        self.assertEqual(r.json()['keys'], [k for k in sp.CATALOGUE if k != 'manage_team'])

    def test_only_a_super_or_an_org_admin_knocks(self):
        for who in (self.admin, self.reviewer):
            self.assertEqual(authed_client(who).get(_url(self.reviewer)).status_code, 403)
            self.assertEqual(_patch(who, self.reviewer, ['review']).status_code, 403)

    def test_another_organisation_and_a_fellow_org_admin_are_404(self):
        for target in (self.foreign, self.colleague, self.org_admin, self.super, self.partner):
            self.assertEqual(authed_client(self.org_admin).get(_url(target)).status_code, 404)
            self.assertEqual(_patch(self.org_admin, target, ['review']).status_code, 404)

    def test_a_super_still_cannot_edit_a_lead_tier_super_or_partner_row(self):
        for target in (self.org_admin, self.partner):
            r = _patch(self.super, target, ['review'])
            self.assertEqual((r.status_code, r.json()['code']), (400, 'not_editable'))
            self.assertFalse(authed_client(self.super).get(_url(target)).json()['editable'])

    def test_nobody_edits_their_own_row(self):
        r = _patch(self.super, self.super, ['review'])
        self.assertEqual((r.status_code, r.json()['code']), (403, 'own_permissions'))
        self.assertEqual(_patch(self.org_admin, self.org_admin, ['review']).status_code, 404)

    def test_each_bad_list_is_refused_and_nothing_is_written(self):
        cases = [
            (['review', 'nonsense'], 400, 'unknown_permission'),
            (['review', 'manage_team'], 400, 'lead_tier'),
            (['qc'], 400, 'qc_needs_see_all'),
            ('review', 400, 'bad_request'),
            ([1, 2], 400, 'bad_request'),
        ]
        for keys, status, code in cases:
            r = _patch(self.org_admin, self.reviewer, keys)
            self.assertEqual((r.status_code, r.json()['code']), (status, code), keys)
            r = _patch(self.org_admin, self.reviewer, keys, dry_run=True)
            self.assertEqual(r.json()['code'], code)                   # a dry run refuses alike
        r = authed_client(self.org_admin).patch(_url(self.reviewer), {'dry_run': True}, format='json')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'bad_request'))
        self.assertIsNone(_fresh(self.reviewer).permissions)
        self.assertFalse(StaffPermissionChange.objects.exists())

    def test_qc_with_see_all_is_accepted(self):
        r = _patch(self.org_admin, self.reviewer, ['review', 'see_all', 'qc'])
        self.assertEqual(r.status_code, 200, r.content[:300])

    def test_a_revoked_person_is_restored_first(self):
        gone = make_admin('reviewer', owning_org=self.org, is_active=False)
        r = _patch(self.org_admin, gone, ['review', 'spending'])
        self.assertEqual((r.status_code, r.json()['code']), (400, 'not_active'))


@override_settings(**API)
class TestSavingAndHistory(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.org_admin = make_admin('org_admin', owning_org=cls.org)

    def test_a_save_writes_the_row_a_history_line_and_an_audit_line(self):
        target = make_admin('reviewer', owning_org=self.org)
        with self.assertLogs('apps.scholarship.views_admin', level='INFO') as logs:
            r = _patch(self.org_admin, target, ['review', 'spending'])
        self.assertEqual(r.status_code, 200)
        h = StaffPermissionChange.objects.get()
        self.assertEqual((h.target_id, h.target_email, h.kind, h.role, h.before, h.after),
                         (target.pk, target.email, 'edit', 'reviewer', ['review'],
                          ['review', 'spending']))
        self.assertEqual((h.changed_by_email, h.changed_by_role, h.organisation_id),
                         (self.org_admin.email, 'org_admin', self.org.pk))
        line = ' '.join(logs.output)
        self.assertIn(f'AUDIT staff_permissions_changed by={self.org_admin.email} target={target.pk}'
                      f' role=reviewer before=review after=review,spending', line)

    def test_the_preset_is_stored_as_null_and_an_unchanged_save_writes_nothing(self):
        target = make_admin('admin', owning_org=self.org)
        r = _patch(self.org_admin, target, ['payments_prepare', 'see_all', 'spending'])
        self.assertEqual((r.json()['changed'], r.json()['custom']), (False, False))
        self.assertFalse(StaffPermissionChange.objects.exists())
        _patch(self.org_admin, target, ['see_all', 'payments_prepare'])          # minus Spending
        self.assertEqual(_fresh(target).permissions, ['see_all', 'payments_prepare'])
        r = _patch(self.org_admin, target, ['see_all', 'spending', 'payments_prepare'])   # reset
        self.assertEqual((r.json()['custom'], r.json()['added']), (False, ['spending']))
        self.assertIsNone(_fresh(target).permissions)
        self.assertEqual(StaffPermissionChange.objects.count(), 2)

    def test_an_empty_set_is_allowed_and_holds_nothing(self):
        target = make_admin('finance', owning_org=self.org)
        r = _patch(self.org_admin, target, [])
        self.assertEqual((r.status_code, r.json()['removed']), (200, ['payments_approve']))
        self.assertEqual(sp.resolve(_fresh(target)), ())

    def test_revoke_and_restore_keep_the_set(self):
        target = make_admin('reviewer', owning_org=self.org)
        _patch(self.org_admin, target, ['review', 'spending'])
        client = authed_client(self.org_admin)
        for action in ('revoke', 'restore'):
            r = client.patch(f'/api/v1/admin/admins/{target.pk}/revoke/', {'action': action},
                             format='json')
            self.assertEqual(r.status_code, 200, r.content[:300])
            self.assertEqual(_fresh(target).permissions, ['review', 'spending'])
        self.assertTrue(target.is_active)
        self.assertTrue(target.has_perm('spending'))

    def test_a_delete_keeps_the_history(self):
        target = make_admin('admin', owning_org=self.org)
        _patch(self.org_admin, target, ['see_all'])
        email = target.email
        target.delete()
        h = StaffPermissionChange.objects.get()
        self.assertEqual((h.target_id, h.target_email), (None, email))


@override_settings(**API)
class TestCasesAreNeverStranded(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.cohort = make_cohort(owning_organisation=cls.org)
        cls.org_admin = make_admin('org_admin', owning_org=cls.org)

    def test_removing_review_from_somebody_holding_a_case_is_refused(self):
        target = make_admin('reviewer', owning_org=self.org)
        make_application('assigned', reviewer=target, cohort=self.cohort)
        for dry in (True, False):
            r = _patch(self.org_admin, target, ['see_all', 'qc'], dry_run=dry)
            self.assertEqual((r.status_code, r.json()['code'], r.json()['open_cases']),
                             (409, 'has_open_cases', 1))
        self.assertIsNone(_fresh(target).permissions)
        # Adding to the set strands nothing.
        self.assertEqual(_patch(self.org_admin, target, ['review', 'spending']).status_code, 200)

    def test_removing_see_all_from_an_admin_holding_a_case_is_refused_unless_review_stays(self):
        target = make_admin('admin', owning_org=self.org)
        make_application('assigned', reviewer=target, cohort=self.cohort)      # a super's R1 choice
        r = _patch(self.org_admin, target, ['spending', 'payments_prepare'])
        self.assertEqual((r.status_code, r.json()['code']), (409, 'has_open_cases'))
        r = _patch(self.org_admin, target, ['review', 'spending', 'payments_prepare'])
        self.assertEqual(r.status_code, 200, r.content[:300])

    def test_a_finished_case_does_not_block(self):
        target = make_admin('reviewer', owning_org=self.org)
        make_application('rejected', reviewer=target, cohort=self.cohort)
        self.assertEqual(_patch(self.org_admin, target, ['see_all', 'qc']).status_code, 200)

    def test_an_assignment_racing_the_removal_re_reads_the_target(self):
        """The TD-382 class: the assign service re-reads its target under the editor's row lock, so
        a page that loaded before `review` was taken away cannot hand the case over."""
        target = make_admin('reviewer', owning_org=self.org)
        stale = PartnerAdmin.objects.get(pk=target.pk)          # holds `review` in memory
        self.assertEqual(_patch(self.org_admin, target, ['see_all', 'qc']).status_code, 200)
        app = make_application('profile_complete', cohort=self.cohort)
        with self.assertRaises(AssignmentError) as caught:
            assign_reviewer(app, reviewer=stale, by_admin=self.org_admin)
        self.assertEqual(caught.exception.code, 'not_reviewer')
        app.refresh_from_db()
        self.assertIsNone(app.assigned_to_id)


@override_settings(**API)
class TestConsequences(TestCase):
    """Every consequence code the dry run names, from the same holders the payment chain reads."""

    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.org_admin = make_admin('org_admin', owning_org=cls.org)

    def _says(self, target, keys):
        r = _patch(self.org_admin, target, keys, dry_run=True)
        self.assertEqual(r.status_code, 200, r.content[:300])
        return r.json()['consequences']

    def test_the_first_approver_turns_the_fallback_off_and_the_last_turns_it_on(self):
        admin = make_admin('admin', owning_org=self.org, first_seen_at=SEEN)
        self.assertIn('approver_fallback_off',
                      self._says(admin, ['see_all', 'spending', 'payments_prepare',
                                         'payments_approve']))
        fin = make_admin('finance', owning_org=self.org, first_seen_at=SEEN)
        self.assertEqual(self._says(fin, []), ['approver_fallback_on'])
        make_admin('finance', owning_org=self.org, first_seen_at=SEEN)        # a second approver
        self.assertEqual(self._says(fin, []), [])

    def test_the_check_step_switches_on_and_off(self):
        target = make_admin('reviewer', owning_org=self.org, first_seen_at=SEEN)
        self.assertEqual(self._says(target, ['review', 'payments_check']), ['check_on'])
        _patch(self.org_admin, target, ['review', 'payments_check'])
        self.assertTrue(payments.finance_check_required(self.org))            # the live rule moved
        self.assertEqual(self._says(target, ['review']), ['check_off'])

    def test_someone_who_never_signed_in_changes_nothing_until_they_do(self):
        target = make_admin('admin', owning_org=self.org)                      # first_seen_at NULL
        self.assertEqual(self._says(target, ['see_all', 'payments_approve']), ['not_signed_in'])

    def test_finance_given_review_is_told_the_files_widen(self):
        fin = make_admin('finance', owning_org=self.org, first_seen_at=SEEN)
        self.assertEqual(self._says(fin, ['review', 'payments_approve']), ['files_widened_assigned'])

    def test_see_all_is_named_as_every_file_not_assigned_only(self):
        """Review fix 3: Finance or a Reviewer given See all reads EVERY student's file."""
        fin = make_admin('finance', owning_org=self.org, first_seen_at=SEEN)
        self.assertEqual(self._says(fin, ['see_all', 'payments_approve']), ['files_widened_all'])
        rev = make_admin('reviewer', owning_org=self.org)
        self.assertEqual(self._says(rev, ['review', 'see_all']), ['files_widened_all'])
        self.assertEqual(self._says(rev, ['review', 'spending']), [])

    def test_prepare_and_approve_together_is_named(self):
        fin = make_admin('finance', owning_org=self.org, first_seen_at=SEEN)
        self.assertEqual(self._says(fin, ['payments_prepare', 'payments_approve']),
                         ['prepare_and_approve'])

    def test_granting_approve_mid_run_moves_the_live_rule(self):
        """S2's live rule, door list: a run already at `admin_signed` changes approver the moment
        the grant lands — nothing is stored on the run."""
        maker = make_admin('admin', owning_org=self.org, first_seen_at=SEEN)
        run = PaymentRun.objects.create(organisation=self.org, payment_date=datetime.date(2026, 11, 1),
                                        status='admin_signed', created_by=maker.email,
                                        admin_signed_email=maker.email)
        self.assertTrue(payments.approver_fallback(run))
        reviewer = make_admin('reviewer', owning_org=self.org, first_seen_at=SEEN)
        _patch(self.org_admin, reviewer, ['review', 'payments_approve'])
        self.assertFalse(payments.approver_fallback(run))
        self.assertEqual(payments.next_step_for(run, _fresh(reviewer)), 'approve')


@override_settings(**API)
class TestChangeRoleResets(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.org_admin = make_admin('org_admin', owning_org=cls.org)

    def _role(self, target, role, **extra):
        return authed_client(self.org_admin).patch(
            f'/api/v1/admin/admins/{target.pk}/role/', {'role': role, **extra}, format='json')

    def test_a_custom_set_goes_back_to_the_new_preset_and_the_dry_run_says_so(self):
        target = make_admin('reviewer', owning_org=self.org)
        _patch(self.org_admin, target, ['review', 'spending'])
        dry = self._role(target, 'qc', dry_run=True)
        self.assertTrue(dry.json()['permissions_reset'])
        self.assertEqual(_fresh(target).permissions, ['review', 'spending'])
        r = self._role(target, 'qc')
        self.assertEqual((r.status_code, r.json()['permissions_reset']), (200, True))
        target = _fresh(target)
        self.assertEqual((target.role, target.permissions), ('qc', None))
        self.assertEqual(sp.resolve(target), ('see_all', 'qc'))
        h = StaffPermissionChange.objects.filter(kind='role_change').get()
        self.assertEqual((h.before, h.after, h.role, h.changed_by_email),
                         (['review', 'spending'], ['see_all', 'qc'], 'qc', self.org_admin.email))

    def test_a_preset_holder_changes_role_with_no_reset_and_no_history(self):
        target = make_admin('reviewer', owning_org=self.org)
        r = self._role(target, 'qc')
        self.assertFalse(r.json()['permissions_reset'])
        self.assertFalse(StaffPermissionChange.objects.exists())


@override_settings(**API)
class TestPeopleChipsAndPause(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.org_admin = make_admin('org_admin', owning_org=cls.org)
        cls.rohini = make_admin('reviewer', owning_org=cls.org,
                                permissions=['review', 'spending'])
        cls.fin = make_admin('finance', owning_org=cls.org,
                             permissions=['review', 'payments_approve'])
        cls.checker = make_admin('reviewer', owning_org=cls.org, permissions=['see_all', 'qc'])
        cls.plain = make_admin('admin', owning_org=cls.org)

    def test_the_staff_list_serves_the_chips(self):
        rows = {a['id']: a for a in
                authed_client(self.org_admin).get('/api/v1/admin/admins/').json()['admins']}
        self.assertEqual((rows[self.rohini.pk]['custom'], rows[self.rohini.pk]['permissions_added'],
                          rows[self.rohini.pk]['permissions_removed']), (True, ['spending'], []))
        self.assertEqual((rows[self.plain.pk]['custom'], rows[self.plain.pk]['permissions_added']),
                         (False, []))
        lead = rows[self.org_admin.pk]
        self.assertEqual((lead['custom'], lead['permissions_added']), (False, []))

    def test_the_reviewers_list_serves_the_same_chips(self):
        rows = {a['id']: a for a in
                authed_client(self.org_admin).get('/api/v1/admin/reviewers/').json()['reviewers']}
        self.assertEqual(rows[self.checker.pk]['permissions_added'], ['see_all', 'qc'])
        self.assertEqual(rows[self.checker.pk]['permissions_removed'], ['review'])
        self.assertEqual(rows[self.fin.pk]['permissions_added'], ['review'])

    def test_pausable_follows_the_pause_endpoint(self):
        client = authed_client(self.org_admin)
        for target, expect in ((self.rohini, True), (self.fin, True), (self.checker, False)):
            detail = client.get(f'/api/v1/admin/reviewers/{target.pk}/').json()
            self.assertEqual(detail['pausable'], expect, target.permissions)
            r = client.post(f'/api/v1/admin/reviewers/{target.pk}/pause/', {'paused': True},
                            format='json')
            self.assertEqual(r.status_code, 200 if expect else 400, r.content[:200])

@override_settings(**API)
class TestReviewFixes(TestCase):
    """The Sprint 4 adversarial review (2026-10-21): SHIP AFTER FIXES. One test per finding."""

    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.cohort = make_cohort(owning_organisation=cls.org)
        cls.org_admin = make_admin('org_admin', owning_org=cls.org, first_seen_at=SEEN)

    # 1 (HIGH) — nobody vanishes from People.
    def test_a_reviewer_or_qc_must_keep_review_or_qc(self):
        rev = make_admin('reviewer', owning_org=self.org)
        qc = make_admin('qc', owning_org=self.org)
        for target, keys in ((rev, ['spending']), (rev, []), (qc, ['see_all', 'spending'])):
            for dry in (True, False):
                r = _patch(self.org_admin, target, keys, dry_run=dry)
                self.assertEqual((r.status_code, r.json()['code']), (400, 'would_leave_people'), keys)
        self.assertIsNone(_fresh(rev).permissions)
        self.assertEqual(_patch(self.org_admin, rev, ['see_all', 'qc']).status_code, 200)
        self.assertEqual(_patch(self.org_admin, qc, ['review']).status_code, 200)
        # Admin / Finance are listed by ROLE on the Admins tab, so an empty set stays reachable.
        self.assertEqual(_patch(self.org_admin, make_admin('admin', owning_org=self.org), [])
                         .status_code, 200)

    # 2 (MEDIUM) — the creator of a run never approves or checks it.
    def _run(self, creator, maker):
        return PaymentRun.objects.create(
            organisation=self.org, payment_date=datetime.date(2026, 11, 1), status='admin_signed',
            created_by=creator.email.upper(), admin_signed_email=maker.email,
            admin_signed_name=maker.name)

    def test_the_creator_cannot_approve_and_the_fallback_takes_it(self):
        author = make_admin('admin', owning_org=self.org, first_seen_at=SEEN,
                            permissions=['see_all', 'payments_prepare', 'payments_approve'])
        maker = make_admin('admin', owning_org=self.org, first_seen_at=SEEN)
        run = self._run(author, maker)
        self.assertIsNone(payments.next_step_for(run, author))
        self.assertEqual(payments.eligible_approvers(run), [])
        self.assertTrue(payments.approver_fallback(run))
        self.assertEqual(payments.next_step_for(run, self.org_admin), 'approve')
        with self.assertRaises(payments.PaymentsError) as caught:
            payments.sign(run, author, author.name)
        self.assertEqual(caught.exception.code, 'same_signer')
        # Another approver who did not create it is the approver; the fallback goes off.
        other = make_admin('finance', owning_org=self.org, first_seen_at=SEEN)
        self.assertEqual(payments.eligible_approvers(run), [other])
        self.assertEqual(payments.next_step_for(run, other), 'approve')

    def test_the_creator_cannot_check_either(self):
        author = make_admin('admin', owning_org=self.org, first_seen_at=SEEN,
                            permissions=['see_all', 'payments_prepare', 'payments_check'])
        maker = make_admin('admin', owning_org=self.org, first_seen_at=SEEN)
        run = self._run(author, maker)
        self.assertEqual(payments.eligible_checkers(run), [])
        self.assertFalse(payments.check_required_for(run))     # nobody else could: no check step
        self.assertIsNone(payments.next_step_for(run, author))

    def test_an_org_admin_who_created_a_run_still_approves_under_the_fallback(self):
        maker = make_admin('admin', owning_org=self.org, first_seen_at=SEEN)
        run = self._run(self.org_admin, maker)
        self.assertEqual(payments.next_step_for(run, self.org_admin), 'approve')

    # 4 (MEDIUM) — Change role names what the reset does to the payment chain.
    def _role(self, target, role):
        return authed_client(self.org_admin).patch(
            f'/api/v1/admin/admins/{target.pk}/role/', {'role': role, 'dry_run': True}, format='json')

    def test_change_role_names_the_approval_fallback(self):
        adm = make_admin('admin', owning_org=self.org, first_seen_at=SEEN)   # no approver yet
        self.assertIn('approver_fallback_off', self._role(adm, 'finance').json()['consequences'])
        fin = make_admin('finance', owning_org=self.org, first_seen_at=SEEN)
        self.assertIn('approver_fallback_on', self._role(fin, 'admin').json()['consequences'])

    def test_a_finance_person_without_approve_changes_no_approval_by_switching(self):
        fin = make_admin('finance', owning_org=self.org, first_seen_at=SEEN, permissions=[])
        body = self._role(fin, 'admin').json()
        self.assertNotIn('approver_fallback_on', body['consequences'])
        self.assertIn('files_widened_all', body['consequences'])     # the admin preset: see_all
        self.assertTrue(body['permissions_reset'])
        self.assertEqual(body['consequence'], 'finance_check_off')   # the CREDIT check still moves

    # 5 (LOW) — a reopened decision is a held case.
    def test_a_reopened_decision_counts_as_a_held_case(self):
        rev = make_admin('reviewer', owning_org=self.org)
        make_application('rejected', reviewer=rev, cohort=self.cohort,
                         decision_reopened_at=timezone.now())
        r = _patch(self.org_admin, rev, ['see_all', 'qc'])
        self.assertEqual((r.status_code, r.json()['code']), (409, 'has_open_cases'))

    # 7 (LOW) — the caller-aware rule, on the locked row.
    def test_an_org_admin_cannot_hand_a_case_to_a_non_review_holder_through_the_service(self):
        adm = make_admin('admin', owning_org=self.org)          # an R1 target for a super only
        app = make_application('profile_complete', cohort=self.cohort)
        with self.assertRaises(AssignmentError) as caught:
            assign_reviewer(app, reviewer=adm, by_admin=self.org_admin)
        self.assertEqual(caught.exception.code, 'not_reviewer')

    # 8 (LOW) — a revoked person's card is not editable.
    def test_a_revoked_person_is_not_editable(self):
        gone = make_admin('reviewer', owning_org=self.org, is_active=False)
        body = authed_client(self.org_admin).get(_url(gone)).json()
        self.assertEqual((body['editable'], body['is_active']), (False, False))

    # 10 (NIT) — only a JSON true is a dry run; a same-set save changes nothing.
    def test_only_a_boolean_true_is_a_dry_run(self):
        rev = make_admin('reviewer', owning_org=self.org)
        r = _patch(self.org_admin, rev, ['review', 'spending'], dry_run='yes')
        self.assertEqual(r.json()['dry_run'], False)
        self.assertEqual(_fresh(rev).permissions, ['review', 'spending'])

    def test_a_reordered_same_set_writes_no_history(self):
        rev = make_admin('reviewer', owning_org=self.org, permissions=['spending', 'review'])
        r = _patch(self.org_admin, rev, ['review', 'spending'])
        self.assertEqual((r.status_code, r.json()['changed']), (200, False))
        self.assertFalse(StaffPermissionChange.objects.exists())


@override_settings(**API)
class TestPersonPageReadsTheHistory(TestCase):
    """Team → a person → Permissions (2026-10-22): the GET also serves the header and the history."""

    @classmethod
    def setUpTestData(cls):
        cls.org, cls.other = make_org(), make_org()
        cls.org_admin = make_admin('org_admin', owning_org=cls.org, name='Priya Lead')
        cls.super = make_admin('super', super_admin=True)
        cls.target = make_admin('admin', owning_org=cls.org, first_seen_at=SEEN)

    def _get(self, who, target=None):
        return authed_client(who).get(_url(target or self.target))

    def test_header_and_history_shape_newest_first(self):
        _patch(self.org_admin, self.target, ['see_all', 'payments_prepare'])       # Spending off
        _patch(self.org_admin, self.target, ['see_all', 'payments_prepare', 'payments_approve'])
        body = self._get(self.org_admin).json()
        self.assertEqual((body['email'], body['signed_in'], body['paused']),
                         (self.target.email, True, False))
        self.assertTrue(body['created_at'])
        first, second = body['history']
        self.assertEqual((first['kind'], first['role'], first['added'], first['removed']),
                         ('edit', 'admin', ['payments_approve'], []))
        self.assertEqual((second['added'], second['removed']), ([], ['spending']))
        self.assertEqual((first['by'], first['by_super']), ('Priya Lead', False))
        self.assertTrue(first['at'] and first['before'] == ['see_all', 'payments_prepare'])

    def test_the_history_is_capped_and_an_invitee_is_not_signed_in(self):
        fresh = make_admin('finance', owning_org=self.org)
        for i in range(25):
            StaffPermissionChange.objects.create(target=fresh, organisation=self.org, kind='edit',
                                                 role='finance',
                                                 before=[], after=['spending'] if i % 2 else [])
        body = self._get(self.org_admin, fresh).json()
        self.assertEqual((len(body['history']), body['signed_in']), (20, False))

    def test_a_supers_address_is_never_shown_to_an_organisation(self):
        _patch(self.super, self.target, ['see_all'])
        row = self._get(self.org_admin).json()['history'][0]
        self.assertEqual((row['by'], row['by_super']), ('', True))
        self.assertNotIn(self.super.email, str(self._get(self.org_admin).content))
        self.assertTrue(self._get(self.super).json()['history'][0]['by_super'])

    def test_another_organisations_admin_is_404_and_admin_or_finance_403(self):
        stranger = make_admin('org_admin', owning_org=self.other)
        self.assertEqual(self._get(stranger).status_code, 404)
        for role in ('admin', 'finance'):
            self.assertEqual(self._get(make_admin(role, owning_org=self.org)).status_code, 403)

    def test_a_person_moved_to_another_organisation_shows_none_of_the_old_ones_history(self):
        # A cancelled invite re-sent into another organisation reuses the row (`bring_back`).
        moved = make_admin('finance', owning_org=self.org)
        _patch(self.org_admin, moved, ['spending', 'payments_approve'])
        PartnerAdmin.objects.filter(pk=moved.pk).update(owning_organisation=self.other)
        their_lead = make_admin('org_admin', owning_org=self.other)
        res = self._get(their_lead, moved)
        self.assertEqual(res.json()['history'], [])
        self.assertNotIn(self.org_admin.email, str(res.content))

    def test_a_revoked_person_still_shows_their_history(self):
        gone = make_admin('reviewer', owning_org=self.org)
        _patch(self.org_admin, gone, ['review', 'spending'])
        PartnerAdmin.objects.filter(pk=gone.pk).update(is_active=False)
        body = self._get(self.org_admin, gone).json()
        self.assertEqual((body['is_active'], len(body['history'])), (False, 1))
        self.assertEqual(body['history'][0]['added'], ['spending'])
