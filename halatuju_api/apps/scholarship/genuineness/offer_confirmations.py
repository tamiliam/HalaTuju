"""The confirmation-of-studies word lists of the offer-genuineness rulings: the confirmation titles and the
no-private-wing issuers (owner ruling 4). Moved verbatim out of `offer_reading.py` (help sprint H2, 2026-11-15, a
moves-only split: that file stood at 592 lines, under the 600-line standard, and ruling 4's widening needs room).
`offer_reading` imports every name back (its `__all__`), so `offer_rulings` and the tests read them as before.
Pure data, no imports.
"""

#: The confirmation-of-studies title, and the no-private-wing issuers (owner default 2026-11-03).
_CONFIRM_TITLES = (' PENGESAHAN PELAJAR ', ' PENGESAHAN SEBAGAI PELAJAR ', ' PENGESAHAN BELAJAR ',
                   ' PENGESAHAN STATUS PELAJAR ',
                   # help H2 review (2026-11-15): the English titles, read on the same proof as the Malay ones
                   ' CONFIRMATION OF STUDENT STATUS ', ' CONFIRMATION OF STUDIES ', ' CONFIRMATION LETTER ',
                   ' LETTER OF CONFIRMATION ')
_JPPKK = ' JABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI '
_NO_PRIVATE_WING = (
    # (doc_seen, the institution's own names, its public mark anywhere on the page)
    ('confirmation_polytechnic', (' POLITEKNIK ', ' POLYTECHNIC '), (_JPPKK, ' KEMENTERIAN PENDIDIKAN TINGGI ',
                                                    ' MINISTRY OF HIGHER EDUCATION ',
                                                    ' DEPARTMENT OF POLYTECHNIC AND COMMUNITY COLLEGE EDUCATION ')),
    ('confirmation_ums', (' UNIVERSITI MALAYSIA SABAH ', ' UMS '), (' UNIVERSITI MALAYSIA SABAH ',)),
    ('confirmation_form6', (' KOLEJ TINGKATAN ENAM ', ' SMK ', ' SEKOLAH MENENGAH KEBANGSAAN '),
     (' KEMENTERIAN PENDIDIKAN MALAYSIA ', ' MINISTRY OF EDUCATION MALAYSIA ', ' KOLEJ TINGKATAN ENAM ', ' SMK ',
      ' SEKOLAH MENENGAH KEBANGSAAN ')),
)
#: Round 9 (H2): a Form-6 confirmation names Form 6 on its page (an SMK also teaches Forms 1-5).
_FORM6_MARKS = (' TINGKATAN ENAM ', ' TINGKATAN 6 ', ' FORM 6 ', ' FORM SIX ', ' PRA U ', ' PRA UNIVERSITI ')
#: The ministries' own names, Malay and English (a public mark on the page).
_KPM = (' KEMENTERIAN PENDIDIKAN MALAYSIA ', ' MINISTRY OF EDUCATION MALAYSIA ', ' MINISTRY OF EDUCATION ')
_KPT = (_JPPKK, ' KEMENTERIAN PENDIDIKAN TINGGI ', ' MINISTRY OF HIGHER EDUCATION ',
        ' DEPARTMENT OF POLYTECHNIC AND COMMUNITY COLLEGE EDUCATION ')
