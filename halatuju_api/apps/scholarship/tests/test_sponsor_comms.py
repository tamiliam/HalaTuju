"""Sponsor comms (S3, 2026-07-28) — what a sponsor hears, and the gates that keep it quiet.

Before this, a sponsor registered, was vetted and was approved without being told any of it:
`AdminSponsorReviewView` flipped a status field and returned. Eight people on production were
approved in silence.

Three things in here matter more than the rest, and each is a way this sprint could do harm
rather than merely fail:

1. **The three ADOPTED emails must keep sending while the templates are dark.** `new_students`,
   `weekly_digest` and `referral_invite` are LIVE on production. Routing a live email through a
   switched-off template would silently stop it — sponsors would just stop hearing from us, and
   nothing would look broken. That fallback is the reason this can ship dark at all.
2. **`credit_confirmed` fires on `confirmed` and nothing earlier.** A draft credit is money we
   have not agreed we hold; telling a donor otherwise is the one unrecoverable mistake here.
3. **The placeholder allowlist is a privacy control.** No token resolves to a student's identity,
   so an editable template cannot become a new route around the anonymity the pool serializers
   enforce.
"""
from decimal import Decimal
from unittest import mock

import jwt
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.scholarship import sponsor_comms, sponsor_notify
from apps.scholarship import sponsorship as svc
from apps.scholarship.management.commands.seed_sponsor_email_templates import SEEDS
from apps.scholarship.models import (
    Donation, Programme, Sponsor, SponsorEmailLog, SponsorEmailTemplate,
    SponsorProgrammeMembership, SponsorReferral,
)

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
EMAILS = '/api/v1/admin/scholarship/sponsor-emails/'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


def _admin(org, role, name, email):
    return PartnerAdmin.objects.create(
        supabase_user_id=f'sc-{email}', role=role, is_active=True,
        owning_organisation=org, name=name, email=email)


def _template(kind, *, enabled=True, subject=None, body=None):
    seed = SEEDS[kind]
    return SponsorEmailTemplate.objects.create(
        kind=kind, enabled=enabled,
        subject=subject if subject is not None else seed['subject'],
        body=body if body is not None else seed['body'])


class CommsBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='sc-org', name='Alpha Foundation')
        cls.programme = Programme.objects.create(
            organisation=cls.org, code='sc-p', name_en='Alpha Bursary')
        cls.sponsor = Sponsor.objects.create(
            supabase_user_id='sc-spon', name='Bharathan Nair',
            email='nair@example.com', status='approved')
        SponsorProgrammeMembership.objects.create(
            sponsor=cls.sponsor, programme=cls.programme, status='approved')

    def setUp(self):
        mail.outbox = []


# ── the two gates ─────────────────────────────────────────────────────────────

@override_settings(SPONSOR_COMMS_ENABLED=True)
class TestTheGates(CommsBase):
    def test_both_gates_open_sends_and_logs_it(self):
        _template('welcome')
        self.assertTrue(sponsor_notify.send_welcome(self.sponsor))
        self.assertEqual(len(mail.outbox), 1)
        row = SponsorEmailLog.objects.get()
        self.assertTrue(row.ok)
        self.assertEqual(row.recipients, ['nair@example.com'])
        self.assertEqual(row.kind, 'welcome')

    def test_a_switched_off_template_sends_nothing_and_says_why(self):
        _template('welcome', enabled=False)
        self.assertFalse(sponsor_notify.send_welcome(self.sponsor))
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(SponsorEmailLog.objects.get().note, 'disabled')

    def test_an_unseeded_kind_is_distinct_from_a_switched_off_one(self):
        """One is a decision, the other is a deployment step nobody ran."""
        self.assertFalse(sponsor_notify.send_welcome(self.sponsor))
        self.assertEqual(SponsorEmailLog.objects.get().note, 'no_template')

    def test_a_sponsor_with_no_address_is_logged_not_silently_dropped(self):
        _template('welcome')
        nameless = Sponsor.objects.create(supabase_user_id='sc-none', name='No Email', email='')
        self.assertFalse(sponsor_notify.send_welcome(nameless))
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(SponsorEmailLog.objects.get().note, 'no_recipient')


