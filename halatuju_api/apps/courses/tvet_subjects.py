"""UP_TVET subject-table names -> grade-form engine keys (Bumi coverage Sprint F1).

UP_TVET prints SPM subjects in capitals with its own punctuation ("ASUHAN DAN PENDIDIKAN AWAL
KANAK-KANAK", "MAHARAT AL-QURAN", "BAHASA ARAB / BAHASA ARAB TINGGI"). `tvet_subject_keys(name)`
folds case, '&' / 'DAN', hyphens and spaces, then reads the same table the MOHE parser reads
(`spm_subject_names` -> `stpm_engine.SPM_CODE_MAP`, via `spm_syarat.subject_keys`), so the two
catalogues cannot read one subject two ways.

Three answers, as in `spm_syarat`:
  * a list of keys          the subject is on the grade form;
  * []                      a REAL SPM subject the grade form does not offer (most are the pre-2013
                            vocational MPV papers, listed in `OFF_FORM`): no HalaTuju student can hold
                            it, so it is dropped from an "any of" list with a warning; a rule that
                            REQUIRES it is unparsed;
  * None                    a name nobody has reviewed: the row is UNPARSED, never guessed.
"""
import re

from .spm_subject_names import SPM_NAME_TO_CODE
from .spm_syarat import subject_keys

# UP_TVET spellings of subjects the MOHE table already holds under another spelling.
ALIASES = {
    'MENSERVIS PERALATAN PENYEJUKAN DAN PENYAMAN UDARA': 'Menservis Peralatan Penyejukan & Penyamanan Udara',
    'MAHARAT AL QURAN': 'Maharat Al Quran',
    'HIFZ AL QURAN': 'Hifz Al Quran',
    'BAHASA ARAB': 'Bahasa Arab',
    'BAHASA ARAB TINGGI': 'Bahasa Arab Tinggi',
    'INFORMATION AND COMMUNICATION TECHNOLOGY': 'Information And Communication Technology',
    'TEKNOLOGI MAKLUMAT DAN KOMUNIKASI': 'Information And Communication Technology',
    'KESUSASTERAAN DALAM BAHASA INGGERIS': 'Literature In English',
    'BAHASA KADAZAN/DUSUN': 'Bahasa Kadazandusun',
    'BAHASA ARAB KOMUNIKASI': 'Bahasa Arab (komunikasi)',
    'GERONTOLOGI ASAS DAN PERKHIDMATAN GERIATRIK': 'Gerontologi Asas Dan Geriatrik',
    'KAREOGRAFI TARI': 'Koreografi Tari',
    'AURAL DAN TEORI': 'Aural Dan Teori Muzik',
}

#: A table row that means "any subject not named above" (UP_TVET prints it inside a subject list).
ANY_OTHER = 'MATA PELAJARAN SELAIN DI ATAS'

