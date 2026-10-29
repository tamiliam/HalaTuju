"""UP_TVET provider FAMILIES — which public body runs a catalogue row's campus (Bumi coverage Sprint F1).

The UP_TVET catalogue names the campus ("ADTEC JTM KAMPUS PEDAS (ILP PEDAS), NEGERI SEMBILAN"), never the
ministry. HalaTuju groups a programme's campuses by provider family (owner ruling F, 2026-10-29: one
course per programme, every named campus linked), and the family decides the institution's
`category` / `subcategory`, which in turn decides the pathway chip (`apps.py`):

    family      category  pathway chip          what it covers
    iljtm       ILJTM     iljtm                 JTM: ADTEC / ILP / JMTI
    ilkbs       ILKBS     ilkbs                 KBS: IKBN / IKTBN / IKSN
    mara        MARA      mara (Sprint F2)      GIATMARA, KKTM, IKM / TVETMARA, MJII ...
    kraf ...    TVET      tvet_other            every other public body (Kraf, PERDA, agriculture,
                                                fisheries, veterinary, MARDI, FAMA, Peladang, KEMAS, tenun)

`family_of(name)` is a pure first-match over the upper-cased name; an unknown public provider is
None, and the callers FLAG it rather than guess.
"""
import re

# (family key, regex over the UPPER-CASED institution name). Order matters: MARA first (a
# "TVETMARA" campus also says "KEMAHIRAN"), ILKBS before the generic agriculture words.
FAMILY_PATTERNS = (
    ('mara', r'\bMARA\b|GIATMARA|TVETMARA|KKTM|\bMJII\b|KOLEJ KEMAHIRAN TINGGI MARA|INSTITUT KEMAHIRAN MARA'),
    ('iljtm', r'ADTEC|\bILP\b|\bJMTI\b|TEKNIKAL JEPUN|TENAGA MANUSIA|\bCIAST\b'),
    ('ilkbs', r'BELIA NEGARA|\bIKBN\b|\bIKTBN\b|KEMAHIRAN SUKAN NEGARA|\bIKSN\b'),
    ('kraf', r'KRAF NEGARA'),
    ('perda', r'PERDA'),
    ('pertanian', r'KOLEJ PERTANIAN|INSTITUT PERTANIAN'),
    ('perikanan', r'PERIKANAN'),
    ('veterinar', r'VETERINAR'),
    ('unggas', r'UNGGAS'),
    ('mardi', r'\bMARDI\b'),
    ('fama', r'\bFAMA\b'),
    ('peladang', r'PELADANG'),
    ('kemas', r'\bKEMAS\b'),
    ('tenun', r'TENUN'),
)

#: family -> (Institution.category, Institution.subcategory default, id prefix, provider label).
#: ILJTM / ILKBS keep prod's own scheme (IJTM-NNN / IKBN-NNN; subcategory read from the campus name);
#: every other public body is category 'TVET' (the "Other skills training" chip) under a NEW prefix ILKA-NNN
#: (the type every TVET institute already carries), so it cannot be read as a course id (TVET-<id_kursus>).
FAMILY_INSTITUTION = {
    'iljtm': ('ILJTM', 'ILP', 'IJTM', 'Jabatan Tenaga Manusia'),
    'ilkbs': ('ILKBS', 'IKBN', 'IKBN', 'Kementerian Belia dan Sukan'),
    'mara': ('MARA', 'MARA', 'MARA', 'Majlis Amanah Rakyat'),
    'kraf': ('TVET', 'KRAF', 'ILKA', 'Kraftangan Malaysia'),
    'perda': ('TVET', 'PERDA', 'ILKA', 'PERDA'),
    'pertanian': ('TVET', 'PERTANIAN', 'ILKA', 'Jabatan Pertanian'),
    'perikanan': ('TVET', 'PERIKANAN', 'ILKA', 'Jabatan Perikanan'),
    'veterinar': ('TVET', 'VETERINAR', 'ILKA', 'Jabatan Perkhidmatan Veterinar'),
    'unggas': ('TVET', 'VETERINAR', 'ILKA', 'Jabatan Perkhidmatan Veterinar'),
    'mardi': ('TVET', 'MARDI', 'ILKA', 'MARDI'),
    'fama': ('TVET', 'FAMA', 'ILKA', 'Lembaga Pemasaran Pertanian Persekutuan (FAMA)'),
    'peladang': ('TVET', 'PELADANG', 'ILKA', 'Lembaga Pertubuhan Peladang'),
    'kemas': ('TVET', 'KEMAS', 'ILKA', 'KEMAS'),
    'tenun': ('TVET', 'TENUN', 'ILKA', 'Kerajaan Negeri Pahang'),
}

#: Families Sprint F1 ingests (everything public except MARA, which is F2).
F1_FAMILIES = tuple(k for k, _ in FAMILY_PATTERNS if k != 'mara')


def tidy(text):
    """Layout whitespace (the catalogue wraps names over lines) -> single spaces."""
    return re.sub(r'\s+', ' ', text or '').strip()


def family_of(institution_name):
    """'ADTEC JTM KAMPUS PEDAS (ILP PEDAS), NEGERI SEMBILAN' -> 'iljtm'; unknown -> None."""
    upper = tidy(institution_name).upper()
    return next((key for key, pattern in FAMILY_PATTERNS if re.search(pattern, upper)), None)
