"""Sprint S3 / M4b (owner rulings Q-A to Q-D, 23 Nov 2026): sponsor credits and the Vircle ID on switches.

Pinned here, each against the production shapes the factory makes (after 0097-0100, and before 0100):

  * the SEAT TABLE: who records, checks, approves and cancels a credit, who corrects a Vircle ID, and who
    gets the Overview's credit card (TD-503) — every seat a switch, never a role label;
  * Q-A: an organisation admin never records or first-signs, whatever its stored list says;
  * Q-C: Payments Approve approves, and nobody approves a credit they recorded or checked (`same_signer`);
  * TD-561: a signature or a void re-reads the actor's row and the credit's row under a lock, and the
    "money received" email leaves only after the commit;
  * Q-D (TD-498 remainder): sponsor terms and sponsor emails READ on Sponsors: view, WRITE on Sponsors: edit;
  * the sponsor page's served flags (`can_record_credit`, per credit `can_sign` / `blocked` / `can_void`).
"""
from decimal import Decimal
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import PartnerAdmin
from apps.scholarship import credit_steps, surface_gates
from apps.scholarship import sponsorship as svc
from apps.scholarship.models import Donation, Sponsor, SponsorProgrammeMembership
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_org, make_programme,
)

ADMIN = '/api/v1/admin/scholarship/'
HTTP = override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)


def _exact(admin, keys, signed_in=True):
    """Store EXACTLY these keys on the row (the factory merges a preset), signed in unless told not."""
    PartnerAdmin.objects.filter(pk=admin.pk).update(
        permissions=keys, first_seen_at=timezone.now() if signed_in else None)
    admin.refresh_from_db()
    return admin


def _seats(admin):
    return {'record': credit_steps.may_record(admin), 'check': credit_steps.holds_checker_seat(admin),
            'approve': credit_steps.may_approve(admin), 'cancel': credit_steps.may_cancel(admin),
            'vircle': surface_gates.may_correct_vircle_id(admin), 'card': credit_steps.checks_credits(admin)}


def _row(make, check, approve, cancel, vircle, card):
    return {'record': make, 'check': check, 'approve': approve, 'cancel': cancel, 'vircle': vircle, 'card': card}


class TestTheSeatTable(TestCase):
    """The seat table the brief records, row by row, on the factory's production shapes."""

    @classmethod
    def setUpTestData(cls):
        org = make_org()
        cls.cast = {
            'admin (production shape)': make_admin('admin', owning_org=org),
            'admin with Payments Approve added': make_admin('admin', owning_org=org,
                                                            permissions=['payments_approve']),
            'payments switches only': _exact(make_admin('finance', owning_org=org), ['payments_approve']),
            'finance (production shape)': make_admin('finance', owning_org=org),
            'organisation admin (after 0100)': make_admin('org_admin', owning_org=org),
            'organisation admin (before 0100)': make_admin('org_admin', owning_org=org, pre_m4a=True),
            'reviewer': make_admin('reviewer', owning_org=org),
            'super': make_admin(super_admin=True),
        }

    def test_every_seat_is_a_switch(self):
        expected = {
            'admin (production shape)': _row(True, False, False, True, False, True),
            'admin with Payments Approve added': _row(True, True, True, True, True, True),
            'payments switches only': _row(False, True, True, False, True, True),
            'finance (production shape)': _row(False, True, True, False, True, True),
            'organisation admin (after 0100)': _row(False, False, True, True, True, True),
            # Before 0100 the stored list lacks `organisation.admin`: no approve, no Vircle. S3 lands
            # with or after S2's 0100 (its migrate-first step), never before.
            'organisation admin (before 0100)': _row(False, False, False, True, False, False),
            'reviewer': _row(False, False, False, False, False, False),
            'super': _row(True, False, True, True, True, False),
        }
        got = {name: _seats(a) for name, a in self.cast.items()}
        self.assertEqual(got, expected)


