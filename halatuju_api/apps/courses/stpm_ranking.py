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

from .ranking_engine import FIELD_KEY_MAP

BASE_SCORE = 50
CGPA_MARGIN_CAP = 1.0
CGPA_MARGIN_MULTIPLIER = 20  # points per 1.0 CGPA margin
FIELD_MATCH_BONUS = 10
INTERVIEW_PENALTY = 3


def _match_field_interest(field_key: str, signals: Dict) -> bool:
    """Check if course field_key matches student's field interests."""
    field_interests = signals.get('field_interest', {})
    if not field_interests or not field_key:
        return False
    for sig_name in field_interests:
        keys = FIELD_KEY_MAP.get(sig_name, [])
        if field_key in keys:
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

    # 2. Field interest match (uses taxonomy field_key)
    if _match_field_interest(course.get('field_key', ''), signals):
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
