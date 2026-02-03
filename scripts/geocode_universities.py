"""
Geocode University Addresses
Adds latitude and longitude to univ_institutions.csv based on addresses
"""

import pandas as pd
import time
from pathlib import Path

try:
    from geopy.geocoders import Nominatim
    from geopy.exc import GeocoderTimedOut, GeocoderServiceError
except ImportError:
    print("ERROR: geopy not installed. Install with: pip install geopy")
    exit(1)

# Paths
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
INPUT_FILE = DATA_DIR / "univ_institutions.csv"
OUTPUT_FILE = DATA_DIR / "univ_institutions.csv"

def geocode_address(geocoder, address, retry=3):
    """
    Geocode an address with retry logic
    """
    for attempt in range(retry):
        try:
            location = geocoder.geocode(address, timeout=10)
            if location:
                return location.latitude, location.longitude
            else:
                # Try without postcode if first attempt fails
                address_parts = address.split(',')
                if len(address_parts) > 2:
                    # Try with just city and state
                    simplified = f"{address_parts[-2].strip()}, {address_parts[-1].strip()}"
                    location = geocoder.geocode(simplified, timeout=10)
                    if location:
                        return location.latitude, location.longitude
                return None, None
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            print(f"  Attempt {attempt + 1} failed: {e}")
            if attempt < retry - 1:
                time.sleep(2)
            continue
    return None, None

def main():
    # Load institutions
    df = pd.read_csv(INPUT_FILE)

    print(f"Loaded {len(df)} institutions")
    print(f"\nGeocoding addresses using OpenStreetMap Nominatim...")
    print("This respects rate limits (1 request/second) so will take ~20 seconds.\n")

    # Initialize geocoder
    geocoder = Nominatim(user_agent="halatuju_university_geocoder")

    # Geocode each address
    geocoded_count = 0
    failed = []

    for idx, row in df.iterrows():
        institution = row['institution_name']
        address = row['address']
        acronym = row['acronym']

        print(f"[{idx + 1}/{len(df)}] {acronym}: ", end='', flush=True)

        # Try full address first, then with university name
        search_address = f"{address}, Malaysia"
        lat, lon = geocode_address(geocoder, search_address)

        if lat is None:
            # Try with institution name
            search_address = f"{institution}, {address}, Malaysia"
            lat, lon = geocode_address(geocoder, search_address)

        if lat is not None:
            df.at[idx, 'latitude'] = lat
            df.at[idx, 'longitude'] = lon
            geocoded_count += 1
            print(f"OK ({lat:.6f}, {lon:.6f})")
        else:
            failed.append(f"{acronym}: {address}")
            print(f"FAILED")

        # Respect rate limit (1 request per second)
        time.sleep(1.1)

    # Save results
    df.to_csv(OUTPUT_FILE, index=False)

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Successfully geocoded: {geocoded_count}/{len(df)}")
    print(f"Failed: {len(failed)}")

    if failed:
        print("\nFailed addresses:")
        for addr in failed:
            print(f"  - {addr}")
        print("\nThese may need manual geocoding or address correction.")

    print(f"\nOutput saved to: {OUTPUT_FILE}")
    print("\nNote: Coordinates are from OpenStreetMap Nominatim.")
    print("For production use, consider verifying accuracy against official sources.")

if __name__ == "__main__":
    main()
