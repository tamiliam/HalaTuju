"""
University Requirements Parser

Parses MOHE source data (mohe_programs_with_khas.csv) and generates
a structured requirements file for the HalaTuju eligibility engine.

Filters:
- Bumiputera-only courses (excluded)
- Courses requiring Islamic school subjects (excluded)

Output: data/university_requirements.csv
"""

import pandas as pd
import json
import re
import os
from pathlib import Path

# Project paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
SOURCE_FILE = Path("c:/Users/tamil/Python/Random/data/spm/mohe_programs_with_khas.csv")

# Load subject mapping
with open(DATA_DIR / "subject_name_mapping.json", "r", encoding="utf-8") as f:
    MAPPING = json.load(f)

SUBJECT_MAP = MAPPING["subject_map"]
ISLAMIC_SUBJECTS = MAPPING["islamic_subjects"]
BUMIPUTERA_MARKERS = MAPPING["bumiputera_markers"]
GRADE_MAP = MAPPING["grade_map"]


def is_bumiputera_only(row):
    """Check if course is restricted to Bumiputera students."""
    bumi_col = str(row.get("bumiputera", "")).lower()
    syarat_khas = str(row.get("syarat_khas", "")).lower()

    # Check bumiputera column
    for marker in BUMIPUTERA_MARKERS:
        if marker.lower() in bumi_col:
            return True

    # Also check in syarat_khas
    for marker in BUMIPUTERA_MARKERS:
        if marker.lower() in syarat_khas:
            return True

    return False


def requires_islamic_subject(syarat_khas):
    """Check if course requires Islamic school subjects."""
    text = str(syarat_khas).lower()

    # Check for single Islamic subject requirements
    for subj in ISLAMIC_SUBJECTS:
        if subj.lower() in text:
            pattern = rf"gred\s+[a-z+\-]+\s+.*{re.escape(subj.lower())}"
            if re.search(pattern, text):
                single_pattern = rf"dalam mata pelajaran\s+{re.escape(subj.lower())}"
                if re.search(single_pattern, text):
                    return True

    # Check for OR-groups where ALL subjects are Islamic
    # Pattern: "Gred X dalam SATU/DUA/etc (N) mata pelajaran berikut:"
    or_group_pattern = r"gred\s+[a-z+\-]+\s+dalam\s+(?:satu|dua|tiga|empat|lima|enam|tujuh|lapan|sembilan|sepuluh)\s*\(\d+\)\s*mata\s+pelajaran\s+berikut\s*:"

    for match in re.finditer(or_group_pattern, text):
        # Extract the subjects part (next ~500 chars or until next requirement)
        start_pos = match.end()
        end_pos = min(start_pos + 500, len(text))
        subjects_text = text[start_pos:end_pos]

        # Stop at next requirement (but need at least one bullet point worth of content)
        # Look for the pattern that indicates a NEW requirement section
        next_req = re.search(r"[•�]\s*mendapat sekurang", subjects_text)
        if next_req:
            subjects_text = subjects_text[:next_req.start()]

        # Check if ANY regular (non-Islamic) SPM subject is mentioned
        regular_subjects_found = False
        for subj_name in SUBJECT_MAP.keys():
            if subj_name.lower() in subjects_text and subj_name not in ISLAMIC_SUBJECTS:
                regular_subjects_found = True
                break

        # Check if ANY Islamic subject is mentioned
        islamic_subjects_found = False
        for islamic_subj in ISLAMIC_SUBJECTS:
            if islamic_subj.lower() in subjects_text:
                islamic_subjects_found = True
                break

        # If Islamic subjects found but NO regular subjects, it's Islamic-only
        if islamic_subjects_found and not regular_subjects_found:
            return True

    return False


def parse_merit(merit_str):
    """Parse merit percentage string to float."""
    if pd.isna(merit_str) or not merit_str:
        return 0.0

    # Remove % and convert
    try:
        return float(str(merit_str).replace("%", "").strip())
    except ValueError:
        return 0.0


def parse_grade_requirement(text):
    """
    Parse grade from requirement text.
    Returns: (grade_letter, grade_value)
    """
    # Match patterns like "Gred C", "Gred B+", "Gred A-"
    match = re.search(r"[Gg]red\s+([A-G][+\-]?)", text)
    if match:
        grade = match.group(1)
        return grade, GRADE_MAP.get(grade, 0)
    return None, 0


