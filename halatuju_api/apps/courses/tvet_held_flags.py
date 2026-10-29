"""Held UP_TVET courses: three gate flags brought in line with their campus pages (Bumi F1b).

The held TVET courses (prod's IJTM-* / IKBN-*: one `course_requirements` row each, linked to many
campuses) were never written by Sprint F1, and their pages disagree with their stored flags. Owner
rulings (2026-10-29/30, decisions.md "Bumi F1b"), for these three flags ONLY:

  req_malaysian   "Warganegara Malaysia Sahaja"                         -> true
  no_colorblind   "Tiada Masalah Penglihatan Atau Rabun Warna"           -> true
  no_disability   the QUALIFIED line "tidak mempunyai ketidakupayaan ... yang menyukarkan kerja amali"
                  is text, never a gate -> false; a blanket "Tidak menerima sebarang OKU" keeps it

`build_flag_fix(...)` is PURE (a test rebuilds the committed `data/tvet/held_flag_fix_F1b.json` from the
committed `uptvet_F1_source.json`, the frozen read of the page cache). Each page is re-parsed with the F1
parser (`tvet_syarat.parse_requirements`), so a page's value of a flag is exactly what F1 would have
given a new course.

WHICH PAGES BELONG TO A HELD COURSE. A held course's campuses are the (course, institution) PAIRS prod
holds (`held_tvet_links.json`, read-only SQL 2026-10-29) plus the pairs F1 added (`held_links` with
`already_linked: false` in the F1 review file; live since F1). Prod's hyperlinks carry June's id_kursus,
so a pair is matched, never an id: an October catalogue row belongs to a held course when its id_kursus
is one prod links (`id_kursus`), else when its normalised name is exactly one held course's name in the
same family (`name`), else when the name matches several held courses and exactly ONE of them is linked
to that campus (`name+pair`, the four duplicate-name pairs prod holds). The row's campus is
`tvet_institutions.held_institution`. A row whose (course, campus) pair is not linked is listed in
`unlinked_rows` and ignored; a linked pair with no October row is listed per course (`no_page`).

THE RULE, per course and flag: every linked campus page agrees -> `new` is that value; they disagree ->
no change, and the course is in `conflicts` with each page's value and wording (the owner decides). A
page the parser could not read for its CONDITIONS (an unparsed reason about a condition, a gate or a
joiner) puts the course's three flags in `conflicts`; a page unparsed only for its academic rule (e.g.
"no SPM route") still reads its condition cards and counts. Every other difference between a page and
the held rule (three_m_only, subject rules, min_pass ...) is OUT OF SCOPE: listed in `not_applied` for
a later owner decision, never applied.

`old` is the repo fixture's value when the file was built (the fixture then took `new`, so it mirrors
prod after the fix). The lead compares `old` with prod read-only before the push, and
`fix_held_tvet_flags` refuses to write if any `old` differs from the database (compare-and-set).
"""
import re

from .tvet_catalogue_rows import _held_by_name, _read_rows, _rule_differences, norm_name
from .tvet_institutions import held_institution

FLAGS = ('req_malaysian', 'no_colorblind', 'no_disability')
HELD_FAMILIES = ('iljtm', 'ilkbs')

#: Wording shown beside each page's value (for the reviewer; the value itself is the parser's).
EVIDENCE = {
    'req_malaysian': re.compile(r'warganegara', re.I),
    'no_colorblind': re.compile(r'warna', re.I),
    'no_disability': re.compile(r'\bOKU\b|upaya', re.I),
}
#: An unparsed reason that means the CONDITION cards were not fully read (tvet_syarat's own messages).
_CONDITION_UNSAFE = re.compile(r'condition|joined by|no requirement card', re.I)


def _page_lines(page):
    lines = []
    for card in page['cards']:
        lines += [card['title'], card['subtitle']]
        for option in card['options']:
            lines.append(option['heading'])
            lines += [v for k, v in option['body'] if k == 'text']
    return [line for line in dict.fromkeys(lines) if line]


def _evidence(page):
    lines = _page_lines(page)
    found = {flag: [line for line in lines if pattern.search(line)] for flag, pattern in EVIDENCE.items()}
    return {flag: hits for flag, hits in found.items() if hits}


