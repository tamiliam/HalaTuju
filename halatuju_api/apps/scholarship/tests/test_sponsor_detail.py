"""One sponsor, whole — the admin detail payload (2026-07-27).

Before this, `/admin/sponsors` was a flat vetting table: an administrator could approve or
suspend a sponsor and see nothing else. The wallet, the sponsorships, the people they
invited and whether they had ever come back were all invisible.

The load-bearing decision pinned here is the SPLIT. A `Sponsor` is a platform-level account
with no organisation, so identity is shown whole and cross-org by design. But a credit
belongs to a programme an organisation runs, and a sponsorship belongs to an application an
organisation owns — so every figure with money or a student in it is fenced to the caller's
own organisation. Getting that backwards in either direction is the bug this file exists to
prevent: fence the identity and the screen breaks for a super; don't fence the money and one
tenant reads another's giving.

Also pinned: the payload's EXACT key set (a plain dict, never a ModelSerializer, so a column
added to `Sponsor` later cannot arrive on an admin screen unnoticed); that the credits list
shows unconfirmed money while the wallet tiles do not; and that `last_seen_at` is stamped
once a day rather than on every request.
"""
import datetime
from decimal import Decimal
from unittest import mock

import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation, StudentProfile
from apps.scholarship import sponsorship as svc
from apps.scholarship.models import (
    Programme, ScholarshipApplication, ScholarshipCohort, Sponsor,
    SponsorProgrammeMembership, Sponsorship, SponsorReferral,
)

TEST_JWT_SECRET = 'test-supabase-jwt-secret'

#: Every key the detail payload may carry. A new key must be added here DELIBERATELY —
#: that is the whole point (the same guard the funding summary and org-request payloads use).
EXPECTED_KEYS = {
    'id', 'name', 'email', 'phone', 'organisation', 'source', 'note',
    'status', 'is_trusted',
    'created_at', 'reviewed_at', 'reviewed_by', 'last_seen_at',
    'consent_at', 'consent_version',
    'notify_frequency', 'last_digest_sent_at',
    'programmes', 'credits', 'sponsorships', 'referrals', 'memberships',
    'finance_check_required', 'fenced',
}


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


def _admin(org, role, name, email, uid=None):
    return PartnerAdmin.objects.create(
        supabase_user_id=uid or f'sd-{email}', role=role, is_active=True,
        owning_organisation=org, name=name, email=email)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class SponsorDetailBase(TestCase):
    """Two tenants, one sponsor who has given to BOTH — the only shape that can prove the
    split. A single-org fixture would pass whether or not the fence existed."""

    @classmethod
    def setUpTestData(cls):
        cls.org_a = PartnerOrganisation.objects.create(code='sd-a', name='Alpha Foundation')
        cls.org_b = PartnerOrganisation.objects.create(code='sd-b', name='Beta Society')
        cls.prog_a = Programme.objects.create(organisation=cls.org_a, code='sd-pa',
                                              name_en='Alpha Bursary')
        cls.prog_b = Programme.objects.create(organisation=cls.org_b, code='sd-pb',
                                              name_en='Beta Bursary')

        cls.sponsor = Sponsor.objects.create(
            supabase_user_id='sd-spon', name='Bharathan Nair', email='nair@example.com',
            phone='+60 12-345 6789', status='approved', notify_frequency='weekly',
            consent_version='2026-sponsor-draft-1', consent_at=timezone.now())
        for prog in (cls.prog_a, cls.prog_b):
            SponsorProgrammeMembership.objects.create(
                sponsor=cls.sponsor, programme=prog, status='approved')

        cls.maker_a = _admin(cls.org_a, 'admin', 'Poongulali Veeran', 'kulaly@a.com')
        cls.approver_a = _admin(cls.org_a, 'org_admin', 'Suresh Thirugnanam', 'suresh@a.com')
        cls.org_admin_b = _admin(cls.org_b, 'org_admin', 'Beta Admin', 'beta@b.com')
        cls.superadmin = PartnerAdmin.objects.create(
            supabase_user_id='sd-super', role='super', is_super_admin=True, is_active=True,
            name='Owner', email='owner@x.com')

    def _confirmed_credit(self, programme, amount, ref, maker, approver):
        """Drive the REAL chain to `confirmed` — a hand-built row would not prove that the
        wallet tiles read confirmed money only."""
        credit = svc.record_admin_credit(
            sponsor=self.sponsor, programme=programme, amount=Decimal(amount),
            external_reference=ref, admin=maker)
        svc.sign_admin_credit(credit, maker, maker.name)
        svc.sign_admin_credit(credit, approver, approver.name)
        credit.refresh_from_db()
        return credit

    def _student(self, org, programme, uid, amount='3000'):
        cohort = ScholarshipCohort.objects.create(
            code=f'sd-{uid}', name='C', year=2026,
            owning_organisation=org, programme=programme)
        profile = StudentProfile.objects.create(
            supabase_user_id=f'sd-stu-{uid}', nric=f'0101{uid}-14-0001', name=f'Stu {uid}')
        app = ScholarshipApplication.objects.create(
            cohort=cohort, profile=profile, status='recommended',
            award_amount=Decimal(amount))
        Sponsorship.objects.create(sponsor=self.sponsor, application=app,
                                   amount=Decimal(amount), status='offered')
        return app

    def _get(self, admin, pk=None):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(admin.supabase_user_id)}')
        return client.get(f'/api/v1/admin/sponsors/{pk or self.sponsor.pk}/')


