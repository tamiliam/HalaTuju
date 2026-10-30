"""Source sign-in — the adversarial review's findings (2026-10-30), each pinned by a test that failed
before its fix. H1, M1, L1, L2, L3, L4 and L6b; the fixture is `test_source_witness`'s.

H1  A decline still in its cool-off must not change the source console before the student is told.
M1  A recorded witness belongs to the source that signed it; a later override hands it to nobody.
L1  Before a witness, the full contract only while it is live.
L2  `record_once` re-checks the witness organisation under the lock.
L3  A request value that is not text is a 400 `bad_request`, never a 500.
L4  `witness_ip` is the forwarded caller's address.
L6b A source named only by the override sees nothing before the witness step.
"""
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from apps.scholarship import bursary, source_console, source_witness
from apps.scholarship.models import BursaryAgreement, ScholarshipApplication
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort,
)
from apps.scholarship.tests.test_source_witness import (
    APPS, GOOD, OVERVIEW, _Fixture, agreement_url, super_witness_url, witness_url,
)

SCHOLARS = '/api/v1/admin/source/scholars/'
PROFILE = '/api/v1/admin/source/profile/'


def hold_decline(app, *, pre):
    """`decline.admin_reject`'s footprint for a CONTRACTUAL decline still inside its cool-off: the
    status is `rejected` at once, the student email is embargoed (pending marker + due time)."""
    ScholarshipApplication.objects.filter(pk=app.pk).update(
        status='rejected', pre_decline_status=pre, rejection_category='contractual',
        pending_rejection_category='contractual', rejected_at=timezone.now(),
        decline_due_at=timezone.now() + timezone.timedelta(hours=24))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=True)
class TestH1AHeldDeclineChangesNothingYet(_Fixture):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # A paid scholar at `awarded` (the live cohort's shape: wallet on) whose contract waits.
        ScholarshipApplication.objects.filter(pk=cls.ready.pk).update(
            vircle_activated_at=timezone.now())

    def _seen(self):
        scholars = {r['id'] for r in self.client.get(SCHOLARS).json()['scholars']}
        overview = self.client.get(OVERVIEW).json()
        waiting = {r['application_id'] for r in overview['witness_waiting']}
        return scholars, overview['scholars'], waiting

    def test_the_console_is_the_same_before_and_during_the_cool_off(self):
        before = self._seen()
        detail_before = self.client.get(f'{APPS}{self.ready.pk}/').json()
        hold_decline(self.ready, pre='awarded')
        hold_decline(self.countersigned, pre='active')
        self.assertEqual(self._seen(), before)
        detail = self.client.get(f'{APPS}{self.ready.pk}/').json()
        self.assertEqual((detail['stage'], detail['contract']['can_witness']),
                         (detail_before['stage'], True))
        self.assertIn(self.ready.pk, before[0])
        scholar = self.client.get(f'{SCHOLARS}{self.countersigned.pk}/')
        self.assertEqual((scholar.status_code, scholar.json()['status']), (200, 'active'))
        self.assertEqual(self.client.get(agreement_url(self.ready)).json()['can_witness'], True)

    def test_the_witness_may_still_be_recorded_during_the_cool_off(self):
        hold_decline(self.ready, pre='awarded')
        with patch.object(bursary, '_notify_foundation_countersign_pending'):
            resp = self.client.post(witness_url(self.ready), GOOD, format='json')
        self.assertEqual(resp.status_code, 200)

    def test_once_the_student_is_told_it_goes(self):
        hold_decline(self.ready, pre='awarded')
        ScholarshipApplication.objects.filter(pk=self.ready.pk).update(
            pending_rejection_category='', decline_due_at=None,
            decline_email_sent_at=timezone.now())
        scholars, _count, waiting = self._seen()
        self.assertNotIn(self.ready.pk, scholars | waiting)
        resp = self.client.post(witness_url(self.ready), GOOD, format='json')
        self.assertEqual((resp.status_code, resp.json()['code']), (409, 'contract_not_live'))

    def test_a_cancelled_decline_leaves_it_where_it_was(self):
        from apps.scholarship.services.decline import cancel_pending_decline
        before = self._seen()
        hold_decline(self.countersigned, pre='active')
        app = ScholarshipApplication.objects.get(pk=self.countersigned.pk)
        self.assertTrue(cancel_pending_decline(app))
        self.assertEqual(ScholarshipApplication.objects.get(pk=app.pk).status, 'active')
        self.assertEqual(self._seen(), before)

    def test_an_awarded_student_with_no_wallet_was_never_a_scholar(self):
        hold_decline(self.unsigned, pre='awarded')      # no wallet: not in maintenance before either
        self.assertNotIn(self.unsigned.pk, self._seen()[0])


