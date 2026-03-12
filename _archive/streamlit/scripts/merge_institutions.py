"""
Merge institutions.csv, tvet_institutions.csv, and university_institutions.csv
into a single consolidated institutions.csv file.

Standardizes column names to Title Case with spaces (not underscores).
"""

import pandas as pd
import os
from pathlib import Path

# Get project root
script_dir = Path(__file__).parent
project_root = script_dir.parent
data_dir = project_root / 'data'

print("=" * 60)
print("Institution Files Merger")
print("=" * 60)

# Load all three files
print("\n[1/5] Loading files...")
df_poly = pd.read_csv(data_dir / 'institutions.csv')
df_tvet = pd.read_csv(data_dir / 'tvet_institutions.csv')
df_univ = pd.read_csv(data_dir / 'university_institutions.csv')

print(f"  - institutions.csv: {len(df_poly)} rows")
print(f"  - tvet_institutions.csv: {len(df_tvet)} rows")
print(f"  - university_institutions.csv: {len(df_univ)} rows")

# Standardize column names (Title Case, spaces not underscores)
print("\n[2/5] Standardizing column names...")

standard_columns = [
    'institution_id',
    'institution_name',
    'acronym',
    'type',
    'category',
    'subcategory',
    'State',  # Title Case
    'address',
    'phone',
    'url',
    'latitude',
    'longitude',
    'DUN',  # Uppercase
    'Parliament',  # Title Case
    'Indians',  # Title Case
    'Indians %',  # Space, not underscore
    'Ave. Income'  # Space + period
]

# Rename university columns to match standard using dictionary mapping
univ_column_mapping = {
    'state': 'State',
    'dun': 'DUN',
    'parliament': 'Parliament',
    'indians': 'Indians',
    'indians_%': 'Indians %',
    'ave_income': 'Ave. Income'
}
df_univ = df_univ.rename(columns=univ_column_mapping)

# Verify all have same columns
print(f"  - Poly columns: {list(df_poly.columns)}")
print(f"  - TVET columns: {list(df_tvet.columns)}")
print(f"  - Univ columns (after rename): {list(df_univ.columns)}")

# Ensure all dataframes have exactly the same columns in the same order
for df, name in [(df_poly, 'Poly'), (df_tvet, 'TVET'), (df_univ, 'Univ')]:
    if list(df.columns) != standard_columns:
        print(f"\n  WARNING: {name} columns don't match standard!")
        print(f"    Expected: {standard_columns}")
        print(f"    Got: {list(df.columns)}")
        # Try to reorder
        df = df[standard_columns]

# Concatenate all three
print("\n[3/5] Merging files...")
df_merged = pd.concat([df_poly, df_tvet, df_univ], ignore_index=True)

print(f"  - Total institutions: {len(df_merged)}")
print(f"  - Poly/KK: {len(df_poly)}")
print(f"  - TVET: {len(df_tvet)}")
print(f"  - Universities: {len(df_univ)}")

# Check for duplicate institution IDs
print("\n[4/5] Checking for duplicates...")
duplicates = df_merged[df_merged.duplicated(subset=['institution_id'], keep=False)]
if len(duplicates) > 0:
    print(f"  WARNING: Found {len(duplicates)} duplicate institution IDs!")
    print(duplicates[['institution_id', 'institution_name']])
else:
    print("  [OK] No duplicates found")

# Backup original file
print("\n[5/5] Saving merged file...")
backup_path = data_dir / 'backup' / 'institutions.csv.pre-merge'
os.makedirs(data_dir / 'backup', exist_ok=True)

if (data_dir / 'institutions.csv').exists():
    import shutil
    shutil.copy(data_dir / 'institutions.csv', backup_path)
    print(f"  - Backup saved: {backup_path}")

# Save merged file
output_path = data_dir / 'institutions_merged.csv'
df_merged.to_csv(output_path, index=False)
print(f"  - Merged file saved: {output_path}")

print("\n" + "=" * 60)
print("SUCCESS!")
print("=" * 60)
print(f"\nNext steps:")
print(f"1. Review {output_path}")
print(f"2. If correct, rename to institutions.csv")
print(f"3. Move tvet_institutions.csv and university_institutions.csv to data/archive/")
print(f"4. Update src/data_manager.py to load single file")
print(f"5. Run tests: python -m unittest tests/test_golden_master.py")
