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
                # Fallback to gemini-pro as 1.5-flash is 404ing in this env
                self.model = genai.GenerativeModel('gemini-pro', 
                                                 generation_config={"response_mime_type": "application/json"})
        except Exception as e:
            print(f"AI Wrapper Init Error: {e}")

    def generate_narrative_report(self, student_profile, top_courses):
        """
        Generates a deep narrative report using Gemini 1.5.
        """
        if not HAS_GEMINI:
             return {"error": "AI Module Missing (pip install google-generativeai)"}
             
        if not self.model:
            return {"error": "AI Service Unavailable (Missing GEMINI_API_KEY)"}

        # Prepare Payload
        summary_signals = self._extract_dominant_signals(student_profile.get('student_signals', {}))
        
        # Simplified course list
        course_context = []
        for c in top_courses[:3]:
            course_context.append({
                "course_name": c.get('course_name'),
                "fit_reasons": c.get('fit_reasons', []),
                "score": c.get('fit_score')
            })
            
        # Context Construction
        user_context = json.dumps({
            "student_summary": summary_signals,
            "top_courses": course_context
        })
        
        # Prompt Composition
        # Gemini handles system instructions in the model init (system_instruction=...) 
        # But we can also prepend it to the prompt which works well for 1.5.
        # Let's use the explicit system instruction in the chat/generate call if possible or just prepend.
        # Prepending is reliable.
        full_prompt = f"{SYSTEM_PROMPT}\n\nHere is the student data:\n{user_context}"
        
        try:
            response = self.model.generate_content(full_prompt)
            
            # Parse JSON
            # Gemini 1.5 Flash in JSON mode returns raw text that is JSON.
            try:
                result = json.loads(response.text)
                return result
            except json.JSONDecodeError:
                # Fallback if model wraps in markdown json blocks
                text = response.text.strip()
                if text.startswith("```json"):
                    text = text[7:-3].strip()
                elif text.startswith("```"):
                    text = text[3:-3].strip()
                return json.loads(text)
            
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