class _Credits(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.gift = make_programme(organisation=cls.org)
        cls.sponsor = Sponsor.objects.create(supabase_user_id='m4b-sponsor', name='A Benefactor',
                                             email='benefactor@example.test', status='approved')
        SponsorProgrammeMembership.objects.create(sponsor=cls.sponsor, programme=cls.gift, status='approved')
        cls.maker = make_admin('admin', owning_org=cls.org)
        cls.lead = make_admin('org_admin', owning_org=cls.org)
        # Payments Approve, NOT signed in: it approves, and arms no check (TD-560).
        cls.payer = _exact(make_admin('finance', owning_org=cls.org), ['payments_approve'], signed_in=False)

    def _record(self, admin=None):
        return svc.record_admin_credit(sponsor=self.sponsor, programme=self.gift, amount=Decimal('500'),
                                       external_reference='TRF-M4B-1', admin=admin or self.maker)

    def _sign(self, credit, admin):
        return svc.sign_admin_credit(credit, admin, admin.name)

    def _refusal(self, fn, *args):
        with self.assertRaises(svc.CreditError) as ctx:
            fn(*args)
        return ctx.exception.code


class TestQAMaker(_Credits):
    def test_an_organisation_admin_never_records_even_with_sponsors_edit_stored(self):
        lead = make_admin('org_admin', owning_org=self.org)
        self.assertIn('sponsors.edit', lead.permissions)
        self.assertEqual(self._refusal(self._record, lead), 'wrong_role')
        credit = self._record()
        self.assertEqual(self._refusal(self._sign, credit, lead), 'wrong_role')

    def test_an_admin_without_sponsors_edit_stored_neither_records_nor_signs_first(self):
        plain = _exact(make_admin('admin', owning_org=self.org), ['see_all', 'scholars', 'sponsors.view'])
        self.assertEqual(self._refusal(self._record, plain), 'wrong_role')
        credit = self._record()
        self.assertEqual(self._refusal(self._sign, credit, plain), 'wrong_role')

    def test_payments_approve_alone_never_records_or_cancels(self):
        self.assertEqual(self._refusal(self._record, self.payer), 'wrong_role')
        credit = self._record()
        self.assertEqual(self._refusal(svc.cancel_admin_credit, credit, self.payer), 'wrong_role')


class TestQCApprover(_Credits):
    def test_never_signed_in_edge_payments_approve_countersigns_and_the_money_email_waits_for_the_commit(self):
        # THE NEVER-SIGNED-IN EDGE (review SF5): `payer` has never signed in, so it arms no check (TD-560)
        # and the credit goes straight to approval. The reachable path, two signed-in holders, is
        # `TestTwoSignedInHolders` below.
        credit = self._record()
        self._sign(credit, self.maker)
        with mock.patch('apps.scholarship.sponsor_notify.send_credit_confirmed') as sent:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                self._sign(credit, self.payer)
            sent.assert_not_called()               # TD-561: never while the row lock is held
            for cb in callbacks:
                cb()
            sent.assert_called_once()
        credit.refresh_from_db()
        self.assertEqual(credit.status, Donation.STATUS_CONFIRMED)

    def test_nobody_approves_a_credit_they_checked(self):
        checker = _exact(make_admin('finance', owning_org=self.org), ['payments_approve'])   # signed in: arms
        credit = self._record()
        self._sign(credit, self.maker)
        self.assertEqual(self._refusal(self._sign, credit, self.lead), 'finance_check_required')
        self.assertEqual(self._sign(credit, checker).status, Donation.STATUS_FINANCE_CHECKED)
        self.assertEqual(self._refusal(self._sign, credit, checker), 'same_signer')
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self._sign(credit, self.lead).status, Donation.STATUS_CONFIRMED)

    def test_nobody_approves_a_credit_they_recorded(self):
        both = make_admin('admin', owning_org=self.org, permissions=['payments_approve'])
        credit = self._record(both)
        self._sign(credit, both)
        self.assertEqual(self._refusal(self._sign, credit, both), 'same_signer')


