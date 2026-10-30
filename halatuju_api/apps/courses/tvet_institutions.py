"""UP_TVET campuses -> HalaTuju `Institution` rows (Bumi coverage Sprint F1).

`HELD` is prod's TVET institutes as read-only SQL showed them on 2026-10-29 (id -> name, subcategory,
state); a catalogue campus that names one of them links to it and is NEVER rewritten. Any other public
campus is PROPOSED (`propose_institutions`) and created only by `ingest_tvet_courses
--create-institutions` (dry run first), never silently. Id scheme (decisions.md 2026-10-29):

  * ILJTM -> the next IJTM-NNN, ILKBS -> the next IKBN-NNN (prod's own scheme; category ILJTM / ILKBS);
  * every other public body -> ILKA-NNN (type ILKA like every TVET institute; category 'TVET', which
    `apps.py` maps to the "Other skills training" pathway); subcategory = the provider family;
  * MARA (Sprint F2) -> MARA-NNN, category 'MARA'.

State spellings follow prod ("Negeri Sembilan", "Pulau Pinang", "WP Kuala Lumpur", "WP Labuan").
"""
import re

from .tvet_families import FAMILY_INSTITUTION, tidy

# id -> (name, subcategory, state); category is ILJTM for IJTM-*, ILKBS for IKBN-*.
HELD = {
    'IJTM-001': ('Institut Teknikal Jepun Malaysia', 'JMTI', 'Pulau Pinang'),
    'IJTM-002': ('ADTEC JTM Kampus Kuala Lumpur', 'ILP', 'WP Kuala Lumpur'),
    'IJTM-003': ('ADTEC JTM Kampus Ipoh', 'ILP', 'Perak'),
    'IJTM-004': ('ADTEC JTM Kampus Taiping', 'ADTEC', 'Perak'),
    'IJTM-005': ('ADTEC JTM Kampus Serian', 'ILP', 'Sarawak'),
    'IJTM-006': ('ADTEC JTM Kampus Jerantut', 'ADTEC', 'Pahang'),
    'IJTM-007': ('ADTEC JTM Kampus Kuala Langat', 'ILP', 'Selangor'),
    'IJTM-008': ('ADTEC JTM Kampus Perai', 'ILP', 'Pulau Pinang'),
    'IJTM-009': ('ADTEC JTM Kampus Kepala Batas', 'ILP', 'Pulau Pinang'),
    'IJTM-010': ('ADTEC JTM Kampus Selandar', 'ILP', 'Melaka'),
    'IJTM-011': ('ADTEC JTM Kampus Mersing', 'ILP', 'Johor'),
    'IJTM-012': ('ADTEC JTM Kampus Kota Samarahan', 'ILP', 'Sarawak'),
    'IJTM-013': ('ADTEC JTM Kampus Kota Kinabalu', 'ILP', 'Sabah'),
    'IJTM-014': ('ADTEC JTM Kampus Sandakan', 'ILP', 'Sabah'),
    'IJTM-015': ('ADTEC JTM Kampus Marang', 'ILP', 'Terengganu'),
    'IJTM-016': ('ADTEC JTM Kampus Nibong Tebal', 'ILP', 'Pulau Pinang'),
    'IJTM-017': ('ADTEC JTM Kampus Kangar', 'ILP', 'Perlis'),
    'IJTM-018': ('ADTEC JTM Kampus Bukit Katil', 'ILP', 'Melaka'),
    'IJTM-019': ('ADTEC JTM Kampus Pedas', 'ILP', 'Negeri Sembilan'),
    'IJTM-020': ('ADTEC JTM Kampus Tangkak', 'ILP', 'Johor'),
    'IJTM-021': ('ADTEC JTM Kampus Pasir Gudang', 'ILP', 'Johor'),
    'IJTM-022': ('ADTEC JTM Kampus Senai', 'ILP', 'Johor'),
    'IJTM-023': ('ADTEC JTM Kampus Miri', 'ILP', 'Sarawak'),
    'IJTM-024': ('ADTEC JTM Kampus Labuan', 'ILP', 'WP Labuan'),
    'IJTM-025': ('ADTEC JTM Kampus Bintulu', 'ADTEC', 'Sarawak'),
    'IJTM-026': ('ADTEC JTM Kampus Shah Alam', 'ADTEC', 'Selangor'),
    'IJTM-027': ('ADTEC JTM Kampus Kulim', 'ADTEC', 'Kedah'),
    'IJTM-028': ('ADTEC JTM Kampus Jitra', 'ILP', 'Kedah'),
    'IJTM-029': ('ADTEC Melaka', 'ADTEC', 'Melaka'),
    'IJTM-030': ('ADTEC JTM Kampus Batu Pahat', 'ADTEC', 'Johor'),
    'IJTM-031': ('ADTEC JTM Kampus Kemaman', 'ADTEC', 'Terengganu'),
    'IJTM-032': ('ADTEC JTM Kampus Kuantan', 'ILP', 'Pahang'),
    'IJTM-033': ('ADTEC JTM Kampus Kuala Terengganu', 'ILP', 'Terengganu'),
    'IJTM-034': ('ADTEC JTM Kampus Kota Bharu', 'ILP', 'Kelantan'),
    'IKBN-001': ('IKTBN Dusun Tua', 'IKTBN', 'Selangor'),
    'IKBN-002': ('IKTBN Sepang', 'IKTBN', 'Selangor'),
    'IKBN-003': ('IKTBN Chembong', 'IKTBN', 'Negeri Sembilan'),
    'IKBN-004': ('IKTBN Bukit Mertajam', 'IKTBN', 'Pulau Pinang'),
    'IKBN-005': ('IKTBN Alor Gajah', 'IKTBN', 'Melaka'),
    'IKBN-006': ('IKTBN Negara Pagoh', 'IKTBN', 'Johor'),
    'IKBN-007': ('IKTBN Temerloh', 'IKTBN', 'Pahang'),
    'IKBN-008': ('IKTBN Bachok', 'IKTBN', 'Kelantan'),
    'IKBN-009': ('IKSN Kuala Langat', 'IKSN', 'Selangor'),
    'IKBN-010': ('IKBN Peretak', 'IKBN', 'Selangor'),
    'IKBN-011': ('IKBN Seri Iskandar', 'IKBN', 'Perak'),
    'IKBN-012': ('IKBN Naka', 'IKBN', 'Kedah'),
    'IKBN-013': ('IKBN Jitra', 'IKBN', 'Kedah'),
    'IKBN-014': ('IKBN Kuala Perlis', 'IKBN', 'Perlis'),
    'IKBN-015': ('IKBN Tanah Merah', 'IKBN', 'Kelantan'),
    'IKBN-016': ('IKBN Wakaf Tapai', 'IKBN', 'Terengganu'),
    'IKBN-017': ('IKBN Kemasik', 'IKBN', 'Terengganu'),
    'IKBN-018': ('IKBN Pekan', 'IKBN', 'Pahang'),
    'IKBN-019': ('IKBN Bandar Penawar', 'IKBN', 'Johor'),
    'IKBN-020': ('IKBN Kinarut', 'IKBN', 'Sabah'),
    'IKBN-021': ('IKBN Miri', 'IKBN', 'Sarawak'),
}

