"""Sprint M4a (ACCESS-BY-SWITCHES S2, owner Q2, 19 Nov): the payment run's maker-checker rules, by switches.

The manifest's `_about` (`access_manifest.json`) left these to M4. The rules (brief, "The run's rules"):
1. Maker: a Prepare holder signs a draft.  2. Nobody signs twice.
3. Check: a signed-in Check holder who neither signed nor built the run; the step exists only if one exists.
4. Approve: a signed-in Approve holder who neither signed nor built the run.
5. Fallback, only when rule 4 finds nobody: a holder of Organisation admin powers, or an Approve holder, who
   has not signed. The builder is allowed (Q2).
6. A super acts anywhere, once per run.  7. Two different people always sign.

Plus the debt this sprint closes on the chain: TD-605 (the actor's row is locked, and re-read, before the
run), TD-560 (a holder who never signed in arms no check) and TD-614 (a suspended person's Remove names no
payment consequence).
"""
import datetime
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses import staff_permissions as sp
from apps.courses.models import PartnerAdmin
from apps.scholarship import payments, payments_chain
from apps.scholarship.models import PaymentRun
from apps.scholarship.staff_tables_admin import plan_table_change
from apps.scholarship.tests.factories import TEST_JWT_SECRET, authed_client, make_admin, make_org

