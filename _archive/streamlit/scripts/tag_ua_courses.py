"""
Tag UA foundation courses for ranking system.

UA courses are ASASI (foundation) programs that prepare students for degree programs.
Tags are inferred from course field and foundation program characteristics.
"""

import pandas as pd
import json
import os
from pathlib import Path

# Get project root
script_dir = Path(__file__).parent
project_root = script_dir.parent
data_dir = project_root / 'data'

print("=" * 60)
print("UA Course Tagging for Ranking System")
print("=" * 60)

# Load files
print("\n[1/6] Loading files...")
df_courses = pd.read_csv(data_dir / 'courses.csv', encoding='latin1')
df_ua = df_courses[df_courses['course_id'].str.startswith('U', na=False)].copy()

with open(data_dir / 'course_tags.json', 'r', encoding='utf-8') as f:
    existing_tags = json.load(f)

existing_ids = {entry['course_id'] for entry in existing_tags}

print(f"  - Total UA courses: {len(df_ua)}")
print(f"  - Already tagged: {len([x for x in existing_ids if x.startswith('U')])}")
print(f"  - Need to tag: {len(df_ua) - len([x for x in existing_ids if x.startswith('U')])}")

# Field-based tag mappings
print("\n[2/6] Building field-based tag inference...")

# Foundation program defaults (applies to all ASASI)
FOUNDATION_DEFAULTS = {
    "outcome": "pathway_friendly",  # All foundations lead to degrees
    "credential_status": "unregulated",  # Not professional programs
    "career_structure": "stable"  # Academic pathway is stable
}

# Field-specific overrides
FIELD_TAGS = {
    # Engineering fields
    "Kejuruteraan": {
        "work_modality": "hands_on",
        "people_interaction": "moderate_people",
        "cognitive_type": "problem_solving",
        "learning_style": ["project_based", "assessment_heavy"],
        "load": "mentally_demanding",
        "environment": "workshop",
        "creative_output": "functional",
        "service_orientation": "neutral",
        "interaction_type": "mixed"
    },
    "Kejuruteraan Mekanikal": {
        "work_modality": "hands_on",
        "people_interaction": "moderate_people",
        "cognitive_type": "problem_solving",
        "learning_style": ["project_based", "assessment_heavy"],
        "load": "physically_demanding",
        "environment": "workshop",
        "creative_output": "functional",
        "service_orientation": "neutral",
        "interaction_type": "mixed"
    },
    "Kejuruteraan Elektrik": {
        "work_modality": "mixed",
        "people_interaction": "low_people",
        "cognitive_type": "abstract",
        "learning_style": ["project_based", "assessment_heavy"],
        "load": "mentally_demanding",
        "environment": "lab",
        "creative_output": "functional",
        "service_orientation": "neutral",
        "interaction_type": "transactional"
    },
    # Science fields
    "Sains": {
        "work_modality": "mixed",
        "people_interaction": "low_people",
        "cognitive_type": "abstract",
        "learning_style": ["assessment_heavy"],
        "load": "mentally_demanding",
        "environment": "lab",
        "creative_output": "none",
        "service_orientation": "neutral",
        "interaction_type": "transactional"
    },
    # Business/Management
    "Perniagaan": {
        "work_modality": "cognitive",
        "people_interaction": "high_people",
        "cognitive_type": "procedural",
        "learning_style": ["project_based", "continuous_assessment"],
        "load": "socially_demanding",
        "environment": "office",
        "creative_output": "none",
        "service_orientation": "service",
        "interaction_type": "relational"
    },
    "Pengurusan": {
        "work_modality": "cognitive",
        "people_interaction": "high_people",
        "cognitive_type": "procedural",
        "learning_style": ["project_based", "continuous_assessment"],
        "load": "socially_demanding",
        "environment": "office",
        "creative_output": "none",
        "service_orientation": "service",
        "interaction_type": "relational"
    },
    # IT/Technology
    "Teknologi Maklumat": {
        "work_modality": "cognitive",
        "people_interaction": "low_people",
        "cognitive_type": "problem_solving",
        "learning_style": ["project_based", "assessment_heavy"],
        "load": "mentally_demanding",
        "environment": "office",
        "creative_output": "functional",
        "service_orientation": "neutral",
        "interaction_type": "transactional"
    },
    # Health/Medical
    "Perubatan": {
        "work_modality": "mixed",
        "people_interaction": "high_people",
        "cognitive_type": "abstract",
        "learning_style": ["assessment_heavy"],
        "load": "mentally_demanding",
        "environment": "lab",
        "creative_output": "none",
        "service_orientation": "care",
        "interaction_type": "relational"
    },
    # General/Foundation (Umum)
    "Umum": {
        "work_modality": "cognitive",
        "people_interaction": "moderate_people",
        "cognitive_type": "abstract",
        "learning_style": ["assessment_heavy"],
        "load": "mentally_demanding",
        "environment": "lecture",
        "creative_output": "none",
        "service_orientation": "neutral",
        "interaction_type": "transactional"
    }
}

