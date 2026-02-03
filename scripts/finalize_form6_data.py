
import pandas as pd
import os

def finalize_data():
    # 1. Load Clean Data (Base)
    clean_path = os.path.join('data', 'form6_schools_clean.csv')
    df_clean = pd.read_csv(clean_path)
    print(f"Loaded Clean Data: {len(df_clean)} rows")
    
    # 2. Load Raw Data (Subjects)
    raw_path = os.path.join('data', 'form6_schools.csv')
    df_raw = pd.read_csv(raw_path)
    
    # 3. Merge
    print("Merging subject data...")
    df_merged = pd.merge(
        df_clean, 
        df_raw[['KOD_SEKOLAH', 'PAKEJ_MATA_PELAJARAN', 'MATA_PELAJARAN']], 
        left_on='institution_id', 
        right_on='KOD_SEKOLAH', 
        how='left'
    )
    
    # 4. Determine Subcategory
    def get_subcategory(pkg):
        pkg = str(pkg).upper()
        parts = [p.strip() for p in pkg.split(';')]
        
        has_science = 'SAINS' in parts
        has_arts = 'SAINS SOSIAL' in parts
        
        if has_science and has_arts:
            return 'STPM Campuran'
        elif has_science:
            return 'STPM Sains'
        elif has_arts:
            return 'STPM Sastera'
        else:
            # Fallback
            if 'SAINS' in pkg and 'SAINS SOSIAL' not in pkg: return 'STPM Sains'
            return 'STPM Sastera' # Default
            
    df_merged['subcategory'] = df_merged['PAKEJ_MATA_PELAJARAN'].apply(get_subcategory)
    
    # 5. Explode Subjects (Binary Columns)
    # Collect all unique subjects
    all_subjects = set()
    for subjects in df_merged['MATA_PELAJARAN'].dropna():
        subs = [s.strip() for s in str(subjects).split(';')]
        for s in subs:
            if s: 
                # Clean subject code? e.g. "BI (MUET)" -> "BI_MUET"? or just "BI (MUET)"
                # User wants lower case headers.
                # Let's clean special chars for headers: "BI (MUET)" -> "subject_bi_muet"
                all_subjects.add(s)
    
    print(f"Found {len(all_subjects)} unique subjects.")
    
    # Create Binary Columns
    for sub in sorted(list(all_subjects)):
        # Create header name
        # Remove parentheses, replace spaces with underscore, lowercase
        safe_name = sub.replace('(', '').replace(')', '').replace(' ', '_').lower()
        col_name = f"subject_{safe_name}"
        
        # Populate
        # Check if 'sub' is in the row's MATA_PELAJARAN string
        # Need exact match logic to avoid "ART" matching "ARTS"? 
        # But here subjects are distinct strings like "BM", "BIO". "BI" won't match "BIO" if we split carefully.
        
        def has_subject(row_subs, target_sub):
            if pd.isna(row_subs): return 0
            # Normalize list
            current_subs = [s.strip() for s in str(row_subs).split(';')]
            return 1 if target_sub in current_subs else 0
            
        df_merged[col_name] = df_merged['MATA_PELAJARAN'].apply(lambda x: has_subject(x, sub))

    # 6. Cleanup
    # Drop temporary merge columns
    df_final = df_merged.drop(columns=['KOD_SEKOLAH', 'PAKEJ_MATA_PELAJARAN', 'MATA_PELAJARAN'])
    
    # Ensure columns are lower case? User said "headers in lower case only".
    # Existing columns: institution_id, institution_name... are mixed/lower.
    # The new subject columns are lowercase `subject_xxx`.
    # subcategory values are Title Case (STPM Sains).
    
    # Save
    output_path = os.path.join('data', 'form6_schools_final.csv')
    df_final.to_csv(output_path, index=False)
    
    print(f"Saved to {output_path}")
    print("Columns:", list(df_final.columns))
    print("Sample Subcategories:", df_final['subcategory'].value_counts())

if __name__ == "__main__":
    finalize_data()
