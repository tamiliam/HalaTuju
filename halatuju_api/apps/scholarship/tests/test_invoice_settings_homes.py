"""The two invoice settings, on the screens whose SCOPE matches them (2026-10-28).

Owner ruling after filling the form and watching an address spill across three boxes: who is
BILLING is platform-wide and belongs with the rates; who is BILLED is per-organisation and belongs
on that organisation's own settings — **and the organisation may edit its own**.

That last clause is the whole reason this file exists. It moves one write from super-only to
tenant-writable, so the property under test is no longer "the service filters" but **"the door
picks"** (Spending S6 lesson) — and it is asserted from the WIDENING side (TD-241 lesson): the
discriminator is tenant B naming tenant A's organisation, because every test where a tenant names
its own passes with the fence deleted.

The line this sprint keeps, straight from `AdminOrgBuildHoursView`: a tenant may not record what it
is billed FOR, nor set what it is billed AT. It may only say where its own bill is addressed.
"""
import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.scholarship.models import InvoiceIssuer, OrgBillingDetails

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
BASE = '/api/v1/admin/scholarship/billing'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BILLING_USAGE_ENABLED=True)
class _TwoTenants(TestCase):
    """TWO real tenants. One is not enough: with a single organisation every fence returns the
    right rows whether or not it fences."""

    @classmethod
    def setUpTestData(cls):
        cls.a, cls.admin_a = cls._tenant('alpha', 'Alpha Org')
        cls.b, cls.admin_b = cls._tenant('beta', 'Beta Org')
        OrgBillingDetails.objects.create(
            organisation=cls.a, bill_to_name='Alpha Berhad', address='1 Alpha Road',
            emails=['finance@alpha.example'])
        InvoiceIssuer.objects.create(
            legal_name='HalaTuju Platform', address='1 Jalan Contoh', email='billing@halatuju.xyz',
            bank_name='Maybank', bank_account_name='HalaTuju', bank_account_no='5140')
        cls.super = PartnerAdmin.objects.create(
            supabase_user_id='super-uid', is_super_admin=True, is_active=True,
            name='Super', email='super@x.com')

    @classmethod
    def _tenant(cls, code, name):
        """A tenant is an organisation with an active org_admin — `.tenants()`' own rule."""
        org = PartnerOrganisation.objects.create(code=code, name=name)
        admin = PartnerAdmin.objects.create(
            supabase_user_id=f'oa-{code}', role='org_admin', is_active=True,
            owning_organisation=org, name=f'OA {code}', email=f'oa@{code}.example')
        return org, admin

    def client_for(self, uid):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')
        return c


class TestWhoIsBilling(_TwoTenants):
    """The issuer is ONE platform-wide row. Nothing but a super may read or touch it."""

    def test_a_super_reads_and_saves_it(self):
        su = self.client_for('super-uid')
        self.assertEqual(su.get(f'{BASE}/issuer/').json()['issuer']['legal_name'],
                         'HalaTuju Platform')
        r = su.post(f'{BASE}/issuer/',
                    {'issuer': {'legal_name': 'New Name Berhad', 'payment_terms_days': 14}},
                    format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['issuer']['legal_name'], 'New Name Berhad')
        self.assertEqual(InvoiceIssuer.objects.get().payment_terms_days, 14)

    def test_no_tenant_may_read_or_write_it(self):
        """It carries the platform's own bank account. An org_admin is a tenant, not an owner."""
        oa = self.client_for('oa-alpha')
        self.assertEqual(oa.get(f'{BASE}/issuer/').status_code, 403)
        self.assertEqual(oa.post(f'{BASE}/issuer/', {'issuer': {'legal_name': 'Mine Now'}},
                                 format='json').status_code, 403)
        self.assertEqual(InvoiceIssuer.objects.get().legal_name, 'HalaTuju Platform')

    def test_a_bad_email_or_term_is_refused_and_nothing_is_saved(self):
        su = self.client_for('super-uid')
        for body, code in (({'issuer': {'email': 'not-an-email'}}, 'bad_email'),
                           ({'issuer': {'payment_terms_days': 400}}, 'bad_terms'),
                           ({'issuer': {'payment_terms_days': 'soon'}}, 'bad_terms'),
                           ({'organisation_id': self.a.id}, 'bad_issuer')):
            with self.subTest(body=body):
                r = su.post(f'{BASE}/issuer/', body, format='json')
                self.assertEqual(r.status_code, 400)
                self.assertEqual(r.json()['code'], code)
        self.assertEqual(InvoiceIssuer.objects.get().email, 'billing@halatuju.xyz')

    def test_the_read_never_creates_the_row_it_reports_as_missing(self):
        """On the first day in production there is no issuer at all, and the screen says which
        fields are blank. A GET that created a row would make `missing` a lie on the next read."""
        InvoiceIssuer.objects.all().delete()
        body = self.client_for('super-uid').get(f'{BASE}/issuer/').json()
        self.assertIn('legal_name', body['issuer']['missing'])
        self.assertFalse(InvoiceIssuer.objects.exists())