class TestTheDarkLaunch(CommsBase):
    """`SPONSOR_COMMS_ENABLED` unset — the state this sprint SHIPS in."""

    def test_the_platform_gate_alone_stops_an_enabled_template(self):
        _template('welcome', enabled=True)
        self.assertFalse(sponsor_notify.send_welcome(self.sponsor))
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(SponsorEmailLog.objects.get().note, 'platform_off')

    def test_is_enabled_needs_both(self):
        _template('welcome', enabled=True)
        self.assertFalse(sponsor_comms.is_enabled('welcome'))
        with override_settings(SPONSOR_COMMS_ENABLED=True):
            self.assertTrue(sponsor_comms.is_enabled('welcome'))
            SponsorEmailTemplate.objects.update(enabled=False)
            self.assertFalse(sponsor_comms.is_enabled('welcome'))


# ── the three LIVE emails must not go quiet ───────────────────────────────────

class TestAdoptedEmailsKeepSendingWhileDark(CommsBase):
    """The regression this sprint could most easily have caused, and nobody would have noticed.

    These three emails are live on production with their cron jobs enabled. A dark template must
    not silence them — the legacy sender stays the path until an org_admin switches the template
    on.
    """
    def test_a_referral_invite_still_goes_out(self):
        referral = SponsorReferral.objects.create(
            inviter=self.sponsor, invitee_email='friend@example.com',
            invitee_name='Friend', code='abc123', status='invited')
        self.assertTrue(sponsor_notify.send_referral_invite(referral))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('friend@example.com', mail.outbox[0].to)

    def test_the_new_student_alert_still_goes_out(self):
        cards = [{'ref': 'S-AAA111', 'course': 'Medicine', 'amount': '3000'}]
        with mock.patch('apps.scholarship.emails.send_sponsor_new_student_email',
                        return_value=True) as legacy:
            self.assertTrue(sponsor_notify.send_student_alert(self.sponsor, cards))
        legacy.assert_called_once()

    def test_the_weekly_digest_still_goes_out(self):
        cards = [{'ref': 'S-AAA111', 'course': 'Medicine', 'amount': '3000'}]
        with mock.patch('apps.scholarship.emails.send_sponsor_digest_email',
                        return_value=True) as legacy:
            self.assertTrue(sponsor_notify.send_student_alert(self.sponsor, cards, weekly=True))
        legacy.assert_called_once()

    @override_settings(SPONSOR_COMMS_ENABLED=True)
    def test_the_template_takes_over_once_it_is_switched_on(self):
        _template('referral_invite')
        referral = SponsorReferral.objects.create(
            inviter=self.sponsor, invitee_email='friend@example.com',
            invitee_name='Friend', code='abc123', status='invited')
        with mock.patch('apps.scholarship.emails.send_sponsor_referral_invite') as legacy:
            self.assertTrue(sponsor_notify.send_referral_invite(referral))
        legacy.assert_not_called()
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(SponsorEmailLog.objects.get().ok)


# ── credit_confirmed: the one that must never fire early ──────────────────────

