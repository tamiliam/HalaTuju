"""
Restore UA course details (hyperlinks, req_interview, single) from backup.

Run this after stopping Streamlit to restore the data that was deleted by
cleanup_ua_requirements.py script.
"""

import shutil
import pandas as pd

print("=" * 70)
print("Restoring UA Details from Backup")
print("=" * 70)

# Restore from backup
print("\n[1/2] Restoring details.csv from backup...")
try:
    shutil.copy('data/backup/details.csv.pre-ua-cleanup', 'data/details.csv')
    print("  SUCCESS: details.csv restored")
except Exception as e:
    print(f"  ERROR: {e}")
    print("  Make sure Streamlit is stopped (Ctrl+C)")
    exit(1)

# Verify restoration
print("\n[2/2] Verifying restoration...")
df = pd.read_csv('data/details.csv')
ua = df[df['course_id'].str.startswith('U', na=False)]

print(f"  UA courses: {len(ua)}")
print(f"  With hyperlinks: {ua['hyperlink'].notna().sum()}")
print(f"  With req_interview > 0: {(ua['req_interview'] > 0).sum()}")
print(f"  With single > 0: {(ua['single'] > 0).sum()}")

print("\n" + "=" * 70)
print("SUCCESS! UA course details restored")
print("=" * 70)
print("\nNext steps:")
print("  1. Restart Streamlit: streamlit run main.py")
print("  2. UA courses should now have working 'More Details' links")
print("  3. The destructive script has been archived and won't run again")
