
import pandas as pd
import os

def merge_merit():
    base_path = 'c:/Users/tamil/Python/HalaTuju/data'
    req_path = os.path.join(base_path, 'requirements.csv')
    merit_path = os.path.join(base_path, 'merit_cutoffs.csv')
    
    print("Loading files...")
    df_req = pd.read_csv(req_path)
    df_merit = pd.read_csv(merit_path)
    
    print(f"Original Req Rows: {len(df_req)}")
    
    # Check if merit_cutoff already exists
    if 'merit_cutoff' in df_req.columns:
        print("dropping existing merit_cutoff")
        df_req.drop(columns=['merit_cutoff'], inplace=True)
        
    # Merge
    # We valid merit for Poly/KK only here? The merit file has UA too.
    # We only merge for IDs that exist in requirements.csv (Poly/KK)
    
    merged = df_req.merge(df_merit[['course_id', 'merit_cutoff']], on='course_id', how='left')
    
    # Fill NaN with 0
    merged['merit_cutoff'] = merged['merit_cutoff'].fillna(0)
    
    print(f"Merged Req Rows: {len(merged)}")
    print("Sample with Merit:")
    print(merged[merged['merit_cutoff'] > 0][['course_id', 'merit_cutoff']].head())
    
    # Save
    merged.to_csv(req_path, index=False)
    print("Updated requirements.csv")

if __name__ == "__main__":
    merge_merit()
