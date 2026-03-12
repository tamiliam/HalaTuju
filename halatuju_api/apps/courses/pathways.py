"""
Pre-university pathway eligibility engine for Matriculation and STPM.

Pure Python — no Django dependencies. Ported from halatuju-web/src/lib/pathways.ts.
Uses backend grade keys (math, addmath, chem, etc.) not frontend keys.

Input: student's SPM grades dict + CoQ score.
Output: eligibility + merit/mata_gred per pathway track.
"""

# ── Grade Point Scales ───────────────────────────────────────────────────

# Matriculation merit scale (from matrikulasi.moe.gov.my calculator)
MATRIC_GRADE_POINTS = {
    'A+': 25, 'A': 24, 'A-': 23, 'B+': 22, 'B': 21,
    'C+': 20, 'C': 19, 'D': 18, 'E': 17, 'G': 0,
}

# STPM (Form 6) mata gred scale — lower is better
STPM_MATA_GRED = {
    'A+': 1, 'A': 1, 'A-': 2, 'B+': 3, 'B': 4,
    'C+': 5, 'C': 6, 'D': 7, 'E': 8, 'G': 9,
}

# Grade ordering for comparison (lower index = better grade)
GRADE_ORDER = ['A+', 'A', 'A-', 'B+', 'B', 'C+', 'C', 'D', 'E', 'G']


def is_credit(grade):
    """Credit = C or better (mata gred <= 6)."""
    mg = STPM_MATA_GRED.get(grade)
    return mg is not None and mg <= 6


def meets_min(grade, min_grade):
    """Check if grade meets or exceeds the minimum threshold."""
    try:
        grade_idx = GRADE_ORDER.index(grade)
        min_idx = GRADE_ORDER.index(min_grade)
    except ValueError:
        return False
    return grade_idx <= min_idx  # lower index = better grade


# ── Matriculation ────────────────────────────────────────────────────────

MATRIC_TRACKS = [
    {'id': 'sains', 'name': 'Science', 'name_ms': 'Sains', 'name_ta': 'அறிவியல்'},
    {'id': 'kejuruteraan', 'name': 'Engineering', 'name_ms': 'Kejuruteraan', 'name_ta': 'பொறியியல்'},
    {'id': 'sains_komputer', 'name': 'Computer Science', 'name_ms': 'Sains Komputer', 'name_ta': 'கணினி அறிவியல்'},
    {'id': 'perakaunan', 'name': 'Accounting', 'name_ms': 'Perakaunan', 'name_ta': 'கணக்கியல்'},
]

# Subject requirements per track (using backend keys)
MATRIC_REQUIREMENTS = {
    'sains': [
        {'subject_id': 'math', 'min_grade': 'B'},
        {'subject_id': 'addmath', 'min_grade': 'C'},
        {'subject_id': 'chem', 'min_grade': 'C'},
        {'subject_id': 'phy', 'min_grade': 'C', 'alternatives': ['bio']},
    ],
    'kejuruteraan': [
        {'subject_id': 'math', 'min_grade': 'B'},
        {'subject_id': 'addmath', 'min_grade': 'C'},
        {'subject_id': 'phy', 'min_grade': 'C'},
        # 4th: any elective with min C — handled by slot filling
    ],
    'sains_komputer': [
        {'subject_id': 'math', 'min_grade': 'C'},
        {'subject_id': 'addmath', 'min_grade': 'C'},
        {'subject_id': 'comp_sci', 'min_grade': 'C'},
        # 4th: any elective with min C — handled by slot filling
    ],
    'perakaunan': [
        {'subject_id': 'math', 'min_grade': 'C'},
        # 3 electives with min C — handled by slot filling
    ],
}

_MATRIC_TRACK_MAP = {t['id']: t for t in MATRIC_TRACKS}


def find_best_elective(grades, exclude_ids, min_grade):
    """Find the best unused subject meeting min_grade.

    Returns {'id': str, 'grade': str} or None.
    """
    best = None
    for subj_id, grade in grades.items():
        if subj_id in exclude_ids:
            continue
        if not meets_min(grade, min_grade):
            continue
        pts = MATRIC_GRADE_POINTS.get(grade, 0)
        if best is None or pts > best[2]:
            best = (subj_id, grade, pts)
    if best is None:
        return None
    return {'id': best[0], 'grade': best[1]}


def check_matric_track(track_id, grades, coq_score):
    """Check eligibility for a specific Matric track.

    Args:
        track_id: One of 'sains', 'kejuruteraan', 'sains_komputer', 'perakaunan'.
        grades: Dict mapping backend subject keys to grade strings.
        coq_score: Co-curricular score (0-10).

    Returns:
        Dict with pathway result.
    """
    track = _MATRIC_TRACK_MAP[track_id]
    reqs = MATRIC_REQUIREMENTS[track_id]
    used_subjects = []  # list of {'id': str, 'grade': str}
    used_ids = set()

    # Check fixed requirements
    for req in reqs:
        candidates = [req['subject_id']] + req.get('alternatives', [])
        found = False
        for subj_id in candidates:
            grade = grades.get(subj_id)
            if grade and meets_min(grade, req['min_grade']):
                used_subjects.append({'id': subj_id, 'grade': grade})
                used_ids.add(subj_id)
                found = True
                break
        if not found:
            has_subject = any(grades.get(sid) for sid in candidates)
            return {
                'pathway': 'matric',
                'track_id': track_id,
                'track_name': track['name'],
                'track_name_ms': track['name_ms'],
                'track_name_ta': track['name_ta'],
                'eligible': False,
                'merit': None,
                'mata_gred': None,
                'max_mata_gred': None,
                'reason': 'pathways.gradeTooLow' if has_subject else 'pathways.subjectMissing',
            }

    # Fill remaining slots with best electives (always need 4 total)
    slots_needed = 4 - len(used_subjects)
    for _ in range(slots_needed):
        elective = find_best_elective(grades, used_ids, 'C')
        if elective is None:
            return {
                'pathway': 'matric',
                'track_id': track_id,
                'track_name': track['name'],
                'track_name_ms': track['name_ms'],
                'track_name_ta': track['name_ta'],
                'eligible': False,
                'merit': None,
                'mata_gred': None,
                'max_mata_gred': None,
                'reason': 'pathways.notEnoughElectives',
            }
        used_subjects.append(elective)
        used_ids.add(elective['id'])

    # Calculate merit
    subject_points = sum(
        MATRIC_GRADE_POINTS.get(s['grade'], 0) for s in used_subjects
    )
    academic = (subject_points / 100) * 90
    coq = min(max(coq_score, 0), 10)
    merit = min(academic + coq, 100)
    merit = round(merit * 100) / 100  # 2 decimal places

    return {
        'pathway': 'matric',
        'track_id': track_id,
        'track_name': track['name'],
        'track_name_ms': track['name_ms'],
        'track_name_ta': track['name_ta'],
        'eligible': True,
        'merit': merit,
        'mata_gred': None,
        'max_mata_gred': None,
        'reason': None,
    }


