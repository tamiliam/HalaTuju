"""Unified pre-university scoring: Asasi, Matriculation and STPM fit scores.

Moved verbatim out of `ranking_engine.py` (audit sprint A3.6, a moves-only split: the file was a
ledgered oversize file). `ranking_engine.py` re-exports every name, so every
`from apps.courses.ranking_engine import ...` is unchanged. Nothing here changed.
"""

from .pathways import MATRIC_TRACKS, STPM_BIDANGS
from .ranking_constants import BASE_SCORE

# The English track names the fit reason shows ('pathway:track_id' -> name); fit reasons are
# English, like every other fit reason.
_TRACK_NAMES = {
    **{f"matric:{t['id']}": t['name'] for t in MATRIC_TRACKS},
    **{f"stpm:{b['id']}": b['name'] for b in STPM_BIDANGS},
}

# --- Pre-University Unified Scoring (Asasi) ---
# See docs/plans/2026-03-11-pre-u-scoring-design.md
# Asasi is the most prestigious pre-u pathway.
ASASI_PRESTIGE_BONUS = 12
ASASI_SIGNAL_CAP = 6

# Asasi field → quiz field signal mapping
ASASI_FIELD_MAP = {
    'Kejuruteraan': ['field_mechanical', 'field_electrical', 'field_civil', 'field_heavy_industry'],
    'Pengurusan Dan Strategi': ['field_business'],
    'Perubatan': ['field_health'],
    'Sains Sosial': [],  # uses creative signal instead
}


def asasi_academic_bonus(student_merit):
    """Academic bonus for Asasi based on student merit (0-100)."""
    try:
        m = float(student_merit or 0)
    except (TypeError, ValueError):
        return 0
    if m >= 90:
        return 8
    if m >= 84:
        return 4
    return 0


def asasi_field_preference(course_field, signals):
    """Field preference bonus (+3) if quiz field interest matches Asasi variant."""
    if not signals:
        return 0
    field_interest = signals.get('field_interest', {})

    # Social science: boost if creative work preference
    if course_field == 'Sains Sosial':
        creative = signals.get('work_preference_signals', {}).get('creative', 0)
        return 3 if creative > 0 else 0

    mapped = ASASI_FIELD_MAP.get(course_field, [])
    for f in mapped:
        if field_interest.get(f, 0) > 0:
            return 3
    return 0


def asasi_signal_adjustment(course_field, signals):
    """Unified signal adjustment for Asasi (same logic as frontend Matric/STPM)."""
    if not signals:
        return 0

    def get_sig(cat, key):
        return signals.get(cat, {}).get(key, 0)

    is_socsci = course_field == 'Sains Sosial'
    adj = 0

    # Work style
    if get_sig('work_preference_signals', 'problem_solving') > 0 and not is_socsci:
        adj += 2
    if get_sig('work_preference_signals', 'creative') > 0 and is_socsci:
        adj += 1
    if get_sig('work_preference_signals', 'hands_on') > 0:
        adj -= 1

    # Environment
    if get_sig('environment_signals', 'workshop_environment') > 0:
        adj -= 1
    if get_sig('environment_signals', 'field_environment') > 0:
        adj -= 1

    # Learning style
    if get_sig('learning_tolerance_signals', 'concept_first') > 0:
        adj += 2
    if get_sig('learning_tolerance_signals', 'rote_tolerant') > 0:
        adj += 1
    if get_sig('learning_tolerance_signals', 'learning_by_doing') > 0:
        adj -= 1

    # Values (Asasi doesn't get allowance or proximity bonuses — those are Matric/STPM only)
    if get_sig('value_tradeoff_signals', 'pathway_priority') > 0:
        adj += 3
    if get_sig('value_tradeoff_signals', 'fast_employment_priority') > 0:
        adj -= 2
    if get_sig('value_tradeoff_signals', 'quality_priority') > 0:
        adj += 2
    if get_sig('value_tradeoff_signals', 'employment_guarantee') > 0:
        adj -= 1

    # Energy
    if get_sig('energy_sensitivity_signals', 'mental_fatigue_sensitive') > 0:
        adj -= 2
    if get_sig('energy_sensitivity_signals', 'high_stamina') > 0:
        adj += 1

    return max(min(adj, ASASI_SIGNAL_CAP), -ASASI_SIGNAL_CAP)


def calculate_asasi_fit_score(item, student_profile):
    """
    Calculate fit score for Asasi courses using the unified pre-u scoring.
    Replaces generic course-tag matching for pathway_type == 'asasi'.
    """
    signals = student_profile.get('student_signals', student_profile)
    course_field = item.get('field', '')
    student_merit = item.get('student_merit', 0)

    score = BASE_SCORE + ASASI_PRESTIGE_BONUS
    score += asasi_academic_bonus(student_merit)
    score += asasi_field_preference(course_field, signals)
    score += asasi_signal_adjustment(course_field, signals)

    reasons = ["Pre-university pathway to degree programmes"]
    if asasi_field_preference(course_field, signals) > 0:
        reasons.append(f"matches your interest in {course_field}")

    return score, reasons

# --- Pre-University Unified Scoring (Matric / STPM) ---
# See docs/plans/2026-03-11-pre-u-scoring-design.md
MATRIC_PRESTIGE_BONUS = 8
STPM_PRESTIGE_BONUS = 5
PRE_U_SIGNAL_CAP = 6

