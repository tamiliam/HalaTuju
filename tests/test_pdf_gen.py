import sys
import os
import io

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.reports.pdf_generator import PDFReportGenerator

def test_pdf_generation():
    generator = PDFReportGenerator()
    
    profile = {
        "id": "12345678",
        "grades": {"Math": "A", "English": "B", "Science": "C"}
    }
    
    mock_markdown = """
### A. Cerminan Diri
- You are organized.
- You like structure.

### B. Isyarat Akademik
- Math A means good logic.

**Some bold text** should be bold.
    """
    
    try:
        pdf_buffer = generator.generate_pdf(profile, mock_markdown)
        print("PDF Generated successfully.")
        print(f"Buffer Size: {pdf_buffer.getbuffer().nbytes} bytes")
        
        # Optional: write to file for manual inspection if needed
        # with open("test_output.pdf", "wb") as f:
        #     f.write(pdf_buffer.getvalue())
        
    except Exception as e:
        print(f"PDF Generation Failed: {e}")
        raise e

if __name__ == "__main__":
    test_pdf_generation()