def _resolve(item, held_links, by_name, pairs):
    """(held course id, matched_by, institution id); course None when the row is no held course's."""
    inst = held_institution(item['family'], item['campus'])
    kid = item['row']['id_kursus']
    if kid in held_links:
        return held_links[kid][0], 'id_kursus', inst
    names = by_name.get((item['family'], norm_name(item['name'])), [])
    if len(names) == 1:
        return names[0], 'name', inst
    linked = [cid for cid in names if (cid, inst) in pairs]
    if len(names) > 1 and len(linked) == 1:
        return linked[0], 'name+pair', inst
    return None, ('ambiguous:' + ','.join(sorted(names))) if names else None, inst


def _flag(value):
    return bool(value)


_QUALIFIED = re.compile(r'menyukarkan|amali', re.I)


def _basis(flag, value, campuses):
    """Why a changed flag took its value, in words, from the pages' own wording (for the reviewer)."""
    n = len(campuses)
    if flag == 'no_disability' and not value:
        qualified = sum(1 for p in campuses if any(_QUALIFIED.search(line)
                                                    for line in p['evidence'].get('no_disability', [])))
        if qualified == n:
            return f'every linked page ({n}) carries only the qualified "... menyukarkan kerja amali" line (text)'
        if qualified == 0:
            return f'no linked page ({n}) carries any disability wording'
        return f'{qualified} of {n} linked pages carry the qualified line; the rest carry no disability wording'
    return f'every linked page ({n}) sets {flag} (wording: each campus\'s evidence)' if value \
        else f'no linked page ({n}) sets {flag}'


def build_flag_fix(source, held_links, prod_links, f1_new_links, held_courses):
    """`source`: the F1 source file ({'catalogue', 'pages'}); `held_links`: {id_kursus: (course, inst)}
    from prod; `prod_links`: [{'course_id', 'institution_id', 'id_kursus'}] (prod's pairs, June ids);
    `f1_new_links`: the F1 review's `held_links` with `already_linked` false; `held_courses`:
    {course_id: {'course': name, 'requirement': {field: value}}} (the repo fixture BEFORE the fix)."""
    pairs = {(x['course_id'], x['institution_id']): x['id_kursus'] for x in prod_links}
    for x in f1_new_links:
        pairs.setdefault((x['course_id'], x['institution_id']), x['id_kursus'])
    by_name = _held_by_name(held_courses)
    pages, unlinked, ambiguous = {}, [], []
    for item in _read_rows(source, HELD_FAMILIES):
        cid, matched_by, inst = _resolve(item, held_links, by_name, pairs)
        kid = item['row']['id_kursus']
        if cid is None:
            if matched_by:
                ambiguous.append({'id_kursus': kid, 'name': item['name'], 'institution_id': inst,
                                  'held_courses': matched_by[len('ambiguous:'):].split(',')})
            continue
        if (cid, inst) not in pairs:
            unlinked.append({'course_id': cid, 'id_kursus': kid, 'institution_id': inst, 'campus': item['campus'],
                             'matched_by': matched_by})
            continue
        parsed = item['parsed']
        pages.setdefault(cid, []).append({
            'institution_id': inst, 'id_kursus': kid, 'campus': item['campus'], 'matched_by': matched_by,
            'page': {flag: _flag(parsed['fields'][flag]) for flag in FLAGS},
            'unparsed': parsed['unparsed'],
            'conditions_read': not any(_CONDITION_UNSAFE.search(r) for r in parsed['unparsed']),
            'evidence': _evidence(item['page']),
            '_fields': parsed['fields'],
        })
    courses, conflicts, not_applied, no_page = [], [], [], []
    counts = {flag: {'false_to_true': 0, 'true_to_false': 0, 'unchanged': 0, 'conflict': 0} for flag in FLAGS}
    linked_courses = sorted({cid for cid, _ in pairs})
    for cid in linked_courses:
        held = held_courses.get(cid, {})
        requirement = held.get('requirement', {})
        missing = sorted(inst for c, inst in pairs if c == cid and inst not in
                         {p['institution_id'] for p in pages.get(cid, [])})
        missing = [{'institution_id': inst, 'prod_id_kursus': pairs[(cid, inst)]} for inst in missing]
        if cid not in pages:
            no_page.append({'course_id': cid, 'course': held.get('course', ''), 'linked_campuses': missing})
            continue
        campuses = sorted(pages[cid], key=lambda p: (p['institution_id'], int(p['id_kursus'])))
        old = {flag: _flag(requirement.get(flag)) for flag in FLAGS}
        new = dict(old)
        unreadable = [p for p in campuses if not p['conditions_read']]
        for flag in FLAGS:
            values = {p['page'][flag] for p in campuses}
            if unreadable or len(values) > 1:
                counts[flag]['conflict'] += 1
                conflicts.append({
                    'course_id': cid, 'flag': flag, 'old': old[flag],
                    'why': 'a linked page could not be read for its conditions' if unreadable
                           else 'the linked campus pages disagree',
                    'pages': [{'institution_id': p['institution_id'], 'id_kursus': p['id_kursus'],
                               'value': p['page'][flag], 'conditions_read': p['conditions_read'],
                               'wording': p['evidence'].get(flag, [])} for p in campuses]})
                continue
            new[flag] = values.pop()
            key = 'unchanged' if new[flag] == old[flag] else 'false_to_true' if new[flag] else 'true_to_false'
            counts[flag][key] += 1
        courses.append({
            'course_id': cid, 'course': held.get('course', ''), 'old': old, 'new': new,
            'basis': {flag: _basis(flag, new[flag], campuses) for flag in FLAGS if new[flag] != old[flag]},
            'campuses': [{k: v for k, v in p.items() if not k.startswith('_')} for p in campuses],
            'linked_campuses_without_page': missing,
        })
        by_field = {}
        for p in campuses:
            for field, diff in _rule_differences(p['_fields'], requirement).items():
                if field not in FLAGS:
                    by_field.setdefault(field, []).append((p['id_kursus'], diff['page']))
        for field in sorted(by_field):
            not_applied.append({'course_id': cid, 'field': field, 'held': requirement.get(field),
                                'pages': [{'id_kursus': kid, 'value': value} for kid, value in by_field[field]]})
    return {
        'built_from': 'data/tvet/uptvet_F1_source.json',
        'pairs_from': ['data/tvet/held_tvet_links.json (prod pairs)',
                       'data/tvet/tvet_new_courses_F1.json (held_links with already_linked false)'],
        'parser': 'apps/courses/tvet_syarat.py',
        'flags': list(FLAGS),
        'counts': {'courses': len(courses), 'campus_pages': sum(len(c['campuses']) for c in courses),
                   'no_page_courses': len(no_page), 'conflicts': len(conflicts),
                   'not_applied': len(not_applied), 'per_flag': counts},
        'courses': courses, 'conflicts': conflicts, 'not_applied': not_applied, 'no_page': no_page,
        'unlinked_rows': unlinked, 'ambiguous_rows': ambiguous,
    }


