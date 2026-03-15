"""
Ranking engine for HalaTuju course recommendations.

Ported from src/ranking_engine.py (Streamlit version).
Calculates fit scores based on student quiz signals matched against
course tags and institution modifiers.

Architecture:
- Course tags and institution data are loaded at startup by AppConfig
- This module receives data as parameters (no file I/O, no globals)
- Pure functions: deterministic, testable, no side effects
"""

# --- Constants & Tuning Knobs ---
BASE_SCORE = 100
GLOBAL_CAP = 20
INSTITUTION_CAP = 5
CATEGORY_CAP = 6  # Normalised cap per category

# Category-specific caps (override CATEGORY_CAP for these)
FIELD_INTEREST_CAP = 8
WORK_PREFERENCE_CAP = 4

# Field interest → taxonomy field_key mapping
# Maps quiz signal names to the canonical taxonomy keys they match.
# Used by both SPM and STPM ranking for field interest scoring.
FIELD_KEY_MAP = {
    'field_mechanical': ['mekanikal', 'automotif', 'mekatronik'],
    'field_digital': ['it-perisian', 'it-rangkaian', 'multimedia'],
    'field_business': ['perniagaan', 'perakaunan', 'pengurusan'],
    'field_health': ['perubatan', 'farmasi', 'sains-hayat'],
    'field_creative': ['senireka', 'multimedia'],
    'field_hospitality': ['hospitaliti', 'kulinari', 'kecantikan'],
    'field_agriculture': ['pertanian', 'alam-sekitar'],
    'field_heavy_industry': [
        'mekanikal', 'automotif', 'mekatronik',
        'aero', 'marin', 'minyak-gas',
        'elektrik', 'sivil', 'senibina',
        'kimia-proses',
    ],
    'field_electrical': ['elektrik'],
    'field_civil': ['sivil', 'senibina'],
    'field_aero_marine': ['aero', 'marin'],
    'field_oil_gas': ['minyak-gas'],
}

