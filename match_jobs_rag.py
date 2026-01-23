import csv
import os
import time
import json
import re
import numpy as np
import pickle

try:
    import google.generativeai as genai
    from google.api_core import exceptions
except ImportError:
    print("CRITICAL: google-generativeai module not found.")
    exit(1)

# Retrieve API Key
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    try:
        import streamlit as st
        API_KEY = st.secrets.get("GEMINI_API_KEY")
    except:
        pass
if not API_KEY:
    print("CRITICAL: GEMINI_API_KEY not found.")
    exit(1)

genai.configure(api_key=API_KEY)

# Models
EMBED_MODEL = "models/text-embedding-004"
LLM_MODEL = "gemini-2.0-flash" 

DATA_DIR = "data"
JOBS_FILE = os.path.join(DATA_DIR, "jobs_mapped.csv")
MASCO_FILE = os.path.join(DATA_DIR, "masco.csv")
CACHE_FILE = os.path.join(DATA_DIR, "masco_embeddings.pkl")

def load_masco():
    masco_list = []
    for enc in ['utf-8', 'cp1252', 'latin1']:
        try:
            with open(MASCO_FILE, 'r', encoding=enc) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    masco_list.append({
                        'code': row.get('kod_masco', '').strip(),
                        'title': row.get('tajuk_pekerjaan', '').strip()
                    })
            print(f"Loaded {len(masco_list)} MASCO entries using {enc}")
            break
        except Exception:
            continue
    return masco_list

def get_embeddings_batch(texts):
    results = []
    BATCH_SIZE = 50 # Lower batch size
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i+BATCH_SIZE]
        try:
            resp = genai.embed_content(
                model=EMBED_MODEL,
                content=batch,
                task_type="retrieval_document"
            )
            results.extend(resp['embedding'])
            if i % 500 == 0: print(f"   Embedded {len(results)}/{len(texts)}...")
        except Exception as e:
            print(f"   Embed Batch Error: {e}, retrying singly...")
            time.sleep(5)
            for text in batch:
                try:
                    r = genai.embed_content(model=EMBED_MODEL,content=text,task_type="retrieval_document")
                    results.append(r['embedding'])
                except:
                    results.append(None)
    return results

def get_query_embeddings_batch(texts):
    results = []
    BATCH_SIZE = 50
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i+BATCH_SIZE]
        try:
            resp = genai.embed_content(
                model=EMBED_MODEL,
                content=batch,
                task_type="retrieval_query"
            )
            results.extend(resp['embedding'])
        except:
             results.extend([None]*len(batch))
    return results

def match_with_llm(model, job_title, candidates, retries=5):
    cand_str = ""
    for c in candidates:
        cand_str += f"- {c['title']} (Code: {c['code']})\n"
        
    prompt = f"""
    You are an HR Expert. Map the Job Title to the BEST match from the candidates provided.
    
    JOB TITLE: "{job_title}"
    
    CANDIDATES:
    {cand_str}
    
    INSTRUCTIONS:
    1. Select the single best semantic match.
    2. Handle translations (e.g. "Game" -> "Permainan").
    3. If none are good, return null.
    
    Return JSON: {{"masco_code": "...", "masco_title": "..."}}
    """
    
    for attempt in range(retries):
        try:
            response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
            return json.loads(response.text)
        except Exception as e:
            if "quota" in str(e).lower() or "429" in str(e):
                wait = (attempt + 1) * 15 # Aggressive wait: 15, 30, 45...
                print(f"Rate limit for '{job_title}'. Waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"LLM Error for {job_title}: {e}")
                return {}
    return {}

def match_jobs_rag():
    print("1. Loading Data...")
    masco_list = load_masco()
    if not masco_list: return
    
    # 2. Embed MASCO (With Caching)
    masco_titles = [m['title'] for m in masco_list]
    masco_vecs = []
    
    if os.path.exists(CACHE_FILE):
        print("   Loading cached embeddings...")
        with open(CACHE_FILE, 'rb') as f:
            masco_vecs = pickle.load(f)
    else:
        print("2. Embedding MASCO (This takes time)...")
        masco_vecs = get_embeddings_batch(masco_titles)
        with open(CACHE_FILE, 'wb') as f:
            pickle.dump(masco_vecs, f)
    
    # Filter valid
    valid_indices = [i for i, v in enumerate(masco_vecs) if v is not None]
    masco_matrix = np.array([masco_vecs[i] for i in valid_indices])
    masco_lookup = [masco_list[i] for i in valid_indices]
    
    # 3. Process Jobs
    updated_rows = []
    fieldnames = []
    
    with open(JOBS_FILE, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
        
    jobs_to_process = []
    job_indices = []
    
    print("3. Scanning for unmatched jobs...")
    for idx, row in enumerate(rows):
        # Skip if manual match exists
        if row.get('masco', '').strip(): continue
        
        # SKIP only if MANUAL match exists
        if row.get('masco', '').strip(): continue
        
        # We DO NOT skip imperfect matches anymore, because we want to improve them.
        # if row.get('imperfect_masco', '').strip(): continue
        
        jobs_to_process.append(row.get('jobs', ''))
        job_indices.append(idx)
        
    print(f"   Found {len(jobs_to_process)} remaining jobs to match.")
    if not jobs_to_process:
        print("No jobs left to match.")
        return

    print("4. Embedding Jobs Batch...")
    job_vecs = get_query_embeddings_batch(jobs_to_process)
    
    # 5. RAG Loop
    print("5. RAG Matching...")
    llm_model = genai.GenerativeModel(LLM_MODEL)
    matches_found = 0
    
    for i, job_vec in enumerate(job_vecs):
        if job_vec is None: continue
        
        row_idx = job_indices[i]
        job_title = jobs_to_process[i]
        
        # A. Retrieval
        vec_a = np.array(job_vec)
        dot_products = np.dot(masco_matrix, vec_a)
        norm_a = np.linalg.norm(vec_a)
        norms_b = np.linalg.norm(masco_matrix, axis=1)
        cosine_sims = dot_products / (norm_a * norms_b)
        
        top_indices = np.argsort(cosine_sims)[-20:][::-1]
        candidates = [masco_lookup[idx] for idx in top_indices]
        
        # B. Generation
        result = match_with_llm(llm_model, job_title, candidates)
        code = result.get('masco_code', '')
        title = result.get('masco_title', '')
        
        if code and title:
            rows[row_idx]['imperfect_masco'] = code
            rows[row_idx]['imperfect_match'] = title
            matches_found += 1
            print(f"   Matched: {job_title} -> {title}")
        
        # Save every 10 rows to allow resuming
        if i % 10 == 0:
            with open(JOBS_FILE, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
        
        # Rate Limit Safety: 10 seconds delay = 6 RPM
        time.sleep(10)

    print(f"Done. {matches_found} new matches.")
    # Final Save
    with open(JOBS_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

if __name__ == "__main__":
    match_jobs_rag()
