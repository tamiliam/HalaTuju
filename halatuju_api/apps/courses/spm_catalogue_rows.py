"""One scraped MOHE SPM programme row -> one human-reviewable catalogue entry (Bumi Sprint D1).

`build_entry(row)` turns a row of `data/spm/mohe_bumi_<date>.csv` (scraped with `--with-syarat
--with-syarat-am`) into the dict `ingest_spm_courses` writes to `Course` + `CourseRequirement` +
`CourseInstitution`, keeping the two source texts BESIDE the parsed fields so a reviewer can read
one against the other. A row the parser could not represent faithfully comes back with its
`unparsed` reasons and is never ingested.

Course-level fields MOHE does not give us are derived, deterministically:
  * name: the card title, "Baru" (new-programme marker) and layout whitespace removed, title case;
  * level: from the title's first word (ASASI / DIPLOMA / SARJANA MUDA);
  * department + the `classify_course` hint: from the programme code's NEC field digits
    (UE4 **526** 003 -> 52x engineering, 526 civil), the code family MOHE itself uses;
  * field_key: `backfill_spm_field_key.classify_course` (the one SPM classifier), except three
    health codes whose taxonomy key exists but which that classifier has no rule for;
  * merit_cutoff: like `sync_spm_mohe._parse_merit` — blank or "Baru" is NULL.

Sprint D2 adds: the parent institution per row (`INSTITUTION_IDS`, owner ruling: ONE parent per
course, campuses later; MARA has no row yet, so `NEW_INSTITUTIONS` proposes one); "Tamhidi" (USIM's
foundation year) as level Asasi; a field key from the NAME when the programme code's NEC field is
the general 0xx (most Asasi codes), where `classify_course` reads "Sains Sosial" as life science;
the reviewed ATAU scopes (`spm_atau_scopes.py`); and the two Bumi-only Matrikulasi programmes as
synthetic matric rows (`BUMI_MATRIC_TRACKS`, `build_matric_entry`), the way the four open tracks are
held (`matric-<track>`, source and merit type 'matric', no institution row).
"""
import re

from .management.commands.backfill_spm_field_key import classify_course
from .spm_atau_scopes import ATAU_SCOPES
from .spm_syarat import parse_requirements

# NEC field (2 digits, then 3 where it matters) -> (department, classify_course frontend label).
NEC_DEPARTMENT = {
    '14': ('Pendidikan', 'pendidikan'),
    '21': ('Seni Dan Reka Bentuk', 'seni reka & kreatif'),
    '22': ('Bahasa Dan Komunikasi', ''),
    '221': ('Pengajian Islam', ''),
    '32': ('Bahasa Dan Komunikasi', ''),
    '34': ('Perniagaan Dan Pengurusan', 'perniagaan & perdagangan'),
    '38': ('Undang-Undang', ''),
    '42': ('Sains', 'sains & teknologi'),
    '46': ('Sains', ''),
    '48': ('Teknologi Maklumat', 'teknologi maklumat'),
    '52': ('Kejuruteraan', ''),
    '521': ('Kejuruteraan', 'mekanikal & pembuatan'),
    '522': ('Kejuruteraan', 'elektrik & elektronik'),
    '523': ('Kejuruteraan', 'elektrik & elektronik'),
    '526': ('Kejuruteraan', 'sivil, seni bina & pembinaan'),
    '54': ('Teknologi Pembuatan', ''),
    '545': ('Sains', 'sains & teknologi'),
    '58': ('Seni Bina Dan Binaan', 'sivil, seni bina & pembinaan'),
    '62': ('Pertanian Dan Bio-Industri', 'pertanian & bio-industri'),
    '72': ('Kesihatan', ''),
    '81': ('Hospitaliti', 'hospitaliti, kulinari & pelancongan'),
    '813': ('Sains Sukan', 'sains sosial'),
}
# Taxonomy keys `classify_course` has no rule (or the wrong one) for, by NEC code.
NEC_FIELD_KEY = {'723': 'kejururawatan', '724': 'pergigian', '727': 'farmasi', '726': 'perubatan',
                 '221': 'pengajian-islam', '222': 'bahasa', '321': 'komunikasi', '322': 'komunikasi',
                 '461': 'sains-fizikal', '462': 'sains-data', '440': 'sains-fizikal', '840': 'pengurusan'}
# A general (0xx) NEC field says nothing about the subject: read the name (first match wins).
NAME_FIELD_KEY = (
    (r'Agrisains', 'pertanian'), (r'Kejururawatan', 'kejururawatan'), (r'Pergigian', 'pergigian'),
    (r'Farmasi', 'farmasi'), (r'Perubatan|Kesihatan', 'perubatan'),
    (r'Pengkomputeran|Sains Komputer|Teknologi Maklumat', 'it-perisian'),
    (r'Sains Fizikal', 'sains-fizikal'), (r'Sains Hayat', 'sains-hayat'),
    (r'Sains Sosial|Kemanusiaan', 'sains-sosial'), (r'Wahyu|Islam', 'pengajian-islam'),
)
LEVELS = (('SARJANA MUDA', 'Ijazah Sarjana Muda'), ('DIPLOMA', 'Diploma'), ('ASASI', 'Asasi'),
          ('TAMHIDI', 'Asasi'))
