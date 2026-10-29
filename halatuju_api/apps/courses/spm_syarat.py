"""MOHE SPM Syarat Am + Syarat Khas text -> `CourseRequirement` fields (Bumi coverage Sprint D1).

Input: the two texts `scrape_mohe_stpm --with-syarat --with-syarat-am` writes (e.g.
`data/spm/mohe_bumi_2026-10-29.csv`). Output: `parse_requirements(am, khas)` returns
`{'fields': {...}, 'unparsed': [...], 'warnings': [...]}`. A row with ANY `unparsed` reason is NOT
faithful and must not be ingested as it stands (`ingest_spm_courses` refuses it): this parser never
guesses. The shapes it reads, and how each lands:

  Syarat Am  "Warganegara Malaysia ..."                        -> req_malaysian
             "Gred C/E bagi matapelajaran BAHASA MELAYU|SEJARAH" -> the flag (credit_bm / pass_history ...)
             "N (n) C dalam mana-mana matapelajaran yang belum dikira"
                                                                -> a count-once block of its own
  Syarat Khas "Gred G dalam mata pelajaran X."                 -> the exact flag when one exists
                                                                   (credit_english, distinction_eng ...),
                                                                   else a one-subject group
             "Gred G dalam N (n) mata pelajaran berikut : • a / b • c"
                                                                -> an `or_groups` group; bullets are
                                                                   slots, so a list whose bullets hold
                                                                   alternatives becomes a slotted group
             "Gred G dalam mana-mana N (n) mata pelajaran yang belum diambil kira | yang belum dikira |
              selain di atas [tidak termasuk mata pelajaran berikut : • x]"
                                                                -> `count_once` remaining entry
             "Gred C dalam mana-mana N (n) mata pelajaran"     -> min_credits (E -> min_pass)
             "Lulus ujian dan / atau temu duga"                 -> req_interview
             "Berketurunan Melayu, Anak Negeri ... sahaja"      -> req_bumiputera
             "ATAU", "Gred A- dalam SATU (1) mata pelajaran DAN Gred B dalam TIGA (3) ..."
                                                                -> UNPARSED (alternatives; D2 hand entry)

Count-once semantics and the JSON shape: `spm_count_once.py`. Legacy `or_groups` keep their own
semantics (each group counted on its own); only a row with a "not yet counted" clause or a slotted
list gets a count-once block. Subject names map through `spm_subject_names` -> `stpm_engine.SPM_CODE_MAP`;
an unknown name is UNPARSED, never dropped.
"""
import re

from .spm_subject_names import SPM_NAME_TO_CODE
from .stpm_engine import SPM_CODE_ALSO, SPM_CODE_MAP

_NAME_LOOKUP = {name.lower(): code for name, code in SPM_NAME_TO_CODE.items()}
NUMBER_WORDS = {'SATU': 1, 'DUA': 2, 'TIGA': 3, 'EMPAT': 4, 'LIMA': 5, 'ENAM': 6, 'TUJUH': 7,
                'LAPAN': 8, 'SEMBILAN': 9, 'SEPULUH': 10}
GRADES = ('A+', 'A', 'A-', 'B+', 'B', 'C+', 'C', 'D', 'E')

# The exact single-subject flags the engine already has (`engine.check_eligibility`). Anything not
# here (e.g. "C in Matematik": `credit_math` means Math OR Add Math) becomes a one-subject group.
SINGLE_SUBJECT_FLAGS = {
    ('bm', 'E'): 'pass_bm', ('bm', 'C'): 'credit_bm', ('bm', 'B'): 'credit_bm_b',
    ('bm', 'A-'): 'distinction_bm',
    ('eng', 'E'): 'pass_eng', ('eng', 'C'): 'credit_english', ('eng', 'B'): 'credit_eng_b',
    ('eng', 'A-'): 'distinction_eng',
    ('math', 'E'): 'pass_math', ('math', 'B'): 'credit_math_b', ('math', 'A-'): 'distinction_math',
    ('addmath', 'C'): 'credit_addmath', ('addmath', 'B'): 'credit_addmath_b',
    ('addmath', 'A-'): 'distinction_addmath',
    ('hist', 'E'): 'pass_history',
    ('sci', 'E'): 'pass_sci', ('sci', 'C'): 'credit_sci', ('sci', 'A-'): 'distinction_sci',
    ('phy', 'A-'): 'distinction_phy', ('chem', 'A-'): 'distinction_chem', ('bio', 'A-'): 'distinction_bio',
    ('islam', 'E'): 'pass_islam', ('islam', 'C'): 'credit_islam',
    ('moral', 'E'): 'pass_moral', ('moral', 'C'): 'credit_moral',
}