class TestH1TheScholarSetMirrorsTheStudentsView(TestCase):
    """`source_console.scholar_q` (a query) agrees with `has_file` judged on what the student sees, for
    every pre-decline status x wallet, held and told."""

    def test_query_and_record_agree(self):
        from apps.scholarship.maintenance_scope import has_file
        from apps.scholarship.student_status import student_facing_status
        cohort = make_cohort()
        cases = []
        for pre in ('submitted', 'shortlisted', 'interviewing', 'recommended', 'awarded', 'active',
                    'maintenance'):
            for wallet in (None, timezone.now()):
                for held in (True, False):
                    app = make_application('submitted', cohort=cohort)
                    ScholarshipApplication.objects.filter(pk=app.pk).update(
                        status='rejected', pre_decline_status=pre, vircle_activated_at=wallet,
                        pending_rejection_category='interview' if held else '')
                    cases.append(app.pk)
        in_q = set(ScholarshipApplication.objects.filter(pk__in=cases)
                   .filter(source_console.scholar_q()).values_list('pk', flat=True))
        for app in ScholarshipApplication.objects.filter(pk__in=cases):
            seen = ScholarshipApplication(status=student_facing_status(app),
                                          vircle_activated_at=app.vircle_activated_at)
            self.assertEqual(app.pk in in_q, has_file(seen), (app.pre_decline_status,
                                                              app.pending_rejection_category))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=True)
class TestM1TheSignedContractStaysWithItsWitness(_Fixture):
    def setUp(self):
        super().setUp()
        self.other_client = authed_client(make_admin('source_partner', owning_org=self.org,
                                                     source=self.other))

    def _witness_then_move(self, app, to):
        with patch.object(bursary, '_notify_foundation_countersign_pending'):
            self.assertEqual(self.client.post(witness_url(app), GOOD, format='json').status_code,
                             200)
        ScholarshipApplication.objects.filter(pk=app.pk).update(witness_org=to)

    def test_a_moved_override_hands_the_contract_to_nobody(self):
        self._witness_then_move(self.ready, self.other)
        # The new override source: the case is in its scope, but it never signed this contract.
        for url in (agreement_url(self.ready), f'{agreement_url(self.ready)}?link=1',
                    f'{APPS}{self.ready.pk}/'):
            self.assertEqual(self.other_client.get(url).status_code, 404, url)
        # The source that witnessed keeps what it signed.
        body = self.client.get(agreement_url(self.ready)).json()
        self.assertEqual((body['witness_is_you'], body['can_witness']), (True, False))

    def test_a_witness_only_case_stays_with_its_witness_when_the_override_is_cleared(self):
        self._witness_then_move(self.witness_only, None)
        self.assertEqual(self.client.get(agreement_url(self.witness_only)).status_code, 200)
        detail = self.client.get(f'{APPS}{self.witness_only.pk}/').json()
        self.assertEqual((detail['kind'], detail['contract']['witness_is_you']),
                         ('witness_only', True))

    def test_the_witness_keeps_access_after_the_contract_ends(self):
        self._witness_then_move(self.ready, self.source)
        ScholarshipApplication.objects.filter(pk=self.ready.pk).update(status='closed')
        self.assertEqual(self.client.get(agreement_url(self.ready)).status_code, 200)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=True)
class TestL1TheContractOnlyWhileLive(_Fixture):
    def test_a_dead_contract_nobody_witnessed_is_not_served(self):
        for status in ('closed', 'withdrawn', 'expired'):
            ScholarshipApplication.objects.filter(pk=self.ready.pk).update(status=status)
            self.assertEqual(self.client.get(agreement_url(self.ready)).status_code, 404, status)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=True)
class TestL6bAnOverrideAloneRevealsNothing(_Fixture):
    def test_before_the_witness_step_the_case_is_404(self):
        url = f'{APPS}{self.witness_only.pk}/'
        BursaryAgreement.objects.filter(application=self.witness_only).update(
            guarantor_signed_at=None)
        self.assertEqual(self.client.get(url).status_code, 404)
        BursaryAgreement.objects.filter(application=self.witness_only).delete()
        self.assertEqual(self.client.get(url).status_code, 404)
        BursaryAgreement.objects.create(application=self.witness_only, version='v1',
                                        student_signed_at=timezone.now(),
                                        guarantor_signed_at=timezone.now())
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_the_applicants_own_source_still_sees_its_student(self):
        BursaryAgreement.objects.filter(application=self.unsigned).update(guarantor_signed_at=None)
        self.assertEqual(self.client.get(f'{APPS}{self.unsigned.pk}/').status_code, 200)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=True)
