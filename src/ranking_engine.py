import pandas as pd
import json
import os

# --- Constants & Tuning knobs ---
BASE_SCORE = 100
GLOBAL_CAP = 20
INSTITUTION_CAP = 5
CATEGORY_CAP = 6 # Normalized cap per category

def load_course_tags():
    """
    Loads course tags from JSON.
    Expected path: data/course_tags.json
    """
    # Use relative path from this file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    path = os.path.join(project_root, 'data', 'course_tags.json')
    
    if not os.path.exists(path):
        return {}
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # transform list to dict for fast lookup: {course_id: tags_dict}
            return {item['course_id']: item['tags'] for item in data}
    except Exception as e:
        print(f"Error loading course tags: {e}")
        return {}

# Cache tags on module load (simple caching)
COURSE_TAGS = load_course_tags()
TAG_COUNT = len(COURSE_TAGS)

def load_institution_modifiers():
    """
    Loads institution modifiers from JSON.
    Expected path: data/institutions.json
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    path = os.path.join(project_root, 'data', 'institutions.json')
    
    if not os.path.exists(path):
        return {}
        
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # transform list to dict: {inst_id: modifiers_dict}
            mapping = {}
            for item in data:
                key = item.get('inst_id', item.get('institution_id'))
                if key:
                    # Robustness: Strip whitespace from keys
                    clean_key = str(key).strip()
                    mapping[clean_key] = item.get('modifiers', {})
            return mapping
    except Exception as e:
        print(f"Error loading inst modifiers: {e}")
        return {}

INST_MODIFIERS = load_institution_modifiers()

def calculate_fit_score(student_profile, course_id, institution_id):
    """
    Calculates the fit score for a single course/institution pair.
    Returns: (final_score, reasons_list)
    """
    
    # 1. Get Metadata
    c_tags = COURSE_TAGS.get(course_id, {})
    
    # Robustness: Strip whitespace from input ID
    clean_inst_id = str(institution_id).strip()
    i_mods = INST_MODIFIERS.get(clean_inst_id, {})
    
    # Handle input flexibility
    if 'student_signals' in student_profile:
        signals = student_profile['student_signals']
    else:
        signals = student_profile
    
    reasons = []
    
    # Initialize Categorical Buckets
    cat_scores = {
        'work_preference_signals': 0,
        'learning_tolerance_signals': 0,
        'environment_signals': 0,
        'value_tradeoff_signals': 0,
        'energy_sensitivity_signals': 0
    }
    
    # Helper to safeguard signal access
    def get_signal(category, key):
        return signals.get(category, {}).get(key, 0)
    
    # --- A. Fit Scoring (Course) ---
    
    # 1. Work Preference: Hands-on & Problem Solving
    sig_hands_on = get_signal('work_preference_signals', 'hands_on')
    sig_prob_solve = get_signal('work_preference_signals', 'problem_solving')
    sig_creative = get_signal('work_preference_signals', 'creative')
    tag_modality = c_tags.get('work_modality', '')
    tag_cognitive = c_tags.get('cognitive_type', '')
    
    # Hands-on rule
    if sig_hands_on > 0 and tag_modality == 'hands_on':
        cat_scores['work_preference_signals'] += 5
        reasons.append("Matches your hands-on work preference.")
    elif sig_hands_on == 0 and tag_modality == 'hands_on':
        cat_scores['work_preference_signals'] -= 3
        
    # Problem Solving rule
    if sig_prob_solve > 0 and tag_modality == 'mixed':
        cat_scores['work_preference_signals'] += 3
        reasons.append("Balanced approach suits your problem-solving style.")
        
    # People Helping
    if get_signal('work_preference_signals', 'people_helping') > 0 and c_tags.get('people_interaction') == 'high_people':
        cat_scores['work_preference_signals'] += 4
        reasons.append("Matches your desire to help people.")
        
    # Creative Rule (Updated: Split Logic)
    tag_learning = c_tags.get('learning_style', []) 
    if sig_creative > 0:
        boosted = False
        if 'project_based' in tag_learning:
            cat_scores['work_preference_signals'] += 4
            reasons.append("Matches your creative thinking style (Project Based).")
            boosted = True
        
        # If not already boosted by project_based, apply the Abstract check with lower weight
        if not boosted and tag_cognitive == 'abstract':
             cat_scores['work_preference_signals'] += 2
             reasons.append("Matches your creative thinking style (Abstract).")

    # 2. Environment Fit
    sig_workshop = get_signal('environment_signals', 'workshop_environment')
    sig_high_ppl_env = get_signal('environment_signals', 'high_people_environment')
    sig_field = get_signal('environment_signals', 'field_environment')
    tag_env = c_tags.get('environment', '')
    
    if sig_workshop > 0 and tag_env == 'workshop':
        cat_scores['environment_signals'] += 4
        reasons.append(f"Work environment fits your style ({tag_env}).")
        
    # High People Environment rule
    if sig_high_ppl_env > 0 and (tag_env == 'office' or c_tags.get('people_interaction') == 'high_people'):
        cat_scores['environment_signals'] += 3
        reasons.append("Social environment matches your preference.")
        
    # Office Environment Rule
    sig_office = get_signal('environment_signals', 'office_environment')
    if sig_office > 0 and tag_env == 'office':
        cat_scores['environment_signals'] += 4
        reasons.append(f"Matches your preference for office environments.")

    # Field Environment Rule
    if sig_field > 0 and tag_env == 'field':
        cat_scores['environment_signals'] += 4
        reasons.append("Matches your preference for field/outdoor work.")

    # 3. Learning Tolerance
    sig_learning = get_signal('learning_tolerance_signals', 'learning_by_doing')
    sig_theory = get_signal('learning_tolerance_signals', 'theory_oriented')
    sig_project = get_signal('learning_tolerance_signals', 'project_based')
    sig_concept = get_signal('learning_tolerance_signals', 'concept_first')
    tag_styles = c_tags.get('learning_style', [])
    
    # Learning by Doing
    if sig_learning > 0 and (tag_modality == 'hands_on' or 'project_based' in tag_styles):
         cat_scores['learning_tolerance_signals'] += 3
         reasons.append(f"Aligned with your 'learning by doing' preference.")
         
    # Theory Oriented
    if sig_theory > 0 and tag_modality in ['theory', 'mixed']:
         cat_scores['learning_tolerance_signals'] += 3
         reasons.append(f"Suits your theory-oriented preference.")
         
    # Concept First
    if sig_concept > 0 and (tag_modality == 'theoretical' or tag_cognitive == 'abstract'):
        cat_scores['learning_tolerance_signals'] += 3
        reasons.append("Matches your preference for conceptual learning.")
         
    # Project Based Rule
    if sig_project > 0 and 'project_based' in tag_styles:
         cat_scores['learning_tolerance_signals'] += 3
         reasons.append("Aligns with your preference for project-based assessment.")

    # 4. Energy Sensitivity
    sig_low_people = get_signal('energy_sensitivity_signals', 'low_people_tolerance')
    sig_fatigue = get_signal('energy_sensitivity_signals', 'physical_fatigue_sensitive')
    tag_people = c_tags.get('people_interaction', '')
    tag_load = c_tags.get('load', '')
    
    if sig_low_people > 0 and tag_people == 'high_people':
        cat_scores['energy_sensitivity_signals'] -= 6
        reasons.append("May be draining due to high public interaction.")
    
    # Physical Fatigue Rule (Safety Rail)
    if sig_fatigue > 0 and tag_load == 'physically_demanding':
        cat_scores['energy_sensitivity_signals'] -= 6 
        reasons.append("Caution: Course is physically demanding.")
        
    # 5. Values Alignment
    sig_risk = get_signal('value_tradeoff_signals', 'income_risk_tolerant')
    sig_stability = get_signal('value_tradeoff_signals', 'stability_priority')
    sig_pathway = get_signal('value_tradeoff_signals', 'pathway_priority')
    sig_meaning = get_signal('value_tradeoff_signals', 'meaning_priority')
    tag_outcome = c_tags.get('outcome', '')
    
    if sig_risk > 0 and tag_outcome == 'entrepreneurial':
        cat_scores['value_tradeoff_signals'] += 3
        reasons.append("Great for future entrepreneurs.")
        
    # Stability Rule
    if sig_stability > 0 and tag_outcome in ['regulated_profession', 'employment_first']:
        cat_scores['value_tradeoff_signals'] += 4
        reasons.append("Offers a stable career pathway.")
        
    # Pathway Priority Rule
    if sig_pathway > 0 and tag_outcome == 'pathway_friendly':
        cat_scores['value_tradeoff_signals'] += 4
        reasons.append("Designed for easy continuation to Degree.")
        
    # Meaning Priority Rule
    if sig_meaning > 0 and (c_tags.get('people_interaction') == 'high_people' or tag_outcome == 'regulated_profession'):
        cat_scores['value_tradeoff_signals'] += 3
        reasons.append("Aligns with your priority for meaningful/service-oriented work.")

    # --- B. Normalization & Aggregation ---
    fit_score = 0
    
    # Sum capped category scores
    for cat, score in cat_scores.items():
        # Clamp between -CAP and +CAP
        capped = max(min(score, CATEGORY_CAP), -CATEGORY_CAP)
        fit_score += capped
        
    # --- C. Institution Modifiers (Tie-breakers) ---
    inst_score = 0
    
    # Urban/Rural Preference
    sig_income_focus = get_signal('value_tradeoff_signals', 'income_risk_tolerant')
    is_urban = i_mods.get('urban', False)
    
    if sig_income_focus > 0 and is_urban:
        inst_score += 2
        reasons.append("Campus location suits income/urban focus.")
        
    # Cultural Safety Net
    sig_proximity = get_signal('value_tradeoff_signals', 'proximity_priority') 
    safety_net = i_mods.get('cultural_safety_net', 'low')

    if sig_proximity > 0:
        if safety_net == 'high':
            inst_score += 4 # Strong boost for community hubs
            reasons.append("High community support available.")
        elif safety_net == 'low':
            inst_score -= 2 # Slight nudge away from isolation
            
    # Cap Institution Score
    inst_score = max(min(inst_score, INSTITUTION_CAP), -INSTITUTION_CAP)
    
    # Global Cap
    total_adjust = fit_score + inst_score
    total_adjust = max(min(total_adjust, GLOBAL_CAP), -GLOBAL_CAP)
    
    final_score = BASE_SCORE + total_adjust
    
    return final_score, reasons

def get_ranked_results(eligible_courses, student_profile):
    """
    eligible_courses: List of dicts (from engine.py) including 'course_id' and 'institution_id'.
    student_profile: JSON output from quiz.
    
    Returns:
    {
        "top_5": [ ...augmented items... ],
        "rest": [ ...augmented items... ]
    }
    """
    ranked_list = []
    
    # Debug Limiter
    debug_count = 0
    
    for item in eligible_courses:
        c_id = item.get('course_id')
        i_id = item.get('institution_id')
        c_name = item.get('course_name', 'Unknown')
        
        score, reasons = calculate_fit_score(student_profile, c_id, i_id)
        
        # Clone item to avoid mutating original list references if reused
        new_item = item.copy()
        new_item['fit_score'] = score
        new_item['fit_reasons'] = reasons
        
        ranked_list.append(new_item)
        
        # TRACE LOG (First 3 items only)
        if debug_count < 3:
            print(f"DEBUG TRACE: {c_name}")
            print(f"Base: {BASE_SCORE} -> Final: {score} (Reasons: {reasons})")
            debug_count += 1
        
    # Sort by score descending (Force Int to avoid string sort issues)
    ranked_list.sort(key=lambda x: int(x['fit_score']), reverse=True)
    
    # Split
    top_5 = ranked_list[:5]
    rest = ranked_list[5:]
    
    return {
        "top_5": top_5,
        "rest": rest
    }
