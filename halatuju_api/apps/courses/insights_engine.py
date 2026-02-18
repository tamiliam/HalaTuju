"""
Deterministic insights engine for HalaTuju.

Generates structured summaries from eligibility results — no AI, no randomness.
Pure function: takes eligible courses list, returns insights dict.

Used by:
- EligibilityCheckView (embedded in response)
- Future: AI report backend (Sprint 11) consumes these as input
"""

# Source type display labels (Malay)
SOURCE_TYPE_LABELS = {
    'poly': 'Politeknik',
    'kkom': 'Kolej Komuniti',
    'tvet': 'TVET',
    'ua': 'Universiti Awam',
    'pismp': 'PISMP (Perguruan)',
}


def generate_insights(eligible_courses):
    """
    Generate deterministic insights from eligibility results.

    Args:
        eligible_courses: List of dicts, each with:
            course_id, course_name, level, field, source_type,
            merit_cutoff, student_merit, merit_label, merit_color

    Returns:
        Dict with:
            stream_breakdown: [{source_type, label, count}, ...]
            top_fields: [{field, count}, ...] (top 5)
            level_distribution: [{level, count}, ...]
            merit_summary: {high, fair, low, no_data}
            summary_text: One-line Malay summary
    """
    if not eligible_courses:
        return {
            'stream_breakdown': [],
            'top_fields': [],
            'level_distribution': [],
            'merit_summary': {'high': 0, 'fair': 0, 'low': 0, 'no_data': 0},
            'summary_text': 'Tiada kursus yang layak ditemui.',
        }

    # --- Stream Breakdown ---
    stream_counts = {}
    for course in eligible_courses:
        st = course.get('source_type', 'unknown')
        stream_counts[st] = stream_counts.get(st, 0) + 1

    stream_breakdown = [
        {
            'source_type': st,
            'label': SOURCE_TYPE_LABELS.get(st, st),
            'count': count,
        }
        for st, count in sorted(stream_counts.items(), key=lambda x: -x[1])
    ]

    # --- Top Fields ---
    field_counts = {}
    for course in eligible_courses:
        field = course.get('field', '').strip()
        if field:
            field_counts[field] = field_counts.get(field, 0) + 1

    top_fields = [
        {'field': field, 'count': count}
        for field, count in sorted(field_counts.items(), key=lambda x: -x[1])[:5]
    ]

    # --- Level Distribution ---
    level_counts = {}
    for course in eligible_courses:
        level = course.get('level', '').strip()
        if level:
            level_counts[level] = level_counts.get(level, 0) + 1

    level_distribution = [
        {'level': level, 'count': count}
        for level, count in sorted(level_counts.items(), key=lambda x: -x[1])
    ]

    # --- Merit Summary ---
    merit_summary = {'high': 0, 'fair': 0, 'low': 0, 'no_data': 0}
    for course in eligible_courses:
        label = (course.get('merit_label') or '').lower()
        if label == 'high':
            merit_summary['high'] += 1
        elif label == 'fair':
            merit_summary['fair'] += 1
        elif label == 'low':
            merit_summary['low'] += 1
        else:
            merit_summary['no_data'] += 1

    # --- Summary Text ---
    total = len(eligible_courses)
    stream_count = len(stream_counts)
    top_field_name = top_fields[0]['field'] if top_fields else ''
    top_field_count = top_fields[0]['count'] if top_fields else 0

    summary_text = (
        f'Anda layak memohon {total} kursus merentasi {stream_count} aliran.'
    )
    if top_field_name:
        summary_text += (
            f' Bidang terkuat anda ialah {top_field_name} '
            f'({top_field_count} kursus).'
        )

    return {
        'stream_breakdown': stream_breakdown,
        'top_fields': top_fields,
        'level_distribution': level_distribution,
        'merit_summary': merit_summary,
        'summary_text': summary_text,
    }
