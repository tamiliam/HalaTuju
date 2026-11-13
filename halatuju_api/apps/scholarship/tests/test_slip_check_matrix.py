"""F1 slip-check matrix: one row per cell of the owner-approved rule table.

Source of every expected value: ``docs/plans/2026-11-13-f1-slip-check-rule-table.md`` (approved
2026-11-13, Q1 to Q8 as recommended). Seven tables (A SPM holder post-SPM, B STPM, C Matriculation,
D Diploma, E Asasi, F degree-bound SPM holder, G the optional SPM slip of a tertiary holder) x seven
slip states. Each reachable cell pins the drawer chips, the Academic band and the wording keys;
each unreachable cell (Q8) is pinned as "cannot happen" by a probe that shows why.

A new route, a new slip state or a changed answer is a ROW here first. The static test at the end
fails when `results_route.destination()` can return a value no table covers.
"""
import ast
import inspect
from dataclasses import dataclass, field

from django.test import TestCase, override_settings

from apps.courses.models import FieldTaxonomy, StpmCourse
from apps.scholarship import results_route
from apps.scholarship.academic_engine import student_slip_check
from apps.scholarship.genuineness.bands import NOT_CHECKED, NOT_FINAL_SEEN
from apps.scholarship.higher_results import student_higher_check
from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.tests.factories import create_document, make_application, make_student
from apps.scholarship.verdict_engine import build_verdict

DEGREE_ID = 'UH6481099'
CERTAIN, PROBABLE, UNSURE, FAIL = 'verified', 'review', 'recommend', 'gap'
SUBMITTED = 'profile_complete'

# ── Profiles ───────────────────────────────────────────────────────────────────────────────────
CORE_TYPED = {'bm': 'A', 'eng': 'A', 'math': 'A', 'hist': 'B'}
SPM_TYPED = {**CORE_TYPED, 'phy': 'A'}
STPM_GRADES = {'PA': 'A', 'MATH_T': 'A-', 'PHYSICS': 'A-', 'CHEMISTRY': 'B+'}    # PNGK 3.67
SPM_HELD = dict(exam_type='spm', results_exam_type='spm', grades=SPM_TYPED)
STPM_HELD = dict(exam_type='stpm', results_exam_type='stpm', grades=SPM_TYPED, stpm_grades=STPM_GRADES,
                 stpm_cgpa=3.67, completed_qualifications=['spm', 'stpm'])
MATRIC_HELD = dict(exam_type='matric', results_exam_type='matric', grades=SPM_TYPED, higher_cgpa=3.5,
                   higher_koko=8, completed_qualifications=['spm', 'matric'])
DIPLOMA_HELD = dict(exam_type='diploma', results_exam_type='diploma', grades=SPM_TYPED, higher_cgpa=3.2,
                    higher_institution_type='public', completed_qualifications=['spm', 'diploma'])
ASASI_HELD = dict(exam_type='asasi', results_exam_type='asasi', grades=SPM_TYPED, higher_cgpa=3.4,
                  completed_qualifications=['spm', 'asasi'])

DEGREE = {'chosen_pathway': '', 'pathway_certainty': 'sure',
          'chosen_programme': {'course_id': DEGREE_ID, 'course_name': 'Ijazah Sarjana Muda X'}}
POST_SPM = {'chosen_pathway': 'matric', 'pathway_certainty': 'sure', 'chosen_programme': {}}

# ── Reads ──────────────────────────────────────────────────────────────────────────────────────
CORE_ROWS = [{'subject': 'BAHASA MELAYU', 'grade': 'A'}, {'subject': 'BAHASA INGGERIS', 'grade': 'A'},
             {'subject': 'MATEMATIK', 'grade': 'A'}, {'subject': 'SEJARAH', 'grade': 'B'}]
SPM_ROWS = CORE_ROWS + [{'subject': 'FIZIK', 'grade': 'A'}]
SHORT_ROWS = [r for r in SPM_ROWS if r['subject'] != 'MATEMATIK']   # a compulsory subject dropped


def spm_read(rows, printed=None):
    """An SPM slip read; `printed` = the subject total the slip prints ("JUMLAH MATA PELAJARAN : ENAM"),
    carried the way a Gemini read keeps it (its word capture, `printed_subject_count`)."""
    out = {'candidate_name': 'PRIYA', 'exam': 'SIJIL PELAJARAN MALAYSIA 2024', 'results': rows}
    if printed:
        words = f'SIJIL PELAJARAN MALAYSIA JUMLAH MATA PELAJARAN : {printed}'.split()
        out['_slip_ocr_diag'] = {'reason': 'parse_none', 'capture': [{'text': w} for w in words]}
    return out


