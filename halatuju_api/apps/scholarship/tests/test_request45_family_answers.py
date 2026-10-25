"""Request #45 — the cockpit shows the student's "About your family" answers, and the tick beside
the parent contact's name means that name MATCHES a read parent/guardian IC.

The fault on application 171: the IC on file was the father's, the contact name was the mother's,
and the tick showed anyway (it meant only "some parent IC was read"). `guardian_ic_name_match` is
computed on the server with `vision.name_match`, so these tests pin the shape the cockpit reads.
Every name here is invented.
"""
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship.models import ApplicantDocument
from apps.scholarship.serializers_admin_family import guardian_ic_name_match
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application,
)

FATHER = 'ARUNAN A/L KOVALAN'
MOTHER = 'MEENA A/P SELVAM'


def _doc(**kw):
    base = {'id': 1, 'doc_type': 'parent_ic', 'superseded_at': None, 'vision_name': FATHER,
            'vision_run_at': '2026-10-01T00:00:00Z', 'vision_error': ''}
    base.update(kw)
    return base


class TestGuardianIcNameMatch(TestCase):
    """The pure rule, on the serialised shapes it reads."""

    def test_app_171_shape_father_ic_mother_contact_is_no_match(self):
        self.assertEqual(guardian_ic_name_match([{'name': MOTHER}], [_doc()]), [])

    def test_the_contact_name_on_the_ic_matches(self):
        self.assertEqual(guardian_ic_name_match([{'name': FATHER}], [_doc(id=7)]), [7])

    def test_case_spacing_and_the_parentage_marker_are_tolerated(self):
        for typed in ('arunan a/l kovalan', 'Arunan  A / L  Kovalan', 'ARUNAN KOVALAN'):
            with self.subTest(typed=typed):
                self.assertEqual(guardian_ic_name_match([{'name': typed}], [_doc(id=3)]), [3])

    def test_a_partial_name_is_not_a_match(self):
        self.assertEqual(guardian_ic_name_match([{'name': 'ARUNAN'}], [_doc()]), [])

    def test_only_a_live_legibly_read_parent_ic_counts(self):
        contact = [{'name': FATHER}]
        for doc in (_doc(superseded_at='2026-10-02T00:00:00Z'), _doc(vision_error='timeout'),
                    _doc(vision_run_at=None), _doc(vision_name=''), _doc(doc_type='ic')):
            with self.subTest(doc=doc):
                self.assertEqual(guardian_ic_name_match(contact, [doc]), [])

    def test_no_contact_name_no_match(self):
        for guardians in ([], None, [{}], [{'name': '  '}], 'junk'):
            with self.subTest(guardians=guardians):
                self.assertEqual(guardian_ic_name_match(guardians, [_doc()]), [])

    def test_the_first_guardian_is_the_contact(self):
        self.assertEqual(
            guardian_ic_name_match([{'name': MOTHER}, {'name': FATHER}], [_doc()]), [])


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheDetailPayloadServesTheFamilyAnswers(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.app = make_application(
            'interviewing',
            income_declared={'mother': 900},
            income_nonearning={'father': {'reason': 'Factory closed', 'since': '2025-03'}},
        )
        cls.app.profile.guardians = [{'name': MOTHER, 'phone': '0123456789'}]
        cls.app.profile.save(update_fields=['guardians'])
        cls.ic = ApplicantDocument.objects.create(
            application=cls.app, doc_type='parent_ic', storage_path=f'{cls.app.id}/parent_ic/x',
            household_member='father', vision_name=FATHER,
            vision_run_at=timezone.now(), vision_error='')
        cls.admin = make_admin('org_admin', owning_org=cls.app.owning_organisation)

    def _payload(self):
        r = authed_client(self.admin).get(f'/api/v1/admin/scholarship/applications/{self.app.id}/')
        self.assertEqual(r.status_code, 200, r.content[:200])
        return r.json()

    def test_declared_and_nonearning_answers_are_served(self):
        data = self._payload()
        self.assertEqual(data['income_declared'], {'mother': 900})
        self.assertEqual(data['income_nonearning'],
                         {'father': {'reason': 'Factory closed', 'since': '2025-03'}})

    def test_father_ic_with_mother_contact_serves_no_match(self):
        """The regression: app 171's shape must not earn the tick."""
        self.assertEqual(self._payload()['guardian_ic_name_match'], [])

    def test_a_matching_ic_is_named_by_id(self):
        ApplicantDocument.objects.create(
            application=self.app, doc_type='parent_ic', storage_path=f'{self.app.id}/parent_ic/y',
            household_member='mother', vision_name=MOTHER,
            vision_run_at=timezone.now(), vision_error='')
        data = self._payload()
        mother_ic = [d['id'] for d in data['documents'] if d['vision_name'] == MOTHER]
        self.assertEqual(data['guardian_ic_name_match'], mother_ic)

    def test_existing_keys_are_untouched(self):
        data = self._payload()
        self.assertIn('programme', data)          # the gift mixin still runs
        self.assertEqual(data['guardians'][0]['name'], MOTHER)
