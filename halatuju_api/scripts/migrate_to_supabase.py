"""
Migrate HalaTuju data from CSV files to Supabase.

This script generates SQL INSERT statements that can be executed
via Supabase MCP or SQL editor.

Usage:
    python scripts/migrate_to_supabase.py [table_name] [batch_number]

Examples:
    python scripts/migrate_to_supabase.py courses 0    # First 50 courses
    python scripts/migrate_to_supabase.py courses 1    # Next 50 courses
    python scripts/migrate_to_supabase.py institutions 0
    python scripts/migrate_to_supabase.py requirements 0
"""
import os
import sys
import json
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
BATCH_SIZE = 30  # Keep batches small to avoid size limits


def esc(v):
    """Escape value for SQL."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return 'NULL'
    if v == '' or v == 'nan':
        return 'NULL'
    s = str(v).replace("'", "''")
    return f"'{s}'"


def esc_bool(v):
    """Convert to SQL boolean."""
    if v is None or v == '' or pd.isna(v):
        return 'FALSE'
    return 'TRUE' if str(v).lower() in ('true', '1', 'yes', 't') else 'FALSE'


def esc_json(v):
    """Escape JSON value."""
    if v is None or v == '' or pd.isna(v):
        return 'NULL'
    try:
        if isinstance(v, str):
            # Validate it's valid JSON
            json.loads(v)
            return f"'{v.replace(chr(39), chr(39)+chr(39))}'"
        return f"'{json.dumps(v).replace(chr(39), chr(39)+chr(39))}'"
    except:
        return 'NULL'


def generate_courses_sql(batch_num):
    """Generate INSERT for courses table."""
    df = pd.read_csv(os.path.join(DATA_DIR, 'courses.csv'), dtype=str).fillna('')

    start = batch_num * BATCH_SIZE
    end = start + BATCH_SIZE
    batch_df = df.iloc[start:end]

    if batch_df.empty:
        return None, 0, len(df)

    rows = []
    for _, r in batch_df.iterrows():
        wbl = 'TRUE' if str(r.get('wbl', '0')) == '1' else 'FALSE'
        sem = r.get('semesters', '')
        sem = sem if sem else 'NULL'
        # Truncate description to avoid size issues
        desc = str(r.get('description', ''))[:500]
        row = f"({esc(r['course_id'])}, {esc(r.get('course', ''))}, {wbl}, {esc(r.get('level', ''))}, {esc(r.get('department', ''))}, {esc(r.get('field', ''))}, {esc(r.get('frontend_label', ''))}, {sem}, {esc(desc)})"
        rows.append(row)

    sql = f"""INSERT INTO courses (course_id, course, wbl, level, department, field, frontend_label, semesters, description) VALUES
{','.join(rows)}
ON CONFLICT (course_id) DO NOTHING;"""

    return sql, len(rows), len(df)


def generate_institutions_sql(batch_num):
    """Generate INSERT for institutions table."""
    df = pd.read_csv(os.path.join(DATA_DIR, 'institutions.csv'), dtype=str).fillna('')

    start = batch_num * BATCH_SIZE
    end = start + BATCH_SIZE
    batch_df = df.iloc[start:end]

    if batch_df.empty:
        return None, 0, len(df)

    rows = []
    for _, r in batch_df.iterrows():
        lat = r.get('lat', '')
        lat = lat if lat and lat != '' else 'NULL'
        lng = r.get('lng', '')
        lng = lng if lng and lng != '' else 'NULL'

        row = f"({esc(r['institution_id'])}, {esc(r.get('institution_name', ''))}, {esc(r.get('acronym', ''))}, {esc(r.get('type', ''))}, {esc(r.get('category', ''))}, {esc(r.get('subcategory', ''))}, {esc(r.get('state', ''))}, {esc(r.get('address', ''))}, {esc(r.get('phone', ''))}, {esc(r.get('url', ''))}, {lat}, {lng})"
        rows.append(row)

    sql = f"""INSERT INTO institutions (institution_id, institution_name, acronym, type, category, subcategory, state, address, phone, url, latitude, longitude) VALUES
{','.join(rows)}
ON CONFLICT (institution_id) DO NOTHING;"""

    return sql, len(rows), len(df)


def generate_requirements_sql(batch_num, source_file, source_type):
    """Generate INSERT for course_requirements table."""
    df = pd.read_csv(os.path.join(DATA_DIR, source_file), dtype=str).fillna('')

    start = batch_num * BATCH_SIZE
    end = start + BATCH_SIZE
    batch_df = df.iloc[start:end]

    if batch_df.empty:
        return None, 0, len(df)

    bool_cols = [
        'req_malaysian', 'req_male', 'req_female', 'no_colorblind', 'no_disability',
        'pass_bm', 'pass_history', 'pass_eng', 'pass_math',
        'credit_bm', 'credit_english', 'credit_math', 'credit_addmath',
        'pass_stv', 'credit_stv', 'credit_sf', 'credit_sfmt', 'credit_bmbi',
        'pass_math_addmath', 'pass_science_tech', 'pass_math_science',
        'credit_math_sci', 'credit_math_sci_tech', 'three_m_only', 'single',
        'credit_bm_b', 'credit_eng_b', 'credit_math_b', 'credit_addmath_b',
        'distinction_bm', 'distinction_eng', 'distinction_math', 'distinction_addmath',
        'distinction_phy', 'distinction_chem', 'distinction_bio', 'distinction_sci',
        'pass_islam', 'credit_islam', 'pass_moral', 'credit_moral', 'req_interview',
    ]

    rows = []
    for _, r in batch_df.iterrows():
        course_id = r.get('course_id')
        if not course_id:
            continue

        min_credits = r.get('min_credits', '0')
        min_credits = min_credits if min_credits else '0'
        min_pass = r.get('min_pass', '0')
        min_pass = min_pass if min_pass else '0'
        max_agg = r.get('max_aggregate_units', '100')
        max_agg = max_agg if max_agg else '100'
        merit = r.get('merit_cutoff', '')
        merit = merit if merit and merit != '' else 'NULL'

        bools = []
        for col in bool_cols:
            # Handle column name mapping
            csv_col = '3m_only' if col == 'three_m_only' else col
            bools.append(esc_bool(r.get(csv_col, '')))

        subj_req = esc_json(r.get('subject_group_req', ''))
        complex_req = esc_json(r.get('complex_requirements', ''))
        remarks = esc(r.get('remarks', ''))

        row = f"({esc(course_id)}, '{source_type}', {min_credits}, {min_pass}, {max_agg}, {merit}, {', '.join(bools)}, {subj_req}, {complex_req}, {remarks})"
        rows.append(row)

    if not rows:
        return None, 0, len(df)

    cols = ['course_id', 'source_type', 'min_credits', 'min_pass', 'max_aggregate_units', 'merit_cutoff'] + bool_cols + ['subject_group_req', 'complex_requirements', 'remarks']

    sql = f"""INSERT INTO course_requirements ({', '.join(cols)}) VALUES
{','.join(rows)}
ON CONFLICT (course_id) DO UPDATE SET source_type = EXCLUDED.source_type;"""

    return sql, len(rows), len(df)


def generate_links_sql(batch_num):
    """Generate INSERT for course_institutions table."""
    df = pd.read_csv(os.path.join(DATA_DIR, 'links.csv'), dtype=str).fillna('')

    start = batch_num * BATCH_SIZE
    end = start + BATCH_SIZE
    batch_df = df.iloc[start:end]

    if batch_df.empty:
        return None, 0, len(df)

    rows = []
    for _, r in batch_df.iterrows():
        course_id = r.get('course_id')
        inst_id = r.get('institution_id')
        if not course_id or not inst_id:
            continue
        hyperlink = esc(r.get('hyperlink', ''))
        row = f"({esc(course_id)}, {esc(inst_id)}, {hyperlink})"
        rows.append(row)

    if not rows:
        return None, 0, len(df)

    sql = f"""INSERT INTO course_institutions (course_id, institution_id, hyperlink) VALUES
{','.join(rows)}
ON CONFLICT (course_id, institution_id) DO NOTHING;"""

    return sql, len(rows), len(df)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python migrate_to_supabase.py <table> <batch_num>")
        print("Tables: courses, institutions, requirements, tvet_requirements, university_requirements, links")
        sys.exit(1)

    table = sys.argv[1]
    batch_num = int(sys.argv[2])

    if table == 'courses':
        sql, count, total = generate_courses_sql(batch_num)
    elif table == 'institutions':
        sql, count, total = generate_institutions_sql(batch_num)
    elif table == 'requirements':
        sql, count, total = generate_requirements_sql(batch_num, 'requirements.csv', 'poly')
    elif table == 'tvet_requirements':
        sql, count, total = generate_requirements_sql(batch_num, 'tvet_requirements.csv', 'tvet')
    elif table == 'university_requirements':
        sql, count, total = generate_requirements_sql(batch_num, 'university_requirements.csv', 'ua')
    elif table == 'links':
        sql, count, total = generate_links_sql(batch_num)
    else:
        print(f"Unknown table: {table}")
        sys.exit(1)

    if sql:
        print(sql)
        print(f"\n-- Batch {batch_num}: {count} rows (total: {total}, batches needed: {(total + BATCH_SIZE - 1) // BATCH_SIZE})", file=sys.stderr)
    else:
        print(f"-- No more data for {table} (batch {batch_num})", file=sys.stderr)
