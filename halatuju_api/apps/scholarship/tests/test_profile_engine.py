"""Tests for the AI sponsor-profile prompt builder (S5c rebuild, TD-060).

These exercise the *pure* prompt construction + language resolution — the Gemini
call itself is never made here. The key regression: `_build_prompt` must run
against the CURRENT (profile-canonical) data model without `AttributeError`.
"""
from django.test import TestCase

from apps.courses.models import StudentProfile
from apps.scholarship.models import (
    ApplicantDocument, FundingNeed, Referee, ScholarshipApplication, ScholarshipCohort,
)
from apps.scholarship.profile_engine import (
    DEFAULT_LANGUAGE, _DO_NOT_CLAIM, _build_prompt, _grades_summary, _resolve_language,
    generate_sponsor_profile,
)


class TestProfilePrompt(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.profile = StudentProfile.objects.create(
            supabase_user_id='pe-1', nric='030101-14-1234', name='Priya', school='SMK Taman',
            exam_type='SPM',
            # Realistic keys across groups, incl. a vernacular-language subject (b_tamil)
            # that must NOT surface by name (ethnicity) and must never leak as a raw key.
            grades={'bm': 'A+', 'eng': 'A', 'math': 'A+', 'addmath': 'A', 'phy': 'A',
                    'chem': 'A-', 'bio': 'A', 'hist': 'A', 'moral': 'A', 'b_tamil': 'A+'},
            household_income=1800, household_size=6, receives_str=True, receives_jkm=False,
            student_signals={
                'field_interest': {'field_business': 3, 'field_digital': 2},
                'work_preference_signals': {'problem_solving': 3, 'hands_on': 1},
            },
        )
        cls.app = ScholarshipApplication.objects.create(
            cohort=cls.cohort, profile=cls.profile, status='shortlisted', locale='ms',
            aspirations='Saya mahu menjadi akauntan',  # Malay narrative
            plans='Belajar rajin setiap hari',
            family_context='என் தந்தை ஒரு லாரி ஓட்டுநர்',  # Tamil narrative
            daily_life='I help at my family stall after school',  # English narrative
            first_in_family=True, parents_occupation='Lorry driver', siblings_studying_count=2,
            field_of_study='Accounting', pathways_considered=['matriculation', 'stpm'],
            # Every other thing the student told us — must all reach the draft prompt.
            justification='Pendapatan keluarga tidak mencukupi untuk yuran',  # why assistance is needed
            fears='Saya takut tidak mampu membayar pengangkutan',  # worries
            anything_else='I volunteer teaching younger kids on weekends',  # anything else
            top_choices=[{'rank': 1, 'course_name': 'Ijazah Perakaunan', 'institution': 'UiTM'}],
            other_scholarships=['jpa'], other_scholarships_text='Yayasan Khazanah',
            help_university='yes', help_scholarship='yes',
            uncertainty_reasons=['financial'], uncertainty_note='Masih menunggu keputusan rayuan UPU',
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

    def test_prompt_distils_all_student_inputs(self):
        """Nothing the student filled in should be silently dropped from the draft prompt."""
        prompt = _build_prompt(self.app)
        # Free-text the student wrote (verbatim, any language)
        self.assertIn('Pendapatan keluarga tidak mencukupi', prompt)   # justification
        self.assertIn('Saya takut tidak mampu', prompt)                # fears
        self.assertIn('I volunteer teaching younger kids', prompt)     # anything_else
        self.assertIn('Masih menunggu keputusan rayuan', prompt)       # uncertainty_note
        # Structured plans/support the student gave us
        self.assertIn('Ijazah Perakaunan', prompt)                     # top choice course
        self.assertIn('UiTM', prompt)                                  # top choice institution
        self.assertIn('Yayasan Khazanah', prompt)                      # other scholarships text
        self.assertIn('university applications', prompt)               # help_university=yes
        self.assertIn('scholarship applications', prompt)              # help_scholarship=yes
        self.assertIn('financial', prompt)                             # uncertainty reason

    def test_prompt_includes_statement_of_intent_text(self):
        """The OCR'd Statement of Intent letter (vision_fields['text']) feeds the draft."""
        ApplicantDocument.objects.create(
            application=self.app, doc_type='statement_of_intent', storage_path='soi.pdf',
            vision_fields={'text': 'I want to become a nurse to serve my rural community.'})
        prompt = _build_prompt(self.app)
        self.assertIn('serve my rural community', prompt)
        self.assertIn('Statement of Intent letter', prompt)

    def test_statement_of_intent_blank_when_not_uploaded(self):
        prompt = _build_prompt(self.app)   # fixture app has no SoI document
        self.assertIn('Statement of Intent letter (student\'s uploaded letter, OCR\'d', prompt)
        # the value renders as the not-provided marker, not a stray letter
        self.assertNotIn('serve my rural community', prompt)

    def test_grades_summarised_by_group_and_ethnicity_safe(self):
        """Grades are summarised by GROUP — never per-subject, never a vernacular-language
        subject by name, never a raw subject key."""
        s = _grades_summary(self.profile)
        self.assertIn('A-grade subjects', s)          # count summary
        self.assertIn('sciences', s)                   # phy/chem/bio
        self.assertIn('mathematics', s)                # math/addmath
        self.assertIn('languages', s)                  # bm/eng/b_tamil folded in
        self.assertIn('humanities', s)                 # hist/moral
        for forbidden in ('Tamil', 'Chinese', 'Cina', 'B_TAMIL', 'b_tamil'):
            self.assertNotIn(forbidden, s)             # no ethnicity reveal / raw key
        self.assertNotIn(':', s)                        # no "Subject: A+" enumeration

    def test_generation_result_is_version_tagged(self):
        """A successful generation result carries PROMPT_VERSION (persisted for stale-draft
        detection); an error result is left untagged."""
        from apps.scholarship.profile_engine import PROMPT_VERSION, _with_version
        ok = _with_version({'markdown': 'x', 'model_used': 'gemini-2.5-flash'})
        self.assertEqual(ok['prompt_version'], PROMPT_VERSION)
        self.assertNotIn('prompt_version', _with_version({'error': 'boom'}))

    def test_grades_summary_unknown_key_never_leaks(self):
        """A subject key not in the group map falls back to 'other subjects', never the key."""
        self.profile.grades = {'some_new_subject': 'A+', 'math': 'A'}
        s = _grades_summary(self.profile)
        self.assertIn('other subjects', s)
        self.assertNotIn('some_new_subject', s)
        self.assertNotIn('SOME_NEW_SUBJECT', s)

    def test_prompt_includes_quiz_interests_accretively(self):
        """Idea 1: the interest-quiz result is fed as supportive context, with an
        explicit accretive-only instruction (never used to weaken the pathway)."""
        prompt = _build_prompt(self.app)
        self.assertIn('business', prompt)            # strongest field signal -> label
        self.assertIn('problem-solving', prompt)     # strongest work-style signal -> label
        self.assertIn('ACCRETIVE ONLY', prompt)      # the guard instruction is present
        self.assertIn('NEVER use the quiz', prompt)

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
