"""S-ASSIGN part three — which gifts list a SOURCE, and which gift a reviewer covers as the
assignment dropdown sees it (2026-09-04; the source half rewritten 2026-10-08).

Two narrow claims, both about a NARROWING rather than a fence:

1. **Which gifts list a source records the organisation's choice — and today it reaches no
   student.** Since 2026-10-08 each gift chooses its own sources (``ProgrammeReferralSource``,
   set in the gift's Configuration; the single ``PartnerOrganisation.programme`` FK is
   deprecated). The apply form's referring-organisation list is still the hard-coded
   ``REFERRING_ORG_OPTIONS`` constant in ``lib/scholarship.ts`` until Sprint 2 wires it, so
   ``test_setting_a_gift_does_NOT_narrow_the_student_form_yet`` pins that honestly rather than
   letting a later reader assume the form is filtered. The endpoint and seed tests are in
   ``test_gift_sources.py``.

2. **A reviewer's gift travels on the assignment payload the way `paused` does** — flagged,
   never filtered out. Dropping anybody from that list reproduces bug #66, because the cockpit
   unions the current assignee in from it. ⚠ NULL MEANS EVERY GIFT there, with no backfill, so
   a blank must read as an answer, never as a missing value.
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


class TestWhichGiftsListASource(_Base):
    def test_a_gift_switching_a_source_on_is_counted_on_the_sources_page(self):
        from apps.scholarship.models import ProgrammeReferralSource
        ProgrammeReferralSource.objects.create(programme=self.sabah, source=self.source)
        self._auth('gs-oa')
        row = {s['code']: s for s in self.client.get(SOURCES).json()['sources']}['smc']
        self.assertEqual((row['gift_count'], row['gift_total']), (1, 2))
        self.assertNotIn('programme_id', row)

    def test_the_retired_single_gift_field_is_refused(self):
        self._auth('gs-oa')
        r = self.client.patch(f'{SOURCES}{self.source.id}/', {'programme_id': self.sabah.id},
                              format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.source.refresh_from_db()
        self.assertIsNone(self.source.programme_id)

    def test_setting_a_gift_does_NOT_narrow_the_student_form_yet(self):
        """⚠ AN HONEST LIMIT, PINNED SO NOBODY ASSUMES OTHERWISE (rewritten 2026-10-08).

        Each gift now chooses its sources (`ProgrammeReferralSource`, the gift's Configuration),
        but the student's referring-organisation list is still the hard-coded
        `REFERRING_ORG_OPTIONS` constant in `lib/scholarship.ts`, and the student intake reads
        neither the links nor `show_in_apply`. Switching a source on for a gift changes what an
        ADMIN sees and nothing a visitor sees. Per-gift sources Sprint 2 wires the form to the
        links; this test is what should fail (and be deleted with TD-230) on that day.
        """
        from apps.scholarship import views as student_views
        from apps.scholarship.models import ProgrammeReferralSource
        from apps.scholarship.services import intake
        ProgrammeReferralSource.objects.create(programme=self.sabah, source=self.source)
        for module, anchor in ((student_views, 'class ScholarshipIntakeView'),
                               (intake, 'def create_application')):
            source = open(module.__file__, encoding='utf-8').read()
            # The positive half: this IS the file that would read them (a negative assertion goes
            # green when its subject leaves the file it reads).
            self.assertIn(anchor, source, module.__file__)
            for marker in ('show_in_apply', 'ProgrammeReferralSource', 'gift_sources',
                           'referral_source_links'):
                self.assertNotIn(marker, source,
                                 f'{module.__name__} now reads `{marker}` — rewrite this test, '
                                 'the note on `_source_dict` and TD-230, which say it does not')


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
