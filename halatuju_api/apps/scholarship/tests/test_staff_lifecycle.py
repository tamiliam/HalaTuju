"""Staff lifecycle (2026-10-09): change a role within its pair, cancel properly, delete properly.

Owner's rulings: the switchable roles are Admin <-> Finance and Reviewer <-> QC, never to or from
org_admin / super / partner. A cancelled invitee's emailed password dies at Supabase too, and the
address can be invited again with a FRESH password (TD-335). A delete removes the Supabase login it
provisioned when nothing else rides on it, so a re-invite is a brand-new person. Every Supabase
call is mocked exactly as the invite tests mock it (`apps.courses.views_admin.http_requests`, which
IS the `requests` module, so the patch bites wherever it is called from).
"""
import datetime
import io
from unittest.mock import MagicMock, patch

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import PartnerAdmin, StudentProfile
from apps.scholarship import invitations, payments
from apps.scholarship.models import Invitation, PaymentRun
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
)

REQ = 'apps.courses.views_admin.http_requests'
SUPABASE = dict(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                SUPABASE_URL='https://x.supabase.co', SUPABASE_SERVICE_ROLE_KEY='svc-key')


def _resp(status=200, body=None):
    return MagicMock(status_code=status, text='', json=lambda: (body if body is not None else {}))


def _auth_user(uid, email, *, signed_in=False, owes=True, providers=('email',)):
    """An admin-API user object shaped like GoTrue's."""
    return {'id': uid, 'email': email,
            'last_sign_in_at': '2026-10-01T09:00:00Z' if signed_in else None,
            'identities': [{'provider': p} for p in providers],
            'app_metadata': {'must_change_password': owes}}


def _role(who, target, role, **extra):
    return authed_client(who).patch(f'/api/v1/admin/admins/{target.pk}/role/',
                                    {'role': role, **extra}, format='json')