@override_settings(SPONSOR_COMMS_ENABLED=True)
class TestCreditConfirmed(CommsBase):
    def _credit(self, status):
        return Donation.objects.create(
            sponsor=self.sponsor, programme=self.programme, amount=Decimal('10000'),
            source=Donation.SOURCE_ADMIN, external_reference='TRF-1',
            reference='TRF-1', status=status)

    def test_never_fires_before_the_money_is_confirmed(self):
        _template('credit_confirmed')
        for status in (Donation.STATUS_DRAFT, Donation.STATUS_ADMIN_SIGNED,
                       Donation.STATUS_FINANCE_CHECKED, Donation.STATUS_CANCELLED):
            self.assertFalse(sponsor_notify.send_credit_confirmed(self._credit(status)), status)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(SponsorEmailLog.objects.count(), 0)

    def test_fires_on_confirmed_and_states_the_amount_and_reference(self):
        _template('credit_confirmed')
        self.assertTrue(sponsor_notify.send_credit_confirmed(
            self._credit(Donation.STATUS_CONFIRMED)))
        body = mail.outbox[0].body
        self.assertIn('10000.00', body)
        self.assertIn('TRF-1', body)


@override_settings(SPONSOR_COMMS_ENABLED=True)
class TestCreditChainNotifies(CommsBase):
    """Driven through the real sign-off chain rather than a hand-set status — the point is that
    the notification hangs off the transition, not off a field somebody assigned."""

    def test_the_donor_hears_only_at_the_countersignature(self):
        _template('credit_confirmed')
        maker = _admin(self.org, 'admin', 'Poongulali Veeran', 'kulaly@a.com')
        approver = _admin(self.org, 'org_admin', 'Suresh Thirugnanam', 'suresh@a.com')
        credit = svc.record_admin_credit(
            sponsor=self.sponsor, programme=self.programme, amount=Decimal('5000'),
            external_reference='TRF-9', admin=maker)

        svc.sign_admin_credit(credit, maker, maker.name)      # maker signs — still not ours
        self.assertEqual(len(mail.outbox), 0)

        svc.sign_admin_credit(credit, approver, approver.name)   # countersigned → confirmed
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(SponsorEmailLog.objects.filter(ok=True, kind='credit_confirmed').count(), 1)


# ── the vetting outcome, which used to be silence ─────────────────────────────

@override_settings(SPONSOR_COMMS_ENABLED=True)
class TestVettingOutcome(CommsBase):
    def test_each_decision_picks_its_own_email(self):
        for status, kind in (('approved', 'approved'), ('rejected', 'rejected'),
                             ('suspended', 'suspended')):
            SponsorEmailLog.objects.all().delete()
            SponsorEmailTemplate.objects.all().delete()
            _template(kind)
            self.assertTrue(sponsor_notify.send_vetting_outcome(self.sponsor, status))
            self.assertEqual(SponsorEmailLog.objects.get().kind, kind)

    def test_approving_a_SUSPENDED_sponsor_reinstates_rather_than_welcomes(self):
        """The two read very differently to somebody who was suspended, and the review endpoint
        uses one action for both."""
        _template('reinstated')
        self.assertTrue(sponsor_notify.send_vetting_outcome(
            self.sponsor, 'approved', previous_status='suspended'))
        self.assertEqual(SponsorEmailLog.objects.get().kind, 'reinstated')


# ── nothing may raise into a caller ───────────────────────────────────────────

@override_settings(SPONSOR_COMMS_ENABLED=True)
class TestItNeverBreaksTheCaller(CommsBase):
    def test_a_failing_sender_is_swallowed_and_logged(self):
        _template('welcome')
        with mock.patch('apps.scholarship.sponsor_notify.send_sponsor_email',
                        side_effect=RuntimeError('smtp down')):
            self.assertFalse(sponsor_notify.send_welcome(self.sponsor))
        row = SponsorEmailLog.objects.get()
        self.assertFalse(row.ok)
        self.assertIn('RuntimeError', row.note)

    def test_even_a_broken_render_cannot_escape(self):
        _template('welcome')
        with mock.patch('apps.scholarship.sponsor_comms.render',
                        side_effect=ValueError('boom')):
            self.assertFalse(sponsor_notify.send_welcome(self.sponsor))


# ── the guards on saved copy ──────────────────────────────────────────────────