class TestTD561Lock(_Credits):
    def test_a_stale_copy_is_re_read_so_one_step_is_never_taken_twice(self):
        credit = self._record()
        stale = Donation.objects.get(pk=credit.pk)              # read while still a draft
        self._sign(credit, self.maker)
        # Without the lock the stale DRAFT would let the maker sign the first step again.
        self.assertEqual(self._refusal(self._sign, stale, self.maker), 'wrong_role')
        self.assertEqual(stale.status, Donation.STATUS_ADMIN_SIGNED)

    def test_a_void_on_a_stale_copy_never_cancels_confirmed_money(self):
        credit = self._record()
        stale = Donation.objects.get(pk=credit.pk)
        self._sign(credit, self.maker)
        with self.captureOnCommitCallbacks(execute=True):
            self._sign(credit, self.payer)
        self.assertEqual(self._refusal(svc.cancel_admin_credit, stale, self.maker), 'bad_state')
        credit.refresh_from_db()
        self.assertEqual(credit.status, Donation.STATUS_CONFIRMED)

    def test_a_switch_taken_away_mid_request_is_seen(self):
        credit = self._record()
        PartnerAdmin.objects.filter(pk=self.maker.pk).update(permissions=['see_all'])
        self.assertEqual(self._refusal(self._sign, credit, self.maker), 'wrong_role')   # in-memory copy stale


@HTTP
class TestServedFlags(_Credits):
    def _detail(self, who):
        r = authed_client(who).get(f'/api/v1/admin/sponsors/{self.sponsor.pk}/')
        self.assertEqual(r.status_code, 200, r.content[:200])
        return r.json()

    def test_the_page_draws_only_what_the_server_serves(self):
        self._record()

        def flags(detail):
            return {k: detail['credits'][0][k] for k in ('can_sign', 'blocked', 'can_void')}
        maker, lead, payer = self._detail(self.maker), self._detail(self.lead), self._detail(self.payer)
        self.assertEqual((maker['can_record_credit'], flags(maker)),
                         (True, {'can_sign': True, 'blocked': None, 'can_void': True}))
        self.assertEqual((lead['can_record_credit'], flags(lead)),
                         (False, {'can_sign': False, 'blocked': None, 'can_void': True}))
        self.assertEqual((payer['can_record_credit'], flags(payer)),
                         (False, {'can_sign': False, 'blocked': None, 'can_void': False}))

    def test_the_approver_is_told_the_check_comes_first(self):
        _exact(make_admin('finance', owning_org=self.org), ['payments_approve'])               # arms
        self._sign(self._record(), self.maker)
        credit = self._detail(self.lead)['credits'][0]
        self.assertEqual((credit['can_sign'], credit['blocked']), (False, 'awaiting_finance'))

    def test_the_maker_is_not_offered_a_second_signature(self):
        self._sign(self._record(), self.maker)
        self.assertFalse(self._detail(self.maker)['credits'][0]['can_sign'])
        self.assertTrue(self._detail(self.payer)['credits'][0]['can_sign'])


@HTTP
class TestTD503Card(_Credits):
    def _card(self, who):
        cards = {c['key']: c for c in authed_client(who).get(f'{ADMIN}my-pending/').json()['cards']}
        return {'count': cards['wallet_credits']['count']} if 'wallet_credits' in cards else None

    def test_each_seat_counts_the_credits_waiting_for_it(self):
        credit = self._record()
        self.assertEqual(self._card(self.maker), {'count': 1})
        self.assertEqual(self._card(self.payer), {'count': 0})
        self._sign(credit, self.maker)
        self.assertEqual(self._card(self.maker), {'count': 0})
        self.assertEqual(self._card(self.payer), {'count': 1})
        self.assertEqual(self._card(self.lead), {'count': 1})
        self.assertIsNone(self._card(make_admin('reviewer', owning_org=self.org)))


