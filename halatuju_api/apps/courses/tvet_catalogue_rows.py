"""UP_TVET catalogue rows + saved pages -> the human-reviewable F1 file (Bumi coverage Sprint F1).

`build_review(source, held_links, held_courses)` is PURE: everything it reads is passed in, so the
committed review file `data/tvet/tvet_new_courses_F1.json` is rebuilt byte for byte by a test from the
committed `data/tvet/uptvet_F1_source.json` (catalogue rows + `tvet_pages.read_page` structures).

Owner rulings F (2026-10-29): public (Awam) rows only; ONE course per programme with every named campus
linked. A programme is grouped by provider family + normalised name + IDENTICAL parsed rule (the
remarks text aside); campuses whose rules differ become separate courses (counted in `counts`). The
course id is `TVET-<lowest id_kursus>` of its group.

HELD courses (prod's IJTM-* / IKBN-*): a catalogue row is held when prod already links its `id_kursus`
(`held_links`, read-only SQL 2026-10-29) or, failing that, when its normalised name is EXACTLY one held
course's name within the same family. A held course NEVER changes: its clean campuses become extra
`held_links` (campus offerings only; `already_linked` when prod holds the (course, campus) PAIR, whatever
id_kursus its hyperlink carries), and every difference between the page's parsed rule and the held
row's rule goes into `held_rule_differences` for review. Rows the parser could not read
(`tvet_syarat`) go to `flagged`, with their source text, and are never written; so does a row of a held
course the fixture holds but prod does not (`not_in_prod`, from `held_tvet_links.json`).

Course fields UP_TVET does not give us are derived deterministically: `level` from the page's "Tahap
Pengajian" (Diploma / Sijil Lanjutan / Sijil), `semesters` = the "Tempoh Pengajian" months // 6,
`department` / `field_key` from the name (`FIELD_RULES`, first match; no match = flagged).

Sprint F2 (MARA, `data/tvet/tvet_new_courses_F2.json`, built for `--families mara`): colour vision no
longer splits a programme; the course HIDES from a colour-blind student when ANY campus page excludes
colour blindness (owner, 2026-10-30), and `colour_excluded_by` lists those campuses when they are not all.
F1 had no such pair, so its file is unchanged. `review_summary` is the reviewer's first page.
"""
import json
import re

from .tvet_families import F1_FAMILIES, family_of, tidy
from .tvet_institutions import campus_name, held_institution, propose_institutions
from .tvet_pages import card_text
from .tvet_syarat import parse_requirements

