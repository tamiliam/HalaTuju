"""
Audit sprint A3.6 — golden prompts of the AI sponsor profile (`profile_engine.py`).

Written BEFORE `profile_engine.py` (1043 lines) was split, and passed on that code. The split is a pure
move: the prompt every case below builds must stay BYTE-IDENTICAL afterwards, so `PROMPT_VERSION` does
not move (a bump re-drafts every assigned unedited profile through the paid daily backfill).

What is read, for four synthetic students (a full SPM case, a bare one, an STPM holder and a
Matriculation holder):

- the DRAFT prompt: `_build_prompt` in English, and the prompt `generate_sponsor_profile` sends in the
  applicant's own locale;
- the FINAL prompt `refine_sponsor_profile` sends (a submitted interview with findings in every sponsor
  area, the officer's four-fact verdict and conclusion);
- the sponsor-pool card: the prompt `generate_anon_blurb` sends and the clipped line it returns;
- the result dicts (the `prompt_version` tag) and the names other modules import from `profile_engine`.

No model is ever called: the one prose seam, `profile_engine._call_gemini_text`, is mocked and only
records the prompt, and the API key is blanked as a second fence. Two values change from run to run
and are replaced by placeholders before comparing: the pool alias (it is built from the row id) and
today's date. On a mismatch the test writes what it read to the system temp folder and names the file.
"""
import datetime
import json
import tempfile
from pathlib import Path
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import profile_engine
from apps.scholarship.models import ApplicantDocument, FundingNeed, InterviewSession, ResolutionItem
from apps.scholarship.pool import pool_ref
from apps.scholarship.tests.factories import make_application, make_cohort, make_student, matched_str_pair

GOLDEN_FILE = Path(__file__).resolve().parent / 'fixtures' / 'a36_profile_goldens.json'

#: Names other modules and tests import from `profile_engine` — every one must stay importable there.
IMPORTED_NAMES = [
    'DEFAULT_LANGUAGE', 'LANGUAGE_NAMES', 'MODEL_CASCADE', 'PRO_CASCADE', 'PROMPT_VERSION',
    'PROFILE_PROMPT', 'REFINE_PROMPT', 'ANON_BLURB_MAX_WORDS',
    '_ABOVE_LINE_EMPHASIS', '_ASSISTANCE_NATURE', '_BELOW_LINE_AFFIRM', '_BUCKET_LABELS',
    '_BUCKET_ORDER', '_COVERAGE', '_DO_NOT_CLAIM', '_EVERGREEN', '_REDACTION', '_STYLE',
    '_SUBJECT_GROUP', '_GROUP_ORDER', '_SIGNAL_LABELS', '_SIGNAL_CATEGORIES', '_VERDICT_LABELS',
    '_OFFICER_FACT_LABELS',
    '_alias', '_build_anon_blurb_prompt', '_build_prompt', '_call_gemini_text', '_clip_words',
    '_deliberation', '_funding', '_gated_first_in_family', '_gated_jkm', '_gated_str',
    '_grades_summary', '_help_wanted', '_income_above_line', '_income_context', '_income_evidence',
    '_join_human', '_ledger_verification', '_merit', '_other_scholarships', '_pathway', '_pronouns',
    '_quiz_interests', '_region', '_render_interview', '_render_officer_decision', '_render_qa',
    '_reporting_date', '_resolve_language', '_siblings_studying_display', '_statement_of_intent',
    '_today_str', '_top_choices', '_with_version', '_yesno', 'count_spm_a_grades',
    'generate_anon_blurb', 'generate_sponsor_profile', 'refine_sponsor_profile',
]

_LONG_BLURB = ('"She is a determined young woman from a large household who hopes to study accounting, '
               'and the support would ease her monthly living and transport costs while she studies."')


class _Recorder:
    """Stands in for the Gemini prose seam: records each prompt, answers with fixed text."""

    def __init__(self, answer):
        self.answer = answer
        self.calls = []

    def __call__(self, prompt, target_language, models=None):
        self.calls.append({'prompt': prompt, 'target_language': target_language,
                           'models': list(models) if models else None})
        return {'markdown': self.answer, 'model_used': 'mocked', 'language': target_language}