STPM_ROWS = [{'subject': 'PENGAJIAN AM', 'grade': 'A'}, {'subject': 'MATEMATIK (T)', 'grade': 'A-'},
             {'subject': 'FIZIK', 'grade': 'A-'}, {'subject': 'KIMIA', 'grade': 'B+'}]


def stpm_read(rows=STPM_ROWS, cgpa='3.67'):
    return {'candidate_name': 'PRIYA', 'exam': 'SIJIL TINGGI PERSEKOLAHAN MALAYSIA 2025', 'cgpa': cgpa,
            'cgpa_label': 'PNGK', 'results_kind_detected': 'stpm', 'results': rows}


def cgpa_read(kind, cgpa):
    return {'candidate_name': 'PRIYA', 'cgpa': cgpa, 'cgpa_label': 'PNGK', 'results_kind_detected': kind}


GENUINE, SUSPECT = {'status': 'genuine'}, {'status': 'suspect'}
#: The stored record of the deterministic STPM exact read (`higher_results._read_higher`).
EXACT_READ = {'capture': 'deterministic', 'parser_version': 'stpm_parse_1'}


def not_final(seen):
    return {'status': NOT_CHECKED, 'doc_seen': seen}


# ── Builders ───────────────────────────────────────────────────────────────────────────────────
def _degree_course():
    FieldTaxonomy.objects.get_or_create(key='f1-matrix', defaults={
        'name_en': 'X', 'name_ms': 'X', 'name_ta': 'X', 'image_slug': 'x'})
    StpmCourse.objects.get_or_create(course_id=DEGREE_ID, defaults={
        'course_name': 'Ijazah Sarjana Muda X', 'university': 'Universiti Malaya', 'field_key_id': 'f1-matrix'})


def _app(profile, plan, stage='shortlisted'):
    _degree_course()
    student = make_student(name='Priya', nric='030101-14-1234', **profile)
    return make_application(stage, student=student, **plan)


def _doc(app, doc_type, fields, auth=None, stored=None, **kw):
    vf = {'fields': fields, 'student_verdict': 'ok', 'error': '', **(stored or {})}
    if auth is not None:
        vf['authenticity'] = auth
    return create_document(application=app, doc_type=doc_type, storage_path=f'test/{doc_type}',
                           vision_fields=vf, **kw)


@dataclass
class Case:
    profile: dict
    plan: dict
    slip: tuple = None        # (fields, authenticity) of the SPM-slot upload, or None
    higher: tuple = None      # (fields, authenticity[, stored record keys]) of the higher upload, or None
    stage: str = 'shortlisted'   # Table F: 'profile_complete' (the owed / undeclared rules are post-submit)


@dataclass
class Row:
    table: str
    state: str
    case: Case = None
    band: str = ''
    unresolved: frozenset = frozenset()
    evidence: frozenset = frozenset()
    slip_chips: dict = field(default_factory=dict)     # student_slip_check: name / subjects / results
    higher_chips: dict = field(default_factory=dict)   # student_higher_check: name / kind / cgpa / grades
    unreachable: str = ''                              # Q8: why the cell cannot happen

    @property
    def id(self):
        return f'{self.table}:{self.state}'


def R(table, state, case, band, unresolved=(), evidence=(), slip_chips=None, higher_chips=None):
    return Row(table, state, case, band, frozenset(unresolved), frozenset(evidence),
               slip_chips or {}, higher_chips or {})


def U(table, state, reason):
    return Row(table, state, unreachable=reason)


def slip_chips(name='match', subjects='match', results='match'):
    return {'name': name, 'subjects': subjects, 'results': results}


def higher_chips(name='match', kind='match', cgpa='match', grades=''):
    return {'name': name, 'kind_status': kind, 'cgpa_status': cgpa, 'grades_status': grades}


STATES = ('checked', 'not_final', 'suspect', 'short_read', 'extra_typed', 'subject_missing',
          'undeclared_higher')
NAME_OK = 'results_slip_name_ok'
NOT_DECLARED = 'higher_results_not_declared'
HIGHER_OK = ('higher_results_name_ok', 'higher_results_kind_ok', 'higher_results_cgpa_ok')
NO_FINAL_RULE = 'no "not final" rule reads this page (NOT_FINAL_SEEN: matriculation / polytechnic only)'
NO_SUBJECTS = 'CGPA only: no subject is compared on this route'
DECLARED = 'a tertiary holder has declared her higher results'