# (pattern over the UPPER-CASED name, department, field_key). First match wins; the order matters
# ("PEMBUATAN MAKANAN" is food, not manufacturing; "AUTOMOTIF (PEMBUATAN)" is automotive).
FIELD_RULES = (
    (r'KAPAL TERBANG|PESAWAT|PENERBANGAN|AERO', 'Aero & Marin', 'aero'),
    (r'MARIN|PERIKANAN|NAKHODA|PERKAPALAN|VESEL PENANGKAPAN|PENANGKAPAN IKAN', 'Aero & Marin', 'marin'),
    (r'MEKATRONIK|AUTOMASI', 'Mekanikal & Pembuatan', 'mekatronik'),
    (r'AUTOMOTIF|KENDERAAN|KERETA|MOTOSIKAL|JENTERA BERAT|TOLAK TANAH', 'Automotif', 'automotif'),
    (r'ROTI|PASTRI|MAKANAN|KULINARI|MASAKAN|BAKERI|KATERING|KONFEKSIONERI', 'Hospitaliti & Gaya Hidup', 'kulinari'),
    (r'SANITARI', 'Sivil & Bangunan', 'sivil'),
    (r'MINYAK|\bGAS\b|PAIP', 'Minyak & Gas', 'minyak-gas'),
    (r'KAWALAN PROSES', 'Kimia & Proses', 'kimia-proses'),
    (r'SIBER', 'ICT & Multimedia', 'it-rangkaian'),
    (r'ELEKTRIK|ELEKTRONIK|PENDAWAIAN|PENYEJUK|PENYAMANAN|TELEKOMUNIKASI|INSTRUMEN', 'Elektrik & Elektronik',
     'elektrik'),
    (r'KOMPUTER|RANGKAIAN|MULTIMEDIA|GRAFIK|TEKNOLOGI MAKLUMAT|ANIMASI|DIGITAL|PERISIAN|FOTOGRAFI', 'ICT & Multimedia',
     'multimedia'),
    (r'BINAAN|SENIBINA|TEKNOLOGI AWAM|BANGUNAN|SIVIL|PERABOT|SCAFFOLD|KAYU|UKUR', 'Sivil & Bangunan', 'sivil'),
    (r'KIMPALAN|PEMESINAN|PEMBUATAN|MEKANIKAL|POLIMER|CADD|PERKAKASAN|FABRIKASI|BOILER|REKABENTUK PRODUK|'
     r'KUALITI|PENYELENGGARAAN INDUSTRI|INDUSTRI', 'Mekanikal & Pembuatan', 'mekanikal'),
    (r'HOSPITALITI|PELANCONGAN|KAUNTER|PENYAJIAN|HOTEL|PENGEMASAN', 'Hospitaliti & Gaya Hidup', 'hospitaliti'),
    (r'KOSMETOLOGI|KECANTIKAN|RAMBUT|\bSPA\b|SOLEKAN|ANDAMAN', 'Hospitaliti & Gaya Hidup', 'kecantikan'),
    (r'FESYEN|PAKAIAN|JAHITAN|TEKSTIL|TENUN|KRAF|BATIK|SONGKET', 'Seni Reka', 'senireka'),
    (r'PERTANIAN|TANAMAN|TERNAKAN|AKUAKULTUR|AGRO|HORTIKULTUR|LADANG|LANDSKAP|HAIWAN|VETERINAR|UNGGAS|'
     r'PEMASARAN HASIL', 'Pertanian', 'pertanian'),
    (r'ASUHAN|KANAK-KANAK|PENDIDIKAN AWAL', 'Pendidikan', 'pendidikan'),
    (r'PERNIAGAAN|PERAKAUNAN|KEUSAHAWANAN|PENTADBIRAN|PEJABAT|RUNCIT', 'Perniagaan', 'perniagaan'),
    (r'SUKAN|KEJURULATIHAN|REKREASI', 'Sains Sukan', 'sains-sosial'),
    # MARA (Sprint F2): appended, so no earlier match moves (the F1 file rebuilds byte for byte).
    (r'MOTORCYCLE|\bENJIN\b|TRANSMISI|ELECTRIC VEHICLE|CUSTOM PAINTING', 'Automotif', 'automotif'),
    (r'BARISTA|BEVERAGE|BREAD|BUTCHERY|CAKE', 'Hospitaliti & Gaya Hidup', 'kulinari'),
    (r'ELECTRICAL|HVAC|TELEFON', 'Elektrik & Elektronik', 'elektrik'),
    (r'PETROLEUM|PESISIR', 'Minyak & Gas', 'minyak-gas'),
    (r'\bLOJI\b|PLASTIK|SERAMIK|KOMPOSIT|FOUNDRI|WELDING', 'Mekanikal & Pembuatan', 'mekanikal'),
    (r'HERBA', 'Sains Hayat', 'sains-hayat'),
    (r'REKABENTUK|FABRIK|UPHOLSTERI|PATCHWORK', 'Seni Reka', 'senireka'),
    (r'FILEM|PENYIARAN|PENCETAKAN', 'ICT & Multimedia', 'multimedia'),
    (r'BEKALAN AIR|PEMBETUNGAN', 'Sivil & Bangunan', 'sivil'),
    (r'ESTETIK', 'Hospitaliti & Gaya Hidup', 'kecantikan'),
    (r'FAMILY CARE', 'Pendidikan', 'pendidikan'),
)
NAME_ACRONYMS = ('DKM', 'SKM', 'DLKM', 'CNC', 'HVAC', 'CAD', 'CAM', 'CADD', 'BEV', 'EEV', 'EV', 'PW1', 'PW2',
                 'PW3', 'PW4', 'PW5', 'PW6', 'A0', 'A1', 'A4', 'B0', 'B1', 'B4', 'IT', 'ICT', 'KEMAS', 'FAMA',
                 'IOT', 'PLC', 'LPG', 'NDT', 'MIG', 'TIG', 'SMAW', 'GMAW', 'GTAW')