class TestPayloadShape(SponsorDetailBase):
    def test_exact_key_set(self):
        """A `Sponsor` column added later must not reach an admin screen by accident."""
        res = self._get(self.superadmin)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(set(res.data), EXPECTED_KEYS)

    def test_identity_is_shown_whole(self):
        res = self._get(self.superadmin)
        self.assertEqual(res.data['name'], 'Bharathan Nair')
        self.assertEqual(res.data['email'], 'nair@example.com')
        self.assertEqual(res.data['notify_frequency'], 'weekly')
        self.assertEqual(res.data['consent_version'], '2026-sponsor-draft-1')

    def test_unknown_sponsor_is_404(self):
        self.assertEqual(self._get(self.superadmin, pk=999999).status_code, 404)


class TestRoleGate(SponsorDetailBase):
    def test_reviewer_and_qc_are_refused(self):
        """The Sponsors surface is super/org_admin/admin/finance — the same gate as the
        list. A reviewer has no business in a funder's record."""
        for role in ('reviewer', 'qc'):
            admin = _admin(self.org_a, role, role.title(), f'{role}@a.com')
            self.assertEqual(self._get(admin).status_code, 403, role)

    def test_finance_may_read(self):
        finance = _admin(self.org_a, 'finance', 'Sam Finance', 'sam@a.com')
        self.assertEqual(self._get(finance).status_code, 200)


class TestMoneyIsOrgFenced(SponsorDetailBase):
    """The sprint's load-bearing invariant."""

    def setUp(self):
        self._confirmed_credit(self.prog_a, '20000', 'TRF-A-1',
                               self.maker_a, self.approver_a)
        # Maker must be a plain `admin`, approver an `org_admin` — the live BrightPath
        # shape, and enforced by the service (a reversed pair raises `wrong_role`).
        self._confirmed_credit(self.prog_b, '5000', 'TRF-B-1',
                               _admin(self.org_b, 'admin', 'B Maker', 'bm@b.com'),
                               self.org_admin_b)
        self._student(self.org_a, self.prog_a, '11')
        self._student(self.org_b, self.prog_b, '22')

    def test_super_sees_both_organisations(self):
        res = self._get(self.superadmin)
        self.assertFalse(res.data['fenced'])
        self.assertEqual({p['programme_name'] for p in res.data['programmes']},
                         {'Alpha Bursary', 'Beta Bursary'})
        self.assertEqual(len(res.data['credits']), 2)
        self.assertEqual(len(res.data['sponsorships']), 2)

    def test_org_admin_sees_only_its_own_share(self):
        res = self._get(self.approver_a)
        self.assertTrue(res.data['fenced'])
        self.assertEqual([p['programme_name'] for p in res.data['programmes']],
                         ['Alpha Bursary'])
        self.assertEqual([c['external_reference'] for c in res.data['credits']], ['TRF-A-1'])
        self.assertEqual([s['programme_name'] for s in res.data['sponsorships']],
                         ['Alpha Bursary'])

    def test_the_other_tenants_money_never_appears(self):
        """Stated as a leak test, not a count: the failure that matters is Beta's figures
        showing up in Alpha's screen at all."""
        body = str(self._get(self.approver_a).data)
        self.assertNotIn('TRF-B-1', body)
        self.assertNotIn('Beta Bursary', body)
        self.assertNotIn('5000', body)

    def test_memberships_are_fenced_too(self):
        res = self._get(self.approver_a)
        self.assertEqual([m['programme_name'] for m in res.data['memberships']],
                         ['Alpha Bursary'])


