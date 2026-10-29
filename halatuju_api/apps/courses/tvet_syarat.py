"""UP_TVET "Pra-Syarat Kursus" cards -> `CourseRequirement` fields (Bumi coverage Sprint F1).

Input: `tvet_pages.read_page(html)`. Output of `parse_requirements(page)`:
`{'fields': {...}, 'unparsed': [...], 'warnings': [...], 'remarks': [...], 'header_mismatches': n,
'open': bool}`. Any `unparsed` reason means the row is NOT faithful and is never ingested
(`tvet_catalogue_rows` moves it to the review file's `flagged` list): this parser never guesses.

Cards are joined by DAN (all must hold); the options inside one card ("Syarat Wajib", or "Syarat
Pilihan 1 ATAU Syarat Pilihan 2 ...") are alternatives. Owner rulings F (2026-10-29):

  ACADEMIC CARD   an option with "Tiada Pendidikan Formal ..."     -> the card adds NO academic rule
                  SPM options ("Bil. Subjek : N / Gred Minimum : X" + subject table, items "1. ..."
                  joined by Dan; or the Wajib/Pilihan table)    -> the academic rule; one option is a
                  count-once block (`spm_count_once.py`), several are ONE `any_of` group
                  SVM / SKM / STM / Sijil / CGPA options          -> ignored (not an SPM leaver's route)
                  only non-SPM options                            -> UNPARSED (no SPM route)
  Warganegara Malaysia Sahaja                                     -> req_malaysian
  Calon Bumiputera Sahaja / Berbangsa Melayu, Orang Asli ...      -> req_bumiputera (a Bumi ATAU
                  citizen card is citizen only: a Bumiputera is always a citizen)
  Tiada Masalah Penglihatan Atau Rabun Warna                      -> no_colorblind
  Tidak menerima sebarang OKU                                     -> no_disability
  Bujang                                                          -> single (shown, never a gate)
  temu duga                                                       -> req_interview (+ the text)
  Umur Minimum / Maksimum, Sihat Tubuh Badan, membaca/menulis/mengira, BMI, and the QUALIFIED
                  "tidak mempunyai ketidakupayaan ... yang menyukarkan kerja amali"
                                                                  -> remarks TEXT, never a gate
  any gender wording, a religion, an unknown line                 -> UNPARSED
  ... and in an ACADEMIC card, every line of every option (SVM / Tahfiz / open too) is read for those
  gates (`academic_gate_hits`): gender / religion, or a gate no condition card sets, is UNPARSED

Inside an SPM option every item counts ONCE with the others (one block): "Lulus dua (2) subjek wajib;
Lulus satu (1) subjek Matematik; Lulus satu (1) subjek pilihan" are four different subjects. An item
"selain di atas", or a table holding "MATA PELAJARAN SELAIN DI ATAS", is N more subjects excluding
every subject named before it (the strict reading, decisions.md 2026-10-29). Where the item's
printed title disagrees with its table (count or grade), the TABLE wins, the title goes into the
remarks, and `header_mismatches` counts it. Subject names: `tvet_subjects.py`.
"""
import re

from .spm_syarat import SINGLE_SUBJECT_FLAGS, _once
from .tvet_subjects import ANY_OTHER, split_names, tvet_subject_keys

NUMBER_WORDS = {'satu': 1, 'dua': 2, 'tiga': 3, 'empat': 4, 'lima': 5, 'enam': 6}
GRADES = {'A+', 'A', 'A-', 'B+', 'B', 'C+', 'C', 'D', 'E', 'G'}

_OPEN_RE = re.compile(r'Tiada Pendidikan Formal', re.I)
_OTHER_RE = re.compile(r'\bSVM\b|Vokasional|\bSKM\b|Sijil Kemahiran|Tahfiz|Pondok|Politeknik|Kekompetenan|'
                       r'pengalaman kerja|Jenis Sijil|CGPA|\bDKM\b|\bDLKM\b|Sijil Tahap|\bSTM\b', re.I)
