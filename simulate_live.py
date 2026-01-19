
import sys
import os
import json
import pandas as pd

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from ranking_engine import get_ranked_results, COURSE_TAGS

# User's Actual Profile (Conflicting: High People Env + Low People Tolerance)
profile_live = {
    "student_signals": {
        "work_preference_signals": { "people_helping": 2 },
        "learning_tolerance_signals": { "learning_by_doing": 1 }, 
        "environment_signals": { "high_people_environment": 1 },
        "value_tradeoff_signals": { "meaning_priority": 2 },
        "energy_sensitivity_signals": { "low_people_tolerance": 1 }
    }
}

# Poly Courses
courses = [
    {"course_id": "POLY-DIP-001", "course_name": "Diploma Agroteknologi", "institution_id": "POLY-021"},
    {"course_id": "POLY-DIP-002", "course_name": "Diploma Bioteknologi", "institution_id": "POLY-005"},
    {"course_id": "POLY-DIP-003", "course_name": "Diploma Geomatik", "institution_id": "POLY-001"},
    {"course_id": "POLY-DIP-004", "course_name": "Diploma in Retail Operations Management", "institution_id": "POLY-012"},
    {"course_id": "POLY-DIP-005", "course_name": "Diploma Insurans", "institution_id": "POLY-011"}
]

def run_sim():
    print(f"\n=== Simulation: LIVE Profile ===")
    results = get_ranked_results(courses, profile_live)
    
    print(f"{'Course':<40} | {'Score':<5} | {'Reasons'}")
    print("-" * 120)
    
    # Combine lists
    all_res = results['top_5'] + results['rest']
    for c in all_res:
        reasons = c.get('fit_reasons', [])
        print(f"{c['course_name']:<40} | {c['fit_score']:<5} | {reasons}")

if __name__ == "__main__":
    run_sim()
