import streamlit as st
import json
import os
from src.prompts import SYSTEM_PROMPT

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False
    print("Warning: 'google-generativeai' module not found. AI features disabled.")

class AIReportWrapper:
    """
    Wrapper for Generative AI reporting using Google Gemini.
    """
    
    def __init__(self):
        # Try loading key from Streamlit secrets or Env
        self.api_key = None
        self.model = None
        
        if not HAS_GEMINI:
            return

        try:
            # Check for GEMINI_API_KEY first, fallback to GOOGLE_API_KEY
            if "GEMINI_API_KEY" in st.secrets:
                self.api_key = st.secrets["GEMINI_API_KEY"]
            elif "GOOGLE_API_KEY" in st.secrets:
                self.api_key = st.secrets["GOOGLE_API_KEY"]
            else:
                self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
                
            if self.api_key:
                genai.configure(api_key=self.api_key)
                # Found available alias via list_models()
                # Remove JSON MIME type for Markdown output
                self.model = genai.GenerativeModel('gemini-flash-latest')
        except Exception as e:
            print(f"AI Wrapper Init Error: {e}")

    def generate_narrative_report(self, student_profile, top_courses):
        """
        Generates a deep narrative report using Gemini 1.5.
        Returns a dictionary with 'markdown' key.
        """
        if not HAS_GEMINI:
             return {"error": "AI Module Missing (pip install google-generativeai)"}
             
        if not self.model:
            return {"error": "AI Service Unavailable (Missing GEMINI_API_KEY)"}

        # 0. Determine Persona
        # 0. Determine Persona (Randomized for variety)
        import random
        counsellor_name = random.choice(["Cikgu Siva", "Cikgu Mani"])

        # Prepare Context Strings
        # 1. Profile
        summary_signals = self._extract_dominant_signals(student_profile.get('student_signals', {}))
        profile_str = f"Traits: {json.dumps(summary_signals)}"
        
        # 2. Academic Context (Grades)
        spm_grades = student_profile.get('grades', {})
        academic_str = "SPM Results:\n"
        for subject, grade in spm_grades.items():
            academic_str += f"- {subject}: {grade}\n"
            
        # 3. Recommended Courses
        courses_str = ""
        for i, c in enumerate(top_courses[:3]):
            c_name = c.get('course_name')
            inst = c.get('institution_name', 'Unknown')
            score = c.get('fit_score')
            courses_str += f"{i+1}. {c_name} at {inst} (Fit Score: {score})\n"
            
        # Prompt Composition
        try:
            full_prompt = SYSTEM_PROMPT.format(
                counsellor_name=counsellor_name,
                student_profile=profile_str,
                academic_context=academic_str,
                recommended_courses=courses_str
            )
        except Exception as e:
            # Fallback if format fails
            print(f"Prompt formatting error: {e}")
            full_prompt = f"Anda ialah {counsellor_name}.\n{SYSTEM_PROMPT}\n\nDATA:\nProfile: {profile_str}\nGrades: {academic_str}\nCourses: {courses_str}"
        
        try:
            response = self.model.generate_content(full_prompt)
            # Return raw markdown text AND the persona name used
            return {
                "markdown": response.text,
                "counsellor_name": counsellor_name
            }
            
        except Exception as e:
            return {"error": f"Generation Failed: {str(e)}"}

    def _extract_dominant_signals(self, signals):
        """
        Extracts only signals > 0 to reduce noise.
        """
        dominant = {}
        for category, sig_dict in signals.items():
            for k, v in sig_dict.items():
                if v > 0:
                    dominant[k] = v
        return dominant
