"""
STPM course ranking engine.

Scores eligible STPM courses based on:
1. CGPA margin (student CGPA - min_cgpa) — higher margin = safer admission
2. Field interest match (course name keywords vs quiz signals)
3. Interview penalty (slight discount for courses requiring interview)

Scoring:
  BASE = 50
  CGPA margin: +20 max (10 per 0.5 margin, capped at 1.0)
  Field match: +10
  Interview: -3
"""
from typing import Dict, List, Tuple

BASE_SCORE = 50
CGPA_MARGIN_CAP = 1.0
CGPA_MARGIN_MULTIPLIER = 20  # points per 1.0 CGPA margin
FIELD_MATCH_BONUS = 10
INTERVIEW_PENALTY = 3

# Course name keywords → field interest signals
COURSE_FIELD_MAP = {
    'kejuruteraan': ['field_mechanical', 'field_electrical', 'field_civil', 'field_heavy_industry'],
    'engineering': ['field_mechanical', 'field_electrical', 'field_civil', 'field_heavy_industry'],
    'sains komputer': ['field_digital'],
    'computer science': ['field_digital'],
    'teknologi maklumat': ['field_digital'],
    'perniagaan': ['field_business'],
    'perakaunan': ['field_business'],
    'ekonomi': ['field_business', 'field_social_science'],
    'undang': ['field_social_science'],
    'pendidikan': ['field_social_science', 'field_education'],
    'seni': ['field_arts'],
    'sastera': ['field_arts'],
    'perubatan': ['field_medical', 'field_health'],
    'farmasi': ['field_health'],
    'kejururawatan': ['field_health'],
    'pertanian': ['field_agriculture'],
    'sains': ['field_science'],
    'biologi': ['field_science', 'field_health'],
    'kimia': ['field_science'],
    'fizik': ['field_science'],
    'matematik': ['field_science'],
    'senibina': ['field_architecture'],
    'alam bina': ['field_architecture'],
}


def _match_field_interest(course_name: str, signals: Dict) -> bool:
    """Check if course name keywords match student's field interests."""
    field_interests = signals.get('field_interest', {})
    if not field_interests:
        return False
    name_lower = course_name.lower()
    for keyword, fields in COURSE_FIELD_MAP.items():
        if keyword in name_lower:
            if any(f in field_interests for f in fields):
                return True
    return False


def calculate_stpm_fit_score(
    course: Dict,
    student_cgpa: float,
    signals: Dict,
) -> Tuple[float, List[str]]:
    """Calculate fit score for a single STPM course.

    Args:
        course: Eligible course dict from stpm_engine
        student_cgpa: Student's calculated STPM CGPA
        signals: Quiz signals dict (field_interest, work_preference, etc.)

    Returns:
        (score, reasons) tuple
    """
    score = BASE_SCORE
    reasons = []

    # 1. CGPA margin bonus
    margin = student_cgpa - course['min_cgpa']
    capped_margin = min(margin, CGPA_MARGIN_CAP)
    cgpa_bonus = round(capped_margin * CGPA_MARGIN_MULTIPLIER, 1)
    if cgpa_bonus > 0:
        score += cgpa_bonus
        reasons.append(f'CGPA margin: +{margin:.2f}')

    # 2. Field interest match
    if _match_field_interest(course['course_name'], signals):
        score += FIELD_MATCH_BONUS
        reasons.append('Field match')

    # 3. Interview penalty
    if course.get('req_interview', False):
        score -= INTERVIEW_PENALTY
        reasons.append('Interview required: -3')

    return round(score, 1), reasons


def get_stpm_ranked_results(
    courses: List[Dict],
    student_cgpa: float,
    signals: Dict,
) -> List[Dict]:
    """Rank eligible STPM courses by fit score.

    Args:
        courses: List of eligible course dicts
        student_cgpa: Student's STPM CGPA
        signals: Quiz signals

    Returns:
        Courses sorted by fit_score descending, each with fit_score and fit_reasons added
    """
    if not courses:
        return []

    scored = []
    for course in courses:
        fit_score, fit_reasons = calculate_stpm_fit_score(course, student_cgpa, signals)
        scored.append({**course, 'fit_score': fit_score, 'fit_reasons': fit_reasons})

    scored.sort(key=lambda c: (-c['fit_score'], c['course_name']))
    return scored
