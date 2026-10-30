"""Held UP_TVET courses: three gate flags and the remarks brought in line with their pages (Bumi F1b).

The held TVET courses (prod's IJTM-* / IKBN-*: one `course_requirements` row each, linked to many
campuses) were never written by Sprint F1, and their pages disagree with their stored flags. Owner
rulings (2026-10-29/30, decisions.md "Bumi F1b"), for these four fields ONLY:

  req_malaysian   "Warganegara Malaysia Sahaja"                         -> true
  no_colorblind   "Tiada Masalah Penglihatan Atau Rabun Warna" on ANY read campus page -> true (a
                  colour-blind student is hidden from the course); false only when every read page is
                  silent (owner, 2026-10-30)
  no_disability   the QUALIFIED line "tidak mempunyai ketidakupayaan ... yang menyukarkan kerja amali"
                  is text, never a gate -> false; a page with no disability wording at all -> false
                  (owner, 2026-10-30); a blanket "Tidak menerima sebarang OKU" would keep it
  remarks         an EMPTY held remark takes the text F1 builds for a new row (`tvet_syarat`: age, health,
                  the qualified OKU line ...), so an OKU student sees the note (review M2). Text only: the
                  engine never reads it. Campuses that word only the qualified OKU line differently -> the
                  wording most of them use (tie: the most used across all held pages); other differences
                  -> the parts common to all (or nothing); both listed in `remark_variants`. A non-empty held remark is never touched.

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

THE RULE for req_malaysian and no_disability: every linked campus page agrees -> `new` is that value;
they disagree -> no change, and the course is in `conflicts` with each page's value and wording (the owner
decides; none today). no_colorblind has no disagreement path: any page that excludes colour blindness
wins. A page the parser could not read for its CONDITIONS (an unparsed reason about a condition, a gate
or a joiner) puts the course's three flags in `conflicts` and leaves its remark empty; a page unparsed only
for its academic rule (e.g. "no SPM route") still reads its condition cards and counts. Every other difference between a page and
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
#: Every column the fix writes (and compares before writing): the three flags and the remark text.
FIELDS = FLAGS + ('remarks',)
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
    if flag == 'no_colorblind' and value:
        k = sum(1 for p in campuses if p['page'][flag])
        return f'{k} of {n} linked pages exclude colour blindness (any one hides the course, owner 2026-10-30)'
    return f'every linked page ({n}) sets {flag} (wording: each campus\'s evidence)' if value \
        else f'no linked page ({n}) sets {flag}'


_OKU_LINE = re.compile(r'tidak mempunyai (ketidakupayaan|kurang upaya).*(menyukarkan|amali)', re.I)


def _remark(held, campuses, unreadable, counts, oku_wordings):
    """(remark to write, why). Only an EMPTY held remark is filled; the text is F1's own for a new row.
    Campuses that differ ONLY in how they word the qualified OKU line get the page text with the wording
    most of THIS course's campuses use (a tie: the wording most read pages of all held courses use;
    then the text, for a fixed order), so every OKU student sees the note (lead, 2026-10-30)."""
    if held:
        counts['held_not_empty'] += 1
        return held, 'held remark not empty: never touched'
    if unreadable:
        counts['left_empty'] += 1
        return '', 'left empty: a linked page could not be read for its conditions'
    texts = {p['remarks'] for p in campuses}
    if len(texts) == 1:
        text = texts.pop()
        counts['set_same_on_every_page' if text else 'left_empty'] += 1
        return text, f'every linked page ({len(campuses)}) gives this text'
    parts = [part for part in campuses[0]['_remark_parts'] if all(part in p['_remark_parts'] for p in campuses)]
    lines = [[part for part in p['_remark_parts'] if part not in parts] for p in campuses]
    if all(len(x) == 1 and _OKU_LINE.search(x[0]) for x in lines):
        here = {}
        for x in lines:
            here[x[0]] = here.get(x[0], 0) + 1
        chosen = max(here, key=lambda w: (here[w], oku_wordings.get(w, 0), w))
        text = next(p['remarks'] for p, x in zip(campuses, lines) if x[0] == chosen)
        counts['set_most_common_oku_wording'] += 1
        return text, (f'most common wording of the qualified OKU line: {here[chosen]} of {len(campuses)} linked '
                      f'pages ({oku_wordings.get(chosen, 0)} read pages of all held courses); the others are '
                      'listed in remark_variants')
    if not parts:
        counts['left_empty'] += 1
        return '', 'left empty: the linked pages share no remark text'
    counts['set_common_parts'] += 1
    return '. '.join(parts) + '.', f'common to all {len(campuses)} linked pages (their texts differ)'


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
            'remarks': parsed['fields']['remarks'],
            '_remark_parts': parsed['remarks'],
            'unparsed': parsed['unparsed'],
            'conditions_read': not any(_CONDITION_UNSAFE.search(r) for r in parsed['unparsed']),
            'evidence': _evidence(item['page']),
            '_fields': parsed['fields'],
        })
    courses, conflicts, not_applied, no_page, remark_variants = [], [], [], [], []
    counts = {flag: {'false_to_true': 0, 'true_to_false': 0, 'unchanged': 0, 'conflict': 0} for flag in FLAGS}
    remark_counts = {'set_same_on_every_page': 0, 'set_most_common_oku_wording': 0, 'set_common_parts': 0,
                     'left_empty': 0, 'held_not_empty': 0}
    oku_wordings = {}
    for cid_pages in pages.values():
        for p in cid_pages:
            for part in p['_remark_parts']:
                if _OKU_LINE.search(part):
                    oku_wordings[part] = oku_wordings.get(part, 0) + 1
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
        old['remarks'] = requirement.get('remarks') or ''
        new = dict(old)
        unreadable = [p for p in campuses if not p['conditions_read']]
        for flag in FLAGS:
            values = {p['page'][flag] for p in campuses}
            if flag == 'no_colorblind' and not unreadable:
                values = {any(values)}      # any read page that excludes colour blindness hides the course
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
        new['remarks'], remark_basis = _remark(old['remarks'], campuses, unreadable, remark_counts, oku_wordings)
        if remark_basis.startswith(('most common', 'common', 'left empty')):
            remark_variants.append({'course_id': cid, 'used': new['remarks'], 'why': remark_basis,
                                    'pages': [{'id_kursus': p['id_kursus'], 'remarks': p['remarks']}
                                              for p in campuses]})
        basis = {flag: _basis(flag, new[flag], campuses) for flag in FLAGS if new[flag] != old[flag]}
        if new['remarks'] != old['remarks']:
            basis['remarks'] = remark_basis
        courses.append({
            'course_id': cid, 'course': held.get('course', ''), 'old': old, 'new': new, 'basis': basis,
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
        'flags': list(FLAGS), 'fields': list(FIELDS),
        'counts': {'courses': len(courses), 'campus_pages': sum(len(c['campuses']) for c in courses),
                   'no_page_courses': len(no_page), 'conflicts': len(conflicts),
                   'not_applied': len(not_applied), 'per_flag': counts, 'remarks': remark_counts},
        'courses': courses, 'conflicts': conflicts, 'remark_variants': remark_variants,
        'not_applied': not_applied, 'no_page': no_page,
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
    """[(course_id, field, expected current value, value to write)] for every field whose `old` != `new`."""
    out = []
    for course in fix['courses']:
        for flag in FIELDS:
            old, new = course['old'][flag], course['new'][flag]
            if old != new:
                out.append((course['course_id'], flag, new, old) if reverse else (course['course_id'], flag, old, new))
    return out


def check_sql(fix, reverse=False):
    """ONE read-only statement: every listed course whose three flags or remarks in `course_requirements`
    differ from the file's `old` (`new` with reverse), or that is missing. Empty result = the file's
    picture is prod's."""
    side = 'new' if reverse else 'old'

    def literal(value):
        return ('true' if value else 'false') if isinstance(value, bool) else "'" + value.replace("'", "''") + "'"
    rows = [f"('{c['course_id']}', " + ', '.join(literal(c[side][f]) for f in FIELDS) + ')'
            for c in fix['courses']]
    lines = [f"WITH f (course_id, {', '.join(FIELDS)}) AS (VALUES",
             '  ' + ',\n  '.join(rows),
             ')',
             'SELECT f.course_id, r.course_id IS NULL AS missing,',
             ',\n'.join(f'  f.{x} AS file_{x}, r.{x} AS db_{x}' for x in FIELDS),
             'FROM f LEFT JOIN course_requirements r ON r.course_id = f.course_id',
             'WHERE r.course_id IS NULL',
             f"   OR (r.{', r.'.join(FIELDS)}) IS DISTINCT FROM (f.{', f.'.join(FIELDS)})",
             'ORDER BY f.course_id;']
    return '\n'.join(lines)

