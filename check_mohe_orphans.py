
import pandas as pd
import re

def normalize_name(name):
    if not isinstance(name, str):
        return ""
    # Remove extra spaces, standardize to uppercase
    name = name.upper().strip()
    # Remove #, *, etc.
    name = re.sub(r'[#*]', '', name).strip()
    # Normalize 'REKABENTUK' -> 'REKA BENTUK' for consistent matching
    name = name.replace('REKABENTUK', 'REKA BENTUK')
    return name

def read_csv_safe(path):
    for enc in ['utf-8', 'cp1252', 'latin1']:
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError:
            continue
    print(f"Failed to read {path}")
    return pd.DataFrame()

def check_orphans():
    print("--- LOADING DATA ---")
    mohe_file = 'c:/Users/tamil/Python/Random/archive/spm/intermediate/mohe_programs_with_kampus.csv'
    ht_file = 'c:/Users/tamil/Python/HalaTuju/data/courses.csv' # Contains IDs and Names
    req_file = 'c:/Users/tamil/Python/HalaTuju/data/requirements.csv' # Contains IDs

    df_mohe = read_csv_safe(mohe_file)
    df_ht_courses = read_csv_safe(ht_file)
    df_ht_req = read_csv_safe(req_file)

    # 1. UA Programs (Check by Code)
    # MOHE UA codes usually start with U... (e.g. UH, UP, UY)
    # HT UA codes also use UPU codes.
    
    # Filter MOHE for UA
    # Heuristic: Code starts with 'U' and length > 3
    mohe_ua = df_mohe[df_mohe['code'].astype(str).str.startswith('U')].copy()
    
    # Filter HT for UA
    # HT IDs in requirements.csv AND new_pathways_requirements.csv AND courses.csv?
    # Currently UA requirements are NOT yet generated (per task.md), so we expect high orphan count.
    # But let's check matches in courses.csv just in case.
    
    df_ht_courses['course_id'] = df_ht_courses['course_id'].astype(str)
    ht_ua_ids = set(df_ht_courses[df_ht_courses['course_id'].str.startswith('U')]['course_id'])
    
    print(f"DEBUG: HT UA IDs in courses.csv: {len(ht_ua_ids)}")
    
    # Find MOHE UA Orphans
    mohe_ua_codes = set(mohe_ua['code'])
    ua_orphans = mohe_ua[~mohe_ua['code'].isin(ht_ua_ids)]
    
    print(f"\n[UA] MOHE Codes: {len(mohe_ua)}")
    print(f"[UA] Orphans (In MOHE, not in HT): {len(ua_orphans)}")
    if not ua_orphans.empty:
        # print(ua_orphans[['code', 'program_name']].head().to_string())
        pass 

    # 2. Poly/KK Programs (Check by Name)
    # Filter MOHE for Poly/KK
    mohe_poly_kk = df_mohe[~df_mohe['code'].astype(str).str.startswith('U')].copy()
    mohe_poly_kk['norm_name'] = mohe_poly_kk['program_name'].apply(normalize_name)
    
    # Filter HT for Poly/KK (Ids start with POLY or KKOM)
    ht_poly_kk = df_ht_req[df_ht_req['course_id'].astype(str).str.contains('POLY|KKOM')].copy()
    # Need names from courses.csv
    ht_poly_kk = ht_poly_kk.merge(df_ht_courses, on='course_id', how='left')
    ht_poly_kk['norm_name'] = ht_poly_kk['course'].apply(normalize_name)
    
    # Handle the known mappings
    # 1. Generic IT: If MOHE has 'DIPLOMA TEKNOLOGI MAKLUMAT', it is used by HT 'POLY-DIP-072'...'077'
    # So if 'DIPLOMA TEKNOLOGI MAKLUMAT' is in MOHE, it IS mapped, even if exact name isn't in HT.
    # We should add the mapped names to the HT set.
    
    ht_names = set(ht_poly_kk['norm_name'])
    # Add mapped names manually to avoid false positives
    ht_names.add(normalize_name("DIPLOMA TEKNOLOGI MAKLUMAT"))
    
    pk_orphans = mohe_poly_kk[~mohe_poly_kk['norm_name'].isin(ht_names)]
    
    print(f"\n[POLY/KK] MOHE Rows: {len(mohe_poly_kk)}")
    print(f"[POLY/KK] Orphans (In MOHE, not in HT): {len(pk_orphans)}")
    
    if not pk_orphans.empty:
        print(pk_orphans[['code', 'program_name', 'university']].to_string())

    # Write detailed report
    with open('mohe_orphans.txt', 'w', encoding='utf-8') as f:
        f.write("--- MOHE ORPHANS REPORT ---\n")
        f.write("Courses present in MOHE data but NOT found in HalaTuju.\n\n")
        
        f.write(f"[UA PROGRAMS] Orphans: {len(ua_orphans)}\n")
        if not ua_orphans.empty:
            f.write(ua_orphans[['code', 'program_name', 'university']].to_string())
        
        f.write(f"\n\n[POLY/KK PROGRAMS] Orphans: {len(pk_orphans)}\n")
        if not pk_orphans.empty:
            f.write(pk_orphans[['code', 'program_name', 'university']].to_string())

if __name__ == "__main__":
    check_orphans()
