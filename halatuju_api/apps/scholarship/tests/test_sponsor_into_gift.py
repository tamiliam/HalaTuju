"""S-ASSIGN — a benefactor is invited by the ORGANISATION and accepted into a GIFT (2026-09-04).

This is the sprint that unblocks the RM100,000. Until now `sync_account_membership` hard-coded
``DEFAULT_PROGRAMME_CODE = 'brightpath-flagship'``, so a sponsor could only ever join the flagship
and ``record_admin_credit`` then refused ``sponsor_not_in_programme`` for any other gift. A second
gift's first benefactor could not be recorded without an engineer writing SQL — which is precisely
what the owner's acceptance test forbids.

The two rules everything here is arranged around:

  1. **NOTHING IS GUESSED.** One active gift resolves itself; several with nothing stated is a
     REFUSAL, not a pick. Filing a benefactor — and their money — against the wrong gift is worse
     than asking (PF-1's rule, applied to the money).
  2. **THE ACCOUNT GATE AND THE GIFT GATE ARE SEPARATE.** `Sponsor.status` is settled once,
     platform-wide; acceptance into a gift is the organisation's own decision, and approving
     somebody into one gift says nothing about any other.
"""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.scholarship import sponsorship as svc
from apps.scholarship.models import (
    Invitation, Programme, Sponsor, SponsorProgrammeMembership,
)
from apps.scholarship.tests.test_api import TEST_JWT_SECRET, _make_token


def _org(code):
    return PartnerOrganisation.objects.create(code=code, name=code.title(), is_active=True)


def _admin(uid, org=None, role='org_admin', super_=False):
    return PartnerAdmin.objects.create(
        supabase_user_id=uid, email=f'{uid}@example.com', name=uid,
        role=role, is_super_admin=super_, is_active=True, owning_organisation=org)


def _sponsor(email='giver@example.com', status='approved'):
    return Sponsor.objects.create(
        supabase_user_id=f'sp-{email}', name='A Giver', email=email, status=status)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _Case(TestCase):
    @classmethod
    def setUpTestData(cls):
        # ⚠ MIGRATION 0098 SEEDS BRIGHTPATH INTO EVERY TEST DATABASE, so a bare fixture already
        # holds one active gift. Left alone, "this organisation runs one gift" would silently be
        # "the platform runs two" and every resolution test would assert the ambiguous branch
        # while claiming to test the simple one. Switched off here so the fixture states exactly
        # the world it means.
        Programme.objects.update(is_active=False)
        cls.org_a, cls.org_b = _org('gift-a'), _org('gift-b')
        cls.flagship = Programme.objects.create(
            organisation=cls.org_a, code='a-flagship', name_en='A Flagship', is_active=True)
        cls.admin_a = _admin('gift-admin-a', cls.org_a)
        cls.admin_b = _admin('gift-admin-b', cls.org_b)
        cls.plain_admin = _admin('gift-plain', cls.org_a, role='admin')

    def setUp(self):
        self.client = APIClient()

    def _post(self, admin, url, body):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_make_token(admin.supabase_user_id)}')
        return self.client.post(url, body, format='json')

    def _second_gift(self, active=True):
        return Programme.objects.create(
            organisation=self.org_a, code='a-sabah', name_en='A Sabah', is_active=active)