MATRIX = [
    # ── Table A: SPM holder, post-SPM course ──
    R('A', 'checked', Case(SPM_HELD, POST_SPM, slip=(spm_read(SPM_ROWS), GENUINE)), CERTAIN,
      evidence=(NAME_OK, 'grades_verified'), slip_chips=slip_chips()),
    U('A', 'not_final', NO_FINAL_RULE),
    R('A', 'suspect', Case(SPM_HELD, POST_SPM, slip=(spm_read(SPM_ROWS), SUSPECT)), PROBABLE,
      unresolved=('document_not_genuine',), evidence=(NAME_OK, 'grades_verified'), slip_chips=slip_chips()),
    # Q1 (changed 2026-11-13): the subjects the short read missed are named; no tick, at best Probable.
    R('A', 'short_read', Case(SPM_HELD, POST_SPM, slip=(spm_read(SHORT_ROWS), GENUINE)), PROBABLE,
      unresolved=('academic_grades_unchecked',), evidence=(NAME_OK,),
      slip_chips=slip_chips(subjects='pending', results='pending')),
    R('A', 'extra_typed', Case({**SPM_HELD, 'grades': {**SPM_TYPED, 'chem': 'A'}}, POST_SPM,
                               slip=(spm_read(SPM_ROWS), GENUINE)), PROBABLE,
      unresolved=('academic_extra_subjects',), evidence=(NAME_OK,), slip_chips=slip_chips(subjects='mismatch')),
    R('A', 'subject_missing', Case({**SPM_HELD, 'grades': CORE_TYPED}, POST_SPM,
                                   slip=(spm_read(SPM_ROWS), GENUINE)), PROBABLE,
      unresolved=('academic_missing_subjects',), evidence=(NAME_OK,), slip_chips=slip_chips(subjects='mismatch')),
    R('A', 'undeclared_higher', Case(SPM_HELD, POST_SPM, slip=(stpm_read(), None)), PROBABLE,
      unresolved=('results_slip_is_higher', 'results_slip_missing'), evidence=(NAME_OK,),
      slip_chips=slip_chips(subjects='not_spm', results='not_spm')),

    # ── Table B: STPM holder ──
    R('B', 'checked', Case(STPM_HELD, DEGREE, higher=(stpm_read(), GENUINE)), CERTAIN,
      evidence=HIGHER_OK, higher_chips=higher_chips(grades='match')),
    U('B', 'not_final', NO_FINAL_RULE),
    R('B', 'suspect', Case(STPM_HELD, DEGREE, higher=(stpm_read(), SUSPECT)), PROBABLE,
      unresolved=('document_not_genuine',), evidence=HIGHER_OK, higher_chips=higher_chips(grades='match')),
    # Q2 (changed 2026-11-13): Pengajian Am not read = a short read; what it missed is named, holds Certain.
    R('B', 'short_read', Case(STPM_HELD, DEGREE, higher=(stpm_read(STPM_ROWS[1:]), GENUINE)), PROBABLE,
      unresolved=('academic_grades_unchecked',), evidence=HIGHER_OK, higher_chips=higher_chips(grades='pending')),
    # Q3 (changed 2026-11-13): an entered STPM subject not on a full EXACT read is flagged, red like
    # missing (an AI read cannot tell "not printed" from "skipped": see EXTRA B:extra_typed_ai_read).
    R('B', 'extra_typed', Case({**STPM_HELD, 'stpm_grades': {**STPM_GRADES, 'BIOLOGY': 'C'}}, DEGREE,
                               higher=(stpm_read(), GENUINE, EXACT_READ)), PROBABLE,
      unresolved=('academic_extra_subjects',), evidence=HIGHER_OK, higher_chips=higher_chips(grades='mismatch')),
    R('B', 'subject_missing', Case({**STPM_HELD, 'stpm_grades': {k: v for k, v in STPM_GRADES.items()
                                                                if k != 'CHEMISTRY'}}, DEGREE,
                                   higher=(stpm_read(), GENUINE)), PROBABLE,
      unresolved=('higher_results_subjects_missing',), evidence=HIGHER_OK[:2],
      higher_chips=higher_chips(cgpa='pending', grades='mismatch')),
    U('B', 'undeclared_higher', DECLARED),

    # ── Table C: Matriculation holder ──
    R('C', 'checked', Case(MATRIC_HELD, DEGREE, higher=(cgpa_read('matric', '3.50'), GENUINE)), CERTAIN,
      evidence=HIGHER_OK, higher_chips=higher_chips()),
    R('C', 'not_final', Case(MATRIC_HELD, DEGREE, higher=(cgpa_read('matric', '3.50'),
                                                          not_final('matric_result_slip'))), PROBABLE,
      unresolved=('higher_results_not_final',), evidence=HIGHER_OK, higher_chips=higher_chips()),
    U('C', 'suspect', 'matriculation pages are stored genuine or not checked, never suspect (ruling 4, 2026-10-29)'),
    U('C', 'short_read', NO_SUBJECTS),
    U('C', 'extra_typed', NO_SUBJECTS),
    U('C', 'subject_missing', NO_SUBJECTS),
    U('C', 'undeclared_higher', DECLARED),

    # ── Table D: Diploma holder (Q5: keep) ──
    R('D', 'checked', Case(DIPLOMA_HELD, DEGREE, higher=(cgpa_read('diploma', '3.20'), GENUINE)), CERTAIN,
      evidence=HIGHER_OK, higher_chips=higher_chips()),
    R('D', 'not_final', Case(DIPLOMA_HELD, DEGREE, higher=(cgpa_read('diploma', '3.20'),
                                                           not_final('poly_result_slip'))), PROBABLE,
      unresolved=('higher_results_not_final',), evidence=HIGHER_OK, higher_chips=higher_chips()),
    U('D', 'suspect', 'diploma pages are stored genuine or not checked, never suspect (ruling 4, 2026-10-29)'),
    U('D', 'short_read', NO_SUBJECTS),
    U('D', 'extra_typed', NO_SUBJECTS),
    U('D', 'subject_missing', NO_SUBJECTS),
    U('D', 'undeclared_higher', DECLARED),

    # ── Table E: Asasi holder (Q5: keep) ──
    R('E', 'checked', Case(ASASI_HELD, DEGREE, higher=(cgpa_read('asasi', '3.40'), None)), PROBABLE,
      evidence=HIGHER_OK + ('higher_results_not_checked',), higher_chips=higher_chips()),
    U('E', 'not_final', NO_FINAL_RULE),
    U('E', 'suspect', 'no Asasi page is ever scored'),
    U('E', 'short_read', NO_SUBJECTS),
    U('E', 'extra_typed', NO_SUBJECTS),
    U('E', 'subject_missing', NO_SUBJECTS),
    U('E', 'undeclared_higher', DECLARED),

    # ── Table F: SPM holder going to a degree (submitted: the owed / undeclared rules) ──
    R('F', 'checked', Case(SPM_HELD, DEGREE, slip=(spm_read(SPM_ROWS), GENUINE), stage=SUBMITTED), UNSURE,
      unresolved=(NOT_DECLARED,), evidence=(NAME_OK, 'grades_verified'), slip_chips=slip_chips()),
    R('F', 'not_final', Case(SPM_HELD, DEGREE, slip=(spm_read(SPM_ROWS), GENUINE),
                             higher=(cgpa_read('matric', '3.50'), not_final('matric_result_slip')), stage=SUBMITTED),
      UNSURE, unresolved=('higher_results_not_final', 'higher_results_undeclared'),
      evidence=(NAME_OK, 'higher_results_name_ok', 'grades_verified'),
      slip_chips=slip_chips(), higher_chips=higher_chips(kind='', cgpa='pending')),
    R('F', 'suspect', Case(SPM_HELD, DEGREE, slip=(spm_read(SPM_ROWS), SUSPECT), stage=SUBMITTED), UNSURE,
      unresolved=(NOT_DECLARED, 'document_not_genuine'), evidence=(NAME_OK, 'grades_verified'),
      slip_chips=slip_chips()),
    R('F', 'short_read', Case(SPM_HELD, DEGREE, slip=(spm_read(SHORT_ROWS), GENUINE), stage=SUBMITTED), UNSURE,
      unresolved=(NOT_DECLARED, 'academic_grades_unchecked'), evidence=(NAME_OK,),       # Q1
      slip_chips=slip_chips(subjects='pending', results='pending')),
    R('F', 'extra_typed', Case({**SPM_HELD, 'grades': {**SPM_TYPED, 'chem': 'A'}}, DEGREE,
                               slip=(spm_read(SPM_ROWS), GENUINE), stage=SUBMITTED), UNSURE,
      unresolved=('academic_extra_subjects', NOT_DECLARED), evidence=(NAME_OK,),
      slip_chips=slip_chips(subjects='mismatch')),
    R('F', 'subject_missing', Case({**SPM_HELD, 'grades': CORE_TYPED}, DEGREE,
                                   slip=(spm_read(SPM_ROWS), GENUINE), stage=SUBMITTED), UNSURE,
      unresolved=('academic_missing_subjects', NOT_DECLARED), evidence=(NAME_OK,),
      slip_chips=slip_chips(subjects='mismatch')),
    R('F', 'undeclared_higher', Case(SPM_HELD, DEGREE, slip=(spm_read(SPM_ROWS), GENUINE),
                                     higher=(cgpa_read('matric', '3.50'), GENUINE), stage=SUBMITTED), UNSURE,
      unresolved=('higher_results_undeclared',), evidence=(NAME_OK, 'higher_results_name_ok', 'grades_verified'),
      slip_chips=slip_chips(), higher_chips=higher_chips(kind='', cgpa='pending')),

    # ── Table G: the optional SPM slip of a tertiary holder (STPM here; the rule is one for all four) ──
    R('G', 'checked', Case({**STPM_HELD, 'spm_prereq_grades': CORE_TYPED}, DEGREE,
                           slip=(spm_read(CORE_ROWS), GENUINE), higher=(stpm_read(), GENUINE)), CERTAIN,
      evidence=HIGHER_OK + (NAME_OK, 'grades_verified'), slip_chips=slip_chips(),
      higher_chips=higher_chips(grades='match')),
    U('G', 'not_final', NO_FINAL_RULE),
    R('G', 'suspect', Case({**STPM_HELD, 'spm_prereq_grades': CORE_TYPED}, DEGREE,
                           slip=(spm_read(CORE_ROWS), SUSPECT), higher=(stpm_read(), GENUINE)), PROBABLE,
      unresolved=('document_not_genuine',), evidence=HIGHER_OK + (NAME_OK, 'grades_verified'),
      slip_chips=slip_chips(), higher_chips=higher_chips(grades='match')),
    R('G', 'short_read', Case({**STPM_HELD, 'spm_prereq_grades': CORE_TYPED}, DEGREE,
                              slip=(spm_read(SHORT_ROWS), GENUINE), higher=(stpm_read(), GENUINE)), PROBABLE,
      unresolved=('academic_grades_unchecked',), evidence=HIGHER_OK + (NAME_OK,),
      slip_chips=slip_chips(results='pending'), higher_chips=higher_chips(grades='match')),
    R('G', 'extra_typed', Case({**STPM_HELD, 'spm_prereq_grades': {**CORE_TYPED, 'chem': 'A'}}, DEGREE,
                               slip=(spm_read(SPM_ROWS), GENUINE), higher=(stpm_read(), GENUINE)), PROBABLE,
      unresolved=('academic_extra_subjects',), evidence=HIGHER_OK + (NAME_OK,),
      slip_chips=slip_chips(subjects='mismatch'), higher_chips=higher_chips(grades='match')),
    R('G', 'subject_missing', Case({**STPM_HELD, 'spm_prereq_grades': CORE_TYPED}, DEGREE,
                                   slip=(spm_read(SPM_ROWS), GENUINE), higher=(stpm_read(), GENUINE)), CERTAIN,
      evidence=HIGHER_OK + (NAME_OK, 'grades_verified'), slip_chips=slip_chips(),
      higher_chips=higher_chips(grades='match')),
    U('G', 'undeclared_higher', DECLARED),
]

