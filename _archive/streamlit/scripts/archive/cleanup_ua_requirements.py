"""
Clean up university_requirements.csv by removing fluff columns.

1. DELETE 'notes' column (course names in courses.csv, institution links in links.csv)
2. MOVE 'syarat_khas_raw' to details.csv (details_syarat_etc column)

Keeps only machine-readable eligibility columns in requirements files.
"""

import pandas as pd
import os
from pathlib import Path

# Get project root
script_dir = Path(__file__).parent
project_root = script_dir.parent
data_dir = project_root / 'data'

print("=" * 60)
print("UA Requirements Cleanup - Remove Fluff Columns")
print("=" * 60)

# Load files
print("\n[1/5] Loading files...")
df_ua_req = pd.read_csv(data_dir / 'university_requirements.csv')
df_details = pd.read_csv(data_dir / 'details.csv')

print(f"  - university_requirements.csv: {len(df_ua_req)} courses, {len(df_ua_req.columns)} columns")
print(f"  - details.csv: {len(df_details)} rows")

# Extract fluff columns
print("\n[2/5] Extracting fluff columns...")
fluff_data = df_ua_req[['course_id', 'syarat_khas_raw']].copy()
print(f"  - Extracted syarat_khas_raw for {len(fluff_data)} UA courses")

# Add to details.csv
print("\n[3/5] Adding syarat_khas_raw to details.csv...")

# Remove existing UA entries in details.csv (if any)
df_details_clean = df_details[~df_details['course_id'].str.startswith('U', na=False)].copy()
print(f"  - Removed {len(df_details) - len(df_details_clean)} existing UA rows from details.csv")

# Create new UA details rows
ua_details = []
for idx, row in fluff_data.iterrows():
    ua_details.append({
        'course_id': row['course_id'],
        'req_interview': 0,  # Default
        'single': 0,  # Default
        'source_type': 'univ',
        'institution_id': '',  # Will be populated via links.csv merge in data_manager
        'hyperlink': '',  # Can be manually added later
        'monthly_allowance': '',
        'practical_allowance': '',
        'free_hostel': '',
        'free_meals': '',
        'tuition_fee_semester': '',
        'hostel_fee_semester': '',
        'registration_fee': '',
        'details_syarat_etc': row['syarat_khas_raw']  # ← Move syarat_khas here
    })

df_ua_details = pd.DataFrame(ua_details)
df_details_combined = pd.concat([df_details_clean, df_ua_details], ignore_index=True)

print(f"  - Added {len(df_ua_details)} UA rows to details.csv")
print(f"  - Total details.csv rows: {len(df_details_combined)}")

# Remove fluff columns from university_requirements.csv
print("\n[4/5] Removing fluff columns from university_requirements.csv...")
columns_to_drop = ['notes', 'syarat_khas_raw']
df_ua_req_clean = df_ua_req.drop(columns=columns_to_drop)

print(f"  - Dropped columns: {columns_to_drop}")
print(f"  - Columns: {len(df_ua_req.columns)} -> {len(df_ua_req_clean.columns)}")
print(f"  - Remaining columns: {list(df_ua_req_clean.columns)[:10]}...")

# Backup and save
print("\n[5/5] Saving cleaned files...")
backup_dir = data_dir / 'backup'
os.makedirs(backup_dir, exist_ok=True)

# Backup university_requirements.csv
import shutil
ua_backup = backup_dir / 'university_requirements.csv.pre-cleanup'
shutil.copy(data_dir / 'university_requirements.csv', ua_backup)
print(f"  - Backup: {ua_backup}")

# Backup details.csv
details_backup = backup_dir / 'details.csv.pre-ua-cleanup'
shutil.copy(data_dir / 'details.csv', details_backup)
print(f"  - Backup: {details_backup}")

# Save cleaned files
df_ua_req_clean.to_csv(data_dir / 'university_requirements.csv', index=False)
print(f"  - Saved: university_requirements.csv ({len(df_ua_req_clean.columns)} columns)")

df_details_combined.to_csv(data_dir / 'details.csv', index=False)
print(f"  - Saved: details.csv ({len(df_details_combined)} rows)")

print("\n" + "=" * 60)
print("SUCCESS!")
print("=" * 60)
print(f"\nSummary:")
print(f"  - Deleted columns: notes (redundant with courses.csv + links.csv)")
print(f"  - Moved syarat_khas_raw -> details.csv (details_syarat_etc column)")
print(f"  - university_requirements.csv: {len(df_ua_req.columns)} -> {len(df_ua_req_clean.columns)} columns")
print(f"  - details.csv: {len(df_details)} -> {len(df_details_combined)} rows")
print(f"\nNext steps:")
print(f"  1. Update data_manager.py to remove notes column parsing")
print(f"  2. Run golden master tests to verify")