#: Catalogue campus names whose place word is not the prod name's (reviewed by hand).
SPECIAL = {
    'INSTITUT TEKNIKAL JEPUN MALAYSIA (JMTI)': 'IJTM-001',
    'PROTON INSTITUTE (ADTEC MELAKA)': 'IJTM-029',
    'INSTITUT KEMAHIRAN SUKAN NEGARA': 'IKBN-009',
}
ACRONYMS = ('ADTEC', 'JTM', 'ILP', 'JMTI', 'IKBN', 'IKTBN', 'IKSN', 'AKBG', 'KEMAS', 'FAMA', 'ILFKB', 'MARA',
            'PERDA', 'TECH', 'KKTM', 'IKM', 'MJII', 'GIATMARA', 'TVETMARA', 'MCI')


def _key(name):
    return re.sub(r'[^A-Z0-9]+', ' ', (name or '').upper()).strip()


def _place_index():
    index = {}
    for iid, (name, _, _) in HELD.items():
        m = re.match(r'ADTEC JTM Kampus (.+)$', name)
        if m:
            index[('iljtm', _key(m.group(1)))] = iid
        m = re.match(r'(IKTBN|IKBN) (?:Negara )?(.+)$', name)
        if m:
            index[('ilkbs', m.group(1) + ' ' + _key(m.group(2)))] = iid
    return index


_INDEX = _place_index()


def campus_name(catalogue_institution):
    """'ADTEC JTM KAMPUS PEDAS (ILP PEDAS), NEGERI SEMBILAN' -> 'ADTEC JTM KAMPUS PEDAS (ILP PEDAS)'."""
    text = tidy(catalogue_institution)
    return text.rsplit(',', 1)[0].strip() if ',' in text else text


def held_institution(family, campus):
    """The prod institution a catalogue campus names, or None (a new campus)."""
    campus = tidy(campus).upper()
    if campus in SPECIAL:
        return SPECIAL[campus]
    if family == 'iljtm':
        m = re.match(r'ADTEC JTM KAMPUS (.+?) \(', campus)
        return _INDEX.get(('iljtm', _key(m.group(1)))) if m else None
    if family == 'ilkbs':
        m = re.match(r'INSTITUT KEMAHIRAN (TINGGI )?BELIA NEGARA (.+)$', campus)
        if m:
            return _INDEX.get(('ilkbs', ('IKTBN ' if m.group(1) else 'IKBN ') + _key(m.group(2))))
    return None