def extract_subject_from_text(text):
    """
    Extract subject name from requirement text.
    Returns the internal key if found.
    """
    text_lower = text.lower()

    # Try each subject mapping
    for subj_name, key in SUBJECT_MAP.items():
        if subj_name.lower() in text_lower:
            return key

    return None


def parse_single_subject_req(line):
    """
    Parse: "Gred X dalam mata pelajaran SUBJECT"
    Returns: (subject_key, grade, grade_value) or None
    """
    # Pattern for single subject requirement
    pattern = r"[Gg]red\s+([A-G][+\-]?)\s+dalam\s+mata\s+pelajaran\s+(.+?)(?:\.|$)"
    match = re.search(pattern, line)

    if match:
        grade = match.group(1)
        subject_text = match.group(2).strip()
        subject_key = extract_subject_from_text(subject_text)

        if subject_key:
            return (subject_key, grade, GRADE_MAP.get(grade, 0))

    return None


def parse_or_group_req(full_text, start_pos=0):
    """
    Parse: "Gred X dalam SATU (1) mata pelajaran berikut: • A / B / C"
    Note: Subjects may be on separate bullets after the header.
    Returns: list of (subjects_list, grade, grade_value, count) tuples
    """
    results = []

    # Pattern for OR group header (expanded to handle EMPAT-SEPULUH)
    pattern = r"[Gg]red\s+([A-G][+\-]?)\s+dalam\s+(SATU|DUA|TIGA|EMPAT|LIMA|ENAM|TUJUH|LAPAN|SEMBILAN|SEPULUH)\s*\(\d+\)\s*mata\s+pelajaran\s+berikut\s*:?"

    for match in re.finditer(pattern, full_text[start_pos:], re.IGNORECASE):
        grade = match.group(1)
        count_word = match.group(2).upper()
        count_map = {"SATU": 1, "DUA": 2, "TIGA": 3, "EMPAT": 4, "LIMA": 5, "ENAM": 6, "TUJUH": 7, "LAPAN": 8, "SEMBILAN": 9, "SEPULUH": 10}
        count = count_map.get(count_word, 1)

        # Extract subjects from the text following the match
        # Look for subjects in the next 500 characters (covers bullet-pointed subjects)
        end_pos = match.end() + 500
        subjects_part = full_text[match.end():min(end_pos, len(full_text))]

        # Stop at next requirement pattern or "Lulus ujian"
        stop_patterns = [r"[Mm]endapat sekurang", r"[Ll]ulus ujian", r"[Cc]alon hendaklah"]
        for stop_pattern in stop_patterns:
            stop_match = re.search(stop_pattern, subjects_part)
            if stop_match:
                subjects_part = subjects_part[:stop_match.start()]
                break

        subjects = []
        matched_subjects = []  # Track which subject names were matched

        # Sort subjects by length (longest first) to prioritize complete matches
        # This prevents "Matematik" from matching inside "Matematik Tambahan"
        sorted_subjects = sorted(SUBJECT_MAP.items(), key=lambda x: len(x[0]), reverse=True)

        for subj_name, key in sorted_subjects:
            subj_lower = subj_name.lower()
            text_lower = subjects_part.lower()

            if subj_lower in text_lower:
                # Check if this subject is a substring of an already-matched subject
                # e.g., skip "Matematik" if "Matematik Tambahan" was already matched
                is_substring_of_matched = any(
                    subj_lower in matched_lower
                    for matched_lower in matched_subjects
                )

                if not is_substring_of_matched:
                    subjects.append(key)
                    matched_subjects.append(subj_lower)

        if subjects:
            results.append((subjects, grade, GRADE_MAP.get(grade, 0), count))

    return results


def parse_any_subjects_req(line):
    """
    Parse: "Gred X dalam mana-mana SATU/DUA (N) mata pelajaran yang belum diambil kira"
    Returns: (grade, grade_value, count) or None
    """
    pattern = r"[Gg]red\s+([A-G][+\-]?)\s+dalam\s+mana-mana\s+(SATU|DUA|TIGA|EMPAT|LIMA|ENAM|TUJUH|LAPAN|SEMBILAN|SEPULUH)\s*\(\d+\)\s*mata\s+pelajaran"
    match = re.search(pattern, line, re.IGNORECASE)

    if match:
        grade = match.group(1)
        count_word = match.group(2).upper()
        count_map = {"SATU": 1, "DUA": 2, "TIGA": 3, "EMPAT": 4, "LIMA": 5, "ENAM": 6, "TUJUH": 7, "LAPAN": 8, "SEMBILAN": 9, "SEPULUH": 10}
        count = count_map.get(count_word, 1)

        return (grade, GRADE_MAP.get(grade, 0), count)

    return None