# Fuzzy field matching
def get_field_tags(field):
    """Get tags for a field, with fuzzy matching."""
    if pd.isna(field):
        return FIELD_TAGS["Umum"].copy()

    field = str(field)

    # Exact match
    if field in FIELD_TAGS:
        return FIELD_TAGS[field].copy()

    # Fuzzy match (check if field contains key)
    for key in FIELD_TAGS:
        if key in field or field in key:
            return FIELD_TAGS[key].copy()

    # Default to Umum (general)
    return FIELD_TAGS["Umum"].copy()

# Generate tags
print("\n[3/6] Generating tags for UA courses...")
new_tags = []
field_counts = {}

for idx, row in df_ua.iterrows():
    course_id = row['course_id']

    # Skip if already tagged
    if course_id in existing_ids:
        continue

    course_name = row['course']
    field = row['field']

    # Get field-specific tags
    tags = get_field_tags(field)

    # Add foundation defaults
    tags.update(FOUNDATION_DEFAULTS)

    # Create entry
    new_tags.append({
        "course_id": course_id,
        "course_name": course_name,
        "tags": tags
    })

    # Track field distribution
    field_key = field if pd.notna(field) else "Unknown"
    field_counts[field_key] = field_counts.get(field_key, 0) + 1

print(f"  - Generated tags for {len(new_tags)} UA courses")
print(f"\n  Field distribution:")
for field, count in sorted(field_counts.items(), key=lambda x: -x[1])[:10]:
    print(f"    - {field}: {count} courses")

# Combine with existing tags
print("\n[4/6] Merging with existing tags...")
combined_tags = existing_tags + new_tags
print(f"  - Existing tags: {len(existing_tags)}")
print(f"  - New UA tags: {len(new_tags)}")
print(f"  - Total tags: {len(combined_tags)}")

# Validate all tags have required fields
print("\n[5/6] Validating tag structure...")
required_fields = [
    "work_modality", "people_interaction", "cognitive_type", "learning_style",
    "load", "outcome", "environment", "credential_status", "creative_output",
    "service_orientation", "interaction_type", "career_structure"
]

validation_errors = []
for entry in combined_tags:
    course_id = entry['course_id']
    tags = entry.get('tags', {})
    for field in required_fields:
        if field not in tags:
            validation_errors.append(f"{course_id} missing {field}")

if validation_errors:
    print(f"  WARNING: {len(validation_errors)} validation errors:")
    for error in validation_errors[:5]:
        print(f"    - {error}")
    if len(validation_errors) > 5:
        print(f"    ... and {len(validation_errors) - 5} more")
else:
    print("  [OK] All tags valid")

# Save
print("\n[6/6] Saving updated course_tags.json...")
backup_path = data_dir / 'backup' / 'course_tags.json.pre-ua-tags'
os.makedirs(data_dir / 'backup', exist_ok=True)

import shutil
shutil.copy(data_dir / 'course_tags.json', backup_path)
print(f"  - Backup saved: {backup_path}")

with open(data_dir / 'course_tags.json', 'w', encoding='utf-8') as f:
    json.dump(combined_tags, f, indent=2, ensure_ascii=False)

print(f"  - Updated course_tags.json saved")

print("\n" + "=" * 60)
print("SUCCESS!")
print("=" * 60)
print(f"\nSummary:")
print(f"  - UA courses tagged: {len(new_tags)}")
print(f"  - Total courses in course_tags.json: {len(combined_tags)}")
print(f"  - Coverage: {len(combined_tags)}/410 courses ({len(combined_tags)*100//410}%)")
print(f"\nNext steps:")
print(f"  1. Review generated tags (especially for less common fields)")
print(f"  2. Manually adjust if needed")
print(f"  3. Verify ranking works for UA courses")