class TestWalletFigures(SponsorDetailBase):
    def test_given_committed_available_reconcile_per_programme(self):
        self._confirmed_credit(self.prog_a, '20000', 'TRF-A-1',
                               self.maker_a, self.approver_a)
        self._student(self.org_a, self.prog_a, '11', amount='3000')
        self._student(self.org_a, self.prog_a, '12', amount='3000')

        row = self._get(self.approver_a).data['programmes'][0]
        self.assertEqual(row['given'], '20000.00')
        self.assertEqual(row['committed'], '6000.00')
        self.assertEqual(row['available'], '14000.00')
        self.assertEqual(row['credits'], 1)
        self.assertEqual(row['students'], 2)

    def test_an_unconfirmed_credit_is_in_the_ledger_but_not_in_the_balance(self):
        """An admin must SEE a draft in order to sign it; a donor must never be told we
        hold money that has not cleared the chain. Both at once."""
        self._confirmed_credit(self.prog_a, '20000', 'TRF-A-1',
                               self.maker_a, self.approver_a)
        svc.record_admin_credit(
            sponsor=self.sponsor, programme=self.prog_a, amount=Decimal('10000'),
            external_reference='TRF-A-PENDING', admin=self.maker_a)

        data = self._get(self.approver_a).data
        self.assertIn('TRF-A-PENDING', [c['external_reference'] for c in data['credits']])
        # The pending RM10,000 is absent from BOTH figures — no student is funded here, so
        # available == given, and the draft has changed neither.
        self.assertEqual(data['programmes'][0]['given'], '20000.00')
        self.assertEqual(data['programmes'][0]['available'], '20000.00')
        self.assertEqual(data['programmes'][0]['credits'], 1)

    def test_committed_counts_offered_not_only_active(self):
        """Award acceptance is switched off in production, so NOTHING reaches `active`.
        A committed figure that counted only `active` would read RM0 beside a reduced
        balance — the contradiction this sprint fixes."""
        self._confirmed_credit(self.prog_a, '20000', 'TRF-A-1',
                               self.maker_a, self.approver_a)
        self._student(self.org_a, self.prog_a, '11', amount='3000')
        self.assertEqual(
            self.sponsor.sponsorships.filter(status='active').count(), 0)
        self.assertEqual(self._get(self.approver_a).data['programmes'][0]['committed'],
                         '3000.00')