#: Cells outside the 7 states that the table also rules on (grade differences, Q4, Q6).
EXTRA = [
    # Table F before submit: the live rule requires the higher results, so none on file is Fail.
    R('F', 'checked_before_submit', Case(SPM_HELD, DEGREE, slip=(spm_read(SPM_ROWS), GENUINE)), FAIL,
      unresolved=('higher_results_missing',), slip_chips=slip_chips()),
    # Q1 review (2026-11-13): the slip prints SIX subjects, the read caught five, all five typed found.
    # The sixth row was never seen, so no green Subjects chip and at best Probable, the reason named.
    R('A', 'short_read_printed_count', Case(SPM_HELD, POST_SPM, slip=(spm_read(SPM_ROWS, 'ENAM'), GENUINE)),
      PROBABLE, unresolved=('academic_slip_rows_unread',), evidence=(NAME_OK,),
      slip_chips=slip_chips(subjects='pending')),
    R('F', 'short_read_printed_count', Case(SPM_HELD, DEGREE, slip=(spm_read(SPM_ROWS, 'ENAM'), GENUINE),
                                            stage=SUBMITTED), UNSURE,
      unresolved=(NOT_DECLARED, 'academic_slip_rows_unread'), evidence=(NAME_OK,),
      slip_chips=slip_chips(subjects='pending')),
    # The printed count met (six printed, six read): a full read, Certain - so the row above is the count.
    R('A', 'full_read_printed_count', Case({**SPM_HELD, 'grades': {**SPM_TYPED, 'chem': 'A'}}, POST_SPM,
                                           slip=(spm_read(SPM_ROWS + [{'subject': 'KIMIA', 'grade': 'A'}], 'ENAM'),
                                                 GENUINE)),
      CERTAIN, evidence=(NAME_OK, 'grades_verified'), slip_chips=slip_chips()),
    # Q3 review (2026-11-13): an AI read that skipped a row (3 of 4, Pengajian Am read, every row
    # recognised) never calls the typed subject it skipped "not on the slip": amber, named.
    R('B', 'skipped_row_ai_read', Case(STPM_HELD, DEGREE, higher=(stpm_read(STPM_ROWS[:3]), GENUINE)), PROBABLE,
      unresolved=('academic_grades_unchecked',), evidence=HIGHER_OK, higher_chips=higher_chips(grades='pending')),
    R('B', 'extra_typed_ai_read', Case({**STPM_HELD, 'stpm_grades': {**STPM_GRADES, 'BIOLOGY': 'C'}}, DEGREE,
                                       higher=(stpm_read(), GENUINE)), PROBABLE,
      unresolved=('academic_grades_unchecked',), evidence=HIGHER_OK, higher_chips=higher_chips(grades='pending')),
    # Table B grade difference, Q4 (changed 2026-11-13): a +/- STPM difference (typed A, slip A-) on an
    # AI read is amber "check by eye"; the PNGK it moves is still a red CGPA difference.
    R('B', 'pm_grade_ai_read', Case({**STPM_HELD, 'stpm_grades': {**STPM_GRADES, 'PHYSICS': 'A'}}, DEGREE,
                                    higher=(stpm_read(), GENUINE)), PROBABLE,
      unresolved=('higher_results_grade_uncertain', 'higher_results_cgpa_mismatch'), evidence=HIGHER_OK[:2],
      higher_chips=higher_chips(cgpa='mismatch', grades='pending')),
    # Q4, the +/- alone: the slip's PNGK matches her typed grades (3.75), so the amber difference is
    # the ONLY thing holding the card from Certain.
    R('B', 'pm_grade_only', Case({**STPM_HELD, 'stpm_grades': {**STPM_GRADES, 'PHYSICS': 'A'}}, DEGREE,
                                 higher=(stpm_read(cgpa='3.75'), GENUINE)), PROBABLE,
      unresolved=('higher_results_grade_uncertain',), evidence=HIGHER_OK,
      higher_chips=higher_chips(grades='pending')),
    # Q4: the same difference on the deterministic exact read (letter and point agree) stays red.
    R('B', 'pm_grade_exact_read', Case({**STPM_HELD, 'stpm_grades': {**STPM_GRADES, 'PHYSICS': 'A'}}, DEGREE,
                                       higher=(stpm_read(), GENUINE, EXACT_READ)), PROBABLE,
      unresolved=('higher_results_grade_mismatch', 'higher_results_cgpa_mismatch'), evidence=HIGHER_OK[:2],
      higher_chips=higher_chips(cgpa='mismatch', grades='mismatch')),
    # Q6 (changed 2026-11-13): a higher result in the SPM slot of a tertiary holder is named, but does
    # not hold a clean higher card.
    R('G', 'higher_in_spm_slot', Case(STPM_HELD, DEGREE, slip=(stpm_read(), None),
                                      higher=(stpm_read(), GENUINE)), CERTAIN,
      unresolved=('results_slip_is_higher',), evidence=HIGHER_OK + (NAME_OK,),
      slip_chips=slip_chips(subjects='not_spm', results='not_spm'), higher_chips=higher_chips(grades='match')),
]


