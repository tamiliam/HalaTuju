"""S-ASSIGN part three — which gift a SOURCE appears under, and which gift a reviewer covers
as the assignment dropdown sees it (2026-09-04).

Two narrow claims, both about a NARROWING rather than a fence, and both with the same
permissive default:

1. **A source's gift records which apply form lists it — and today it reaches no student.**
   The apply form's referring-organisation list is still the hard-coded
   ``REFERRING_ORG_OPTIONS`` constant in ``lib/scholarship.ts``; nothing on the student side
   reads ``show_in_apply``, let alone the gift beneath it. So this column is intent, and
   ``test_setting_a_gift_does_NOT_narrow_the_student_form_yet`` pins that honestly rather than
   letting a later reader assume the form is filtered.

2. **A reviewer's gift travels on the assignment payload the way `paused` does** — flagged,
   never filtered out. Dropping anybody from that list reproduces bug #66, because the cockpit
   unions the current assignee in from it.

⚠ NULL MEANS EVERY GIFT on both. There is NO backfill on either column — all seven live
referral organisations and all 17 org-scoped staff carry NULL — so a blank must read as an
answer, never as a missing value.
"""
import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.scholarship.models import Programme

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
SOURCES = '/api/v1/admin/scholarship/sources/'
ASSIGNABLE = '/api/v1/admin/scholarship/assignable-admins/'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='gs', name='Gift Scope Org')
        cls.other = PartnerOrganisation.objects.create(code='gs2', name='Other Org')
        cls.flagship = Programme.objects.create(
            organisation=cls.org, code='gs-flag', name_en='Flagship Bursary')
        cls.sabah = Programme.objects.create(
            organisation=cls.org, code='gs-sabah', name_en='Sabah Bursary')
        cls.foreign_gift = Programme.objects.create(
            organisation=cls.other, code='gs-x', name_en='Another Tenant Gift')

        # The referral source. ⚠ A referral organisation is an ATTRIBUTION relationship and is
        # NOT the tenant that runs a gift — the two live in the same table, which is exactly why
        # the model docstrings say so twice.
        cls.source = PartnerOrganisation.objects.create(
            code='smc', name='SMC', show_in_apply=True)

        cls.oa = PartnerAdmin.objects.create(
            supabase_user_id='gs-oa', role='org_admin', is_active=True,
            owning_organisation=cls.org, name='Dina', email='dina@gs.test')
        cls.reviewer = PartnerAdmin.objects.create(
            supabase_user_id='gs-r1', role='reviewer', is_active=True,
            owning_organisation=cls.org, name='Anand', email='anand@gs.test')

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')


class TestWhichGiftListsASource(_Base):
    def _patch(self, **body):
        return self.client.patch(f'{SOURCES}{self.source.id}/', body, format='json')

    def test_a_source_with_no_gift_reads_as_EVERY_gift(self):
        self._auth('gs-oa')
        row = {s['code']: s for s in self.client.get(SOURCES).json()['sources']}['smc']
        self.assertIsNone(row['programme_id'])
        self.assertEqual(row['programme_name'], '')

    def test_it_records_the_gift(self):
        self._auth('gs-oa')
        r = self._patch(programme_id=self.sabah.id)
        self.assertEqual(r.status_code, 200, r.content)
        self.source.refresh_from_db()
        self.assertEqual(self.source.programme_id, self.sabah.id)

    def test_clearing_it_means_EVERY_gift(self):
        self._auth('gs-oa')
        self._patch(programme_id=self.sabah.id)
        r = self._patch(programme_id=None)
        self.assertEqual(r.status_code, 200, r.content)
        self.source.refresh_from_db()
        self.assertIsNone(self.source.programme_id)

    def test_another_tenants_gift_is_refused(self):
        """A tenant must not be able to list a source on somebody else's apply form."""
        self._auth('gs-oa')
        self.assertEqual(self._patch(programme_id=self.foreign_gift.id).status_code, 404)
        self.source.refresh_from_db()
        self.assertIsNone(self.source.programme_id)

    def test_omitting_the_field_leaves_it_alone(self):
        """The PATCH is field-by-field: editing a phone number must not clear the gift."""
        self._auth('gs-oa')
        self._patch(programme_id=self.sabah.id)
        self._patch(phone='012-345 6789')
        self.source.refresh_from_db()
        self.assertEqual(self.source.programme_id, self.sabah.id)

    def test_the_choices_are_the_callers_own_ACTIVE_gifts(self):
        """ACTIVE only, unlike the reviewer and sponsor pickers: this narrows which apply FORM
        lists the source, and a form that is not open lists nothing."""
        self.sabah.is_active = False
        self.sabah.save(update_fields=['is_active'])
        self._auth('gs-oa')
        codes = {p['code'] for p in self.client.get(SOURCES).json()['programmes']}
        self.assertEqual(codes, {'gs-flag'})

    def test_setting_a_gift_does_NOT_narrow_the_student_form_yet(self):
        """⚠ AN HONEST LIMIT, PINNED SO NOBODY ASSUMES OTHERWISE.

        The student's referring-organisation list is the hard-coded `REFERRING_ORG_OPTIONS`
        constant in `lib/scholarship.ts`. Nothing student-facing reads `show_in_apply`, so
        nothing reads the gift beneath it either — setting this changes what an ADMIN sees and
        nothing a visitor sees. Wiring the form to the registry is its own change, and this test
        is what should fail (and be rewritten) on the day it happens.
        """
        from apps.scholarship import views as student_views
        self._auth('gs-oa')
        self._patch(programme_id=self.sabah.id)
        source = open(student_views.__file__, encoding='utf-8').read()
        self.assertNotIn('show_in_apply', source,
                         'the student views now read the registry — rewrite this test and the '
                         'note on `_source_dict`, which says they do not')


class TestTheAssignmentDropdownSeesTheGift(_Base):
    def test_it_carries_the_gift_so_the_picker_can_grey_a_mismatch(self):
        self.reviewer.programme = self.sabah
        self.reviewer.save(update_fields=['programme'])
        self._auth('gs-oa')
        rows = {a['name']: a for a in self.client.get(ASSIGNABLE).json()['admins']}
        self.assertEqual(rows['Anand']['programme_id'], self.sabah.id)
        self.assertEqual(rows['Anand']['programme_name'], 'Sabah Bursary')

    def test_a_reviewer_on_another_gift_is_STILL_LISTED(self):
        """⚠ FLAGGED, NEVER FILTERED — the same rule as `paused`, and for the same reason: the
        cockpit unions the CURRENT assignee in from this list, so dropping anybody makes their
        case read "Unassigned" (bug #66). The screen greys the row instead."""
        self.reviewer.programme = self.sabah
        self.reviewer.save(update_fields=['programme'])
        self._auth('gs-oa')
        names = [a['name'] for a in self.client.get(ASSIGNABLE).json()['admins']]
        self.assertIn('Anand', names)

    def test_a_reviewer_with_no_gift_reads_as_EVERY_gift(self):
        self._auth('gs-oa')
        rows = {a['name']: a for a in self.client.get(ASSIGNABLE).json()['admins']}
        self.assertIsNone(rows['Anand']['programme_id'])
        self.assertEqual(rows['Anand']['programme_name'], '')