def display_name(campus):
    """'AKADEMI KEMAHIRAN KEMAS GOPENG' -> 'Akademi Kemahiran KEMAS Gopeng'."""
    words = tidy(campus).title().split(' ')
    fixed = []
    for word in words:
        bare = re.sub(r'[^A-Za-z]', '', word).upper()
        fixed.append(word.upper() if bare in ACRONYMS else word)
    return ' '.join(fixed)


#: The MARA pages' "W.PERSEKUTUAN (KL)" spelling -> prod's (Sprint F2).
_WP = {'KL': 'WP Kuala Lumpur', 'KUALA LUMPUR': 'WP Kuala Lumpur', 'LABUAN': 'WP Labuan',
       'PUTRAJAYA': 'WP Putrajaya'}


def state_name(negeri):
    """Page 'Negeri' -> prod's spelling."""
    m = re.match(r'^W\.?\s*PERSEKUTUAN\s*\((.+)\)$', tidy(negeri).upper())
    if m and m.group(1).strip() in _WP:
        return _WP[m.group(1).strip()]
    text = tidy(negeri).title()
    text = re.sub(r'^Wilayah Persekutuan\s+', 'WP ', text)
    return text


#: MARA campus kinds (Sprint F2): (pattern over the catalogue campus, subcategory). The catalogue prints
#: "TVETMARA SIK (INSTITUT KEMAHIRAN MARA SIK)" or "GIATMARA MUAR"; the bracket is the official name.
MARA_KINDS = (
    (r'KOLEJ KEMAHIRAN TINGGI MARA', 'KKTM'),
    (r'INSTITUT KEMAHIRAN MARA', 'IKM'),
    (r'JAPAN INDUSTRIAL INSTITUTE|\bMJII\b', 'MJII'),
    (r'GIATMARA', 'GIATMARA'),
)


def mara_kind(campus):
    """'TVETMARA SIK (INSTITUT KEMAHIRAN MARA SIK)' -> 'IKM'; an unknown MARA body -> 'MARA'."""
    upper = tidy(campus).upper()
    return next((kind for pattern, kind in MARA_KINDS if re.search(pattern, upper)), 'MARA')


def _mara_spec(campus, page):
    """(name, acronym, url) of a MARA campus: the official name in the bracket when the catalogue gives
    one ("Institut Kemahiran MARA Sik"), else the campus ("GIATMARA Muar"); the acronym is its kind."""
    m = re.search(r'\((.+)\)\s*$', tidy(campus))
    name = display_name(m.group(1) if m else campus)
    website = re.split(r'\s+,\s+', tidy(page.get('website', '')))[0]
    if re.search(r'giatmara', website, re.I) and not re.match(r'^(https?://)?(www\.)?giatmara\.edu\.my/?$', website,
                                                              re.I):
        website = 'www.giatmara.edu.my'   # "www,giatmara,edu,my" and other misprints of the one site
    return name, mara_kind(campus), _url(website)


def propose_institutions(campuses):
    """{(family, campus): page} for campuses `held_institution` does not know -> {id: Institution spec}.
    Ids are allotted in sorted (family, campus) order after the highest held id of the prefix."""
    taken = set(HELD)
    proposals, ids = {}, {}
    for (family, campus), page in sorted(campuses.items()):
        category, subcategory, prefix, _ = FAMILY_INSTITUTION[family]
        if family == 'ilkbs' and 'SUKAN' in campus.upper():
            subcategory = 'IKSN'
        n = 1
        while f'{prefix}-{n:03d}' in taken:
            n += 1
        iid = f'{prefix}-{n:03d}'
        taken.add(iid)
        ids[(family, campus)] = iid
        name, acronym, url = display_name(campus), _acronym(campus), _url(page.get('website', ''))
        if family == 'mara':
            name, acronym, url = _mara_spec(campus, page)
            subcategory = acronym
        proposals[iid] = {
            'institution_id': iid, 'institution_name': name, 'acronym': acronym,
            'type': 'ILKA', 'category': category, 'subcategory': subcategory,
            'state': state_name(page.get('negeri', '')), 'address': page.get('address', ''),
            'url': url,
        }
    return ids, proposals


def _acronym(campus):
    """The bracketed short name a campus prints ('... (ILFKB)'), else ''."""
    m = re.search(r'\(([A-Z][A-Z-]{1,19})\)', tidy(campus).upper())
    return m.group(1) if m else ''


def _url(text):
    text = tidy(text)
    if not text or text == '-' or '@' in text:
        return ''
    return text if text.startswith('http') else f'https://{text}'