_GRADE = r'(A\+|A-|A|B\+|B|C\+|C|D|E)'
_COUNT = r'(SATU|DUA|TIGA|EMPAT|LIMA|ENAM|TUJUH|LAPAN|SEMBILAN|SEPULUH) \((\d+)\)'
_PREFIX = r'Mendapat sekurang-kurangnya Gred ' + _GRADE + r' dalam '
_SINGLE_RE = re.compile(_PREFIX + r'mata pelajaran (.+?)\.?$')
_LIST_RE = re.compile(_PREFIX + _COUNT + r' mata pelajaran berikut :(.*)$')
_REMAINING_RE = re.compile(
    _PREFIX + r'mana-mana ' + _COUNT + r' mata pelajaran(?: lain)? '
    r'(?:yang belum diambil kira|yang belum dikira|selain di ?atas)'
    r'(?: tidak termasuk mata pelajaran berikut :(.*))?\.?$')
_ANY_RE = re.compile(_PREFIX + r'mana-mana ' + _COUNT + r' mata pelajaran\.?$')
_SPLIT_RE = re.compile(r'(?=Mendapat sekurang-kurangnya|Lulus ujian|Berketurunan Melayu|\bATAU\b)')
_INTERVIEW_RE = re.compile(r'^Lulus ujian dan / atau temu duga', re.I)
_BUMI_RE = re.compile(r'^Berketurunan Melayu, Anak Negeri Sabah, Anak Negeri Sarawak dan Orang Asli sahaja\.?$')
_AM_SUBJECT_RE = re.compile(r'Gred ' + _GRADE + r' bagi matapelajaran (BAHASA MELAYU|SEJARAH)')
_AM_REMAINING_RE = re.compile(_COUNT + r' ' + _GRADE + r' dalam mana-mana matapelajaran yang belum dikira')
_AM_SPM_RE = re.compile(r'Memiliki Sijil Pelajaran Malaysia \(SPM\) dengan mendapat sekurang-kurangnya')


def _tidy(text):
    text = re.sub(r'\s+', ' ', text or '').strip()
    return text.replace('mata pelajaran. mata pelajaran', 'mata pelajaran')  # a MOHE typo (UE4581004)


def _count(word, digits, problems, clause):
    if NUMBER_WORDS.get(word) != int(digits):
        problems.append(f'count word and digits disagree: {clause!r}')
    return int(digits)


def subject_keys(name):
    """A display name -> its engine keys (usually one; Al-lughah also `lughah_arabiah`), or None
    when the name is unknown. [] when the name is known but no grade-form key exists for it."""
    code = _NAME_LOOKUP.get(re.sub(r'\s+', ' ', name).strip().lower())
    if code is None:
        return None
    if code not in SPM_CODE_MAP:
        return []
    keys = [SPM_CODE_MAP[code]]
    if code in SPM_CODE_ALSO:
        keys.append(SPM_CODE_ALSO[code])
    return keys


def _bullets(text, problems, warnings):
    """'• a / b • c' -> [[keys of a + b], [keys of c]]; an unknown name is a problem."""
    slots = []
    for bullet in (b.strip() for b in (text or '').split('•')):
        if not bullet:
            continue
        keys = []
        for name in (n.strip() for n in bullet.split(' / ')):
            found = subject_keys(name)
            if found is None:
                problems.append(f'unknown subject name: {name!r}')
            elif not found:
                warnings.append(f'no grade-form key, dropped from its list: {name!r}')
            keys += [k for k in found or [] if k not in keys]
        if keys:
            slots.append(keys)
    return slots


def _once(keys):
    """Each engine key once, in order: Sains Pertanian and Pertanian are ONE subject (owner ruling:
    a subject counts once per group)."""
    return list(dict.fromkeys(keys))


def _list_groups(count, grade, slots):
    """A bullet list -> (legacy groups, slotted group or None). Bullets are slots."""
    if len(slots) == 1 or all(len(s) == 1 for s in slots):
        return [{'count': count, 'grade': grade, 'subjects': _once(k for s in slots for k in s)}], None
    if count == len(slots):  # one from each bullet: plain one-subject-of groups say it exactly
        return [{'count': 1, 'grade': grade, 'subjects': s} for s in slots], None
    return [], {'count': count, 'grade': grade, 'slots': slots,
                'subjects': _once(k for s in slots for k in s)}


