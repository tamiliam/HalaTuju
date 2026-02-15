"""
Generate SQL INSERT statements from CSV files for Supabase migration.

Usage:
    python scripts/generate_sql_inserts.py

Outputs SQL files that can be executed via Supabase MCP or SQL editor.
"""
import os
import json
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'sql_output')


def escape_sql(value):
    """Escape single quotes for SQL."""
    if value is None or pd.isna(value):
        return 'NULL'
    if isinstance(value, bool):
        return 'TRUE' if value else 'FALSE'
    if isinstance(value, (int, float)):
        if pd.isna(value):
            return 'NULL'
        return str(value)
    if isinstance(value, (dict, list)):
        return f"'{json.dumps(value).replace(chr(39), chr(39)+chr(39))}'"
    # String
    return f"'{str(value).replace(chr(39), chr(39)+chr(39))}'"


def generate_courses_sql():
    """Generate INSERT for courses table."""
    csv_path = os.path.join(DATA_DIR, 'courses.csv')
    df = pd.read_csv(csv_path, dtype=str).fillna('')

    values = []
    for _, row in df.iterrows():
        wbl = 'TRUE' if str(row.get('wbl', '')).lower() == 'true' else 'FALSE'
        semesters = row.get('semesters', '')
        semesters = f"'{semesters}'" if semesters else 'NULL'

        val = f"({escape_sql(row['course_id'])}, {escape_sql(row.get('course', ''))}, {wbl}, {escape_sql(row.get('level', ''))}, {escape_sql(row.get('department', ''))}, {escape_sql(row.get('field', ''))}, {escape_sql(row.get('frontend_label', ''))}, {semesters}, {escape_sql(row.get('description', ''))})"
        values.append(val)

    sql = f"""INSERT INTO courses (course_id, course, wbl, level, department, field, frontend_label, semesters, description)
VALUES
{','.join(values[:50])}
ON CONFLICT (course_id) DO NOTHING;"""

    return sql, len(values)


def generate_institutions_sql():
    """Generate INSERT for institutions table."""
    csv_path = os.path.join(DATA_DIR, 'institutions.csv')
    df = pd.read_csv(csv_path, dtype=str).fillna('')

    values = []
    for _, row in df.iterrows():
        lat = row.get('lat', '')
        lat = lat if lat else 'NULL'
        lng = row.get('lng', '')
        lng = lng if lng else 'NULL'

        val = f"({escape_sql(row['institution_id'])}, {escape_sql(row.get('institution_name', ''))}, {escape_sql(row.get('acronym', ''))}, {escape_sql(row.get('type', ''))}, {escape_sql(row.get('category', ''))}, {escape_sql(row.get('subcategory', ''))}, {escape_sql(row.get('state', ''))}, {escape_sql(row.get('address', ''))}, {escape_sql(row.get('phone', ''))}, {escape_sql(row.get('url', ''))}, {lat}, {lng})"
        values.append(val)

    sql = f"""INSERT INTO institutions (institution_id, institution_name, acronym, type, category, subcategory, state, address, phone, url, latitude, longitude)
VALUES
{','.join(values[:50])}
ON CONFLICT (institution_id) DO NOTHING;"""

    return sql, len(values)


if __name__ == '__main__':
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Generate courses
    sql, count = generate_courses_sql()
    print(f"Generated {count} course inserts (showing first 50)")
    with open(os.path.join(OUTPUT_DIR, '01_courses.sql'), 'w', encoding='utf-8') as f:
        f.write(sql)

    # Generate institutions
    sql, count = generate_institutions_sql()
    print(f"Generated {count} institution inserts (showing first 50)")
    with open(os.path.join(OUTPUT_DIR, '02_institutions.sql'), 'w', encoding='utf-8') as f:
        f.write(sql)

    print(f"\nSQL files written to {OUTPUT_DIR}")
