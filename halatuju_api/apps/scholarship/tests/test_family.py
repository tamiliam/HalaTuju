"""Tests for the structured family roster (redesign 2026-06).

Covers the pure taxonomy/derivation module (`family.py`) + the derive-on-save
behaviour in `services.save_application_details` (the structured roster is the
INPUT; first_in_family + parents_occupation become OUTPUTS).
"""
from django.test import TestCase

from apps.courses.models import StudentProfile
from apps.scholarship import family
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort
from apps.scholarship.services import save_application_details


class FamilyTaxonomyTests(TestCase):
    def test_codes_unique_and_other_present(self):
        codes = [c for c, _ in family.PROFESSION_CHOICES]
        self.assertEqual(len(codes), len(set(codes)), 'duplicate profession code')
        self.assertIn('other', family.PROFESSION_CODES)
        # The B60-focused additions the owner asked for are present.
        for code in ('technician', 'tuition', 'caregiver', 'fnb', 'maintenance',
                     'storekeeper', 'hairdresser', 'factory', 'retail', 'cleaner', 'clerk'):
            self.assertIn(code, family.PROFESSION_CODES)

    def test_occupation_label(self):
        self.assertEqual(family.occupation_label('homemaker'), 'Homemaker')
        self.assertEqual(family.occupation_label('other', 'Puppeteer'), 'Puppeteer')
        self.assertEqual(family.occupation_label('other', ''), 'Other')
        self.assertEqual(family.occupation_label(''), '')

    def test_clean_other_members(self):
        raw = [
            {'role': 'brother', 'occupation': 'odd_jobs'},
            {'role': 'sister', 'occupation': 'other', 'occupation_other': 'Model'},
            {'role': 'cousin', 'occupation': 'gov'},          # bad role → dropped
            {'role': 'guardian', 'occupation': 'nope'},        # bad occupation → dropped
            'garbage',                                          # non-dict → dropped
        ]
        out = family.clean_other_members(raw)
        self.assertEqual(out, [
            {'role': 'brother', 'occupation': 'odd_jobs'},
            {'role': 'sister', 'occupation': 'other', 'occupation_other': 'Model'},
        ])
        self.assertEqual(family.clean_other_members('not a list'), [])
        # Cap is enforced.
        many = [{'role': 'brother', 'occupation': 'gov'}] * 10
        self.assertEqual(len(family.clean_other_members(many)), family.MAX_OTHER_MEMBERS)


class _AppBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='fam', name='B40', year=2026)

    def _app(self):
        profile = StudentProfile.objects.create(
            supabase_user_id=f'fam-{self.id()}', name='Priya Devi', nric='030101-14-1234')
        return ScholarshipApplication.objects.create(profile=profile, cohort=self.cohort)


class DeriveFirstInFamilyTests(_AppBase):
    def test_derived_true_when_no_tertiary_sibling(self):
        app = self._app()
        app.siblings_in_tertiary = 0
        self.assertTrue(family.derive_first_in_family(app))
        app.siblings_in_tertiary = None
        self.assertTrue(family.derive_first_in_family(app))

    def test_derived_false_when_a_sibling_in_tertiary(self):
        app = self._app()
        app.siblings_in_tertiary = 1
        self.assertFalse(family.derive_first_in_family(app))


class SaveDerivesLegacyColumnsTests(_AppBase):
    def test_structured_roster_derives_first_in_family_and_summary(self):
        app = self._app()
        save_application_details(app, {
            'father_name': 'MOHD RIZAL BIN ABDULLAH', 'father_occupation': 'self_employed',
            'mother_name': 'SITI AMINAH', 'mother_occupation': 'homemaker',
            'other_family_members': [{'role': 'brother', 'occupation': 'odd_jobs'}],
            'siblings_in_tertiary': 0, 'siblings_in_school': 2,
        })
        app.refresh_from_db()
        # first_in_family DERIVED from the (zero) tertiary count.
        self.assertTrue(app.first_in_family)
        # parents_occupation DERIVED as a summary of the roster.
        self.assertIn('Father: Self-employed / freelance', app.parents_occupation)
        self.assertIn('Mother: Homemaker', app.parents_occupation)
        self.assertIn('Brother: Odd jobs / daily wage', app.parents_occupation)
        # The member pool was cleaned + stored.
        self.assertEqual(app.other_family_members, [{'role': 'brother', 'occupation': 'odd_jobs'}])

    def test_tertiary_sibling_flips_first_in_family_off(self):
        app = self._app()
        save_application_details(app, {
            'father_occupation': 'driver', 'siblings_in_tertiary': 1})
        app.refresh_from_db()
        self.assertFalse(app.first_in_family)

    def test_earning_members_prefill(self):
        app = self._app()
        save_application_details(app, {
            'father_occupation': 'driver',          # earns
            'mother_occupation': 'homemaker',         # does NOT earn
            'other_family_members': [
                {'role': 'brother', 'occupation': 'odd_jobs'},     # earns
                {'role': 'sister', 'occupation': 'unemployed'},     # does NOT earn
            ],
        })
        app.refresh_from_db()
        self.assertEqual(family.earning_members(app), ['father', 'brother'])

    def test_grandfathered_free_text_untouched_without_roster(self):
        # No structured roster → the legacy free text / toggle are left as-is.
        app = self._app()
        save_application_details(app, {
            'parents_occupation': 'My dad drives a lorry.', 'first_in_family': True})
        app.refresh_from_db()
        self.assertEqual(app.parents_occupation, 'My dad drives a lorry.')
        self.assertTrue(app.first_in_family)
