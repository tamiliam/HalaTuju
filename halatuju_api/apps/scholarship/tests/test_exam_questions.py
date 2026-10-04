"""TD-218 — `exam_type` answered two questions; each reader now names the one it means.

`apps/courses/exam_questions.py` holds the two accessors. This file pins three things:

1. **The accessors themselves**, including the Form Six explorer (declared STPM, holds SPM) and
   #15's mirage (declared SPM, STPM grades typed into the course guide) — the case
   `results_held` must NEVER promote on presence alone.
2. **The characterisation table** — every reader's answer on a fixed list of profile shapes,
   written against the tree BEFORE the switch (Now sprint 4, 2026-10-02) and kept here as the
   contract. A dated sequence: sprint 4 changed ONE reader's answers — the student payload — and
   only where `heading_for` and `results_held` disagree, and HELD three readers that mean
   results-held (the shortlist gate, the sponsor band, the slip parser) on the declaration
   pending the production probe. The same day the owner ruled "switch all three" (TD-324: 68
   live agree, 1 Form Six explorer, 0 the other way), and their cells were amended in that
   change — each amended row says so. That is the only reason any cell here has moved.
3. **A source guard** that none of the six readers reads the ambiguous field by name again.
"""
import re
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, TestCase

from apps.courses.models import StudentProfile
from apps.courses import exam_questions
from apps.courses.exam_questions import heading_for, results_held
from apps.scholarship import pool, serializers_admin, shortlisting, vision
from apps.scholarship.income_engine import epf_evidence, occupation
from apps.scholarship.serializers import ApplicationReadSerializer
from apps.scholarship.tests.factories import make_application, make_student
from apps.scholarship.tests.source_walk import floor_count, read_source

