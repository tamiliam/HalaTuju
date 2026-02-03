"""Verify 5 sample courses are parsed correctly"""
import pandas as pd
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
req_df = pd.read_csv(DATA_DIR / "university_requirements.csv")
details_df = pd.read_csv(DATA_DIR / "details.csv")

# Pick 5 diverse courses
courses = [
    'UK0010001',  # ASASIPINTAR UKM (7 distinctions)
    'UM0221002',  # ASASI PENGAJIAN ISLAM
    'UZ0520001',  # ASASI KEJURUTERAAN
    'UD4221001',  # Diploma
    'UC4340001'   # E-COMMERCE with complex OR-group
]

for cid in courses:
    print("\n" + "="*70)
    if cid not in req_df['course_id'].values:
        print(f"Course {cid} NOT FOUND")
        continue

    row = req_df[req_df['course_id'] == cid].iloc[0]
    details_row = details_df[details_df['course_id'] == cid].iloc[0]

    print(f"Course: {cid}")
    print(f"Name: {row['notes'][:60]}")
    print(f"Merit: {row['merit_cutoff']}")

    # Check distinctions
    distinctions = []
    for col in ['distinction_bm', 'distinction_eng', 'distinction_math',
                'distinction_addmath', 'distinction_bio', 'distinction_phy',
                'distinction_chem', 'distinction_sci']:
        if row[col] == 1:
            distinctions.append(col.replace('distinction_', ''))

    if distinctions:
        print(f"Distinctions (A-): {', '.join(distinctions)}")

    # Check credits
    credits = []
    for col in ['credit_math', 'credit_addmath', 'credit_science_group']:
        if row[col] == 1:
            credits.append(col.replace('credit_', ''))

    if credits:
        print(f"Credits (C): {', '.join(credits)}")

    # Check complex requirements
    if pd.notna(row['complex_requirements']) and row['complex_requirements']:
        try:
            complex_req = json.loads(row['complex_requirements'])
            if complex_req['or_groups']:
                print(f"Complex OR-groups:")
                for og in complex_req['or_groups']:
                    print(f"  - {og['count']} subjects with grade {og['grade']} from:")
                    print(f"    {', '.join(og['subjects'][:10])}{'...' if len(og['subjects']) > 10 else ''}")
                    print(f"    (total {len(og['subjects'])} subjects)")
        except:
            print(f"Complex req (raw): {row['complex_requirements'][:100]}")
    else:
        print("Complex requirements: None")

    # Check details
    print(f"\nDetails.csv:")
    print(f"  - Interview required: {'Yes' if details_row['req_interview'] == 1 else 'No'}")
    print(f"  - Single only: {'Yes' if details_row['single'] == 1 else 'No'}")
    print(f"  - Source type: {details_row['source_type']}")

print("\n" + "="*70)
print("VERIFICATION COMPLETE")
