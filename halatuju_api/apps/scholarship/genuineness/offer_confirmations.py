"""The confirmation-of-studies word lists of the offer-genuineness rulings: the confirmation titles and the
no-private-wing issuers (owner ruling 4). Moved verbatim out of `offer_reading.py` (help sprint H2, 2026-11-15, a
moves-only split: that file stood at 592 lines, under the 600-line standard, and ruling 4's widening needs room).
`offer_reading` imports every name back (its `__all__`), so `offer_rulings` and the tests read them as before.
Pure data (one compiled pattern).

Help H2, owner option B (2026-11-15): the no-private-wing three below keep their live recognition rule exactly,
but since the owner's ruling of 16 Nov 2026 they read SUSPECT, never genuine (no confirmation reads genuine by
itself anywhere). Every OTHER public confirmation (`_PUBLIC_CONFIRMERS`, the TVET institutes, the other public
universities, an English title) is RECOGNISED but reads SUSPECT - a person checks; it never reads genuine by
itself and never blocks (`offer_rulings._confirmation_lift`).
"""
import re

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
#: The generic titles, read as a confirmation like the two above (H2 review 7: a wrong block of a real student's
#: letter hurts more than a non-study letter reaching a person, who checks every suspect).
_CONFIRM_TITLES_EN_GENERIC = (' CONFIRMATION LETTER ', ' LETTER OF CONFIRMATION ')
#: H2 review 7 (lead's rule): a NEWLY covered confirmation stays `not_offer_letter` ONLY on a CLEAR phrase that
#: the person is not studying there now (`offer_confirm_checks._not_studying`; main's live polytechnic / UMS / Form-6
#: path does not read them: TD-636). Matched per sentence, on the folded text; a conditional or footnote
#: sentence (`_CONDITIONAL`) never blocks. Bare words (TAMAT, COMPLETED, BERHENTI, ALUMNI, STAFF, KAKITANGAN)
#: never block; every other wording reads suspect and a person checks it (decisions.md ruling 4).
_NOT_STUDYING = (
    # past tense: finished, graduated, a former student
    ' TELAH TAMAT PENGAJIAN ', ' SUDAH TAMAT PENGAJIAN ', ' TELAH MENAMATKAN PENGAJIAN ',
    ' SUDAH MENAMATKAN PENGAJIAN ', ' HAS GRADUATED ', ' HAVE GRADUATED ', ' HAD GRADUATED ',
    ' HAS COMPLETED THE PROGRAMME ', ' HAS COMPLETED THE PROGRAM ', ' HAS COMPLETED HIS STUDIES ',
    ' HAS COMPLETED HER STUDIES ', ' HAS COMPLETED THE COURSE ', ' PERNAH BELAJAR ', ' PERNAH MENUNTUT ',
    ' WAS A STUDENT ',                  # "was formerly" (not "formerly known as"): offer_confirm_checks._WAS_FORMERLY
    # a refusal
    ' TIDAK BERJAYA ', ' TIDAK DITAWARKAN ', ' TIDAK LAYAK ', ' NOT OFFERED ', ' NOT BEEN OFFERED ',
    ' NOT SELECTED ', ' NOT BEEN SELECTED ', ' NOT SUCCESSFUL ', ' UNSUCCESSFUL ', ' DID NOT SUCCEED ',
    ' NOT ELIGIBLE ', ' WAITING LIST ', ' SENARAI MENUNGGU ', ' CANCELLATION OF OFFER ', ' WITHDRAWAL OF OFFER ',
    ' PEMBATALAN TAWARAN ', ' TELAH MENOLAK TAWARAN ',
    # a dismissal
    ' TELAH DIBERHENTIKAN ', ' SUDAH DIBERHENTIKAN ', ' HAS BEEN TERMINATED ', ' HAVE BEEN TERMINATED ',
    ' WAS TERMINATED ', ' WERE TERMINATED ', ' HAS BEEN DISMISSED ', ' WAS DISMISSED ', ' HAS BEEN EXPELLED ',
    ' WAS EXPELLED ')