SPM = {'bm': 'A', 'eng': 'A', 'math': 'A+', 'hist': 'A', 'moral': 'A'}
STPM = {'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'A'}

#: name -> profile fields. The same list the sprint-4 retro's table is drawn from.
SHAPES = {
    'declared_spm': dict(exam_type='spm', grades=SPM),
    'declared_stpm_with_stpm': dict(exam_type='stpm', stpm_grades=STPM, stpm_cgpa=3.5),
    'form_six_explorer': dict(exam_type='stpm', grades=SPM),
    'declared_stpm_both': dict(exam_type='stpm', grades=SPM, stpm_grades=STPM, stpm_cgpa=3.5),
    'explorer_recorded_spm': dict(exam_type='stpm', grades=SPM, results_exam_type='spm'),
    'declared_spm_recorded_stpm': dict(exam_type='spm', grades=SPM, stpm_grades=STPM,
                                       stpm_cgpa=3.5, results_exam_type='stpm'),
    'declared_stpm_both_recorded_spm': dict(exam_type='stpm', grades=SPM, stpm_grades=STPM,
                                            stpm_cgpa=3.5, results_exam_type='spm'),
    'mirage_15': dict(exam_type='spm', grades=SPM, stpm_grades=STPM, stpm_cgpa=4.0),
    'declared_stpm_nothing': dict(exam_type='stpm'),
    'blank': dict(exam_type=''),
}

#: Floors unreachable on purpose, so `_academic_ok`'s failure reason NAMES the branch that ran.
_COHORT = SimpleNamespace(min_stpm_pngk=4.1, min_spm_a_count=99, min_spm_bplus_count=None,
                          min_merit_score=None)


def _profile(shape):
    return StudentProfile(supabase_user_id='char', **SHAPES[shape])


def _readers(p):
    """Every reader's answer for one unsaved profile. No database: the document helpers are
    patched to "nothing on file" so each income check reaches its exam branch."""
    app = SimpleNamespace(profile=p, chosen_pathway='', documents=object())
    _ok, why = shortlisting._academic_ok(p, _COHORT)
    with mock.patch.object(occupation, '_has_read_doc', return_value=False), \
            mock.patch.object(occupation, 'has_live_doc', return_value=False), \
            mock.patch.object(occupation, '_docs_or_none', return_value=object()):
        leaving = occupation.school_leaving_cert_gap(app)
    with mock.patch.object(epf_evidence, '_has_read_doc', return_value=False), \
            mock.patch.object(epf_evidence, '_docs_or_none', return_value=object()):
        semester = epf_evidence.semester_result_gap(app)
    doc = SimpleNamespace(application=app, content_type='image/jpeg')
    _res, diag = vision._extract_slip_deterministic(doc, b'img', words=[])
    field = ApplicationReadSerializer().fields['exam_type']
    return {
        'shortlist': 'stpm' if 'PNGK' in why else 'spm',
        'pool': pool.academic_band(p).split(' ')[0],
        'leaving_cert_ask': leaving,
        'semester_ask': semester,
        'spm_parser': diag.get('reason') != 'not_spm_exam',
        'payload': field.to_representation(field.get_attribute(app)),
    }


# The characterisation table. Each row: heading_for, results_held, then each reader.
#   shortlist / pool / spm_parser — sprint 4 HELD them on the declaration; SWITCHED to
#     results_held on the owner's TD-324 ruling (2026-10-02). The rows marked TD-324 are the ones
#     whose cells that ruling amended (sprint 4 pinned heading_for's answer there: stpm/STPM/False
#     on the three explorer-shaped rows, spm/SPM/True on the promote row) — superseded by the
#     ruling, not bent to fit.
#   leaving_cert_ask / semester_ask — MEAN heading-for: unchanged by construction.
#   payload — SWITCHED to results_held in sprint 4; the four rows marked * changed then.
TABLE = {
    #                                   head    held    shortl  pool    leave  sem    parser payload
    'declared_spm':                    ('spm',  'spm',  'spm',  'SPM',  True,  False, True,  'spm'),
    'declared_stpm_with_stpm':         ('stpm', 'stpm', 'stpm', 'STPM', False, True,  False, 'stpm'),
    'form_six_explorer':               ('stpm', 'spm',  'spm',  'SPM',  False, True,  True,  'spm'),   # * TD-324
    'declared_stpm_both':              ('stpm', 'stpm', 'stpm', 'STPM', False, True,  False, 'stpm'),
    'explorer_recorded_spm':           ('stpm', 'spm',  'spm',  'SPM',  False, True,  True,  'spm'),   # * TD-324
    'declared_spm_recorded_stpm':      ('spm',  'stpm', 'stpm', 'STPM', True,  False, False, 'stpm'),  # * TD-324
    'declared_stpm_both_recorded_spm': ('stpm', 'spm',  'spm',  'SPM',  False, True,  True,  'spm'),   # * TD-324
    'mirage_15':                       ('spm',  'spm',  'spm',  'SPM',  True,  False, True,  'spm'),
    'declared_stpm_nothing':           ('stpm', 'stpm', 'stpm', 'STPM', False, True,  False, 'stpm'),
    'blank':                           ('',     '',     'spm',  'SPM',  True,  False, True,  ''),
}


class TestTheAccessors(SimpleTestCase):
    def test_heading_for_is_the_declaration_verbatim(self):
        self.assertEqual(heading_for(_profile('form_six_explorer')), 'stpm')
        self.assertEqual(heading_for(_profile('declared_spm_recorded_stpm')), 'spm')
        # verbatim: no normalising, so a raw reader moved onto it keeps its exact answer
        self.assertEqual(heading_for(SimpleNamespace(exam_type='STPM ')), 'STPM ')
        self.assertEqual(heading_for(SimpleNamespace(exam_type=None)), '')
        self.assertEqual(heading_for(SimpleNamespace()), '')
        self.assertEqual(heading_for(None), '')

    def test_results_held_reads_the_form_six_explorer_as_spm(self):
        # She declared STPM (heading for it) and holds only SPM results.
        self.assertEqual(results_held(_profile('form_six_explorer')), 'spm')

    def test_results_held_never_promotes_on_typed_stpm_data(self):
        """#15: a 4.0 CGPA and five STPM subjects, none of them sat. Presence proves nothing."""
        self.assertEqual(results_held(_profile('mirage_15')), 'spm')

    def test_a_recorded_completion_wins_both_ways(self):
        self.assertEqual(results_held(_profile('explorer_recorded_spm')), 'spm')
        self.assertEqual(results_held(_profile('declared_spm_recorded_stpm')), 'stpm')
        self.assertEqual(results_held(_profile('declared_stpm_both_recorded_spm')), 'spm')

    def test_absence_with_nothing_else_repeats_the_declaration(self):
        self.assertEqual(results_held(_profile('declared_stpm_nothing')), 'stpm')
        self.assertEqual(results_held(_profile('blank')), '')
        self.assertEqual(results_held(None), '')

    def test_held_qualification_IS_results_held(self):
        # The admin label, the merit source and the audit command call the old name; it must be
        # the same function, not a copy that can drift.
        self.assertIs(serializers_admin.held_qualification, exam_questions.results_held)


class TestTheCharacterisationTable(SimpleTestCase):
    """Every reader on every shape. A change to any cell is an outcome change — read the module
    docstring of `exam_questions` and TD-324 before editing a row."""

    def test_the_table_covers_every_shape(self):
        floor_count(list(TABLE), len(SHAPES), 'characterised shapes',
                    'TD-218: the table must describe every shape SHAPES lists, or a reader '
                    'can change on an uncharacterised profile.')
        self.assertEqual(set(TABLE), set(SHAPES))

    def test_every_reader_on_every_shape(self):
        for shape, row in TABLE.items():
            p = _profile(shape)
            head, held, shortl, band, leave, sem, parser, payload = row
            got = _readers(p)
            with self.subTest(shape=shape):
                self.assertEqual(heading_for(p), head)
                self.assertEqual(results_held(p), held)
                self.assertEqual(got['shortlist'], shortl)
                self.assertEqual(got['pool'], band)
                self.assertEqual(got['leaving_cert_ask'], leave)
                self.assertEqual(got['semester_ask'], sem)
                self.assertEqual(got['spm_parser'], parser)
                self.assertEqual(got['payload'], payload)

    def test_the_results_readers_equal_results_held(self):
        """⚠ THE FENCE. shortlisting, pool and the slip parser MEAN results-held and read it.
        Dated: sprint 4 held them on the declaration (this test then asserted they equalled
        `heading_for`); the owner's ruling of 2026-10-02 (TD-324) switched all three, and this
        fence now holds them on `results_held`. If it fails, a reader drifted off the question it
        means — and a change to `results_held` itself moves all three at once."""
        for shape in SHAPES:
            p = _profile(shape)
            held = results_held(p) or 'spm'
            got = _readers(p)
            with self.subTest(shape=shape):
                self.assertEqual(got['shortlist'], held)
                self.assertEqual(got['pool'], held.upper())
                self.assertEqual(got['spm_parser'], held == 'spm')


class TestTheConvertedReadersOnTheExplorer(TestCase):
    """The Form Six explorer through each reader, on a REAL application from the factory."""

    def setUp(self):
        self.student = make_student(exam_type='stpm', grades=SPM)
        self.app = make_application('submitted', student=self.student)

    def test_the_student_payload_serves_the_results_she_holds(self):
        self.assertEqual(ApplicationReadSerializer(self.app).data['exam_type'], 'spm')

    def test_the_payload_follows_her_stpm_results_when_they_land(self):
        self.student.stpm_cgpa = 3.4
        self.student.save(update_fields=['stpm_cgpa'])
        self.app.refresh_from_db()
        self.assertEqual(ApplicationReadSerializer(self.app).data['exam_type'], 'stpm')

    def test_a_missing_profile_still_omits_the_key(self):
        # Exactly what `source='profile.exam_type'` did for an object with no profile: DRF skips a
        # read-only field whose dotted source breaks on None, so the key is ABSENT, not null.
        # (Found by characterising before the switch: the first draft served None.)
        from rest_framework import serializers as drf

        class _Old(drf.Serializer):
            exam_type = drf.CharField(source='profile.exam_type', read_only=True)

        class _New(drf.Serializer):
            exam_type = exam_questions.ResultsHeldField()

        orphan = SimpleNamespace(profile=None)
        self.assertNotIn('exam_type', _Old(orphan).data)
        self.assertNotIn('exam_type', _New(orphan).data)
        # positive control: with a profile both serve the key
        self.assertIn('exam_type', _New(SimpleNamespace(profile=self.student)).data)

    def test_the_income_readers_ask_by_the_exam_she_is_heading_for(self):
        # In Form Six: no leaving certificate to ask for; the semester-result arm applies.
        with mock.patch.object(occupation, '_has_read_doc', return_value=False), \
                mock.patch.object(occupation, 'has_live_doc', return_value=False):
            self.assertFalse(occupation.school_leaving_cert_gap(self.app))
        with mock.patch.object(epf_evidence, '_has_read_doc', return_value=False):
            self.assertTrue(epf_evidence.semester_result_gap(self.app))


def _cohort(**floors):
    base = dict(min_stpm_pngk=None, min_spm_a_count=None, min_spm_bplus_count=None,
                min_merit_score=None)
    base.update(floors)
    return SimpleNamespace(**base)


def _slip_gate(app):
    """The slip-parser gate's verdict for this application, without a Vision call: `words=[]`
    stops a parse that got PAST the gate at 'no_words'."""
    doc = SimpleNamespace(application=app, content_type='image/jpeg')
    return vision._extract_slip_deterministic(doc, b'img', words=[])[1]


class TestTheResultsReadersOnTheExplorer(TestCase):
    """TD-324: the Form Six explorer — declared STPM, SPM grades on file, no STPM results,
    `results_exam_type` blank — through each switched reader, on a REAL application.

    TD-324 (owner, 2026-10-02): the three results readers were switched to `results_held`.
    Sprint 4 pinned the opposite in `TestTheConvertedReadersOnTheExplorer`
    (`test_the_held_readers_still_treat_her_as_declared`: a bare 'STPM' band and 'STPM PNGK not
    provided'); the ruling superseded it, so these pin the explorer's NEW answers, one reader
    each."""

    def setUp(self):
        self.student = make_student(exam_type='stpm', grades=SPM)
        self.app = make_application('submitted', student=self.student)
        self.assertEqual(self.student.results_exam_type or '', '')   # the shape, not assumed

    def test_the_shortlist_gate_tests_her_on_the_spm_bar(self):
        # An STPM floor is set too: before TD-324 she failed it on 'STPM PNGK not provided'.
        self.assertEqual(shortlisting._academic_ok(self.student, _cohort(min_stpm_pngk=2.9,
                                                                         min_spm_a_count=6)),
                         (False, '5 at A- (need 6)'))
        self.assertEqual(shortlisting._academic_ok(self.student, _cohort(min_stpm_pngk=2.9,
                                                                         min_spm_a_count=5)),
                         (True, ''))

    def test_the_sponsor_band_reads_her_spm_results(self):
        self.assertEqual(pool.academic_band(self.student), 'SPM · 5 As')

    def test_the_slip_gate_lets_the_spm_parser_run(self):
        diag = _slip_gate(self.app)
        self.assertNotEqual(diag.get('reason'), 'not_spm_exam')
        self.assertEqual(diag.get('reason'), 'no_words')   # positive: it got past the gate


class TestTheResultsReadersOnThePromoteShape(TestCase):
    """TD-324, the other direction, pinned openly: declared SPM with a RECORDED STPM completion.
    The switch moves her too — 0 live applications in this shape when the owner ruled
    (2026-10-02)."""

    def setUp(self):
        self.student = make_student(exam_type='spm', grades=SPM, stpm_grades=STPM, stpm_cgpa=3.5,
                                    results_exam_type='stpm')
        self.app = make_application('submitted', student=self.student)

    def test_the_shortlist_gate_tests_her_on_her_pngk(self):
        self.assertEqual(shortlisting._academic_ok(self.student, _cohort(min_stpm_pngk=3.6,
                                                                         min_spm_a_count=1)),
                         (False, 'PNGK 3.5 below 3.6'))

    def test_the_sponsor_band_reads_her_stpm_results(self):
        self.assertEqual(pool.academic_band(self.student), 'STPM · PNGK 3.5')

    def test_the_slip_gate_skips_the_spm_parser(self):
        self.assertEqual(_slip_gate(self.app),
                         {'reason': 'not_spm_exam', 'exam_type': 'stpm'})


#: The six readers TD-218 names (the admin serializers were converted first, as
#: `held_qualification`), each with the accessor it must call. Dated: shortlisting, pool and
#: vision called `heading_for(` after sprint 4 and `results_held(` since TD-324 (2026-10-02).
_READERS = {
    'apps/scholarship/shortlisting.py': 'results_held(',
    'apps/scholarship/pool.py': 'results_held(',
    'apps/scholarship/income_engine/occupation.py': 'heading_for(',
    'apps/scholarship/income_engine/epf_evidence.py': 'heading_for(',
    'apps/scholarship/vision.py': 'results_held(',
    'apps/scholarship/serializers.py': 'ResultsHeldField(',
    # TD-325 (2026-10-04): the sponsor-profile prompt and the Check-2 facts ledger name the
    # results we hold (owner ruling TD-324), so they read `results_held` too.
    'apps/scholarship/profile_engine.py': 'results_held(',
    'apps/scholarship/submission_review.py': 'results_held(',
}
_API = Path(__file__).resolve().parents[3]
_RAW_GETATTR = re.compile(r"getattr\([^()]*,\s*'exam_type'")
_RAW_ATTR = re.compile(r'\b\w+\.exam_type\b')


class TestNoReaderReadsTheAmbiguousName(SimpleTestCase):
    def test_each_reader_calls_its_named_accessor_and_never_the_raw_field(self):
        why = ('TD-218/TD-325: each of the eight exam_type readers must call a named accessor from '
               'apps/courses/exam_questions.py, never read profile.exam_type directly.')
        seen = []
        for rel, accessor in _READERS.items():
            src = read_source(_API / rel, why)
            with self.subTest(reader=rel):
                # positive: the accessor is CALLED here (not merely imported)
                self.assertGreaterEqual(src.count(accessor), 1, f'{rel} no longer calls {accessor}')
                # negative: no raw read of the field by name — a getattr of it, or attribute access
                self.assertIsNone(_RAW_GETATTR.search(src), f'{rel} reads the ambiguous field')
                self.assertIsNone(_RAW_ATTR.search(src), f'{rel} reads the ambiguous field')
            seen.append(rel)
        floor_count(seen, 8, 'reader modules', why)


class TestTheTd325ReadersOnTheExplorer(TestCase):
    """TD-325 (2026-10-04): the sponsor-profile prompt and the Check-2 facts ledger, on the Form
    Six explorer (declared STPM, SPM grades on file, no STPM results). Before TD-325 both repeated
    the declaration — 'stpm' — with nothing behind it."""

    def setUp(self):
        self.student = make_student(exam_type='stpm', grades=SPM)
        self.app = make_application('submitted', student=self.student)

    def test_the_facts_ledger_claims_the_results_she_holds(self):
        from apps.scholarship import submission_review
        with mock.patch.object(submission_review, '_verdict_map', return_value={}):
            rows = submission_review.build_facts_ledger(self.app)
        qual = [r for r in rows if r['claim'] == 'qualification']
        self.assertEqual(len(qual), 1)
        self.assertEqual(qual[0]['value'], 'spm')

    def test_the_facts_ledger_follows_her_stpm_results_when_they_land(self):
        from apps.scholarship import submission_review
        self.student.stpm_grades, self.student.stpm_cgpa = STPM, 3.5
        self.student.save()
        with mock.patch.object(submission_review, '_verdict_map', return_value={}):
            rows = submission_review.build_facts_ledger(self.app)
        self.assertEqual([r['value'] for r in rows if r['claim'] == 'qualification'], ['stpm'])

    def test_the_sponsor_prompt_names_the_results_she_holds(self):
        from apps.scholarship import profile_engine
        prompt = profile_engine._build_prompt(self.app)
        self.assertIn('Qualification: spm ', prompt)
        self.assertNotIn('Qualification: stpm', prompt)