class TestListColumns(SponsorDetailBase):
    """The list gained `given` + `students` + `last_seen_at` so it can be SCANNED. All three
    carry the same fence as the detail page — the account is cross-org, the money is not."""

    def _list(self, admin):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(admin.supabase_user_id)}')
        return client.get('/api/v1/admin/sponsors/')

    def test_given_is_org_fenced_on_the_list_too(self):
        self._confirmed_credit(self.prog_a, '20000', 'TRF-A-1',
                               self.maker_a, self.approver_a)
        self._confirmed_credit(self.prog_b, '5000', 'TRF-B-1',
                               _admin(self.org_b, 'admin', 'B Maker', 'bm@b.com'),
                               self.org_admin_b)

        rows = {r['id']: r for r in self._list(self.superadmin).data['sponsors']}
        self.assertEqual(rows[self.sponsor.id]['given'], '25000.00')

        rows = {r['id']: r for r in self._list(self.approver_a).data['sponsors']}
        self.assertEqual(rows[self.sponsor.id]['given'], '20000.00')

    def test_an_unconfirmed_credit_is_not_counted_as_given(self):
        svc.record_admin_credit(
            sponsor=self.sponsor, programme=self.prog_a, amount=Decimal('9000'),
            external_reference='TRF-A-DRAFT', admin=self.maker_a)
        rows = {r['id']: r for r in self._list(self.approver_a).data['sponsors']}
        self.assertEqual(rows[self.sponsor.id]['given'], '0.00')

    def test_a_sponsor_who_gave_nothing_reads_zero_not_null(self):
        """A null would render as a blank cell that reads like missing data."""
        Sponsor.objects.create(supabase_user_id='sd-none', name='Nobody',
                               email='none@x.com', status='approved')
        rows = {r['name']: r for r in self._list(self.superadmin).data['sponsors']}
        self.assertEqual(rows['Nobody']['given'], '0.00')
        self.assertEqual(rows['Nobody']['students'], 0)
        self.assertIsNone(rows['Nobody']['last_seen_at'])

    def test_students_is_org_fenced_on_the_list_too(self):
        """Students fence on the APPLICATION's owner, not the programme's."""
        self._student(self.org_a, self.prog_a, '21')
        self._student(self.org_a, self.prog_a, '22')
        self._student(self.org_b, self.prog_b, '23')

        rows = {r['id']: r for r in self._list(self.superadmin).data['sponsors']}
        self.assertEqual(rows[self.sponsor.id]['students'], 3)

        rows = {r['id']: r for r in self._list(self.approver_a).data['sponsors']}
        self.assertEqual(rows[self.sponsor.id]['students'], 2)

        rows = {r['id']: r for r in self._list(self.org_admin_b).data['sponsors']}
        self.assertEqual(rows[self.sponsor.id]['students'], 1)

    def test_money_and_students_do_not_inflate_each_other(self):
        """The join-fan-out trap: counting students in the SAME annotate() as the money
        multiplies the two relations, so 2 credits × 3 students would read 6 of each — and
        `Sum(distinct=True)`, the usual cure, is worse (it collapses two equal credits into
        one). Hence the separate aggregate. This is the test that catches either mistake."""
        self._confirmed_credit(self.prog_a, '10000', 'TRF-A-1', self.maker_a, self.approver_a)
        self._confirmed_credit(self.prog_a, '10000', 'TRF-A-2', self.maker_a, self.approver_a)
        for uid in ('31', '32', '33'):
            self._student(self.org_a, self.prog_a, uid, amount='1000')

        row = {r['id']: r for r in self._list(self.approver_a).data['sponsors']}[self.sponsor.id]
        self.assertEqual(row['given'], '20000.00')   # not 60,000, and not 10,000
        self.assertEqual(row['students'], 3)         # not 6

    def test_each_sponsor_gets_its_own_count(self):
        """The count is one grouped query, not one per row — so it has to be keyed correctly.
        With a single sponsor in the fixture a mis-keyed total would still look right."""
        other = Sponsor.objects.create(supabase_user_id='sd-other', name='Other Giver',
                                       email='other@x.com', status='approved')
        self._student(self.org_a, self.prog_a, '51')
        app = self._student(self.org_a, self.prog_a, '52')
        Sponsorship.objects.filter(application=app).update(sponsor=other)

        rows = {r['name']: r for r in self._list(self.approver_a).data['sponsors']}
        self.assertEqual(rows['Bharathan Nair']['students'], 1)
        self.assertEqual(rows['Other Giver']['students'], 1)

    def test_a_finished_sponsorship_is_not_a_current_student(self):
        """`students` counts HOLDING allocations — the same rule the detail page's per-wallet
        `students` uses, so the two surfaces cannot disagree."""
        app = self._student(self.org_a, self.prog_a, '41')
        Sponsorship.objects.filter(application=app).update(status='cancelled')
        rows = {r['id']: r for r in self._list(self.approver_a).data['sponsors']}
        self.assertEqual(rows[self.sponsor.id]['students'], 0)


