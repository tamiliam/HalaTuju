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

# Merit-based ranking penalty (v1.4)
MERIT_PENALTY = {
    "High": 0,     # Meets/exceeds cutoff — no penalty
    "Fair": -5,    # Within 5 points of cutoff
    "Low": -15,    # Significantly below cutoff
}

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


def get_credential_priority(course_name):
    """
    Returns credential priority for tie-breaking (higher is better).
    Asasi/Foundation > Diploma > Sijil Lanjutan > Sijil.
    """
    name_lower = course_name.lower().strip()
    if name_lower.startswith("asasi") or "foundation" in name_lower:
        return 4
    elif name_lower.startswith("diploma"):
        return 3
    elif "sijil lanjutan" in name_lower:
        return 2
    elif name_lower.startswith("sijil"):
        return 1
    return 0


def calculate_fit_score(student_profile, course_id, institution_id,
                        course_tags_map, inst_modifiers_map):
    """
    Calculates the fit score for a single course/institution pair.

    Args:
        student_profile: Dict with 'student_signals' key containing
            categorised signal dicts from quiz.
        course_id: Course ID string.
        institution_id: Institution ID string.
        course_tags_map: Dict {course_id: tags_dict} from CourseTag model.
        inst_modifiers_map: Dict {inst_id: modifiers_dict} from JSON.

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
        'work_preference_signals': 0,
        'learning_tolerance_signals': 0,
        'environment_signals': 0,
        'value_tradeoff_signals': 0,
        'energy_sensitivity_signals': 0,
    }

    def get_signal(category, key):
        return signals.get(category, {}).get(key, 0)

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

    # 5. Values Alignment
    sig_risk = get_signal('value_tradeoff_signals', 'income_risk_tolerant')
    sig_stability = get_signal('value_tradeoff_signals', 'stability_priority')
    sig_pathway = get_signal('value_tradeoff_signals', 'pathway_priority')
    sig_meaning = get_signal('value_tradeoff_signals', 'meaning_priority')
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

    if sig_meaning > 0 and (c_tags.get('people_interaction') == 'high_people'
                             or tag_outcome == 'regulated_profession'):
        cat_scores['value_tradeoff_signals'] += 3
        match_reasons.append("priority for meaningful/service-oriented work")

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

    # --- v1.2 Taxonomy Enhancements ---
    tag_service = c_tags.get('service_orientation', 'neutral')
    tag_interaction = c_tags.get('interaction_type', 'mixed')
    tag_structure = c_tags.get('career_structure', 'volatile')
    tag_credential = c_tags.get('credential_status', 'unregulated')
    tag_creative_out = c_tags.get('creative_output', 'none')

    if sig_meaning > 0:
        if tag_service == 'care':
            cat_scores['value_tradeoff_signals'] += 4
            match_reasons.append("desire for care-oriented roles")
        elif tag_interaction == 'relational':
            cat_scores['value_tradeoff_signals'] += 3
            match_reasons.append("preference for relational work")
        elif tag_service == 'service':
            cat_scores['value_tradeoff_signals'] += 1
            match_reasons.append("service orientation")

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
    fit_score = 0
    for cat, score in cat_scores.items():
        capped = max(min(score, CATEGORY_CAP), -CATEGORY_CAP)
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
    2. Credential priority (desc)
    3. Institution priority (desc)
    4. Merit points (desc)
    5. Course name (asc)

    Args:
        course_list: List of course dicts with 'fit_score', 'course_name', etc.
        inst_subcategories: Dict {inst_id: subcategory_string} for tie-breaking.

    Returns:
        Sorted list (new list, does not mutate input).
    """
    def sort_key(item):
        score = int(item.get('fit_score', 0))
        inst_id = str(item.get('institution_id', '')).strip()
        subcat = inst_subcategories.get(inst_id, '')
        inst_priority = INST_PRIORITY_MAP.get(subcat, 0)

        c_name = str(item.get('course_name') or '')
        cred_priority = get_credential_priority(c_name)

        merit = float(item.get('merit_cutoff', 0) or 0)

        return (-score, -cred_priority, -inst_priority, -merit, c_name)

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

        score, reasons = calculate_fit_score(
            student_profile, c_id, i_id,
            course_tags_map, inst_modifiers_map,
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

    top_5 = ranked_list[:5]
    rest = ranked_list[5:]

    return {
        "top_5": top_5,
        "rest": rest,
    }
