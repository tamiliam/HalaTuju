"""
Standalone script to map courses to MASCO career occupations via Gemini AI.

Reads course data from CSV input files (exported from Supabase),
uses local masco_full.csv for candidate filtering,
calls Gemini API for matching,
writes review CSVs.

Usage:
  python scripts/gemini_map_careers.py --input data/courses_ua.csv --output data/review_ua.csv
  python scripts/gemini_map_careers.py --input data/courses_pismp.csv --output data/review_pismp.csv
  python scripts/gemini_map_careers.py --input data/courses_stpm.csv --output data/review_stpm.csv --limit 951

Input CSV must have columns: course_id, course_name, field_key_id, type (spm or stpm)
"""
import csv
import json
import os
import re
import sys
import time

# Add parent dir to path for masco_mapping import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Gemini model cascade
MODEL_CASCADE = [
    'gemini-2.5-flash',
    'gemini-2.5-flash-lite',
    'gemini-2.0-flash',
]

MASCO_CODE_RE = re.compile(r'\b(\d{4}-\d{2})\b')

# Import field_key mapping directly
from apps.courses.masco_mapping import FIELD_KEY_TO_MASCO


def load_masco_data(csv_path: str) -> dict[str, list[dict]]:
    """Load MASCO CSV and group specific jobs by 2-digit prefix."""
    by_prefix = {}
    seen = set()
    with open(csv_path, 'r', encoding='latin-1') as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row['kod_masco'].strip()
            if code in seen or '-' not in code:
                continue
            seen.add(code)
            title = row['tajuk_pekerjaan'].strip()
            prefix = code[:2]
            by_prefix.setdefault(prefix, []).append({
                'masco_code': code,
                'job_title': title,
            })
    return by_prefix


def filter_by_field_key(field_key: str, masco_by_prefix: dict) -> list[dict]:
    """Get MASCO candidates for a field_key using the mapping."""
    groups = FIELD_KEY_TO_MASCO.get(field_key, [])
    if not groups:
        return []
    result = []
    for g in groups:
        result.extend(masco_by_prefix.get(g, []))
    return result


def call_gemini(course_name: str, field_key: str, masco_list: list[dict], client) -> list[str]:
    """Ask Gemini to pick 3 most relevant MASCO codes."""
    candidates = '\n'.join(
        f"  {m['masco_code']}  {m['job_title']}"
        for m in masco_list
    )

    prompt = (
        f"Anda pakar kerjaya Malaysia. Kursus ini:\n"
        f"  Nama: {course_name}\n"
        f"  Bidang: {field_key}\n\n"
        f"Senarai pekerjaan MASCO yang berkaitan:\n{candidates}\n\n"
        f"Pilih TEPAT 3 kod MASCO yang PALING sesuai untuk graduan kursus ini.\n"
        f"Jawab HANYA dengan 3 kod, satu per baris. Contoh:\n"
        f"2141-01\n7233-01\n2141-03\n"
        f"Jangan tulis apa-apa lain."
    )

    valid_codes = {m['masco_code'] for m in masco_list}

    for model_name in MODEL_CASCADE:
        try:
            response = client.models.generate_content(
                model=model_name, contents=prompt
            )
            text = response.text
            found = MASCO_CODE_RE.findall(text)
            validated = [c for c in found if c in valid_codes]
            seen = set()
            result = []
            for c in validated:
                if c not in seen:
                    seen.add(c)
                    result.append(c)
                if len(result) >= 3:
                    break
            return result
        except Exception as e:
            print(f'  Gemini {model_name} failed: {e}')
            continue

    return []


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Map courses to MASCO via Gemini')
    parser.add_argument('--input', required=True, help='Input CSV with course data')
    parser.add_argument('--output', required=True, help='Output review CSV')
    parser.add_argument('--limit', type=int, default=0, help='Max courses (0=all)')
    parser.add_argument('--delay', type=float, default=0.5, help='Seconds between calls')
    parser.add_argument('--masco-csv', default='data/masco_full.csv', help='MASCO CSV path')
    args = parser.parse_args()

    api_key = os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        # Try loading from .env
        env_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith('GEMINI_API_KEY='):
                        api_key = line.strip().split('=', 1)[1]
                        break
    if not api_key:
        print('ERROR: GEMINI_API_KEY not found')
        sys.exit(1)

    from google import genai
    client = genai.Client(api_key=api_key)

    # Load MASCO data
    print(f'Loading MASCO data from {args.masco_csv}...')
    masco_by_prefix = load_masco_data(args.masco_csv)
    total_jobs = sum(len(v) for v in masco_by_prefix.values())
    print(f'  Loaded {total_jobs} specific jobs across {len(masco_by_prefix)} groups')

    # Load course data
    with open(args.input, 'r', encoding='utf-8') as f:
        courses = list(csv.DictReader(f))

    if args.limit > 0:
        courses = courses[:args.limit]

    print(f'Processing {len(courses)} courses...')

    rows = []
    failed = 0
    for i, course in enumerate(courses):
        cid = course['course_id']
        name = course['course_name']
        fk = course['field_key_id']
        ctype = course.get('type', 'spm')

        candidates = filter_by_field_key(fk, masco_by_prefix)
        if not candidates:
            print(f'  [{i+1}/{len(courses)}] {cid}: NO candidates for field_key={fk}')
            failed += 1
            continue

        codes = call_gemini(name, fk, candidates, client)

        if not codes:
            print(f'  [{i+1}/{len(courses)}] {cid}: Gemini returned no matches')
            failed += 1
            continue

        lookup = {m['masco_code']: m['job_title'] for m in candidates}
        for code in codes:
            rows.append({
                'course_id': cid,
                'course_name': name,
                'field_key': fk,
                'masco_code': code,
                'job_title': lookup.get(code, ''),
                'type': ctype,
            })

        print(f'  [{i+1}/{len(courses)}] {cid}: {name[:40]} -> {codes}')

        if args.delay > 0 and i < len(courses) - 1:
            time.sleep(args.delay)

    # Write output
    fieldnames = ['course_id', 'course_name', 'field_key', 'masco_code', 'job_title', 'type']
    with open(args.output, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f'\nDone! Wrote {len(rows)} rows ({len(rows)//3} courses) to {args.output}')
    if failed:
        print(f'  {failed} courses had no matches')


if __name__ == '__main__':
    main()
