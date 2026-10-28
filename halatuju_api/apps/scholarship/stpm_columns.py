"""The STPM certificate's COLUMN-ordered text layer, for `stpm_parse` (parser 1.1.0 / 1.3.0, 2026-10-28).

Some digital 2023/24 paper certificates store their text layer column by column: every subject name,
then every grade letter (under "Gred" / "(Grade)"), then every grade point with its status, with the
year and the PNGK near their labels. Read ONLY from a text layer (no word boxes — the caller checks),
ONLY from bounded blocks, paired by order only when the three lists are the same length;
`stpm_parse._checked_results` then applies every gate unchanged. Pure; the caller catches.

TWO SHAPES of the same column order, depending on the PDF library (1.3.0):
  * ONE ITEM PER LINE (pypdf 6.x, other producers): each subject name, letter and "point (status)"
    on its own line; "(Subject)", "(Grade)" and the year / PNGK on the lines after their labels.
  * MERGED LINES (pypdf 5.9.0 — PRODUCTION's locked library): the subject names run together on a
    line or two ("PENGAJIAN AM BAHASA MELAYU ..."), every letter sits on the "Gred (Grade)" header
    line, every "point (LULUS PENUH)" on ONE line, and the year / PNGK END their label lines after
    the English subtitle ("Tahun Peperiksaan: (Year of Examination) 2024").
The run of subject words is cut into known subjects only when exactly ONE cut exists.
"""
from __future__ import annotations

import re

from .stpm_parse import _STATUS, _SUBJECT_BY_KEY, _SUBJECTS, STPM_SCALE, _after, _find, _letters, _point_of

#: Every word of a known subject name, exactly as printed ("PENGAJIAN", "AM", "(T)", "AL-QURAN").
_SUBJECT_WORDS = frozenset(w for s in _SUBJECTS for w in s.split())
_LONGEST_SUBJECT = max(len(s.split()) for s in _SUBJECTS)


#: A printed status, whole: the statuses `stpm_parse` knows, plus the certificate's "LULUS PENUH".
_PRINTED_STATUS = frozenset(_STATUS) | {'LULUSPENUH'}


def _is_status(rest):
    """'(LULUS PENUH)' — ONE bracketed group that is EXACTLY a known printed status (review 2026-10-28):
    anything else in it ("(LULUS PENUH) Nota: (x)", "(LULUS) (X)") is not a status."""
    return (bool(rest) and rest[0].startswith('(') and rest[-1].endswith(')')
            and sum(t.count('(') for t in rest) == 1 and _letters(''.join(rest)) in _PRINTED_STATUS)


def _point_groups(row):
    """The grade points on a 'point (status)' row, or None: one group (one item per line), or
    several on one line — '3.67 (LULUS PENUH) 3.00 (LULUS PENUH) ...'; each status exact and closed."""
    if not row or _point_of(row[0]) is None:
        return None
    cuts = [i for i, t in enumerate(row) if _point_of(t) is not None] + [len(row)]
    groups = [row[a:b] for a, b in zip(cuts, cuts[1:])]
    if not all(len(g) >= 2 and _is_status(g[1:]) for g in groups):
        return None
    return [_point_of(g[0]) for g in groups]


def _split_names(tokens):
    """The ONE way to cut a run of subject words into known subjects, or None (none, or several)."""
    ways = [None] * len(tokens) + [[[]]]          # ways[i]: the cuts of tokens[i:], at most two kept
    for i in range(len(tokens) - 1, -1, -1):
        found = []
        for j in range(i + 1, min(len(tokens), i + _LONGEST_SUBJECT) + 1):
            subject = _SUBJECT_BY_KEY.get(_letters(''.join(tokens[i:j])))
            if subject and ways[j]:
                found += [[subject] + rest for rest in ways[j]]
        ways[i] = found[:2]
    return ways[0][0] if len(ways[0]) == 1 else None


