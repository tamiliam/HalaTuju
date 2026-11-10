"""Audit A3.7 pins: the serializers and the courses models keep their public face through the split.

Written BEFORE the split and passing on the unsplit code (`serializers.py`, `serializers_admin.py`,
`courses/models.py`), then left untouched: the same file must pass on the packages. Behaviour is
kept, so what is pinned is only what a caller can see:

* every name the three modules exposed still resolves from the old import path;
* every serializer class declares the same fields in the same order (the API contract);
* a few made-up objects serialise to the same shapes, and bad input gives the same errors;
* every courses model keeps its label, table, ordering and field order (the migration state).

`a37_pins.json` is the snapshot taken from the unsplit code.
"""
import importlib
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

from django.apps import apps
from django.test import SimpleTestCase, TestCase
from rest_framework import serializers as drf

_PINS = json.loads(Path(__file__).with_name('a37_pins.json').read_text(encoding='utf-8'))


class TestOldNamesStillResolve(SimpleTestCase):
    def _check(self, modname, names):
        mod = importlib.import_module(modname)
        for name in names:
            with self.subTest(name=name):
                self.assertTrue(hasattr(mod, name), f'{modname}.{name} no longer resolves')

    def test_scholarship_serializers(self):
        self._check('apps.scholarship.serializers', _PINS['apps.scholarship.serializers']['names'])

    def test_scholarship_serializers_admin(self):
        self._check('apps.scholarship.serializers_admin', _PINS['apps.scholarship.serializers_admin']['names'])

    def test_courses_models(self):
        self._check('apps.courses.models', _PINS['courses.models']['names'])

    def test_the_identity_the_tests_lean_on(self):
        from apps.courses import public
        from apps.scholarship import serializers_admin
        self.assertIs(serializers_admin.held_qualification, public.results_held)

    def test_partneradmin_reexport_is_the_staff_module_class(self):
        from apps.courses import models, models_staff
        self.assertIs(models.PartnerAdmin, models_staff.PartnerAdmin)
        self.assertIs(models.ReviewerGift, models_staff.ReviewerGift)


class TestSerializerFieldOrder(SimpleTestCase):
    def _check(self, modname):
        mod = importlib.import_module(modname)
        pinned = _PINS[modname]['fields']
        for name, fields in pinned.items():
            with self.subTest(serializer=name):
                self.assertEqual(list(getattr(mod, name)().fields.keys()), fields)

    def test_scholarship_serializers(self):
        self._check('apps.scholarship.serializers')

    def test_scholarship_serializers_admin(self):
        self._check('apps.scholarship.serializers_admin')

    def test_no_serializer_class_is_missing_from_the_pin(self):
        # a serializer the split dropped, or one added without a pin, shows here
        for modname in ('apps.scholarship.serializers', 'apps.scholarship.serializers_admin'):
            mod = importlib.import_module(modname)
            found = {n for n, c in inspect.getmembers(mod, inspect.isclass)
                     if issubclass(c, drf.BaseSerializer) and (c.__module__ == modname or c.__module__.startswith(modname + '.'))}
            self.assertEqual(found, set(_PINS[modname]['fields']), modname)


class TestCoursesModelsKeepTheirShape(SimpleTestCase):
    def test_every_model_keeps_label_table_ordering_and_field_order(self):
        pinned = _PINS['courses.models']['models']
        live = {m.__name__: m for m in apps.get_app_config('courses').get_models()}
        self.assertEqual(sorted(live), sorted(pinned))
        for name, want in pinned.items():
            m = live[name]
            with self.subTest(model=name):
                self.assertEqual(m._meta.label, want['label'])
                self.assertEqual(m._meta.db_table, want['table'])
                self.assertEqual(list(m._meta.ordering), want['ordering'])
                self.assertEqual([f.name for f in m._meta.get_fields()], want['fields'])


