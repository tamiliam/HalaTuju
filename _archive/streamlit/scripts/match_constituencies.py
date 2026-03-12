"""
Match Universities with Political Constituencies
Uses point-in-polygon spatial matching to assign DUN and Parliament data
"""

import pandas as pd
from pathlib import Path

try:
    from shapely.wkt import loads
    from shapely.geometry import Point
except ImportError:
    print("ERROR: shapely not installed. Install with: pip install shapely")
    exit(1)

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
MISC_DIR = PROJECT_ROOT.parent / "Misc"

CONSTITUENCIES_FILE = MISC_DIR / "Political Constituencies.csv"
INSTITUTIONS_FILE = DATA_DIR / "university_institutions.csv"

def load_constituencies():
    """Load political constituencies with polygon data"""
    print(f"Loading constituencies from: {CONSTITUENCIES_FILE}")
    # Try different encodings
    for encoding in ['utf-8', 'latin-1', 'cp1252']:
        try:
            df = pd.read_csv(CONSTITUENCIES_FILE, encoding=encoding)
            print(f"Loaded {len(df)} constituencies (encoding: {encoding})")
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("Failed to load file with any encoding")

    # Parse WKT polygons
    constituencies = []
    for idx, row in df.iterrows():
        try:
            polygon = loads(row['WKT'])
            constituencies.append({
                'polygon': polygon,
                'dun': row['DUN'],
                'parliament': row['Parliment'],  # Note: typo in original file
                'indians': row.get('Indians', ''),
                'indians_pct': row.get('Indians %', ''),
                'ave_income': row.get('Ave. Income', '')
            })
        except Exception as e:
            print(f"  Warning: Failed to parse polygon for {row['DUN']}: {e}")
            continue

    print(f"Successfully parsed {len(constituencies)} polygons")
    return constituencies

def find_constituency(lat, lon, constituencies):
    """Find which constituency contains the given point"""
    if pd.isna(lat) or pd.isna(lon):
        return None

    point = Point(lon, lat)  # Note: Shapely uses (lon, lat) order

    for const in constituencies:
        try:
            if const['polygon'].contains(point):
                return const
        except Exception:
            continue

    return None

def main():
    print("=" * 60)
    print("University Constituency Matcher")
    print("=" * 60)

    # Load data
    constituencies = load_constituencies()

    print(f"\nLoading universities from: {INSTITUTIONS_FILE}")
    unis_df = pd.read_csv(INSTITUTIONS_FILE)
    print(f"Loaded {len(unis_df)} universities")

    # Match each university
    print("\nMatching universities to constituencies...")
    matched = 0
    unmatched = []

    for idx, row in unis_df.iterrows():
        name = row['institution_name']
        acronym = row['acronym']
        lat = row['latitude']
        lon = row['longitude']

        print(f"\n[{idx + 1}/{len(unis_df)}] {acronym} - {name}")
        print(f"  Coordinates: ({lat:.4f}, {lon:.4f})")

        const = find_constituency(lat, lon, constituencies)

        if const:
            unis_df.at[idx, 'dun'] = const['dun']
            unis_df.at[idx, 'parliament'] = const['parliament']
            unis_df.at[idx, 'indians'] = const['indians']
            unis_df.at[idx, 'indians_%'] = const['indians_pct']
            unis_df.at[idx, 'ave_income'] = const['ave_income']

            print(f"  MATCHED:")
            print(f"    DUN: {const['dun']}")
            print(f"    Parliament: {const['parliament']}")
            print(f"    Indians: {const['indians']} ({const['indians_pct']})")
            print(f"    Ave Income: {const['ave_income']}")
            matched += 1
        else:
            unis_df.at[idx, 'dun'] = ''
            unis_df.at[idx, 'parliament'] = ''
            print(f"  NOT MATCHED (coordinates outside constituencies)")
            unmatched.append(f"{acronym} - {name}")

    # Save updated file
    unis_df.to_csv(INSTITUTIONS_FILE, index=False)

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Total universities: {len(unis_df)}")
    print(f"Matched: {matched}")
    print(f"Unmatched: {len(unmatched)}")

    if unmatched:
        print("\nUnmatched universities:")
        for uni in unmatched:
            print(f"  - {uni}")
        print("\nThese may be outside Malaysia or have incorrect coordinates.")

    print(f"\nUpdated file saved to: {INSTITUTIONS_FILE}")

if __name__ == "__main__":
    main()