@override_settings(**SUPABASE)
class TestChangeRole(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.other = make_org()
        cls.org_admin = make_admin('org_admin', owning_org=cls.org)
        cls.super = make_admin('super', super_admin=True)
        cls.foreign_admin = make_admin('org_admin', owning_org=cls.other)

    def test_admin_becomes_finance_and_the_finance_check_switches_on(self):
        target = make_admin('admin', owning_org=self.org)
        self.assertFalse(payments.finance_check_required(self.org))
        with self.assertLogs('apps.scholarship.views_admin', level='INFO') as logs:
            r = _role(self.org_admin, target, 'finance')
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertEqual((r.json()['from'], r.json()['to'], r.json()['consequence']),
                         ('admin', 'finance', 'finance_check_on'))
        target.refresh_from_db()
        self.assertEqual(target.role, 'finance')
        self.assertFalse(target.is_super_admin)
        self.assertTrue(payments.finance_check_required(self.org))
        line = ' '.join(logs.output)
        self.assertIn('AUDIT staff_role_changed', line)
        self.assertIn(f'by={self.org_admin.email} target={target.pk} from=admin to=finance', line)

    def test_a_dry_run_names_the_consequence_and_writes_nothing(self):
        target = make_admin('finance', owning_org=self.org)
        r = _role(self.org_admin, target, 'admin', dry_run=True)
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertEqual((r.json()['consequence'], r.json()['dry_run']), ('finance_check_off', True))
        target.refresh_from_db()
        self.assertEqual(target.role, 'finance')

    def test_the_last_finance_admin_becoming_admin_switches_the_check_off(self):
        target = make_admin('finance', owning_org=self.org)
        r = _role(self.org_admin, target, 'admin')
        self.assertEqual(r.json()['consequence'], 'finance_check_off')
        self.assertFalse(payments.finance_check_required(self.org))

    def test_with_another_finance_admin_there_is_no_consequence(self):
        make_admin('finance', owning_org=self.org)
        target = make_admin('finance', owning_org=self.org)
        self.assertIsNone(_role(self.org_admin, target, 'admin').json()['consequence'])
        self.assertTrue(payments.finance_check_required(self.org))

    def test_reviewer_and_qc_switch_both_ways_and_keep_their_cases(self):
        target = make_admin('reviewer', owning_org=self.org)
        app = make_application('assigned', reviewer=target,
                               cohort=make_cohort(owning_organisation=self.org))
        r = _role(self.org_admin, target, 'qc')
        self.assertEqual((r.status_code, r.json()['consequence']), (200, None), r.content[:300])
        app.refresh_from_db()
        self.assertEqual(app.assigned_to_id, target.pk)          # nothing stranded
        self.assertEqual(_role(self.org_admin, target, 'reviewer').status_code, 200)
        target.refresh_from_db()
        self.assertEqual(target.role, 'reviewer')

    def test_everything_outside_the_two_pairs_is_refused(self):
        cases = [('admin', 'reviewer'), ('admin', 'qc'), ('reviewer', 'admin'),
                 ('qc', 'finance'), ('finance', 'qc'), ('admin', 'admin'),
                 ('admin', 'org_admin'), ('reviewer', 'org_admin'), ('admin', 'super'),
                 ('finance', 'partner'), ('qc', '')]
        for old, new in cases:
            with self.subTest(old=old, new=new):
                target = make_admin(old, owning_org=self.org)
                r = _role(self.org_admin, target, new)
                self.assertEqual((r.status_code, r.json()['code']), (400, 'role_not_switchable'))
                target.refresh_from_db()
                self.assertEqual(target.role, old)

    def test_a_super_cannot_switch_an_org_admin_partner_or_super_either(self):
        for target in (make_admin('org_admin', owning_org=self.org),
                       make_admin('partner', org=self.other),
                       make_admin('super', super_admin=True)):
            with self.subTest(role=target.role):
                for new in ('admin', 'finance', 'reviewer', 'qc'):
                    r = _role(self.super, target, new)
                    self.assertEqual(r.json()['code'], 'role_not_switchable')

    def test_a_super_switches_any_organisations_staff(self):
        target = make_admin('qc', owning_org=self.other)
        self.assertEqual(_role(self.super, target, 'reviewer').status_code, 200)

    def test_another_organisations_staff_and_a_peer_org_admin_are_404(self):
        self.assertEqual(_role(self.foreign_admin, make_admin('admin', owning_org=self.org),
                               'finance').status_code, 404)
        peer = make_admin('org_admin', owning_org=self.org)
        self.assertEqual(_role(self.org_admin, peer, 'admin').status_code, 404)
        self.assertEqual(authed_client(self.org_admin).patch(
            '/api/v1/admin/admins/999999/role/', {'role': 'qc'}, format='json').status_code, 404)

    def test_only_a_super_or_an_org_admin_may_switch(self):
        target = make_admin('reviewer', owning_org=self.org)
        for role in ('admin', 'finance', 'qc', 'reviewer'):
            with self.subTest(caller=role):
                r = _role(make_admin(role, owning_org=self.org), target, 'qc')
                self.assertEqual(r.status_code, 403)
        target.refresh_from_db()
        self.assertEqual(target.role, 'reviewer')

    def test_a_revoked_account_is_restored_first(self):
        target = make_admin('admin', owning_org=self.org, is_active=False)
        r = _role(self.org_admin, target, 'finance')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'not_active'))

    def test_an_admin_holding_open_cases_cannot_become_finance(self):
        target = make_admin('admin', owning_org=self.org)
        cohort = make_cohort(owning_organisation=self.org)
        make_application('assigned', reviewer=target, cohort=cohort)
        make_application('recommended', reviewer=target, cohort=cohort)
        for dry in (True, False):
            r = _role(self.org_admin, target, 'finance', dry_run=dry)
            self.assertEqual((r.status_code, r.json()['code'], r.json()['open_cases']),
                             (409, 'has_open_cases', 2))
        target.refresh_from_db()
        self.assertEqual(target.role, 'admin')

    def test_a_finished_case_does_not_block_the_switch(self):
        target = make_admin('admin', owning_org=self.org)
        make_application('rejected', reviewer=target,
                         cohort=make_cohort(owning_organisation=self.org))
        self.assertEqual(_role(self.org_admin, target, 'finance').status_code, 200)

    def test_an_admin_with_a_run_in_progress_cannot_become_finance(self):
        target = make_admin('admin', owning_org=self.org)
        PaymentRun.objects.create(organisation=self.org, created_by=target.email,
                                  payment_date=datetime.date(2026, 10, 1))
        r = _role(self.org_admin, target, 'finance')
        self.assertEqual((r.status_code, r.json()['code']), (409, 'run_in_progress'))

    def test_L3_a_run_they_created_that_somebody_else_signed_still_blocks(self):
        target = make_admin('admin', owning_org=self.org)
        PaymentRun.objects.create(organisation=self.org, created_by=target.email,
                                  status='admin_signed', admin_signed_email='other@example.test',
                                  payment_date=datetime.date(2026, 10, 1))
        r = _role(self.org_admin, target, 'finance')
        self.assertEqual((r.status_code, r.json()['code']), (409, 'run_in_progress'))

    def test_a_finished_run_they_created_does_not_block(self):
        target = make_admin('admin', owning_org=self.org)
        PaymentRun.objects.create(organisation=self.org, created_by=target.email,
                                  status='completed', payment_date=datetime.date(2026, 9, 1))
        self.assertEqual(_role(self.org_admin, target, 'finance').status_code, 200)

    def test_L1_a_malformed_body_is_a_400_never_a_500(self):
        target = make_admin('admin', owning_org=self.org)
        url = f'/api/v1/admin/admins/{target.pk}/role/'
        client = authed_client(self.org_admin)
        for body in ({'role': 5}, {'role': ['finance']}, {'role': None}, {}, ['finance']):
            with self.subTest(body=body):
                r = client.patch(url, body, format='json')
                self.assertEqual((r.status_code, r.json()['code']), (400, 'bad_request'))
        target.refresh_from_db()
        self.assertEqual(target.role, 'admin')

    def test_a_pause_is_kept_between_reviewer_and_qc(self):
        target = make_admin('reviewer', owning_org=self.org, paused_at=timezone.now())
        _role(self.org_admin, target, 'qc')
        target.refresh_from_db()
        self.assertIsNotNone(target.paused_at)

    def test_L2_a_recorder_turned_qc_cannot_qc_their_own_verdict_after_a_reassign(self):
        # The reviewer recorded the verdict; the case was then handed to someone else (so the
        # assignment no longer names them); they are switched to QC. The recorder guard holds.
        recorder = make_admin('reviewer', owning_org=self.org)
        app = make_application('awaiting_qc', outcome='recommend', reviewer=recorder,
                               cohort=make_cohort(owning_organisation=self.org))
        type(app).objects.filter(pk=app.pk).update(
            assigned_to=make_admin('reviewer', owning_org=self.org))
        self.assertEqual(_role(self.org_admin, recorder, 'qc').status_code, 200)
        r = authed_client(recorder).post(
            f'/api/v1/admin/scholarship/applications/{app.pk}/qc-decision/',
            {'decision': 'accept'}, format='json')
        self.assertEqual((r.status_code, r.json().get('code')), (403, 'self_verdict_qc_forbidden'))

    def test_moving_to_finance_clears_a_pause(self):
        target = make_admin('admin', owning_org=self.org, paused_at=timezone.now())
        _role(self.org_admin, target, 'finance')
        target.refresh_from_db()
        self.assertIsNone(target.paused_at)

    def test_an_open_invitation_carries_the_new_role_and_an_answered_one_does_not(self):
        target = make_admin('reviewer', owning_org=self.org)
        old = invitations.create_or_refresh(audience='staff', email=target.email, role='reviewer',
                                            organisation=self.org, partner_admin=target, ttl_days=7)
        Invitation.objects.filter(pk=old.pk).update(accepted_at=timezone.now())
        live = Invitation.objects.create(audience='staff', email=target.email, role='reviewer',
                                         organisation=self.org, partner_admin=target, code='live-x')
        _role(self.org_admin, target, 'qc')
        old.refresh_from_db()
        live.refresh_from_db()
        self.assertEqual((old.role, live.role), ('reviewer', 'qc'))


