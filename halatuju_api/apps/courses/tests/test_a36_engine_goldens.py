"""
Audit sprint A3.6 — golden readings of the eligibility and ranking engines, over the WHOLE course set.

Written BEFORE `check_eligibility` (engine.py) and `calculate_fit_score` (ranking_engine.py) were broken
up, and passed on that code. Every reading here must stay identical after the split: the sprint is a
pure move and extract, so a changed digest means a changed rule, threshold, order, score, tie-break or
word, and the split is wrong.

What is read (all synthetic — no real student, no live data):

- ELIGIBILITY: every grade profile below x every row of the course fixtures (`courses` + `requirements`,
  loaded through the same DataFrame the app uses), the verdict AND the full audit trail (every label,
  pass/fail and reason, in order). One digest per profile.
- FIT: every signal profile below x every course, through `calculate_fit_score`, with deterministic
  synthetic course tags and institution modifiers (the fixtures carry none), the score AND the reasons.
  Plus a pre-university grid through the Asasi and Matric / STPM scorers (merit and mata gred edges).
- RANK: for every grade profile, the eligible list the eligibility route builds (merit label per course,
  PISMP de-duplication, the route's sort), then `get_ranked_results` with one signal profile: the
  ranked order, score, merit label and reasons.

The expected digests live in `fixtures/a36_engine_goldens.json`. On a mismatch the test writes what it
read to its pytest temp folder and names the file, so a reviewer can diff profile by profile.
"""
import hashlib
import json
from pathlib import Path

import pytest

from apps.courses.engine import StudentProfile, check_eligibility
from apps.courses.eligibility_service import (
    compute_course_merit, compute_student_merit, deduplicate_pismp, sort_eligible_courses,
)
from apps.courses.ranking_engine import (
    FIELD_KEY_MAP, INST_PRIORITY_MAP, calculate_asasi_fit_score, calculate_fit_score,
    calculate_matric_stpm_fit_score, get_ranked_results, sort_courses,
)
from apps.courses.tests.conftest import load_requirements_df

GOLDEN_FILE = Path(__file__).resolve().parent / 'fixtures' / 'a36_engine_goldens.json'


def _h(*parts):
    """A stable small integer from text (no `random`, so no Python-version drift)."""
    return int(hashlib.sha256('|'.join(str(p) for p in parts).encode('utf-8')).hexdigest()[:8], 16)


def _pick(options, *parts):
    return options[_h(*parts) % len(options)]


def _digest(lines):
    return hashlib.sha256('\n'.join(lines).encode('utf-8')).hexdigest()