#: Help H2 (owner ruling 2026-11-15, ruling 4 WIDENED): every other PUBLIC institution type's confirmation of
#: studies is acceptable too. Same proof as the three above (`offer_rulings.confirmation_kind`). NOT in the
#: BLOCK's public names (`offer_reading._public_names` reads `_NO_PRIVATE_WING` only): a company below one of
#: these names on a letterhead stays BLOCK proof, exactly as before. The closed-list TVET institutes
#: (`confirmation_tvet`) and the other public universities (`confirmation_ua`, suspect) are added by
#: `offer_reading._confirmers`, which reads their lists.
#: Help H2 review (2026-11-15): a type's names make it a CANDIDATE only; its marks (the ministry) must sit on the
#: letterhead and its exact public name must be on a known list for GENUINE (`offer_rulings.confirmation_proof`).
#: "BAHAGIAN MATRIKULASI" is a name, never its own mark: the mark is the ministry.
_PUBLIC_CONFIRMERS = (
    ('confirmation_matriculation', (' KOLEJ MATRIKULASI ', ' BAHAGIAN MATRIKULASI ', ' MATRICULATION COLLEGE ',
                                    ' MATRICULATION DIVISION '), _KPM),
    # "KAMPUS" is an organisation noun (`offer_reading._ORG_WORDS`): every IPG is "IPG Kampus <place>"
    ('confirmation_ipg', (' INSTITUT PENDIDIKAN GURU KAMPUS ', ' IPG KAMPUS ', ' INSTITUT PENDIDIKAN GURU ',
                          ' IPG ', ' INSTITUTE OF TEACHER EDUCATION '), _KPM),
    ('confirmation_kv', (' KOLEJ VOKASIONAL ', ' VOCATIONAL COLLEGE '), _KPM),
    ('confirmation_kolej_komuniti', (' KOLEJ KOMUNITI ', ' COMMUNITY COLLEGE '), _KPT),
)
#: Help H2 review (owner 2026-11-15): the KNOWN public names, exactly as the institutions print them. A
#: confirmation from one of these types reads GENUINE only under a name on its list; an unknown name in the
#: public pattern ("KOLEJ MATRIKULASI MERCU") reads SUSPECT (a person checks), never genuine. Sources: the
#: matriculation colleges = `halatuju-web/src/data/matric-colleges.ts` (15; KMK = Kolej Matrikulasi
#: Kejuruteraan) and the course guide's `institutions` table (the same 15); the IPG campuses (27) and the
#: community colleges (101) = the course guide's `institutions` table, read 2026-11-15. A type with no list here
#: (the KVs, the TVET institutes' campuses) never reads genuine on a confirmation: suspect at best. A list grows
#: only from that table, never by hand-written guesses.
_KNOWN_PUBLIC_NAMES = {
    'confirmation_matriculation': (
        'BAHAGIAN MATRIKULASI', 'MATRICULATION DIVISION',      # KPM's own division, as the issuer
        'KOLEJ MATRIKULASI JOHOR', 'KOLEJ MATRIKULASI KEDAH', 'KOLEJ MATRIKULASI KELANTAN',
        'KOLEJ MATRIKULASI LABUAN', 'KOLEJ MATRIKULASI MELAKA', 'KOLEJ MATRIKULASI NEGERI SEMBILAN',
        'KOLEJ MATRIKULASI PAHANG', 'KOLEJ MATRIKULASI PERAK', 'KOLEJ MATRIKULASI PERLIS',
        'KOLEJ MATRIKULASI PULAU PINANG', 'KOLEJ MATRIKULASI SARAWAK', 'KOLEJ MATRIKULASI SELANGOR',
        'KOLEJ MATRIKULASI KEJURUTERAAN JOHOR', 'KOLEJ MATRIKULASI KEJURUTERAAN KEDAH',
        'KOLEJ MATRIKULASI KEJURUTERAAN PAHANG'),
    'confirmation_ipg': tuple(f'INSTITUT PENDIDIKAN GURU KAMPUS {c}' for c in (
        'BAHASA ANTARABANGSA', 'BAHASA MELAYU', 'BATU LINTANG', 'DARULAMAN', "DATO' RAZALI ISMAIL", 'GAYA',
        'ILMU KHAS', 'IPOH', 'KENINGAU', 'KENT', 'KOTA BHARU', 'PENDIDIKAN ISLAM', 'PENDIDIKAN TEKNIK',
        'PEREMPUAN MELAYU MELAKA', 'PERLIS', 'PULAU PINANG', 'RAJA MELEWAR', 'RAJANG', 'SARAWAK',
        'SULTAN ABDUL HALIM', 'SULTAN MIZAN', 'TAWAU', 'TEMENGGONG IBRAHIM', 'TENGKU AMPUAN AFZAN',
        'TUANKU BAINUN', 'TUN ABDUL RAZAK', 'TUN HUSSEIN ONN')),
    'confirmation_kolej_komuniti': tuple(f'KOLEJ KOMUNITI {c}' for c in (
        'AMPANG', 'ARAU', 'ARAU CAWANGAN KANGAR', 'BAGAN DATUK', 'BAGAN SERAI', 'BALING', 'BANDAR BAHARU',
        'BANDAR DARULAMAN', 'BANDAR DARULAMAN CAWANGAN JERLUN', 'BANDAR PENAWAR',
        'BANDAR PENAWAR CAWANGAN GELANG PATAH', 'BANDAR TENGGARA', 'BATU GAJAH', 'BATU PAHAT', 'BAYAN BARU',
        'BEAUFORT', 'BENTONG', 'BERA', 'BESUT', 'BETONG', 'BUKIT BERUANG', 'BUKIT MERTAJAM', 'CHENDEROH',
        'GERIK', 'GOPENG', 'HULU LANGAT', 'HULU SELANGOR', 'JASIN', 'JELEBU', 'JELI', 'JEMPOL', 'JERAI',
        'JERANTUT', 'KELANA JAYA', 'KEMAMAN', 'KEPALA BATAS', 'KLANG', 'KLUANG', 'KOK LANAS', 'KOTA MARUDU',
        'KOTA MELAKA', 'KOTA TINGGI', 'KUALA KANGSAR', 'KUALA LANGAT', 'KUALA LANGAT CAWANGAN SEPANG',
        'KUALA PILAH', 'KUALA TERENGGANU', 'KUALA TERENGGANU CAW. HULU TERENGGANU',
        'KUALA TERENGGANU CAWANGAN KUALA NERUS', 'KUALA TERENGGANU CAWANGAN SETIU', 'KUANTAN', 'KUCHING',
        'KULIM', 'LAHAD DATU', 'LANGKAWI', 'LEDANG', 'MANJUNG', 'MAS GADING', 'MASJID TANAH', 'MIRI', 'MUAR',
        'NIBONG TEBAL', 'PADANG TERAP', 'PAGOH', 'PAPAR', 'PASIR GUDANG', 'PASIR MAS',
        'PASIR MAS CAWANGAN RANTAU PANJANG', 'PASIR SALAK', 'PAYA BESAR', 'PEKAN', 'PENAMPANG', 'RAUB',
        'REMBAU', 'ROMPIN', 'SABAK BERNAM', 'SANDAKAN', 'SANTUBONG', 'SARIKEI', 'SARIKEI CAWANGAN SIBU',
        'SEBERANG JAYA', 'SEGAMAT', 'SEGAMAT 2', 'SELANDAR', 'SELAYANG', 'SEMPORNA', 'SHAH ALAM', 'SIK',
        'SUNGAI PETANI', 'SUNGAI SIPUT', 'TAIPING', 'TAMBUNAN', 'TAMPIN', 'TANGGA BATU', 'TANJUNG KARANG',
        'TANJUNG PIAI', 'TAPAH', 'TASEK GELUGOR', 'TAWAU', 'TELUK INTAN', 'TEMERLOH')),
}
#: The words of a type's own pattern: every one on the letterhead must sit inside a KNOWN name.
_PUBLIC_PATTERN = {
    'confirmation_matriculation': (' KOLEJ MATRIKULASI ', ' MATRICULATION COLLEGE ', ' MATRICULATION DIVISION ',
                                   ' BAHAGIAN MATRIKULASI '),
    'confirmation_ipg': (' INSTITUT PENDIDIKAN GURU ', ' IPG ', ' INSTITUTE OF TEACHER EDUCATION '),
    'confirmation_kolej_komuniti': (' KOLEJ KOMUNITI ', ' COMMUNITY COLLEGE '),
}
#: Approval / registration wording: a ministry named after it ("Approved by KPT", "Berdaftar dengan KPM") is the
#: regulator of a PRIVATE college, never the issuer — it is not a public mark (`offer_rulings._approval_blanked`).
_APPROVAL = (' APPROVED BY ', ' APPROVED UNDER ', ' REGISTERED WITH ', ' REGISTERED UNDER ', ' REGISTERED BY ',
             ' RECOGNISED BY ', ' RECOGNIZED BY ', ' LICENSED BY ', ' LICENSED UNDER ', ' ACCREDITED BY ',
             ' DILULUSKAN OLEH ', ' DILULUSKAN DI BAWAH ', ' DIDAFTARKAN DENGAN ', ' DIDAFTARKAN DI BAWAH ',
             ' BERDAFTAR DENGAN ', ' BERDAFTAR DI BAWAH ', ' DIIKTIRAF OLEH ', ' DIPERAKUI OLEH ',
             ' KELULUSAN ', ' NO PENDAFTARAN ', ' REGISTRATION NO ')
#: Every confirmation code: a confirmation never writes a course pick (`pathway_engine.is_confirmation_letter`).
#: Help H2: `confirmation_ua` is back (owner 2026-11-15: a university WITH a private wing reads suspect).
CONFIRMATION_SEEN = frozenset([k for k, _n, _m in _NO_PRIVATE_WING + _PUBLIC_CONFIRMERS]
                              + ['confirmation_tvet', 'confirmation_ua'])
#: The polytechnics' department, Malay and English: it names no polytechnic or college (blanked before a scan).
_POLY_DEPARTMENTS = (_JPPKK, ' DEPARTMENT OF POLYTECHNIC AND COMMUNITY COLLEGE EDUCATION ')
#: The least a real confirmation scores on the families (every corpus one: 0.13-0.30).
CONFIRM_MIN = 0.10