_SPM_RE = re.compile(r'\bSPM\b|Sijil Pelajaran Malaysia|Tingkatan 5|Bil\. Subjek', re.I)
_ITEM_RE = re.compile(r'^(\d+)\.\s*(.*)$')
_COUNT_RE = re.compile(r'^Bil\. Subjek\s*:\s*(\d*)$')
_GRADE_RE = re.compile(r'^Gred Minimum\s*:\s*(\S*)$')
_EXCLUDED_RE = re.compile(r'^Subjek Yang Dikecualikan', re.I)
_OPEN_COUNT_RE = re.compile(r'Bil\. Subjek Pilihan Kategori (.+?) Diperlukan\s*:\s*(\d+)', re.I)

#: Non-academic lines: (pattern, action). First match wins; an unmatched line is UNPARSED.
LINE_RULES = (
    (r'^Umur Minimum\s*:\s*(\d+)', 'age_min'),
    (r'^Umur Maksimum\s*:\s*(\d+)', 'age_max'),
    (r'\bLelaki\b|\bPerempuan\b|\bWanita\b|\bjantina\b', 'gender'),
    (r'beragama|\bIslam\b|Muslim', 'religion'),
    (r'Warganegara Malaysia Sahaja|^WARGANEGARA SAHAJA$|^Warganegara Malaysia$', 'req_malaysian'),
    (r'Bumiputera Sahaja|Berbangsa Melayu, Orang Asli', 'req_bumiputera'),
    (r'Tiada Masalah Penglihatan Atau Rabun Warna', 'no_colorblind'),
    (r'Tidak menerima sebarang OKU', 'no_disability'),
    (r'tidak mempunyai (ketidakupayaan|kurang upaya)', 'remark_disability'),
    (r'Sihat Tubuh Badan', 'remark_health'),
    (r'(membaca|menulis|mengira)', 'remark_literacy'),
    (r'Indeks Jisim Badan|\bBMI\b', 'remark_text'),
    (r'temu ?duga|peperiksaan khas', 'req_interview'),
    (r'^\d*\.?\s*Bujang', 'single'),
    (r'[Bb]erumur|\btahun\b|^Umur Calon$', 'age_text'),
    (r'^(Mestilah|Calon mestilah|Pemohon adalah|Pemohon (Hendaklah|mestilah)|Syarat Umum|Syarat-syarat AM|'
     r'MALAYSIA|Mestilah Berumur|Pemohon Hendaklah Berumur|WARGANEGARA SAHAJA|Warganegara sahaja|'
     r'Had Umur Minimum dan Maksimun|Bumiputera sahaja|Calon mestilah :|Minimum)\W*$', 'ignore'),
    (r'^(Calon diwajibkan memenuhi|Pemohon Hendaklah Memenuhi) syarat(-syarat)? tambahan '
     r'(berikut|seperti berikut)\W*$', 'ignore'),
)
_RULES = [(re.compile(p, re.I), a) for p, a in LINE_RULES]
FIXED_REMARKS = {'remark_health': 'Sihat tubuh badan',
                 'remark_literacy': 'Boleh membaca, menulis dan mengira'}


def _option_lines(option):
    lines = [option['heading']] if option['heading'] else []
    return lines + [v for k, v in option['body'] if k == 'text']


def _tables(option):
    return [v for k, v in option['body'] if k == 'table']


def classify_option(option):
    """'open' | 'other' (a non-SPM qualification) | 'spm' | None (not an academic option)."""
    text = ' '.join(_option_lines(option))
    tables = _tables(option)
    if _OPEN_RE.search(text):
        return 'open'
    if _OTHER_RE.search(option['heading']) or any(len(t['headers']) == 4 for t in tables) \
            or re.search(r'Jenis Sijil|CGPA|\[[A-Z]{1,3}\d?-\d', text):
        return 'other'
    if _SPM_RE.search(text) or any(len(t['headers']) in (2, 6) for t in tables):
        return 'spm'
    if _OTHER_RE.search(text):
        return 'other'
    return None


# --- SPM options -----------------------------------------------------------------------------