def parse_syarat_khas(syarat_khas):
    """
    Parse the syarat_khas field and extract structured requirements.

    Returns a dict with:
    - single_reqs: [(subject_key, grade, grade_value), ...]
    - or_groups: [(subjects_list, grade, grade_value, count), ...]
    - any_reqs: [(grade, grade_value, count), ...]
    - single_required: bool (must be unmarried)
    """
    result = {
        "single_reqs": [],
        "or_groups": [],
        "any_reqs": [],
        "single_required": False
    }

    if pd.isna(syarat_khas) or not syarat_khas:
        return result

    full_text = str(syarat_khas)

    # Parse OR groups from full text first (before splitting)
    or_groups = parse_or_group_req(full_text)

    # Convert OR-groups where count == list_size to individual requirements
    # (e.g., "TUJUH (7) mata pelajaran berikut: BM, Eng, Math..." with 7 subjects = ALL required)
    for subjects, grade, grade_val, count in or_groups:
        if count >= len(subjects):
            # All subjects required - convert to individual single requirements
            for subj_key in subjects:
                result["single_reqs"].append((subj_key, grade, grade_val))
        else:
            # True OR-group (pick N from list)
            result["or_groups"].append((subjects, grade, grade_val, count))

    # Check for marital status
    if "bujang" in full_text.lower() or "taraf perkahwinan" in full_text.lower():
        result["single_required"] = True

    # Split by bullet points for single subject and any-subject requirements
    lines = re.split(r"[•\n]", full_text)

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Skip lines that are part of OR groups (contain "berikut")
        if "berikut" in line.lower():
            continue

        # Try parsing as single subject requirement
        single_req = parse_single_subject_req(line)
        if single_req:
            result["single_reqs"].append(single_req)
            continue

        # Try parsing as any-subjects requirement
        any_req = parse_any_subjects_req(line)
        if any_req:
            result["any_reqs"].append(any_req)

    return result