class TestWhichGiftARegistrationJoins(_Case):
    """`signup_programme_for` — the function that replaced the tenant literal."""

    def test_one_active_gift_resolves_itself_which_is_production_today(self):
        # The old constant's behaviour, reproduced without naming a tenant.
        self.assertEqual(svc.signup_programme_for(_sponsor()), self.flagship)

    def test_an_INACTIVE_second_gift_does_not_make_the_answer_ambiguous(self):
        # A gift created but not switched on is taking nobody, so it must not turn a resolvable
        # answer into a question. This is production the day the owner creates a draft gift.
        self._second_gift(active=False)
        self.assertEqual(svc.signup_programme_for(_sponsor()), self.flagship)

    def test_TWO_ACTIVE_gifts_and_no_invitation_resolves_to_NOTHING(self):
        # ⚠ THE REFUSAL. A stranger off the public form: nothing on the platform knows which gift
        # they meant, and guessing files their money against the wrong one.
        self._second_gift()
        self.assertIsNone(svc.signup_programme_for(_sponsor()))

    def test_the_invitation_they_answered_names_the_gift(self):
        sabah = self._second_gift()
        Invitation.objects.create(
            audience='sponsor', email='giver@example.com', organisation=self.org_a,
            programme=sabah, code='inv-1')
        self.assertEqual(svc.signup_programme_for(_sponsor()), sabah)

    def test_the_invitation_wins_even_when_one_gift_would_have_resolved(self):
        # Otherwise an organisation that states a gift is overruled by the fallback whenever the
        # fallback happens to have an answer — which is exactly when it is most confident.
        sabah = self._second_gift(active=False)
        Invitation.objects.create(
            audience='sponsor', email='giver@example.com', organisation=self.org_a,
            programme=sabah, code='inv-2')
        self.assertEqual(svc.signup_programme_for(_sponsor()), sabah)

    def test_a_REVOKED_invitation_states_nothing(self):
        from django.utils import timezone
        self._second_gift()
        Invitation.objects.create(
            audience='sponsor', email='giver@example.com', organisation=self.org_a,
            programme=self.flagship, code='inv-3', revoked_at=timezone.now())
        self.assertIsNone(svc.signup_programme_for(_sponsor()))


class TestTheMembershipWriter(_Case):
    def test_it_writes_nothing_rather_than_falling_back(self):
        # ⚠ None is handled, NOT defaulted. A default here is how the tenant literal survived.
        s = _sponsor()
        self.assertIsNone(svc.sync_account_membership(s, None))
        self.assertEqual(SponsorProgrammeMembership.objects.filter(sponsor=s).count(), 0)

    def test_the_programme_is_required_positionally_so_no_caller_can_forget_it(self):
        with self.assertRaises(TypeError):
            svc.sync_account_membership(_sponsor())      # type: ignore[call-arg]

    def test_it_touches_ONLY_the_gift_it_was_given(self):
        # ⚠ The rule that predates the parameter: a second gift's membership is that
        # organisation's separate acceptance decision and must never be flipped as a side-effect
        # of platform-level account vetting.
        s = _sponsor(status='approved')
        sabah = self._second_gift()
        svc.set_programme_membership(s, sabah, 'approved', vetted_by='a@example.com')
        svc.sync_account_membership(s, self.flagship, vetted_by='b@example.com')
        by_code = {m.programme.code: m.status
                   for m in SponsorProgrammeMembership.objects.filter(sponsor=s)}
        self.assertEqual(by_code, {'a-sabah': 'approved', 'a-flagship': 'approved'})