def _dump(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


# ---------------------------------------------------------------- grade profiles (SPM)

SCIENCE = ('bm', 'eng', 'hist', 'math', 'addmath', 'phy', 'chem', 'bio', 'moral')
LADDER = ('A+', 'A', 'A-', 'B+', 'B', 'C+', 'C', 'D', 'E', 'G')


def _all(subjects, grade, **extra):
    grades = {s: grade for s in subjects}
    grades.update(extra)
    return grades


def _p(grades, gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False, bumi=False):
    return {'grades': grades, 'gender': gender, 'nationality': nationality,
            'colorblind': colorblind, 'disability': disability, 'bumiputera': bumi}


GRADE_PROFILES = {}
# The edge grades: a science-stream student with every subject at one grade, top to bottom.
for _g in LADDER:
    GRADE_PROFILES[f'science_all_{_g}'] = _p(_all(SCIENCE, _g))
GRADE_PROFILES.update({
    'science_sci_not_triple': _p({'bm': 'A', 'eng': 'B', 'hist': 'C', 'math': 'A-', 'sci': 'B+',
                                  'addsci': 'C', 'moral': 'B'}),
    'arts_high': _p(_all(('bm', 'eng', 'hist', 'math', 'ekonomi', 'geo', 'poa', 'business',
                          'lit_bm', 'psv', 'moral'), 'A-')),
    'arts_credit_edge': _p(_all(('bm', 'eng', 'hist', 'math', 'ekonomi', 'geo', 'poa', 'keusahawanan',
                                 'moral'), 'C')),
    'technical_stream': _p(_all(('bm', 'eng', 'hist', 'math', 'addmath', 'phy', 'eng_civil', 'eng_draw',
                                 'gkt', 'moral'), 'B')),
    'it_stream': _p(_all(('bm', 'eng', 'hist', 'math', 'comp_sci', 'multimedia', 'digital_gfx',
                          'sci', 'moral'), 'B+')),
    'vocational_stream': _p(_all(('bm', 'eng', 'hist', 'math', 'voc_construct', 'voc_weld', 'voc_auto',
                                  'voc_food', 'moral'), 'C+')),
    'legacy_tech_voc_keys': _p({'bm': 'C', 'eng': 'D', 'hist': 'D', 'math': 'C', 'tech': 'C',
                                'voc': 'B', 'moral': 'C'}),
    # TVET: the 3M door (BM and Maths attempted, nothing more) and its edges.
    'tvet_3m_only': _p({'bm': 'E', 'math': 'G'}),
    'tvet_bm_only': _p({'bm': 'D'}),
    'tvet_weak_passes': _p({'bm': 'D', 'eng': 'E', 'hist': 'E', 'math': 'D', 'sci': 'E', 'moral': 'D'}),
    'no_grades': _p({}),
    # Gender- and health-restricted rows.
    'female_science': _p(_all(SCIENCE, 'B+'), gender='Perempuan'),
    'female_tamil_label': _p(_all(SCIENCE, 'B'), gender='பெண்'),
    'male_english_label': _p(_all(SCIENCE, 'B'), gender='Male'),
    'unknown_gender': _p(_all(SCIENCE, 'B'), gender='X'),
    'colourblind': _p(_all(SCIENCE, 'A-'), colorblind=True),
    'disability': _p(_all(SCIENCE, 'A-'), disability=True),
    'colourblind_disability_tvet': _p({'bm': 'C', 'eng': 'D', 'math': 'C', 'sci': 'D', 'hist': 'D'},
                                      colorblind=True, disability=True),
    'non_citizen': _p(_all(SCIENCE, 'A'), nationality='Bukan Warganegara'),
    # Bumiputera-only rows (a real True opens them) and the Islamic subjects.
    'bumi_islamic': _p(_all(('bm', 'eng', 'hist', 'math', 'sci', 'islam', 'pertanian', 'addsci'), 'B',
                            islam='A'), bumi=True),
    'bumi_science': _p(_all(SCIENCE, 'A-'), bumi=True),
    # PISMP medium-of-instruction zones.
    'pismp_tamil_stream': _p(_all(('bm', 'eng', 'hist', 'math', 'sci', 'b_tamil', 'lit_tamil', 'moral'),
                                  'A', b_tamil='A+')),
    'pismp_chinese_stream': _p(_all(('bm', 'eng', 'hist', 'math', 'sci', 'b_cina', 'lit_cina', 'moral'),
                                    'A-')),
    # Mixed edges: each subject on a different boundary.
    'mixed_boundaries': _p({'bm': 'C', 'eng': 'D', 'hist': 'E', 'math': 'C+', 'addmath': 'B', 'phy': 'B+',
                            'chem': 'A-', 'bio': 'G', 'moral': 'A'}),
    'addmath_spike': _p({'bm': 'B', 'eng': 'C', 'hist': 'C', 'math': 'G', 'addmath': 'A+', 'phy': 'C',
                         'chem': 'D', 'moral': 'B'}),
})


def _student(p):
    return StudentProfile(grades=p['grades'], gender=p['gender'], nationality=p['nationality'],
                          colorblind=p['colorblind'], disability=p['disability'], bumiputera=p['bumiputera'])


# ---------------------------------------------------------------- signal profiles

SIGNAL_KEYS = {
    'work_preference_signals': ('hands_on', 'problem_solving', 'creative', 'people_helping'),
    'learning_tolerance_signals': ('learning_by_doing', 'theory_oriented', 'project_based', 'concept_first',
                                   'rote_tolerant'),
    'environment_signals': ('workshop_environment', 'high_people_environment', 'field_environment',
                            'office_environment'),
    'energy_sensitivity_signals': ('low_people_tolerance', 'physical_fatigue_sensitive',
                                   'mental_fatigue_sensitive', 'high_stamina'),
    'value_tradeoff_signals': ('income_risk_tolerant', 'stability_priority', 'pathway_priority',
                               'fast_employment_priority', 'quality_priority', 'proximity_priority',
                               'allowance_priority', 'employment_guarantee'),
}


def _signals(seed, density):
    """Deterministic signals: each key on (1-3) when its hash falls under `density` (out of 10)."""
    out = {'field_interest': {}}
    for name in sorted(FIELD_KEY_MAP):
        if _h(seed, 'field', name) % 10 < density:
            out['field_interest'][name] = 1 + _h(seed, 'fv', name) % 3
    for cat, keys in SIGNAL_KEYS.items():
        out[cat] = {k: 1 + _h(seed, cat, k) % 3 for k in keys if _h(seed, cat, k, 'on') % 10 < density}
    return out


def _all_signals(value):
    out = {'field_interest': {name: value for name in FIELD_KEY_MAP}}
    for cat, keys in SIGNAL_KEYS.items():
        out[cat] = {k: value for k in keys}
    return out


SIGNAL_PROFILES = {
    'empty': {'student_signals': {}},
    'all_on': {'student_signals': _all_signals(2)},
    'all_zero': {'student_signals': _all_signals(0)},
    'flat_no_wrapper': _signals('flat', 5),      # the "input flexibility" path: no student_signals key
}
for _i in range(12):
    SIGNAL_PROFILES[f'seeded_{_i:02d}'] = {'student_signals': _signals(f'seed{_i}', 2 + _i % 7)}


# ---------------------------------------------------------------- synthetic tags and institutions

TAG_OPTIONS = {
    'work_modality': ['hands_on', 'mixed', 'theoretical', 'theory', ''],
    'people_interaction': ['high_people', 'moderate_people', 'low_people', ''],
    'cognitive_type': ['procedural', 'abstract', 'problem_solving', ''],
    'load': ['physically_demanding', 'mentally_demanding', 'balanced_load', ''],
    'outcome': ['employment_first', 'pathway_friendly', 'regulated_profession', 'entrepreneurial',
                'industry_specific', ''],
    'environment': ['field', 'lab', 'office', 'workshop', ''],
    'credential_status': ['regulated', 'unregulated'],
    'creative_output': ['none', 'expressive', 'design'],
    'service_orientation': ['neutral', 'service'],
    'interaction_type': ['mixed', 'transactional', 'relational'],
    'career_structure': ['stable', 'volatile', 'portfolio'],
}
LEARNING_STYLES = ('project_based', 'continuous_assessment', 'assessment_heavy')

INSTITUTIONS = {
    'GI-URBAN-HIGH': ({'urban': True, 'cultural_safety_net': 'high'}, 'Penyelidikan'),
    'GI-URBAN-LOW': ({'urban': True, 'cultural_safety_net': 'low'}, 'Premier'),
    'GI-RURAL-HIGH': ({'urban': False, 'cultural_safety_net': 'high'}, 'Kolej Komuniti'),
    'GI-RURAL-MED': ({'urban': False, 'cultural_safety_net': 'medium'}, 'ILP'),
    'GI-NOMODS': ({}, 'IKBN'),
    'GI-UNKNOWN': ({'urban': True}, 'Something Else'),
}
INST_IDS = sorted(INSTITUTIONS) + [' GI-URBAN-HIGH ']   # a padded id: the scorer strips it


def _tags(course_id):
    """Deterministic tags; one course in seven has none, one in five drops the defaulted keys."""
    if _h(course_id, 'none') % 7 == 0:
        return None
    tags = {k: _pick(v, course_id, k) for k, v in TAG_OPTIONS.items()}
    tags['learning_style'] = [s for s in LEARNING_STYLES if _h(course_id, 'ls', s) % 2]
    if _h(course_id, 'sparse') % 5 == 0:
        for k in ('career_structure', 'credential_status', 'creative_output', 'service_orientation',
                  'interaction_type'):
            tags.pop(k)
    return tags


def _institution_for(course_id):
    return _pick(INST_IDS, course_id, 'inst')


# ---------------------------------------------------------------- the readings

def _requirement_rows():
    from django.apps import apps
    return [row.to_dict() for _, row in apps.get_app_config('courses').requirements_df.iterrows()]


def _courses():
    from apps.courses.models import Course
    return {c.course_id: c for c in Course.objects.all()}


def read_eligibility(rows):
    out = {}
    for name, p in GRADE_PROFILES.items():
        student = _student(p)
        lines, eligible = [], 0
        for req in rows:
            ok, audit = check_eligibility(student, req)
            eligible += bool(ok)
            lines.append(f"{req['course_id']}|{bool(ok)}|{_dump(audit)}")
        out[name] = {'eligible': eligible, 'sha256': _digest(lines)}
    return out


def read_fit(courses):
    tags_map = {cid: t for cid in courses for t in [_tags(cid)] if t is not None}
    mods = {iid: m for iid, (m, _) in INSTITUTIONS.items()}
    out = {}
    for name, profile in SIGNAL_PROFILES.items():
        lines, total = [], 0
        for cid in sorted(courses):
            field_key = courses[cid].field_key_id or ''
            score, reasons = calculate_fit_score(profile, cid, _institution_for(cid), tags_map, mods,
                                                 field_key=field_key)
            total += score
            lines.append(f'{cid}|{score}|{_dump(reasons)}')
        out[name] = {'total': total, 'sha256': _digest(lines)}
    return out


PRE_U_GRID = (
    [{'pathway_type': 'asasi', 'field': f, 'student_merit': m}
     for f in ('Kejuruteraan', 'Pengurusan Dan Strategi', 'Perubatan', 'Sains Sosial', 'Lain')
     for m in (None, 'x', 83.9, 84, 89.9, 90, 100)]
    + [{'pathway_type': 'matric', 'track_id': t, 'student_merit': m}
       for t in ('kejuruteraan', 'sains_komputer', 'perakaunan', 'sains', 'sains_sosial', '')
       for m in (None, 'x', 88.9, 89, 93.9, 94)]
    + [{'pathway_type': 'stpm', 'track_id': t, 'mata_gred': mg}
       for t in ('sains', 'sains_sosial', '')
       for mg in (None, 'x', 0, 4, 4.5, 10, 10.5, 99)]
)


def read_pre_u():
    lines = []
    for name, profile in SIGNAL_PROFILES.items():
        for i, item in enumerate(PRE_U_GRID):
            fn = calculate_asasi_fit_score if item['pathway_type'] == 'asasi' else calculate_matric_stpm_fit_score
            score, reasons = fn(item, profile)
            lines.append(f'{name}|{i}|{score}|{_dump(reasons)}')
    return {'pairs': len(lines), 'sha256': _digest(lines)}


def _eligible_items(p, rows, courses, pathway_map):
    """The eligible list the eligibility route builds for this student (views.EligibilityCheckView)."""
    import math
    data = {'grades': p['grades'], 'coq_score': 5.0}
    student_merit = compute_student_merit(data)
    student = _student(p)
    items, hashes = [], {}
    for req in rows:
        cid = req.get('course_id', '')
        if req.get('source_type') == 'pismp':
            sgr = req.get('subject_group_req')
            hashes[cid] = 'null' if sgr is None else (
                json.dumps(sgr, sort_keys=True) if not isinstance(sgr, str) else sgr)
        if not check_eligibility(student, req)[0]:
            continue
        source_type = req.get('source_type', 'poly')
        cutoff = req.get('merit_cutoff')
        if cutoff is not None and (math.isnan(cutoff) or math.isinf(cutoff)):
            cutoff = None
        merit = compute_course_merit(req.get('merit_type', 'standard'), source_type, cutoff,
                                     student_merit, cid, data, student.grades)
        if merit is None:
            continue
        course = courses.get(cid)
        item = {
            'course_id': cid, 'course_name': course.course if course else cid,
            'field_key': (course.field_key_id or '') if course else '', 'source_type': source_type,
            'pathway_type': pathway_map.get(cid, source_type), 'institution_id': _institution_for(cid),
            'merit_cutoff': merit['merit_cutoff'], 'student_merit': merit['student_merit'],
            'merit_label': merit['merit_label'],
        }
        if merit['track_id']:  # Matric / Form 6 rows, as the view adds them
            item['track_id'], item['mata_gred'] = merit['track_id'], merit['mata_gred']
        items.append(item)
    return sort_eligible_courses(deduplicate_pismp(items, hashes))


def read_rank(rows, courses):
    from django.apps import apps
    pathway_map = apps.get_app_config('courses').course_pathway_map
    tags_map = {cid: t for cid in courses for t in [_tags(cid)] if t is not None}
    mods = {iid: m for iid, (m, _) in INSTITUTIONS.items()}
    subcats = {iid: s for iid, (_, s) in INSTITUTIONS.items()}
    signal_names = sorted(SIGNAL_PROFILES)
    out = {}
    for i, (name, p) in enumerate(GRADE_PROFILES.items()):
        items = _eligible_items(p, rows, courses, pathway_map)
        signals = SIGNAL_PROFILES[signal_names[i % len(signal_names)]]
        ranked = get_ranked_results(items, signals, tags_map, mods, subcats)['ranked']
        lines = [f"{r['course_id']}|{r['fit_score']}|{r['merit_label']}|{_dump(r['fit_reasons'])}"
                 for r in ranked]
        # sort_courses alone, on the route's order, so a tie-break change cannot hide behind the scorer.
        lines += [r['course_id'] for r in sort_courses(ranked[::-1], subcats)]
        out[name] = {'ranked': len(ranked), 'sha256': _digest(lines)}
    return out


@pytest.mark.django_db
class TestA36EngineGoldens:
    """Golden eligibility, fit and rank readings, identical before and after the A3.6 split."""

    @pytest.fixture(autouse=True)
    def load_data(self):
        from io import StringIO

        from django.core.management import call_command
        call_command('loaddata', 'courses', 'requirements', stdout=StringIO(), verbosity=0)
        load_requirements_df()

    @pytest.fixture
    def golden(self):
        return json.loads(GOLDEN_FILE.read_text(encoding='utf-8'))

    @staticmethod
    def _check(name, actual, expected, tmp_path):
        if actual != expected:
            out = tmp_path / f'a36_{name}_actual.json'
            out.write_text(json.dumps(actual, indent=1, sort_keys=True, ensure_ascii=False), encoding='utf-8')
            changed = sorted(k for k in set(actual) | set(expected) if actual.get(k) != expected.get(k))
            pytest.fail(f'{name} golden changed for {changed[:20]} — actual readings in {out}')

    def test_the_course_set_is_the_whole_catalogue(self, golden):
        rows = _requirement_rows()
        assert len(rows) == golden['courses'] == len(_courses())
        assert len(GRADE_PROFILES) == golden['grade_profiles']
        assert len(SIGNAL_PROFILES) == golden['signal_profiles']

    def test_eligibility_and_audit_trail_per_profile(self, golden, tmp_path):
        self._check('eligibility', read_eligibility(_requirement_rows()), golden['eligibility'], tmp_path)

    def test_fit_score_and_reasons_per_signal_profile(self, golden, tmp_path):
        self._check('fit', read_fit(_courses()), golden['fit'], tmp_path)

    def test_pre_university_scorers(self, golden, tmp_path):
        self._check('pre_u', read_pre_u(), golden['pre_u'], tmp_path)

    def test_ranked_order_per_profile(self, golden, tmp_path):
        self._check('rank', read_rank(_requirement_rows(), _courses()), golden['rank'], tmp_path)
