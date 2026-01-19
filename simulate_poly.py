
import sys
import os
import json
import pandas as pd

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from ranking_engine import get_ranked_results, COURSE_TAGS

# 1. Define Profiles
profile_A = {"student_signals":{"work_preference_signals":{"hands_on":2},"learning_tolerance_signals":{"project_based":1},"environment_signals":{"workshop_environment":1},"value_tradeoff_signals":{"meaning_priority":2},"energy_sensitivity_signals":{"time_pressure_sensitive":1}},"signal_strength":{"hands_on":"strong","workshop_environment":"moderate","project_based":"moderate","meaning_priority":"strong","time_pressure_sensitive":"moderate"}}

profile_B = {"student_signals":{"work_preference_signals":{"organising":2},"learning_tolerance_signals":{"rote_tolerant":1},"environment_signals":{"field_environment":1},"value_tradeoff_signals":{"pathway_priority":2},"energy_sensitivity_signals":{"physical_fatigue_sensitive":1}},"signal_strength":{"organising":"strong","field_environment":"moderate","rote_tolerant":"moderate","pathway_priority":"strong","physical_fatigue_sensitive":"moderate"}}

# 2. Define Mock Courses (Using the User's List)
courses = [
    {"course_id": "POLY-DIP-001", "course_name": "Diploma Agroteknologi", "institution_id": "POLY-021"},
    {"course_id": "POLY-DIP-002", "course_name": "Diploma Bioteknologi", "institution_id": "POLY-005"},
    {"course_id": "POLY-DIP-003", "course_name": "Diploma Geomatik", "institution_id": "POLY-001"},
    {"course_id": "POLY-DIP-004", "course_name": "Diploma in Retail Operations Management", "institution_id": "POLY-012"},
    {"course_id": "POLY-DIP-005", "course_name": "Diploma Insurans", "institution_id": "POLY-011"}
]

def check_tags():
    print("\n--- Checking Tags ---")
    for c in courses:
        tags = COURSE_TAGS.get(c['course_id'])
        print(f"{c['course_name']} ({c['course_id']}): {tags is not None}")
        if tags is None:
            # Try to fuzzy find key in COURSE_TAGS
            found = False
            for k in COURSE_TAGS.keys():
                if k == c['course_id']:
                    found = True
            print(f"  Exact Key Match in Dict keys? {found}")

def run_sim(name, profile):
    print(f"\n=== Simulation: {name} ===")
    results = get_ranked_results(courses, profile)
    
    print(f"{'Course':<40} | {'Score':<5}")
    print("-" * 50)
    # Combine lists
    all_res = results['top_5'] + results['rest']
    for c in all_res:
        print(f"{c['course_name']:<40} | {c['fit_score']:<5}")

if __name__ == "__main__":
    check_tags()
    run_sim("Profile A (Hands-on)", profile_A)
    run_sim("Profile B (Organising/Pro-Field)", profile_B)
