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
_CONFIRM_TITLES_EN = (' CONFIRMATION OF STUDENT STATUS ', ' CONFIRMATION OF STUDIES ')
#: H2 review 6 (H): the generic titles confirm anything (a hostel fee, an internship, a graduation, a failed
#: application). Read as a confirmation of studies ONLY when the page says the person studies there NOW
#: (`_STUDYING_NOW`) and names no hostel / training / staff matter (`_NOT_STUDIES_EN`).
_CONFIRM_TITLES_EN_GENERIC = (' CONFIRMATION LETTER ', ' LETTER OF CONFIRMATION ')
_STUDYING_NOW = (' IS CURRENTLY STUDYING ', ' IS CURRENTLY A STUDENT ', ' IS CURRENTLY PURSUING ',
                 ' IS CURRENTLY ENROLLED ', ' IS A REGISTERED STUDENT ', ' IS A FULL TIME STUDENT ',
                 ' IS AN ACTIVE STUDENT ', ' IS A BONA FIDE STUDENT ', ' SEDANG MENGIKUTI ', ' SEDANG BELAJAR ',
                 ' MASIH BELAJAR ', ' PELAJAR BERDAFTAR ', ' PELAJAR AKTIF ')
_NOT_STUDIES_EN = (' HOSTEL ', ' ASRAMA ', ' INTERNSHIP ', ' INDUSTRIAL TRAINING ', ' PRACTICAL TRAINING ',
                   ' LATIHAN INDUSTRI ')
#: H2 review 6 (M): the person is no longer (or never was) studying - a former student, a graduate, a dismissal,
#: a withdrawal, a failed application, a member of staff. A NEWLY covered confirmation with any of these stays
#: `not_offer_letter` (`offer_rulings._not_studying`; main's live polytechnic / UMS / Form-6 path does not read
#: them: TD-636). Folded page, matched as phrases.
_NOT_STUDYING = (' TELAH TAMAT ', ' TELAH MENAMATKAN ', ' MENAMATKAN PENGAJIAN ', ' DITAMATKAN ', ' DIBERHENTIKAN ',
                 ' BERHENTI ', ' TIDAK BERJAYA ', ' MENARIK DIRI ', ' BEKAS PELAJAR ', ' DIGUGURKAN ', ' DIBUANG ',
                 ' GRADUATED ', ' COMPLETED ', ' UNSUCCESSFUL ', ' NOT SUCCESSFUL ', ' TERMINATED ', ' WITHDRAWN ',
                 ' WITHDREW ', ' FORMER STUDENT ', ' DISMISSED ', ' EXPELLED ', ' ALUMNI ', ' ALUMNUS ',
                 ' KAKITANGAN ', ' STAFF ', ' EMPLOYEE ', ' SALARY ', ' GAJI ')
#: UM's open channel on a letterhead line ("UNIVERSITI MALAYA / UM SATU"): a private wing, never a university's
#: own confirmation. Letterhead lines only - "Semester Satu" in a body is "one" (`results_doc` note).
_WING_HEAD = (' SATU ',)
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
#: H2 review 6 (L): a refusal, an appeal's answer or a status check is no offer (anywhere on the page) ...
_NOT_AN_OFFER_EN = (' UNSUCCESSFUL ', ' NOT SUCCESSFUL ', ' NOT OFFERED ', ' NOT BEEN OFFERED ', ' REGRET ', ' APPEAL ',
                    ' RAYUAN ', ' TIDAK BERJAYA ', ' DUKACITA ', ' APPLICATION STATUS ', ' STATUS PERMOHONAN ',
                    ' SEMAKAN STATUS ', ' REJECTED ')
#: ... and the offer line itself names no application, result or status ("APPLICATION FOR ADMISSION ... OFFER").
_NOT_THE_OFFER_LINE = (' APPLICATION ', ' PERMOHONAN ', ' RESULT ', ' RESULTS ', ' STATUS ', ' KEPUTUSAN ')
#: Every code that may stand in for an offer but NEVER writes a course pick (`pathway_engine.is_confirmation_letter`):
#: the confirmation codes (`confirmation_ua` is back, H2: a public university's reads suspect) and the English
#: matric offer (help H2 option B: a person checks it before anything is written from it).
CONFIRMATION_SEEN = frozenset([k for k, _n, _m in _NO_PRIVATE_WING + _PUBLIC_CONFIRMERS]
                              + ['confirmation_tvet', 'confirmation_ua', MATRIC_OFFER_EN])
