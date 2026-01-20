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

def load_institution_priorities():
    """
    Loads institution subcategories from CSVs for tie-breaking.
    Returns: {inst_id: subcategory_string}
    """
    priorities = {}
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    
    # Files to check
    files = ['institutions.csv', 'tvet_institutions.csv']
    
    for filename in files:
        path = os.path.join(project_root, 'data', filename)
        if not os.path.exists(path):
            continue
            
        try:
            df = pd.read_csv(path)
            # Ensure columns exist
            if 'institution_id' in df.columns and 'subcategory' in df.columns:
                for _, row in df.iterrows():
                    inst_id = str(row['institution_id']).strip()
                    subcat = str(row['subcategory']).strip()
                    priorities[inst_id] = subcat
        except Exception as e:
            print(f"Error loading priorities from {filename}: {e}")
            
    return priorities

INST_MODIFIERS = load_institution_modifiers()
INST_SUBCATEGORIES = load_institution_priorities()

# Tie-breaker Map (Higher is better)
INST_PRIORITY_MAP = {
  "Premier": 10,
  "Konvensional": 9,
  "JMTI": 8,
  "METrO": 7,
  "ADTEC": 6,
  "IKTBN": 5,
  "Kolej Komuniti": 4,
  "ILP": 3,
  "IKBN": 2,
  "IKBS": 1
}

