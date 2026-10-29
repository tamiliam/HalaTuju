"""SPM MERIT CALCULATION — the UPU formula, the stream pools and `prepare_merit_inputs`.

Moved verbatim out of `engine.py` (Bumi coverage Sprint D1, 2026-10-29), a moves-only split:
`engine.py` is a ledgered oversize file (see `halatuju_api/CLAUDE.md`, `## Code standards`) and sat
at its 858-line budget, and Sprint D1 adds the Bumiputera gate there. `engine.py` re-exports every
name, so every `from apps.courses.engine import ...` is unchanged. Nothing here changed: the
golden masters and the merit tests still hold it to the same numbers.
"""

# --- MERIT CALCULATION CONSTANTS (High is Good) ---
MERIT_GRADE_POINTS = {
    "A+": 18, "A": 16, "A-": 14,
    "B+": 12, "B": 10, "C+": 8, "C": 6,
    "D": 4, "E": 2, "G": 0
}


# ============================================
# SPM MERIT CALCULATION (UPU Formula)
# ============================================
#
# DO NOT CHANGE THIS FORMULA without explicit approval from the user.
#
# Source: UPU (Unit Pusat Universiti) official merit calculation.
#
# Grade scale (MERIT_GRADE_POINTS, higher = better):
#   A+=18, A=16, A-=14, B+=12, B=10, C+=8, C=6, D=4, E=2, G=0
#
# Subject grouping (4+2+2 = 8 subjects):
#   Sec1 (Teras/Core):    4 FIXED subjects — BM, BI, Math, Sejarah
#                          Max = 4 × 18 = 72 pts
#   Sec2 (Aliran/Stream): Best 2 from student's stream pool
#                          (science/arts/technical)
#                          Max = 2 × 18 = 36 pts
#   Sec3 (Tambahan/Elective): Best 2 from remaining subjects
#                          Max = 2 × 18 = 36 pts
#
# Weighted formula:
#   weighted = (Sec1/72 × 40) + (Sec2/36 × 30) + (Sec3/36 × 10)
#   Simplified: ((p1 × 5/9) + (p2 × 5/6) + (p3 × 5/18))
#
# Academic merit:
#   academic = weighted × 9/8, capped at 90
#
# Final merit:
#   final = academic + CoQ (co-curriculum, 0-10), max 100
#
# ============================================

def calculate_merit_score(sec1_grades, sec2_grades, sec3_grades, coq_score):
    """
    UPU SPM merit score from three subject sections + co-curriculum.

    Args:
        sec1_grades: List of 4 grade strings (core: BM, BI, Math, Sejarah)
        sec2_grades: List of 2 grade strings (best from stream pool)
        sec3_grades: List of 2 grade strings (best from remaining)
        coq_score: Co-curriculum score (0-10)

    Returns:
        Dict with academic_merit (0-90), final_merit (0-100), total_points.
    """
    def get_points(g_list):
        return sum(MERIT_GRADE_POINTS.get(g, 0) for g in g_list)

    p1 = get_points(sec1_grades)
    p2 = get_points(sec2_grades)
    p3 = get_points(sec3_grades)

    total_points = p1 + p2 + p3

    # Formula: ((S1 * 40/72) + (S2 * 5/6) + (S3 * 5/18)) * (9/8)
    academic_merit = ((p1 * 5/9) + (p2 * 5/6) + (p3 * 5/18)) * (9/8)
    academic_merit = min(academic_merit, 90.00)
    final_merit = academic_merit + min(max(coq_score, 0), 10.0)

    return {
        "academic_merit": round(academic_merit, 2),
        "final_merit": round(final_merit, 2),
        "total_points": total_points
    }


# Merit probability gap thresholds (SPM standard merit)
MERIT_GAP_HIGH = 0      # gap >= 0 → High
MERIT_GAP_FAIR = -5     # gap >= -5 → Fair, below → Low

# Merit label/colour constants
MERIT_COLORS = {
    'High': '#2ecc71',
    'Fair': '#f1c40f',
    'Low': '#e74c3c',
    'Unknown': '#95a5a6',
}


def check_merit_probability(student_merit, course_cutoff):
    """
    Returns (label, color_hex) based on the gap between student merit and course cutoff.
    """
    try:
        cutoff = float(course_cutoff)
        merit = float(student_merit)
    except (ValueError, TypeError):
        return "Unknown", MERIT_COLORS['Unknown']

    gap = merit - cutoff

    if gap >= MERIT_GAP_HIGH:
        return "High", MERIT_COLORS['High']
    elif gap >= MERIT_GAP_FAIR:
        return "Fair", MERIT_COLORS['Fair']
    else:
        return "Low", MERIT_COLORS['Low']