def build_requirement_row(row, parsed_reqs):
    """
    Build a requirements row from source data and parsed requirements.
    """
    # Build complex_requirements JSON for OR-groups
    complex_reqs = {"or_groups": []}
    for subjects, grade, grade_val, count in parsed_reqs["or_groups"]:
        complex_reqs["or_groups"].append({
            "count": count,
            "grade": grade,
            "subjects": subjects
        })

    result = {
        "type": "UA",
        "course_id": row["code"],
        "merit_cutoff": parse_merit(row.get("merit", "")),
        "min_credits": 5,  # Default SPM requirement
        "min_pass": 0,
        "pass_history": 1,  # Usually required
        "pass_bm": 1,
        "credit_bm": 0,
        "pass_eng": 0,
        "credit_english": 0,
        "credit_math": 0,
        "credit_addmath": 0,
        "pass_sci": 0,
        "credit_sci": 0,
        "pass_islam": 0,
        "credit_islam": 0,
        "pass_moral": 0,
        "credit_moral": 0,
        # New grade B columns
        "credit_bm_b": 0,
        "credit_eng_b": 0,
        "credit_math_b": 0,
        "credit_addmath_b": 0,
        # New distinction columns (A- or better)
        "distinction_bm": 0,
        "distinction_eng": 0,
        "distinction_math": 0,
        "distinction_addmath": 0,
        "distinction_bio": 0,
        "distinction_phy": 0,
        "distinction_chem": 0,
        "distinction_sci": 0,
        # OR groups (encoded as comma-separated subject lists)
        "credit_science_group": 0,  # phy/chem/bio/sci
        "credit_math_or_addmath": 0,
        # Other
        "req_malaysian": 1,
        "notes": f"{row['program_name']} | {row['university']}",
        "syarat_khas_raw": str(row.get("syarat_khas", ""))[:500],  # Truncate for storage
        "complex_requirements": json.dumps(complex_reqs) if complex_reqs["or_groups"] else ""
    }

    # Process single subject requirements
    for subj_key, grade, grade_val in parsed_reqs["single_reqs"]:
        if subj_key == "bm":
            if grade_val >= GRADE_MAP.get("A-", 9):
                result["distinction_bm"] = 1
            elif grade_val >= GRADE_MAP.get("B-", 6):
                result["credit_bm_b"] = 1
            elif grade_val >= GRADE_MAP.get("C", 4):
                result["credit_bm"] = 1
            else:
                result["pass_bm"] = 1

        elif subj_key == "eng":
            if grade_val >= GRADE_MAP.get("A-", 9):
                result["distinction_eng"] = 1
            elif grade_val >= GRADE_MAP.get("B-", 6):
                result["credit_eng_b"] = 1
            elif grade_val >= GRADE_MAP.get("C", 4):
                result["credit_english"] = 1
            else:
                result["pass_eng"] = 1

        elif subj_key == "math":
            if grade_val >= GRADE_MAP.get("A-", 9):
                result["distinction_math"] = 1
            elif grade_val >= GRADE_MAP.get("B-", 6):
                result["credit_math_b"] = 1
            elif grade_val >= GRADE_MAP.get("C", 4):
                result["credit_math"] = 1

        elif subj_key == "addmath":
            if grade_val >= GRADE_MAP.get("A-", 9):
                result["distinction_addmath"] = 1
            elif grade_val >= GRADE_MAP.get("B-", 6):
                result["credit_addmath_b"] = 1
            elif grade_val >= GRADE_MAP.get("C", 4):
                result["credit_addmath"] = 1

        elif subj_key == "hist":
            result["pass_history"] = 1

        elif subj_key == "islam":
            if grade_val >= GRADE_MAP.get("C", 4):
                result["credit_islam"] = 1
            else:
                result["pass_islam"] = 1

        elif subj_key == "moral":
            if grade_val >= GRADE_MAP.get("C", 4):
                result["credit_moral"] = 1
            else:
                result["pass_moral"] = 1

        elif subj_key == "bio":
            if grade_val >= GRADE_MAP.get("A-", 9):
                result["distinction_bio"] = 1
            elif grade_val >= GRADE_MAP.get("C", 4):
                result["credit_sci"] = 1
            else:
                result["pass_sci"] = 1

        elif subj_key == "phy":
            if grade_val >= GRADE_MAP.get("A-", 9):
                result["distinction_phy"] = 1
            elif grade_val >= GRADE_MAP.get("C", 4):
                result["credit_sci"] = 1
            else:
                result["pass_sci"] = 1

        elif subj_key == "chem":
            if grade_val >= GRADE_MAP.get("A-", 9):
                result["distinction_chem"] = 1
            elif grade_val >= GRADE_MAP.get("C", 4):
                result["credit_sci"] = 1
            else:
                result["pass_sci"] = 1

        elif subj_key == "sci":
            if grade_val >= GRADE_MAP.get("A-", 9):
                result["distinction_sci"] = 1
            elif grade_val >= GRADE_MAP.get("C", 4):
                result["credit_sci"] = 1
            else:
                result["pass_sci"] = 1

    # Process OR groups
    for subjects, grade, grade_val, count in parsed_reqs["or_groups"]:
        # Check if it's a science group
        science_subjects = {"phy", "chem", "bio", "sci", "addsci"}
        if science_subjects.intersection(set(subjects)):
            if grade_val >= GRADE_MAP.get("C", 4):
                result["credit_science_group"] = 1

        # Check if it's math/addmath group
        if "math" in subjects and "addmath" in subjects:
            if grade_val >= GRADE_MAP.get("C", 4):
                result["credit_math_or_addmath"] = 1

    return result


def build_details_row(row, parsed_reqs):
    """
    Build a details row for details.csv (non-academic metadata).
    """
    return {
        "course_id": row["code"],
        "req_interview": 1 if str(row.get("interview", "")).lower() == "ya" else 0,
        "source_type": "univ",
        "institution_id": "",  # Can be populated later
        "hyperlink": "",
        "single": 1 if parsed_reqs["single_required"] else 0,
        "monthly_allowance": "",
        "practical_allowance": "",
        "free_hostel": "",
        "free_meals": "",
        "tuition_fee_semester": "",
        "hostel_fee_semester": "",
        "registration_fee": "",
        "req_academic": "",
        "medical_restrictions": ""
    }


