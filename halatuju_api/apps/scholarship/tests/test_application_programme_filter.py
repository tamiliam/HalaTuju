"""The Applications list narrows to the gift the breadcrumb switcher is on.

The owner's item 3: the switcher moved the crumb and filtered nothing, so 143 people belonging to
one gift were listed under another gift's name. The narrowing is `?programme=<code>`, re-fenced
server-side on the caller's own organisation.

⚠ THE THREE CLAIMS THAT MATTER, and each has a test that fails without its line of code:
  1. NAMED  → only that gift's applications.
  2. OMITTED → every gift the caller may see. Blank is a real answer for a READ, not a missing one.
  3. UNKNOWN OR ANOTHER TENANT'S → **404**, never "show everything". Silently dropping a narrowing
     the caller asked for is the very defect this sprint fixes; and a cross-tenant code must not
     confirm that gift exists, which is why it is 404 and never 403.

⚠ IT IS A NARROWING, NEVER A FENCE. The organisation wall is `_org_scoped`, unchanged — a caller
who omits the parameter reaches exactly the rows the fence already allowed, and no client can widen
anything by sending one. The reviewer's assignment scope composes on top rather than being replaced.
"""
import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation, StudentProfile
from apps.scholarship.models import Programme, ScholarshipApplication, ScholarshipCohort

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
URL = '/api/v1/admin/scholarship/applications/'


def _token(uid):
    return jwt.encode(
        {'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
        TEST_JWT_SECRET, algorithm='HS256',
    )


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class ApplicationProgrammeFilterTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # ⚠ `PartnerOrganisation.code` is unique PLATFORM-WIDE and a migration seeds the real
        # BrightPath row, so a fixture must not reuse a live code. Prefixed, like test_org_fence.
        cls.org = PartnerOrganisation.objects.create(
            name='BrightPath', code='gs-brightpath', is_active=True)
        cls.other_org = PartnerOrganisation.objects.create(
            name='Inspire', code='gs-inspire', is_active=True)

        cls.flagship = Programme.objects.create(
            organisation=cls.org, code='bp-flagship', name_en='BrightPath Bursary')
        cls.second = Programme.objects.create(
            organisation=cls.org, code='bp-sabah', name_en='Test Programme')
        cls.foreign = Programme.objects.create(
            organisation=cls.other_org, code='inspire-one', name_en='Inspire Bursary')

        # ⚠ An application's organisation is copied from its COHORT's own owning_organisation,
        # not from programme.organisation — the fixture gotcha this suite would otherwise hit.
        cls.flagship_round = ScholarshipCohort.objects.create(
            code='bp-2026', name='BrightPath 2026', year=2026,
            owning_organisation=cls.org, programme=cls.flagship)
        cls.second_round = ScholarshipCohort.objects.create(
            code='sabah-2026', name='Test 2026', year=2026,
            owning_organisation=cls.org, programme=cls.second)

        cls.org_admin = PartnerAdmin.objects.create(
            supabase_user_id='org-admin', role='org_admin', is_active=True,
            name='Org Admin', email='org@example.com', owning_organisation=cls.org)
        cls.reviewer = PartnerAdmin.objects.create(
            supabase_user_id='reviewer', role='reviewer', is_active=True,
            name='Reviewer', email='rev@example.com', owning_organisation=cls.org)

        cls.flagship_apps = [cls._app(cls.flagship_round, i) for i in range(3)]
        cls.second_apps = [cls._app(cls.second_round, 10 + i) for i in range(2)]

    @classmethod
    def _app(cls, cohort, i):
        profile = StudentProfile.objects.create(
            supabase_user_id=f'student-{i:03d}', nric=f'{i:06d}-14-1234',
            name=f'Applicant {i:03d}')
        return ScholarshipApplication.objects.create(
            cohort=cohort, profile=profile, status='shortlisted', bucket='A')

    def _as(self, admin):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(admin.supabase_user_id)}')
        return client

    def _ids(self, response):
        return sorted(row['id'] for row in response.json()['applications'])

    # ── 1. named ─────────────────────────────────────────────────────────────────────────────
    def test_a_named_gift_lists_only_its_own_applicants(self):
        res = self._as(self.org_admin).get(f'{URL}?programme=bp-sabah')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self._ids(res), sorted(a.id for a in self.second_apps))
        self.assertEqual(res.json()['count'], 2)

    def test_the_other_gift_is_narrowed_too(self):
        res = self._as(self.org_admin).get(f'{URL}?programme=bp-flagship')
        self.assertEqual(self._ids(res), sorted(a.id for a in self.flagship_apps))

    # ── 2. omitted ───────────────────────────────────────────────────────────────────────────
    def test_omitting_the_gift_lists_every_gift_the_caller_may_see(self):
        """Blank is a real answer for a READ — several gifts and no choice shows all of them.

        Deliberately unlike the configuration screens, where a silent pick would EDIT the wrong
        gift and the honest response is to ask.
        """
        res = self._as(self.org_admin).get(URL)
        self.assertEqual(res.json()['count'], 5)

    def test_an_empty_programme_value_is_the_same_as_omitting_it(self):
        res = self._as(self.org_admin).get(f'{URL}?programme=')
        self.assertEqual(res.json()['count'], 5)

    # ── 3. refused ───────────────────────────────────────────────────────────────────────────
    def test_an_unknown_code_is_404_and_NOT_every_gift(self):
        """A narrowing that cannot be resolved must refuse, never widen.

        Falling back to "show everything" would put the wrong people under a named heading —
        which is the defect this whole sprint exists to fix.
        """
        res = self._as(self.org_admin).get(f'{URL}?programme=no-such-gift')
        self.assertEqual(res.status_code, 404)

    def test_another_tenants_gift_is_404_never_403_and_never_listed(self):
        res = self._as(self.org_admin).get(f'{URL}?programme=inspire-one')
        self.assertEqual(res.status_code, 404)

    # ── the fence and the assignment scope both still hold ───────────────────────────────────
    def test_a_reviewers_assignment_scope_composes_with_the_gift(self):
        """The gift NARROWS what the reviewer already sees; it never widens it."""
        mine = self.second_apps[0]
        mine.assigned_to = self.reviewer
        mine.save(update_fields=['assigned_to'])

        client = self._as(self.reviewer)
        self.assertEqual(self._ids(client.get(f'{URL}?programme=bp-sabah')), [mine.id])
        # The other gift holds none of theirs — narrowing cannot reveal an unassigned case.
        self.assertEqual(client.get(f'{URL}?programme=bp-flagship').json()['count'], 0)

    def test_the_filter_reaches_THROUGH_the_cohort_when_the_column_has_drifted(self):
        """`ScholarshipApplication.programme` is denormalised and SET ONCE at first save.

        A cohort moved between gifts therefore leaves its old applications pointing at the OLD
        gift, so filtering on the column alone would report a gift's own round as empty. The
        predicate mirrors `programme_delete_blocker`'s — do not narrow it to the column.
        """
        drifted = self.second_apps[0]
        # Force the drift the column can genuinely hold; .update() bypasses the set-once save().
        ScholarshipApplication.objects.filter(pk=drifted.pk).update(programme=self.flagship)

        res = self._as(self.org_admin).get(f'{URL}?programme=bp-sabah')
        self.assertIn(drifted.id, self._ids(res), 'its own round still holds this student')
