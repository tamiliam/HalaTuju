"""The confirmation-of-studies word lists of the offer-genuineness rulings: the confirmation titles and the
no-private-wing issuers (owner ruling 4). Moved verbatim out of `offer_reading.py` (help sprint H2, 2026-11-15, a
moves-only split: that file stood at 592 lines, under the 600-line standard, and ruling 4's widening needs room).
`offer_reading` imports every name back (its `__all__`), so `offer_rulings` and the tests read them as before.
Pure data, no imports.

Help H2, owner option B (2026-11-15): the no-private-wing three below keep their live rule exactly (genuine on
round-7 proof). Every OTHER public confirmation (`_PUBLIC_CONFIRMERS`, the TVET institutes, the other public
universities, an English title) is RECOGNISED but reads SUSPECT - a person checks; it never reads genuine by
itself and never blocks (`offer_rulings._confirmation_lift`).
"""

#: The confirmation-of-studies title, and the no-private-wing issuers (owner default 2026-11-03).
_CONFIRM_TITLES = (' PENGESAHAN PELAJAR ', ' PENGESAHAN SEBAGAI PELAJAR ', ' PENGESAHAN BELAJAR ',
                   ' PENGESAHAN STATUS PELAJAR ')
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
#: The polytechnics' department, Malay and English: it names no polytechnic or college (blanked before a scan).
_POLY_DEPARTMENTS = (_JPPKK, ' DEPARTMENT OF POLYTECHNIC AND COMMUNITY COLLEGE EDUCATION ')
#: The least a real confirmation scores on the families (every corpus one: 0.13-0.30).
CONFIRM_MIN = 0.10

# ── Help H2, option B: the newly covered confirmations (SUSPECT only) ──────────────────────
#: The English titles, read as the Malay one ONLY on the suspect path (`offer_rulings._english_titled`): the
#: live `_CONFIRM_TITLES` (letterhead stops, the genuine path) stay exactly as before.
_CONFIRM_TITLES_EN = (' CONFIRMATION OF STUDENT STATUS ', ' CONFIRMATION OF STUDIES ', ' CONFIRMATION LETTER ',
                      ' LETTER OF CONFIRMATION ')
#: The ministries' own names, Malay and English (a public mark on the page).
_KPM = (' KEMENTERIAN PENDIDIKAN MALAYSIA ', ' MINISTRY OF EDUCATION MALAYSIA ', ' MINISTRY OF EDUCATION ')
_KPT = (_JPPKK, ' KEMENTERIAN PENDIDIKAN TINGGI ', ' MINISTRY OF HIGHER EDUCATION ',
        ' DEPARTMENT OF POLYTECHNIC AND COMMUNITY COLLEGE EDUCATION ')
#: (doc_seen, the type's names, its ministry mark on the page). NOT in the BLOCK's public names
#: (`offer_reading._public_names` reads `_NO_PRIVATE_WING` only): a company below one of these names on a
#: letterhead stays BLOCK proof, exactly as before. "BAHAGIAN MATRIKULASI" is a name, never its own mark.
#: The closed-list TVET institutes (`confirmation_tvet`) and the other public universities (`confirmation_ua`)
#: are added by `offer_reading._confirmers`, which reads their lists.
_PUBLIC_CONFIRMERS = (
    ('confirmation_matriculation', (' KOLEJ MATRIKULASI ', ' BAHAGIAN MATRIKULASI ', ' MATRICULATION COLLEGE ',
                                    ' MATRICULATION DIVISION '), _KPM),
    # "KAMPUS" is an organisation noun (`offer_reading._ORG_WORDS`): every IPG is "IPG Kampus <place>"
    ('confirmation_ipg', (' INSTITUT PENDIDIKAN GURU KAMPUS ', ' IPG KAMPUS ', ' INSTITUT PENDIDIKAN GURU ',
                          ' IPG ', ' INSTITUTE OF TEACHER EDUCATION '), _KPM),
    ('confirmation_kv', (' KOLEJ VOKASIONAL ', ' VOCATIONAL COLLEGE '), _KPM),
    ('confirmation_kolej_komuniti', (' KOLEJ KOMUNITI ', ' COMMUNITY COLLEGE '), _KPT),
)
#: Approval / registration wording: a ministry named after it ("Approved by KPT", "Berdaftar dengan KPM") is the
#: regulator of a PRIVATE college, never the issuer — it is not a public mark (`offer_rulings._approval_blanked`).
#: Folded: "No. Pendaftaran" = NO PENDAFTARAN, "Reg. No." = REG NO.
_APPROVAL = (' APPROVED BY ', ' APPROVED UNDER ', ' REGISTERED WITH ', ' REGISTERED UNDER ', ' REGISTERED BY ',
             ' RECOGNISED BY ', ' RECOGNIZED BY ', ' LICENSED BY ', ' LICENSED UNDER ', ' ACCREDITED BY ',
             ' DILULUSKAN OLEH ', ' DILULUSKAN DI BAWAH ', ' DIDAFTARKAN DENGAN ', ' DIDAFTARKAN DI BAWAH ',
             ' BERDAFTAR DENGAN ', ' BERDAFTAR DI BAWAH ', ' DIIKTIRAF OLEH ', ' DIPERAKUI OLEH ',
             ' KELULUSAN ', ' NO PENDAFTARAN ', ' REGISTRATION NO ', ' DIDAFTAR DENGAN ', ' DILESENKAN OLEH ',
             ' DI BAWAH SELIAAN ', ' REG NO ', ' UNDER THE PURVIEW OF ')
#: KPM's English matriculation offer, recognised by its text (`offer_rulings.english_matric_offer`): suspect,
#: never a course pick (option B).
MATRIC_OFFER_EN = 'matric_offer_en'
#: Every code that may stand in for an offer but NEVER writes a course pick (`pathway_engine.is_confirmation_letter`):
#: the confirmation codes (`confirmation_ua` is back, H2: a public university's reads suspect) and the English
#: matric offer (help H2 option B: a person checks it before anything is written from it).
CONFIRMATION_SEEN = frozenset([k for k, _n, _m in _NO_PRIVATE_WING + _PUBLIC_CONFIRMERS]
                              + ['confirmation_tvet', 'confirmation_ua', MATRIC_OFFER_EN])
