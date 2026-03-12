class InsightGenerator:
    """
    Deterministic logic for generating short, instant insights without LLM.
    """
    
    @staticmethod
    def generate_report(student_profile, top_courses):
        """
        Generates a structured dictionary of insights.
        """
        insights = {
            "academic_snapshot": InsightGenerator._get_academic_snapshot(student_profile.get('grades', {})),
            "learning_style": InsightGenerator._get_learning_style(student_profile.get('student_signals', {})),
            "top_course_rationales": InsightGenerator._get_course_rationales(top_courses),
            "caution": InsightGenerator._get_caution(student_profile.get('student_signals', {}))
        }
        return insights

    @staticmethod
    def _get_academic_snapshot(grades):
        # Simplistic logic based on grades
        # Assuming grade keys: math, sci, eng, etc.
        # This is a placeholder for more complex logic if needed.
        # For now, we return a generic string or specific based on key subjects.
        
        # Check Math/Science strength
        math_grade = grades.get('math', 'G')
        sci_grade = grades.get('sci', 'G')
        
        strong_grades = ['A+', 'A', 'A-', 'B+']
        
        if math_grade in strong_grades and sci_grade in strong_grades:
            return "Strong quantitative & scientific foundation."
        elif math_grade in strong_grades:
            return "Strong quantitative skills."
        elif sci_grade in strong_grades:
            return "Strong scientific interest."
        else:
            return "Balanced academic profile."

    @staticmethod
    def _get_learning_style(signals):
        # Map signals to sentences
        styles = []
        
        # Work Preference
        if signals.get('work_preference_signals', {}).get('hands_on', 0) > 0:
            styles.append("You prefer practical, applied learning environments.")
        if signals.get('work_preference_signals', {}).get('creative', 0) > 0:
            styles.append("You thrive in creative, expressive settings.")
        if signals.get('work_preference_signals', {}).get('people_helping', 0) > 0:
            styles.append("You are motivated by helping others.")
            
        # Environment
        if signals.get('environment_signals', {}).get('workshop_environment', 0) > 0:
            styles.append("You work best in technical workshop settings.")
            
        if not styles:
            return "You have a flexible learning style."
            
        return " ".join(styles)

    @staticmethod
    def _get_course_rationales(top_courses):
        # Extract the pre-calculated reasons from the ranking engine
        rationales = []
        for course in top_courses[:3]: # Focus on top 3
            if 'fit_reasons' in course and course['fit_reasons']:
                # The reasons are already natural language sentences (mostly)
                # or fragments if we updated the engine.
                # Assuming engine v1.3 returns a list of strings "Matches X, Y, Z." and "Caution: ..."
                
                # Filter for positive matches only for the "Rationale" section
                positive_reasons = [r for r in course['fit_reasons'] if not r.startswith("Caution") and not r.startswith("May be")]
                
                if positive_reasons:
                    rationales.append(f"**{course.get('course_name', 'Course')}**: {positive_reasons[0]}")
        
        return rationales

    @staticmethod
    def _get_caution(signals):
        # Find strongest negative signal
        energy = signals.get('energy_sensitivity_signals', {})
        
        if energy.get('physical_fatigue_sensitive', 0) > 0:
            return "Note: Some recommended courses may be physically demanding. Ensure you are comfortable with active work."
        if energy.get('low_people_tolerance', 0) > 0:
            return "Note: You prefer lower social interaction. Some service roles might be draining over time."
        if energy.get('mental_fatigue_sensitive', 0) > 0:
            return "Note: Intense cognitive load can be tiring. Balance checking detail-oriented tasks."
            
        return "Transitioning to tertiary education requires adjustment. Pace yourself."