class TestMadeUpObjectsSerialiseTheSame(SimpleTestCase):
    def test_funding_need_shape(self):
        from apps.scholarship.models import FundingNeed
        from apps.scholarship.serializers import FundingNeedSerializer
        data = FundingNeedSerializer(FundingNeed(categories=['tuition'], funding_note='n', programme_months=12)).data
        self.assertEqual(list(data), ['categories', 'funding_note', 'programme_months'])
        self.assertEqual(data['categories'], ['tuition'])
        self.assertEqual(data['programme_months'], 12)

    def test_funding_note_ceiling(self):
        from apps.scholarship.serializers import STORY_TEXT_MAX, FundingNeedSerializer
        s = FundingNeedSerializer(data={'funding_note': 'x' * (STORY_TEXT_MAX + 1)})
        self.assertFalse(s.is_valid())
        self.assertIn('funding_note', s.errors)

    def test_income_route_switch_errors(self):
        from apps.scholarship.serializers import IncomeRouteSwitchSerializer as S
        s = S(data={'income_route': 'str'})
        self.assertFalse(s.is_valid())
        self.assertEqual(list(s.errors), ['income_earner'])
        s = S(data={'income_route': 'salary', 'income_working_members': []})
        self.assertFalse(s.is_valid())
        self.assertEqual(list(s.errors), ['income_working_members'])
        s = S(data={'income_route': 'salary', 'income_working_members': ['father', 'father']})
        self.assertFalse(s.is_valid())
        self.assertIn('Duplicate', str(s.errors['income_working_members']))
        s = S(data={'income_route': 'str', 'income_earner': 'mother'})
        self.assertTrue(s.is_valid())
        self.assertEqual(dict(s.validated_data),
                         {'income_route': 'str', 'income_earner': 'mother', 'income_working_members': []})

    def test_bank_account_number_floor(self):
        from apps.scholarship.serializers import BankAccountConfirmSerializer as S
        s = S(data={'bank_name': 'B', 'account_number': '12-3', 'account_holder': 'H'})
        self.assertFalse(s.is_valid())
        self.assertEqual(str(s.errors['account_number'][0]), 'account_number_invalid')
        s = S(data={'bank_name': 'B', 'account_number': ' 1234 5678 ', 'account_holder': 'H'})
        self.assertTrue(s.is_valid())
        self.assertEqual(s.validated_data['account_number'], '1234 5678')

    def test_document_create_defaults_and_errors(self):
        from apps.scholarship.serializers import DocumentCreateSerializer as S
        s = S(data={'doc_type': 'not_a_type', 'storage_path': ''})
        self.assertFalse(s.is_valid())
        self.assertEqual(sorted(s.errors), ['doc_type', 'storage_path'])
        s = S(data={'doc_type': 'parent_ic', 'storage_path': 'a/b.pdf'})
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(dict(s.validated_data), {
            'doc_type': 'parent_ic', 'household_member': '', 'request_code': '',
            'storage_path': 'a/b.pdf', 'original_filename': '', 'content_type': '', 'size': 0})

    def test_consent_create_relationship_check(self):
        from apps.scholarship.serializers import ConsentCreateSerializer as S
        s = S(data={'granted_by': 'guardian', 'guardian_relationship': 'cousin-twice-removed'})
        self.assertFalse(s.is_valid())
        self.assertIn('guardian_relationship', s.errors)
        s = S(data={})
        self.assertTrue(s.is_valid())
        self.assertEqual(dict(s.validated_data), {
            'consent_type': 'share_with_sponsors', 'locale': 'en', 'granted_by': 'self',
            'guardian_name': '', 'guardian_relationship': '', 'guardian_nric': ''})

    def test_reviewer_profile_graduation_year(self):
        from apps.scholarship.serializers_admin import ReviewerProfileSerializer as S
        s = S(data={'graduation_year': 1900}, partial=True)
        self.assertFalse(s.is_valid())
        self.assertEqual(str(s.errors['graduation_year'][0]), 'Enter a valid graduation year.')

    def test_reviewer_profile_read_only_fields(self):
        from apps.scholarship.serializers_admin import ReviewerProfileSerializer as S
        ro = [n for n, f in S().fields.items() if f.read_only]
        self.assertEqual(ro, ['phone', 'share_phone_with_students'])

    def test_admin_name_by_email_blank_is_empty(self):
        from apps.scholarship.serializers_admin import _admin_name_by_email
        self.assertEqual(_admin_name_by_email(''), '')
        self.assertEqual(_admin_name_by_email(None), '')

    def test_full_name_prefers_signature_and_upper_cases(self):
        from apps.scholarship.serializers_admin import _full_name
        app = SimpleNamespace(declaration_name='sharmila a/p sanggar', profile=SimpleNamespace(name='Sharmila 1204'))
        self.assertEqual(_full_name(app), 'SHARMILA A/P SANGGAR')
        app = SimpleNamespace(declaration_name='', profile=SimpleNamespace(name='ravi'))
        self.assertEqual(_full_name(app), 'RAVI')


class TestTenantsReadsThePartnerAdminTable(TestCase):
    """`PartnerOrganisationQuerySet.tenants` names `PartnerAdmin`, which lives in `models_staff`
    and used to be a module-level name of `courses/models.py`. It must still resolve after the
    split (added with the split commit; passes on the unsplit code as well)."""

    def test_tenants_runs_and_keeps_an_org_with_an_org_admin(self):
        from apps.courses.models import PartnerAdmin, PartnerOrganisation
        before = set(PartnerOrganisation.objects.tenants().values_list('pk', flat=True))
        org = PartnerOrganisation.objects.create(code='a37-org', name='A37 Org')
        self.assertNotIn(org.pk, set(PartnerOrganisation.objects.tenants().values_list('pk', flat=True)))
        PartnerAdmin.objects.create(supabase_user_id='a37-u', email='a37@example.test', name='A',
                                    role='org_admin', owning_organisation=org, is_active=True)
        after = set(PartnerOrganisation.objects.tenants().values_list('pk', flat=True))
        self.assertEqual(after, before | {org.pk})
