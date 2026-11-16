"""Request #71 - change a gift programme's name (analysis 165, 2026-11-16).

The PATCH that changes a gift's short code also takes the three names. These tests pin the rename as
a feature: same gate as the code change, English required, Malay and Tamil allowed blank, the cap of
the model, the fence, and that neither the code nor the apply link moves.
"""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.scholarship import surface_gates
from apps.scholarship.models import Programme, ProgrammeCodeAlias
from apps.scholarship.tests.factories import TEST_JWT_SECRET, auth_token as _make_token

PROGRAMMES = '/api/v1/admin/scholarship/programmes/'


def _admin(uid, org, role='org_admin'):
    return PartnerAdmin.objects.create(
        supabase_user_id=uid, email=f'{uid}@example.com', name=uid, role=role,
        is_active=True, owning_organisation=org)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   FRONTEND_URL='https://halatuju.xyz')
class TestChangeTheName(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org_a = PartnerOrganisation.objects.create(code='r71-a', name='A', is_active=True)
        cls.org_b = PartnerOrganisation.objects.create(code='r71-b', name='B', is_active=True)
        cls.prog = Programme.objects.create(
            organisation=cls.org_a, code='r71-gift', name_en='Old Name',
            name_ms='Nama Lama', name_ta='', is_active=True)
        cls.other = Programme.objects.create(
            organisation=cls.org_b, code='r71-other', name_en='Other', is_active=True)
        cls.admin = _admin('r71-admin', cls.org_a)
        cls.url = f'{PROGRAMMES}{cls.prog.id}/'

    def setUp(self):
        self.client = APIClient()

    def _patch(self, admin, body, url=None):
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {_make_token(admin.supabase_user_id)}')
        return self.client.patch(url or self.url, body, format='json')

    def test_the_names_are_saved_trimmed_and_the_row_served_back(self):
        r = self._patch(self.admin, {'name_en': '  New Name ', 'name_ms': ' Nama Baharu ',
                                     'name_ta': ' புதிய '})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['name_en'], 'New Name')
        self.prog.refresh_from_db()
        self.assertEqual((self.prog.name_en, self.prog.name_ms, self.prog.name_ta),
                         ('New Name', 'Nama Baharu', 'புதிய'))

    def test_english_is_required(self):
        for blank in ('', '   ', None):
            r = self._patch(self.admin, {'name_en': blank})
            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.data['code'], 'name_required')
        self.prog.refresh_from_db()
        self.assertEqual(self.prog.name_en, 'Old Name')

    def test_blank_malay_and_tamil_are_allowed_and_stored_blank(self):
        r = self._patch(self.admin, {'name_en': 'Fresh', 'name_ms': '', 'name_ta': '  '})
        self.assertEqual(r.status_code, 200)
        self.prog.refresh_from_db()
        self.assertEqual((self.prog.name_ms, self.prog.name_ta), ('', ''))

    def test_a_name_over_the_models_cap_is_refused_with_a_code(self):
        for f in ('name_en', 'name_ms', 'name_ta'):
            r = self._patch(self.admin, {'name_en': 'Fine', f: 'x' * 201})
            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.data['code'], 'name_too_long')
        r = self._patch(self.admin, {'name_en': 'x' * 200})
        self.assertEqual(r.status_code, 200)

    def test_a_refused_name_leaves_a_code_change_in_the_same_patch_unsaved(self):
        # The code saves at once with its alias, so the names must be checked first.
        r = self._patch(self.admin, {'code': 'r71-moved', 'name_en': 'x' * 201})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'name_too_long')
        self.prog.refresh_from_db()
        self.assertEqual(self.prog.code, 'r71-gift')
        self.assertFalse(ProgrammeCodeAlias.objects.filter(programme=self.prog).exists())

    def test_the_code_the_link_and_the_aliases_do_not_move(self):
        before = self._patch(self.admin, {}).data['apply_url']
        r = self._patch(self.admin, {'name_en': 'Renamed'})
        self.assertEqual(r.data['code'], 'r71-gift')
        self.assertEqual(r.data['apply_url'], before)
        self.prog.refresh_from_db()
        self.assertEqual(self.prog.code, 'r71-gift')
        self.assertFalse(ProgrammeCodeAlias.objects.filter(programme=self.prog).exists())

    def test_another_organisations_gift_is_404_and_untouched(self):
        r = self._patch(self.admin, {'name_en': 'Hijack'}, url=f'{PROGRAMMES}{self.other.id}/')
        self.assertEqual(r.status_code, 404)
        self.other.refresh_from_db()
        self.assertEqual(self.other.name_en, 'Other')

    def test_permission_matrix_matches_the_code_change_gate(self):
        """Keys decide, not role labels: whoever may change the short code may change the name, and
        nobody else. A refusal changes nothing."""
        for role in ('org_admin', 'super', 'admin', 'reviewer', 'qc', 'finance', 'partner'):
            org = None if role == 'super' else self.org_a
            who = _admin(f'r71-x-{role}', org, role=role)
            may = surface_gates.may_edit_programmes(who)
            name = self._patch(who, {'name_en': f'By {role}'})
            code = self._patch(who, {'code': 'r71-by-' + role.replace('_', '')})
            self.assertEqual(name.status_code, code.status_code, role)
            self.assertEqual(name.status_code, 200 if may else 403, role)
            if not may:
                self.prog.refresh_from_db()
                self.assertNotEqual(self.prog.name_en, f'By {role}')
        self.assertTrue(surface_gates.may_edit_programmes(self.admin))
