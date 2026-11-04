"""Team tables T5c P5b S1 (2026-11-05): the Overview's per-person pending cards.

`GET admin/scholarship/my-pending/` (`views_admin/my_pending.py`, `my_pending.pending_for`), driven per
role through the real endpoint: exact counts per role, a card the caller may not see ABSENT (never zero),
the union for a two-role person, the pooled super, the org fence, the refusals, and PARITY with the
pages each card opens (the Overview's attention / mine / qc, the payment list's `your_step`, the
invitations page, the request and sponsor badges). The QC card leaves out the cases `qc_separation`
bars; `barred_ids` is pinned to `refusal` case by case.
"""
import datetime
from datetime import date
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import qc_separation, sponsorship
from apps.scholarship.models import (
    AssignmentEvent, Donation, InterviewSession, Invitation, MentoringSession, Mentor, MentorAssignment,
    OrgRequest, PaymentRun, ScholarshipApplication, Sponsor, StaffActivity,
)
from apps.scholarship.review_sla import clocks as review_clocks
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org, make_programme,
    unique_suffix,
)

PENDING = '/api/v1/admin/scholarship/my-pending/'
OVERVIEW = '/api/v1/admin/scholarship/programme-overview/'
RUNS = '/api/v1/admin/scholarship/payment-runs/'
REQUESTS_BADGE = '/api/v1/admin/scholarship/requests/count/'
INVITATIONS = '/api/v1/admin/invitations/'
SPONSOR_BADGE = '/api/v1/admin/sponsors/pending-count/'
APPLICATION_KEYS = {'unassigned', 'overdue', 'awaiting_qc'}


def _scholar(cohort, **kw):
    return make_application('maintenance', cohort=cohort,
                            active_at=timezone.now() - datetime.timedelta(days=60), **kw)


def _sponsor(status):
    return Sponsor.objects.create(supabase_user_id=unique_suffix('sp-'), name='Sponsor', email=f'{unique_suffix("sp")}@example.test',
                                  phone='0123456789', source='friend', consent_at=timezone.now(), status=status)


def _org_data(cls, org, gift, cohort, tag):
    """The money / invitation / request rows of one organisation."""
    PaymentRun.objects.create(organisation=org, programme=gift, payment_date=date(2026, 7, 1),
                              period_month=date(2026, 7, 1), status='admin_signed', reference=f'{tag}-run',
                              admin_signed_email='maker@example.test', admin_signed_name='Maker',
                              admin_signed_at=timezone.now())
    sponsor = _sponsor('approved')
    Donation.objects.create(sponsor=sponsor, amount=Decimal('100'), programme=gift,
                            status=Donation.STATUS_ADMIN_SIGNED, recorded_by_email='maker@example.test')
    Donation.objects.create(sponsor=sponsor, amount=Decimal('50'), programme=gift, status=Donation.STATUS_DRAFT)
    Invitation.objects.create(audience='staff', email=f'{tag}-inv@example.test', name='Invitee',
                              code=unique_suffix('inv'), organisation=org, role='reviewer',
                              expires_at=timezone.now() + datetime.timedelta(days=7))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET, REQUESTS_ENABLED=True)
