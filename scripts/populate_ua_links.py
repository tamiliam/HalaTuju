"""
Populate links.csv with UA course-institution mappings.

Extracts institution names from university_requirements.csv notes column,
matches with institutions.csv, and adds to links.csv.
"""

import pandas as pd
import os
from pathlib import Path

# Get project root
script_dir = Path(__file__).parent
project_root = script_dir.parent
data_dir = project_root / 'data'

print("=" * 60)
print("UA Course-Institution Links Generator")
print("=" * 60)

# Load files
print("\n[1/5] Loading files...")
df_ua_req = pd.read_csv(data_dir / 'university_requirements.csv')
df_institutions = pd.read_csv(data_dir / 'institutions.csv')
df_links = pd.read_csv(data_dir / 'links.csv')

print(f"  - university_requirements.csv: {len(df_ua_req)} courses")
print(f"  - institutions.csv: {len(df_institutions)} institutions")
print(f"  - links.csv: {len(df_links)} existing links")

# Filter to UA institutions only
df_ua_inst = df_institutions[df_institutions['type'] == 'IPTA'].copy()
print(f"  - UA institutions in institutions.csv: {len(df_ua_inst)}")

# Extract institution names from notes column
print("\n[2/5] Extracting institution names from notes...")
# Format: "PROGRAM NAME | INSTITUTION NAME"
ua_links = []
unmatched = []

for idx, row in df_ua_req.iterrows():
    course_id = row['course_id']
    notes = str(row.get('notes', ''))

    if ' | ' in notes:
        parts = notes.split(' | ', 1)
        if len(parts) == 2:
            institution_name = parts[1].strip()

            # Match with institutions.csv
            matched = df_ua_inst[df_ua_inst['institution_name'] == institution_name]

            if len(matched) == 1:
                institution_id = matched.iloc[0]['institution_id']
                ua_links.append({
                    'institution_id': institution_id,
                    'course_id': course_id
                })
            elif len(matched) > 1:
                print(f"  WARNING: Multiple matches for '{institution_name}' (course {course_id})")
                unmatched.append((course_id, institution_name, 'multiple_matches'))
            else:
                # Try partial match
                partial = df_ua_inst[df_ua_inst['institution_name'].str.contains(institution_name, case=False, na=False)]
                if len(partial) == 1:
                    institution_id = partial.iloc[0]['institution_id']
                    ua_links.append({
                        'institution_id': institution_id,
                        'course_id': course_id
                    })
                    print(f"  Partial match: '{institution_name}' → '{partial.iloc[0]['institution_name']}'")
                else:
                    unmatched.append((course_id, institution_name, 'no_match'))
        else:
            unmatched.append((course_id, notes, 'invalid_format'))
    else:
        unmatched.append((course_id, notes, 'no_separator'))

print(f"  - Matched: {len(ua_links)} courses")
print(f"  - Unmatched: {len(unmatched)} courses")

# Show unmatched details
if unmatched:
    print("\n[3/5] Unmatched courses:")
    for course_id, inst_name, reason in unmatched[:10]:
        print(f"  - {course_id}: {inst_name[:50]} ({reason})")
    if len(unmatched) > 10:
        print(f"  ... and {len(unmatched) - 10} more")

# Remove existing UA links (if any)
print("\n[4/5] Removing existing UA links...")
existing_ua_count = len(df_links[df_links['course_id'].str.startswith('U', na=False)])
df_links_clean = df_links[~df_links['course_id'].str.startswith('U', na=False)]
print(f"  - Removed {existing_ua_count} existing UA links")

# Add new UA links
print("\n[5/5] Adding new UA links...")
df_ua_links = pd.DataFrame(ua_links)
df_combined = pd.concat([df_links_clean, df_ua_links], ignore_index=True)

print(f"  - Total links: {len(df_combined)} ({len(df_links_clean)} existing + {len(df_ua_links)} new UA)")

# Backup and save
backup_path = data_dir / 'backup' / 'links.csv.pre-ua'
os.makedirs(data_dir / 'backup', exist_ok=True)

if (data_dir / 'links.csv').exists():
    import shutil
    shutil.copy(data_dir / 'links.csv', backup_path)
    print(f"  - Backup saved: {backup_path}")

output_path = data_dir / 'links.csv'
df_combined.to_csv(output_path, index=False)
print(f"  - Updated links.csv saved: {output_path}")

print("\n" + "=" * 60)
print("SUCCESS!")
print("=" * 60)
print(f"\nSummary:")
print(f"  - Total courses processed: {len(df_ua_req)}")
print(f"  - Successfully linked: {len(df_ua_links)}")
print(f"  - Failed to match: {len(unmatched)}")
print(f"  - Total links in file: {len(df_combined)}")

if unmatched:
    print(f"\nNext steps:")
    print(f"  1. Review unmatched courses (see list above)")
    print(f"  2. Either fix institution names in university_requirements.csv notes column")
    print(f"  3. Or add missing institutions to institutions.csv")