@override_settings(**SUPABASE)
class TestCancelKillsThePassword(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.org_admin = make_admin('org_admin', owning_org=cls.org)

    def _staff_inv(self, role='reviewer', **kw):
        account = make_admin(role, owning_org=self.org, **kw)
        inv = invitations.create_or_refresh(
            audience='staff', email=account.email, role=role, organisation=self.org,
            invited_by=self.org_admin, partner_admin=account, credential_issued=True, ttl_days=7)
        return inv, account

    def _cancel(self, inv):
        return authed_client(self.org_admin).post(f'/api/v1/admin/invitations/{inv.pk}/cancel/')

    def test_the_emailed_password_is_rotated_dead(self):
        inv, account = self._staff_inv()
        with patch(f'{REQ}.get', return_value=_resp(
                body=_auth_user(account.supabase_user_id, account.email))), \
                patch(f'{REQ}.put', return_value=_resp()) as put, \
                self.assertLogs('apps.scholarship.views_admin', level='INFO') as logs:
            r = self._cancel(inv)
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertTrue(put.call_args[0][0].endswith(f'/auth/v1/admin/users/{account.supabase_user_id}'))
        body = put.call_args[1]['json']
        self.assertGreater(len(body['password']), 30)                 # long, random, never sent
        self.assertTrue(body['app_metadata']['temp_password_expired'])
        self.assertIsNone(body['app_metadata']['temp_password_issued_at'])
        self.assertIn('login=killed', ' '.join(logs.output))
        self.assertEqual(len(mail.outbox), 0)

    def test_a_password_they_chose_is_never_touched(self):
        inv, account = self._staff_inv()
        with patch(f'{REQ}.get', return_value=_resp(body=_auth_user(
                account.supabase_user_id, account.email, owes=False))), \
                patch(f'{REQ}.put') as put:
            self.assertEqual(self._cancel(inv).status_code, 200)
        put.assert_not_called()

    def test_a_login_that_is_also_a_student_is_left_alone(self):
        inv, account = self._staff_inv()
        StudentProfile.objects.create(supabase_user_id=account.supabase_user_id, name='Also Student')
        with patch(f'{REQ}.get') as get, patch(f'{REQ}.put') as put:
            self.assertEqual(self._cancel(inv).status_code, 200)
        get.assert_not_called()
        put.assert_not_called()

    def test_a_supabase_failure_does_not_undo_the_cancel(self):
        inv, account = self._staff_inv()
        with patch(f'{REQ}.get', return_value=_resp(500)), patch(f'{REQ}.put') as put:
            r = self._cancel(inv)
        self.assertEqual(r.status_code, 200)
        put.assert_not_called()
        account.refresh_from_db()
        self.assertFalse(account.is_active)

    def test_a_revoked_login_with_a_stale_temp_password_is_now_swept(self):
        # The daily job used to read active accounts only.
        account = make_admin('reviewer', owning_org=self.org, is_active=False)
        stale = (timezone.now() - datetime.timedelta(days=30)).isoformat()
        user = _auth_user(account.supabase_user_id, account.email)
        user['app_metadata']['temp_password_issued_at'] = stale
        mod = 'apps.courses.management.commands.expire_temp_passwords.http_requests'
        with patch(f'{mod}.get', return_value=_resp(body=user)), \
                patch(f'{mod}.put', return_value=_resp()) as put:
            call_command('expire_temp_passwords', stdout=io.StringIO())
        urls = [c[0][0] for c in put.call_args_list]
        self.assertTrue(any(u.endswith(account.supabase_user_id) for u in urls))

    def test_L4_a_revoked_row_whose_login_is_also_a_student_is_not_swept(self):
        account = make_admin('reviewer', owning_org=self.org, is_active=False)
        StudentProfile.objects.create(supabase_user_id=account.supabase_user_id, name='Student')
        stale = (timezone.now() - datetime.timedelta(days=30)).isoformat()
        user = _auth_user(account.supabase_user_id, account.email)
        user['app_metadata']['temp_password_issued_at'] = stale
        mod = 'apps.courses.management.commands.expire_temp_passwords.http_requests'
        with patch(f'{mod}.get', return_value=_resp(body=user)) as get, \
                patch(f'{mod}.put', return_value=_resp()) as put:
            call_command('expire_temp_passwords', stdout=io.StringIO())
        self.assertFalse(any(c[0][0].endswith(account.supabase_user_id) for c in get.call_args_list))
        self.assertFalse(any(c[0][0].endswith(account.supabase_user_id) for c in put.call_args_list))


@override_settings(**SUPABASE)
class TestInviteAgainAfterCancel(TestCase):
    """TD-335: the address is invited again, with a fresh password and the new invite's role."""

    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.other = make_org()
        cls.org_admin = make_admin('org_admin', owning_org=cls.org)

    def setUp(self):
        mail.outbox = []

    def _cancelled(self, role='reviewer', email=None, org=None):
        org = org or self.org
        kw = {'email': email} if email else {}
        account = make_admin(role, owning_org=org, **kw)
        inv = invitations.create_or_refresh(
            audience='staff', email=account.email, role=role, organisation=org,
            partner_admin=account, credential_issued=True, ttl_days=7)
        Invitation.objects.filter(pk=inv.pk).update(revoked_at=timezone.now())
        PartnerAdmin.objects.filter(pk=account.pk).update(is_active=False)
        return account, inv

    def _invite(self, email, role='qc', name='Again'):
        return authed_client(self.org_admin).post(
            '/api/v1/admin/invite/', {'email': email, 'name': name, 'role': role}, format='json')

    def test_a_cancelled_invitee_is_invited_again_with_a_fresh_password(self):
        account, old = self._cancelled(role='reviewer')
        user = _auth_user(account.supabase_user_id, account.email)   # still owes (killed at cancel)
        with patch(f'{REQ}.get', return_value=_resp(body=user)), \
                patch(f'{REQ}.put', return_value=_resp()) as put, \
                patch(f'{REQ}.post') as create:
            r = self._invite(account.email, role='qc')
        self.assertEqual(r.status_code, 201, r.content[:300])
        self.assertFalse(r.json()['already_registered'])
        create.assert_not_called()                                   # same login, not a new one
        password = put.call_args[1]['json']['password']
        self.assertTrue(put.call_args[1]['json']['app_metadata']['must_change_password'])
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(password, mail.outbox[0].body)
        account.refresh_from_db()
        self.assertEqual((account.is_active, account.role, account.name), (True, 'qc', 'Again'))
        new = Invitation.objects.filter(partner_admin=account).exclude(pk=old.pk).get()
        self.assertEqual((new.role, new.credential_issued, invitations.status_of(new)),
                         ('qc', True, 'invited'))
        old.refresh_from_db()
        self.assertEqual(invitations.status_of(old), 'revoked')

    def test_an_active_account_is_still_refused(self):
        account = make_admin('reviewer', owning_org=self.org)
        with patch(f'{REQ}.get') as get, patch(f'{REQ}.put') as put, patch(f'{REQ}.post') as post:
            r = self._invite(account.email)
        self.assertEqual(r.status_code, 409)
        for m in (get, put, post):
            m.assert_not_called()

    def test_somebody_who_signed_in_and_was_revoked_is_still_refused(self):
        account, _ = self._cancelled()
        PartnerAdmin.objects.filter(pk=account.pk).update(first_seen_at=timezone.now())
        self.assertEqual(self._invite(account.email).status_code, 409)

    def test_another_organisations_cancelled_invitee_is_still_refused(self):
        account, _ = self._cancelled(org=self.other)
        with patch(f'{REQ}.put') as put:
            self.assertEqual(self._invite(account.email).status_code, 409)
        put.assert_not_called()
        account.refresh_from_db()
        self.assertFalse(account.is_active)

    def test_a_login_used_with_its_own_password_is_a_person_who_arrived_so_409(self):
        # Review H1: `first_seen_at` NULL is "not recorded" for staff predating it. A login signed
        # in to with a password they chose means they came — Restore, never a re-invite.
        account, _ = self._cancelled()
        user = _auth_user(account.supabase_user_id, account.email, signed_in=True, owes=False)
        with patch(f'{REQ}.get', return_value=_resp(body=user)), patch(f'{REQ}.put') as put:
            r = self._invite(account.email)
        self.assertEqual(r.status_code, 409, r.content[:300])
        put.assert_not_called()
        account.refresh_from_db()
        self.assertEqual((account.is_active, account.role), (False, 'reviewer'))
        self.assertEqual(len(mail.outbox), 0)

    def test_H1_a_legacy_revoked_WORKER_is_never_resurrected(self):
        # The reviewer's reproduction: a revoked admin, first_seen_at NULL (not recorded), who
        # signed in long ago and made a draft payment run, re-invited as finance under a new name.
        worker = make_admin('admin', owning_org=self.org, is_active=False, name='Old Name')
        PaymentRun.objects.create(organisation=self.org, created_by=worker.email,
                                  payment_date=datetime.date(2026, 10, 1))
        user = _auth_user(worker.supabase_user_id, worker.email, signed_in=True, owes=False)
        with patch(f'{REQ}.get', return_value=_resp(body=user)) as get, \
                patch(f'{REQ}.put') as put, patch(f'{REQ}.post') as post:
            r = self._invite(worker.email, role='finance', name='New Name')
        self.assertEqual(r.status_code, 409, r.content[:300])
        for m in (get, put, post):
            m.assert_not_called()                        # refused on the footprint, before Supabase
        worker.refresh_from_db()
        self.assertEqual((worker.is_active, worker.role, worker.name), (False, 'admin', 'Old Name'))

    def test_H1_a_cancelled_invitee_already_holding_cases_is_not_brought_back(self):
        # A cancel unassigns nothing, so a never-signed-in invitee can hold assigned cases.
        account, _ = self._cancelled(role='reviewer')
        make_application('assigned', reviewer=account,
                         cohort=make_cohort(owning_organisation=self.org))
        with patch(f'{REQ}.put') as put:
            r = self._invite(account.email, role='qc')
        self.assertEqual(r.status_code, 409)
        put.assert_not_called()

    def test_H1_a_google_row_that_already_has_a_login_is_not_brought_back(self):
        account, _ = self._cancelled(email='td335.linked@gmail.com')   # factory gives it a UID
        r = self._invite(account.email)
        self.assertEqual(r.status_code, 409, r.content[:300])
        account.refresh_from_db()
        self.assertFalse(account.is_active)

    def test_a_supabase_failure_brings_nobody_back(self):
        account, _ = self._cancelled()
        with patch(f'{REQ}.get', return_value=_resp(500)):
            r = self._invite(account.email)
        self.assertEqual(r.status_code, 502)
        account.refresh_from_db()
        self.assertFalse(account.is_active)
        self.assertEqual(len(mail.outbox), 0)

    def test_a_cancelled_google_invitee_is_invited_again_without_a_password(self):
        account, _ = self._cancelled(email='td335.again@gmail.com')
        # A Google invitee who never signed in has no login yet (it appears on first sign-in).
        PartnerAdmin.objects.filter(pk=account.pk).update(supabase_user_id=None)
        with patch(f'{REQ}.get') as get, patch(f'{REQ}.put') as put:
            r = self._invite(account.email)
        self.assertEqual(r.status_code, 201, r.content[:300])
        self.assertTrue(r.json()['google'])
        get.assert_not_called()
        put.assert_not_called()
        account.refresh_from_db()
        self.assertTrue(account.is_active)


@override_settings(**SUPABASE)
class TestResendAndSignIn(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.org_admin = make_admin('org_admin', owning_org=cls.org)

    def test_resend_is_refused_for_a_switched_off_account(self):
        target = make_admin('reviewer', owning_org=self.org, is_active=False)
        with patch(f'{REQ}.put') as put:
            r = authed_client(self.org_admin).post(f'/api/v1/admin/admins/{target.pk}/resend/')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'not_active'))
        put.assert_not_called()
        self.assertEqual(len(mail.outbox), 0)

    def test_the_role_check_tells_a_withdrawn_account_so_and_nobody_else(self):
        target = make_admin('reviewer', owning_org=self.org, is_active=False)
        body = authed_client(target).get('/api/v1/admin/role/').json()
        self.assertEqual(body, {'is_admin': False, 'withdrawn': True})
        stranger = authed_client('a-uid-nobody-has').get('/api/v1/admin/role/').json()
        self.assertEqual(stranger, {'is_admin': False, 'withdrawn': False})

    def _google_client(self, email, verified):
        import jwt
        from rest_framework.test import APIClient
        token = jwt.encode({'sub': 'google-sub-td335', 'aud': 'authenticated', 'role': 'authenticated',
                            'email': email, 'email_verified': verified},
                           TEST_JWT_SECRET, algorithm='HS256')
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        return client

    def test_a_cancelled_google_invitee_signing_in_is_told_too_by_verified_email_only(self):
        # Cancelled before their first Google sign-in, so the row has no UID to match on.
        make_admin('reviewer', owning_org=self.org, is_active=False, uid=None,
                   email='cancelled.google@gmail.com')
        PartnerAdmin.objects.filter(email='cancelled.google@gmail.com').update(supabase_user_id=None)
        told = self._google_client('cancelled.google@gmail.com', True).get('/api/v1/admin/role/')
        self.assertEqual(told.json(), {'is_admin': False, 'withdrawn': True})
        claimed = self._google_client('cancelled.google@gmail.com', False).get('/api/v1/admin/role/')
        self.assertEqual(claimed.json(), {'is_admin': False, 'withdrawn': False})


