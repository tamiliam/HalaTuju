
import sys
import os
import json
import pandas as pd

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from ranking_engine import get_ranked_results

# 1. Define Profiles
profile_A = {"student_signals":{"work_preference_signals":{"hands_on":2},"learning_tolerance_signals":{"project_based":1},"environment_signals":{"workshop_environment":1},"value_tradeoff_signals":{"meaning_priority":2},"energy_sensitivity_signals":{"physical_fatigue_sensitive":1}},"signal_strength":{"hands_on":"strong","workshop_environment":"moderate","project_based":"moderate","meaning_priority":"strong","physical_fatigue_sensitive":"moderate"}}

profile_B = {"student_signals":{"work_preference_signals":{"problem_solving":2},"learning_tolerance_signals":{"concept_first":1},"environment_signals":{"office_environment":1},"value_tradeoff_signals":{"pathway_priority":2},"energy_sensitivity_signals":{"mental_fatigue_sensitive":1}},"signal_strength":{"problem_solving":"strong","office_environment":"moderate","concept_first":"moderate","pathway_priority":"strong","mental_fatigue_sensitive":"moderate"}}

# 2. Define Mock Courses (using IDs found in Step 1115/1109)
# KKOM-CET-001 (Culinary), KKOM-CET-005 (Animasi), KKOM-CET-002 (F&B), KKOM-CET... (Recreational?)
# We will just verify Culinary vs Animasi for now to prove flip.

courses = [
    {"course_id": "KKOM-CET-001", "course_name": "Certificate in Culinary Arts", "institution_id": "KKOM-054"},
    {"course_id": "KKOM-CET-002", "course_name": "Certificate in F&B", "institution_id": "KKOM-054"},
    {"course_id": "KKOM-CET-005", "course_name": "Sijil Animasi 2D", "institution_id": "KKOM-005"}
]

def run_sim(name, profile):
    print(f"\n=== Simulation: {name} ===")
    results = get_ranked_results(courses, profile)
    
    print(f"{'Course':<30} | {'Score':<5} | {'Reasons'}")
    print("-" * 80)
    for c in results['top_5']:
        print(f"{c['course_name']:<30} | {c['fit_score']:<5} | {c.get('fit_reasons', [])}")

if __name__ == "__main__":
    run_sim("Profile A (Hands-on/Workshop)", profile_A)
    run_sim("Profile B (Problem/Office)", profile_B)