def main():
    print("=" * 60)
    print("University Requirements Parser")
    print("=" * 60)

    # Load source data
    print(f"\nLoading source: {SOURCE_FILE}")
    df = pd.read_csv(SOURCE_FILE)
    print(f"Total programs: {len(df)}")

    # Statistics
    stats = {
        "total": len(df),
        "asasi_total": 0,
        "diploma_university": 0,
        "diploma_politeknik": 0,
        "diploma_kk": 0,
        "certificate": 0,
        "sarjana": 0,
        "other": 0,
        "university_courses_before_filter": 0,
        "bumiputera_filtered": 0,
        "islamic_filtered": 0,
        "included": 0,
        "parse_errors": 0
    }

    results = []
    details_rows = []

    for idx, row in df.iterrows():
        course_id = row.get("code", "")
        program_name = row.get("program_name", "")
        level = row.get("level", "")

        # Count by type
        if level == "Asasi/ Matrikulasi/ Foundation":
            stats["asasi_total"] += 1
        elif level == "Diploma":
            if course_id.startswith("U"):
                stats["diploma_university"] += 1
            elif course_id.startswith("FB"):
                stats["diploma_politeknik"] += 1
            elif course_id.startswith("FC"):
                stats["diploma_kk"] += 1
        elif level.startswith("Sijil"):
            stats["certificate"] += 1
        elif level == "Sarjana Muda":
            stats["sarjana"] += 1
        else:
            stats["other"] += 1

        # Filter: Include ALL University courses (U*), exclude Politeknik/KK/Kolej Mara
        # University codes: U*, Politeknik: FB*, Kolej Komuniti: FC*, Kolej Mara: OM*
        if not course_id.startswith("U"):
            continue

        stats["university_courses_before_filter"] += 1

        # Filter: Bumiputera-only
        if is_bumiputera_only(row):
            stats["bumiputera_filtered"] += 1
            continue

        # Filter: Islamic subject requirements
        syarat_khas = row.get("syarat_khas", "")
        if requires_islamic_subject(syarat_khas):
            stats["islamic_filtered"] += 1
            continue

        # Filter: HUFFAZ programs (Quran memorization programs)
        if "HUFFAZ" in program_name.upper():
            stats["islamic_filtered"] += 1
            continue

        # Parse requirements
        try:
            parsed = parse_syarat_khas(syarat_khas)
            req_row = build_requirement_row(row, parsed)
            details_row = build_details_row(row, parsed)
            results.append(req_row)
            details_rows.append(details_row)
            stats["included"] += 1
        except Exception as e:
            print(f"  Error parsing {course_id}: {e}")
            stats["parse_errors"] += 1

    # Create output DataFrames
    output_df = pd.DataFrame(results)
    details_df = pd.DataFrame(details_rows)

    # Output requirements file
    requirements_file = DATA_DIR / "university_requirements.csv"
    output_df.to_csv(requirements_file, index=False)

    # Append to existing details.csv
    details_file = DATA_DIR / "details.csv"
    if details_file.exists():
        # Read existing details and append
        existing_details = pd.read_csv(details_file)
        # Remove any existing university courses (in case of re-run)
        existing_details = existing_details[existing_details["source_type"] != "univ"]
        combined_details = pd.concat([existing_details, details_df], ignore_index=True)
        combined_details.to_csv(details_file, index=False)
        print(f"\nAppended {len(details_df)} university courses to details.csv")
    else:
        details_df.to_csv(details_file, index=False)
        print(f"\nCreated details.csv with {len(details_df)} university courses")

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Total programs in source:           {stats['total']}")
    print(f"\nBreakdown by type:")
    print(f"  Asasi/Foundation:                 {stats['asasi_total']}")
    print(f"  Diploma (University):             {stats['diploma_university']}")
    print(f"  Diploma (Politeknik):             {stats['diploma_politeknik']}")
    print(f"  Diploma (Kolej Komuniti):         {stats['diploma_kk']}")
    print(f"  Certificate:                      {stats['certificate']}")
    print(f"  Sarjana Muda:                     {stats['sarjana']}")
    print(f"  Other:                            {stats['other']}")
    print(f"\nUniversity courses before filters:  {stats['university_courses_before_filter']}")
    print(f"  Filtered (Bumiputera-only):       {stats['bumiputera_filtered']}")
    print(f"  Filtered (Islamic subjects):      {stats['islamic_filtered']}")
    print(f"  Parse errors:                     {stats['parse_errors']}")
    print(f"\nIncluded in output:                 {stats['included']}")
    print(f"\nOutput written to: {requirements_file}")

    # Sample output
    print("\n" + "=" * 60)
    print("SAMPLE OUTPUT (first 5 rows)")
    print("=" * 60)
    print(output_df[["course_id", "merit_cutoff", "credit_bm", "credit_bm_b", "credit_english", "complex_requirements", "notes"]].head())

    return output_df


if __name__ == "__main__":
    main()