@HTTP
class TestQDSponsorReads(TestCase):
    """TD-498 remainder: reading the terms and the sponsor emails asks Sponsors: view; writing, Sponsors: edit."""

    @classmethod
    def setUpTestData(cls):
        org = make_org()
        cls.viewer = _exact(make_admin('admin', owning_org=org), ['sponsors.view'])
        cls.reviewer = make_admin('reviewer', owning_org=org)

    def test_sponsors_view_reads_and_never_writes(self):
        c = authed_client(self.viewer)
        self.assertEqual(c.get(f'{ADMIN}sponsor-terms/').status_code, 200)
        self.assertEqual(c.get(f'{ADMIN}sponsor-emails/').status_code, 200)
        self.assertEqual(c.post(f'{ADMIN}sponsor-terms/', {}, format='json').status_code, 403)
        self.assertEqual(c.patch(f'{ADMIN}sponsor-emails/welcome/', {}, format='json').status_code, 403)

    def test_without_sponsors_view_nothing_opens(self):
        c = authed_client(self.reviewer)
        self.assertEqual(c.get(f'{ADMIN}sponsor-terms/').status_code, 403)
        self.assertEqual(c.get(f'{ADMIN}sponsor-emails/').status_code, 403)


@HTTP
class TestVircleIdBySwitch(TestCase):
    """TD-664 d: correcting a scholar's Vircle ID asks Payments Approve (or Organisation admin powers), never
    the role, and only once the case's own write fence (`_require_app_write`) has let the caller in."""

    @classmethod
    def setUpTestData(cls):
        from apps.scholarship.tests.factories import make_application, make_cohort
        cohort = make_cohort()
        org = cohort.owning_organisation
        cls.app = make_application('maintenance', cohort=cohort)
        cls.payer = make_admin('admin', owning_org=org, permissions=['see_all', 'scholars', 'payments_approve'])
        cls.plain = make_admin('admin', owning_org=org, permissions=['see_all', 'scholars'])
        cls.lead = make_admin('org_admin', owning_org=org)
        cls.fenced = _exact(make_admin('finance', owning_org=org), ['payments_approve'])

    def _patch(self, who):
        return authed_client(who).patch(f'{ADMIN}applications/{self.app.pk}/', {'vircle_id': ''}, format='json')

    def test_payments_approve_or_the_powers_correct_it_and_the_label_does_not(self):
        self.assertEqual(self._patch(self.payer).status_code, 200)
        self.assertEqual(self._patch(self.lead).status_code, 200)
        self.assertEqual(self._patch(self.plain).status_code, 403)

    def test_the_case_fence_still_comes_first(self):
        self.assertTrue(surface_gates.may_correct_vircle_id(self.fenced))
        self.assertEqual(self._patch(self.fenced).status_code, 403)