def _items(option, problems):
    """An SPM option's body -> items [{title, lines, count, grade, rows, exclusion, wide}]."""
    items, current = [], None
    for kind, value in option['body']:
        if kind == 'table':
            if current is None:
                current = {'title': '', 'lines': [], 'count': None, 'grade': None, 'rows': None,
                           'exclusion': False}
                items.append(current)
            current['rows'] = value['rows']
            current['wide'] = len(value['headers']) == 6
            continue
        m = _ITEM_RE.match(value)
        if current is not None and not m and (current['rows'] is not None or current['exclusion']) \
                and (value.lower() == 'dan' or _COUNT_RE.match(value)):
            # A second rule inside one numbered item ("KEPUJIAN bagi subjek: Bahasa Inggeris ... Dan
            # Matematik / ..."): its own count, grade and table, under the same title.
            current = {'title': current['title'], 'lines': [], 'count': None, 'grade': None, 'rows': None,
                       'exclusion': False}
            items.append(current)
            if value.lower() == 'dan':
                continue
        if m:
            current = {'title': m.group(2), 'lines': [], 'count': None, 'grade': None, 'rows': None,
                       'exclusion': False}
            items.append(current)
        elif current is None:
            continue  # the option's own preamble ("Calon memiliki SPM dengan:")
        elif _COUNT_RE.match(value):
            digits = _COUNT_RE.match(value).group(1)
            current['count'] = int(digits) if digits else None
        elif _GRADE_RE.match(value):
            current['grade'] = _GRADE_RE.match(value).group(1) or None
        elif _EXCLUDED_RE.match(value):
            current['exclusion'] = True
        elif _OPEN_COUNT_RE.search(value):
            current.setdefault('open_counts', []).append(_OPEN_COUNT_RE.search(value).groups())
        else:
            current['lines'].append(value)
    return items


def _row_keys(cell, problems, warnings):
    """One table cell -> keys (alternatives in one row are one slot); None when unknown."""
    keys = []
    for name in split_names(cell):
        found = tvet_subject_keys(name)
        if found is None:
            problems.append(f'unknown subject name: {name!r}')
            return None
        if not found:
            warnings.append(f'no grade-form key, dropped from its list: {name!r}')
        keys += [k for k in found if k not in keys]
    return keys


def _title_says(title):
    """(count, grade) the item's printed title states, each None when it states none."""
    low = title.lower()
    m = re.search(r'\b(satu|dua|tiga|empat|lima|enam)\b\s*\((\d)\)', low)
    count = int(m.group(2)) if m else None
    grade = 'C' if re.search(r'kepujian|kredit', low) else 'E' if re.search(r'\blulus\b', low) else None
    return count, grade


def _wide_item(item, problems, warnings):
    """The Wajib/Pilihan table (Kod | Subjek | Wajib/Pilihan | Kategori | Min Gred | Aktif) -> groups."""
    groups, by_category = [], {}
    for row in item['rows']:
        if len(row) < 6 or row[5].lower() != 'aktif':
            warnings.append(f'inactive row skipped: {row!r}')
            continue
        keys = _row_keys(row[1], problems, warnings)
        if keys is None:
            return None
        if row[2].lower() == 'wajib':
            if not keys:
                problems.append(f'a required subject is not on the grade form: {row[1]!r}')
                return None
            groups.append({'count': 1, 'grade': row[4], 'subjects': keys})
        else:
            by_category.setdefault(row[3] or 'Terbuka', []).append((keys, row[4]))
    pilihan = [entry for rows in by_category.values() for entry in rows]
    for category, n in item.get('open_counts', []):
        pool = pilihan if category.lower() == 'terbuka' else by_category.get(category, [])
        grades = {g for _, g in pool}
        if not pool or len(grades) != 1:
            problems.append(f'Pilihan category {category!r} cannot be read (grades {sorted(grades)})')
            return None
        groups.append({'count': int(n), 'grade': grades.pop(), 'subjects': _once(k for ks, _ in pool for k in ks)})
    if pilihan and not item.get('open_counts'):
        problems.append('Pilihan subjects with no "Bil. Subjek Pilihan ... Diperlukan" count')
        return None
    return groups


