"""M1 — "which application is this request about" stops being answered by position.

`_current_application()` was `.order_by('-submitted_at').first()`, with "latest wins" in its
docstring as though it were a rule. It was an assumption that held only because one cohort had
ever existed. Thirteen endpoints resolve through it — document sign-upload and listing, consent,
bank details, the Action Centre — so a student holding applications to two programmes uploads
their IC for programme B and it attaches to whichever they submitted most recently. Silently, and
into the wrong organisation's hands.

Same defect as PF-1 (`resolve_open_cohort`), one layer up. Same fix: refuse rather than guess.

Unreachable today — the unique constraint `(cohort, profile)` excludes only `expired`, so within
one cohort a student holds at most one non-expired application, and one cohort exists. These tests
therefore have to CREATE the second programme to reach the bug at all.
"""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerOrganisation, StudentProfile
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort
from apps.scholarship.tests.test_api import TEST_JWT_SECRET, _make_token
from apps.scholarship.views import AmbiguousApplication, _current_application

USER = 'm1-student'


def _cohort(code):
    org = PartnerOrganisation.objects.create(code=code, name=code.title())
    return ScholarshipCohort.objects.create(
        code=code, name=f'Cohort {code}', year=2026, owning_organisation=org,
        is_active=True, is_open=True,
    )


class TestOneLiveApplicationIsUnchanged(TestCase):
    """The promise that makes this shippable: today's single-application behaviour does not move."""

    def setUp(self):
        self.profile = StudentProfile.objects.create(supabase_user_id=USER, name='Test Student')
        self.app = ScholarshipApplication.objects.create(
            cohort=_cohort('a-2026'), profile=self.profile, status='profile_complete',
        )

    def test_the_single_live_application_resolves(self):
        self.assertEqual(_current_application(USER), self.app)

    def test_no_application_still_returns_None(self):
        self.assertIsNone(_current_application('nobody'))

    def test_a_finished_application_is_not_live(self):
        """`rejected` is outside the editable + funded sets, so it never resolves."""
        self.app.status = 'rejected'
        self.app.save(update_fields=['status'])
        self.assertIsNone(_current_application(USER))

    def test_an_expired_application_beside_a_live_one_is_not_ambiguous(self):
        """The restart case: an expired row stays as history and must not count as live —
        otherwise every student who restarted would be locked out by this change."""
        ScholarshipApplication.objects.create(
            cohort=_cohort('old-2025'), profile=self.profile, status='expired',
        )
        self.assertEqual(_current_application(USER), self.app)


class TestTwoLiveApplicationsAreRefused(TestCase):
    def setUp(self):
        self.profile = StudentProfile.objects.create(supabase_user_id=USER, name='Test Student')
        self.app_a = ScholarshipApplication.objects.create(
            cohort=_cohort('a-2026'), profile=self.profile, status='profile_complete',
        )
        self.app_b = ScholarshipApplication.objects.create(
            cohort=_cohort('b-2026'), profile=self.profile, status='shortlisted',
        )

    def test_it_refuses_instead_of_picking_the_latest(self):
        """Pre-fix this returned one of them — whichever sorted first by -submitted_at."""
        with self.assertRaises(AmbiguousApplication):
            _current_application(USER)

    def test_the_refusal_is_a_409_not_a_500(self):
        """It reaches the student through DRF's handler, so a call site that has never heard of
        this class still behaves correctly — which is the point of using APIException."""
        self.assertEqual(AmbiguousApplication.status_code, 409)
        self.assertEqual(AmbiguousApplication.default_code, 'application_ambiguous')

    def test_a_funded_application_counts_as_live_too(self):
        """The funded states are in scope precisely because a funded student keeps uploading."""
        self.app_a.status = 'active'
        self.app_a.save(update_fields=['status'])
        with self.assertRaises(AmbiguousApplication):
            _current_application(USER)

    def test_closing_one_of_them_resolves_it(self):
        self.app_b.status = 'rejected'
        self.app_b.save(update_fields=['status'])
        self.assertEqual(_current_application(USER), self.app_a)

    def test_another_students_applications_never_create_ambiguity(self):
        other = StudentProfile.objects.create(supabase_user_id='someone-else', name='Other')
        ScholarshipApplication.objects.create(
            cohort=_cohort('c-2026'), profile=other, status='profile_complete',
        )
        with self.assertRaises(AmbiguousApplication):
            _current_application(USER)          # still theirs, still two
        self.assertIsNotNone(_current_application('someone-else'))   # unaffected


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheEndpointsRefuseRatherThanMisattribute(TestCase):
    """Through the wire, because that is where a wrong answer becomes a misfiled document."""

    def setUp(self):
        self.client = APIClient()
        self.profile = StudentProfile.objects.create(
            supabase_user_id=USER, name='Test Student', nric='010101010101',
        )
        for code, st in (('a-2026', 'profile_complete'), ('b-2026', 'shortlisted')):
            ScholarshipApplication.objects.create(
                cohort=_cohort(code), profile=self.profile, status=st,
            )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_make_token(USER)}')

    def test_document_upload_refuses_rather_than_filing_under_the_wrong_programme(self):
        resp = self.client.post(
            '/api/v1/scholarship/documents/sign-upload/',
            {'doc_type': 'ic', 'filename': 'ic.jpg', 'content_type': 'image/jpeg'},
            format='json',
        )
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json().get('code'), 'application_ambiguous')