# Real SPM subjects with no grade-form key (reviewed 2026-10-29 against the UP_TVET tables): the
# pre-2013 vocational (MPV) and technical papers, and a few languages / arts papers.
OFF_FORM = frozenset({
    'TEKNOLOGI ELEKTRIK', 'PEMASANGAN DAN KAWALAN ELEKTRIK', 'LUKISAN GEOMETRI DAN ELEKTRIK',
    'AUTOMOTIF ELEKTRIK DAN DISEL', 'AUTOMOTIF KENDERAAN', 'KERJA KAYU DAN BATA',
    'KERJA PENYEJUKAN DAN PENYAMANAN UDARA', 'KIMPALAN ARKA', 'KIMPALAN GAS',
    'LUKISAN GEOMETRI DAN AUTOMOTIF', 'LUKISAN GEOMETRI DAN ELEKTRONIK', 'PERAKAUNAN PERNIAGAAN',
    'TEKNOLOGI BENGKEL MESIN', 'TEKNOLOGI KIMPALAN DAN FABRIKASI LOGAM',
    'TEKNOLOGI PENYEJUKAN DAN PENYAMANAN UDARA', 'TEKNOLOGI REKAAN FESYEN DAN MEMBUAT PAKAIAN',
    'BAHASA PUNJABI', 'BIBBLE KNOWLEDGE', 'AMALAN BENGKEL MEKANIKAL', 'ASAS KEMAHIRAN PELANCONGAN',
    'ASAS PEMEROSESAN MAKLUMAT', 'ASUHAN KANAK KANAK', 'BAHASA JEPUN', 'BAHASA JERMAN', 'BAHASA PERANCIS',
    'DANDANAN RAMBUT', 'ENGLISH FOR SCIENCE AND TECHNOLOGY', 'FUNDAMENTALS OF PROGRAMMING',
    'KERJA KIMPALAN #', 'KERJA MENGGEGAS DAN MELARIK', 'LUKISAN GEOMETRI DAN BINAAN BANGUNAN',
    'LUKISAN GEOMETRI DAN FABRIKASI LOGAM', 'LUKISAN GEOMETRI DAN PENYAMANAN UDARA', 'MEMBUAT PAKAIAN',
    'MEMBUAT PERABOT', 'MENGASUH DAN MEMBIMBING KANAK KANAK', 'MENSERVIS DAN MEMBAIKI KENDERAAN',
    'MENSERVIS RADIO DAN TV', 'MUZIK', 'PATISSERIE', 'PELANCONGAN DAN REKREASI',
    'PENGAJIAN PERKEMBANGAN KANAK KANAK', 'PENJAGAAN MUKA DAN DANDANAN RAMBUT',
    'PENYAJIAN MAKANAN DAN MINUMAN', 'PENYAMANAN UDARA', 'PENYEDIAAN DAN PERKHIDMATAN MAKANAN',
    'PENYEDIAAN MASAKAN BARAT DAN TIMUR', 'PENYEJUKAN', 'PERKHIDMATAN AWAL KANAK KANAK', 'PERSOLEKAN',
    'PERSOLEKAN DAN MENDANDAN RAMBUT', 'POLA PAKAIAN', 'PROGRAMMING AND DEVELOPMENT TOOLS',
    'REKAAN FESYEN DAN MEMBUAT PAKAIAN', 'REKABENTUK', 'ROTI DAN MAKANAN YIS', 'SENI HALUS', 'TARI',
    'TEATER', 'TEKNOLOGI AUTOMOTIF', 'TEKNOLOGI BAKERI DAN KONFEKSIONERI', 'TEKNOLOGI ELEKTRONIK',
    'TEKNOLOGI KATERING', 'TEKNOLOGI PEJABAT PERNIAGAAN', 'TEKNOLOGI SENI KECANTIKAN',
    # MARA pages (Sprint F2, reviewed 2026-10-30): the MPAK papers (own SPM codes 1120 / 1224 / 1226 /
    # 1450, not the academic BI / PI / PM / Matematik) and one more pre-2013 MPV drawing paper.
    'BAHASA INGGERIS (MPAK)', 'MATEMATIK (MPAK)', 'PENDIDIKAN ISLAM (MPAK)', 'PENDIDIKAN MORAL (MPAK)',
    'LUKISAN GEOMETRI DAN MESIN',
})

_NORMALISED = {}


def _norm(name):
    name = (name or '').upper().replace('&', ' DAN ').replace('-', ' ').replace('’', "'")
    return re.sub(r'\s+', ' ', name).strip()


def _lookup():
    if not _NORMALISED:
        for display in SPM_NAME_TO_CODE:
            _NORMALISED.setdefault(_norm(display), display)
        for printed, display in ALIASES.items():
            _NORMALISED[_norm(printed)] = display
    return _NORMALISED


def tvet_subject_keys(name):
    """One printed subject name -> keys / [] (real, off the form) / None (unknown)."""
    norm = _norm(name)
    if norm in OFF_FORM:
        return []
    display = _lookup().get(norm)
    return None if display is None else subject_keys(display)


def split_names(cell):
    """'BAHASA ARAB / BAHASA ARAB TINGGI' -> both names (one table row naming alternatives)."""
    return [part.strip() for part in (cell or '').split(' / ') if part.strip()]
