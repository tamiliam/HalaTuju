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


class FamilyCompletenessTests(_AppBase):
    """The structured roster is compulsory (`family_done`) — names exempt for an
    absent (deceased / no-contact) parent; both sibling counts must be answered."""

    def _fill(self, app, **over):
        data = dict(father_name='Aroon', father_occupation='driver',
                    mother_name='Komathi', mother_occupation='homemaker',
                    siblings_in_school=1, siblings_in_tertiary=0)
        data.update(over)
        save_application_details(app, data)
        app.refresh_from_db()

    def test_family_done_requires_full_roster(self):
        from apps.scholarship.services import application_completeness
        app = self._app()
        self.assertFalse(application_completeness(app)['family_done'])
        self._fill(app)
        self.assertTrue(application_completeness(app)['family_done'])

    def test_name_exempt_for_absent_parent(self):
        from apps.scholarship.services import application_completeness
        app = self._app()
        # Father passed away with no name → still done (name exempt for deceased).
        self._fill(app, father_name='', father_occupation='deceased')
        self.assertTrue(application_completeness(app)['family_done'])

    def test_missing_sibling_count_blocks(self):
        from apps.scholarship.services import application_completeness
        app = self._app()
        self._fill(app, siblings_in_tertiary=None)
        self.assertFalse(application_completeness(app)['family_done'])

    def test_consent_gate_blocks_on_incomplete_roster(self):
        from apps.scholarship.services import consent_blockers
        app = self._app()
        self.assertIn('family_incomplete', consent_blockers(app))
        self._fill(app)
        self.assertNotIn('family_incomplete', consent_blockers(app))

    def test_consent_blocks_on_results_slip_name_mismatch(self):
        from unittest.mock import patch
        from apps.scholarship.models import ApplicantDocument
        from apps.scholarship.services import consent_blockers
        app = self._app()
        ApplicantDocument.objects.create(application=app, doc_type='results_slip', storage_path='x/r')
        with patch('apps.scholarship.academic_engine._slip_name_status', return_value='mismatch'):
            self.assertIn('results_slip_name_mismatch', consent_blockers(app))
        with patch('apps.scholarship.academic_engine._slip_name_status', return_value='match'):
            self.assertNotIn('results_slip_name_mismatch', consent_blockers(app))

    def test_grandfathered_submitted_app_is_exempt(self):
        from django.utils import timezone
        from apps.scholarship.services import application_completeness
        app = self._app()
        # Already-submitted (profile_completed_at set) → grandfathered, no roster needed.
        app.profile_completed_at = timezone.now()
        app.save(update_fields=['profile_completed_at'])
        self.assertTrue(application_completeness(app)['family_done'])


class ConsentRedGateTests(TestCase):
    """document_red_blockers: ANY red ('Doesn't match' / STR rejected-stale) per-document
    check blocks consent. Reads the stored student_*_check verdicts (mocked here)."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='red', name='B40', year=2026)

    def _app_with_doc(self, doc_type):
        from apps.scholarship.models import ApplicantDocument
        profile = StudentProfile.objects.create(
            supabase_user_id=f'red-{self.id()}', name='X', nric='030101-14-1234')
        app = ScholarshipApplication.objects.create(profile=profile, cohort=self.cohort)
        ApplicantDocument.objects.create(application=app, doc_type=doc_type, storage_path='x')
        return app

    def test_results_slip_name_and_grades_mismatch_block(self):
        from unittest.mock import patch
        from apps.scholarship.services import document_red_blockers
        app = self._app_with_doc('results_slip')
        with patch('apps.scholarship.academic_engine.student_slip_check',
                   return_value={'name': 'mismatch', 'subjects': 'match', 'results': 'match'}):
            self.assertIn('results_slip_name_mismatch', document_red_blockers(app))
        with patch('apps.scholarship.academic_engine.student_slip_check',
                   return_value={'name': 'match', 'subjects': 'match', 'results': 'mismatch'}):
            self.assertIn('results_slip_grades_mismatch', document_red_blockers(app))

    def test_str_rejected_or_stale_blocks(self):
        from unittest.mock import patch
        from apps.scholarship.services import document_red_blockers
        app = self._app_with_doc('str')
        with patch('apps.scholarship.income_engine.student_str_check',
                   return_value={'name_status': 'match', 'nric_status': 'match', 'current_status': 'rejected'}):
            self.assertIn('income_document_mismatch', document_red_blockers(app))

    def test_bc_child_mismatch_blocks(self):
        from unittest.mock import patch
        from apps.scholarship.services import document_red_blockers
        app = self._app_with_doc('birth_certificate')
        with patch('apps.scholarship.income_engine.student_bc_check',
                   return_value={'child_status': 'mismatch', 'mother_status': 'match', 'father_status': 'match'}):
            self.assertIn('income_document_mismatch', document_red_blockers(app))

    def test_offer_pathway_clash_is_soft_not_gated(self):
        from unittest.mock import patch
        from apps.scholarship.services import document_red_blockers
        app = self._app_with_doc('offer_letter')
        # name/ic match, only the pathway clashes → SOFT, not gated.
        with patch('apps.scholarship.pathway_engine.student_offer_check',
                   return_value={'name': 'match', 'ic': 'match', 'pathway': 'mismatch'}):
            self.assertEqual(document_red_blockers(app), [])
        with patch('apps.scholarship.pathway_engine.student_offer_check',
                   return_value={'name': 'mismatch', 'ic': 'match', 'pathway': 'match'}):
            self.assertIn('offer_letter_mismatch', document_red_blockers(app))