@override_settings(**SUPABASE)
class TestDeleteRemovesTheLogin(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.org_admin = make_admin('org_admin', owning_org=cls.org)

    def setUp(self):
        mail.outbox = []

    def _delete(self, target):
        return authed_client(self.org_admin).delete(f'/api/v1/admin/admins/{target.pk}/')

    def test_delete_then_invite_again_is_a_brand_new_person(self):
        target = make_admin('admin', owning_org=self.org)
        with patch(f'{REQ}.get', return_value=_resp(
                body=_auth_user(target.supabase_user_id, target.email))), \
                patch(f'{REQ}.delete', return_value=_resp(200)) as gone:
            r = self._delete(target)
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertTrue(gone.call_args[0][0].endswith(f'/auth/v1/admin/users/{target.supabase_user_id}'))
        self.assertFalse(PartnerAdmin.objects.filter(pk=target.pk).exists())
        self.assertFalse(Invitation.objects.filter(email=target.email).exists())   # CASCADE
        # …and the same address is invited as if for the first time: a NEW login, a password.
        with patch(f'{REQ}.post', return_value=_resp(200, {'id': 'brand-new-uid'})) as create:
            r = authed_client(self.org_admin).post('/api/v1/admin/invite/', {
                'email': target.email, 'name': 'New Person', 'role': 'finance'}, format='json')
        self.assertEqual(r.status_code, 201, r.content[:300])
        self.assertFalse(r.json()['already_registered'])
        password = create.call_args[1]['json']['password']
        self.assertIn(password, mail.outbox[-1].body)
        again = PartnerAdmin.objects.get(email=target.email)
        self.assertEqual((again.supabase_user_id, again.role), ('brand-new-uid', 'finance'))

    def test_a_login_that_is_also_a_student_survives(self):
        target = make_admin('admin', owning_org=self.org)
        StudentProfile.objects.create(supabase_user_id=target.supabase_user_id, name='Student Too')
        with patch(f'{REQ}.get') as get, patch(f'{REQ}.delete') as gone:
            self.assertEqual(self._delete(target).status_code, 200)
        get.assert_not_called()
        gone.assert_not_called()
        self.assertTrue(StudentProfile.objects.filter(supabase_user_id=target.supabase_user_id).exists())

    def test_a_login_they_have_used_with_their_own_password_is_kept(self):
        target = make_admin('finance', owning_org=self.org)
        user = _auth_user(target.supabase_user_id, target.email, signed_in=True, owes=False)
        with patch(f'{REQ}.get', return_value=_resp(body=user)), \
                patch(f'{REQ}.delete') as gone, patch(f'{REQ}.put') as put:
            self.assertEqual(self._delete(target).status_code, 200)
        gone.assert_not_called()
        put.assert_not_called()

    def test_a_used_login_with_another_identity_only_loses_its_temp_password(self):
        target = make_admin('admin', owning_org=self.org)
        user = _auth_user(target.supabase_user_id, target.email, signed_in=True,
                          providers=('email', 'google'))
        with patch(f'{REQ}.get', return_value=_resp(body=user)), \
                patch(f'{REQ}.delete') as gone, patch(f'{REQ}.put', return_value=_resp()) as put:
            self.assertEqual(self._delete(target).status_code, 200)
        gone.assert_not_called()
        self.assertTrue(put.call_args[1]['json']['app_metadata']['temp_password_expired'])

    def test_supabase_down_deletes_nothing(self):
        target = make_admin('admin', owning_org=self.org)
        with patch(f'{REQ}.get', return_value=_resp(503)), patch(f'{REQ}.delete') as gone:
            r = self._delete(target)
        self.assertEqual((r.status_code, r.json()['code']), (502, 'login_cleanup_failed'))
        gone.assert_not_called()
        self.assertTrue(PartnerAdmin.objects.filter(pk=target.pk).exists())

    def test_a_login_already_gone_at_supabase_does_not_block_the_delete(self):
        target = make_admin('admin', owning_org=self.org)
        with patch(f'{REQ}.get', return_value=_resp(404)), patch(f'{REQ}.delete') as gone:
            self.assertEqual(self._delete(target).status_code, 200)
        gone.assert_not_called()

    def test_M1_a_finance_checker_or_an_approver_who_signed_a_run_has_work(self):
        checker = make_admin('finance', owning_org=self.org)
        approver = make_admin('org_admin', owning_org=self.org)
        PaymentRun.objects.create(organisation=self.org, created_by='maker@example.test',
                                  status='completed', finance_signed_email=checker.email,
                                  org_admin_signed_email=approver.email,
                                  payment_date=datetime.date(2026, 9, 1))
        sup = make_admin('super', super_admin=True)
        with patch(f'{REQ}.get') as get, patch(f'{REQ}.delete') as gone:
            r1 = authed_client(sup).delete(f'/api/v1/admin/admins/{checker.pk}/')
            r2 = authed_client(sup).delete(f'/api/v1/admin/admins/{approver.pk}/')
        self.assertEqual((r1.status_code, r1.json()['work']), (409, {'payment_runs_checked': 1}))
        self.assertEqual((r2.status_code, r2.json()['work']),
                         (409, {'payment_runs_countersigned': 1}))
        get.assert_not_called()
        gone.assert_not_called()

    def test_M2_the_row_goes_FIRST_and_a_failed_row_delete_never_touches_the_login(self):
        from django.db import DatabaseError
        target = make_admin('admin', owning_org=self.org)
        with patch(f'{REQ}.get', return_value=_resp(
                body=_auth_user(target.supabase_user_id, target.email))), \
                patch(f'{REQ}.delete') as gone, \
                patch.object(PartnerAdmin, 'delete', side_effect=DatabaseError('boom')):
            r = self._delete(target)
        self.assertEqual((r.status_code, r.json()['code']), (503, 'delete_failed'))
        gone.assert_not_called()
        self.assertTrue(PartnerAdmin.objects.filter(pk=target.pk).exists())

    def test_M2_a_login_removal_failing_after_the_row_is_gone_is_logged_and_adopted_later(self):
        target = make_admin('admin', owning_org=self.org)
        uid, email = target.supabase_user_id, target.email
        user = _auth_user(uid, email)
        with patch(f'{REQ}.get', return_value=_resp(body=user)), \
                patch(f'{REQ}.delete', return_value=_resp(500)), \
                self.assertLogs('apps.scholarship.staff_lifecycle', level='ERROR'):
            r = self._delete(target)
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertFalse(PartnerAdmin.objects.filter(pk=target.pk).exists())
        # The login survives at Supabase. Inviting the address again ADOPTS it — a fresh password.
        exists = _resp(422, {'error_code': 'email_exists'})

        def get(url, **kw):
            if url.endswith('/auth/v1/admin/users'):
                return _resp(body={'users': [{'id': uid, 'email': email}]})
            return _resp(body=user)
        self.assertEqual(r.json()['login'], 'failed')
        self.assertIn('could not be removed', r.json()['message'])       # N3: said honestly
        with patch(f'{REQ}.post', return_value=exists), patch(f'{REQ}.get', side_effect=get), \
                patch(f'{REQ}.put', return_value=_resp()) as put:
            r = authed_client(self.org_admin).post('/api/v1/admin/invite/', {
                'email': email, 'name': 'Again', 'role': 'admin'}, format='json')
        self.assertEqual(r.status_code, 201, r.content[:300])
        self.assertFalse(r.json()['already_registered'])
        password = put.call_args[1]['json']['password']
        self.assertIn(password, mail.outbox[-1].body)
        self.assertEqual(PartnerAdmin.objects.get(email=email).supabase_user_id, uid)

    def test_a_students_existing_login_is_never_adopted_by_an_invite(self):
        # Same "already registered" answer, but the login carries no server-written flag.
        student_login = {'id': 'stud-uid', 'email': 'stud@example.org', 'app_metadata': {},
                         'identities': [{'provider': 'email'}], 'last_sign_in_at': None}

        def get(url, **kw):
            if url.endswith('/auth/v1/admin/users'):
                return _resp(body={'users': [student_login]})
            return _resp(body=student_login)
        with patch(f'{REQ}.post', return_value=_resp(422, {'error_code': 'email_exists'})), \
                patch(f'{REQ}.get', side_effect=get), patch(f'{REQ}.put') as put:
            r = authed_client(self.org_admin).post('/api/v1/admin/invite/', {
                'email': 'stud@example.org', 'name': 'Stud', 'role': 'admin'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.json()['already_registered'])
        put.assert_not_called()

    def _invite_onto(self, existing_login):
        """Invite `existing_login['email']` while Supabase answers "already registered" and the
        read-back finds `existing_login`. Returns (response, put mock)."""
        def get(url, **kw):
            if url.endswith('/auth/v1/admin/users'):
                return _resp(body={'users': [existing_login]})
            return _resp(body=existing_login)
        with patch(f'{REQ}.post', return_value=_resp(422, {'error_code': 'email_exists'})), \
                patch(f'{REQ}.get', side_effect=get), \
                patch(f'{REQ}.put', return_value=_resp()) as put:
            r = authed_client(self.org_admin).post('/api/v1/admin/invite/', {
                'email': existing_login['email'], 'name': 'X', 'role': 'admin'}, format='json')
        return r, put

    def test_N1_a_login_signed_in_after_its_temp_password_expired_is_not_adopted(self):
        # The flag is cleared only by our set-password page; this person set a password elsewhere
        # (a reset link) after the expiry job rotated the temp one dead, and has signed in since.
        login = {'id': 'expired-then-used', 'email': 'used@example.org',
                 'identities': [{'provider': 'email'}], 'last_sign_in_at': '2026-10-05T09:00:00Z',
                 'app_metadata': {'must_change_password': True, 'temp_password_issued_at': None,
                                  'temp_password_expired': True}}
        r, put = self._invite_onto(login)
        self.assertEqual(r.status_code, 201, r.content[:300])
        self.assertTrue(r.json()['already_registered'])
        put.assert_not_called()

    def test_N1_a_sign_in_AFTER_the_issue_is_not_adopted_either(self):
        login = {'id': 'signed-after', 'email': 'after@example.org',
                 'identities': [{'provider': 'email'}], 'last_sign_in_at': '2026-10-05T09:00:00Z',
                 'app_metadata': {'must_change_password': True,
                                  'temp_password_issued_at': '2026-10-01T09:00:00+00:00'}}
        r, put = self._invite_onto(login)
        self.assertTrue(r.json()['already_registered'])
        put.assert_not_called()

    def test_N1_a_sign_in_BEFORE_a_live_issue_is_still_adopted(self):
        login = {'id': 'signed-before', 'email': 'before@example.org',
                 'identities': [{'provider': 'email'}], 'last_sign_in_at': '2026-09-01T09:00:00Z',
                 'app_metadata': {'must_change_password': True,
                                  'temp_password_issued_at': '2026-10-01T09:00:00+00:00'}}
        r, put = self._invite_onto(login)
        self.assertEqual(r.status_code, 201, r.content[:300])
        self.assertFalse(r.json()['already_registered'])
        self.assertTrue(put.called)

    def test_N2_a_login_another_staff_row_owns_is_never_adopted(self):
        other = make_admin('reviewer', owning_org=self.org)
        login = {'id': other.supabase_user_id, 'email': 'second@example.org',
                 'identities': [{'provider': 'email'}], 'last_sign_in_at': None,
                 'app_metadata': {'must_change_password': True}}
        r, put = self._invite_onto(login)
        self.assertEqual(r.status_code, 201, r.content[:300])
        self.assertTrue(r.json()['already_registered'])
        put.assert_not_called()
        self.assertIsNone(PartnerAdmin.objects.get(email='second@example.org').supabase_user_id)

    def test_N1_the_reinvite_after_cancel_never_overwrites_a_password_chosen_elsewhere(self):
        account = make_admin('reviewer', owning_org=self.org, is_active=False)
        user = _auth_user(account.supabase_user_id, account.email, signed_in=True, owes=True)
        user['app_metadata']['temp_password_expired'] = True
        with patch(f'{REQ}.get', return_value=_resp(body=user)), patch(f'{REQ}.put') as put:
            r = authed_client(self.org_admin).post('/api/v1/admin/invite/', {
                'email': account.email, 'name': 'X', 'role': 'qc'}, format='json')
        self.assertEqual(r.status_code, 409)
        put.assert_not_called()

    def test_a_login_whose_address_no_longer_matches_is_kept(self):
        target = make_admin('admin', owning_org=self.org)
        user = _auth_user(target.supabase_user_id, 'someone.else@example.org')
        with patch(f'{REQ}.get', return_value=_resp(body=user)), \
                patch(f'{REQ}.delete') as gone, patch(f'{REQ}.put') as put:
            self.assertEqual(self._delete(target).status_code, 200)
        gone.assert_not_called()
        put.assert_not_called()

    def test_still_refused_for_work_and_for_reviewers(self):
        worked = make_admin('admin', owning_org=self.org)
        PaymentRun.objects.create(organisation=self.org, created_by=worked.email,
                                  payment_date=datetime.date(2026, 9, 1))
        rev = make_admin('reviewer', owning_org=self.org)
        with patch(f'{REQ}.get') as get, patch(f'{REQ}.delete') as gone:
            self.assertEqual(self._delete(worked).json()['code'], 'has_work')
            self.assertEqual(self._delete(rev).json()['code'], 'not_deletable')
        get.assert_not_called()
        gone.assert_not_called()
