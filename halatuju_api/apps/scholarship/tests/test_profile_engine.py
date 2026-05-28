"""Tests for the AI sponsor-profile prompt builder (S5c rebuild, TD-060).

These exercise the *pure* prompt construction + language resolution — the Gemini
call itself is never made here. The key regression: `_build_prompt` must run
against the CURRENT (profile-canonical) data model without `AttributeError`.
"""
from django.test import TestCase

from apps.courses.models import StudentProfile
from apps.scholarship.models import (
    FundingNeed, Referee, ScholarshipApplication, ScholarshipCohort,
)
from apps.scholarship.profile_engine import (
    DEFAULT_LANGUAGE, _build_prompt, _resolve_language, generate_sponsor_profile,
)


class TestProfilePrompt(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.profile = StudentProfile.objects.create(
            supabase_user_id='pe-1', nric='030101-14-1234', name='Priya', school='SMK Taman',
            exam_type='SPM', grades={f'sub{i}': 'A' for i in range(7)},
            household_income=1800, household_size=6, receives_str=True, receives_jkm=False,
        )
        cls.app = ScholarshipApplication.objects.create(
            cohort=cls.cohort, profile=cls.profile, status='shortlisted', locale='ms',
            aspirations='Saya mahu menjadi akauntan',  # Malay narrative
            plans='Belajar rajin setiap hari',
            family_context='என் தந்தை ஒரு லாரி ஓட்டுநர்',  # Tamil narrative
            daily_life='I help at my family stall after school',  # English narrative
            first_in_family=True, parents_occupation='Lorry driver', siblings_studying=True,
            field_of_study='Accounting', pathways_considered=['matriculation', 'stpm'],
        )
        FundingNeed.objects.create(
            application=cls.app, categories=['living', 'transport'],
            funding_note='Saya akan cuba PTPTN juga', programme_months=12,
        )
        Referee.objects.create(application=cls.app, name='Cikgu Devi', role='teacher')

    def test_build_prompt_runs_on_current_model(self):
        """TD-060 regression: no AttributeError against the profile-canonical model."""
        prompt = _build_prompt(self.app)
        self.assertIsInstance(prompt, str)
        self.assertGreater(len(prompt), 200)

    def test_prompt_includes_current_fields(self):
        prompt = _build_prompt(self.app)
        self.assertIn('Priya', prompt)
        self.assertIn('SMK Taman', prompt)
        self.assertIn('SPM', prompt)
        self.assertIn('7', prompt)               # SPM A-count from profile.grades
        self.assertIn('1800', prompt)            # household income from the profile
        self.assertIn('Accounting', prompt)      # pathway from field_of_study
        self.assertIn('living, transport', prompt)  # funding categories, not a total
        self.assertIn('Cikgu Devi', prompt)      # referee

    def test_prompt_includes_story_narrative(self):
        prompt = _build_prompt(self.app)
        self.assertIn('Saya mahu menjadi akauntan', prompt)   # Malay aspirations
        self.assertIn('என் தந்தை ஒரு லாரி ஓட்டுநர்', prompt)  # Tamil family context
        self.assertIn('Lorry driver', prompt)

    def test_prompt_has_no_dead_total(self):
        """The dead FundingNeed `total` must not appear (TD-059)."""
        prompt = _build_prompt(self.app)
        self.assertNotIn('RM0 total', prompt)
        self.assertNotIn('total', prompt.lower().split('funding need')[0])

    def test_prompt_language_instructions(self):
        prompt = _build_prompt(self.app, target_language='Malay (Bahasa Melayu)')
        self.assertIn('Malay, English, or Tamil', prompt)            # multilingual input
        self.assertIn('Write the FINAL profile in Malay', prompt)    # target-language output

    def test_resolve_language(self):
        self.assertEqual(_resolve_language(self.app, 'en'), 'English')
        self.assertEqual(_resolve_language(self.app, 'ms'), 'Malay (Bahasa Melayu)')
        # app.locale is 'ms' → defaults to Malay when no explicit language
        self.assertEqual(_resolve_language(self.app, None), 'Malay (Bahasa Melayu)')
        # an unknown locale falls back to English
        self.app.locale = 'zz'
        self.assertEqual(_resolve_language(self.app, None), DEFAULT_LANGUAGE)

    def test_generate_without_api_key_is_graceful(self):
        """No API key → error dict, never a 500 from the (now-current) builder."""
        with self.settings(GEMINI_API_KEY=''):
            result = generate_sponsor_profile(self.app)
        self.assertIn('error', result)

    def test_build_prompt_handles_missing_funding_and_referees(self):
        app2 = ScholarshipApplication.objects.create(
            cohort=ScholarshipCohort.objects.create(code='c2', name='B40-2', year=2027),
            profile=self.profile, status='shortlisted',
        )
        prompt = _build_prompt(app2)
        self.assertIn('none provided', prompt)   # referees
        self.assertIn('not provided', prompt)     # funding categories/note