def _column_subjects(rows, head, lulus):
    """The subject names between the "(Subject)" header and "Bilangan Mata Pelajaran Lulus": the
    rows made ONLY of subject words, in order, cut into known subjects (the one cut, else None).
    Other rows (prose, the index number) are passed over, but a row carrying a grade or a point, a
    subject word with debris or among other words ("SEJARAH,"), or reading like an unknown subject,
    → None — never skipped."""
    if _letters(''.join(rows[head])) == 'MATAPELAJARANSUBJECT':
        start = head + 1                         # merged: "Mata Pelajaran (Subject)" on one line
    elif head + 1 < lulus and _letters(''.join(rows[head + 1])) == 'SUBJECT':
        start = head + 2
    else:
        return None
    words = []
    for row in rows[start:lulus]:
        if all(t in _SUBJECT_WORDS for t in row):
            words += row                     # may open with "(T)": a name broken across lines
        elif row[0].startswith('('):
            continue                         # a bilingual subtitle: "(GENERAL STUDIES)"
        elif any(t in STPM_SCALE or _point_of(t) is not None for t in row):
            return None
        elif any(re.sub(r"[^A-Za-z()\-]", '', t) in _SUBJECT_WORDS for t in row):
            return None                      # a subject word with debris ("SEJARAH,") or among other words
        elif len(row) >= 2 and all(re.fullmatch(r'[A-Z()]+', t) for t in row):
            return None                      # an unknown subject name: never skipped silently
    return _split_names(words) if words else None


def _column_grades(rows):
    """("Gred" row, grade letters) — the letters under the ONE "Gred" / "(Grade)" header: those on
    the header line itself (merged), then the run of rows that are each a single STPM-scale letter."""
    heads = []                                       # (Gred row, last header row, letters on it)
    for i, row in enumerate(rows):
        if len(row) >= 2 and _letters(row[0]) == 'GRED' and row[1].startswith('(') and _letters(row[1]) == 'GRADE':
            heads.append((i, i, row[2:]))            # merged: "Gred (Grade) A- B B+ ..."
        elif i + 1 < len(rows) and _letters(''.join(row)) == 'GRED' and _letters(''.join(rows[i + 1])) == 'GRADE':
            heads.append((i, i + 1, []))
    if len(heads) != 1:
        return None
    gred, last, grades = heads[0]
    if any(t not in STPM_SCALE for t in grades):
        return None
    grades = list(grades)
    for row in rows[last + 1:]:
        if len(row) != 1 or row[0] not in STPM_SCALE:
            break
        grades.append(row[0])
    return gred, grades


def _column_points(rows, purata):
    """The grade points: the run of 'point (status)' rows that ends directly above the PNGK label,
    and no such point anywhere else on the page."""
    if purata < 1 or not (rows[purata] and _letters(''.join(rows[purata])).startswith('PURATANILAIGRED')):
        return None
    start = purata
    while start > 0 and _point_groups(rows[start - 1]) is not None:
        start -= 1
    points = [p for r in rows[start:purata] for p in _point_groups(r)]
    if sum(len(_point_groups(r) or []) for r in rows) != len(points):
        return None
    return points


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


def _label_value(rows, i, label_key, subtitle, pattern, window):
    """The value of label row `i`: below it (one item per line), or ending the label line after
    EXACTLY its English subtitle (merged): "(Year of Examination) 2024". Anything else → None."""
    rest = _after(rows[i], label_key)
    if not rest:
        return _value_below(rows, i, pattern, window)
    close = next((k for k, t in enumerate(rest) if t.endswith(')')), None)
    if not rest[0].startswith('(') or close is None or _letters(''.join(rest[:close + 1])) != subtitle:
        return None
    tail = rest[close + 1:]
    return tail[0] if len(tail) == 1 and re.fullmatch(pattern, tail[0]) else None


def cert_columns(rows, head, lulus, purata):
    """(rows_read, pngk, year, passed count) from a column-ordered text layer, or None. The
    passed count is the ONE bare one- or two-digit row between "Bilangan Mata Pelajaran Lulus" and
    the "Gred" header (none or two → None)."""
    names = _column_subjects(rows, head, lulus)
    gred, grades = _column_grades(rows) or (-1, None)
    points = _column_points(rows, purata)
    if not names or grades is None or points is None or not len(names) == len(grades) == len(points):
        return None
    if _after(rows[purata], 'KESELURUHAN'):
        return None                          # a value on this label row: not this layout
    pngk = _label_value(rows, purata, 'KUMULATIF', 'CUMULATIVEGRADEPOINTAVERAGE', r'[0-4]\.\d{2}', 2)
    tahun = _find(rows, 'TAHUNPEPERIKSAAN')
    if tahun < 0:
        return None
    year = _label_value(rows, tahun, 'PEPERIKSAAN', 'YEAROFEXAMINATION', r'20\d\d', 4)
    counts = [r[0] for r in rows[lulus + 1:gred] if len(r) == 1 and re.fullmatch(r'\d{1,2}', r[0])]
    if not pngk or not year or len(counts) != 1:
        return None
    read = [{'subject': n, 'grade': g, 'point': p} for n, g, p in zip(names, grades, points)]
    return read, pngk, int(year), int(counts[0])
