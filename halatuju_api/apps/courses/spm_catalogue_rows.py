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
"""
import re

from .management.commands.backfill_spm_field_key import classify_course
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
                 '461': 'sains-fizikal', '462': 'sains-data'}
LEVELS = (('SARJANA MUDA', 'Ijazah Sarjana Muda'), ('DIPLOMA', 'Diploma'), ('ASASI', 'Asasi'))
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


def build_entry(row):
    """A scraped CSV row -> {course fields, requirement, source texts, unparsed, warnings}."""
    cid = row['course_id'].strip()
    name = clean_name(row['course_name'])
    upper = name.upper()
    level = next((lvl for word, lvl in LEVELS if upper.startswith(word)), '')
    field = re.sub(r'^(Asasi|Diploma|Sarjana Muda( Sains)?( \(Kepujian\))?)\s+', '', name)
    department, label = _nec(cid)
    parsed = parse_requirements(row.get('syarat_am', ''), row.get('syarat_khas', ''))
    requirement = dict(parsed['fields'], merit_cutoff=parse_merit(row.get('merit')))
    return {
        'course_id': cid,
        'course': name,
        'level': level,
        'department': department,
        'field': field,
        'field_key': NEC_FIELD_KEY.get(cid[3:6]) or classify_course(label, field, name),
        'semesters': None,
        'university': row.get('university', ''),
        'mohe_url': row.get('mohe_url', ''),
        'requirement': requirement,
        'source': {'syarat_am': row.get('syarat_am', ''), 'syarat_khas': row.get('syarat_khas', '')},
        'unparsed': parsed['unparsed'] + ([] if level else [f'level not recognised: {name!r}']),
        'warnings': parsed['warnings'],
    }