API = dict(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
SEEN = timezone.make_aware(datetime.datetime(2026, 9, 1))
PREPARE = ['see_all', 'payments_prepare']
APPROVE = ['see_all', 'payments_approve']
BOTH = ['see_all', 'payments_prepare', 'payments_approve']


def _sign_url(run):
    return f'/api/v1/admin/scholarship/payment-runs/{run.pk}/sign/'


class _Chain(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.lead = make_admin('org_admin', owning_org=cls.org, first_seen_at=SEEN)
        cls.maker = make_admin('admin', owning_org=cls.org, first_seen_at=SEEN, permissions=BOTH)
        cls.builder = make_admin('admin', owning_org=cls.org, first_seen_at=SEEN, permissions=BOTH)

    def run_for(self, *, status='admin_signed', creator=None, maker=None, checker=None):
        maker = maker or self.maker
        kw = {}
        if status != 'draft':
            kw.update(admin_signed_email=maker.email, admin_signed_name=maker.name,
                      admin_signed_at=timezone.now())
        if checker is not None:
            kw.update(finance_signed_email=checker.email, finance_signed_name=checker.name,
                      finance_signed_at=timezone.now())
        self._n = getattr(self, '_n', 0) + 1           # the reference is unique
        return PaymentRun.objects.create(
            organisation=self.org, payment_date=datetime.date(2026, 12, 1), status=status,
            reference=f'PR-M4A-{self.org.pk}-{self._n:03d}',
            created_by=(creator or maker).email.upper(), **kw)

    def refused(self, run, admin):
        with self.assertRaises(payments.PaymentsError) as caught:
            payments.sign(run, admin, admin.name)
        return caught.exception.code


@override_settings(**API)
class TheMakerNeverChecksOrApproves(_Chain):
    def test_at_the_service(self):
        checker = make_admin('admin', owning_org=self.org, first_seen_at=SEEN,
                             permissions=['see_all', 'payments_check', 'payments_approve'])
        run = self.run_for()
        self.assertIsNone(payments.next_step_for(run, self.maker))
        self.assertEqual(self.refused(run, self.maker), 'same_signer')
        self.assertEqual(payments.next_step_for(run, checker), 'check')
        # With nobody else eligible the fallback is on — and still never the maker's (rule 2).
        PartnerAdmin.objects.filter(pk__in=[checker.pk, self.builder.pk]).update(is_active=False)
        self.assertTrue(payments.approver_fallback(run))
        self.assertEqual(self.refused(run, self.maker), 'same_signer')

    def test_at_the_sign_view(self):
        run = self.run_for()
        r = authed_client(self.maker).post(_sign_url(run), {'typed_name': self.maker.name}, format='json')
        self.assertEqual(r.json().get('code'), 'same_signer', r.content[:300])
        self.assertGreaterEqual(r.status_code, 400)
        run.refresh_from_db()
        self.assertEqual(run.status, 'admin_signed')


class TheBuilder(_Chain):
    def test_cannot_approve_while_another_eligible_approver_exists_and_can_under_the_fallback(self):
        run = self.run_for(creator=self.builder)
        other = make_admin('admin', owning_org=self.org, first_seen_at=SEEN, permissions=APPROVE)
        self.assertEqual(payments.eligible_approvers(run), [other])
        self.assertIsNone(payments.next_step_for(run, self.builder))
        self.assertEqual(self.refused(run, self.builder), 'same_signer')
        other.is_active = False
        other.save(update_fields=['is_active'])
        self.assertTrue(payments.approver_fallback(run))
        self.assertEqual(payments.next_step_for(run, self.builder), 'approve')        # Q2
        self.assertIn(self.builder, payments.fallback_approvers(run))
        signed = payments.sign(run, self.builder, self.builder.name)
        self.assertEqual(signed.status, 'completed')
        self.assertEqual(signed.org_admin_signed_email, self.builder.email)

    def test_who_checked_never_approves(self):
        both = make_admin('admin', owning_org=self.org, first_seen_at=SEEN,
                          permissions=['see_all', 'payments_check', 'payments_approve'])
        run = self.run_for(status='finance_checked', checker=both)
        self.assertIsNone(payments.next_step_for(run, both))
        self.assertEqual(self.refused(run, both), 'same_signer')


class TheFallback(_Chain):
    def test_on_when_the_only_approve_holder_signed_off_when_another_appears_never_the_makers(self):
        run = self.run_for()                       # the maker holds Approve and is the only holder
        self.assertEqual(payments.eligible_approvers(run), [self.builder])
        self.builder.is_active = False
        self.builder.save(update_fields=['is_active'])
        self.assertEqual(payments.eligible_approvers(run), [])
        self.assertTrue(payments.approver_fallback(run))
        self.assertNotIn(self.maker, payments.fallback_approvers(run))
        self.assertIn(self.lead, payments.fallback_approvers(run))
        never = make_admin('admin', owning_org=self.org, permissions=APPROVE)          # never signed in
        self.assertTrue(payments.approver_fallback(run))
        self.assertNotIn(never, payments.fallback_approvers(run))
        later = make_admin('admin', owning_org=self.org, first_seen_at=SEEN, permissions=APPROVE)
        self.assertFalse(payments.approver_fallback(run))
        self.assertIsNone(payments.next_step_for(run, self.lead))
        self.assertEqual(payments.next_step_for(run, later), 'approve')


class TheOrganisationAdmin(_Chain):
    def test_builds_but_never_signs_as_maker_and_approves_only_under_the_fallback(self):
        self.assertTrue(payments.may_read(self.lead))
        self.assertTrue(payments.may_prepare(self.lead))
        draft = self.run_for(status='draft', creator=self.lead)
        self.assertIsNone(payments.next_step_for(draft, self.lead))
        self.assertEqual(self.refused(draft, self.lead), 'wrong_role')
        run = self.run_for()
        self.assertEqual(payments.eligible_approvers(run), [self.builder])
        self.assertIsNone(payments.next_step_for(run, self.lead))
        self.assertEqual(self.refused(run, self.lead), 'wrong_role')
        self.builder.is_active = False
        self.builder.save(update_fields=['is_active'])
        self.assertEqual(payments.next_step_for(run, self.lead), 'approve')

    def test_with_the_key_unticked_reads_builds_and_approves_nothing(self):
        PartnerAdmin.objects.filter(pk=self.lead.pk).update(
            permissions=[k for k in self.lead.permissions if k != sp.ORG_ADMIN_KEY])
        self.lead.refresh_from_db()
        self.builder.is_active = False
        self.builder.save(update_fields=['is_active'])
        run = self.run_for()
        self.assertTrue(payments.approver_fallback(run))
        self.assertFalse(payments.may_read(self.lead))
        self.assertFalse(payments.may_prepare(self.lead))
        self.assertIsNone(payments.next_step_for(run, self.lead))
        self.assertNotIn(self.lead, payments.fallback_approvers(run))
        self.assertEqual(self.refused(run, self.lead), 'wrong_role')


class ARoleAloneOpensNothing(_Chain):
    def test_a_finance_row_without_approve_in_its_stored_list_cannot_approve(self):
        fin = make_admin('finance', owning_org=self.org, first_seen_at=SEEN, permissions=['see_all'])
        self.builder.is_active = False
        self.builder.save(update_fields=['is_active'])
        run = self.run_for()
        self.assertNotIn(fin, payments.eligible_approvers(run))
        self.assertNotIn(fin, payments.fallback_approvers(run))
        self.assertIsNone(payments.next_step_for(run, fin))
        self.assertFalse(payments.may_read(fin))

    def test_a_view_only_member_opens_payments_and_cannot_build_or_sign(self):
        viewer = make_admin('admin', owning_org=self.org, first_seen_at=SEEN,
                            permissions=['see_all', 'payments.view'])
        self.assertTrue(payments.may_read(viewer))
        self.assertFalse(payments.may_prepare(viewer))
        for run in (self.run_for(status='draft'), self.run_for()):
            with self.subTest(status=run.status):
                self.assertIsNone(payments.next_step_for(run, viewer))
                self.assertEqual(self.refused(run, viewer), 'wrong_role')


class ASuperActsOnce(_Chain):
    def test_once_per_run(self):
        boss = make_admin('super', super_admin=True)
        run = self.run_for(status='draft', creator=boss)
        self.assertEqual(payments.next_step_for(run, boss), 'sign')
        payments.sign(run, boss, boss.name)
        self.assertIsNone(payments.next_step_for(run, boss))
        self.assertEqual(self.refused(run, boss), 'same_signer')


class TD605TheActorsRowFirst(_Chain):
    def test_sign_locks_the_actor_before_the_run(self):
        order = []
        real_actor, real_run = payments_chain.lock_actor, payments_chain._lock
        with patch.object(payments_chain, 'lock_actor', side_effect=lambda a: order.append('actor') or real_actor(a)), \
                patch.object(payments_chain, '_lock', side_effect=lambda r: order.append('run') or real_run(r)):
            payments.sign(self.run_for(status='draft'), self.maker, self.maker.name)
        self.assertEqual(order[:2], ['actor', 'run'])

    def test_a_key_taken_while_in_flight_is_seen(self):
        run = self.run_for(status='draft')
        stale = PartnerAdmin.objects.get(pk=self.maker.pk)                # loaded with Prepare
        PartnerAdmin.objects.filter(pk=self.maker.pk).update(permissions=['see_all'])
        self.assertEqual(self.refused(run, stale), 'wrong_role')
        gone = PartnerAdmin.objects.get(pk=self.builder.pk)
        PartnerAdmin.objects.filter(pk=self.builder.pk).update(is_active=False)
        self.assertEqual(self.refused(run, gone), 'wrong_role')
        run.refresh_from_db()
        self.assertEqual(run.status, 'draft')

    def test_create_reads_the_actor_under_its_lock(self):
        stale = PartnerAdmin.objects.get(pk=self.maker.pk)
        PartnerAdmin.objects.filter(pk=self.maker.pk).update(permissions=['see_all'])
        with self.assertRaises(payments.PaymentsError) as caught:
            payments.create_run(self.org, datetime.date(2026, 12, 1), datetime.date(2026, 12, 1),
                                _programme(self.org), actor=stale)
        self.assertEqual(caught.exception.code, 'wrong_role')
        self.assertEqual(stale.permissions, ['see_all'])        # `lock_actor` re-read the row onto the actor


def _programme(org):
    from apps.scholarship.tests.factories import make_programme
    return make_programme(organisation=org)


class TD560OnlyASignedInHolderArmsTheChecks(_Chain):
    def test_the_run_check_and_the_credit_check(self):
        org = make_org()
        never = make_admin('admin', owning_org=org, permissions=['see_all', 'payments_check', 'payments_approve'])
        self.assertFalse(payments.finance_check_required(org))
        self.assertFalse(payments.credit_check_required(org))
        never.first_seen_at = SEEN
        never.save(update_fields=['first_seen_at'])
        self.assertTrue(payments.finance_check_required(org))
        self.assertTrue(payments.credit_check_required(org))


class TD614ASuspendedPersonsRemoveNamesNoMoneyConsequence(_Chain):
    def test_suspended(self):
        holder = make_admin('admin', owning_org=self.org, first_seen_at=SEEN,
                            permissions=['review', 'see_all', 'payments_approve'])
        live = plan_table_change(holder, 'admins', 'remove')
        holder.is_active = False
        holder.save(update_fields=['is_active'])
        suspended = plan_table_change(holder, 'admins', 'remove')
        self.assertEqual(suspended['consequences'], [])
        self.assertFalse(suspended['finance_check_off'])
        self.assertIsInstance(live['consequences'], list)
