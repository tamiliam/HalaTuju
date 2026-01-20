import json
import os
import streamlit as st
from src.prompts import SYSTEM_PROMPT

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    print("Warning: 'openai' module not found. AI features disabled.")

class AIReportWrapper:
    """
    Wrapper for Generative AI reporting.
    """
    
    def __init__(self):
        # Try loading key from Streamlit secrets or Env
        self.api_key = None
        self.client = None
        
        if not HAS_OPENAI:
            return
            
        try:
            if "OPENAI_API_KEY" in st.secrets:
                self.api_key = st.secrets["OPENAI_API_KEY"]
            else:
                self.api_key = os.getenv("OPENAI_API_KEY")
                
            if self.api_key:
                self.client = OpenAI(api_key=self.api_key)
        except Exception as e:
            print(f"AI Wrapper Init Error: {e}")

    def generate_narrative_report(self, student_profile, top_courses):
        """
        Generates a deep narrative report using LLM.
        """
        if not HAS_OPENAI:
             return {"error": "AI Module Missing (pip install openai)"}
             
        if not self.client:
            return {"error": "AI Service Unavailable (No Key)"}

        # Prepare Payload
        # We only need impactful signals, not everything
        summary_signals = self._extract_dominant_signals(student_profile.get('student_signals', {}))
        
        # Simplified course list to save tokens
        course_context = []
        for c in top_courses[:3]:
            course_context.append({
                "course_name": c.get('course_name'),
                "fit_reasons": c.get('fit_reasons', []),
                "score": c.get('fit_score')
            })
            
        payload = {
            "student_summary": summary_signals,
            "top_courses": course_context
        }
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o", # Or gpt-3.5-turbo if cost is concern
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(payload)}
                ],
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            return json.loads(content)
            
        except Exception as e:
            return {"error": f"Generation Failed: {str(e)}"}

    def _extract_dominant_signals(self, signals):
        """
        Extracts only signals > 0 to reduce noise for the AI.
        """
        dominant = {}
        for category, sig_dict in signals.items():
            for k, v in sig_dict.items():
                if v > 0:
                    dominant[k] = v
        return dominant