def _item_rule(item, named, problems, warnings, remarks):
    """One item -> (flags, groups, remaining), reading the table first. `named`: keys named before."""
    count, grade = item['count'], item['grade']
    if item.get('wide'):
        groups = _wide_item(item, problems, warnings)
        return ([], groups, []) if groups is not None else None
    title = ' '.join([item['title']] + item['lines']).strip()
    if not count or grade not in GRADES:
        problems.append(f'item without a count or grade: {title!r}')
        return None
    said_count, said_grade = _title_says(title)
    if (said_count and said_count != count) or (said_grade and said_grade != grade and grade != 'G'):
        remarks.append(f'UP_TVET: "{title}" (jadual: {count} subjek, gred {grade})')
        item['mismatch'] = True
    if item['rows'] is None and not item['exclusion']:
        problems.append(f'item lists no subjects: {title!r}')
        return None
    rows = item['rows'] or []
    if item['exclusion'] or any(len(r) > 1 and r[1].upper() == ANY_OTHER for r in rows):
        # "N more, not these" (an exclusion table), or a list holding "any subject not named above".
        exclude = list(named) if (not item['exclusion'] or 'selain' in title.lower()) else []
        for row in rows if item['exclusion'] else []:
            keys = _row_keys(row[1] if len(row) > 1 else '', problems, warnings)
            if keys is None:
                return None
            exclude += keys
        return [], [], [{'count': count, 'grade': grade, 'exclude': _once(exclude)}]
    slots = []
    for row in rows:
        keys = _row_keys(row[1] if len(row) > 1 else '', problems, warnings)
        if keys is None:
            return None
        if keys:
            slots.append(keys)
        elif count >= len(rows):
            problems.append(f'a required subject is not on the grade form: {row!r}')
            return None
    if len(slots) < count:
        problems.append(f'fewer subjects on the grade form than the count: {title!r}')
        return None
    if count == len(slots):   # every row is required
        flags = [(s[0], grade) for s in slots if len(s) == 1 and (s[0], grade) in SINGLE_SUBJECT_FLAGS]
        groups = [{'count': 1, 'grade': grade, 'subjects': s} for s in slots
                  if not (len(s) == 1 and (s[0], grade) in SINGLE_SUBJECT_FLAGS)]
        return flags, groups, []
    if all(len(s) == 1 for s in slots):
        return [], [{'count': count, 'grade': grade, 'subjects': _once(k for s in slots for k in s)}], []
    return [], [{'count': count, 'grade': grade, 'slots': slots,
                 'subjects': _once(k for s in slots for k in s)}], []


def spm_option_rule(option, problems, warnings, remarks):
    """An SPM option -> {'flags': [(key, grade)], 'block': count-once block or None} or None."""
    items = _items(option, problems)
    flags, groups, remaining, named = [], [], [], []
    mismatches = 0
    if any(item.get('wide') for item in items) and re.search(r'\d|kredit|kepujian', option['heading'], re.I):
        # The Wajib/Pilihan table's own heading states a rule in words; the TABLE wins.
        remarks.append(f"UP_TVET: \"{option['heading']}\"")
        mismatches += 1
    for item in items:
        if not item['title'] and not item['lines'] and item['rows'] is None and item['count'] is None:
            continue
        before = len(problems)
        rule = _item_rule(item, named, problems, warnings, remarks)
        if rule is None:
            if len(problems) == before:
                problems.append(f"item not read: {item['title']!r}")
            return None
        mismatches += 1 if item.get('mismatch') else 0
        flags += rule[0]
        groups += rule[1]
        remaining += rule[2]
        named += [k for k, _ in rule[0]] + [k for g in rule[1] for k in g.get('subjects', [])]
    block = None
    if groups or remaining:
        block = {'counted': [k for k, _ in flags], 'groups': groups, 'remaining': remaining}
    return {'flags': flags, 'block': block, 'mismatches': mismatches}


def _as_alternative(rule, problems):
    """An SPM option inside an ATAU -> a list of groups (flags become one-subject groups)."""
    if rule['block'] and rule['block']['remaining']:
        problems.append('"any N subjects" inside alternative SPM options (cannot be represented)')
        return None
    return [{'count': 1, 'grade': g, 'subjects': [k]} for k, g in rule['flags']] \
        + (rule['block']['groups'] if rule['block'] else [])


# --- cards -----------------------------------------------------------------------------------

def _line_actions(lines, problems):
    """Non-academic lines -> the set of actions, with the matched texts."""
    actions = []
    for line in lines:
        for pattern, action in _RULES:
            m = pattern.search(line)
            if m:
                actions.append((action, line, m))
                break
        else:
            problems.append(f'condition not recognised: {line!r}')
    return actions