def _session(app):
    return InterviewSession.objects.create(
        application=app, status='submitted', submitted_at=timezone.now(),
        findings={
            'afford': {'verdict': 'resolved', 'rationale': 'Will use a PTPTN top-up for the rest'},
            'grades': {'verdict': 'still_unclear', 'rationale': 'Could not show the trial results'},
            'offer': {'verdict': 'new_concern', 'rationale': 'The offer letter names another intake'},
            'manual_1': {'verdict': 'resolved', 'rationale': 'Mother recently lost her job'},
            'unbucketed': {'verdict': '', 'rationale': ''},
            'not_a_dict': 'ignored',
        },
        rubric={'clarity_of_plan': 4, 'financial_need': 5},
        overall_note='Motivated; genuine need.')


_GAPS = [
    {'code': 'afford', 'bucket': 'financial_need', 'question': 'How will you afford it?'},
    {'code': 'grades', 'bucket': 'academic_resilience', 'question': 'How did your trials go?'},
    {'code': 'offer', 'bucket': 'pathway_confidence', 'question': 'Which intake is yours?'},
    {'code': 'unbucketed', 'bucket': 'no_such_bucket', 'question': ''},
]


@override_settings(GEMINI_API_KEY='')
class TestA36ProfileGoldens(TestCase):
    @classmethod
    def setUpTestData(cls):
        cohort = make_cohort(code='a36p', name='B40', year=2026)
        cls.cases = {}

        rich = make_student(
            nric='030303-14-0002', gender='female', school='SMK Taman', exam_type='SPM',
            grades={'bm': 'A+', 'eng': 'A', 'math': 'A+', 'addmath': 'A', 'phy': 'A', 'chem': 'A-',
                    'bio': 'A', 'hist': 'A', 'moral': 'A', 'b_tamil': 'A+', 'mystery_key': 'A',
                    'psv': 'B', 'empty': ''},
            household_income=1800, household_size=6, receives_str=True, receives_jkm=False,
            city='Ipoh', preferred_state='Perak',
            student_signals={
                'field_interest': {'field_business': 3, 'field_digital': 2, 'field_health': 1,
                                   'field_creative': 1, 'unknown_signal': 5},
                'work_preference_signals': {'problem_solving': 3, 'hands_on': 1, 'creative': 0},
            },
        )
        app = make_application(
            'submitted', cohort=cohort, student=rich, locale='ms',
            aspirations='Saya mahu menjadi akauntan', plans='Belajar rajin setiap hari',
            family_context='என் தந்தை ஒரு லாரி ஓட்டுநர்', daily_life='I help at my family stall',
            first_in_family=True, parents_occupation='Lorry driver', siblings_studying_count=2,
            field_of_study='Accounting', pathways_considered=['matriculation', 'stpm'],
            justification='Pendapatan keluarga tidak mencukupi', fears='Saya takut tentang pengangkutan',
            anything_else='I volunteer teaching younger kids on weekends',
            top_choices=[{'rank': 1, 'course_name': 'Ijazah Perakaunan', 'institution': 'UiTM'},
                         {'rank': 2, 'course_name': 'Diploma Perakaunan', 'institution': ''},
                         {'course_name': ''}, 'not a dict'],
            other_scholarships=['jpa', ''], other_scholarships_text='Yayasan Khazanah',
            help_university='yes', help_scholarship='yes',
            uncertainty_reasons=['financial'], uncertainty_note='Masih menunggu rayuan UPU',
            chosen_programme={'course_name': 'Asasi Perakaunan', 'institution': 'UiTM Tapah',
                              'source': 'offer_letter_read'},
            pre_u_track='Asasi', reporting_date=datetime.date(2026, 7, 12),
            interview_gaps=_GAPS,
            officer_verdict={'identity': 'verified', 'academic': 'verified', 'pathway': 'pending',
                             'income': 'verified'},
            verdict_reason='A clear case; the household is B40 and the place is held.',
        )
        FundingNeed.objects.create(application=app, categories=['living', 'transport'],
                                   funding_note='Saya akan cuba PTPTN juga', programme_months=12)
        matched_str_pair(app)
        ApplicantDocument.objects.create(
            application=app, doc_type='statement_of_intent', storage_path='test/soi',
            vision_fields={'text': 'I want to become an accountant. ' * 80})
        base = timezone.make_aware(datetime.datetime(2026, 6, 1, 9, 0))
        ResolutionItem.objects.create(application=app, fact='income', code='q_income',
                                      prompt='Who earns in your family?', resolution_text='Only my father.',
                                      resolved_at=base + datetime.timedelta(days=2))
        ResolutionItem.objects.create(application=app, fact='pathway', code='q_offer', prompt='',
                                      resolution_text='  I accepted the UiTM offer.  ',
                                      resolved_at=base + datetime.timedelta(days=1))
        ResolutionItem.objects.create(application=app, fact='other', code='q_blank', prompt='Blank?',
                                      resolution_text='   ', resolved_at=base)
        cls.cases['rich_spm'] = app

        bare = make_student(nric='030303-14-0004')
        cls.cases['bare'] = make_application('submitted', cohort=cohort, student=bare)

        stpm = make_student(
            nric='030303-14-0006', gender='male', exam_type='stpm', results_exam_type='stpm',
            stpm_grades={'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'A-', 'CHEMISTRY': 'B+', 'BIOLOGY': 'C'},
            stpm_cgpa=3.21, stpm_koko=8.0, completed_qualifications=['spm', 'stpm'],
            grades={'bm': 'A', 'eng': 'B'}, receives_str=True, receives_jkm=True,
        )
        cls.cases['stpm'] = make_application(
            'submitted', cohort=cohort, student=stpm, first_in_family=True,
            pre_u_institution='Kolej Tingkatan Enam', interview_gaps=[], officer_verdict={})

        matric = make_student(
            nric='030303-14-0009', exam_type='matric', grades={'bm': 'A', 'eng': 'A', 'math': 'A+'},
            higher_cgpa=3.5, higher_koko=8, results_exam_type='matric',
            completed_qualifications=['spm', 'matric'], student_signals={'field_interest': 'not a dict'},
        )
        cls.cases['matric'] = make_application(
            'submitted', cohort=cohort, student=matric, locale='en',
            reporting_date=datetime.date(2026, 9, 1))

    def _normalise(self, text, app, today):
        return text.replace(pool_ref(app.id), '<ALIAS>').replace(today, '<TODAY>')

    def _read_case(self, name, app):
        today = profile_engine._today_str()
        out = {'build_prompt_en': self._normalise(profile_engine._build_prompt(app), app, today)}

        draft = _Recorder('A draft profile.')
        with mock.patch('apps.scholarship.profile_engine._call_gemini_text', draft):
            res = profile_engine.generate_sponsor_profile(app)
        (call,) = draft.calls
        out['draft_call'] = {**call, 'prompt': self._normalise(call['prompt'], app, today)}
        out['draft_result'] = res

        session = _session(app)
        final = _Recorder('The final profile.')
        with mock.patch('apps.scholarship.profile_engine._call_gemini_text', final):
            res = profile_engine.refine_sponsor_profile(app, '  The draft text.  ', session, language='en')
            empty = profile_engine.refine_sponsor_profile(app, '', session)
        out['refine_call'] = {**final.calls[0], 'prompt': self._normalise(final.calls[0]['prompt'], app, today)}
        out['refine_empty_draft_call'] = {**final.calls[1],
                                          'prompt': self._normalise(final.calls[1]['prompt'], app, today)}
        out['refine_result'] = res
        out['refine_empty_result'] = empty

        blurb = _Recorder(_LONG_BLURB)
        with mock.patch('apps.scholarship.profile_engine._call_gemini_text', blurb):
            out['blurb'] = profile_engine.generate_anon_blurb(app, '  An anonymous profile for ' + name + '.  ')
            out['blurb_empty_source'] = profile_engine.generate_anon_blurb(app, '   ')
        out['blurb_call'] = blurb.calls[0]
        out['blurb_call_count'] = len(blurb.calls)
        return out

    def test_every_prompt_is_byte_identical(self):
        actual = {name: self._read_case(name, app) for name, app in self.cases.items()}
        actual['_prompt_version'] = profile_engine.PROMPT_VERSION
        actual['_error_result_untagged'] = profile_engine._with_version({'error': 'x'})
        with mock.patch('apps.scholarship.profile_engine._call_gemini_text',
                        return_value={'error': 'down'}):
            actual['_blurb_on_error'] = profile_engine.generate_anon_blurb(self.cases['bare'], 'text')
        text = json.dumps(actual, sort_keys=True, ensure_ascii=False, indent=1, default=str)
        expected = GOLDEN_FILE.read_text(encoding='utf-8') if GOLDEN_FILE.exists() else ''
        if text.strip() != expected.strip():
            out = Path(tempfile.gettempdir()) / 'a36_profile_goldens.actual.json'
            out.write_text(text, encoding='utf-8')
            self.fail(f'A profile prompt changed. What was read is in {out}; diff it with {GOLDEN_FILE}.')

    def test_every_imported_name_still_resolves_on_profile_engine(self):
        missing = [n for n in IMPORTED_NAMES if not hasattr(profile_engine, n)]
        self.assertEqual(missing, [])