# ── STPM (Form 6) ───────────────────────────────────────────────────────

# Subject groups — student must have credits from 3 DIFFERENT groups
STPM_SCIENCE_GROUPS = [
    ['math', 'addmath'],
    ['phy'],
    ['chem'],
    ['bio'],
    ['eng_draw', 'eng_mech', 'eng_civil', 'eng_elec', 'reka_cipta',
     'sports_sci', 'srt', 'comp_sci', 'gkt'],
]

STPM_SOCSCI_GROUPS = [
    ['bm'],
    ['eng'],
    ['hist'],
    ['geo', 'psv'],
    ['islam', 'moral'],
    ['math', 'addmath'],
    ['poa'],
    ['sci', 'addsci'],
    ['ekonomi', 'business', 'keusahawanan', 'sports_sci', 'srt', 'comp_sci',
     'gkt', 'pertanian'],
]

STPM_BIDANGS = [
    {'id': 'sains', 'name': 'Science', 'name_ms': 'Sains',
     'name_ta': 'அறிவியல்', 'max_mata_gred': 18},
    {'id': 'sains_sosial', 'name': 'Social Science', 'name_ms': 'Sains Sosial',
     'name_ta': 'சமூக அறிவியல்', 'max_mata_gred': 18},
]

_STPM_BIDANG_MAP = {b['id']: b for b in STPM_BIDANGS}


def check_stpm_bidang(bidang_id, grades):
    """Check eligibility for a specific STPM bidang.

    Args:
        bidang_id: 'sains' or 'sains_sosial'.
        grades: Dict mapping backend subject keys to grade strings.

    Returns:
        Dict with pathway result.
    """
    bidang = _STPM_BIDANG_MAP[bidang_id]
    groups = STPM_SCIENCE_GROUPS if bidang_id == 'sains' else STPM_SOCSCI_GROUPS

    def _fail(reason, mata_gred=None, **extra):
        return {
            'pathway': 'stpm',
            'track_id': bidang_id,
            'track_name': bidang['name'],
            'track_name_ms': bidang['name_ms'],
            'track_name_ta': bidang['name_ta'],
            'eligible': False,
            'merit': None,
            'mata_gred': mata_gred,
            'max_mata_gred': bidang['max_mata_gred'],
            'reason': reason,
        }

    # General requirement: credit in BM
    bm_grade = grades.get('bm')
    if not bm_grade or not is_credit(bm_grade):
        return _fail('pathways.bmCreditRequired')

    # Find best credit from each group
    candidates = []  # (group_idx, subject_id, mata_gred)
    for gi, group in enumerate(groups):
        best_in_group = None
        for subj_id in group:
            grade = grades.get(subj_id)
            if not grade or not is_credit(grade):
                continue
            mg = STPM_MATA_GRED[grade]
            if best_in_group is None or mg < best_in_group[2]:
                best_in_group = (gi, subj_id, mg)
        if best_in_group:
            candidates.append(best_in_group)

    # Sort by mata gred (lowest first = best)
    candidates.sort(key=lambda c: c[2])

    if len(candidates) < 3:
        return _fail('pathways.notEnoughCredits')

    # Take best 3
    best_3 = candidates[:3]
    total_mata_gred = sum(c[2] for c in best_3)

    if total_mata_gred > bidang['max_mata_gred']:
        return _fail('pathways.mataGredTooHigh', mata_gred=total_mata_gred)

    return {
        'pathway': 'stpm',
        'track_id': bidang_id,
        'track_name': bidang['name'],
        'track_name_ms': bidang['name_ms'],
        'track_name_ta': bidang['name_ta'],
        'eligible': True,
        'merit': None,
        'mata_gred': total_mata_gred,
        'max_mata_gred': bidang['max_mata_gred'],
        'reason': None,
    }


# ── Public API ───────────────────────────────────────────────────────────

def check_all_pathways(grades, coq_score):
    """Check eligibility for all pre-university pathways.

    Args:
        grades: Dict mapping backend subject keys to grade strings.
        coq_score: Co-curricular score (0-10).

    Returns:
        List of 6 result dicts (4 matric + 2 stpm).
    """
    results = []

    for track in MATRIC_TRACKS:
        results.append(check_matric_track(track['id'], grades, coq_score))

    for bidang in STPM_BIDANGS:
        results.append(check_stpm_bidang(bidang['id'], grades))

    return results
