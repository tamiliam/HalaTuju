import pandas as pd
from src.engine import check_eligibility

def get_institution_type(course_code):
    code = str(course_code).upper()
    if code.startswith("P-") or "POLI" in code:
        return "Politeknik"
    elif code.startswith("IKBN") or "ILP" in code:
        return "IKBN / ILP (Skills)"
    elif code.startswith("KK") or "KOLEJ" in code:
        return "Kolej Komuniti"
    else:
        return "TVET / Other"

def calculate_match_quality(student, req):
    required_credits = int(req.get('min_credits', 0))
    student_credits = student.credits
    
    if student_credits >= (required_credits + 2):
        return "Safe Bet 🟢"
    elif student_credits > required_credits:
        return "Good Match 🔵"
    else:
        return "Reach 🟡"

def generate_dashboard_data(student, df_courses):
    eligible_courses = []
    stats = {"Politeknik": 0, "IKBN / ILP (Skills)": 0, "Kolej Komuniti": 0, "TVET / Other": 0}
    
    courses_list = df_courses.to_dict('records')
    
    for course in courses_list:
        is_eligible, audit = check_eligibility(student, course)
        
        if is_eligible:
            inst_type = get_institution_type(course.get('institution_id', ''))
            if inst_type in stats:
                stats[inst_type] += 1
            else:
                stats["TVET / Other"] += 1
            
            quality = calculate_match_quality(student, course)
            
            eligible_courses.append({
                "course_name": course.get('course_name', 'Unknown Course'),
                "institution": course.get('institution_name', course.get('institution_id')),
                "type": inst_type,
                "quality": quality,
                "code": course.get('course_id')
            })

    top_picks = []
    if eligible_courses:
        eligible_courses.sort(key=lambda x: (x['quality'] == "Safe Bet 🟢"), reverse=True)
        
        polys = [c for c in eligible_courses if c['type'] == "Politeknik"]
        if polys:
            top_picks.append(polys[0])
            eligible_courses.remove(polys[0])

        skills = [c for c in eligible_courses if c['type'] == "IKBN / ILP (Skills)"]
        if skills:
            top_picks.append(skills[0])
            eligible_courses.remove(skills[0])

        while len(top_picks) < 3 and eligible_courses:
            top_picks.append(eligible_courses.pop(0))

    return {
        "user_status": "Eligible" if top_picks else "Not Eligible",
        "total_matches": sum(stats.values()),
        "summary_stats": stats,
        "featured_matches": top_picks,
        "is_locked": True 
    }