# Merit-based ranking penalty (v1.4)
MERIT_PENALTY = {
    "High": 0,     # Meets/exceeds cutoff — no penalty
    "Fair": -5,    # Within 5 points of cutoff
    "Low": -15,    # Significantly below cutoff
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
        reasons.append(f"matches your interest in {track_id}")

    return score, reasons


# Merit label sort priority (safe bets first, mirroring Streamlit quality_key)
MERIT_LABEL_PRIORITY = {'High': 3, 'Fair': 2, 'Low': 1}

# Institution tie-breaker priorities (higher is better)
INST_PRIORITY_MAP = {
    # Universities (IPTA)
    "Penyelidikan": 14,
    "Komprehensif": 13,
    "Berfokus": 12,
    "Teknikal": 11,
    # Polytechnics & Colleges
    "Premier": 10,
    "Konvensional": 9,
    "JMTI": 8,
    "METrO": 7,
    "Kolej Komuniti": 6,
    # TVET Institutions
    "ADTEC": 5,
    "IKTBN": 4,
    "ILP": 3,
    "IKBN": 2,
    "IKBS": 1,
    "IKSN": 2,
}


def get_credential_priority(course_name, source_type=''):
    """
    Returns credential priority for tie-breaking (higher is better).
    Asasi/Foundation > Diploma > PISMP > Sijil Lanjutan > Sijil.
    """
    # PISMP leads to Ijazah Sarjana Muda Pendidikan (full degree) but ranks
    # below Diploma in sort so Poly High appears before PISMP on dashboard
    if source_type == 'pismp':
        return 2.5
    if source_type in ('matric', 'stpm'):
        return 5
    name_lower = course_name.lower().strip()
    if name_lower.startswith("asasi") or "foundation" in name_lower:
        return 5
    elif name_lower.startswith("matriculation") or name_lower.startswith("form 6"):
        return 5
    elif name_lower.startswith("diploma"):
        return 3
    elif "sijil lanjutan" in name_lower:
        return 2
    elif name_lower.startswith("sijil"):
        return 1
    return 0


def calculate_fit_score(student_profile, course_id, institution_id,
                        course_tags_map, inst_modifiers_map, field_key=''):
    """
    Calculates the fit score for a single course/institution pair.

    Args:
        student_profile: Dict with 'student_signals' key containing
            categorised signal dicts from quiz.
        course_id: Course ID string.
        institution_id: Institution ID string.
        course_tags_map: Dict {course_id: tags_dict} from CourseTag model.
        inst_modifiers_map: Dict {inst_id: modifiers_dict} from JSON.
        field_key: Taxonomy field_key for field interest matching.

    Returns:
        (final_score: int, reasons: list[str])
    """
    c_tags = course_tags_map.get(course_id, {})
    clean_inst_id = str(institution_id).strip()
    i_mods = inst_modifiers_map.get(clean_inst_id, {})

    # Handle input flexibility
    if 'student_signals' in student_profile:
        signals = student_profile['student_signals']
    else:
        signals = student_profile

    match_reasons = []
    caution_reasons = []

    # Initialise categorical buckets
    cat_scores = {
        'field_interest': 0,
        'work_preference_signals': 0,
        'learning_tolerance_signals': 0,
        'environment_signals': 0,
        'value_tradeoff_signals': 0,
        'energy_sensitivity_signals': 0,
    }

    def get_signal(category, key):
        return signals.get(category, {}).get(key, 0)

    # --- Field Interest Matching ---
    field_signals = signals.get('field_interest', {})

    if field_signals and field_key:
        # Find matching field signals, sorted by score (highest first)
        matches = []
        for sig_name, sig_score in sorted(field_signals.items(), key=lambda x: -x[1]):
            keys = FIELD_KEY_MAP.get(sig_name, [])
            if field_key in keys:
                matches.append(sig_score)

        if matches:
            # Primary match: +8 boost
            cat_scores['field_interest'] += 8
            match_reasons.append(f"strong interest in {field_key} field")
            if len(matches) > 1:
                # Secondary match: +4 additional
                cat_scores['field_interest'] += 4

    # --- A. Fit Scoring (Course) ---

    # 1. Work Preference: Hands-on & Problem Solving
    sig_hands_on = get_signal('work_preference_signals', 'hands_on')
    sig_prob_solve = get_signal('work_preference_signals', 'problem_solving')
    sig_creative = get_signal('work_preference_signals', 'creative')
    tag_modality = c_tags.get('work_modality', '')
    tag_cognitive = c_tags.get('cognitive_type', '')

    if sig_hands_on > 0 and tag_modality == 'hands_on':
        cat_scores['work_preference_signals'] += 5
        match_reasons.append("hands-on work preference")
    elif sig_hands_on == 0 and tag_modality == 'hands_on':
        cat_scores['work_preference_signals'] -= 3

    if sig_prob_solve > 0 and tag_modality == 'mixed':
        cat_scores['work_preference_signals'] += 3
        match_reasons.append("problem-solving style")

    if (get_signal('work_preference_signals', 'people_helping') > 0
            and c_tags.get('people_interaction') == 'high_people'):
        cat_scores['work_preference_signals'] += 4
        match_reasons.append("desire to help people")

    # Creative Rule (Split Logic)
    tag_learning = c_tags.get('learning_style', [])
    if sig_creative > 0:
        boosted = False
        if 'project_based' in tag_learning:
            cat_scores['work_preference_signals'] += 4
            match_reasons.append("creative thinking style (Project Based)")
            boosted = True
        if not boosted and tag_cognitive == 'abstract':
            cat_scores['work_preference_signals'] += 2
            match_reasons.append("creative thinking style (Abstract)")

    # 2. Environment Fit
    sig_workshop = get_signal('environment_signals', 'workshop_environment')
    sig_high_ppl_env = get_signal('environment_signals', 'high_people_environment')
    sig_field = get_signal('environment_signals', 'field_environment')
    tag_env = c_tags.get('environment', '')

    if sig_workshop > 0 and tag_env == 'workshop':
        cat_scores['environment_signals'] += 4
        match_reasons.append(f"preference for {tag_env} environments")

    if sig_high_ppl_env > 0 and (tag_env == 'office'
                                  or c_tags.get('people_interaction') == 'high_people'):
        cat_scores['environment_signals'] += 3
        match_reasons.append("social environment preference")

    sig_office = get_signal('environment_signals', 'office_environment')
    if sig_office > 0 and tag_env == 'office':
        cat_scores['environment_signals'] += 4
        match_reasons.append("preference for office environments")

    if sig_field > 0 and tag_env == 'field':
        cat_scores['environment_signals'] += 4
        match_reasons.append("preference for field/outdoor work")

    # 3. Learning Tolerance
    sig_learning = get_signal('learning_tolerance_signals', 'learning_by_doing')
    sig_theory = get_signal('learning_tolerance_signals', 'theory_oriented')
    sig_project = get_signal('learning_tolerance_signals', 'project_based')
    sig_concept = get_signal('learning_tolerance_signals', 'concept_first')
    tag_styles = c_tags.get('learning_style', [])

    if sig_learning > 0 and (tag_modality == 'hands_on' or 'project_based' in tag_styles):
        cat_scores['learning_tolerance_signals'] += 3
        match_reasons.append("learning by doing preference")

    if sig_theory > 0 and tag_modality in ['theory', 'mixed']:
        cat_scores['learning_tolerance_signals'] += 3
        match_reasons.append("theory-oriented preference")

    if sig_concept > 0 and (tag_modality == 'theoretical' or tag_cognitive == 'abstract'):
        cat_scores['learning_tolerance_signals'] += 3
        match_reasons.append("preference for conceptual learning")

    if sig_project > 0 and 'project_based' in tag_styles:
        cat_scores['learning_tolerance_signals'] += 3
        match_reasons.append("preference for project-based assessment")

    # Rote tolerant → assessment_heavy match (was dead signal, now wired)
    sig_rote = get_signal('learning_tolerance_signals', 'rote_tolerant')
    if sig_rote > 0 and 'assessment_heavy' in tag_styles:
        cat_scores['learning_tolerance_signals'] += 3
        match_reasons.append("comfort with structured assessment")

    # 4. Energy Sensitivity
    sig_low_people = get_signal('energy_sensitivity_signals', 'low_people_tolerance')
    sig_fatigue = get_signal('energy_sensitivity_signals', 'physical_fatigue_sensitive')
    tag_people = c_tags.get('people_interaction', '')
    tag_load = c_tags.get('load', '')

    if sig_low_people > 0 and tag_people == 'high_people':
        cat_scores['energy_sensitivity_signals'] -= 6
        caution_reasons.append("May be draining due to high public interaction.")

    if sig_fatigue > 0 and tag_load == 'physically_demanding':
        cat_scores['energy_sensitivity_signals'] -= 6
        caution_reasons.append("Caution: Course is physically demanding.")

    sig_mental_fatigue = get_signal('energy_sensitivity_signals', 'mental_fatigue_sensitive')
    if sig_mental_fatigue > 0 and tag_load == 'mentally_demanding':
        cat_scores['energy_sensitivity_signals'] -= 6
        caution_reasons.append("Caution: Course is mentally demanding.")

    # High stamina: positive boost for demanding courses
    sig_stamina = get_signal('energy_sensitivity_signals', 'high_stamina')
    if sig_stamina > 0 and tag_load in ('physically_demanding', 'mentally_demanding'):
        cat_scores['energy_sensitivity_signals'] += 2
        match_reasons.append("high stamina for demanding programme")

    # 5. Values Alignment
    sig_risk = get_signal('value_tradeoff_signals', 'income_risk_tolerant')
    sig_stability = get_signal('value_tradeoff_signals', 'stability_priority')
    sig_pathway = get_signal('value_tradeoff_signals', 'pathway_priority')
    tag_outcome = c_tags.get('outcome', '')

    if sig_risk > 0 and tag_outcome == 'entrepreneurial':
        cat_scores['value_tradeoff_signals'] += 3
        match_reasons.append("entrepreneurial ambition")

    if sig_stability > 0 and tag_outcome in ['regulated_profession', 'employment_first']:
        cat_scores['value_tradeoff_signals'] += 4
        match_reasons.append("need for a stable career pathway")

    if sig_pathway > 0 and tag_outcome == 'pathway_friendly':
        cat_scores['value_tradeoff_signals'] += 4
        match_reasons.append("priority for degree pathways")

    # --- v1.3 Fast Employment & Pathway Conflict ---
    sig_fast_emp = get_signal('value_tradeoff_signals', 'fast_employment_priority')

    if sig_fast_emp > 0:
        if tag_outcome == 'employment_first':
            cat_scores['value_tradeoff_signals'] += 4
            match_reasons.append("priority for fast employment")
        elif tag_outcome == 'industry_specific':
            cat_scores['value_tradeoff_signals'] += 2
            match_reasons.append("industry-specific focus")

        tag_struct_v13 = c_tags.get('career_structure', 'volatile')
        if tag_struct_v13 == 'stable':
            cat_scores['value_tradeoff_signals'] += 1
        elif tag_struct_v13 == 'volatile':
            cat_scores['value_tradeoff_signals'] -= 1

    if sig_pathway > 0 and sig_fast_emp > 0:
        if tag_outcome == 'pathway_friendly':
            cat_scores['value_tradeoff_signals'] -= 2
            caution_reasons.append("Pathway score dampened by fast employment priority.")

    # Quality priority: small boost for pathway-friendly / regulated courses
    sig_quality = get_signal('value_tradeoff_signals', 'quality_priority')
    if sig_quality > 0 and tag_outcome in ('pathway_friendly', 'regulated_profession'):
        cat_scores['value_tradeoff_signals'] += 1
        match_reasons.append("preference for quality programme")

    # --- v1.2 Taxonomy Enhancements ---
    tag_service = c_tags.get('service_orientation', 'neutral')
    tag_interaction = c_tags.get('interaction_type', 'mixed')
    tag_structure = c_tags.get('career_structure', 'volatile')
    tag_credential = c_tags.get('credential_status', 'unregulated')
    tag_creative_out = c_tags.get('creative_output', 'none')

    if sig_low_people > 0:
        if tag_interaction == 'transactional':
            cat_scores['energy_sensitivity_signals'] -= 2
            caution_reasons.append("Transactional interaction may be draining.")
        if tag_service == 'service':
            cat_scores['energy_sensitivity_signals'] -= 2
            caution_reasons.append("Service focus may be draining.")

    if sig_stability > 0 and tag_structure == 'stable':
        cat_scores['value_tradeoff_signals'] += 3
        match_reasons.append("preference for stable career structures")

    if sig_risk > 0:
        if tag_structure == 'volatile':
            cat_scores['value_tradeoff_signals'] += 2
            match_reasons.append("tolerance for volatile income")
        elif tag_structure == 'portfolio':
            cat_scores['value_tradeoff_signals'] += 2
            match_reasons.append("interest in portfolio careers")

    if sig_stability > 0 and tag_credential == 'regulated':
        cat_scores['value_tradeoff_signals'] += 2
        match_reasons.append("regulated profession confidence")

    if sig_creative > 0:
        if tag_creative_out == 'expressive':
            cat_scores['work_preference_signals'] += 4
            match_reasons.append("expressive creative style")
        elif tag_creative_out == 'design':
            cat_scores['work_preference_signals'] += 3
            match_reasons.append("design-oriented creative preference")

    # --- B. Normalisation & Aggregation ---
    CAPS = {
        'field_interest': FIELD_INTEREST_CAP,
        'work_preference_signals': WORK_PREFERENCE_CAP,
        'learning_tolerance_signals': CATEGORY_CAP,
        'environment_signals': CATEGORY_CAP,
        'value_tradeoff_signals': CATEGORY_CAP,
        'energy_sensitivity_signals': CATEGORY_CAP,
    }
    fit_score = 0
    for cat, score in cat_scores.items():
        cap = CAPS.get(cat, CATEGORY_CAP)
        capped = max(min(score, cap), -cap)
        fit_score += capped

    # --- C. Institution Modifiers (Tie-breakers) ---
    inst_score = 0

    sig_income_focus = get_signal('value_tradeoff_signals', 'income_risk_tolerant')
    is_urban = i_mods.get('urban', False)

    if sig_income_focus > 0 and is_urban:
        inst_score += 2
        match_reasons.append("income/urban focus")

    sig_proximity = get_signal('value_tradeoff_signals', 'proximity_priority')
    safety_net = i_mods.get('cultural_safety_net', 'low')

    if sig_proximity > 0:
        if safety_net == 'high':
            inst_score += 4
            match_reasons.append("need for high community support")
        elif safety_net == 'low':
            inst_score -= 2
            caution_reasons.append("Low community support may isolate.")

    # v1.3 Fast Employment Support logic
    sig_fast_emp_inst = get_signal('value_tradeoff_signals', 'fast_employment_priority')

    if sig_proximity > 0 and sig_fast_emp_inst > 0 and safety_net == 'high':
        inst_score += 2
        match_reasons.append("need for local high-support job networks")

    inst_score = max(min(inst_score, INSTITUTION_CAP), -INSTITUTION_CAP)

    # Global Cap
    total_adjust = fit_score + inst_score
    total_adjust = max(min(total_adjust, GLOBAL_CAP), -GLOBAL_CAP)

    final_score = BASE_SCORE + total_adjust

    # --- Formulate Natural Language Reason ---
    final_reasons = []

    if match_reasons:
        unique_matches = []
        for x in match_reasons:
            if x not in unique_matches:
                unique_matches.append(x)

        if len(unique_matches) == 1:
            combined = f"Matches or aligns with your {unique_matches[0]}."
        elif len(unique_matches) == 2:
            combined = f"Matches or aligns with your {unique_matches[0]} and {unique_matches[1]}."
        else:
            combined = (f"Matches or aligns with your "
                        f"{', '.join(unique_matches[:-1])}, and {unique_matches[-1]}.")
        final_reasons.append(combined)

    final_reasons.extend(caution_reasons)

    return final_score, final_reasons


def sort_courses(course_list, inst_subcategories):
    """
    Sorts courses by comprehensive hierarchy:
    1. Score (desc)
    2. Merit chance tier (desc)
    3. Merit delta (Fair/Low only, desc)
    4. Credential priority (desc)
    5. Institution priority (desc)
    6. Competitiveness — merit cutoff (desc)
    7. Course name (asc)

    Args:
        course_list: List of course dicts with 'fit_score', 'course_name', etc.
        inst_subcategories: Dict {inst_id: subcategory_string} for tie-breaking.

    Returns:
        Sorted list (new list, does not mutate input).
    """
    def sort_key(item):
        score = int(item.get('fit_score', 0))
        merit_chance = MERIT_LABEL_PRIORITY.get(item.get('merit_label') or '', 2)  # no data = Fair
        inst_id = str(item.get('institution_id', '')).strip()
        subcat = inst_subcategories.get(inst_id, '')
        inst_priority = INST_PRIORITY_MAP.get(subcat, 0)

        c_name = str(item.get('course_name') or '')
        s_type = str(item.get('source_type') or '')
        cred_priority = get_credential_priority(c_name, s_type)

        # Delta sort only for Fair/Low — High courses sort by credential instead
        label = item.get('merit_label') or ''
        if label in ('Fair', 'Low'):
            student_m = float(item.get('student_merit', 0) or 0)
            cutoff = float(item.get('merit_cutoff', 0) or 0)
            merit_delta = student_m - cutoff
        else:
            merit_delta = 0

        competitiveness = float(item.get('merit_cutoff') or 0)
        return (-score, -merit_chance, -merit_delta, -cred_priority, -inst_priority, -competitiveness, c_name)

    return sorted(course_list, key=sort_key)


def get_ranked_results(eligible_courses, student_profile,
                       course_tags_map, inst_modifiers_map,
                       inst_subcategories):
    """
    Main entry point: rank eligible courses by fit score.

    Args:
        eligible_courses: List of dicts from eligibility engine, each with
            'course_id', 'institution_id', 'course_name', 'merit_cutoff'.
        student_profile: Dict with 'student_signals' from quiz.
        course_tags_map: Dict {course_id: tags_dict}.
        inst_modifiers_map: Dict {inst_id: modifiers_dict}.
        inst_subcategories: Dict {inst_id: subcategory_string}.

    Returns:
        {"top_5": [...], "rest": [...]}
    """
    from .engine import check_merit_probability

    ranked_list = []

    for item in eligible_courses:
        c_id = item.get('course_id')
        i_id = item.get('institution_id', '')

        # Pre-u pathways use unified scoring instead of generic course-tag matching
        if item.get('pathway_type') == 'asasi':
            score, reasons = calculate_asasi_fit_score(item, student_profile)
        elif item.get('pathway_type') in ('matric', 'stpm'):
            score, reasons = calculate_matric_stpm_fit_score(item, student_profile)
        else:
            score, reasons = calculate_fit_score(
                student_profile, c_id, i_id,
                course_tags_map, inst_modifiers_map,
                field_key=item.get('field_key', ''),
            )

        # v1.4: Apply merit-based penalty as "reality check"
        merit_cutoff = item.get('merit_cutoff', 0)
        student_merit = item.get('student_merit', 0)

        if merit_cutoff and merit_cutoff > 0:
            prob_label, _ = check_merit_probability(student_merit, merit_cutoff)
            penalty = MERIT_PENALTY.get(prob_label, 0)
            score += penalty

        new_item = item.copy()
        new_item['fit_score'] = score
        new_item['fit_reasons'] = reasons

        ranked_list.append(new_item)

    ranked_list = sort_courses(ranked_list, inst_subcategories)

    top_5 = ranked_list[:6]
    rest = ranked_list[6:]

    return {
        "top_5": top_5,
        "rest": rest,
    }