class TestWhoIsBilled(_TwoTenants):
    """An organisation's own bill-to. The one invoice setting a tenant may write."""

    def test_a_tenant_reads_and_writes_its_own(self):
        oa = self.client_for('oa-alpha')
        self.assertEqual(oa.get(f'{BASE}/bill-to/?organisation={self.a.code}').json()['bill_to_name'],
                         'Alpha Berhad')
        r = oa.post(f'{BASE}/bill-to/?organisation={self.a.code}',
                    {'bill_to_name': 'Alpha Sdn Bhd', 'address': '2 Alpha Road',
                     'emails': 'pay@alpha.example; ap@alpha.example'}, format='json')
        self.assertEqual(r.status_code, 200)
        row = OrgBillingDetails.objects.get(organisation=self.a)
        self.assertEqual(row.bill_to_name, 'Alpha Sdn Bhd')
        self.assertEqual(row.emails, ['pay@alpha.example', 'ap@alpha.example'])
        self.assertEqual(row.updated_by_email, 'oa@alpha.example')

    def test_the_widening_side_one_tenant_cannot_read_or_write_anothers(self):
        """⚠ THE DISCRIMINATOR. Every test above passes with the fence deleted; only this one
        fails. Beta naming Alpha's id must be a 404 — the same answer as an id that does not
        exist, so the route leaks no existence either."""
        ob = self.client_for('oa-beta')
        self.assertEqual(ob.get(f'{BASE}/bill-to/?organisation={self.a.code}').status_code, 404)
        r = ob.post(f'{BASE}/bill-to/?organisation={self.a.code}',
                    {'bill_to_name': 'Beta Took This', 'address': 'x',
                     'emails': ['beta@evil.example']}, format='json')
        self.assertEqual(r.status_code, 404)
        row = OrgBillingDetails.objects.get(organisation=self.a)
        self.assertEqual(row.bill_to_name, 'Alpha Berhad')
        self.assertEqual(row.emails, ['finance@alpha.example'])
        # ...and Beta did not quietly get a row of its own out of the attempt.
        self.assertFalse(OrgBillingDetails.objects.filter(organisation=self.b).exists())

    def test_with_two_tenants_a_super_must_say_which_one(self):
        """⚠ NEVER A SILENT PICK. Two tenants exist here, so a super naming none is refused and
        told the choices. Guessing which organisation a bill is addressed to is the one thing this
        endpoint must not do — and with one tenant on production the guess would look correct
        right up to the day a second arrives."""
        r = self.client_for('super-uid').get(f'{BASE}/bill-to/')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'organisation_required')
        # `brightpath` is the tenant a data migration seeds; the refusal lists every real one.
        self.assertEqual(sorted(r.json()['organisations']), ['alpha', 'beta', 'brightpath'])

    def test_a_lone_tenant_needs_no_code(self):
        """An org_admin's queryset is already narrowed to its own organisation, so the code is
        optional for them — and on today's production, where there is one tenant, for a super too."""
        self.assertEqual(self.client_for('oa-alpha').get(f'{BASE}/bill-to/').json()['bill_to_name'],
                         'Alpha Berhad')

    def test_a_missing_organisation_is_the_same_404_for_a_super(self):
        su = self.client_for('super-uid')
        self.assertEqual(su.get(f'{BASE}/bill-to/?organisation=no-such-org').status_code, 404)
        self.assertEqual(su.post(f'{BASE}/bill-to/?organisation=no-such-org', {'emails': []},
                                 format='json').status_code, 404)

    def test_a_referral_organisation_is_not_a_tenant_and_has_no_bill_to(self):
        """This table is dual-role: ten rows on production, one tenant. A school never gets a bill."""
        school = PartnerOrganisation.objects.create(code='a-school', name='A School')
        self.assertEqual(self.client_for('super-uid').get(
            f'{BASE}/bill-to/?organisation={school.code}').status_code, 404)

    def test_a_super_may_write_any_tenants(self):
        r = self.client_for('super-uid').post(
            f'{BASE}/bill-to/?organisation={self.b.code}',
            {'bill_to_name': 'Beta Berhad', 'address': 'KL', 'emails': ['ap@beta.example']},
            format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(OrgBillingDetails.objects.get(organisation=self.b).bill_to_name,
                         'Beta Berhad')

    def test_who_may_act_is_not_who_may_see(self):
        """⚠ The People-actions lesson, as a test. `admin` and `finance` can OPEN the organisation
        page this tab sits on; neither may act on the money printed on an invoice."""
        for role in ('admin', 'finance', 'qc', 'reviewer'):
            with self.subTest(role=role):
                PartnerAdmin.objects.create(
                    supabase_user_id=f'r-{role}', role=role, is_active=True,
                    owning_organisation=self.a, name=role, email=f'{role}@alpha.example')
                c = self.client_for(f'r-{role}')
                self.assertEqual(c.get(f'{BASE}/bill-to/?organisation={self.a.code}').status_code, 403)
                self.assertEqual(c.post(f'{BASE}/bill-to/?organisation={self.a.code}', {'emails': []},
                                        format='json').status_code, 403)
        self.assertEqual(OrgBillingDetails.objects.get(organisation=self.a).bill_to_name,
                         'Alpha Berhad')

    def test_a_bad_email_is_refused_and_the_stored_row_is_untouched(self):
        r = self.client_for('oa-alpha').post(
            f'{BASE}/bill-to/?organisation={self.a.code}',
            {'bill_to_name': 'Alpha', 'address': 'x', 'emails': ['ok@alpha.example', 'broken']},
            format='json')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'bad_email'))
        self.assertEqual(OrgBillingDetails.objects.get(organisation=self.a).emails,
                         ['finance@alpha.example'])

    def test_duplicate_inboxes_are_collapsed_once(self):
        self.client_for('oa-alpha').post(
            f'{BASE}/bill-to/?organisation={self.a.code}',
            {'bill_to_name': 'Alpha', 'address': 'x',
             'emails': 'a@alpha.example, a@alpha.example , b@alpha.example'}, format='json')
        self.assertEqual(OrgBillingDetails.objects.get(organisation=self.a).emails,
                         ['a@alpha.example', 'b@alpha.example'])

    def test_a_tenant_with_no_row_yet_reads_blanks_and_is_told_what_is_missing(self):
        body = self.client_for('oa-beta').get(f'{BASE}/bill-to/?organisation={self.b.code}').json()
        self.assertEqual(body['bill_to_name'], '')
        self.assertEqual(set(body['missing']), {'bill_to_name', 'address', 'emails'})
        self.assertFalse(OrgBillingDetails.objects.filter(organisation=self.b).exists())