class TestTheGuards(TestCase):
    def test_an_unsupplied_token_is_refused(self):
        self.assertEqual(
            sponsor_comms.unknown_placeholders('welcome', 'Hi {sponsor_name} {student_cards}'),
            ('student_cards',))

    def test_no_kind_can_reach_a_student_identity(self):
        """The allowlist is a privacy control: `student_cards` is the ONLY student content any
        template can render, and it is the same anonymised card the pool serializer produces."""
        forbidden = {'student_name', 'student_email', 'student_nric', 'school', 'name', 'nric'}
        for kind, allowed in sponsor_comms.PLACEHOLDERS.items():
            self.assertEqual(allowed & forbidden, set(), kind)

    def test_a_tax_relief_claim_is_refused(self):
        """We hold no LHDN s44(6) approval — this is the one line that could cost a donor money."""
        self.assertIn('tax deductible',
                      sponsor_comms.banned_phrases('Your gift is tax deductible'))
        self.assertIn('tax-exempt', sponsor_comms.banned_phrases('a tax-exempt donation'))

    def test_student_ownership_and_urgency_are_refused(self):
        self.assertIn('your student', sponsor_comms.banned_phrases('Read about your student'))
        self.assertIn('act now', sponsor_comms.banned_phrases('Act now to help'))

    def test_clean_copy_passes(self):
        self.assertEqual(sponsor_comms.banned_phrases('Thank you for supporting a student.'), ())


class TestTheSeeds(TestCase):
    def test_the_seeds_cover_exactly_the_model_kinds(self):
        """Derived from the model's own choices, not a hand-copied list — a list that enumerates
        what it guards narrows silently every time the source grows."""
        self.assertEqual(set(SEEDS), set(sponsor_comms.KINDS))
        self.assertEqual(set(SEEDS),
                         {k for k, _ in SponsorEmailTemplate.KIND_CHOICES})

    def test_every_seed_satisfies_the_guards_a_hand_edit_would_face(self):
        for kind, seed in SEEDS.items():
            self.assertEqual(
                sponsor_comms.unknown_placeholders(kind, seed['subject'], seed['body']), (), kind)
            self.assertEqual(
                sponsor_comms.banned_phrases(seed['subject'], seed['body']), (), kind)

    def test_every_kind_has_a_placeholder_allowlist(self):
        self.assertEqual(set(sponsor_comms.PLACEHOLDERS), set(sponsor_comms.KINDS))

    def test_seeding_is_idempotent_and_never_switches_anything_on(self):
        call_command('seed_sponsor_email_templates', verbosity=0)
        self.assertEqual(SponsorEmailTemplate.objects.count(), len(SEEDS))
        self.assertEqual(SponsorEmailTemplate.objects.filter(enabled=True).count(), 0)

        tpl = SponsorEmailTemplate.objects.get(kind='welcome')
        tpl.enabled, tpl.subject = True, 'Edited by an org admin'
        tpl.save()

        call_command('seed_sponsor_email_templates', verbosity=0)
        tpl.refresh_from_db()
        self.assertEqual(tpl.subject, 'Edited by an org admin')   # wording left alone
        self.assertTrue(tpl.enabled)                              # switch never touched

        call_command('seed_sponsor_email_templates', '--reset', verbosity=0)
        tpl.refresh_from_db()
        self.assertEqual(tpl.subject, SEEDS['welcome']['subject'])   # wording reset
        self.assertTrue(tpl.enabled)                                 # switch STILL not touched


# ── rendering ─────────────────────────────────────────────────────────────────

