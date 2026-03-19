"""
STPM course ranking engine (v2 — quiz-informed).

Scoring formula (design doc Section 11):
  BASE_SCORE (50)
  + CGPA_MARGIN          (max +20, unchanged from v1)
  + FIELD_MATCH           (max +12, from Q2–Q4 field_key match)
  + RIASEC_ALIGNMENT      (max +8, from subject seed + Q5 cross-domain)
  + EFFICACY_MODIFIER     (+4 to -2, from Q4 + grade analysis)
  + GOAL_ALIGNMENT        (max +4, from Q9)
  - INTERVIEW_PENALTY     (-3, unchanged)
  - RESILIENCE_DISCOUNT   (0 to -3, from Q7 vs programme difficulty)

Maximum possible: 50 + 20 + 12 + 8 + 4 + 4 - 0 = 98

Result framing modes (from Q1 crystallisation signal):
  - confirmatory: "Your profile aligns with..."
  - guided: "Based on your interests, consider these programmes"
  - discovery: "Here are fields worth exploring"
"""
from typing import Dict, List, Tuple

from .stpm_quiz_data import STPM_FIELD_KEY_MAP

# --- Constants ---
BASE_SCORE = 50

# CGPA margin
CGPA_MARGIN_CAP = 1.0
CGPA_MARGIN_MULTIPLIER = 20  # +20 max

# Field match (max +12)
FIELD_MATCH_PRIMARY = 8    # Q3 sub-field match
FIELD_MATCH_SECONDARY = 4  # Q2 broad direction match
FIELD_MATCH_CROSS = 2      # Q5 cross-domain match
FIELD_MATCH_CAP = 12

# RIASEC alignment (max +8)
RIASEC_PRIMARY_MATCH = 6
RIASEC_SECONDARY_MATCH = 3
RIASEC_CROSS_MATCH = 2
RIASEC_ALIGNMENT_CAP = 8

# Efficacy modifier (+4 to -2)
EFFICACY_SCORES = {
    'efficacy_confirmed': 4,
    'efficacy_confident': 2,
    'efficacy_open': 0,
    'efficacy_redirect': -1,
    'efficacy_uncertain': -1,
    'efficacy_mismatch': -2,
}

# Goal alignment (max +4)
GOAL_SCORES = {
    'goal_professional': {
        'high': 4,     # regulated profession + professional goal
        'moderate': 2,
        'low': 0,
    },
    'goal_postgrad': {
        'high': 4,     # research-intensive + postgrad goal
        'moderate': 2,
        'low': 0,
    },
    'goal_employment': {
        'high': 3,
        'moderate': 2,
        'low': 0,
    },
    'goal_entrepreneurial': {
        'high': 3,
        'moderate': 2,
        'low': 0,
    },
}

# Professional programmes (for goal_professional matching)
PROFESSIONAL_FIELD_KEYS = {
    'perubatan', 'farmasi', 'undang-undang',
    'mekanikal', 'elektrik', 'sivil', 'mekatronik', 'kimia-proses',
    'aero', 'marin', 'senibina',
}

# Research-intensive programmes (for goal_postgrad matching)
RESEARCH_FIELD_KEYS = {
    'sains-tulen', 'bioteknologi', 'sains-hayat',
    'it-perisian', 'kimia-proses',
}

# Business/management programmes (for goal_entrepreneurial matching)
BUSINESS_FIELD_KEYS = {
    'perniagaan', 'pengurusan', 'pemasaran', 'perakaunan', 'kewangan',
}

# Resilience discount (0 to -3)
# resilience_redirect + high difficulty = -3
# resilience_redirect + moderate difficulty = -1
# resilience_supported + high difficulty = -1
RESILIENCE_MATRIX = {
    ('resilience_redirect', 'high'): -3,
    ('resilience_redirect', 'moderate'): -1,
    ('resilience_supported', 'high'): -1,
}

INTERVIEW_PENALTY = 3

# Result framing modes
FRAMING_MODES = {
    'crystallisation_high': 'confirmatory',
    'crystallisation_moderate': 'guided',
    'crystallisation_low': 'discovery',
}