def _academic(app):
    return next(f for f in build_verdict(ScholarshipApplication.objects.get(pk=app.pk)) if f['fact'] == 'academic')


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
class SlipCheckMatrix(TestCase):
    def _check(self, row):
        c = row.case
        app = _app(c.profile, c.plan, c.stage)
        slip = _doc(app, 'results_slip', *c.slip) if c.slip else None
        higher = _doc(app, 'higher_results', *c.higher) if c.higher else None
        fact = _academic(app)
        got = {
            'band': fact['status'],
            'unresolved': {i['code'] for i in fact['unresolved']},
            'evidence': {i['code'] for i in fact['evidence']},
            'slip_chips': {k: student_slip_check(slip)[k] for k in row.slip_chips} if slip else {},
            'higher_chips': {k: student_higher_check(higher)[k] for k in row.higher_chips} if higher else {},
        }
        want = {'band': row.band, 'unresolved': set(row.unresolved), 'evidence': set(row.evidence),
                'slip_chips': row.slip_chips, 'higher_chips': row.higher_chips}
        return [f'{row.id} {k}: got {got[k]!r}, want {want[k]!r}' for k in want if got[k] != want[k]]

    def test_every_reachable_cell(self):
        # Every cell is checked and every difference reported at once (one cell's change names itself).
        wrong = [line for row in MATRIX + EXTRA if not row.unreachable for line in self._check(row)]
        self.assertEqual(wrong, [], '\n'.join(wrong))

    def test_the_matrix_has_one_row_per_cell(self):
        cells = [(r.table, r.state) for r in MATRIX]
        self.assertEqual(len(cells), len(set(cells)))
        self.assertEqual(set(cells), {(t, s) for t in 'ABCDEFG' for s in STATES})
        self.assertEqual(sum(1 for r in MATRIX if r.unreachable), 21)     # Q8: 21 cannot happen

    # ── Q8: the unreachable cells, each shown to be unreachable ──

    def test_not_final_is_matriculation_and_polytechnic_only(self):
        # A2, B2, E2, G2: the only pages read as "not final" are matriculation / polytechnic ones.
        self.assertTrue(NOT_FINAL_SEEN)
        self.assertTrue(all(s.split('_')[0] in ('matric', 'poly') for s in NOT_FINAL_SEEN))

    def test_cgpa_routes_compare_no_subject(self):
        # C/D/E short read, extra typed, subject missing: a CGPA-route read with subject rows and a
        # typed STPM list still compares no subject.
        for held, kind in ((MATRIC_HELD, 'matric'), (DIPLOMA_HELD, 'diploma'), (ASASI_HELD, 'asasi')):
            with self.subTest(kind):
                app = _app({**held, 'stpm_grades': STPM_GRADES}, DEGREE)
                doc = _doc(app, 'higher_results', {**cgpa_read(kind, '3.50'), 'results': STPM_ROWS})
                chk = student_higher_check(doc)
                self.assertEqual((chk['grades_status'], chk['missing'], chk['mismatched']), ('', [], []))

    def test_a_tertiary_holder_is_never_undeclared(self):
        # B7, C7, D7, E7, G7: the undeclared state needs SPM-only results held.
        from apps.scholarship.higher_owed import declared_kind
        for held in (STPM_HELD, MATRIC_HELD, DIPLOMA_HELD, ASASI_HELD):
            with self.subTest(held['exam_type']):
                self.assertTrue(declared_kind(_app(held, DEGREE)))

    def test_matriculation_and_diploma_store_no_suspect(self):
        # C3, D3, E3: the matric / polytechnic scorer returns genuine, a not-final ruling or nothing -
        # never suspect - on any page, a weak or forged-looking one included; Asasi and a UiTM
        # diploma are never scored at all.
        from apps.scholarship.genuineness.matric_poly_doc import matric_poly_higher_genuineness as score
        for text in PAGES_NEVER_SUSPECT:
            with self.subTest(text[:40]):
                self.assertNotEqual(score(text).get('status'), 'suspect')
        for text in (ASASI_PAGE, UITM_DIPLOMA_PAGE):
            with self.subTest(text[:40]):
                self.assertEqual(score(text), {})

    def test_every_unreachable_cell_has_a_probe(self):
        # Q8: each "cannot happen" reason is one a probe above shows; no cell is waved through.
        probed = {NO_FINAL_RULE, NO_SUBJECTS, DECLARED, *UNSCORED_REASONS}
        self.assertEqual({r.unreachable for r in MATRIX if r.unreachable} - probed, set())


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
class Q5UnscoredHigherResults(TestCase):
    """Q5 (keep, owner 2026-11-13): Asasi and a non-polytechnic Diploma can never be scored, so even a
    clean read stops at Probable, with "not checked" said on the card."""

    def test_unscored_asasi_and_diploma_stop_at_probable(self):
        for held, kind, cgpa in ((ASASI_HELD, 'asasi', '3.40'), (DIPLOMA_HELD, 'diploma', '3.20')):
            with self.subTest(kind):
                app = _app({**held, 'higher_institution_type': 'private'}, DEGREE)
                _doc(app, 'higher_results', cgpa_read(kind, cgpa))
                fact = _academic(app)
                self.assertEqual(fact['status'], PROBABLE)
                self.assertIn('higher_results_not_checked', {i['code'] for i in fact['evidence']})