# Credential Priority Map (Higher is better)
def get_credential_priority(course_name):
    name_lower = course_name.lower().strip()
    if name_lower.startswith("diploma"):
        return 3
    elif "sijil lanjutan" in name_lower: # Check substring for Sijil Lanjutan
        return 2
    elif name_lower.startswith("sijil"):
        return 1
    return 0

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
    
    reasons = [] # Deprecated, separating types
    match_reasons = []
    caution_reasons = []
    
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
        match_reasons.append("hands-on work preference")
    elif sig_hands_on == 0 and tag_modality == 'hands_on':
        cat_scores['work_preference_signals'] -= 3
        
    # Problem Solving rule
    if sig_prob_solve > 0 and tag_modality == 'mixed':
        cat_scores['work_preference_signals'] += 3
        match_reasons.append("problem-solving style")
        
    # People Helping
    if get_signal('work_preference_signals', 'people_helping') > 0 and c_tags.get('people_interaction') == 'high_people':
        cat_scores['work_preference_signals'] += 4
        match_reasons.append("desire to help people")
        
    # Creative Rule (Updated: Split Logic)
    tag_learning = c_tags.get('learning_style', []) 
    if sig_creative > 0:
        boosted = False
        if 'project_based' in tag_learning:
            cat_scores['work_preference_signals'] += 4
            match_reasons.append("creative thinking style (Project Based)")
            boosted = True
        
        # If not already boosted by project_based, apply the Abstract check with lower weight
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
        
    # High People Environment rule
    if sig_high_ppl_env > 0 and (tag_env == 'office' or c_tags.get('people_interaction') == 'high_people'):
        cat_scores['environment_signals'] += 3
        match_reasons.append("social environment preference")
        
    # Office Environment Rule
    sig_office = get_signal('environment_signals', 'office_environment')
    if sig_office > 0 and tag_env == 'office':
        cat_scores['environment_signals'] += 4
        match_reasons.append(f"preference for office environments")

    # Field Environment Rule
    if sig_field > 0 and tag_env == 'field':
        cat_scores['environment_signals'] += 4
        match_reasons.append("preference for field/outdoor work")

    # 3. Learning Tolerance
    sig_learning = get_signal('learning_tolerance_signals', 'learning_by_doing')
    sig_theory = get_signal('learning_tolerance_signals', 'theory_oriented')
    sig_project = get_signal('learning_tolerance_signals', 'project_based')
    sig_concept = get_signal('learning_tolerance_signals', 'concept_first')
    tag_styles = c_tags.get('learning_style', [])
    
    # Learning by Doing
    if sig_learning > 0 and (tag_modality == 'hands_on' or 'project_based' in tag_styles):
         cat_scores['learning_tolerance_signals'] += 3
         match_reasons.append("learning by doing preference")
         
    # Theory Oriented
    if sig_theory > 0 and tag_modality in ['theory', 'mixed']:
         cat_scores['learning_tolerance_signals'] += 3
         match_reasons.append("theory-oriented preference")
         
    # Concept First
    if sig_concept > 0 and (tag_modality == 'theoretical' or tag_cognitive == 'abstract'):
        cat_scores['learning_tolerance_signals'] += 3
        match_reasons.append("preference for conceptual learning")
         
    # Project Based Rule
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
    
    # Physical Fatigue Rule (Safety Rail)
    if sig_fatigue > 0 and tag_load == 'physically_demanding':
        cat_scores['energy_sensitivity_signals'] -= 6 
        caution_reasons.append("Caution: Course is physically demanding.")

    # Mental Fatigue Rule (Safety Rail)
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
        
    # Stability Rule
    if sig_stability > 0 and tag_outcome in ['regulated_profession', 'employment_first']:
        cat_scores['value_tradeoff_signals'] += 4
        match_reasons.append("need for a stable career pathway")
        
    # Pathway Priority Rule
    if sig_pathway > 0 and tag_outcome == 'pathway_friendly':
        cat_scores['value_tradeoff_signals'] += 4
        match_reasons.append("priority for degree pathways")
        
    # Meaning Priority Rule
    if sig_meaning > 0 and (c_tags.get('people_interaction') == 'high_people' or tag_outcome == 'regulated_profession'):
        cat_scores['value_tradeoff_signals'] += 3
        match_reasons.append("priority for meaningful/service-oriented work")

    # --- v1.3 Fast Employment & Pathway Conflict ---
    sig_fast_emp = get_signal('value_tradeoff_signals', 'fast_employment_priority')
    
    # 1. Fast Employment Enhancement
    if sig_fast_emp > 0:
        if tag_outcome == 'employment_first':
            cat_scores['value_tradeoff_signals'] += 4
            match_reasons.append("priority for fast employment")
        elif tag_outcome == 'industry_specific':
            cat_scores['value_tradeoff_signals'] += 2
            match_reasons.append("industry-specific focus")
            
        # Structure preference when needing money fast
        tag_struct_v13 = c_tags.get('career_structure', 'volatile')
        if tag_struct_v13 == 'stable':
            cat_scores['value_tradeoff_signals'] += 1
        elif tag_struct_v13 == 'volatile':
            cat_scores['value_tradeoff_signals'] -= 1

    # 2. Pathway vs. Fast Emp Balancing
    if sig_pathway > 0 and sig_fast_emp > 0:
        if tag_outcome == 'pathway_friendly':
            cat_scores['value_tradeoff_signals'] -= 2
            caution_reasons.append("Pathway score dampened by fast employment priority.")

    # --- v1.2 Taxonomy Enhancements ---
    
    # Extract new tags with conservative defaults
    tag_service = c_tags.get('service_orientation', 'neutral')
    tag_interaction = c_tags.get('interaction_type', 'mixed')
    tag_structure = c_tags.get('career_structure', 'volatile') # Conservative default
    tag_credential = c_tags.get('credential_status', 'unregulated')
    tag_creative_out = c_tags.get('creative_output', 'none')

    # 1. Refine "Helping / Meaning" Logic
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

    # 2. Strengthen Burnout Protection (Safety Rails)
    if sig_low_people > 0:
        if tag_interaction == 'transactional':
            cat_scores['energy_sensitivity_signals'] -= 2
            caution_reasons.append("Transactional interaction may be draining.")
        if tag_service == 'service':
            cat_scores['energy_sensitivity_signals'] -= 2
            caution_reasons.append("Service focus may be draining.")

    # 3. Clarify Stability vs Risk Preference
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

    # 4. Use Credential Status Carefully
    if sig_stability > 0 and tag_credential == 'regulated':
        cat_scores['value_tradeoff_signals'] += 2
        match_reasons.append("regulated profession confidence")

    # 5. Improve Creative Matching
    if sig_creative > 0:
        if tag_creative_out == 'expressive':
            cat_scores['work_preference_signals'] += 4
            match_reasons.append("expressive creative style")
        elif tag_creative_out == 'design':
            cat_scores['work_preference_signals'] += 3
            match_reasons.append("design-oriented creative preference")

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
        match_reasons.append("income/urban focus")
        
    # Cultural Safety Net
    sig_proximity = get_signal('value_tradeoff_signals', 'proximity_priority') 
    safety_net = i_mods.get('cultural_safety_net', 'low')

    if sig_proximity > 0:
        if safety_net == 'high':
            inst_score += 4 # Strong boost for community hubs
            match_reasons.append("need for high community support")
        elif safety_net == 'low':
            inst_score -= 2 # Slight nudge away from isolation
            caution_reasons.append("Low community support may isolate.")
            
    # v1.3 Fast Employment Support logic
    sig_fast_emp_inst = get_signal('value_tradeoff_signals', 'fast_employment_priority')
    
    if sig_proximity > 0 and sig_fast_emp_inst > 0 and safety_net == 'high':
        inst_score += 2
        match_reasons.append("need for local high-support job networks")
            
    # Cap Institution Score
    inst_score = max(min(inst_score, INSTITUTION_CAP), -INSTITUTION_CAP)
    
    # Global Cap
    total_adjust = fit_score + inst_score
    total_adjust = max(min(total_adjust, GLOBAL_CAP), -GLOBAL_CAP)
    
    final_score = BASE_SCORE + total_adjust
    
    # --- Formulate Natural Language Reason ---
    final_reasons = []
    
    if match_reasons:
        # Deduplicate while preserving order
        unique_matches = []
        [unique_matches.append(x) for x in match_reasons if x not in unique_matches]
        
        if len(unique_matches) == 1:
            combined = f"Matches or aligns with your {unique_matches[0]}."
        elif len(unique_matches) == 2:
            combined = f"Matches or aligns with your {unique_matches[0]} and {unique_matches[1]}."
        else:
            # Oxford comma
            combined = f"Matches or aligns with your {', '.join(unique_matches[:-1])}, and {unique_matches[-1]}."
        
        final_reasons.append(combined)

    # Append Cautions/Risks (kept separate for emphasis)
    final_reasons.extend(caution_reasons)
    
    return final_score, final_reasons

def sort_courses(course_list):
    """
    Sorts a list of courses based on comprehensive hierarchy:
    1. Score (Desc)
    2. Credential Priority (Desc)
    3. Institution Priority (Desc)
    4. Course Name (Asc)
    """
    def sort_key(item):
        score = int(item.get('fit_score', 0)) # Default to 0 if unranked
        inst_id = str(item.get('institution_id', '')).strip()
        subcat = INST_SUBCATEGORIES.get(inst_id, '')
        inst_priority = INST_PRIORITY_MAP.get(subcat, 0)
        
        c_name = str(item.get('course_name') or '')
        cred_priority = get_credential_priority(c_name)
        
        # Sort Tuple (Descending items negative):
        # (-score, -cred_priority, -inst_priority, name)
        return (-score, -cred_priority, -inst_priority, c_name)

    # Sort in place vs return new list? 
    # Python's list.sort() is in-place. Let's return a sorted copy for safety/chaining.
    return sorted(course_list, key=sort_key)

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
        
    # Use shared sorting logic
    ranked_list = sort_courses(ranked_list)
    
    # Split
    top_5 = ranked_list[:5]
    rest = ranked_list[5:]
    
    return {
        "top_5": top_5,
        "rest": rest
    }