def _parse_am(am, fields, problems):
    """Syarat Am -> flags + its own count-once block (or None)."""
    am = _tidy(am)
    if not am:
        problems.append('Syarat Am is empty')
        return None
    if 'Warganegara Malaysia' in am:
        fields['req_malaysian'] = True
    if not _AM_SPM_RE.search(am):
        problems.append(f'Syarat Am shape not recognised: {am!r}')
        return None
    counted, groups = [], []
    for grade, subject in _AM_SUBJECT_RE.findall(am):
        key = 'bm' if subject == 'BAHASA MELAYU' else 'hist'
        flag = SINGLE_SUBJECT_FLAGS.get((key, grade))
        if flag:
            fields[flag] = True
            counted.append(key)
        else:
            groups.append({'count': 1, 'grade': grade, 'subjects': [key]})
    remaining = [{'count': _count(w, d, problems, am), 'grade': g, 'exclude': []}
                 for w, d, g in _AM_REMAINING_RE.findall(am)]
    if len(counted) + len(groups) != 2 or len(remaining) != 1:
        problems.append(f'Syarat Am shape not recognised: {am!r}')
        return None
    return {'counted': counted, 'groups': groups, 'remaining': remaining}


def _new_fields():
    return {'source_type': 'ua', 'merit_type': 'standard', 'min_credits': 0, 'min_pass': 0,
            'req_bumiputera': False, 'req_interview': False, 'req_malaysian': False,
            'complex_requirements': None, 'subject_group_req': None, 'remarks': ''}


def parse_requirements(syarat_am, syarat_khas):
    """Both texts -> {'fields', 'unparsed', 'warnings'} (see the module doc). Pure."""
    fields, problems, warnings = _new_fields(), [], []
    blocks = []
    am_block = _parse_am(syarat_am, fields, problems)
    # STRICT (owner ruling 2026-10-29): "yang belum diambil kira / selain di atas" = a subject NOT
    # LISTED above — the Syarat Am's subjects and every subject a Khas clause before it names, used or
    # not (Add Maths beside Maths cannot be "another subject").
    listed = []
    if am_block:
        blocks.append(am_block)
        listed += am_block['counted'] + [k for g in am_block['groups'] for k in g['subjects']]

    khas = _tidy(syarat_khas)
    flag_keys, single_groups, list_groups, slotted, remaining = [], [], [], [], []
    for clause in (c.strip() for c in _SPLIT_RE.split(khas)):
        if not clause:
            continue
        if clause.startswith('ATAU'):
            problems.append('ATAU: alternative requirement sets (hand entry, D2)')
            continue
        if _INTERVIEW_RE.search(clause):
            fields['req_interview'] = True
            continue
        if _BUMI_RE.search(clause):
            fields['req_bumiputera'] = True
            continue
        if ' DAN Gred ' in clause:
            problems.append(f'two grades over one list (hand entry, D2): {clause!r}')
            continue
        m = _REMAINING_RE.match(clause)
        if m:
            grade, word, digits, excluded = m.groups()
            exclude = _once(listed + [k for s in _bullets(excluded, problems, warnings) for k in s])
            remaining.append({'count': _count(word, digits, problems, clause), 'grade': grade,
                              'exclude': exclude})
            continue
        m = _ANY_RE.match(clause)
        if m:
            grade, word, digits = m.groups()
            n = _count(word, digits, problems, clause)
            if grade == 'C':
                fields['min_credits'] = max(fields['min_credits'], n)
            elif grade == 'E':
                fields['min_pass'] = max(fields['min_pass'], n)
            else:
                problems.append(f'any-N at a grade with no flag: {clause!r}')
            continue
        m = _LIST_RE.match(clause)
        if m:
            grade, word, digits, body = m.groups()
            slots = _bullets(body, problems, warnings)
            if not slots:
                problems.append(f'empty subject list: {clause!r}')
                continue
            groups, slotted_group = _list_groups(_count(word, digits, problems, clause), grade, slots)
            listed += [k for s in slots for k in s]
            list_groups += groups
            if slotted_group:
                slotted.append(slotted_group)
            continue
        m = _SINGLE_RE.match(clause)
        if m:
            grade, name = m.groups()
            keys = subject_keys(name)
            if not keys:
                problems.append(f'unknown or off-form required subject: {name!r}')
                continue
            listed += keys
            flag = SINGLE_SUBJECT_FLAGS.get((keys[0], grade))
            if flag and len(keys) == 1:
                fields[flag] = True
                flag_keys.append(keys[0])
            else:
                single_groups.append({'count': 1, 'grade': grade, 'subjects': keys})
            continue
        problems.append(f'clause not recognised: {clause!r}')

    or_groups = single_groups + list_groups
    if remaining:
        # "Not yet counted" reads against everything the Syarat Khas named: ONE block holds it all.
        blocks.append({'counted': flag_keys, 'groups': or_groups + slotted, 'remaining': remaining})
        or_groups = []
    else:
        blocks += [{'counted': [], 'groups': [g], 'remaining': []} for g in slotted]
    complex_req = {}
    if or_groups:
        complex_req['or_groups'] = or_groups
    if blocks:
        complex_req['count_once'] = blocks
    fields['complex_requirements'] = complex_req or None
    return {'fields': fields, 'unparsed': problems, 'warnings': warnings}