# Track → quiz field signal mapping (key = "pathway:track_id")
TRACK_FIELD_MAP = {
    'matric:kejuruteraan': ['field_mechanical', 'field_electrical', 'field_civil', 'field_heavy_industry'],
    'matric:sains_komputer': ['field_digital'],
    'matric:perakaunan': ['field_business'],
    'matric:sains': ['field_health', 'field_agriculture'],
    'stpm:sains': ['field_health', 'field_agriculture'],
    'stpm:sains_sosial': [],  # uses creative signal instead
}


def matric_academic_bonus(student_merit):
    """Academic bonus for Matric based on student merit (0-100)."""
    try:
        m = float(student_merit or 0)
    except (TypeError, ValueError):
        return 0
    if m >= 94:
        return 8
    if m >= 89:
        return 4
    return 0


def stpm_academic_bonus(mata_gred):
    """Academic bonus for STPM based on mata gred (lower is better)."""
    try:
        mg = float(mata_gred or 99)
    except (TypeError, ValueError):
        return 0
    if mg <= 4:
        return 8
    if mg <= 10:
        return 4
    return 0


def pre_u_field_preference(track_id, pathway, signals):
    """Field preference bonus (+3) if quiz field interest matches track variant."""
    if not signals:
        return 0

    is_socsci = track_id == 'sains_sosial'
    if is_socsci:
        creative = signals.get('work_preference_signals', {}).get('creative', 0)
        return 3 if creative > 0 else 0

    key = f'{pathway}:{track_id}'
    mapped = TRACK_FIELD_MAP.get(key, [])
    field_interest = signals.get('field_interest', {})
    for f in mapped:
        if field_interest.get(f, 0) > 0:
            return 3
    return 0


def pre_u_signal_adjustment(track_id, pathway, signals):
    """Unified signal adjustment for Matric/STPM (ported from pathways.ts)."""
    if not signals:
        return 0

    def get_sig(cat, key):
        return signals.get(cat, {}).get(key, 0)

    is_matric = pathway == 'matric'
    is_socsci = track_id == 'sains_sosial'
    adj = 0

    # Work style
    if get_sig('work_preference_signals', 'problem_solving') > 0 and not is_socsci:
        adj += 2
    if get_sig('work_preference_signals', 'creative') > 0 and is_socsci:
        adj += 1
    if get_sig('work_preference_signals', 'hands_on') > 0:
        adj -= 1

    # Environment
    if get_sig('environment_signals', 'workshop_environment') > 0:
        adj -= 1
    if get_sig('environment_signals', 'field_environment') > 0:
        adj -= 1

    # Learning style
    if get_sig('learning_tolerance_signals', 'concept_first') > 0:
        adj += 2
    if get_sig('learning_tolerance_signals', 'rote_tolerant') > 0:
        adj += 1
    if get_sig('learning_tolerance_signals', 'learning_by_doing') > 0:
        adj -= 1

    # Values
    if get_sig('value_tradeoff_signals', 'pathway_priority') > 0:
        adj += 3
    if get_sig('value_tradeoff_signals', 'fast_employment_priority') > 0:
        adj -= 2
    if get_sig('value_tradeoff_signals', 'quality_priority') > 0:
        adj += 2
    if get_sig('value_tradeoff_signals', 'allowance_priority') > 0 and is_matric:
        adj += 2
    if get_sig('value_tradeoff_signals', 'proximity_priority') > 0 and not is_matric:
        adj += 1
    if get_sig('value_tradeoff_signals', 'employment_guarantee') > 0:
        adj -= 1

    # Energy
    if get_sig('energy_sensitivity_signals', 'mental_fatigue_sensitive') > 0:
        adj -= 2
    if get_sig('energy_sensitivity_signals', 'high_stamina') > 0:
        adj += 1

    return max(min(adj, PRE_U_SIGNAL_CAP), -PRE_U_SIGNAL_CAP)


def calculate_matric_stpm_fit_score(item, student_profile):
    """
    Calculate fit score for Matric/STPM courses using unified pre-u scoring.
    Replaces generic course-tag matching for pathway_type in ('matric', 'stpm').
    """
    signals = student_profile.get('student_signals', student_profile)
    pathway = item.get('pathway_type', '')
    track_id = item.get('track_id', '')

    # Base + prestige
    if pathway == 'matric':
        score = BASE_SCORE + MATRIC_PRESTIGE_BONUS
    else:
        score = BASE_SCORE + STPM_PRESTIGE_BONUS

    # Academic bonus
    if pathway == 'matric':
        score += matric_academic_bonus(item.get('student_merit', 0))
    else:
        score += stpm_academic_bonus(item.get('mata_gred', 99))

    # Field preference
    score += pre_u_field_preference(track_id, pathway, signals)

    # Signal adjustment
    score += pre_u_signal_adjustment(track_id, pathway, signals)

    reasons = ["Pre-university pathway to degree programmes"]
    if pre_u_field_preference(track_id, pathway, signals) > 0:
        reasons.append(f"matches your interest in {_TRACK_NAMES.get(f'{pathway}:{track_id}', track_id)}")

    return score, reasons