class TestTwoSignedInHolders(_Credits):
    """Review SF1 and SF5: the path production reaches — two SIGNED-IN Payments: Approve holders, so the check
    is armed. One checks, the other approves; neither takes two steps, and a stale page never confirms."""

    def setUp(self):
        self.x = _exact(make_admin('finance', owning_org=self.org), ['payments_approve'])
        self.y = _exact(make_admin('finance', owning_org=self.org), ['payments_approve'])
        self.credit = self._record()
        self._sign(self.credit, self.maker)

    def test_one_checks_the_other_approves_and_the_checker_never_approves(self):
        self.assertEqual(self._sign(self.credit, self.x).status, Donation.STATUS_FINANCE_CHECKED)
        self.assertEqual(self._refusal(self._sign, self.credit, self.x), 'same_signer')
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self._sign(self.credit, self.y).status, Donation.STATUS_CONFIRMED)

    def test_a_stale_check_never_confirms(self):
        y_page = Donation.objects.get(pk=self.credit.pk)          # Y's page drew "Check" (admin_signed)
        svc.sign_admin_credit(self.credit, self.x, self.x.name, expected_status=Donation.STATUS_ADMIN_SIGNED)
        code = self._refusal(svc.sign_admin_credit, y_page, self.y, self.y.name, Donation.STATUS_ADMIN_SIGNED)
        self.assertEqual(code, 'stale')
        self.credit.refresh_from_db()
        self.assertEqual((self.credit.status, self.credit.confirmed_by_email),
                         (Donation.STATUS_FINANCE_CHECKED, ''))

    @HTTP
    def test_the_sign_endpoint_answers_409_stale(self):
        def post(who):
            return authed_client(who).post(f'{ADMIN}credits/{self.credit.pk}/sign/', {
                'typed_name': who.name, 'expected_status': Donation.STATUS_ADMIN_SIGNED}, format='json')
        self.assertEqual(post(self.x).status_code, 200)
        r = post(self.y)
        self.assertEqual((r.status_code, r.json()['code']), (409, 'stale'))
        self.credit.refresh_from_db()
        self.assertEqual(self.credit.status, Donation.STATUS_FINANCE_CHECKED)


class TestBefore0100(_Credits):
    """Review SF2: the pre-0100 behaviour, pinned as KNOWN. An organisation admin whose stored list lacks
    `organisation.admin` approves no credit and corrects no Vircle ID. S3 serves only after courses/0100 has
    run and its post-checks read 0 (release note and brief); nothing at boot reads the database for it."""

    def test_an_organisation_admin_before_0100_cannot_approve(self):
        lead = make_admin('org_admin', owning_org=self.org, pre_m4a=True)
        self.assertNotIn('organisation.admin', lead.permissions or [])
        credit = self._record()
        self._sign(credit, self.maker)
        self.assertEqual(self._refusal(self._sign, credit, lead), 'wrong_role')

    @HTTP
    def test_an_organisation_admin_before_0100_cannot_correct_a_vircle_id(self):
        from apps.scholarship.tests.factories import make_application, make_cohort
        cohort = make_cohort()
        app = make_application('maintenance', cohort=cohort)
        lead = make_admin('org_admin', owning_org=cohort.owning_organisation, pre_m4a=True)
        self.assertFalse(surface_gates.may_correct_vircle_id(lead))
        r = authed_client(lead).patch(f'{ADMIN}applications/{app.pk}/', {'vircle_id': ''}, format='json')
        self.assertEqual(r.status_code, 403)


class TestAPersonInReviewersAndAdmins(_Credits):
    """Owner 24 Nov: labels come from groups, and powers follow the groups a person sits in. Sponsors: edit
    is an Admins switch, so whoever holds it sits in Admins (production: one person also in Reviewers, by
    O8) and records, first-signs and cancels. To undo it, untick Sponsors: edit on their Admins tab."""

    def test_the_stored_key_decides_not_the_label(self):
        keyed = _exact(make_admin('reviewer', owning_org=self.org), ['sponsors.view', 'sponsors.edit'])
        plain = make_admin('reviewer', owning_org=self.org)
        self.assertEqual((_seats(keyed)['record'], _seats(keyed)['cancel']), (True, True))
        self.assertEqual((_seats(plain)['record'], _seats(plain)['cancel']), (False, False))

    def test_holding_an_admins_switch_seats_the_person_in_admins(self):
        from apps.courses import staff_tables
        keyed = _exact(make_admin('reviewer', owning_org=self.org), ['review', 'sponsors.view', 'sponsors.edit'])
        plain = make_admin('reviewer', owning_org=self.org)
        self.assertEqual((staff_tables.in_admins(keyed), staff_tables.in_reviewers(keyed)), (True, True))
        self.assertEqual((staff_tables.in_admins(plain), staff_tables.in_reviewers(plain)), (False, True))