class MyPending(TestCase):

    @classmethod
    def setUpTestData(cls):
        now = timezone.now()
        cls.org, cls.other = make_org(), make_org()
        g1, gb = make_programme(cls.org, code='pd-g1'), make_programme(cls.other, code='pd-gb')
        c1, cb = make_cohort(programme=g1), make_cohort(programme=gb)
        sla, _soon, _grace = review_clocks(cls.org)

        cls.reviewer = make_admin('reviewer', owning_org=cls.org)
        cls.colleague = make_admin('reviewer', owning_org=cls.org)
        make_application('assigned', cohort=c1, reviewer=cls.reviewer)                       # open
        make_application('assigned', cohort=c1, reviewer=cls.reviewer,
                         assigned_at=now - datetime.timedelta(days=sla) + datetime.timedelta(hours=1))  # due soon
        make_application('assigned', cohort=c1, reviewer=cls.reviewer,
                         assigned_at=now - datetime.timedelta(days=sla + 1))                 # overdue
        make_application('assigned', cohort=c1, reviewer=cls.colleague)                      # not the reviewer's
        make_application('profile_complete', cohort=c1)                                      # unassigned + ready
        make_application('profile_complete', cohort=c1)
        make_application('submitted', cohort=c1)                                             # not yet ready: not counted

        cls.qc = make_admin('qc', owning_org=cls.org)
        cls.waiting = [make_application('awaiting_qc', outcome='recommend', cohort=c1, reviewer=cls.colleague)
                       for _ in range(5)]
        ScholarshipApplication.objects.filter(pk=cls.waiting[0].pk).update(
            verdict_decided_at=now - datetime.timedelta(days=10))
        AssignmentEvent.objects.create(application=cls.waiting[2], to_admin=cls.qc)            # barred
        InterviewSession.objects.create(application=cls.waiting[3], interviewer=cls.qc)        # barred
        StaffActivity.objects.create(actor=cls.qc, verb='verdict_recorded', subject_type='application',
                                     subject_id=cls.waiting[4].pk)                             # barred

        cls.org_admin = make_admin('org_admin', owning_org=cls.org)
        cls.finance = make_admin('finance', owning_org=cls.org, first_seen_at=now)
        _org_data(cls, cls.org, g1, c1, 'a')
        _sponsor('pending')
        OrgRequest.objects.create(organisation=cls.org, submitted_by=cls.org_admin, kind='feature', title='T',
                                  description='D', status='quoted', quote_hours=Decimal('2'), quoted_at=now)

        cls.mentor = make_admin('mentor', owning_org=cls.org)
        met = MentorAssignment.objects.create(application=_scholar(c1), mentor=cls.mentor.mentor)
        MentoringSession.objects.create(application=met.application, mentor=cls.mentor.mentor, assignment=met,
                                        met_on=date(2026, 10, 1), mode='video', minutes=45, notes='Met.',
                                        logged_by_email='m@example.test')
        MentorAssignment.objects.create(application=_scholar(c1, help_university='yes'), mentor=cls.mentor.mentor)
        MentorAssignment.objects.create(application=_scholar(c1), mentor=cls.mentor.mentor)
        ended = MentorAssignment.objects.create(application=_scholar(c1), mentor=cls.mentor.mentor)
        ended.ended_at = now
        ended.save(update_fields=['ended_at'])
        MentorAssignment.objects.create(application=_scholar(cb), mentor=cls.mentor.mentor)   # another tenant's file

        cls.both = make_admin('reviewer', owning_org=cls.org, mentor=Mentor.objects.create(organisation=cls.org))
        make_application('assigned', cohort=c1, reviewer=cls.both)
        MentorAssignment.objects.create(application=_scholar(c1), mentor=cls.both.mentor)

        # The other organisation: its own cases, money rows, invitation and request — none may leak.
        cls.other_admin = make_admin('org_admin', owning_org=cls.other)
        make_application('profile_complete', cohort=cb)
        make_application('awaiting_qc', outcome='decline', cohort=cb, reviewer=make_admin('reviewer', owning_org=cls.other))
        _org_data(cls, cls.other, gb, cb, 'b')
        OrgRequest.objects.create(organisation=cls.other, submitted_by=cls.other_admin, kind='feature', title='T',
                                  description='D', status='quoted', quote_hours=Decimal('2'), quoted_at=now)
        cls.super = make_admin('super', super_admin=True)

    def cards(self, who):
        r = authed_client(who).get(PENDING)
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()['cards']
        keys = [c['key'] for c in body]
        self.assertEqual(len(keys), len(set(keys)))                       # no duplicate keys
        return {c['key']: {k: v for k, v in c.items() if k != 'key'} for c in body}

    def get(self, who, url):
        r = authed_client(who).get(url)
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    # ── one per role, exact counts ────────────────────────────────────────────────────────────────────
    def test_an_org_admin_gets_the_application_and_admin_cards(self):
        cards = self.cards(self.org_admin)
        self.assertEqual(cards['unassigned'], {'count': 2})
        self.assertEqual(cards['overdue'], {'count': 1, 'due_soon': 1})
        self.assertEqual(cards['awaiting_qc'], {'count': 5})
        self.assertEqual(cards['sponsors_to_vet'], {'count': 1})
        self.assertEqual(cards['invitations'], {'count': 1})
        self.assertEqual(cards['payment_runs'], {'count': 0})            # finance checks it, not the lead
        self.assertEqual(cards['requests'], {'count': 1})
        self.assertNotIn('wallet_credits', cards)
        self.assertFalse({'my_open', 'qc_awaiting', 'mentees'} & set(cards))

    def test_finance_gets_the_money_cards_and_no_application_keys(self):
        cards = self.cards(self.finance)
        self.assertEqual(cards, {'payment_runs': {'count': 1}, 'wallet_credits': {'count': 1},
                                 'sponsors_to_vet': {'count': 1}, 'invitations': {'count': 1}})
        self.assertFalse(APPLICATION_KEYS & set(cards))

    def test_finance_signing_the_credit_takes_it_off_the_card(self):
        credit = Donation.objects.get(programme__organisation=self.org, status=Donation.STATUS_ADMIN_SIGNED)
        sponsorship.sign_admin_credit(credit, self.finance, self.finance.name)
        self.assertEqual(self.cards(self.finance)['wallet_credits'], {'count': 0})

    def test_a_reviewer_counts_only_their_own_cases(self):
        self.assertEqual(self.cards(self.reviewer), {'my_open': {'count': 3}, 'my_due_soon': {'count': 1},
                                                     'my_overdue': {'count': 1}})
        self.assertEqual(self.cards(self.colleague)['my_open'], {'count': 1})   # their cases at QC are not open

    def test_qc_leaves_out_the_barred_cases(self):
        cards = self.cards(self.qc)
        self.assertEqual(cards['qc_awaiting'], {'count': 2, 'oldest_days': 10})
        self.assertFalse(APPLICATION_KEYS & set(cards))

    def test_barred_ids_agree_with_refusal_case_by_case(self):
        apps = ScholarshipApplication.objects.filter(status='interviewed')
        barred = qc_separation.barred_ids(self.qc, apps)
        for app in apps:
            with self.subTest(app=app.pk):
                self.assertEqual(app.pk in barred, qc_separation.refusal(self.qc, app) is not None)
        self.assertEqual({self.waiting[2].pk, self.waiting[3].pk, self.waiting[4].pk} & barred,
                         {self.waiting[2].pk, self.waiting[3].pk, self.waiting[4].pk})
        self.assertEqual(qc_separation.barred_ids(self.super, apps), set())

    def test_a_mentor_counts_current_own_org_mentees_only(self):
        self.assertEqual(self.cards(self.mentor), {'mentees': {'count': 3}, 'not_met': {'count': 2},
                                                   'asked_help': {'count': 1}})

    def test_a_two_role_person_gets_both_sets(self):
        cards = self.cards(self.both)
        self.assertEqual(cards['my_open'], {'count': 1})
        self.assertEqual(cards['mentees'], {'count': 1})
        self.assertEqual(cards['not_met'], {'count': 1})
        self.assertEqual(cards['asked_help'], {'count': 0})

    def test_a_super_reads_the_pooled_platform(self):
        cards = self.cards(self.super)
        org_admin = self.cards(self.org_admin)
        other = self.cards(self.other_admin)
        self.assertGreaterEqual(cards['unassigned']['count'],
                                org_admin['unassigned']['count'] + other['unassigned']['count'])
        self.assertEqual(cards['awaiting_qc']['count'], ScholarshipApplication.objects.filter(status='interviewed').count())
        self.assertEqual(cards['requests'], self.get(self.super, REQUESTS_BADGE))
        self.assertEqual(cards['invitations']['count'], Invitation.objects.count())

    # ── the fence ─────────────────────────────────────────────────────────────────────────────────────
    def test_nothing_from_a_second_organisation_leaks(self):
        other = self.cards(self.other_admin)
        self.assertEqual(other['unassigned'], {'count': 1})
        self.assertEqual(other['awaiting_qc'], {'count': 1})
        self.assertEqual(other['invitations'], {'count': 1})
        self.assertEqual(other['requests'], {'count': 1})
        self.assertEqual(other['overdue'], {'count': 0, 'due_soon': 0})

    # ── refusals ──────────────────────────────────────────────────────────────────────────────────────
    def test_refusals(self):
        partner = make_admin('partner', org=make_org())
        self.assertEqual(authed_client(partner).get(PENDING).status_code, 403)
        source = make_admin('source_partner', owning_org=self.org)
        self.assertIn(authed_client(source).get(PENDING).status_code, (401, 403))
        inactive = make_admin('org_admin', owning_org=self.org, is_active=False)
        self.assertIn(authed_client(inactive).get(PENDING).status_code, (401, 403))
        stopped = make_admin('mentor', owning_org=self.org)
        stopped.mentor.deactivated_at = timezone.now()
        stopped.mentor.save()
        self.assertEqual(authed_client(stopped).get(PENDING).status_code, 403)

    def test_refusals_match_my_programmes(self):
        for who in (make_admin('partner', org=make_org()), make_admin('source_partner', owning_org=self.org),
                    make_admin('org_admin', owning_org=self.org, is_active=False)):
            with self.subTest(role=who.role):
                self.assertEqual(authed_client(who).get(PENDING).status_code,
                                 authed_client(who).get('/api/v1/admin/scholarship/my-programmes/').status_code)

    # ── parity with the pages the cards open ──────────────────────────────────────────────────────────
    def test_parity_with_the_overview_attention(self):
        attention = self.get(self.org_admin, OVERVIEW)['attention']
        cards = self.cards(self.org_admin)
        self.assertEqual((cards['unassigned']['count'], cards['overdue']['count'], cards['overdue']['due_soon'],
                          cards['awaiting_qc']['count']),
                         (attention['unassigned'], attention['overdue'], attention['due_soon'],
                          attention['awaiting_qc']))

    def test_parity_with_the_overview_mine(self):
        for who in (self.reviewer, self.colleague, self.both):
            mine = self.get(who, OVERVIEW)['mine']
            cards = self.cards(who)
            with self.subTest(who=who.pk):
                self.assertEqual((cards['my_open']['count'], cards['my_due_soon']['count'],
                                  cards['my_overdue']['count']), (mine['open'], mine['due_soon'], mine['overdue']))

    def test_parity_with_the_qc_queue_minus_the_barred(self):
        qc = self.get(self.qc, OVERVIEW)['qc']
        self.assertEqual(self.cards(self.qc)['qc_awaiting']['count'], qc['awaiting'] - 3)

    def test_parity_with_the_payment_list_badges_and_invitations(self):
        for who in (self.org_admin, self.finance, self.other_admin):
            with self.subTest(role=who.role):
                cards = self.cards(who)
                runs = self.get(who, RUNS)['runs']
                self.assertEqual(cards['payment_runs']['count'], sum(1 for r in runs if r['your_step']))
                self.assertEqual(cards['sponsors_to_vet'], self.get(who, SPONSOR_BADGE))
                self.assertEqual(cards['invitations']['count'], sum(self.get(who, INVITATIONS)['waiting'].values()))
        for who in (self.org_admin, self.other_admin):
            self.assertEqual(self.cards(who)['requests'], self.get(who, REQUESTS_BADGE))