def _get_field_match_score(
    course_field_key: str,
    signals: Dict,
) -> Tuple[float, str]:
    """
    Calculate field match score from Q2–Q4 signals.

    Returns (score, reason_label).
    Primary match (Q3 field_key signal): +8
    Secondary match (Q2 broad field_interest via STPM_FIELD_KEY_MAP): +4
    Cross-domain match (Q5): +2
    Capped at +12.
    """
    if not course_field_key:
        return 0, ''

    score = 0

    # Q3 primary field_key match (e.g. field_key_mekanikal → ['mekanikal', 'automotif'])
    field_key_signals = signals.get('field_key', {})
    for sig_name, _weight in field_key_signals.items():
        matched_keys = STPM_FIELD_KEY_MAP.get(sig_name, [])
        if course_field_key in matched_keys:
            score += FIELD_MATCH_PRIMARY
            break

    # Q2 secondary field_interest match (broader — field_engineering → multiple keys)
    if score < FIELD_MATCH_PRIMARY:
        field_interests = signals.get('field_interest', {})
        for sig_name in field_interests:
            # Map Q2 field_interest to field_keys via STPM_FIELD_KEY_MAP
            # field_engineering → field_key_mekanikal, field_key_elektrik, etc.
            for fk_signal, fk_list in STPM_FIELD_KEY_MAP.items():
                if course_field_key in fk_list:
                    # Check if this fk_signal's parent field_interest matches
                    parent = _field_key_to_interest(fk_signal)
                    if parent and parent in field_interests:
                        score += FIELD_MATCH_SECONDARY
                        break
            if score >= FIELD_MATCH_SECONDARY:
                break

    # Q5 cross-domain RIASEC → field_key match
    cross_signals = signals.get('cross_domain', {})
    if cross_signals:
        from .management.commands.enrich_stpm_riasec import FIELD_KEY_TO_RIASEC
        course_riasec = FIELD_KEY_TO_RIASEC.get(course_field_key, '')
        for sig_name in cross_signals:
            # cross_E → 'E'
            cross_type = sig_name.replace('cross_', '')
            if cross_type == course_riasec:
                score += FIELD_MATCH_CROSS
                break

    return min(score, FIELD_MATCH_CAP), 'Field match' if score > 0 else ''


# Map field_key signals back to their parent field_interest
_FK_TO_INTEREST = {
    # Engineering sub-fields
    'field_key_mekanikal': 'field_engineering',
    'field_key_elektrik': 'field_engineering',
    'field_key_sivil': 'field_engineering',
    'field_key_kimia': 'field_engineering',
    'field_key_aero': 'field_engineering',
    # Health sub-fields
    'field_key_perubatan': 'field_health',
    'field_key_farmasi': 'field_health',
    'field_key_allied': 'field_health',
    'field_key_health_admin': 'field_health',
    # Pure science sub-fields
    'field_key_sains_fizik': 'field_pure_science',
    'field_key_sains_kimia': 'field_pure_science',
    'field_key_sains_bio': 'field_pure_science',
    'field_key_alam': 'field_pure_science',
    # Tech sub-fields
    'field_key_it_sw': 'field_tech',
    'field_key_it_net': 'field_tech',
    'field_key_it_data': 'field_tech',
    'field_key_multimedia': 'field_creative',
    # Business sub-fields
    'field_key_pemasaran': 'field_business',
    'field_key_hr': 'field_business',
    'field_key_intl': 'field_business',
    'field_key_entrepren': 'field_business',
    # Law sub-fields
    'field_key_law': 'field_law',
    'field_key_admin': 'field_law',
    'field_key_ir': 'field_law',
    # Education sub-fields
    'field_key_pendidikan': 'field_education',
    'field_key_kaunseling': 'field_education',
    'field_key_sosial': 'field_education',
    # Creative sub-fields
    'field_key_media': 'field_creative',
    'field_key_senireka': 'field_creative',
    'field_key_digital': 'field_creative',
    'field_key_pr': 'field_creative',
    # Finance sub-fields
    'field_key_perakaunan': 'field_finance',
    'field_key_kewangan': 'field_finance',
    'field_key_aktuari': 'field_finance',
    'field_key_fin_plan': 'field_finance',
}


def _field_key_to_interest(fk_signal: str) -> str:
    """Map a field_key signal back to its parent field_interest."""
    return _FK_TO_INTEREST.get(fk_signal, '')


