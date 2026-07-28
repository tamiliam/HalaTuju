"""PF-1 — the open cohort must not be chosen platform-wide.

`resolve_open_cohort()` answered "which round is open on this PLATFORM" and the caller used that
answer to decide which round a student JOINS. With one tenant those are the same question. With
two they are not, and the difference is invisible: `ScholarshipApplication.save()` denormalises
`owning_organisation` from whichever cohort was picked, so a student who applies to organisation B
is filed under organisation A — visible to A's staff, invisible to B's, funded from A's money, with
no error anywhere.

**These tests are the deliverable.** The bug's whole character is that it is silent, so the proof
is a test that fails against the pre-fix code. `TestAmbiguousOpenCohortIsRefused` did exactly that
(verified before the fix: the resolver returned the `-2026`-sorting cohort and the endpoint created
an application under the wrong organisation).

The single-tenant tests are the other half of the promise: while one organisation has an open
round, behaviour is byte-identical to before. That is what makes this safe to ship ahead of the
routing work.
"""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerOrganisation, StudentProfile
from apps.scholarship import services
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort
from apps.scholarship.tests.test_api import TEST_JWT_SECRET, _make_token


def _org(code):
    # NB: never 'brightpath' — migration 0098 already seeds that org into the test DB.
    return PartnerOrganisation.objects.create(code=code, name=code.title())


def _cohort(org, code, *, year=2026, is_open=True, is_active=True):
    return ScholarshipCohort.objects.create(
        code=code, name=f'Cohort {code}', year=year,
        owning_organisation=org, is_open=is_open, is_active=is_active,
    )


class TestAmbiguousOpenCohortIsRefused(TestCase):
    """Two organisations, both open, nothing naming which — the platform must refuse to guess."""

    def setUp(self):
        self.org_a = _org('tenant-a')
        self.org_b = _org('tenant-b')
        # Deliberately ordered so the pre-fix `-year, code` sort has a clear (wrong) winner.
        self.cohort_a = _cohort(self.org_a, 'a-2026')
        self.cohort_b = _cohort(self.org_b, 'b-2026')

    def test_resolver_refuses_rather_than_picking_one(self):
        with self.assertRaises(services.AmbiguousOpenCohort):
            services.resolve_open_cohort()

    def test_the_refusal_names_the_candidates_so_an_operator_can_act(self):
        with self.assertRaises(services.AmbiguousOpenCohort) as ctx:
            services.resolve_open_cohort()
        self.assertCountEqual(ctx.exception.codes, ['a-2026', 'b-2026'])

    def test_an_explicit_code_still_resolves_it(self):
        """The escape hatch that P2's per-organisation apply link will use."""
        self.assertEqual(services.resolve_open_cohort('b-2026'), self.cohort_b)

    def test_only_OPEN_cohorts_count_as_ambiguous(self):
        """B closing is not ambiguity — A is the only round accepting applications."""
        self.cohort_b.is_open = False
        self.cohort_b.save(update_fields=['is_open'])
        self.assertEqual(services.resolve_open_cohort(), self.cohort_a)

    def test_inactive_cohorts_do_not_create_ambiguity_either(self):
        self.cohort_b.is_active = False
        self.cohort_b.save(update_fields=['is_active'])
        self.assertEqual(services.resolve_open_cohort(), self.cohort_a)

    def test_two_open_cohorts_of_the_SAME_organisation_are_still_ambiguous(self):
        """Not a tenancy question — 'which round?' is unanswerable within one org too.

        BrightPath running its 2026 and 2027 intakes open at once is the same defect: nothing in
        the request says which. Refusing is right, and it is what stops PF-1 reappearing one
        layer down the hierarchy.
        """
        self.cohort_b.owning_organisation = self.org_a
        self.cohort_b.save(update_fields=['owning_organisation'])
        with self.assertRaises(services.AmbiguousOpenCohort):
            services.resolve_open_cohort()