def _apply_condition_card(card, out, problems):
    """A non-academic card -> flags / remarks in `out`. ATAU options: only what EVERY option needs."""
    per_option = []
    for option in card['options']:
        flags = set()
        for action, line, m in _line_actions(_option_lines(option), problems):
            if action in ('gender', 'religion'):
                problems.append(f'{action} condition (owner ruling: never a gate, never guessed): {line!r}')
            elif action in ('req_malaysian', 'req_bumiputera', 'no_colorblind', 'no_disability', 'single'):
                flags.add(action)
            elif action == 'req_interview':
                flags.add(action)
                out['remarks'].append(line.rstrip('.').lstrip('0123456789. '))
            elif action == 'age_min':
                out['age'][0] = int(m.group(1))
            elif action == 'age_max':
                out['age'][1] = int(m.group(1))
            elif action in FIXED_REMARKS:
                out['remarks'].append(FIXED_REMARKS[action])
            elif action in ('remark_disability', 'remark_text'):
                out['remarks'].append(line.rstrip('.').lstrip('0123456789. ').replace(' (Wajib)', ''))
            elif action == 'age_text':
                out['age_text'].append(re.sub(r'^\d+\.\s*', '', line))
        if 'req_bumiputera' in flags:
            flags.add('req_malaysian')   # a Bumiputera is always a citizen
        per_option.append(flags)
    if per_option:
        common = set.intersection(*per_option)
        if len(per_option) > 1 and common != set.union(*per_option):
            out['warnings'].append(f"card {card['number']} alternatives: only {sorted(common)} kept")
        out['flags'] |= common


#: Conditions a student can be refused on. In an ACADEMIC card they are read on EVERY line of every
#: option (an SVM / Tahfiz / open option too, and the text before an option's first item), because a
#: gate written inside an option is still a gate (review 2026-10-29). Gender and religion are always
#: UNPARSED; a citizenship / Bumiputera / OKU / colour-vision line is allowed only when a condition card
#: sets the same flag. A Tahfiz CERTIFICATE is a qualification route, not a religion condition: it
#: matches none of these, and a card with an SPM route is decided by the SPM route.
ACADEMIC_GATES = (
    ('gender', re.compile(r'\bLelaki\b|\bPerempuan\b|\bWanita\b|\bjantina\b', re.I)),
    ('religion', re.compile(r'beragama|agama Islam|\bMuslim', re.I)),
    ('req_bumiputera', re.compile(r'Bumiputera|Berbangsa Melayu|Orang Asli|Anak Negeri', re.I)),
    ('req_malaysian', re.compile(r'Warganegara', re.I)),
    ('no_colorblind', re.compile(r'rabun warna|buta warna', re.I)),
    ('no_disability', re.compile(r'\bOKU\b|kurang upaya|ketidakupayaan', re.I)),
)
#: A skills-certificate title (an SKM code such as [TA-010-3]) or a trade name ("Pakaian Lelaki" is
#: menswear) names a qualification, not who may apply.
_NAMES_A_TRADE = re.compile(r'\[[A-Z]{1,4}\d*-\d|Pakaian (Lelaki|Wanita)', re.I)
_QUALIFIED_DISABILITY = re.compile(r'tidak mempunyai (ketidakupayaan|kurang upaya).*(menyukarkan|amali)', re.I)


def _card_lines(card):
    lines = [card['title'], card['subtitle']]
    for option in card['options']:
        lines += _option_lines(option)
    return [line for line in lines if line]


def academic_gate_hits(card):
    """[(gate, line)] for every gate line in an academic card. The QUALIFIED disability sentence
    ("... yang menyukarkan kerja amali") is text, never a gate (owner ruling 2026-10-29)."""
    hits = []
    for line in _card_lines(card):
        if _QUALIFIED_DISABILITY.search(line) or _NAMES_A_TRADE.search(line):
            continue
        gate = next((g for g, pattern in ACADEMIC_GATES if pattern.search(line)), None)
        if gate:
            hits.append((gate, line))
    return hits


