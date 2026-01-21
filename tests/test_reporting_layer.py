import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock Streamlit secrets before importing logic that might use them
sys.modules['streamlit'] = MagicMock()
sys.modules['streamlit'].secrets = {"GEMINI_API_KEY": "fake_key"}

# Mock Google Generative AI
mock_genai = MagicMock()
sys.modules['google.generativeai'] = mock_genai

from src.reports.ai_wrapper import AIReportWrapper

class TestAIReporting(unittest.TestCase):
    def setUp(self):
        # Setup mock model
        self.mock_model = MagicMock()
        mock_genai.GenerativeModel.return_value = self.mock_model
        
        # Mock response
        self.mock_response = MagicMock()
        self.mock_response.text = "## Mocked Report\n\n- Section A..."
        self.mock_model.generate_content.return_value = self.mock_response

    def test_report_generation(self):
        wrapper = AIReportWrapper()
        
        # Sample Data
        profile = {
            "grades": {"Math": "A", "English": "B"},
            "student_signals": {"work_preference_signals": {"hands_on": 5}}
        }
        courses = [
            {"course_name": "Diploma A", "institution_name": "Poly A", "fit_score": 90},
            {"course_name": "Diploma B", "institution_name": "ADTEC B", "fit_score": 85}
        ]
        
        report = wrapper.generate_narrative_report(profile, courses)
        
        # Verify
        self.assertIn("markdown", report)
        print("Report Generated Successfully:")
        print(report['markdown'][:50] + "...")
        
        # Verify Prompt Construction (Check if format inputs were passed)
        # We can inspect the call args to see if the f-string was formatted correctly
        call_args = self.mock_model.generate_content.call_args
        prompt_sent = call_args[0][0]
        
        print("\n--- Prompt Snippet ---")
        print(prompt_sent[:200])
        
        self.assertIn("Traits:", prompt_sent)
        self.assertIn("SPM Results:", prompt_sent)

if __name__ == '__main__':
    unittest.main()
