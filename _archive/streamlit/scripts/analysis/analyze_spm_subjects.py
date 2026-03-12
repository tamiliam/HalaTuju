
import pandas as pd
import re
import os

# Current Attributes (from main.py / engine.py knowledge)
CURRENT_SUBJECTS = {
    "SCIENCE_STREAM": ["Physics", "Chemistry", "Biology", "Add Maths"],
    "CORE": ["Bahasa Melayu", "English", "Mathematics", "History"],
    "ARTS_HUMANITIES": [
        "Economy", "Geography", "Perniagaan", "Prinsip Perakaunan", 
        "Pendidikan Moral", "Pendidikan Islam", "Tassawwur Islam"
    ],
    "LANGUAGES": ["Bahasa Arab", "Bahasa Cina", "Bahasa Tamil", "Literature (eng)", "Literature (bm)"],
    "TECH_VOC": ["Pertanian", "Sains Rumah Tangga", "Sains Komputer", "Grafik Komunikasi Teknikal", "Reka Cipta"],
    "ARTS_CREATIVE": ["Pendidikan Seni Visual", "Seni Halus", "Muzik"] 
    # Note: This list is illustrative for comparison. The script will be more exhaustive.
}

# Regex to capture subjects after keywords like 'Gred C', 'Lulus', 'Kepujian', 'Gred B'
# Patterns:
# - "Kepujian dalam (Subject)"
# - "Gred C dalam (Subject)"
# - "Subject (Gred C)"
# - "sekurang-kurangnya Gred C ... dalam mata pelajaran berikut: ... list ..." (Harder)

def extract_subjects():
    path = 'c:/Users/tamil/Python/Random/archive/spm/intermediate/mohe_programs_with_kampus.csv'
    try:
        df = pd.read_csv(path, encoding='cp1252', on_bad_lines='skip')
    except:
        df = pd.read_csv(path, encoding='utf-8', on_bad_lines='skip')

    # Columns to Scan
    text_cols = ['syarat_am', 'syarat_khas']
    
    # Keyword Stoplist (common non-subject words found in these contexts)
    stoplist = [
        'salah', 'satu', 'mata', 'pelajaran', 'berikut', 'di', 'peringkat', 'spm',
        'dan', 'atau', 'gred', 'kepujian', 'lulus', 'sekurang-kurangnya', 'termasuk',
        'manakala', 'calon', 'tidak', 'rabun', 'warna', 'fizikal', 'temuduga', 'ujian', 'medsi', 'muet', 'tahap'
    ]
    
    extracted_freq = {}
    
    # Regex Strategy: Look for Capitalized Words or Phrases commonly used as subjects
    # But usually they appear in lists.
    # Approach: Split text by comma/semicolon/conditions, look for "Physics", "Fizik", "Kimia", "Biologi".
    # Actually, we want to find NEW ones.
    
    # Better approach might be to look for pattern: 
    # (Gred|Lulus|Kepujian) [A-Z0-9]+ (dalam|pada) (.+?) (dan|atau|;|.)
    
    pattern = re.compile(r'(?:kepujian|gred|lulus)\s+(?:[A-Z0-9-]+\+?)\s+(?:dalam|pada)\s+(mata\s+pelajaran\s+)?(.+?)(?=\s+(?:dan|atau|serta|manakala|;|\.)|$)', re.IGNORECASE)
    
    processed_count = 0
    for col in text_cols:
        if col not in df.columns: continue
        
        for text in df[col].dropna():
            processed_count += 1
            # Normalize
            text = text.replace('\n', ' ').strip()
            
            matches = pattern.findall(text)
            for m in matches:
                # m is tuple: (optional "mata pelajaran ", subject_phrase)
                raw_subj = m[1].strip().upper()
                
                # Cleanup
                # Remove brackets
                raw_subj = re.sub(r'\(.*?\)', '', raw_subj).strip()
                # Remove trailing words if match was greedy
                if "DAN " in raw_subj: raw_subj = raw_subj.split("DAN ")[0]
                if "ATAU " in raw_subj: raw_subj = raw_subj.split("ATAU ")[0]
                
                if len(raw_subj) < 3 or raw_subj.lower() in stoplist: continue
                
                extracted_freq[raw_subj] = extracted_freq.get(raw_subj, 0) + 1

    # Generate Report
    with open('spm_subject_analysis_report.md', 'w', encoding='utf-8') as f:
        f.write("# SPM Subject Analysis Report\n\n")
        f.write(f"Scanned {processed_count} requirement fields.\n")
        f.write("Identified the following potential subjects (sorted by frequency):\n\n")
        
        # Sort
        sorted_items = sorted(extracted_freq.items(), key=lambda x: x[1], reverse=True)
        
        # Categorize
        f.write("## 1. High Frequency (>50 mentions)\n")
        for k, v in sorted_items:
            if v > 50:
                f.write(f"- [ ] **{k}** ({v})\n")
                
        f.write("\n## 2. Medium Frequency (10-50 mentions)\n")
        for k, v in sorted_items:
            if 10 <= v <= 50:
                f.write(f"- [ ] {k} ({v})\n")
                
        f.write("\n## 3. Low Frequency (<10 mentions) - Potential Niche Subjects\n")
        for k, v in sorted_items:
            if v < 10:
                f.write(f"- [ ] {k} ({v})\n")

    print("Analysis complete. Report written to spm_subject_analysis_report.md")

if __name__ == "__main__":
    extract_subjects()
