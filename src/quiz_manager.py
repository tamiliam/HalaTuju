import streamlit as st
from src.quiz_data import get_quiz_questions

class QuizManager:
    def __init__(self):
        if 'quiz_step' not in st.session_state:
            self.reset_quiz()
            
    def reset_quiz(self):
        st.session_state['quiz_step'] = 0
        st.session_state['quiz_scores'] = {}
        st.session_state['quiz_history'] = [] # Stack to store history for backtracking
        
    def get_current_question(self, lang_code='en'):
        questions = get_quiz_questions(lang_code)
        step = st.session_state['quiz_step']
        if 0 <= step < len(questions):
            return questions[step]
        return None
        
    def get_total_questions(self, lang_code='en'):
        return len(get_quiz_questions(lang_code))

    def handle_answer(self, selected_option):
        """
        Updates the score based on selection and advances step.
        selected_option: The full option dict form the questions list.
        """
        # 1. Update Score
        # We aggregate signals. 
        # Structure: {'interest_signals': {'hands_on': 3}, ...}
        # But for now, let's just keep a flat signal map or the structured one requested.
        # The Requirement: "student_signals": { "interest_signals": {...}, ... }
        # However, the input JSON just has "signals": {"hands_on": 2}. 
        # We need to map these to the categories (Interest, Learning, Values, Survival).
        # We can infer category effectively or just store flat for now and categorize at the end?
        # A simpler way: The prompt defines output structure categories. 
        # Questions 1 & 2 -> Interest? 
        # Question 3 -> Learning?
        # Question 4, 5, 6 -> Values/Survival?
        
        # Let's verify mapping based on IDs:
        # q1_modality, q2_environment -> interest_signals (mostly)
        # q3_learning -> learning_signals
        # q4_values -> value_signals
        # q5_energy -> value_signals (or interest?) -> Actually signals like low_people_tolerance.
        # q6_survival -> survival_signals
        
        # To be safe, we will store the raw signals in a flat dict first, 
        # and then format the Final JSON output as requested.
        
        current_scores = st.session_state['quiz_scores']
        for sig, val in selected_option.get('signals', {}).items():
            current_scores[sig] = current_scores.get(sig, 0) + val
            
        st.session_state['quiz_scores'] = current_scores
        
        # 2. History (for Back button)
        # We store the *signals added* so we can subtract them if user goes back?
        # Or simpler: Store the entire previous score state? 
        # Even simpler: Just recalculate? No, just subtract the specific signals of this choice.
        st.session_state['quiz_history'].append(selected_option)
        
        # 3. Advance
        st.session_state['quiz_step'] += 1
        
    def go_back(self):
        if st.session_state['quiz_step'] > 0:
            # Pop last choice
            last_choice = st.session_state['quiz_history'].pop()
            
            # Revert scores
            current_scores = st.session_state['quiz_scores']
            for sig, val in last_choice.get('signals', {}).items():
                current_scores[sig] -= val
                # Remove key if 0 to keep it clean? Optional.
                
            st.session_state['quiz_scores'] = current_scores
            st.session_state['quiz_step'] -= 1

    def is_complete(self, lang_code='en'):
        return st.session_state['quiz_step'] >= self.get_total_questions(lang_code)

    def get_final_results(self):
        """
        Formats the accumulated flat scores into the requested JSON structure.
        Strict 5-category taxonomy refactor.
        """
        raw = st.session_state['quiz_scores']
        
        # Taxonomy Definition (Canonical)
        categories = {
            "work_preference_signals": [
                "hands_on",
                "problem_solving",
                "people_helping",
                "creative",
                "organising"
            ],
            "learning_tolerance_signals": [
                "learning_by_doing",
                "concept_first",
                "rote_tolerant",
                "project_based",
                "exam_sensitive"
            ],
            "environment_signals": [
                "workshop_environment",
                "office_environment",
                "high_people_environment",
                "field_environment",
                # Semantic: Neutral signal. Does not boost or penalize any course. 
                # Used to explicitly record "no bias" or "openness".
                "no_preference" 
            ],
            "value_tradeoff_signals": [
                "stability_priority",
                "income_risk_tolerant",
                "pathway_priority",
                "meaning_priority",
                "fast_employment_priority"
            ],
            "energy_sensitivity_signals": [
                "low_people_tolerance",
                "mental_fatigue_sensitive",
                "physical_fatigue_sensitive",
                "time_pressure_sensitive"
            ]
        }
        
        # Initialize Output Structure
        output = {
            "student_signals": {
                "work_preference_signals": {},
                "learning_tolerance_signals": {},
                "environment_signals": {},
                "value_tradeoff_signals": {},
                "energy_sensitivity_signals": {}
            },
            # Design Affordance: Validated signal strength map (no ranking logic yet)
            "signal_strength": {} 
        }
        
        unknown_signals = []

        # Strict Mapping with Strength & Unknown Handling
        for sig, score in raw.items():
            if score > 0:
                found = False
                for cat, keys in categories.items():
                    if sig in keys:
                        output["student_signals"][cat][sig] = score
                        
                        # Populate Signal Strength (Lightweight map)
                        # Score 2+ -> Strong, 1 -> Moderate
                        strength = "strong" if score >= 2 else "moderate"
                        output["signal_strength"][sig] = strength
                        
                        found = True
                        break
                
                if not found:
                    unknown_signals.append(sig)
        
        # Dev-Only Visibility for Unknown Signals
        if unknown_signals:
            st.session_state["unknown_quiz_signals"] = unknown_signals
            # logger.warning(f"Unknown signals found: {unknown_signals}")
        
        return output
