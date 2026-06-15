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
    DEFAULT_LANGUAGE, _DO_NOT_CLAIM, _build_prompt, _resolve_language,
    generate_sponsor_profile,
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
            first_in_family=True, parents_occupation='Lorry driver', siblings_studying_count=2,
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
        self.assertIn('SMK Taman', prompt)       # school is allowed under the redaction policy
        self.assertIn('SPM', prompt)
        self.assertIn('Merit score', prompt)     # merit is now fed
        self.assertIn('1800', prompt)            # household income from the profile
        self.assertIn('Accounting', prompt)      # pathway from field_of_study
        self.assertIn('living, transport', prompt)  # funding categories, not a total

    def test_prompt_redacts_pii_and_is_narrative(self):
        prompt = _build_prompt(self.app)
        # Single PII-redaction policy: refer to the student by alias, never the name.
        self.assertNotIn('Priya', prompt)            # the name must NOT be in the prompt
        self.assertIn('alias', prompt.lower())
        self.assertIn('NEVER include', prompt)       # the redaction instruction
        # Narrative style, not the old headed sections.
        self.assertIn('three short paragraphs', prompt)
        self.assertNotIn('## Background', prompt)

    def test_prompt_includes_answered_queries(self):
        from apps.scholarship.models import ResolutionItem
        ResolutionItem.objects.create(
            application=self.app, source='check2', code='utility_holder_unknown',
            fact='income', kind='clarify', status='resolved',
            resolution_text="The bill is in my brother's name.")
        prompt = _build_prompt(self.app)
        self.assertIn("The bill is in my brother's name.", prompt)

    def test_prompt_includes_story_narrative(self):
        prompt = _build_prompt(self.app)
        self.assertIn('Saya mahu menjadi akauntan', prompt)   # Malay aspirations
        self.assertIn('என் தந்தை ஒரு லாரி ஓட்டுநர்', prompt)  # Tamil family context
        self.assertIn('Lorry driver', prompt)

    def test_prompt_siblings_uses_count_when_set(self):
        """S15: prompt prefers the integer count over the legacy boolean."""
        self.app.siblings_studying_count = 4
        self.app.save(update_fields=['siblings_studying_count'])
        prompt = _build_prompt(self.app)
        # The line is rendered "Siblings currently studying: 4"
        self.assertIn('Siblings currently studying: 4', prompt)

    def test_prompt_siblings_blank_when_count_unset(self):
        """TD-061: no count → blank (the legacy boolean fallback is gone)."""
        self.app.siblings_studying_count = None
        self.app.save(update_fields=['siblings_studying_count'])
        prompt = _build_prompt(self.app)
        self.assertIn('Siblings currently studying:', prompt)
        # Renders an empty value, not 'yes'.
        self.assertNotIn('Siblings currently studying: yes', prompt)

    def test_prompt_has_no_dead_total(self):
        """The dead FundingNeed `total` must not appear (TD-059)."""
        prompt = _build_prompt(self.app)
        self.assertNotIn('RM0 total', prompt)
        self.assertNotIn('total', prompt.lower().split('funding need')[0])

    def test_prompt_language_instructions(self):
        prompt = _build_prompt(self.app, target_language='Malay (Bahasa Melayu)')
        self.assertIn('Malay, English, or Tamil', prompt)            # multilingual input
        self.assertIn('write the profile in Malay', prompt)          # target-language output

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
        self.assertIn('not provided', prompt)     # funding categories/note render a fallback


class TestClaimGating(TestCase):
    """Check 2 §6: the generator must not assert an UNVERIFIED first-to-university
    claim (the live 'first-generation' bug). Verification comes from the sibling split."""
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='cg', name='B40', year=2026)
        cls.profile = StudentProfile.objects.create(
            supabase_user_id='cg-1', nric='030101-14-1234', name='Priya', school='SMK',
            exam_type='SPM', household_income=1500, household_size=5)

    def _app(self, **kw):
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='shortlisted', **kw)

    def test_unverified_first_in_family_is_not_claimed(self):
        # Claimed, but only a legacy combined count → split unknown → must NOT assert.
        app = self._app(first_in_family=True, siblings_studying_count=2)
        prompt = _build_prompt(app)
        self.assertIn(f'First in family to university: {_DO_NOT_CLAIM}', prompt)

    def test_verified_first_in_family_is_claimed(self):
        # Split says no sibling in tertiary → verified → assert it.
        app = self._app(first_in_family=True, siblings_in_tertiary=0)
        prompt = _build_prompt(app)
        self.assertIn('First in family to university: yes', prompt)

    def test_not_claimed_when_sibling_in_tertiary(self):
        app = self._app(first_in_family=True, siblings_in_tertiary=1)
        prompt = _build_prompt(app)
        self.assertIn(f'First in family to university: {_DO_NOT_CLAIM}', prompt)

    def test_not_first_in_family_says_no(self):
        app = self._app(first_in_family=False)
        prompt = _build_prompt(app)
        self.assertIn('First in family to university: no', prompt)

    def test_prompt_carries_verification_and_tone_rules(self):
        app = self._app(first_in_family=True, siblings_in_tertiary=0)
        prompt = _build_prompt(app)
        self.assertIn('VERIFICATION', prompt)
        self.assertIn('breaking the cycle', prompt)  # the banned-cliché instruction