class TestRendering(CommsBase):
    def test_an_optional_token_that_fills_to_nothing_leaves_no_empty_paragraph(self):
        tpl = _template('referral_invite')
        _s, text, html = sponsor_comms.render('referral_invite', tpl, {
            'inviter_name': 'Suresh', 'invitee_name': 'Friend', 'note': '', 'invite_link': 'x'})
        self.assertNotIn('<p style="margin:0 0 14px;"></p>', html)
        self.assertNotIn('\n\n\n', text)

    def test_the_card_cap_announces_itself(self):
        """A silent truncation reads as "that is everyone" — the chase table learned this too."""
        cards = [{'ref': f'S-{i:06d}', 'course': 'Course', 'amount': '3000'}
                 for i in range(sponsor_comms.MAX_CARDS + 3)]
        html, text = sponsor_comms.student_cards_blocks(cards)
        self.assertIn('and 3 more', text)
        self.assertIn('and 3 more', html)

    def test_money_renders_one_way_everywhere(self):
        tpl = _template('credit_confirmed')
        _s, text, _h = sponsor_comms.render('credit_confirmed', tpl, {
            'amount': Decimal('20000'), 'available': Decimal('3000.00'), 'bank_ref': 'T-1'})
        self.assertIn('20000.00', text)      # not '20000'
        self.assertIn('3000.00', text)

    def test_a_structural_token_never_reaches_a_subject_line(self):
        tpl = _template('new_students', subject='{student_cards} waiting')
        subject, _t, _h = sponsor_comms.render('new_students', tpl, {
            'cards': [{'ref': 'S-A', 'course': 'Medicine', 'amount': '3000'}]})
        self.assertNotIn('{student_cards}', subject)


# ── the endpoints ─────────────────────────────────────────────────────────────

@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestEndpoints(CommsBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.org_admin = _admin(cls.org, 'org_admin', 'Suresh', 'suresh@a.com')
        cls.finance = _admin(cls.org, 'finance', 'Sam Finance', 'finance@a.com')
        cls.reviewer = _admin(cls.org, 'reviewer', 'Rev', 'rev@a.com')

    def _client(self, admin):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(admin.supabase_user_id)}')
        return c

    def test_finance_and_reviewer_are_refused(self):
        """Finance reads sponsors because money is its business; deciding what every donor is
        told is editorial, and deliberately a narrower gate than the sponsor list."""
        for admin in (self.finance, self.reviewer):
            self.assertEqual(self._client(admin).get(EMAILS).status_code, 403)

    def test_an_org_admin_sees_the_templates_and_the_platform_gate(self):
        _template('welcome', enabled=False)
        res = self._client(self.org_admin).get(EMAILS)
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data['comms_enabled'])       # the panel can say the switches are inert
        self.assertEqual(res.data['expected'], len(sponsor_comms.KINDS))
        self.assertEqual([t['kind'] for t in res.data['templates']], ['welcome'])
        self.assertEqual(res.data['templates'][0]['placeholders'],
                         sorted(sponsor_comms.PLACEHOLDERS['welcome']))

    def test_switching_one_on_records_who_did_it(self):
        _template('welcome', enabled=False)
        res = self._client(self.org_admin).patch(
            f'{EMAILS}welcome/', {'enabled': True}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['enabled'])
        self.assertEqual(SponsorEmailTemplate.objects.get().updated_by_email, 'suresh@a.com')

    def test_an_unknown_placeholder_is_refused_with_the_offending_token(self):
        _template('welcome')
        res = self._client(self.org_admin).patch(
            f'{EMAILS}welcome/',
            {'subject': 'Hi', 'body': 'Dear {sponsor_name}, {student_cards}'}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data['code'], 'unknown_placeholder')
        self.assertEqual(res.data['placeholders'], ['student_cards'])

    def test_a_tax_claim_is_refused_on_save(self):
        _template('welcome')
        res = self._client(self.org_admin).patch(
            f'{EMAILS}welcome/',
            {'subject': 'Hi', 'body': 'Your gift is tax deductible.'}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data['code'], 'banned_phrasing')
        self.assertIn('tax deductible', res.data['phrases'])

    def test_an_unseeded_kind_is_404(self):
        self.assertEqual(
            self._client(self.org_admin).patch(f'{EMAILS}welcome/', {'enabled': True},
                                               format='json').status_code, 404)
