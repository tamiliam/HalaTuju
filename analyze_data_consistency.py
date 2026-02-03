
import pandas as pd
import numpy as np

def normalize_name(name):
    if not isinstance(name, str):
        return ""
    return name.upper().strip()

def read_csv_safe(path):
    for enc in ['utf-8', 'cp1252', 'latin1']:
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError:
            continue
    print(f"Failed to read {path}")
    return pd.DataFrame()

def analyze_consistency():
    print("--- LOADING DATA ---")
    # 1. Load Files
    mohe_khas_path = 'c:/Users/tamil/Python/Random/archive/spm/intermediate/mohe_programs_with_kampus.csv'
    uni_courses_path = 'c:/Users/tamil/Python/Random/data/spm/university_courses.csv'
    ht_courses_path = 'c:/Users/tamil/Python/HalaTuju/data/courses.csv'

    df_mohe = read_csv_safe(mohe_khas_path)
    df_uni = read_csv_safe(uni_courses_path)
    df_ht = read_csv_safe(ht_courses_path)

    print(f"MOHE Khas Rows: {len(df_mohe)}")
    print(f"Uni Courses Rows: {len(df_uni)}")

    # 2. Compare Files (MOHE vs Uni Courses)
    print("\n--- FILE COMPARISON ---")
    
    # Common codes
    common_codes = set(df_mohe['code']).intersection(set(df_uni['code']))
    print(f"Common Codes: {len(common_codes)}")
    
    # Unique to MOHE
    only_mohe = set(df_mohe['code']) - set(df_uni['code'])
    print(f"Codes ONLY in MOHE Khas: {len(only_mohe)}")
    if len(only_mohe) > 0:
        print("Sample unique to MOHE:", list(only_mohe)[:5])
        
    # Unique to Uni
    only_uni = set(df_uni['code']) - set(df_mohe['code'])
    print(f"Codes ONLY in Uni Courses: {len(only_uni)}")
    
    # Check consistency of MERIT for common codes
    df_mohe_sub = df_mohe[df_mohe['code'].isin(common_codes)][['code', 'merit']].set_index('code')
    df_uni_sub = df_uni[df_uni['code'].isin(common_codes)][['code', 'merit']].set_index('code')
    
    merged = df_mohe_sub.join(df_uni_sub, lsuffix='_mohe', rsuffix='_uni')
    # Clean merit (remove %)
    merged['m_mohe'] = pd.to_numeric(merged['merit_mohe'].str.replace('%','', regex=False), errors='coerce')
    merged['m_uni'] = pd.to_numeric(merged['merit_uni'].str.replace('%','', regex=False), errors='coerce')
    
    # Compare while handling NaNs (mismatches only if one is valid and other isn't, or values differ)
    # We ignore case where both are NaN
    diff = merged[
        (merged['m_mohe'] != merged['m_uni']) & 
        ~(merged['m_mohe'].isna() & merged['m_uni'].isna())
    ]
    print(f"Merit Mismatches in Common Codes: {len(diff)}")
    if len(diff) > 0:
        print(diff[['merit_mohe', 'merit_uni']].head())

    # Check content of Uni Courses for Poly/KK
    # 3. Analyze Orphans & Naming Variations
    print("\n--- POLYTECHNIC ORPHANS & VARIATIONS ---")
    
    # Filter MOHE for Poly
    mohe_poly = df_mohe[df_mohe['university'].astype(str).str.contains('Politeknik', case=False) | df_mohe['program_name'].astype(str).str.upper().str.contains('POLITEKNIK')].copy()
    mohe_poly['norm_name'] = mohe_poly['program_name'].apply(normalize_name)
    
    # Filter HT for Poly
    ht_poly = df_ht[df_ht['course_id'].str.contains('POLY')].copy()
    ht_poly['norm_name'] = ht_poly['course'].apply(normalize_name)
    
    # Orphans: In MOHE but not in HT
    ht_names = set(ht_poly['norm_name'])
    orphans = mohe_poly[~mohe_poly['norm_name'].isin(ht_names)]

    # Write results to file
    with open('consistency_report.txt', 'w', encoding='utf-8') as f:
        f.write("--- FILE COMPARISON ---\n")
        f.write(f"Common Codes: {len(common_codes)}\n")
        f.write(f"Codes ONLY in MOHE Khas: {len(only_mohe)}\n")
        f.write(f"Codes ONLY in Uni Courses: {len(only_uni)}\n")
        f.write(f"Merit Mismatches: {len(diff)}\n")
        
        f.write("\n--- POLYTECHNIC ORPHANS & VARIATIONS ---\n")
        f.write(f"Total Poly in MOHE: {len(mohe_poly)}\n")
        f.write(f"Orphaned Poly Courses (In MOHE, not in HT): {len(orphans)}\n\n")
        
        f.write("Checking for 'Teknologi Maklumat' variations in Orphans:\n")
        it_orphans = orphans[orphans['norm_name'].str.contains('TEKNOLOGI MAKLUMAT')]
        if it_orphans.empty:
             f.write(" - None found.\n")
        for _, row in it_orphans.iterrows():
            f.write(f" - [{row['code']}] {row['program_name']}\n")
            
        f.write("\nChecking for 'Rekabentuk' variations in Orphans:\n")
        design_orphans = orphans[orphans['norm_name'].str.contains('REKA BENTUK|REKABENTUK')]
        if design_orphans.empty:
             f.write(" - None found.\n")
        for _, row in design_orphans.iterrows():
            f.write(f" - [{row['code']}] {row['program_name']}\n")

        # Check if generic "DIPLOMA TEKNOLOGI MAKLUMAT" exists
        generic_it = mohe_poly[mohe_poly['norm_name'] == 'DIPLOMA TEKNOLOGI MAKLUMAT']
        if not generic_it.empty:
            f.write("\nFOUND GENERIC 'DIPLOMA TEKNOLOGI MAKLUMAT':\n")
            f.write(generic_it[['code', 'program_name', 'university']].to_string())
        else:
            f.write("\nNO EXACT MATCH FOR 'DIPLOMA TEKNOLOGI MAKLUMAT'")
            
    print("Report written to consistency_report.txt")

if __name__ == "__main__":
    analyze_consistency()