def _apply_academic_card(card, kinds, out, problems, warnings):
    out['academic_gates'] += [(card['number'], gate, line) for gate, line in academic_gate_hits(card)]
    if 'open' in kinds:
        out['open_cards'] += 1
        return
    spm = [o for o, k in zip(card['options'], kinds) if k == 'spm']
    if not spm:
        problems.append(f"card {card['number']} {card['title']!r}: no SPM route (only other qualifications)")
        return
    rules = []
    for option in spm:
        rule = spm_option_rule(option, problems, warnings, out['remarks'])
        if rule is None:
            return
        out['mismatches'] += rule['mismatches']
        rules.append(rule)
    if any(not r['flags'] and not r['block'] for r in rules):
        out['open_cards'] += 1      # "holds an SPM" with no subject rule: every SPM leaver meets it
        return
    distinct = []
    for rule in rules:
        if rule not in distinct:
            distinct.append(rule)
    if len(distinct) == 1:
        out['spm_flags'] += distinct[0]['flags']
        if distinct[0]['block']:
            out['blocks'].append(distinct[0]['block'])
        return
    alternatives = [_as_alternative(r, problems) for r in distinct]
    if None not in alternatives:
        out['blocks'].append({'counted': [], 'groups': [{'any_of': alternatives}], 'remaining': []})


def _new_fields():
    return {'source_type': 'tvet', 'merit_type': 'standard', 'merit_cutoff': None, 'min_credits': 0,
            'min_pass': 0, 'req_bumiputera': False, 'req_interview': False, 'req_malaysian': False,
            'no_colorblind': False, 'no_disability': False, 'single': False,
            'complex_requirements': None, 'subject_group_req': None, 'remarks': ''}


def _age_remark(age, texts):
    low, high = age
    if low and high:
        return f'Umur {low}-{high} tahun'
    if low:
        return f'Umur minimum {low} tahun'
    if high:
        return f'Umur maksimum {high} tahun'
    if not texts:
        return None
    return texts[0] if re.search(r'umur', texts[0], re.I) else f'Umur {texts[0]}'


def parse_requirements(page):
    """`read_page` output -> {'fields', 'unparsed', 'warnings', 'remarks', 'header_mismatches', 'open'}."""
    problems, warnings = [], []
    out = {'flags': set(), 'remarks': [], 'age': [None, None], 'age_text': [], 'spm_flags': [], 'academic_gates': [],
           'blocks': [], 'open_cards': 0, 'mismatches': 0, 'warnings': warnings}
    academic = 0
    if not page['cards']:
        problems.append('no requirement card on the page')
    for card in page['cards']:
        if card['joiner'] not in (None, 'DAN'):
            problems.append(f"card {card['number']} is joined by {card['joiner']!r}, not DAN")
        if any(o['joiner'] not in (None, 'ATAU') for o in card['options']):
            problems.append(f"card {card['number']} has options joined by something other than ATAU")
        kinds = [classify_option(o) for o in card['options']]
        if any(k is not None for k in kinds):
            academic += 1
            _apply_academic_card(card, kinds, out, problems, warnings)
        else:
            _apply_condition_card(card, out, problems)
    if page['cards'] and not academic:
        problems.append('no academic requirement card')
    for number, gate, line in out['academic_gates']:
        if gate in ('gender', 'religion') or gate not in out['flags']:
            problems.append(f'{gate} condition inside academic card {number} (not a gate this page sets '
                            f'elsewhere): {line!r}')
    fields = _new_fields()
    for flag in out['flags']:
        fields[flag] = True
    for key, grade in out['spm_flags']:
        fields[SINGLE_SUBJECT_FLAGS[(key, grade)]] = True
    if out['blocks']:
        fields['complex_requirements'] = {'count_once': out['blocks']}
    remarks = [r for r in [_age_remark(out['age'], out['age_text'])] if r] + out['remarks']
    fields['remarks'] = '. '.join(dict.fromkeys(remarks)) + ('.' if remarks else '')
    return {'fields': fields, 'unparsed': list(dict.fromkeys(problems)), 'warnings': list(dict.fromkeys(warnings)),
            'remarks': list(dict.fromkeys(remarks)), 'header_mismatches': out['mismatches'],
            'open': not out['blocks'] and not out['spm_flags']}