class TestL2TheOrganisationIsReCheckedUnderTheLock(_Fixture):
    def test_record_once_refuses_an_organisation_that_is_no_longer_the_witness(self):
        changed = getattr(source_witness, 'WitnessChanged', None)
        self.assertIsNotNone(changed)
        ScholarshipApplication.objects.filter(pk=self.ready.pk).update(witness_org=self.other)
        with self.assertRaises(changed):
            source_witness.record_once(self.agreement(self.ready), org=self.source, by_name='K',
                                       witness_name='Kala')
        self.assertIsNone(self.agreement(self.ready).witness_signed_at)

    def _moves_after_the_view_reads(self):
        """`_resolve_witness_org` answers the source for the view's check, then the other source:
        the override moved between the read and the lock."""
        real, calls = bursary._resolve_witness_org, []

        def resolve(app):
            calls.append(app.pk)
            return real(app) if len(calls) == 1 else self.other
        return patch.object(bursary, '_resolve_witness_org', side_effect=resolve)

    def test_the_source_door_answers_404(self):
        with self._moves_after_the_view_reads():
            resp = self.client.post(witness_url(self.ready), GOOD, format='json')
        self.assertEqual(resp.status_code, 404)
        self.assertIsNone(self.agreement(self.ready).witness_signed_at)

    def test_the_super_door_answers_409(self):
        client = authed_client(make_admin('super', super_admin=True))
        with self._moves_after_the_view_reads():
            resp = client.post(super_witness_url(self.ready), {'witness_name': 'R'}, format='json')
        self.assertEqual((resp.status_code, resp.json().get('code')), (409, 'witness_changed'))
        self.assertIsNone(self.agreement(self.ready).witness_signed_at)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=True)
class TestL3AValueThatIsNotTextIsA400(_Fixture):
    """One sweep over every source write that reads text from the body."""

    def test_every_source_write(self):
        org_admin = authed_client(make_admin('org_admin', owning_org=self.org))
        invite = '/api/v1/admin/invitations/'
        new_source = {'audience': 'source_partner', 'name': 'Raj', 'email': 'raj@src.test',
                      'source_code': 'newsrc', 'source_name': 'New Source'}
        cases = (
            (self.client, 'patch', PROFILE, {'source': {'phone': 123}}),
            (self.client, 'patch', PROFILE, {'user': {'name': 1}}),
            (self.client, 'patch', PROFILE, {'source': {'name': ['x']}}),
            (self.client, 'post', witness_url(self.ready), {'witness_name': 42, 'confirm': True}),
            (org_admin, 'post', invite, {**new_source, 'email': 5}),
            (org_admin, 'post', invite, {**new_source, 'name': 1}),
            (org_admin, 'post', invite, {**new_source, 'source_code': 7}),
            (org_admin, 'post', invite, {**new_source, 'source_name': ['x']}),
            (org_admin, 'post', invite, {**new_source, 'phone': 123}),
            (org_admin, 'patch', f'/api/v1/admin/scholarship/sources/{self.other.pk}/',
             {'phone': 123}),
            (org_admin, 'patch', f'/api/v1/admin/scholarship/sources/{self.other.pk}/',
             {'contact_email': {'a': 1}}),
        )
        for client, method, url, body in cases:
            with self.subTest(url=url, body=body):
                resp = getattr(client, method)(url, body, format='json')
                self.assertEqual((resp.status_code, resp.json().get('code')),
                                 (400, 'bad_request'))
        self.assertIsNone(self.agreement(self.ready).witness_signed_at)
        self.other.refresh_from_db()
        self.assertEqual(self.other.contact_email, 'other@src.test')

    def test_a_number_for_the_audience_is_refused_too(self):
        org_admin = authed_client(make_admin('org_admin', owning_org=self.org))
        resp = org_admin.post('/api/v1/admin/invitations/', {'audience': 5}, format='json')
        self.assertEqual(resp.status_code, 400)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=True)
class TestL4TheWitnessIpIsTheForwardedCaller(_Fixture):
    def _post(self, **meta):
        with patch.object(bursary, '_notify_foundation_countersign_pending'):
            return self.client.post(witness_url(self.ready), GOOD, format='json', **meta)

    def test_the_first_forwarded_hop(self):
        resp = self._post(HTTP_X_FORWARDED_FOR='198.51.100.7, 10.0.0.1', REMOTE_ADDR='10.0.0.1')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.agreement(self.ready).witness_ip, '198.51.100.7')

    def test_a_forged_header_never_fails_the_signature(self):
        resp = self._post(HTTP_X_FORWARDED_FOR='not-an-address', REMOTE_ADDR='10.0.0.1')
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(self.agreement(self.ready).witness_ip)


class TestL4TheSponsorHelperIsUnchanged(SimpleTestCase):
    def test_it_reads_the_same_as_before(self):
        from django.test import RequestFactory
        from apps.scholarship.views_sponsor import _client_ip
        rf = RequestFactory()
        self.assertEqual(_client_ip(rf.get('/', HTTP_X_FORWARDED_FOR='1.2.3.4, 5.6.7.8')),
                         '1.2.3.4')
        self.assertEqual(_client_ip(rf.get('/', REMOTE_ADDR='9.9.9.9')), '9.9.9.9')
        # As before the move: a malformed header is passed through (TD-429), not cleaned.
        self.assertEqual(_client_ip(rf.get('/', HTTP_X_FORWARDED_FOR='junk')), 'junk')