class TestAcceptingIntoAGift(_Case):
    URL = '/api/v1/admin/sponsors/%s/membership/'

    def test_the_owners_scenario_end_to_end_the_money_is_unblocked(self):
        """A benefactor for the SECOND gift: refused before acceptance, accepted after."""
        sabah = self._second_gift()
        s = _sponsor()

        # ⚠ THE MAKER IS A PLAIN `admin`, NOT THE ORG_ADMIN. P4b's chain is maker `admin` ->
        # [finance] -> approver `org_admin`, so recording with the org_admin refuses `wrong_role`
        # long before the membership is looked at — and the test would then pass for the wrong
        # reason, asserting a role refusal while claiming to assert a membership one.
        #
        # Before: the exact refusal that blocked the RM100,000.
        with self.assertRaises(svc.CreditError) as cm:
            svc.record_admin_credit(sponsor=s, programme=sabah, amount=100000,
                                    external_reference='BANK-REF-1', admin=self.plain_admin)
        self.assertEqual(str(cm.exception), 'sponsor_not_in_programme')

        r = self._post(self.admin_a, self.URL % s.id,
                       {'programme_id': sabah.id, 'status': 'approved'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['status'], 'approved')

        # After: it records.
        d = svc.record_admin_credit(sponsor=s, programme=sabah, amount=100000,
                                    external_reference='BANK-REF-1', admin=self.plain_admin)
        self.assertEqual(d.programme_id, sabah.id)

    def test_accepting_into_one_gift_grants_NOTHING_in_another(self):
        # The owner's rule: "specifically onboarded into both and accepted into both — and that is
        # not a given". The pool's own seam is what reads this.
        from apps.scholarship import pool
        sabah = self._second_gift()
        s = _sponsor()
        self._post(self.admin_a, self.URL % s.id, {'programme_id': sabah.id, 'status': 'approved'})
        self.assertEqual(pool.approved_programme_ids(s), [sabah.id])

    def test_an_unvetted_ACCOUNT_cannot_be_accepted_into_a_gift(self):
        # A row saying "approved" while `Sponsor.status` refuses them everything is a screen
        # disagreeing with the system. Vet the account first.
        s = _sponsor(status='pending')
        r = self._post(self.admin_a, self.URL % s.id,
                       {'programme_id': self.flagship.id, 'status': 'approved'})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'account_not_approved')

    def test_acceptance_can_be_taken_back(self):
        from apps.scholarship import pool
        s = _sponsor()
        self._post(self.admin_a, self.URL % s.id,
                   {'programme_id': self.flagship.id, 'status': 'approved'})
        r = self._post(self.admin_a, self.URL % s.id,
                       {'programme_id': self.flagship.id, 'status': 'suspended'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(pool.approved_programme_ids(s), [])

    def test_ANOTHER_TENANTS_gift_is_404_never_403(self):
        # 403 would confirm the tenant exists. The SPONSOR is unfenced by design; the GIFT is not.
        theirs = Programme.objects.create(
            organisation=self.org_b, code='b-flagship', name_en='B Flagship', is_active=True)
        s = _sponsor()
        r = self._post(self.admin_a, self.URL % s.id,
                       {'programme_id': theirs.id, 'status': 'approved'})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(SponsorProgrammeMembership.objects.filter(sponsor=s).count(), 0)

    def test_a_plain_admin_may_not_decide_who_funds_the_students(self):
        # One role narrower than the sponsor LIST, which admin and finance both read. Deciding who
        # may fund your students is the organisation administrator's call.
        s = _sponsor()
        r = self._post(self.plain_admin, self.URL % s.id,
                       {'programme_id': self.flagship.id, 'status': 'approved'})
        self.assertEqual(r.status_code, 403)

    def test_a_nonsense_status_is_refused_rather_than_stored(self):
        s = _sponsor()
        r = self._post(self.admin_a, self.URL % s.id,
                       {'programme_id': self.flagship.id, 'status': 'vip'})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'bad_status')


class TestTheInviteAsksWhichGift(_Case):
    URL = '/api/v1/admin/invitations/'

    def _invite(self, admin, **extra):
        body = {'audience': 'sponsor', 'email': 'newgiver@example.com'}
        body.update(extra)
        return self._post(admin, self.URL, body)

    def test_ONE_gift_asks_nothing_and_the_form_is_unchanged(self):
        r = self._invite(self.admin_a)
        self.assertIn(r.status_code, (201, 502))     # 502 only if the mail seam refuses
        inv = Invitation.objects.get(email='newgiver@example.com')
        self.assertEqual(inv.programme_id, self.flagship.id)

    def test_TWO_gifts_and_none_named_REFUSES_and_lists_the_choices(self):
        # ⚠ Never a silent pick. The screen asks; it does not guess on the owner's behalf.
        sabah = self._second_gift()
        r = self._invite(self.admin_a)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'programme_required')
        self.assertEqual(sorted(p['code'] for p in r.data['programmes']),
                         ['a-flagship', 'a-sabah'])
        self.assertFalse(Invitation.objects.filter(email='newgiver@example.com').exists())
        self.assertTrue(sabah.pk)

    def test_the_named_gift_is_recorded_on_the_invitation(self):
        sabah = self._second_gift()
        r = self._invite(self.admin_a, programme_id=sabah.id)
        self.assertIn(r.status_code, (201, 502))
        self.assertEqual(
            Invitation.objects.get(email='newgiver@example.com').programme_id, sabah.id)

    def test_another_tenants_gift_cannot_be_named(self):
        theirs = Programme.objects.create(
            organisation=self.org_b, code='b-flagship-2', name_en='B Flagship', is_active=True)
        r = self._invite(self.admin_a, programme_id=theirs.id)
        self.assertEqual(r.status_code, 404)
