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

try:
    from openai import OpenAI
except ImportError:
    print("CRITICAL: openai module not found.")
    exit(1)

# Retrieve API Keys
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

# Fallback to Streamlit secrets
if not GEMINI_KEY or not OPENAI_KEY:
    try:
        import streamlit as st
        if not GEMINI_KEY: GEMINI_KEY = st.secrets.get("GEMINI_API_KEY")
        if not OPENAI_KEY: OPENAI_KEY = st.secrets.get("OPENAI_API_KEY")
    except:
        pass

if not GEMINI_KEY:
    print("CRITICAL: GEMINI_API_KEY not found.")
    exit(1)
if not OPENAI_KEY:
    print("CRITICAL: OPENAI_API_KEY not found.")
    exit(1)

# Configure Clients
genai.configure(api_key=GEMINI_KEY)
client = OpenAI(api_key=OPENAI_KEY)

# Models
EMBED_MODEL = "models/text-embedding-004"
OPENAI_MODEL = "gpt-4o-mini"

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

def match_with_openai(job_title, candidates, retries=3):
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
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that outputs only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            if "context_length" in str(e):
                return {}
            print(f"OpenAI Error for {job_title}: {e}")
            time.sleep(1)
            
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
    
    print("3. Scanning for matched jobs (Refining with OpenAI)...")
    manual_count = 0
    already_done_count = 0
    
    for idx, row in enumerate(rows):
        # Skip if manual match exists (authoritative)
        if row.get('masco', '').strip(): 
            manual_count += 1
            continue
        
        # NOTE: We can uncomment this if we want to skip already AI-matched rows
        # if row.get('imperfect_masco', '').strip(): 
        #    already_done_count += 1
        #    continue
        
        jobs_to_process.append(row.get('jobs', ''))
        job_indices.append(idx)
        
    print(f"   Found {len(jobs_to_process)} jobs to match.")
    print(f"   Skipped {manual_count} manual matches.")
    # print(f"   Skipped {already_done_count} existing AI matches.")
    
    if not jobs_to_process:
        print("No jobs left to match.")
        return

    print("4. Embedding Jobs Batch (Gemini)...")
    job_vecs = get_query_embeddings_batch(jobs_to_process)
    
    # 5. RAG Loop
    print("5. RAG Matching (OpenAI)...")
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
        result = match_with_openai(job_title, candidates)
        code = result.get('masco_code', '')
        title = result.get('masco_title', '')
        
        if code:
            rows[row_idx]['imperfect_masco'] = code
            rows[row_idx]['imperfect_match'] = title
            matches_found += 1
            print(f"   Matched: {job_title} -> {title} ({code})")
        
        # Save every 20 rows
        if i % 20 == 0:
            with open(JOBS_FILE, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
        
        # No significant sleep needed for OpenAI paid tier/free tier 2
        # Just a tiny breather
        time.sleep(0.1)

    print(f"Done. {matches_found} matches updated.")
    # Final Save
    with open(JOBS_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

if __name__ == "__main__":
    match_jobs_rag()