#: Pages fed to the matric / polytechnic scorer (C3, D3): weak, partial and forged-looking ones.
PAGES_NEVER_SUSPECT = (
    'KEMENTERIAN PENDIDIKAN MALAYSIA BAHAGIAN MATRIKULASI TRANSKRIP AKADEMIK SEMESTER I SEMESTER II '
    'MATA NILAIAN PNGK 3.50',
    'BAHAGIAN MATRIKULASI SLIP KEPUTUSAN PEPERIKSAAN SEMESTER I',
    'POLITEKNIK SULTAN SALAHUDDIN ABDUL AZIZ SHAH TRANSKRIP AKADEMIK CODE COURSE CREDIT GRADE CGPA 3.20',
    'TRANSKRIP AKADEMIK DIPLOMA PNGK 4.00 LULUS',
)
ASASI_PAGE = 'UNIVERSITI MALAYA PUSAT ASASI SAINS ASASI SAINS HAYAT KEPUTUSAN PEPERIKSAAN PNGK 3.40'
UITM_DIPLOMA_PAGE = 'UNIVERSITI TEKNOLOGI MARA DIPLOMA SAINS TRANSKRIP AKADEMIK PNGK 3.20'
UNSCORED_REASONS = ('matriculation pages are stored genuine or not checked, never suspect (ruling 4, 2026-10-29)',
                    'diploma pages are stored genuine or not checked, never suspect (ruling 4, 2026-10-29)',
                    'no Asasi page is ever scored')