def before_fix(held_courses, fix):
    """`held_courses` (read from the fixture, which now mirrors prod AFTER the fix) with each listed
    course's three flags put back to the file's `old`: the picture the F1 review and this file were
    built against, so both rebuild byte for byte."""
    olds = {c['course_id']: c['old'] for c in fix['courses']}
    return {cid: {**held, 'requirement': {**held['requirement'], **olds.get(cid, {})}}
            for cid, held in held_courses.items()}


def changes(fix, reverse=False):
    """[(course_id, flag, expected current value, value to write)] for every flag whose `old` != `new`."""
    out = []
    for course in fix['courses']:
        for flag in FLAGS:
            old, new = course['old'][flag], course['new'][flag]
            if old != new:
                out.append((course['course_id'], flag, new, old) if reverse else (course['course_id'], flag, old, new))
    return out


def check_sql(fix, reverse=False):
    """ONE read-only statement: every listed course whose three flags in `course_requirements` differ from
    the file's `old` (`new` with reverse), or that is missing. Empty result = the file's picture is prod's."""
    side = 'new' if reverse else 'old'
    rows = [f"('{c['course_id']}', " + ', '.join('true' if c[side][f] else 'false' for f in FLAGS) + ')'
            for c in fix['courses']]
    lines = [f"WITH f (course_id, {', '.join(FLAGS)}) AS (VALUES",
             '  ' + ',\n  '.join(rows),
             ')',
             'SELECT f.course_id, r.course_id IS NULL AS missing,',
             ',\n'.join(f'  f.{x} AS file_{x}, r.{x} AS db_{x}' for x in FLAGS),
             'FROM f LEFT JOIN course_requirements r ON r.course_id = f.course_id',
             'WHERE r.course_id IS NULL',
             f"   OR (r.{', r.'.join(FLAGS)}) IS DISTINCT FROM (f.{', f.'.join(FLAGS)})",
             'ORDER BY f.course_id;']
    return '\n'.join(lines)