def norm_name(name):
    """Grouping key for a programme name: case, '#', punctuation and spacing folded."""
    return re.sub(r'[^A-Z0-9]+', ' ', (name or '').upper().replace('#', ' ')).strip()


def clean_name(raw):
    """'DIPLOMA TEKNOLOGI ELEKTRIK (PENJAGA JENTERA ELEKTRIK A1)' -> 'Diploma Teknologi Elektrik
    (Penjaga Jentera Elektrik A1)'; a mixed-case name keeps its case; the '#' marker is dropped."""
    name = tidy((raw or '').replace('#', ' '))
    if name.upper() == name:
        name = name.title()
        for word in NAME_ACRONYMS:
            name = re.sub(rf'\b{word}\b', word, name, flags=re.I)
        name = re.sub(r'\b(Dan|Dari|Atau|Untuk|Di)\b', lambda m: m.group(1).lower(), name)
    return name


def level_of(name, tahap):
    upper = (name or '').upper()
    if (tahap or '').lower().startswith('diploma') or upper.startswith('DIPLOMA'):
        return 'Diploma'
    if upper.startswith('SIJIL LANJUTAN'):
        return 'Sijil Lanjutan'
    return 'Sijil'


def semesters_of(tempoh):
    m = re.match(r'(\d+)\s*Bulan', tidy(tempoh), re.I)
    return (int(m.group(1)) // 6 or None) if m else None


def field_of(name):
    """(department, field_key) or None when no rule names the programme (the row is then flagged)."""
    upper = (name or '').upper()
    return next(((dept, key) for pattern, dept, key in FIELD_RULES if re.search(pattern, upper)), None)


def _fee(raw):
    raw = (raw or '').strip()
    if not raw:
        return ''
    return 'Percuma' if raw == '0' else f'RM {int(raw):,}'


#: Fields that never split a programme: the remarks (text), and colour vision, which HIDES the course
#: when ANY campus page excludes colour blindness (owner, 2026-10-30, F1b; applied to new courses in F2).
_NOT_IN_RULE_KEY = ('remarks', 'no_colorblind')


def _rule_key(fields):
    return json.dumps({k: v for k, v in fields.items() if k not in _NOT_IN_RULE_KEY}, sort_keys=True)


def _offering(row, institution_id, campus):
    return {'id_kursus': row['id_kursus'], 'institution_id': institution_id, 'campus': campus,
            'kod_tauliah': row.get('kod_tauliah', ''), 'hyperlink': row['info_url'],
            'tuition_fee_semester': _fee(row.get('tuition_fee')), 'registration_fee': _fee(row.get('reg_fee'))}


def _source(page):
    return [card_text(c) for c in page['cards']]


def _held_by_name(held_courses):
    by_name = {}
    for cid, held in held_courses.items():
        family = 'iljtm' if cid.startswith('IJTM') else 'ilkbs' if cid.startswith('IKBN') else None
        by_name.setdefault((family, norm_name(held['course'])), []).append(cid)
    return by_name


def _rule_differences(parsed, held):
    keys = sorted(set(parsed) | set(held))
    return {k: {'page': parsed.get(k), 'held': held.get(k)} for k in keys
            if k not in ('remarks', 'source_type', 'merit_type', 'merit_cutoff', 'subject_group_req',
                         'max_aggregate_units')
            and (parsed.get(k) or None) != (held.get(k) or None)}


def _read_rows(source, families):
    """Every in-scope catalogue row with its family, campus, page, programme name and parse. The
    name is the page's own title (the catalogue's heading carries a campus code in front of it)."""
    out = []
    for kid in sorted(source['catalogue'], key=int):
        row = source['catalogue'][kid]
        family = family_of(row['institution'])
        if family not in families or (row.get('sektor') or '').lower() != 'awam':
            continue
        page = source['pages'][kid]
        out.append({'row': row, 'family': family, 'campus': campus_name(row['institution']), 'page': page,
                    'name': tidy(page.get('name')) or tidy(row['name']), 'parsed': parse_requirements(page)})
    return out


def _held_id(item, held_links, by_name):
    """(held course id, 'id_kursus' | 'name') or (None, None)."""
    if item['row']['id_kursus'] in held_links:
        return held_links[item['row']['id_kursus']][0], 'id_kursus'
    names = by_name.get((item['family'], norm_name(item['name'])), [])
    if len(names) > 1:
        return None, 'ambiguous:' + ','.join(sorted(names))
    return (names[0], 'name') if names else (None, None)


def _reasons(item, held_id, not_in_prod=frozenset()):
    reasons = list(item['parsed']['unparsed'])
    if held_id in not_in_prod:
        reasons.append(f'held course {held_id} is only in the fixture, not in prod: no link until the '
                       'fixture drift is reconciled')
    if (item['matched_by'] or '').startswith('ambiguous:'):
        reasons.append(f"the name matches more than one held course ({item['matched_by'][10:]}): "
                       'which one it is needs a person')
    if not held_id and field_of(item['name']) is None:
        reasons.append(f"field_key: no FIELD_RULES pattern names {item['name']!r}")
    return reasons


def build_review(source, held_links, held_courses, families=F1_FAMILIES, not_in_prod=frozenset()):
    """See the module doc. `held_links`: {id_kursus: (course_id, institution_id)} from prod;
    `held_courses`: {course_id: {'course': name, 'requirement': {field: value}}}."""
    items = _read_rows(source, families)
    # Every (course, campus) pair prod already holds: a link is ALREADY THERE when prod has the pair, even
    # when prod's hyperlink carries an older id_kursus (review 2026-10-29: 22 such pairs).
    prod_pairs = set(held_links.values())
    by_name = _held_by_name(held_courses)
    for item in items:
        item['held_id'], item['matched_by'] = _held_id(item, held_links, by_name)
        item['reasons'] = _reasons(item, item['held_id'], not_in_prod)
    # Only a campus that gets a clean row is proposed, so the ids carry no gaps.
    unknown = {(i['family'], i['campus']): i['page'] for i in items
               if not i['reasons'] and held_institution(i['family'], i['campus']) is None}
    new_ids, proposals = propose_institutions(unknown)
    groups, flagged, links, differences = {}, [], [], []
    counts = {'header_mismatches': 0, 'remark_variants': 0}
    for item in items:
        row, family, parsed, held_id = item['row'], item['family'], item['parsed'], item['held_id']
        counts['header_mismatches'] += parsed['header_mismatches']
        if item['reasons']:
            flagged.append({'id_kursus': row['id_kursus'], 'name': item['name'], 'family': family,
                            'campus': item['campus'], 'held_course': held_id, 'reasons': item['reasons'],
                            'source': _source(item['page'])})
            continue
        inst = item['institution_id'] = held_institution(family, item['campus']) or new_ids[(family, item['campus'])]
        if held_id:
            links.append({**_offering(row, inst, item['campus']), 'course_id': held_id,
                          'matched_by': item['matched_by'],
                          'already_linked': item['matched_by'] == 'id_kursus' or (held_id, inst) in prod_pairs})
            diff = _rule_differences(parsed['fields'], held_courses.get(held_id, {}).get('requirement', {}))
            if diff:
                differences.append({'course_id': held_id, 'id_kursus': row['id_kursus'], 'campus': item['campus'],
                                    'differences': diff, 'remarks': parsed['fields']['remarks']})
        else:
            groups.setdefault((family, norm_name(item['name']), _rule_key(parsed['fields'])), []).append(item)
    courses = [_course(members) for members in groups.values()]
    for course in courses:
        counts['remark_variants'] += 1 if course.get('remark_variants') else 0
    names = [norm_name(c['course']) for c in courses]
    counts.update({
        'rows': len(items), 'flagged_rows': len(flagged), 'new_courses': len(courses),
        'new_offerings': sum(len(c['offerings']) for c in courses), 'held_links': len(links),
        'held_links_new': sum(1 for x in links if not x['already_linked']),
        'held_rule_differences': len(differences), 'split_by_rule': len(names) - len(set(names)),
        'open_courses': sum(1 for c in courses if not c['requirement']['complex_requirements']
                            and not any(c['requirement'].get(f) for f in ('pass_bm', 'pass_history', 'credit_english'))),
        'new_institutions': len(proposals),
    })
    return {'built_from': 'data/tvet/uptvet_F1_source.json', 'families': list(families),
            'parser': 'apps/courses/tvet_syarat.py (pages: tvet_pages.py; count-once: spm_count_once.py)',
            'counts': counts,
            'new_institutions': proposals,
            'courses': sorted(courses, key=lambda c: int(c['course_id'].split('-')[1])),
            'held_links': links, 'held_rule_differences': differences, 'flagged': flagged}


def _coarse(reason):
    """A flagged reason without its quoted text or card number: "card N '...': no SPM route ..."."""
    return re.sub(r'\bcard \d+', 'card N', re.sub(r"""'[^']*'(?=[:\s]|$)|"[^"]*"(?=[:\s]|$)""", "'...'", reason))


def review_summary(review):
    """What a reviewer reads first (Sprint F2): Bumi-only vs open courses, who else they are open to, the
    programmes split by a rule difference (with the fields that differ), and the flagged rows by reason.
    Kept beside `build_review` (not inside it) so the applied F1 file still rebuilds byte for byte."""
    courses = review['courses']
    by_name = {}
    for course in courses:
        by_name.setdefault((course['family'], norm_name(course['course'])), []).append(course)
    splits = []
    for (_, _), group in sorted(by_name.items()):
        if len(group) < 2:
            continue
        reqs = [c['requirement'] for c in group]
        differ = sorted(k for k in reqs[0] if k != 'remarks' and len({json.dumps(r.get(k), sort_keys=True)
                                                                      for r in reqs}) > 1)
        splits.append({'course': group[0]['course'], 'differ': differ,
                       'courses': {c['course_id']: len(c['offerings']) for c in group}})
    reasons = {}
    for row in review['flagged']:
        for reason in row['reasons']:
            reasons[_coarse(reason)] = reasons.get(_coarse(reason), 0) + 1
    return {
        'bumi_only_courses': sum(1 for c in courses if c['requirement']['req_bumiputera']),
        'open_to_non_bumi_courses': sum(1 for c in courses if not c['requirement']['req_bumiputera']),
        'open_to_non_citizens_courses': sum(1 for c in courses if not c['requirement']['req_malaysian']),
        'no_disability_courses': sum(1 for c in courses if c['requirement']['no_disability']),
        'no_colorblind_courses': sum(1 for c in courses if c['requirement']['no_colorblind']),
        'colour_from_some_campuses': sum(1 for c in courses if c.get('colour_excluded_by')),
        'split_programmes': splits,
        'flagged_by_reason': dict(sorted(reasons.items(), key=lambda kv: (-kv[1], kv[0]))),
    }


def _course(members):
    members = sorted(members, key=lambda m: int(m['row']['id_kursus']))
    first = members[0]
    name = clean_name(first['name'])
    department, field_key = field_of(first['name'])
    remarks = {m['parsed']['fields']['remarks'] for m in members}
    colour = [m['row']['id_kursus'] for m in members if m['parsed']['fields']['no_colorblind']]
    course = {
        'course_id': f"TVET-{first['row']['id_kursus']}", 'course': name,
        'level': level_of(first['name'], first['page'].get('tahap')), 'department': department,
        'field': department, 'field_key': field_key, 'semesters': semesters_of(first['page'].get('tempoh')),
        'description': first['page'].get('description', ''), 'family': first['family'],
        'requirement': {**first['parsed']['fields'], 'no_colorblind': bool(colour)},
        'offerings': [_offering(m['row'], m['institution_id'], m['campus']) for m in members],
        'source': _source(first['page']),
        'warnings': first['parsed']['warnings'],
    }
    if len(remarks) > 1:
        course['remark_variants'] = {m['row']['id_kursus']: m['parsed']['fields']['remarks'] for m in members}
    if colour and len(colour) < len(members):
        course['colour_excluded_by'] = colour   # the campus pages that hide it from a colour-blind student
    return course