class TestInactiveRowsHoldNoSeat(_Credits):
    """Review nit: `may_approve` and `checks_credits` refuse an inactive row on their own."""

    def test_an_inactive_approver_neither_approves_nor_gets_the_card(self):
        gone = make_admin('admin', owning_org=self.org, permissions=['payments_approve'])
        self.assertTrue(credit_steps.may_approve(gone))
        gone.is_active = False
        self.assertEqual((credit_steps.may_approve(gone), credit_steps.checks_credits(gone)), (False, False))


@HTTP
class TestReadersSeeNoStaffEmail(TestCase):
    """Review SF4: a Sponsors: view reader is shown no staff email on the terms or the sponsor emails;
    an editor still sees who wrote what."""

    @classmethod
    def setUpTestData(cls):
        from apps.scholarship.models import SponsorEmailTemplate, SponsorTermsVersion
        org = make_org()
        cls.viewer = _exact(make_admin('admin', owning_org=org), ['sponsors.view'])
        cls.editor = make_admin('admin', owning_org=org)
        cls.terms = SponsorTermsVersion.objects.create(
            version='m4b-1', title_en='Terms', created_by_email='author@example.test',
            published_by_email='publisher@example.test')
        SponsorEmailTemplate.objects.create(kind='welcome', subject='Hello', body='Welcome',
                                            updated_by_email='editor@example.test')

    def _emails(self, who):
        c = authed_client(who)
        terms = c.get(f'{ADMIN}sponsor-terms/').json()['versions'][0]
        one = c.get(f'{ADMIN}sponsor-terms/{self.terms.pk}/').json()
        tpl = c.get(f'{ADMIN}sponsor-emails/').json()['templates'][0]
        return {terms['created_by_email'], terms['published_by_email'], one['created_by_email'],
                one['published_by_email'], tpl['updated_by_email']}

    def test_a_reader_never_sees_a_staff_email(self):
        self.assertEqual(self._emails(self.viewer), {''})

    def test_an_editor_still_does(self):
        self.assertEqual(self._emails(self.editor),
                         {'author@example.test', 'publisher@example.test', 'editor@example.test'})


class TestAdversarialRound(_Credits):
    """The adversarial review (24 Nov): a move to another organisation mid-request is seen under the lock; a
    failed confirmation email never turns a confirmed credit into a 500; another organisation's approver
    cannot even find the credit."""

    def test_a_signer_moved_to_another_organisation_mid_request_is_refused(self):
        credit = self._record()
        stale_copy = PartnerAdmin.objects.get(pk=self.maker.pk)        # loaded while still in this org
        PartnerAdmin.objects.filter(pk=self.maker.pk).update(owning_organisation=make_org())
        self.assertEqual(self._refusal(self._sign, credit, stale_copy), 'wrong_role')
        credit.refresh_from_db()
        self.assertEqual(credit.status, Donation.STATUS_DRAFT)

    def test_a_failed_confirmation_email_leaves_the_credit_confirmed_and_raises_nothing(self):
        credit = self._record()
        self._sign(credit, self.maker)
        with mock.patch('apps.scholarship.sponsor_notify.send_credit_confirmed', side_effect=RuntimeError):
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                self._sign(credit, self.payer)
        self.assertEqual(len(callbacks), 1)
        credit.refresh_from_db()
        self.assertEqual(credit.status, Donation.STATUS_CONFIRMED)

    @HTTP
    def test_another_organisations_approver_cannot_find_the_credit(self):
        credit = self._record()
        self._sign(credit, self.maker)
        outsider = _exact(make_admin('finance', owning_org=make_org()), ['payments_approve'])
        r = authed_client(outsider).post(f'{ADMIN}credits/{credit.pk}/sign/', {
            'typed_name': outsider.name, 'expected_status': Donation.STATUS_ADMIN_SIGNED}, format='json')
        self.assertEqual(r.status_code, 404)
        credit.refresh_from_db()
        self.assertEqual(credit.status, Donation.STATUS_ADMIN_SIGNED)
