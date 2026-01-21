import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.dashboard import get_institution_type

def test_jmti():
    row = {
        'institution_name': 'Institut Teknikal Jepun Malaysia',
        'type': 'IPTA',
        'acronym': 'JMTI',
        'course_id': 'IJTM-DIP-001'
    }
    
    result = get_institution_type(row)
    print(f"Input: {row}")
    print(f"Output Key: {result}")
    
    if result == "inst_ikbn":
        print("PASS: JMTI correctly categorized as IKBN/ADTEC group.")
    elif result == "inst_other":
        print("FAIL: JMTI still categorized as Other.")
    else:
        print(f"FAIL: JMTI categorized as {result}")

if __name__ == "__main__":
    test_jmti()
