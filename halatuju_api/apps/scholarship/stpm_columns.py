"""The STPM certificate's COLUMN-ordered text layer, for `stpm_parse` (parser 1.1.0, 2026-10-28).

Some digital 2023/24 paper certificates store their text layer column by column: every subject name,
then every grade letter (under "Gred" / "(Grade)"), then every grade point with its status, with the
year and the PNGK a couple of lines after their labels. Read ONLY from a text layer (no word boxes —
the caller checks), ONLY from bounded blocks, paired by order only when the three lists are the same
length; `stpm_parse._checked_results` then applies every gate unchanged. Pure; the caller catches.
"""
from __future__ import annotations

import re

from .stpm_parse import _STATUS, _SUBJECT_BY_KEY, STPM_SCALE, _after, _find, _letters, _point_of

def _is_point_row(row):
    """'3.67 (LULUS PENUH)' — a grade point followed by its printed status (required)."""
    return (len(row) >= 2 and _point_of(row[0]) is not None and row[1].startswith('(')
            and any(_letters(''.join(row[1:])).startswith(s) for s in _STATUS))


def _column_subjects(rows, head, lulus):
    """The subject names between the "(Subject)" header and "Bilangan Mata Pelajaran Lulus": rows
    that are EXACTLY a known subject. Other rows (prose, the index number) are passed over, but a
    row carrying a grade or a point, or reading like an unknown subject, → None."""
    if head + 1 >= lulus or _letters(''.join(rows[head + 1])) != 'SUBJECT':
        return None
    names = []
    for row in rows[head + 2:lulus]:
        if row[0].startswith('('):
            continue                         # a bilingual subtitle: "(GENERAL STUDIES)"
        subject = _SUBJECT_BY_KEY.get(_letters(''.join(row)))
        if subject:
            names.append(subject)
        elif any(t in STPM_SCALE or _point_of(t) is not None for t in row):
            return None
        elif len(row) >= 2 and all(re.fullmatch(r'[A-Z()]+', t) for t in row):
            return None                      # an unknown subject name: never skipped silently
    return names


def _column_grades(rows):
    """(header row, grade letters) — the letters under the ONE "Gred" / "(Grade)" header: the run
    of rows that are each a single STPM-scale letter, directly below it."""
    heads = [i for i in range(len(rows) - 1)
             if _letters(''.join(rows[i])) == 'GRED' and _letters(''.join(rows[i + 1])) == 'GRADE']
    if len(heads) != 1:
        return None
    grades = []
    for row in rows[heads[0] + 2:]:
        if len(row) != 1 or row[0] not in STPM_SCALE:
            break
        grades.append(row[0])
    return heads[0], grades


def _column_points(rows, purata):
    """The grade points: the run of 'point (status)' rows that ends directly above the PNGK label,
    and no such row anywhere else on the page."""
    if purata < 1 or not (rows[purata] and _letters(''.join(rows[purata])).startswith('PURATANILAIGRED')):
        return None
    start = purata
    while start > 0 and _is_point_row(rows[start - 1]):
        start -= 1
    if sum(1 for r in rows if _is_point_row(r)) != purata - start:
        return None
    return [_point_of(r[0]) for r in rows[start:purata]]


def _value_below(rows, i, pattern, window):
    """The value on the first row after label row `i` that is not an English subtitle '(…)' or a
    neighbouring column's label, within `window` rows: it must be the WHOLE row and match. A
    "Tarikh" (release-date) row ends the search: the release date is never the exam year."""
    for row in rows[i + 1:i + 1 + window]:
        flat = _letters(''.join(row))
        if 'TARIKH' in flat:
            return None
        if row[0].startswith('(') or flat in ('NILAIGRED', 'GRED'):
            continue
        return row[0] if len(row) == 1 and re.fullmatch(pattern, row[0]) else None
    return None


def cert_columns(rows, head, lulus, purata):
    """(rows_read, pngk, year, passed count) from a column-ordered text layer, or None. The
    passed count is the ONE bare one- or two-digit row between "Bilangan Mata Pelajaran Lulus" and
    the "Gred" header (none or two → None)."""
    names = _column_subjects(rows, head, lulus)
    gred, grades = _column_grades(rows) or (-1, None)
    points = _column_points(rows, purata)
    if not names or grades is None or points is None or not len(names) == len(grades) == len(points):
        return None
    if _after(rows[purata], 'KUMULATIF') or _after(rows[purata], 'KESELURUHAN'):
        return None                          # a value on the label row: not this layout
    pngk = _value_below(rows, purata, r'[0-4]\.\d{2}', 2)
    tahun = _find(rows, 'TAHUNPEPERIKSAAN')
    if tahun < 0 or _after(rows[tahun], 'PEPERIKSAAN'):
        return None
    year = _value_below(rows, tahun, r'20\d\d', 4)
    counts = [r[0] for r in rows[lulus + 1:gred] if len(r) == 1 and re.fullmatch(r'\d{1,2}', r[0])]
    if not pngk or not year or len(counts) != 1:
        return None
    read = [{'subject': n, 'grade': g, 'point': p} for n, g, p in zip(names, grades, points)]
    return read, pngk, int(year), int(counts[0])
