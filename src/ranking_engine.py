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
            # Note: institutions.json is a list of objects with "inst_id" or "institution_id"?
            # Based on previous context, likely "inst_id" or "institution_id".
            # Safe checking both or dumping first item to see.
            # Assuming "inst_id" based on user context earlier.
            
            mapping = {}
            for item in data:
                # Handle potential key variations if any, but sticking to "inst_id" as seen in prior JSON snippet
                key = item.get('inst_id', item.get('institution_id'))
                if key:
                    mapping[key] = item.get('modifiers', {})
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
    i_mods = INST_MODIFIERS.get(institution_id, {})
    
    # FIX: Handle input flexibility. 
    # If key 'student_signals' exists, use it. Otherwise assume input IS the signals dict.
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
    # We now accumulate into buckets instead of a flat variable
    
    # 1. Work Preference: Hands-on & Problem Solving
    sig_hands_on = get_signal('work_preference_signals', 'hands_on')
    sig_prob_solve = get_signal('work_preference_signals', 'problem_solving')
    tag_modality = c_tags.get('work_modality', '')
    
    # Hands-on rule
    if sig_hands_on > 0 and tag_modality == 'hands_on':
        cat_scores['work_preference_signals'] += 5
        reasons.append("Matches your hands-on work preference.")
    elif sig_hands_on == 0 and tag_modality == 'hands_on':
        cat_scores['work_preference_signals'] -= 3
        # Note: Negative scores are also accumulated
        
    # Problem Solving rule
    if sig_prob_solve > 0 and tag_modality == 'mixed':
        cat_scores['work_preference_signals'] += 3
        reasons.append("Balanced approach suits your problem-solving style.")
        
    # People Helping (Belongs to Work Preference usually, or Value?)
    # Based on taxonomy, people_helping is in work_preference_signals
    if get_signal('work_preference_signals', 'people_helping') > 0 and c_tags.get('people_interaction') == 'high_people':
        cat_scores['work_preference_signals'] += 4
        reasons.append("Matches your desire to help people.")

        
    # 2. Environment Fit
    sig_workshop = get_signal('environment_signals', 'workshop_environment')
    sig_high_ppl_env = get_signal('environment_signals', 'high_people_environment')
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

    # 3. Energy / People Interaction (Energy Sensitivity)
    sig_low_people = get_signal('energy_sensitivity_signals', 'low_people_tolerance')
    tag_people = c_tags.get('people_interaction', '')
    
    if sig_low_people > 0 and tag_people == 'high_people':
        cat_scores['energy_sensitivity_signals'] -= 6
        reasons.append("May be draining due to high public interaction.")
    
        
    # 4. Values Alignment
    sig_risk = get_signal('value_tradeoff_signals', 'income_risk_tolerant')
    sig_stability = get_signal('value_tradeoff_signals', 'stability_priority')
    sig_pathway = get_signal('value_tradeoff_signals', 'pathway_priority')
    tag_outcome = c_tags.get('outcome', '')
    
    if sig_risk > 0 and tag_outcome == 'entrepreneurial':
        cat_scores['value_tradeoff_signals'] += 3
        reasons.append("Great for future entrepreneurs.")
        
    # Stability Rule (New)
    if sig_stability > 0 and tag_outcome in ['regulated_profession', 'employment_first']:
        cat_scores['value_tradeoff_signals'] += 4
        reasons.append("Offers a stable career pathway.")
        
    # Pathway Priority Rule (New)
    if sig_pathway > 0 and tag_outcome == 'pathway_friendly':
        cat_scores['value_tradeoff_signals'] += 4
        reasons.append("Designed for easy continuation to Degree.")

    # --- B. Normalization & Aggregation ---
    fit_score = 0
    
    # Sum capped category scores
    for cat, score in cat_scores.items():
        # Clamp between -CAP and +CAP
        capped = max(min(score, CATEGORY_CAP), -CATEGORY_CAP)
        fit_score += capped
        
    # --- C. Institution Modifiers (Tie-breakers) ---
    inst_score = 0
    
    # 1. Survival Support -> Subsistence
    # Note: 'allowance_priority' not strictly in 5-cat taxonomy, but checking anyway
    sig_allowance = get_signal('value_tradeoff_signals', 'allowance_priority') 
    # Fallback to check if it's in a different location or just handle gracefully if missing
    
    sig_subsistence = student_profile.get('unknown_signals', []) # Not used logic-wise yet
    
    # Check 'allowance' via direct property if modifiers exist? 
    # Plan called for +4. Current strict taxonomy doesn't pass it. 
    # SKIPPING for now to prevent errors, as verified previously.
    
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
