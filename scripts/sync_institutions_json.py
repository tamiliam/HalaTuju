"""
Sync institutions.json from institutions.csv.

institutions.json should only contain:
- inst_id (mapped from institution_id)
- modifiers (for ranking engine)

This script adds missing institutions (especially UA) while preserving
existing modifiers for Poly/KK/TVET institutions.
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
print("Institutions JSON Sync (from institutions.csv)")
print("=" * 60)

# Load files
print("\n[1/4] Loading files...")
df_inst = pd.read_csv(data_dir / 'institutions.csv')
print(f"  - institutions.csv: {len(df_inst)} institutions")

json_path = data_dir / 'institutions.json'
if json_path.exists():
    with open(json_path, 'r', encoding='utf-8') as f:
        existing_json = json.load(f)
    print(f"  - institutions.json: {len(existing_json)} institutions (existing)")
else:
    existing_json = []
    print(f"  - institutions.json: Not found (will create new)")

# Create lookup of existing modifiers
print("\n[2/4] Building modifier lookup...")
existing_modifiers = {}
for inst in existing_json:
    inst_id = inst.get('inst_id')
    if inst_id:
        existing_modifiers[inst_id] = inst.get('modifiers', {})

print(f"  - Found existing modifiers for {len(existing_modifiers)} institutions")

# Helper function to map Indians % to cultural_safety_net
def get_cultural_safety_net(indians_pct):
    """
    Map Indians % to cultural_safety_net level.

    ≥10% → high
    5-10% → moderate
    <5% → low
    """
    if pd.isna(indians_pct):
        return "unknown"

    pct = float(indians_pct)
    if pct >= 10.0:
        return "high"
    elif pct >= 5.0:
        return "moderate"
    else:
        return "low"

# Helper function to detect urban location
def is_urban(state, address):
    """
    Detect if institution is in urban area based on city names.
    """
    urban_cities = [
        'kuala lumpur', 'kl', 'shah alam', 'petaling jaya', 'subang',
        'johor bahru', 'penang', 'georgetown', 'ipoh', 'kuching',
        'kota kinabalu', 'melaka', 'seremban', 'klang'
    ]

    location = f"{state} {address}".lower()
    return any(city in location for city in urban_cities)

# Build new institutions JSON
print("\n[3/4] Building institutions JSON...")
new_json = []
added_count = 0
preserved_count = 0

for idx, row in df_inst.iterrows():
    inst_id = row['institution_id']

    # Check if modifiers already exist
    if inst_id in existing_modifiers:
        modifiers = existing_modifiers[inst_id]
        preserved_count += 1
    else:
        # Create new modifiers based on CSV data
        modifiers = {
            "urban": is_urban(str(row.get('State', '')), str(row.get('address', ''))),
            "cultural_safety_net": get_cultural_safety_net(row.get('Indians %')),
            "subsistence_support": False,  # Default - can be manually curated
            "strong_hostel": True if row.get('type') in ['IPTA', 'Politeknik'] else False,
            "industry_linked": "pending",  # Requires manual curation
            "supportive_culture": "pending"  # Requires manual curation
        }
        added_count += 1

    new_json.append({
        "inst_id": inst_id,
        "modifiers": modifiers
    })

print(f"  - Preserved existing modifiers: {preserved_count}")
print(f"  - Created new modifiers: {added_count}")
print(f"  - Total institutions: {len(new_json)}")

# Backup and save
print("\n[4/4] Saving institutions.json...")
backup_path = data_dir / 'backup' / 'institutions.json.pre-sync'
os.makedirs(data_dir / 'backup', exist_ok=True)

if json_path.exists():
    import shutil
    shutil.copy(json_path, backup_path)
    print(f"  - Backup saved: {backup_path}")

with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(new_json, f, indent=2, ensure_ascii=False)

print(f"  - Updated institutions.json saved: {json_path}")

# Show sample of new institutions
new_insts = [inst for inst in new_json if inst['inst_id'] not in existing_modifiers]
if new_insts:
    print(f"\n  Sample of {len(new_insts)} new institutions added:")
    for inst in new_insts[:5]:
        print(f"    - {inst['inst_id']}: cultural_safety_net={inst['modifiers']['cultural_safety_net']}, urban={inst['modifiers']['urban']}")
    if len(new_insts) > 5:
        print(f"    ... and {len(new_insts) - 5} more")

print("\n" + "=" * 60)
print("SUCCESS!")
print("=" * 60)
print(f"\nSummary:")
print(f"  - institutions.csv has: {len(df_inst)} institutions")
print(f"  - institutions.json now has: {len(new_json)} institutions")
print(f"  - Existing modifiers preserved: {preserved_count}")
print(f"  - New institutions added: {added_count}")

print(f"\nNext steps:")
print(f"  1. Review new institutions in institutions.json")
print(f"  2. Manually curate 'industry_linked' and 'supportive_culture' if needed")
print(f"  3. Adjust urban/subsistence_support/strong_hostel flags if needed")
