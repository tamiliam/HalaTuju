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

        # Prepare Payload
        summary_signals = self._extract_dominant_signals(student_profile.get('student_signals', {}))
        spm_grades = student_profile.get('grades', {})
        
        # Simplified course list
        course_context = []
        for c in top_courses[:3]:
            course_context.append({
                "course_name": c.get('course_name'),
                "institution": c.get('institution_name', 'Unknown'),
                "fit_reasons": c.get('fit_reasons', []),
                "score": c.get('fit_score')
            })
            
        # Context Construction
        user_context = json.dumps({
            "student_summary": summary_signals,
            "spm_grades": spm_grades,
            "top_courses": course_context
        })
        
        # Prompt Composition
        full_prompt = f"{SYSTEM_PROMPT}\n\nHere is the student data (Use this to customize the report):\n{user_context}"
        
        try:
            response = self.model.generate_content(full_prompt)
            # Return raw markdown text
            return {"markdown": response.text}
            
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