class TestTheLineBetweenWhatATenantMaySet(_TwoTenants):
    """The whole point of the ruling, in one place: where the bill GOES is theirs; what it SAYS is
    not. If a later sprint widens one of these by accident, this is the test that notices."""

    def test_a_tenant_may_set_where_the_bill_goes_but_not_the_rates_or_its_hours(self):
        oa = self.client_for('oa-alpha')
        # Theirs:
        self.assertEqual(oa.post(f'{BASE}/bill-to/?organisation={self.a.code}',
                                 {'bill_to_name': 'Alpha', 'address': 'x',
                                  'emails': ['a@alpha.example']}, format='json').status_code, 200)
        # Not theirs — what they are billed AT, and what they are billed FOR:
        self.assertEqual(oa.get(f'{BASE}/rates/').status_code, 403)
        self.assertEqual(oa.post(f'{BASE}/rates/', {'category': 'metered', 'kind': 'margin_pct',
                                                    'value': '0'}, format='json').status_code, 403)
        self.assertEqual(oa.post(f'{BASE}/hours/{self.a.id}/',
                                 {'period_month': '2026-09', 'module': 'free work',
                                  'hours': '0.0', 'basis': 'mine now'},
                                 format='json').status_code, 403)

class TestAHostileBody(_TwoTenants):
    """Found by attacking the endpoint rather than by using it. None of these is a fence breach —
    they are the ways a bad body turned a refusal into a 500, or let one tenant spend a resource
    that belongs to every tenant."""

    def test_a_json_array_body_is_refused_not_a_crash(self):
        """`request.data` is a LIST for `[1,2]`, and `.get` on a list raises — which reaches the
        caller as a 500 and the logs as an exception nobody caused on purpose."""
        c = self.client_for('oa-alpha')
        r = c.post(f'{BASE}/bill-to/', [1, 2], format='json')
        self.assertLess(r.status_code, 500)
        r = c.get(f'{BASE}/bill-to/')
        self.assertEqual(r.status_code, 200)

    def test_one_tenant_cannot_list_enough_inboxes_to_spend_everyone_elses_mail(self):
        """⚠ The sending quota is the PLATFORM's, shared across every tenant. Every address here
        gets a copy of every invoice, so an unbounded list is one tenant able to burn it."""
        many = [f'a{i}@alpha.example' for i in range(40)]
        r = self.client_for('oa-alpha').post(
            f'{BASE}/bill-to/',
            {'bill_to_name': 'Alpha', 'address': 'x', 'emails': many}, format='json')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'too_many_emails'))
        self.assertEqual(OrgBillingDetails.objects.get(organisation=self.a).emails,
                         ['finance@alpha.example'])

    def test_a_realistic_finance_team_is_well_under_the_cap(self):
        """A cap that refuses a legitimate setting is worse than none (the interview-overlap
        lesson). Four inboxes is a real finance team and must sail through."""
        r = self.client_for('oa-alpha').post(
            f'{BASE}/bill-to/',
            {'bill_to_name': 'Alpha', 'address': 'x',
             'emails': ['ap@alpha.example', 'cfo@alpha.example', 'audit@alpha.example',
                        'admin@alpha.example']}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()['emails']), 4)

    def test_a_name_longer_than_the_column_is_refused_in_words(self):
        """200 characters is the column. A longer value is a database error on Postgres, which
        the caller meets as a 500 rather than as a sentence telling them what to fix."""
        r = self.client_for('oa-alpha').post(
            f'{BASE}/bill-to/',
            {'bill_to_name': 'A' * 201, 'address': 'x', 'emails': ['a@alpha.example']},
            format='json')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'name_too_long'))
        self.assertEqual(OrgBillingDetails.objects.get(organisation=self.a).bill_to_name,
                         'Alpha Berhad')

    def test_a_name_exactly_at_the_column_length_is_accepted(self):
        r = self.client_for('oa-alpha').post(
            f'{BASE}/bill-to/',
            {'bill_to_name': 'A' * 200, 'address': 'x', 'emails': ['a@alpha.example']},
            format='json')
        self.assertEqual(r.status_code, 200)
