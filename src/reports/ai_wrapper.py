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

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    print("Warning: 'openai' module not found.")

class AIReportWrapper:
    """
    Wrapper for Generative AI reporting using Google Gemini.
    Implements model cascade to handle rate limits.
    """
    
    # Model cascade: Try these models in order until one works
    # Based on official deprecation schedule (as of Jan 2026)
    MODEL_CASCADE = [
        "gemini-3-flash-preview",  # Newest (preview, no shutdown announced)
        "gemini-2.5-flash",        # Stable (shutdown June 17, 2026)
        "gemini-2.5-flash-lite",   # High throughput (shutdown July 22, 2026)
        "gemini-2.0-flash",        # Legacy fallback (shutdown Feb 5, 2026)
        "gemini-1.5-flash"         # Old reliable (if still available)
    ]
    
    def __init__(self):
        # Try loading key from Streamlit secrets or Env
        self.api_key = None
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model = None
        
        if not HAS_GEMINI:
            print("google-generativeai not installed")
            return
            
        if not self.api_key:
            print("GEMINI_API_KEY not found in environment")
            return
        
        try:
            genai.configure(api_key=self.api_key)
            
            # Try models in cascade order
            for model_name in self.MODEL_CASCADE:
                try:
                    self.model = genai.GenerativeModel(model_name)
                    print(f"Successfully initialized AI model: {model_name}")
                    break  # Success, stop trying
                except Exception as model_error:
                    print(f"Failed to initialize {model_name}: {model_error}")
                    continue  # Try next model
            
            if not self.model:
                print("All models in cascade failed to initialize")
                
        except Exception as e:
            print(f"AI Wrapper Init Error: {e}")

        # OpenAI Initialization (Fallback)
        self.openai_client = None
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        
        # Also check Streamlit secrets if not in env
        if not self.openai_api_key:
            try:
                self.openai_api_key = st.secrets.get("OPENAI_API_KEY")
            except Exception:
                pass
        
        if HAS_OPENAI and self.openai_api_key:
            try:
                self.openai_client = OpenAI(api_key=self.openai_api_key)
                print("Successfully initialized OpenAI client (Fallback)")
            except Exception as e:
                print(f"Failed to initialize OpenAI client: {e}")
        else:
            print("OpenAI fallback not configured (Missing 'openai' module or OPENAI_API_KEY)")

    def generate_narrative_report(self, student_profile, top_courses):
        """
        Generates a deep narrative report using Gemini with model cascade fallback.
        Returns a dictionary with 'markdown' key.
        """
        if not HAS_GEMINI:
             return {"error": "AI Module Missing (pip install google-generativeai)"}
             
        if not self.model:
            return {"error": "AI Service Unavailable (Missing GEMINI_API_KEY or all models failed)"}

        # 0. Determine Persona (Randomized for variety)
        import random
        counsellor_name = random.choice(["Cikgu Siva", "Cikgu Mani"])

        # Prepare Context Strings
        # 0. Student Name
        student_name = student_profile.get('full_name', 'pelajar')
        
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
                student_name=student_name,
                student_profile=profile_str,
                academic_context=academic_str,
                recommended_courses=courses_str
            )
        except Exception as e:
            # Fallback if format fails
            print(f"Prompt formatting error: {e}")
            full_prompt = f"Anda ialah {counsellor_name}.\n{SYSTEM_PROMPT}\n\nDATA:\nStudent: {student_name}\nProfile: {profile_str}\nGrades: {academic_str}\nCourses: {courses_str}"
        
        # Try to generate with cascade fallback
        # 1. Try Gemini Models
        if self.model:
            for attempt, model_name in enumerate(self.MODEL_CASCADE):
                try:
                    # Reinitialize model if needed
                    if attempt > 0:
                        print(f"Retrying with {model_name}...")
                        self.model = genai.GenerativeModel(model_name)
                    
                    response = self.model.generate_content(full_prompt)
                    text = response.text
                    
                    # Success! Return the report
                    return {
                        "markdown": text,
                        "counsellor_name": counsellor_name,
                        "model_used": model_name
                    }
                    
                except Exception as e:
                    error_msg = str(e)
                    print(f"Generation failed with {model_name}: {error_msg}")
                    continue
        
        # 2. Try OpenAI Fallback (if configured)
        if self.openai_client:
            print("All Gemini models failed. Attempting OpenAI fallback...")
            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a helpful and empathetic career counselor for Malaysian students."},
                        {"role": "user", "content": full_prompt}
                    ],
                    temperature=0.7
                )
                text = response.choices[0].message.content
                return {
                    "markdown": text,
                    "counsellor_name": counsellor_name,
                    "model_used": "openai-gpt-4o-mini"
                }
            except Exception as e:
                print(f"OpenAI fallback failed: {e}")
                return {"error": f"All AI services failed. Gemini: {error_msg if 'error_msg' in locals() else 'Init failed'}, OpenAI: {str(e)}"}

        return {"error": "Failed to generate report with any model (OpenAI not configured or failed)"}

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
