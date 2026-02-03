
import pandas as pd

def check_wbl_status():
    ids = [
        "KKOM-DIP-001", "KKOM-DIP-004", "KKOM-DIP-009", "KKOM-DIP-010",
        "KKOM-DIP-013", "KKOM-DIP-014", "KKOM-DIP-016", 
        "KKOM-CET-002", "KKOM-CET-022"
    ]
    
    try:
        # Load courses.csv
        # Using encoding safe load as per previous learnings
        df = None
        for enc in ['utf-8', 'cp1252', 'latin1']:
            try:
                df = pd.read_csv('c:/Users/tamil/Python/HalaTuju/data/courses.csv', encoding=enc)
                break
            except:
                continue
                
        if df is None:
            print("Failed to load data")
            return

        # Filter for IDs
        subset = df[df['course_id'].isin(ids)].copy()
        
        # Select relevant columns
        # Assuming columns: course_id, course, wbl, level
        # Check if 'wbl' exists
        if 'wbl' not in subset.columns:
            print("WBL column not found!")
            print(subset.columns)
            return

        # Write Table to File
        with open('wbl_full_report.txt', 'w', encoding='utf-8') as f:
            f.write("| Course ID | Course Name | WBL Status |\n")
            f.write("| :--- | :--- | :--- |\n")
            for _, row in subset.iterrows():
                wbl = "Yes" if str(row['wbl']) == '1' else "No" 
                f.write(f"| {row['course_id']} | {row['course']} | {wbl} |\n")
        print("Report written.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_wbl_status()
