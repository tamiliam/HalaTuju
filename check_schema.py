import streamlit as st
from supabase import create_client
import toml
import os

# Load Secrets
try:
    secrets = toml.load(".streamlit/secrets.toml")
    url = secrets["SUPABASE_URL"]
    key = secrets["SUPABASE_KEY"]
except:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

if not url:
    print("No credentials.")
    exit()

supabase = create_client(url, key)

try:
    # Fetch 1 record
    res = supabase.table("student_profiles").select("*").limit(1).execute()
    if res.data:
        print("Columns found:", res.data[0].keys())
    else:
        print("Table empty or no access. Cannot determine columns.")
except Exception as e:
    print(f"Error: {e}")