class TestSingleOpenCohortIsUnchanged(TestCase):
    """The promise that makes P1 shippable on its own: today's behaviour does not move."""

    def setUp(self):
        self.org = _org('tenant-a')
        self.cohort = _cohort(self.org, 'a-2026')

    def test_one_open_cohort_resolves_exactly_as_before(self):
        self.assertEqual(services.resolve_open_cohort(), self.cohort)

    def test_no_open_cohort_still_returns_None_not_an_error(self):
        """A closed intake is a normal state with its own message — never an ambiguity error."""
        self.cohort.is_open = False
        self.cohort.save(update_fields=['is_open'])
        self.assertIsNone(services.resolve_open_cohort())

    def test_an_unknown_explicit_code_still_returns_None(self):
        self.assertIsNone(services.resolve_open_cohort('no-such-cohort'))

    def test_a_closed_cohort_named_explicitly_is_still_returned_for_the_view_to_refuse(self):
        """`views.py` re-checks `is_open` itself and explains why; the resolver must not swallow
        that case, or the student gets 'no open round' when the truth is 'that round has closed'."""
        self.cohort.is_open = False
        self.cohort.save(update_fields=['is_open'])
        self.assertEqual(services.resolve_open_cohort('a-2026'), self.cohort)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestApplyEndpointRefusesToGuess(TestCase):
    """The endpoint, because that is where a wrong answer becomes a permanent database row."""

    def setUp(self):
        self.client = APIClient()
        self.org_a = _org('tenant-a')
        self.org_b = _org('tenant-b')
        self.cohort_a = _cohort(self.org_a, 'a-2026')
        self.cohort_b = _cohort(self.org_b, 'b-2026')
        self.profile = StudentProfile.objects.create(
            supabase_user_id='pf1-user', name='Test Student', nric='010101010101',
            contact_email='student@example.com',
        )

    def _auth(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_make_token("pf1-user")}')

    def test_no_application_is_created_under_an_arbitrary_organisation(self):
        """THE test. Pre-fix this created a row under whichever cohort sorted first."""
        self._auth()
        resp = self.client.post('/api/v1/scholarship/applications/', {}, format='json')
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json().get('code'), 'programme_required')
        self.assertFalse(ScholarshipApplication.objects.exists())

    def test_naming_the_round_lets_the_application_through_to_the_right_tenant(self):
        self._auth()
        resp = self.client.post(
            '/api/v1/scholarship/applications/', {'cohort_code': 'b-2026'}, format='json',
        )
        self.assertEqual(resp.status_code, 201)
        app = ScholarshipApplication.objects.get()
        self.assertEqual(app.cohort, self.cohort_b)
        # The whole point: tenancy follows the cohort, so naming the round names the organisation.
        self.assertEqual(app.owning_organisation_id, self.org_b.id)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestIntakeStatusDoesNotNameAnotherTenantsRound(TestCase):
    """The second unscoped read — public, and it drives the landing page's Apply button.

    Fixing only the apply path would have moved the bug rather than closed it.
    """

    def setUp(self):
        self.client = APIClient()
        self.org_a = _org('tenant-a')
        self.cohort_a = _cohort(self.org_a, 'a-2026')

    def test_one_open_round_still_names_it(self):
        resp = self.client.get('/api/v1/scholarship/intake/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {'open': True, 'cohort_name': 'Cohort a-2026'})

    def test_a_closed_intake_still_reads_closed(self):
        self.cohort_a.is_open = False
        self.cohort_a.save(update_fields=['is_open'])
        self.assertEqual(
            self.client.get('/api/v1/scholarship/intake/').json(),
            {'open': False, 'cohort_name': ''},
        )

    def test_two_open_rounds_stay_OPEN_but_name_neither(self):
        """Applications genuinely are open; naming one of them would be tenant A's programme
        advertised on tenant B's landing page."""
        _cohort(_org('tenant-b'), 'b-2026')
        body = self.client.get('/api/v1/scholarship/intake/').json()
        self.assertTrue(body['open'])
        self.assertEqual(body['cohort_name'], '')


# ── P2: the per-organisation apply link ──────────────────────────────────────────────────────
#
# The owner's answer to "how does an application know which organisation?" (2026-07-28): each
# organisation gets its own apply link carrying its PROGRAMME code. Programme rather than cohort
# because a cohort code is year-specific and a link pinned to one would rot every intake.

def _programme(org, code, name=None):
    from apps.scholarship.models import Programme
    return Programme.objects.create(organisation=org, code=code, name_en=name or code.title())


class TestProgrammeNamedByTheApplyLink(TestCase):
    def setUp(self):
        self.org_a, self.org_b = _org('tenant-a'), _org('tenant-b')
        self.prog_a = _programme(self.org_a, 'tenant-a-bursary')
        self.prog_b = _programme(self.org_b, 'tenant-b-bursary')
        self.cohort_a = _cohort(self.org_a, 'a-2026')
        self.cohort_b = _cohort(self.org_b, 'b-2026')
        self.cohort_a.programme = self.prog_a
        self.cohort_a.save(update_fields=['programme'])
        self.cohort_b.programme = self.prog_b
        self.cohort_b.save(update_fields=['programme'])

    def test_the_link_resolves_its_own_programme_even_though_both_are_open(self):
        self.assertEqual(services.resolve_open_cohort(programme_code='tenant-b-bursary'),
                         self.cohort_b)
        self.assertEqual(services.resolve_open_cohort(programme_code='tenant-a-bursary'),
                         self.cohort_a)

    def test_a_programme_with_no_open_round_reads_closed_not_ambiguous(self):
        self.cohort_b.is_open = False
        self.cohort_b.save(update_fields=['is_open'])
        self.assertIsNone(services.resolve_open_cohort(programme_code='tenant-b-bursary'))

    def test_an_unknown_programme_code_reads_closed(self):
        self.assertIsNone(services.resolve_open_cohort(programme_code='no-such-programme'))

    def test_an_INACTIVE_programme_reads_closed_even_with_an_open_cohort(self):
        self.prog_b.is_active = False
        self.prog_b.save(update_fields=['is_active'])
        self.assertIsNone(services.resolve_open_cohort(programme_code='tenant-b-bursary'))

    def test_two_open_intakes_of_the_SAME_programme_are_still_refused(self):
        """The link narrows to a programme, not to a round — so PF-1's shape can still occur
        one level down, and must still refuse rather than pick the newer year."""
        second = _cohort(self.org_b, 'b-2027', year=2027)
        second.programme = self.prog_b
        second.save(update_fields=['programme'])
        with self.assertRaises(services.AmbiguousOpenCohort):
            services.resolve_open_cohort(programme_code='tenant-b-bursary')

    def test_an_explicit_cohort_code_still_wins_over_the_programme(self):
        self.assertEqual(
            services.resolve_open_cohort('a-2026', 'tenant-b-bursary'), self.cohort_a,
        )


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestApplyLinkEndToEnd(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org_a, self.org_b = _org('tenant-a'), _org('tenant-b')
        for org, code, cohort_code in (
            (self.org_a, 'tenant-a-bursary', 'a-2026'),
            (self.org_b, 'tenant-b-bursary', 'b-2026'),
        ):
            prog = _programme(org, code)
            cohort = _cohort(org, cohort_code)
            cohort.programme = prog
            cohort.save(update_fields=['programme'])
        StudentProfile.objects.create(
            supabase_user_id='pf1-user', name='Test Student', nric='010101010101',
            contact_email='student@example.com',
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_make_token("pf1-user")}')

    def test_the_application_lands_in_the_organisation_whose_link_was_followed(self):
        resp = self.client.post(
            '/api/v1/scholarship/applications/',
            {'programme_code': 'tenant-b-bursary'}, format='json',
        )
        self.assertEqual(resp.status_code, 201)
        app = ScholarshipApplication.objects.get()
        self.assertEqual(app.owning_organisation_id, self.org_b.id)

    def test_the_routing_input_is_not_stored_on_the_row_or_the_intake_snapshot(self):
        """`programme_code` chose the cohort; the FK now records that answer. Keeping it would
        be a second, independently-mutable copy of tenancy — exactly what the model forbids."""
        self.client.post(
            '/api/v1/scholarship/applications/',
            {'programme_code': 'tenant-b-bursary'}, format='json',
        )
        app = ScholarshipApplication.objects.get()
        self.assertNotIn('programme_code', app.intake_snapshot or {})
        self.assertNotIn('cohort_code', app.intake_snapshot or {})

    def test_intake_status_answers_for_the_named_programme_only(self):
        body = self.client.get('/api/v1/scholarship/intake/?programme=tenant-b-bursary').json()
        self.assertEqual(body, {'open': True, 'cohort_name': 'Cohort b-2026'})

    def test_intake_status_hides_whether_an_unknown_programme_exists(self):
        """Public and unauthenticated — 'closed' rather than 404, or anyone could enumerate
        which organisations are on the platform."""
        self.assertEqual(
            self.client.get('/api/v1/scholarship/intake/?programme=nope').json(),
            {'open': False, 'cohort_name': ''},
        )