# The parent institution per MOHE university name (prod ids, read-only SQL 2026-10-29).
INSTITUTION_IDS = {
    'Universiti Islam Antarabangsa Malaysia': 'UNIV-006', 'Universiti Malaya': 'UNIV-001',
    'Universiti Malaysia Sabah': 'UNIV-009', 'Universiti Malaysia Sarawak': 'UNIV-008',
    'Universiti Sains Islam Malaysia': 'UNIV-011', 'Universiti Sultan Zainal Abidin': 'UNIV-018',
    'Universiti Teknologi Mara': 'UNIV-012', 'Mara, Bahagian Pendidikan Tinggi': 'MARA-BPT',
}
# Institutions the catalogue does not hold yet: created ONLY by `ingest_spm_courses
# --create-institutions` (dry run first), never silently. The lead confirms the shape against an
# existing IPTA row before --apply.
NEW_INSTITUTIONS = {
    'MARA-BPT': {
        'institution_id': 'MARA-BPT',
        'institution_name': 'Majlis Amanah Rakyat (MARA) - Bahagian Pendidikan Tinggi',
        'acronym': 'MARA', 'type': 'MARA', 'category': '', 'subcategory': '',
        'state': 'Wilayah Persekutuan Kuala Lumpur', 'url': 'https://www.mara.gov.my',
    },
}
# The two Bumi-only Matrikulasi programmes (owner ruling 2026-10-29: two NEW Bumi-only tracks).
BUMI_MATRIC_TRACKS = {
    'KA0000002': {'course_id': 'matric-sains-4-semester', 'course': 'Matrikulasi — Sains (4 Semester)',
                  'field': 'Sains & Teknologi', 'field_key': 'sains-hayat', 'semesters': 4},
    'KA0000006': {'course_id': 'matric-perakaunan-profesional',
                  'course': 'Matrikulasi — Perakaunan Profesional',
                  'field': 'Perakaunan & Kewangan', 'field_key': 'perakaunan', 'semesters': 2},
}
ACRONYMS = {'Uitm': 'UiTM', 'Kpm': 'KPM', 'Tesl': 'TESL'}


def clean_name(raw):
    """'DIPLOMA SENI HALUS' + layout whitespace + 'Baru' -> 'Diploma Seni Halus'."""
    name = re.sub(r'\s+', ' ', raw or '').strip()
    name = re.sub(r'\s+Baru$', '', name).title()
    for wrong, right in ACRONYMS.items():
        name = re.sub(rf'\b{wrong}\b', right, name)
    return name


def parse_merit(raw):
    """'85.50' -> 85.5; blank, 'Baru' or anything unparseable -> None (as `sync_spm_mohe`)."""
    try:
        return float(raw) if raw else None
    except (TypeError, ValueError):
        return None


def _nec(course_id):
    digits = course_id[3:6]
    return NEC_DEPARTMENT.get(digits) or NEC_DEPARTMENT.get(digits[:2]) or ('Umum', '')


def _field_key(cid, label, field, name):
    if cid[3] == '0':  # a general NEC field: the name is the only signal
        found = next((key for pattern, key in NAME_FIELD_KEY if re.search(pattern, field)), None)
        if found:
            return found
    return NEC_FIELD_KEY.get(cid[3:6]) or classify_course(label, field, name)


def build_entry(row):
    """A scraped CSV row -> {course fields, requirement, source texts, unparsed, warnings}."""
    cid = row['course_id'].strip()
    if cid in BUMI_MATRIC_TRACKS:
        return build_matric_entry(row)
    name = clean_name(row['course_name'])
    upper = name.upper()
    level = next((lvl for word, lvl in LEVELS if upper.startswith(word)), '')
    field = re.sub(r'^(Asasi|Tamhidi|Diploma|Sarjana Muda( Sains)?( \(Kepujian\))?)\s+', '', name)
    department, label = _nec(cid)
    parsed = parse_requirements(row.get('syarat_am', ''), row.get('syarat_khas', ''), ATAU_SCOPES.get(cid))
    requirement = dict(parsed['fields'], merit_cutoff=parse_merit(row.get('merit')))
    return {
        'course_id': cid,
        'course': name,
        'level': level,
        'department': department,
        'field': field,
        'field_key': _field_key(cid, label, field, name),
        'semesters': None,
        'university': row.get('university', ''),
        'institution_id': INSTITUTION_IDS.get(row.get('university', '')),
        'mohe_url': row.get('mohe_url', ''),
        'requirement': requirement,
        'source': {'syarat_am': row.get('syarat_am', ''), 'syarat_khas': row.get('syarat_khas', '')},
        'unparsed': parsed['unparsed'] + ([] if level else [f'level not recognised: {name!r}']),
        'warnings': parsed['warnings'],
    }


def build_matric_entry(row):
    """A Bumi-only Matrikulasi programme (KA...) -> a synthetic `matric-<track>` catalogue row: the
    requirement is parsed from MOHE's text like any other, then held as source and merit type
    'matric' (merit from `pathways.check_matric_track`), with NO institution row (the web lists the
    colleges itself) and no merit cutoff (MOHE publishes none)."""
    track = BUMI_MATRIC_TRACKS[row['course_id'].strip()]
    parsed = parse_requirements(row.get('syarat_am', ''), row.get('syarat_khas', ''))
    requirement = dict(parsed['fields'], source_type='matric', merit_type='matric', merit_cutoff=None)
    return {
        'course_id': track['course_id'], 'course': track['course'], 'level': 'Pra-U',
        'department': 'KPM', 'field': track['field'], 'field_key': track['field_key'],
        'semesters': track['semesters'], 'university': row.get('university', ''),
        'institution_id': None, 'mohe_code': row['course_id'].strip(),
        'mohe_url': row.get('mohe_url', ''), 'requirement': requirement,
        'source': {'syarat_am': row.get('syarat_am', ''), 'syarat_khas': row.get('syarat_khas', '')},
        'unparsed': parsed['unparsed'], 'warnings': parsed['warnings'],
    }
