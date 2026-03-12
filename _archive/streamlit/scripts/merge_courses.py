"""
Merge courses.csv (Poly/KK) and university_courses.csv (UA) into single courses.csv.

Follows the rule: Poly/KK/UA should always be in one file.
TVET kept separate due to schema conflict (months vs semesters, no field column).
"""

import pandas as pd
import os
from pathlib import Path

# Get project root
script_dir = Path(__file__).parent
project_root = script_dir.parent
data_dir = project_root / 'data'

print("=" * 60)
print("Course Files Merger (Poly/KK + UA)")
print("=" * 60)

# Load both files with encoding handling
print("\n[1/4] Loading files...")

# Try multiple encodings for courses.csv
for encoding in ['utf-8', 'latin1', 'cp1252']:
    try:
        df_poly = pd.read_csv(data_dir / 'courses.csv', encoding=encoding)
        print(f"  - courses.csv loaded with {encoding} encoding")
        break
    except UnicodeDecodeError:
        continue

df_ua = pd.read_csv(data_dir / 'university_courses.csv')

print(f"  - courses.csv (Poly/KK): {len(df_poly)} rows")
print(f"  - university_courses.csv (UA): {len(df_ua)} rows")

# Verify schemas match
print("\n[2/4] Verifying schemas...")
print(f"  - Poly columns: {list(df_poly.columns)}")
print(f"  - UA columns: {list(df_ua.columns)}")

if list(df_poly.columns) != list(df_ua.columns):
    print("\n  [ERROR] Column mismatch!")
    print(f"    Poly: {df_poly.columns}")
    print(f"    UA: {df_ua.columns}")
    exit(1)
else:
    print("  [OK] Schemas match perfectly")

# Merge
print("\n[3/4] Merging files...")
df_merged = pd.concat([df_poly, df_ua], ignore_index=True)

print(f"  - Total courses: {len(df_merged)}")
print(f"  - Poly/KK: {len(df_poly)}")
print(f"  - UA: {len(df_ua)}")

# Verify no duplicate course IDs
duplicates = df_merged[df_merged.duplicated(subset=['course_id'], keep=False)]
if len(duplicates) > 0:
    print(f"\n  WARNING: Found {len(duplicates)} duplicate course IDs!")
    print(duplicates[['course_id', 'course']])
else:
    print("  [OK] No duplicates found")

# Backup original file
print("\n[4/4] Saving merged file...")
backup_path = data_dir / 'backup' / 'courses.csv.pre-merge'
os.makedirs(data_dir / 'backup', exist_ok=True)

if (data_dir / 'courses.csv').exists():
    import shutil
    shutil.copy(data_dir / 'courses.csv', backup_path)
    print(f"  - Backup saved: {backup_path}")

# Save merged file
output_path = data_dir / 'courses_merged.csv'
df_merged.to_csv(output_path, index=False)
print(f"  - Merged file saved: {output_path}")

print("\n" + "=" * 60)
print("SUCCESS!")
print("=" * 60)
print(f"\nNext steps:")
print(f"1. Review {output_path}")
print(f"2. If correct, rename to courses.csv")
print(f"3. Move university_courses.csv to data/archive/")
print(f"4. Update src/data_manager.py to remove university_courses.csv loading")
print(f"5. Run tests: python -m unittest tests/test_golden_master.py")