def _get_riasec_alignment(
    course_riasec_type: str,
    signals: Dict,
) -> Tuple[float, str]:
    """
    Calculate RIASEC alignment score.

    Course riasec_type matches student's primary seed: +6
    Matches secondary seed: +3
    Matches cross-domain Q5: +2
    Capped at +8.
    """
    if not course_riasec_type:
        return 0, ''

    score = 0
    riasec_seed = signals.get('riasec_seed', {})

    if riasec_seed:
        # Find primary and secondary seed types
        sorted_seeds = sorted(riasec_seed.items(), key=lambda x: -x[1])
        primary_types = []
        secondary_types = []

        if sorted_seeds:
            max_score = sorted_seeds[0][1]
            primary_types = [
                sig.replace('riasec_', '')
                for sig, s in sorted_seeds if s == max_score
            ]
            if len(sorted_seeds) > len(primary_types):
                next_score = sorted_seeds[len(primary_types)][1]
                secondary_types = [
                    sig.replace('riasec_', '')
                    for sig, s in sorted_seeds
                    if s == next_score and s < max_score
                ]

        if course_riasec_type in primary_types:
            score += RIASEC_PRIMARY_MATCH
        elif course_riasec_type in secondary_types:
            score += RIASEC_SECONDARY_MATCH

    # Cross-domain Q5 match
    cross_signals = signals.get('cross_domain', {})
    for sig_name in cross_signals:
        cross_type = sig_name.replace('cross_', '')
        if cross_type == course_riasec_type:
            score += RIASEC_CROSS_MATCH
            break

    return min(score, RIASEC_ALIGNMENT_CAP), 'RIASEC alignment' if score > 0 else ''


def _get_efficacy_modifier(signals: Dict) -> Tuple[float, str]:
    """
    Get efficacy modifier from Q4 signals.

    efficacy_confirmed: +4
    efficacy_confident: +2
    efficacy_open: 0
    efficacy_redirect: -1
    efficacy_mismatch: -2
    """
    efficacy_signals = signals.get('efficacy', {})
    for sig_name, _weight in efficacy_signals.items():
        mod = EFFICACY_SCORES.get(sig_name, 0)
        if mod != 0:
            label = f'Efficacy: {"+" if mod > 0 else ""}{mod}'
            return mod, label
    return 0, ''


def _get_goal_alignment(
    course_field_key: str,
    signals: Dict,
) -> Tuple[float, str]:
    """
    Calculate goal alignment score from Q9 signals.

    goal_professional + regulated profession: +4
    goal_postgrad + research programme: +4
    goal_employment + any: +3
    goal_entrepreneurial + business: +3
    """
    goal_signals = signals.get('career_goal', {})
    if not goal_signals or not course_field_key:
        return 0, ''

    best_score = 0
    for sig_name in goal_signals:
        tiers = GOAL_SCORES.get(sig_name)
        if not tiers:
            continue

        if sig_name == 'goal_professional':
            tier = 'high' if course_field_key in PROFESSIONAL_FIELD_KEYS else 'low'
        elif sig_name == 'goal_postgrad':
            tier = 'high' if course_field_key in RESEARCH_FIELD_KEYS else 'low'
        elif sig_name == 'goal_entrepreneurial':
            tier = 'high' if course_field_key in BUSINESS_FIELD_KEYS else 'low'
        else:  # goal_employment — universal
            tier = 'high'

        best_score = max(best_score, tiers.get(tier, 0))

    if best_score > 0:
        return best_score, f'Goal alignment: +{best_score}'
    return 0, ''


def _get_resilience_discount(
    course_difficulty: str,
    signals: Dict,
) -> Tuple[float, str]:
    """
    Calculate resilience discount from Q7 signals vs course difficulty.

    resilience_redirect + high difficulty: -3
    resilience_redirect + moderate difficulty: -1
    resilience_supported + high difficulty: -1
    All others: 0
    """
    resilience_signals = signals.get('resilience', {})
    if not resilience_signals or not course_difficulty:
        return 0, ''

    worst_discount = 0
    for sig_name in resilience_signals:
        discount = RESILIENCE_MATRIX.get((sig_name, course_difficulty), 0)
        if discount < worst_discount:
            worst_discount = discount

    if worst_discount < 0:
        return worst_discount, f'Resilience: {worst_discount}'
    return 0, ''


