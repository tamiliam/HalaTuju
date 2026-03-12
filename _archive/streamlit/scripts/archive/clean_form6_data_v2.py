
import pandas as pd
import os
import re

def clean_data():
    input_path = os.path.join('data', 'form6_schools.csv')
    output_path = os.path.join('data', 'form6_schools_clean.csv')
    
    print(f"Loading {input_path}...")
    df = pd.read_csv(input_path)
    
    # --- 1. School Type Inference ---
    def get_school_type(name):
        name_u = str(name).upper()
        if any(x in name_u for x in ['KOLEJ TINGKATAN ENAM', 'KTE', 'KOLEJ T6']):
            return 'Kolej Tingkatan 6'
        elif any(x in name_u for x in ['SMJK']):
            return 'SMJK'
        elif any(x in name_u for x in ['SMKA', 'SMA ', 'SAM ']):
            return 'Agama'
        elif any(x in name_u for x in ['SEKOLAH TINGGI', 'HIGH SCHOOL']):
            return 'Sekolah Tinggi'
        elif 'KOLEJ' in name_u: # Catch-all for other colleges
            return 'Kolej'
        elif any(x in name_u for x in ['SMK', 'SEKOLAH MENENGAH KEBANGSAAN']):
            return 'SMK'
        else:
            return 'Other'

    df['subcategory'] = 'STPM' # Static
    df['School_Type'] = df['NAMA_SEKOLAH'].apply(get_school_type)
    
    # --- 2. School Name Formatting ---
    def clean_name(name):
        # Basic Title Case
        s = str(name).title().replace("'S", "'s") 
        
        # Restore common acronyms in Name
        replacements = {
            'Smk': 'SMK',
            'Smjk': 'SMJK',
            'Smka': 'SMKA',
            'Sma': 'SMA',
            'Kte': 'KTE',
            'Tun': 'Tun', # Keep Title Case
            'Felda': 'FELDA'
        }
        
        words = s.split()
        new_words = [replacements.get(w, w) for w in words]
        
        # Handle parentheses like (P) -> (P) not (p)
        # Actually .title() handles (P) fine usually -> ( P )
        
        return " ".join(new_words)
    
    df['institution_name'] = df['NAMA_SEKOLAH'].apply(clean_name)

    # --- 3. Address Cleaning ---
    
    # Abbreviation Map (lowercase key -> Title Case value)
    abbr_map = {
        'jln': 'Jalan', 'jln.': 'Jalan',
        'tmn': 'Taman', 'tmn.': 'Taman',
        'kg': 'Kampung', 'kg.': 'Kampung',
        'bkt': 'Bukit', 'bkt.': 'Bukit',
        'sg': 'Sungai', 'sg.': 'Sungai',
        'lrg': 'Lorong', 'lrg.': 'Lorong',
        'pdg': 'Padang', 'pdg.': 'Padang',
        'bt': 'Batu', 'bt.': 'Batu',
        'km': 'KM', 'km.': 'KM',
        'jkr': 'JKR',
        'ptd': 'PTD'
    }
    
    # Known Acronyms to restore to Uppercase
    acronyms = {'PJS', 'USJ', 'SS', 'KL', 'PJ', 'KKIP', 'FELDA', 'FELCRA', 'JKR', 'PTD'}

    def clean_address(addr):
        if pd.isna(addr): return ""
        
        # 0. Pre-formatting specific patterns
        s = str(addr)
        # Fix KM spacing: KM1 -> KM 1
        s = re.sub(r'\bKM\s?(\d+)', r'KM \1', s, flags=re.IGNORECASE)
        # Fix missing comma after KM X: KM 5 Jalan -> KM 5, Jalan
        s = re.sub(r'(KM \d+)\s+([A-Za-z])', r'\1, \2', s, flags=re.IGNORECASE)
        # Fix P.O. Box spacing
        s = re.sub(r'P\.?O\.?\s?Box', 'P.O. Box', s, flags=re.IGNORECASE)
        # Fix No. 
        s = re.sub(r'\bNo\s+(\d)', r'No. \1', s, flags=re.IGNORECASE)
        
        # 1. Flatten and Split
        flat = s.replace('\n', ', ').replace('\r', '')
        
        # Split by comma
        parts = [p.strip() for p in flat.split(',')]
        parts = [p for p in parts if p] # Remove empties
        
        cleaned_parts = []
        postcode = None
        state = None
        city = None
        
        # Helper to clean a single part
        def format_part(part_str):
            words = part_str.split()
            new_words = []
            for w in words:
                w_lower = w.lower()
                if w_lower in abbr_map:
                    new_words.append(abbr_map[w_lower])
                else:
                    t = w.title()
                    clean_w = re.sub(r'[^\w\d]', '', w).upper()
                    if re.match(r'^[A-Z]{2,}\d+$', w.upper()): 
                         t = w.upper()
                    elif clean_w in acronyms:
                         t = w.upper()
                    elif w.upper() == 'II':
                         t = 'II'
                    elif w.lower() == 'p.o.': # Handle P.O. specifically if split
                         t = 'P.O.'
                    new_words.append(t)
            return " ".join(new_words)

        # Process all parts first to clean them
        formatted_parts = [format_part(p) for p in parts]
        
        # Find Postcode index
        # Look for 5 digits OR 4 digits (Kedah/Perlis often truncated 0)
        pc_index = -1
        
        for i, p in enumerate(formatted_parts):
            # Check for 5 digits first
            if re.search(r'\b\d{5}\b', p):
                pc_index = i
                m = re.search(r'\b(\d{5})\b', p)
                if m: postcode = m.group(1)
                break # Prefer 5 digits if found?
            # Check for 4 digits (e.g. 6010)
            elif re.search(r'\b\d{4}\b', p):
                # Only accept if it looks like a separate token or at end/start
                # Avoid matching part of phone number or year? 
                m = re.search(r'\b(\d{4})\b', p)
                if m: 
                    candidate = m.group(1)
                    # Heuristic: Postcodes usually > 01000. 
                    # If 4 digits, assume it's a postcode missing '0'.
                    # Especially for Kedah/Perlis (starts with 01, 02 etc -> 1xxx, 2xxx)
                    # Or 06xxx -> 6xxx.
                    pc_index = i
                    postcode = "0" + candidate
                    
                    # Update the part in formatted_parts to reflect the padded postcode for display?
                    # We will reconstruct anyway.
        
        if pc_index != -1 and postcode:
            # Reconstruction Logic
            
            # State: Everything after postcode index
            final_state = ", ".join(formatted_parts[pc_index+1:])
            
            # Postcode Part Remnant (e.g. "83000 Batu Pahat")
            current_pc_part = formatted_parts[pc_index]
            # Replace the *original* found digits with nothing to clear it
            # Need to be careful what we matched.
            # If we matched 4 digits '6010', remove '6010'.
            
            token_to_remove = postcode if len(postcode) == 5 and postcode in current_pc_part else postcode[1:]
            remnant = current_pc_part.replace(token_to_remove, '').strip() # Remove the digits
            
            # If state was in the postcode part (ref: "83000 Johor")
            if pc_index == len(formatted_parts) - 1:
                if remnant:
                    # If remnant matches a state name? Or just assume it is state.
                    if not final_state: final_state = remnant
                    remnant = "" # Consumed as state
            
            # City: Usually the part before postcode OR the remnant before it in the same part?
            # If remnant is at the START of postcode part? "Batu Pahat 83000"
            # If remnant is detected, assume it is City if we don't have one?
            
            if remnant:
                # Assume remnant is part of City?
                # But wait, logic: "Postcode City". 
                # If source was "Batu Pahat 83000", clean logic puts 83000 first.
                final_city = remnant
            elif pc_index > 0:
                 final_city = formatted_parts[pc_index-1]
            else:
                 final_city = ""
                 
            # Street: Everything before the City part
            street_end_index = pc_index - 1 if (pc_index > 0 and not remnant) else pc_index
            if street_end_index > 0:
                final_street = ", ".join(formatted_parts[:street_end_index])
            else:
                final_street = ""
                
            # If street is empty but we have city, check if city is really street?
            # "KM 11, Lebuhraya Utara Selatan, Changlun, 6010, Kedah"
            # Parts: [KM 11], [Lebuhraya...], [Changlun], [6010], [Kedah]
            # PC Index = 3 (6010). 
            # State = Kedah
            # City = Changlun (Index 2)
            # Street = KM 11, Lebuhraya Utara Selatan
            
            # Construct: Street, Postcode City, State
            addr_str = f"{final_street}, {postcode} {final_city}, {final_state}"
            
            # Cleanup double commas or leading commas
            addr_str = re.sub(r'^,\s*', '', addr_str)
            addr_str = re.sub(r',\s*,', ',', addr_str)
            addr_str = addr_str.strip()
            
            # Ensure State is last and clean
            if addr_str.endswith(','): addr_str = addr_str[:-1]
            
            return addr_str
            
        else:
            return ", ".join(formatted_parts)

    df['address'] = df['ALAMAT'].apply(clean_address)
    
    # --- 4. Phone Formatting ---
    def clean_phone(phone):
        if pd.isna(phone): return ""
        p = str(phone).replace('-', '').replace(' ', '')
        
        # Check start
        if p.startswith('03'):
            # 03-xxxx xxxx (2 + 8 = 10 digits usually, sometimes 7?)
            if len(p) >= 2:
                return f"{p[:2]}-{p[2:]}"
        elif p.startswith('08'):
            # 08x-xxxxxx
            # 082, 088 etc
            if len(p) >= 3:
                return f"{p[:3]}-{p[3:]}"
        elif p.startswith('09') or p.startswith('04') or p.startswith('05') or p.startswith('06') or p.startswith('07'):
             # 0x-xxxxxxx (2 digit prefix)
             if len(p) >= 2:
                 return f"{p[:2]}-{p[2:]}"
        elif p.startswith('01'):
             # 01x-xxxxxxx (3 digit prefix usually)
             if len(p) >= 3:
                 return f"{p[:3]}-{p[3:]}"
                 
        return p # Return raw if no match

    df['phone'] = df['NOMBOR_TELEFON'].apply(clean_phone)
    
    # --- 5. Final Schema ---
    # Map Columns
    df = df.rename(columns={
        'KOD_SEKOLAH': 'institution_id',
        'NAMA_SEKOLAH': 'institution_name_raw', # Keep raw? No, we used applied clean_name to institution_name
        'NEGERI': 'State'
    })
    
    df['type'] = 'IPTA'
    df['category'] = 'Kolej Tingkatan 6'
    df['acronym'] = ''
    df['url'] = ''
    
    # State Title Case
    df['State'] = df['State'].str.title()
    
    # Select Final Columns matching institutions.csv
    # institution_id,institution_name,acronym,type,category,subcategory,State,address,phone,url,latitude,longitude,...
    # We will add School_Type as requested.
    
    final_cols = [
        'institution_id', 'institution_name', 'acronym', 'type', 'category', 'subcategory', 'School_Type',
        'State', 'address', 'phone', 'url'
    ]
    
    # Add dummies for lat/lon if needed for merging? No, institutions.csv has them but we don't have them yet.
    # We will leave them out for now.
    
    df_clean = df[final_cols]
    
    print(f"Cleaned shape: {df_clean.shape}")
    print("Sample:\n", df_clean.head())
    
    print("Saving to", output_path)
    df_clean.to_csv(output_path, index=False)
    print("Done.")

if __name__ == "__main__":
    clean_data()