class RouteCoverage(TestCase):
    """Static: every value `results_route.destination()` (and `degree_bound()`) can return, for
    every results-held kind, maps to a table that has all seven states."""

    #: (results held, destination) -> table. Tertiary holders read the higher card on any route.
    TABLE_FOR = {('spm', results_route.POST_SPM): 'A', ('spm', results_route.UNDECIDED): 'A',
                 ('spm', results_route.DEGREE): 'F'}
    TABLE_FOR.update({(k, d): t for k, t in (('stpm', 'B'), ('matric', 'C'), ('diploma', 'D'), ('asasi', 'E'))
                      for d in (results_route.DEGREE, results_route.POST_SPM, results_route.UNDECIDED)})

    def _returned(self, fn):
        """The module constants `fn` can return (the names it assigns to `out` / returns)."""
        tree = ast.parse(inspect.getsource(fn).lstrip())
        names = set()
        for node in ast.walk(tree):
            value = node.value if isinstance(node, (ast.Assign, ast.Return)) else None
            if isinstance(node, ast.Assign) and not any(getattr(t, 'id', '') == 'out' for t in node.targets):
                value = None
            if value is not None:
                names |= {n.id for n in ast.walk(value) if isinstance(n, ast.Name)
                          and isinstance(getattr(results_route, n.id, None), str)}
        return {getattr(results_route, n) for n in names}

    def test_every_destination_has_a_table(self):
        values = self._returned(results_route.destination)
        self.assertEqual(values, {results_route.DEGREE, results_route.POST_SPM, results_route.UNDECIDED})
        tables = {r.table for r in MATRIX}
        for held in ('spm', 'stpm', 'matric', 'diploma', 'asasi'):
            for dest in values:
                with self.subTest(held=held, dest=dest):
                    self.assertIn(self.TABLE_FOR[(held, dest)], tables)

    def test_degree_bound_has_a_table_both_ways(self):
        # The REAL degree_bound on every SPM-holder row's own application: True on each Table F row,
        # False on each Table A row - so both answers have a table and no row sits in the wrong one.
        rows = [r for r in MATRIX + EXTRA if r.table in ('A', 'F') and r.case]
        seen = set()
        for r in rows:
            with self.subTest(r.id):
                got = results_route.degree_bound(_app(r.case.profile, r.case.plan, r.case.stage))
                self.assertEqual(got, r.table == 'F')
                seen.add(got)
        self.assertEqual(seen, {True, False})