def calculate_stpm_fit_score(
    course: Dict,
    student_cgpa: float,
    signals: Dict,
) -> Tuple[float, List[str]]:
    """Calculate fit score for a single STPM course.

    Args:
        course: Eligible course dict (must include field_key, riasec_type,
                difficulty_level; these come from StpmCourse model enrichment)
        student_cgpa: Student's calculated STPM CGPA
        signals: Quiz signals dict from process_stpm_quiz (categorised by
                riasec_seed, field_interest, field_key, cross_domain,
                efficacy, resilience, career_goal, context)

    Returns:
        (score, reasons) tuple
    """
    score = BASE_SCORE
    reasons = []

    # 1. CGPA margin bonus (max +20)
    margin = student_cgpa - course.get('min_cgpa', 2.0)
    capped_margin = min(max(margin, 0), CGPA_MARGIN_CAP)
    cgpa_bonus = round(capped_margin * CGPA_MARGIN_MULTIPLIER, 1)
    if cgpa_bonus > 0:
        score += cgpa_bonus
        reasons.append(f'CGPA margin: +{cgpa_bonus}')

    course_fk = course.get('field_key', '')

    # 2. Field match (max +12)
    field_score, field_reason = _get_field_match_score(course_fk, signals)
    if field_score > 0:
        score += field_score
        reasons.append(f'{field_reason}: +{field_score}')

    # 3. RIASEC alignment (max +8)
    riasec_score, riasec_reason = _get_riasec_alignment(
        course.get('riasec_type', ''), signals,
    )
    if riasec_score > 0:
        score += riasec_score
        reasons.append(f'{riasec_reason}: +{riasec_score}')

    # 4. Efficacy modifier (+4 to -2)
    eff_mod, eff_reason = _get_efficacy_modifier(signals)
    if eff_mod != 0:
        score += eff_mod
        reasons.append(eff_reason)

    # 5. Goal alignment (max +4)
    goal_score, goal_reason = _get_goal_alignment(course_fk, signals)
    if goal_score > 0:
        score += goal_score
        reasons.append(goal_reason)

    # 6. Interview penalty (-3)
    if course.get('req_interview', False):
        score -= INTERVIEW_PENALTY
        reasons.append(f'Interview required: -{INTERVIEW_PENALTY}')

    # 7. Resilience discount (0 to -3)
    res_discount, res_reason = _get_resilience_discount(
        course.get('difficulty_level', ''), signals,
    )
    if res_discount < 0:
        score += res_discount
        reasons.append(res_reason)

    return round(score, 1), reasons


def get_result_framing(signals: Dict) -> Dict:
    """
    Determine result framing mode from Q1 crystallisation signal.

    Returns:
        {
            'mode': 'confirmatory' | 'guided' | 'discovery',
            'heading': str,  # Result page heading
            'subtitle': str, # Result page subtitle
        }
    """
    context_signals = signals.get('context', {})

    mode = 'guided'  # default
    for sig_name in context_signals:
        if sig_name in FRAMING_MODES:
            mode = FRAMING_MODES[sig_name]
            break

    headings = {
        'confirmatory': {
            'heading': 'Your profile aligns with these programmes',
            'subtitle': 'You seem to know what you want — here are the best matches.',
        },
        'guided': {
            'heading': 'Based on your interests, consider these programmes',
            'subtitle': 'You have a direction — these programmes fit your profile.',
        },
        'discovery': {
            'heading': 'Here are fields worth exploring',
            'subtitle': "You're still figuring it out — and that's fine. Explore these options.",
        },
    }

    return {
        'mode': mode,
        **headings.get(mode, headings['guided']),
    }


# Malaysian public university tiers (higher = more prestigious)
UNIVERSITY_TIER = {
    'Universiti Malaya': 3,
    'Universiti Sains Malaysia': 3,
    'Universiti Kebangsaan Malaysia': 3,
    'Universiti Putra Malaysia': 3,
    'Universiti Teknologi Malaysia': 3,
    # Comprehensive
    'Universiti Islam Antarabangsa Malaysia': 2,
    'Universiti Malaysia Sabah': 2,
    'Universiti Malaysia Sarawak': 2,
    'Universiti Pendidikan Sultan Idris': 2,
}
# All others default to 1 (focused/technical)


def get_stpm_ranked_results(
    courses: List[Dict],
    student_cgpa: float,
    signals: Dict,
) -> List[Dict]:
    """Rank eligible STPM courses by fit score.

    Args:
        courses: List of eligible course dicts (should include field_key,
                riasec_type, difficulty_level from StpmCourse enrichment)
        student_cgpa: Student's STPM CGPA
        signals: Quiz signals from process_stpm_quiz

    Returns:
        Courses sorted by 5-level hierarchy:
        1. fit_score (desc)
        2. university tier (desc) — research > comprehensive > focused
        3. competitiveness — min_cgpa (desc)
        4. difficulty_level (desc) — high > medium > low
        5. course_name (asc)
    """
    if not courses:
        return []

    scored = []
    for course in courses:
        fit_score, fit_reasons = calculate_stpm_fit_score(course, student_cgpa, signals)
        scored.append({**course, 'fit_score': fit_score, 'fit_reasons': fit_reasons})

    difficulty_order = {'high': 3, 'medium': 2, 'low': 1, '': 0}

    def sort_key(c):
        uni_tier = UNIVERSITY_TIER.get(c.get('university', ''), 1)
        competitiveness = float(c.get('min_cgpa', 0) or 0)
        diff = difficulty_order.get(c.get('difficulty_level', ''), 0)
        return (-c['fit_score'], -uni_tier, -competitiveness, -diff, c['course_name'])

    scored.sort(key=sort_key)
    return scored
