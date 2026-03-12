import pandas as pd
import requests
import time
import os

# Configuration
FILES_TO_PROCESS = [
    r'c:\Users\tamil\Python\HalaTuju\data\institutions.csv',
    r'c:\Users\tamil\Python\HalaTuju\data\tvet_institutions.csv'
]
USER_AGENT = "HalaTujuApp/1.0"

def get_lat_lon(query):
    """
    Geocode a query string using Nominatim.
    """
    base_url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': query,
        'format': 'json',
        'limit': 1
    }
    headers = {
        'User-Agent': USER_AGENT
    }
    
    try:
        response = requests.get(base_url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data:
            return float(data[0]['lat']), float(data[0]['lon'])
        else:
            return None, None
            
    except Exception as e:
        print(f"    Error querying '{query}': {e}")
        return None, None

def process_file(file_path):
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    print(f"\nProcessing {file_path}...")
    df = pd.read_csv(file_path)

    # Add columns if they don't exist
    if 'latitude' not in df.columns:
        df['latitude'] = None
    if 'longitude' not in df.columns:
        df['longitude'] = None

    updated_count = 0
    
    for index, row in df.iterrows():
        # Check if we already have valid coordinates
        lat = row['latitude']
        lon = row['longitude']
        
        # Simple check for existing valid float values
        try:
             if pd.notna(lat) and pd.notna(lon) and float(lat) != 0.0:
                 continue
        except ValueError:
            pass
            
        name = row['institution_name']
        address = row['address']
        state = row['State']
        
        if not isinstance(name, str): name = ""
        if not isinstance(address, str): address = ""
        if not isinstance(state, str): state = ""
        
        print(f"Geocoding {index+1}/{len(df)}: {name}")

        # Strategy 1: Full Address (cleaned)
        # Remove newlines for query
        query1 = address.replace('\n', ', ').strip()
        
        # Strategy 2: Name + State (often most accurate for institutions)
        query2 = f"{name}, {state}, Malaysia"
        
        # Strategy 3: Name only
        query3 = f"{name}, Malaysia"
        
        # Strategy 4: City + State extraction (simplistic)
        # Trying to find zipcode and take text after it? 
        # For now, let's stick to name-based strategies as they are powerful for landmarks.
        
        strategies = [query1, query2, query3]
        
        found_lat, found_lon = None, None
        
        for q in strategies:
            if not q.strip(): continue
            # Avoid too short queries
            if len(q) < 5: continue
            
            # print(f"  Trying: {q[:50]}...")
            found_lat, found_lon = get_lat_lon(q)
            time.sleep(1.1) # Rate limit
            
            if found_lat:
                print(f"  -> Match found for '{q[:30]}...': {found_lat}, {found_lon}")
                break
        
        if found_lat:
            df.at[index, 'latitude'] = found_lat
            df.at[index, 'longitude'] = found_lon
            updated_count += 1
        else:
            print(f"  -> FAILED to geocode.")

    if updated_count > 0:
        print(f"Saving {updated_count} updates to {file_path}...")
        df.to_csv(file_path, index=False)
    else:
        print("No updates needed.")

def main():
    for f in FILES_TO_PROCESS:
        process_file(f)

if __name__ == "__main__":
    main()
