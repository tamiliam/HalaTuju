"""
Eligibility check service — business logic extracted from EligibilityCheckView.

Functions:
- compute_student_merit: Calculate student merit from grades or use precomputed value
- compute_course_merit: Per-course merit branching (standard/matric/stpm_mata_gred)
- deduplicate_pismp: Collapse PISMP zone variants
- sort_eligible_courses: Multi-key sort by merit tier, delta, credential, pathway
- compute_stats: Count courses by source_type and pathway_type
"""
from collections import defaultdict

from .engine import (
    prepare_merit_inputs,
    calculate_merit_score,
    check_merit_probability,
)
from .pathways import check_matric_track, check_stpm_bidang
from .ranking_engine import get_credential_priority


def compute_student_merit(data):
    """
    Calculate student merit score from request data.

    Uses precomputed merit if provided, otherwise calculates from grades.
    Returns a float merit score.
    """
    student_merit = data.get('student_merit')
    if student_merit is not None:
        return student_merit

    grades_for_merit = dict(data.get('grades', {}))
    if 'hist' in grades_for_merit:
        grades_for_merit['history'] = grades_for_merit.pop('hist')
    sec1, sec2, sec3 = prepare_merit_inputs(grades_for_merit)
    coq_score = data.get('coq_score', 5.0)
    merit_result = calculate_merit_score(sec1, sec2, sec3, coq_score=coq_score)
    return merit_result['final_merit']


_MATRIC_TRACK_MAP = {
    'matric-sains': 'sains',
    'matric-kejuruteraan': 'kejuruteraan',
    'matric-sains-komputer': 'sains_komputer',
    'matric-perakaunan': 'perakaunan',
}

_STPM_BIDANG_MAP = {
    'stpm-sains': 'sains',
    'stpm-sains-sosial': 'sains_sosial',
}


def compute_course_merit(merit_type, source_type, merit_cutoff, student_merit,
                         course_id, data, grades):
    """
    Compute merit label/color for a single course based on its merit_type.

    Returns a dict with merit fields, or None if the course should be skipped
    (matric/STPM pathway says not eligible).
    """
    merit_label = None
    merit_color = None
    merit_display_student = None
    merit_display_cutoff = None
    student_merit_for_course = student_merit

    if merit_type == 'matric':
        track_id = _MATRIC_TRACK_MAP.get(course_id)
        if track_id:
            coq = data.get('coq_score', 5.0)
            matric_result = check_matric_track(track_id, grades, coq)
            if matric_result['eligible'] and matric_result['merit'] is not None:
                student_merit_for_course = matric_result['merit']
                if student_merit_for_course >= 94:
                    merit_label, merit_color = "High", "#2ecc71"
                elif student_merit_for_course >= 89:
                    merit_label, merit_color = "Fair", "#f1c40f"
                else:
                    merit_label, merit_color = "Low", "#e74c3c"
            else:
                return None  # Skip — pathway says not eligible

    elif merit_type == 'stpm_mata_gred':
        bidang_id = _STPM_BIDANG_MAP.get(course_id)
        if bidang_id:
            stpm_result = check_stpm_bidang(bidang_id, grades)
            if stpm_result['eligible'] and stpm_result['mata_gred'] is not None:
                mata_gred = stpm_result['mata_gred']
                max_mg = stpm_result['max_mata_gred']
                if mata_gred <= 12:
                    merit_label, merit_color = "High", "#2ecc71"
                elif mata_gred <= max_mg:
                    merit_label, merit_color = "Fair", "#f1c40f"
                else:
                    merit_label, merit_color = "Low", "#e74c3c"
                merit_display_student = str(mata_gred)
                merit_display_cutoff = str(max_mg)
                student_merit_for_course = (27 - mata_gred) / 24 * 100
            else:
                return None  # Skip — pathway says not eligible

    else:
        # Standard SPM merit — no source_type guard
        if merit_cutoff:
            merit_label, merit_color = check_merit_probability(
                student_merit, merit_cutoff
            )

    return {
        'merit_label': merit_label,
        'merit_color': merit_color,
        'merit_display_student': merit_display_student,
        'merit_display_cutoff': merit_display_cutoff,
        'student_merit': student_merit_for_course,
    }


