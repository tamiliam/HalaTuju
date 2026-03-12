
import pandas as pd
import re

def normalize_name(name):
    if not isinstance(name, str):
        return ""
    # Remove extra spaces, standardize to uppercase
    name = name.upper().strip()
    # Remove #, *, etc.
    name = re.sub(r'[#*]', '', name).strip()
    return name

def analyze_overlap():
    # Try different encodings
    def read_csv_safe(path):
        for enc in ['utf-8', 'cp1252', 'latin1']:
            try:
                return pd.read_csv(path, encoding=enc)
            except UnicodeDecodeError:
                continue
        raise ValueError(f"Failed to read {path}")

    # 1. Load HalaTuju Data
    try:
        req_df = read_csv_safe('c:/Users/tamil/Python/HalaTuju/data/requirements.csv')
        courses_df = read_csv_safe('c:/Users/tamil/Python/HalaTuju/data/courses.csv')
    except Exception as e:
        print(f"Error loading HalaTuju data: {e}")
        return

    # Filter for Poly and KK in HalaTuju
    # IDs start with POLY-DIP or KKOM-DIP or POLY-CET or KKOM-CET? 
    # Let's check IDs in requirements.csv corresponding to Poly/KK
    # Based on file inspection, IDs are POLY-DIP-XXX, KKOM-DIP-XXX, POLY-CET-XXX, KKOM-CET-XXX
    
    # We only care about courses that match the "SPM" file scope which usually contains Diplomas and Sijil/Asasi
    # The SPM file has "Diploma" and "Sijil" levels.
    
    # Merge req with courses to get names
    ht_df = pd.merge(req_df, courses_df, on='course_id', how='left')
    
    poly_ht = ht_df[ht_df['course_id'].str.startswith('POLY')].copy()
    kk_ht = ht_df[ht_df['course_id'].str.startswith('KKOM')].copy()
    
    # Normalize HT names
    poly_ht['norm_name'] = poly_ht['course'].apply(normalize_name)
    kk_ht['norm_name'] = kk_ht['course'].apply(normalize_name)
    
    print(f"HalaTuju Poly Courses: {len(poly_ht)}")
    print(f"HalaTuju KK Courses: {len(kk_ht)}")

    # 2. Load SPM Merit Data
    spm_file = 'c:/Users/tamil/Python/Random/archive/spm/intermediate/mohe_programs_with_kampus.csv'
    try:
        spm_df = read_csv_safe(spm_file)
    except Exception as e:
        print(f"Error loading SPM data: {e}")
        return

    # Filter SPM for Poly and KK
    # Identification: University column contains 'Politeknik' or 'Kolej Komuniti' OR Program Name starts with those/contains those specific codes?
    # Inspecting file: University column has "Politeknik..." and "Kolej Komuniti..."
    
    spm_df['university'] = spm_df['university'].astype(str)
    
    poly_spm = spm_df[spm_df['university'].str.contains('Politeknik', case=False, na=False) | spm_df['program_name'].str.contains('POLITEKNIK', case=False)].copy()
    kk_spm = spm_df[spm_df['university'].str.contains('Kolej Komuniti', case=False, na=False) | spm_df['program_name'].str.contains('KOLEJ KOMUNITI', case=False)].copy()
    
    # Normalize SPM names
    poly_spm['norm_name'] = poly_spm['program_name'].apply(normalize_name)
    kk_spm['norm_name'] = kk_spm['program_name'].apply(normalize_name)

    print(f"SPM Poly Courses: {len(poly_spm)}")
    print(f"SPM KK Courses: {len(kk_spm)}")
    
    # 3. Analyze Overlap (Check if HT courses exist in SPM)
    
    # Poly
    missing_poly = []
    found_poly = []
    
    spm_poly_names = set(poly_spm['norm_name'].unique())
    
    for idx, row in poly_ht.iterrows():
        name = row['norm_name']
        if name in spm_poly_names:
            found_poly.append(name)
        else:
            # Try fuzzy or partial? For now exact match on normalized.
            missing_poly.append({'id': row['course_id'], 'name': row['course']})
            
    # KK
    missing_kk = []
    found_kk = []
    
    spm_kk_names = set(kk_spm['norm_name'].unique())
    
    for idx, row in kk_ht.iterrows():
        name = row['norm_name']
        if name in spm_kk_names:
            found_kk.append(name)
        else:
            missing_kk.append({'id': row['course_id'], 'name': row['course']})
            
    # 4. Report to file
    with open('overlap_report.txt', 'w', encoding='utf-8') as f:
        f.write("--- ANALYSIS REPORT ---\n")
        
        f.write(f"\n[POLYTECHNIC] Found in SPM: {len(found_poly)} / {len(poly_ht)}\n")
        if not missing_poly:
            f.write("CONFIRMED: All HalaTuju Poly courses cleanly map to SPM data.\n")
        else:
            f.write(f"MISSING: {len(missing_poly)} Poly courses not found in SPM data:\n")
            for item in missing_poly:
                f.write(f" - {item['id']}: {item['name']}\n")
                
        f.write(f"\n[COMMUNITY COLLEGE] Found in SPM: {len(found_kk)} / {len(kk_ht)}\n")
        if not missing_kk:
            f.write("CONFIRMED: All HalaTuju KK courses cleanly map to SPM data.\n")
        else:
            f.write(f"MISSING: {len(missing_kk)} KK courses not found in SPM data:\n")
            for item in missing_kk:
                f.write(f" - {item['id']}: {item['name']}\n")
    
    print("Report written to overlap_report.txt")

if __name__ == "__main__":
    analyze_overlap()