#: ... an offer withdrawn, cancelled or declined ("Your OFFER OF ADMISSION has been WITHDRAWN").
_OFFER_UNDONE = re.compile(r' (?:OFFER|TAWARAN)(?: [A-Z0-9]+){0,8}? (?:HAS BEEN|HAVE BEEN|IS|WAS|BEEN|TELAH) '
                           r'(?:WITHDRAWN|CANCELL?ED|DECLINED|REVOKED|DIBATALKAN|DITARIK BALIK)(?= )'
                           r'| OFFER (?:WITHDRAWN|CANCELL?ED|DECLINED)(?= )| DECLINED (?:THE|THIS|YOUR) OFFER(?= )')
#: A sentence with any of these is a condition or a footnote ("Surat ini terbatal sekiranya pelajar menarik
#: diri", "void if the student withdraws"): it never blocks.
_CONDITIONAL = (' SEKIRANYA ', ' JIKA ', ' JIKALAU ', ' IF ', ' SHOULD ', ' UNLESS ', ' AKAN TERBATAL ')
#: A hostel / internship / staff / convocation / interview letter blocks only when that is its SUBJECT: the
#: title line or a PERKARA / RE / SUBJECT / "Per:" line (`offer_confirm_checks._non_study_subject`). In the body these
#: words never block.
_SUBJECT_STARTS = (' PERKARA ', ' RE ', ' SUBJECT ', ' SUBJEK ', ' PER ', ' TAJUK ')
_NOT_STUDIES_SUBJECT = (' HOSTEL ', ' ASRAMA ', ' KOLEJ KEDIAMAN ', ' RESIDENTIAL COLLEGE ', ' ACCOMMODATION ',
                        ' PENGINAPAN ', ' INTERNSHIP ', ' INDUSTRIAL TRAINING ', ' PRACTICAL TRAINING ',
                        ' LATIHAN INDUSTRI ', ' LATIHAN AMALI ', ' LATIHAN PRAKTIKAL ', ' STAFF ', ' KAKITANGAN ',
                        ' EMPLOYEE ', ' EMPLOYMENT ', ' PERKHIDMATAN ', ' SALARY ', ' GAJI ', ' CONVOCATION ',
                        ' KONVOKESYEN ', ' GRADUATION ', ' INTERVIEW ', ' TEMUDUGA ', ' TEMU DUGA ')
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
#: ... and the offer line itself names no application, result or status ("APPLICATION FOR ADMISSION ... OFFER"),
#: and is no form for refusing, cancelling or withdrawing it (H2 review 7: "OFFER REJECTION FORM").
_NOT_THE_OFFER_LINE = (' APPLICATION ', ' PERMOHONAN ', ' RESULT ', ' RESULTS ', ' STATUS ', ' KEPUTUSAN ',
                       ' REJECTION ', ' REJECT ', ' PENOLAKAN ', ' MENOLAK ', ' FORM ', ' BORANG ', ' CANCELLATION ',
                       ' PEMBATALAN ', ' WITHDRAWAL ', ' DECLINE ')
#: ... and no sentence says the offer was turned down (beside `_NOT_STUDYING`'s refusals, conditionals skipped).
_OFFER_REFUSED_EN = (' DECLINED ', ' HAS BEEN WITHDRAWN ', ' BEEN CANCELLED ', ' BEEN CANCELED ')
#: Every code that may stand in for an offer but NEVER writes a course pick (`pathway_engine.is_confirmation_letter`):
#: the confirmation codes (`confirmation_ua` is back, H2: a public university's reads suspect) and the English
#: matric offer (help H2 option B: a person checks it before anything is written from it).
CONFIRMATION_SEEN = frozenset([k for k, _n, _m in _NO_PRIVATE_WING + _PUBLIC_CONFIRMERS]
                              + ['confirmation_tvet', 'confirmation_ua', MATRIC_OFFER_EN])