# Stream subject pools — MUST mirror SPM_STREAM_POOLS in
# halatuju-web/src/lib/subjects.ts. If a subject can be selected as a stream
# subject in the frontend dropdown but is missing here, its grade silently
# drops from the 30% stream weight (Sec2) to the 10% elective weight (Sec3).
# Sciences appear in both SCIENCE and TECHNICAL pools, and a subject may live
# in more than one pool (matches the official SPM elective grouping). The Islamic-
# studies subjects are electives in subjects.ts (no stream), so they are in no pool.
SCIENCE_POOL = {'phy', 'chem', 'bio', 'addmath'}
ARTS_POOL = {
    'ekonomi', 'poa', 'business', 'geo', 'b_tamil', 'b_cina', 'lukisan',
    'psv', 'keusahawanan', 'alat_muzik', 'apresiasi_tari',
    'aural_teori_muzik', 'bahasa_arab', 'bahasa_arab_tinggi', 'bahasa_iban',
    'bahasa_kadazandusun', 'bahasa_punjabi', 'bahasa_semai',
    'bible_knowledge', 'lit_cina', 'lit_eng', 'lit_bm', 'lit_tamil',
    'koreografi', 'lakonan', 'multimedia_kreatif', 'muzik_komputer',
    'music', 'penulisan_skrip', 'produksi_seni', 'reka_bentuk_grafik',
    'reka_bentuk_industri', 'reka_bentuk_kraf', 'sejarah_seni',
    'seni_halus_2d', 'seni_halus_3d', 'sinografi', 'tarian',
}
TECHNICAL_POOL = {
    'eng_civil', 'eng_mech', 'eng_elec', 'eng_draw', 'gkt', 'comp_sci',
    'reka_cipta', 'kelestarian', 'pertanian', 'srt', 'sports_sci',
    'addsci', 'phy', 'chem', 'bio', 'addmath',
}


def prepare_merit_inputs(grades, stream_subjects=None):
    """
    Splits grades into Sec1 (4 core), Sec2 (2 stream), Sec3 (2 elective)
    for UPU-style merit calculation.

    UPU formula sections:
      Sec1 (Teras/Core, 40%): BM, BI, Math, Sejarah — fixed 4, max 72 pts
      Sec2 (Aliran/Stream, 30%): Best 2 from stream pool — max 36 pts
      Sec3 (Tambahan/Elective, 10%): Best 2 from remaining — max 36 pts

    Stream identification (TD-063):
      - If ``stream_subjects`` is given (the subjects the student explicitly
        designated as their stream/aliran on the grades page), Sec2 is the
        best 2 of THOSE — the back-end trusts the student's own selection and
        does not consult the stream pools at all. This is authoritative: a
        designated subject scores at the 30% weight even if it is absent from
        the back-end pools (which is exactly the S18 drift bug, now impossible
        for labelled data).
      - If ``stream_subjects`` is None/empty (the golden-master fixtures and
        any profile saved before the field existed), it falls back to the
        legacy count-heuristic — pick the pool with the most subjects taken.
        This keeps existing/historical flat-grade data scoring identically.
    """
    def get_g(s):
        return grades.get(s, 'G')

    # Section 1: 4 fixed core subjects (BM, BI, Math, Sejarah)
    sec1 = [get_g('bm'), get_g('eng'), get_g('math'), get_g('history')]

    student_keys = set(grades.keys())
    core_keys = {'bm', 'eng', 'math', 'history'}

    # Determine the candidate stream subjects.
    explicit = [s for s in (stream_subjects or []) if s in grades and s not in core_keys]
    if explicit:
        # Trust the student's explicit designation (TD-063).
        stream_candidates = explicit
        if len(stream_candidates) < 2:
            # ⚠ TOP UP TO TWO — DO NOT REMOVE. Sec2 is scored out of TWO
            # subjects, so a designation yielding only one leaves half the 30%
            # band scoring a subject the student never sat, at G = 0 points.
            #
            # That is not a rare edge. The grades page pre-fills the four
            # SCIENCE stream slots for everybody and, on save, keeps whichever
            # slots still name a subject — GRADED OR NOT (grades/page.tsx,
            # `aliranSubjects.filter(Boolean)`). A student who clears three of
            # them and types their real subjects into the ELECTIVE list below
            # ships exactly one usable stream subject. Measured on production
            # 2026-09-02: 15 profiles, 9 of them bursary applicants, each
            # losing 7-15 merit points on a score they can see.
            #
            # Topping up can only RAISE a merit score, never lower one: Sec2
            # weights a grade point at 5/6 against Sec3's 5/18, so promoting a
            # subject out of Sec3 always gains more than its replacement below
            # can lose. Verified over all 9 live carriers.
            spare = sorted(
                (k for k in student_keys
                 if k not in core_keys and k not in stream_candidates),
                key=lambda k: MERIT_GRADE_POINTS.get(grades[k], 0), reverse=True,
            )
            stream_candidates = stream_candidates + spare[:2 - len(stream_candidates)]
    else:
        # Fallback: legacy count-heuristic over the pools.
        science_present = student_keys & SCIENCE_POOL
        arts_present = student_keys & ARTS_POOL
        technical_present = student_keys & TECHNICAL_POOL
        stream_counts = [
            (len(science_present), SCIENCE_POOL),
            (len(arts_present), ARTS_POOL),
            (len(technical_present), TECHNICAL_POOL),
        ]
        stream_counts.sort(key=lambda x: x[0], reverse=True)
        primary_stream_pool = stream_counts[0][1]
        stream_candidates = [k for k in student_keys if k in primary_stream_pool]

    # Section 2: Best 2 from the stream candidates (by grade).
    stream_keys = sorted(
        stream_candidates,
        key=lambda k: MERIT_GRADE_POINTS.get(grades[k], 0), reverse=True
    )
    sec2_keys = stream_keys[:2]
    sec2 = [grades.get(k) for k in sec2_keys]

    # Section 3: Best 2 from remaining (not core, not used in sec2)
    used = core_keys | set(sec2_keys)
    remaining = [k for k in student_keys if k not in used]
    remaining.sort(
        key=lambda k: MERIT_GRADE_POINTS.get(grades[k], 0), reverse=True
    )
    sec3_keys = remaining[:2]
    sec3 = [grades.get(k) for k in sec3_keys]

    return sec1, sec2, sec3