def deduplicate_pismp(eligible_courses, req_hashes):
    """
    Collapse PISMP zone variants into deduplicated cards.

    Zone code in course_id[4:6]: 01/06=National, 03=Chinese, 04=Tamil, 05=Special.
    Rules:
      1. Collapse entries with identical subject_group_req (regardless of zone)
      2. Chinese/Tamil with DIFFERENT requirements from National ->
         merge into one card "(Aliran Cina/Tamil)" with pismp_languages

    Args:
        eligible_courses: List of course dicts (mixed types)
        req_hashes: Dict mapping course_id -> JSON hash of subject_group_req
                    (only for PISMP courses)

    Returns:
        Deduplicated list of course dicts.
    """
    def _pismp_zone(cid):
        z = cid[4:6] if len(cid) >= 6 else ''
        if z == '03':
            return 'cn'
        if z == '04':
            return 'ta'
        if z == '05':
            return 'sn'
        return 'nat'

    pismp_groups = defaultdict(lambda: {'nat': [], 'cn': [], 'ta': [], 'sn': []})
    non_pismp = []
    for c in eligible_courses:
        if c['source_type'] == 'pismp':
            zone = _pismp_zone(c['course_id'])
            pismp_groups[c['course_name']][zone].append(c)
        else:
            non_pismp.append(c)

    _lang_labels = {'cn': 'Bahasa Cina', 'ta': 'Bahasa Tamil'}

    deduped_pismp = []
    for name, zones in pismp_groups.items():
        nat_entries = zones['nat'] + zones['sn']
        nat_hash = req_hashes.get(nat_entries[0]['course_id']) if nat_entries else None

        if nat_entries:
            deduped_pismp.append(nat_entries[0])

        diff_langs = []
        for lang_zone in ('cn', 'ta'):
            lang_entries = zones[lang_zone]
            if not lang_entries:
                continue
            lang_hash = req_hashes.get(lang_entries[0]['course_id'])
            if lang_hash == nat_hash:
                continue
            diff_langs.append((lang_zone, lang_entries[0]))

        if diff_langs:
            base = diff_langs[0][1].copy()
            langs = [_lang_labels[lz] for lz, _ in diff_langs]
            suffix = '/'.join(langs)
            base['course_name'] = f"{name} (Aliran {suffix})"
            base['pismp_languages'] = langs
            deduped_pismp.append(base)

    return non_pismp + deduped_pismp


# Sort constants
_PATHWAY_PRIORITY = {
    'asasi': 8, 'matric': 7, 'stpm': 6,
    'university': 5, 'ua': 5, 'poly': 4, 'pismp': 3, 'kkom': 2,
    'iljtm': 1, 'ilkbs': 1,
}
_MERIT_LABEL_PRIORITY = {'High': 3, 'Fair': 2, 'Low': 1}


def _merit_delta(c):
    """Delta sort only for Fair/Low — High uses credential instead."""
    if c.get('merit_label') in ('Fair', 'Low'):
        return -(c.get('student_merit', 0) - (c['merit_cutoff'] or 0))
    return 0


def _merit_sort_key(c):
    label = c.get('merit_label') or ''
    if label:
        return -_MERIT_LABEL_PRIORITY[label]
    if c.get('source_type') == 'pismp':
        return -_MERIT_LABEL_PRIORITY['High']
    pt = c.get('pathway_type', c.get('source_type', ''))
    if pt in ('iljtm', 'ilkbs'):
        return -1.5
    return -2


def sort_eligible_courses(courses):
    """
    Sort eligible courses by merit tier, delta, credential, pathway, cutoff.

    Returns a new sorted list (does not mutate input).
    """
    return sorted(courses, key=lambda c: (
        _merit_sort_key(c),
        _merit_delta(c),
        -get_credential_priority(c['course_name'], c.get('source_type', '')),
        -_PATHWAY_PRIORITY.get(c.get('pathway_type', c.get('source_type', '')), 0),
        -float(c['merit_cutoff'] or 0),
        c['course_name'],
    ))


def compute_stats(courses):
    """
    Count courses by source_type and pathway_type.

    Returns (stats_dict, pathway_stats_dict).
    """
    stats = {}
    pathway_stats = {}
    for c in courses:
        st = c['source_type']
        stats[st] = stats.get(st, 0) + 1
        pt = c.get('pathway_type', st)
        pathway_stats[pt] = pathway_stats.get(pt, 0) + 1
    return stats, pathway_stats