class TestReferralsAndStudents(SponsorDetailBase):
    def test_people_they_invited_are_listed(self):
        SponsorReferral.objects.create(
            inviter=self.sponsor, invitee_name='Divya A', invitee_email='divya@x.com',
            code='abc123', status='joined', joined_at=timezone.now())
        res = self._get(self.superadmin)
        self.assertEqual([r['invitee_name'] for r in res.data['referrals']], ['Divya A'])

    def test_a_student_is_named_only_by_the_anonymous_ref(self):
        """The sponsor's shared vocabulary, and the same code they see. The real name is one
        click away in the cockpit — it does not belong in this payload."""
        app = self._student(self.org_a, self.prog_a, '11')
        row = self._get(self.approver_a).data['sponsorships'][0]
        self.assertEqual(row['application_id'], app.id)
        self.assertTrue(row['ref'].startswith('S-'))
        body = str(self._get(self.approver_a).data)
        self.assertNotIn('Stu 11', body)


class TestStatementCommittedLine(SponsorDetailBase):
    """The sponsor-facing half of the same contradiction (payload only — the sponsor screen
    layout is deferred; see P4b-ii)."""

    def test_statement_carries_a_committed_total(self):
        self._confirmed_credit(self.prog_a, '20000', 'TRF-A-1',
                               self.maker_a, self.approver_a)
        self._student(self.org_a, self.prog_a, '11', amount='3000')

        st = svc.sponsor_statement(self.sponsor)
        self.assertEqual(st['total_in'], '20000.00')
        self.assertEqual(st['total_out'], '0')          # nothing accepted yet
        self.assertEqual(st['total_committed'], '3000.00')
        self.assertEqual([c['ref'][:2] for c in st['committed']], ['S-'])


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestLastSeenStamp(TestCase):
    """`last_seen_at` answers "is this sponsor still with us" — a question about days."""

    def setUp(self):
        self.sponsor = Sponsor.objects.create(
            supabase_user_id='seen-1', name='Seen', email='seen@x.com', status='approved')
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("seen-1")}')

    def test_first_visit_stamps_it(self):
        self.assertIsNone(self.sponsor.last_seen_at)
        self.client.get('/api/v1/sponsor/me/')
        self.sponsor.refresh_from_db()
        self.assertIsNotNone(self.sponsor.last_seen_at)

    @override_settings(SPONSOR_SEEN_THROTTLE_HOURS=24)
    def test_a_second_visit_the_same_day_does_not_write_again(self):
        self.client.get('/api/v1/sponsor/me/')
        self.sponsor.refresh_from_db()
        first = self.sponsor.last_seen_at
        self.client.get('/api/v1/sponsor/me/')
        self.sponsor.refresh_from_db()
        self.assertEqual(self.sponsor.last_seen_at, first)

    @override_settings(SPONSOR_SEEN_THROTTLE_HOURS=24)
    def test_a_visit_after_the_window_writes_again(self):
        stale = timezone.now() - datetime.timedelta(days=2)
        Sponsor.objects.filter(pk=self.sponsor.pk).update(last_seen_at=stale)
        self.client.get('/api/v1/sponsor/me/')
        self.sponsor.refresh_from_db()
        self.assertGreater(self.sponsor.last_seen_at, stale)

    def test_the_stamp_never_breaks_the_portal(self):
        """Telemetry is not worth an error page — proven by injecting a failure into the
        write itself.

        Tested as a unit, not through the view: patching `Sponsor.objects` at module level
        would break `get_sponsor` (which runs first and is deliberately NOT wrapped), so a
        200 would prove nothing about the stamp.
        """
        from apps.scholarship import views_sponsor
        with mock.patch.object(views_sponsor.Sponsor.objects, 'filter',
                               side_effect=RuntimeError('db down')):
            views_sponsor._touch_last_seen(self.sponsor)    # must not raise

    def test_a_visit_does_not_read_as_an_edit(self):
        """Stamped with update(), so `updated_at` (auto_now) must not move — otherwise a
        visit would look like a change to the account."""
        before = self.sponsor.updated_at
        self.client.get('/api/v1/sponsor/me/')
        self.sponsor.refresh_from_db()
        self.assertEqual(self.sponsor.updated_at, before)
