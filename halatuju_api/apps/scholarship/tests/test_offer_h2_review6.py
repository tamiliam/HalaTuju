"""Help H2, review 6 (2026-11-15), as amended by review 7 and by the lead's decision of 16 Nov 2026 (body-word
blocks removed: only the title block is read; every confirmation reads suspect at best and a person checks it).

(H) a generic English title ("Confirmation Letter") is a confirmation only with a study word in its title block;
(M) no body word blocks: a clear not-studying sentence, a hostel / internship / staff matter in the BODY all read
suspect (main's live polytechnic / UMS / Form-6 path reads suspect since the owner's 16 Nov ruling: TD-636
closed); (M) a KAMPUS / CAMPUS line under the name is dropped unless it names an organisation or a private body;
(L) KPM's English matric offer refuses an appeal / application on its TITLE line, a status-check page and a
private letterhead, never a body word; UM's open channel (SATU) on a letterhead line is a private wing.

Every case of the reviewer's round-6 script is below. Synthetic twins only (`test_no_gitignored_corpus.py`).
"""
from django.test import SimpleTestCase

from apps.scholarship.genuineness.offer_reading import _folded_lines
from apps.scholarship.genuineness.offer_rulings import confirmation_kind, english_matric_offer
from apps.scholarship.tests.test_offer_h2_confirmations import KPM, KPT, MATRIC_EN, _read, _verdict
from apps.scholarship.tests.test_offer_rulings import _confirm

_STUDYING = 'Dengan ini disahkan bahawa penama di bawah adalah pelajar yang sedang mengikuti pengajian.'
KK_HEAD = f'KOLEJ KOMUNITI KLANG\n{KPT}'
UPM_HEAD = 'UNIVERSITI PUTRA MALAYSIA\nBahagian Akademik'
KM_HEAD = f'KOLEJ MATRIKULASI PERAK\n{KPM}'
POLY_HEAD = f'POLITEKNIK UNGKU OMAR\n{KPT}'
#: The newly covered heads (each reads suspect on a plain confirmation of studies).
NEW_HEADS = (KK_HEAD, UPM_HEAD, KM_HEAD, 'UNIVERSITI MALAYA\nJabatan Pendaftar',
             'INSTITUT KEMAHIRAN BELIA NEGARA DUSUN TUA\nKEMENTERIAN BELIA DAN SUKAN')


def _letter(head, title='PENGESAHAN PELAJAR', body=_STUDYING):
    return _confirm(head).replace('PENGESAHAN PELAJAR', title).replace(_STUDYING, body)


#: (title, body): a CLEAR phrase that the person is not studying there now. CHANGED by lead 16 Nov: body-word
#: blocks removed - under a specific title it reads suspect (a person checks); a generic title has no study word,
#: so it is no confirmation (`_expected`).
NOT_STUDYING = (
    ('CONFIRMATION LETTER', 'This is to confirm that the person below has GRADUATED and completed the programme in 2024.'),
    ('LETTER OF CONFIRMATION', 'This is to confirm that the applicant below was NOT successful in the application.'),
    ('CONFIRMATION LETTER', 'This is to confirm that the person below was a student of this college and graduated in 2024.'),
    ('PENGESAHAN PELAJAR', 'Dengan ini disahkan bahawa penama di bawah telah TAMAT pengajian pada tahun 2023.'),
    ('PENGESAHAN PELAJAR', 'Dengan ini disahkan bahawa penama di bawah telah DIBERHENTIKAN pengajian.'),
    ('PENGESAHAN PELAJAR', 'Dengan ini disahkan bahawa permohonan penama di bawah TIDAK BERJAYA.'),
    ('PENGESAHAN PELAJAR', 'Dengan ini disahkan bahawa penama di bawah adalah bekas pelajar yang telah tamat pengajian pada 2024.'),
    ('PENGESAHAN PELAJAR', 'Dengan ini disahkan bahawa penama di bawah telah menamatkan pengajian.'),
    ('CONFIRMATION OF STUDIES', 'This is to confirm that the studies of the person below were terminated.'),
    ('CONFIRMATION OF STUDIES', 'This is to confirm that the application of the person below was unsuccessful.'),
)
#: Review 7: the round-6 bodies that hold no CLEAR phrase (a hostel / training / staff matter in the BODY, a bare
#: completion word, a withdrawal) read suspect under a specific title - a person checks (decisions.md ruling 4).
NOW_SUSPECT = (
    ('CONFIRMATION LETTER', 'This is to confirm that the student below has paid the hostel fee of RM 500.00.'),
    ('LETTER OF CONFIRMATION', 'This is to confirm that the student below has completed industrial training at our office.'),
    ('CONFIRMATION LETTER', 'This is to confirm the hostel placement of the person below for the session 2026/2027.'),
    ('LETTER OF CONFIRMATION', 'This is to confirm that the person below will undergo industrial training at our department.'),
    ('CONFIRMATION LETTER', 'This is to confirm that the person below is currently studying here and stays in the hostel.'),
    ('PENGESAHAN PELAJAR', 'Dengan ini disahkan bahawa penama di bawah telah menarik diri daripada program ini.'),
    ('PENGESAHAN PELAJAR', 'Dengan ini disahkan bahawa penama di bawah adalah kakitangan tetap jabatan ini. Gaji : RM 3,200.00'),
    ('CONFIRMATION OF STUDIES', 'This is to confirm that the person below has withdrawn from the programme.'),
    ('CONFIRMATION OF STUDIES', 'This is to confirm that the person below completed the programme in 2025.'),
)
#: The reviewer's staff letter (a permanent member of staff, a salary; no identity-card line).
STAFF_LETTER = """{head}
Jalan Contoh, 43400 Serdang
CONFIRMATION LETTER
Ref : UPM/PEND/2026
Date : 1 June 2026
This is to confirm that the person below is a permanent staff member of this University.
Name : Abu bin Ali
Position : Pembantu Tadbir
Department : Bendahari
Salary : RM 3,200.00
Thank you.
Yours faithfully,
REGISTRAR
"""


_GENERIC = ('CONFIRMATION LETTER', 'LETTER OF CONFIRMATION')


def _expected(title):
    """CHANGED by lead 16 Nov: body-word blocks removed - a specific title reads suspect whatever the body says; a
    generic title with no study word in its title block is no confirmation (`not_offer_letter`)."""
    return 'not_offer_letter' if title in _GENERIC else 'suspect'


class GenericTitlesNeedAStudyWord(SimpleTestCase):
    """(H) CHANGED by lead 16 Nov: "Confirmation Letter" / "Letter of Confirmation" is a confirmation only when its
    title block holds a study word (STUDENT, STUDIES, STUDY, ENROLMENT, PELAJAR): then suspect, a person checks."""

    def test_with_a_study_word_in_the_title_block_it_reads_suspect(self):
        for head in (KK_HEAD, KM_HEAD, UPM_HEAD):
            for title in ('CONFIRMATION LETTER (STUDENT STATUS)', 'LETTER OF CONFIRMATION - STUDENT',
                          'CONFIRMATION LETTER\nSTUDENT ENROLMENT', 'LETTER OF CONFIRMATION\nRE : STUDIES'):
                with self.subTest(head=head.splitlines()[0], title=title):
                    self.assertEqual(_read(_letter(head, title))['status'], 'suspect')
                    english = _letter(head, title, 'This is to confirm that the person below is currently studying '
                                                   'at this college.')
                    self.assertEqual(_read(english)['status'], 'suspect')

    def test_without_one_it_is_no_confirmation(self):
        for head in NEW_HEADS:
            for title in _GENERIC:
                for body in (_STUDYING, 'This is to confirm the details of the person below.'):
                    with self.subTest(head=head.splitlines()[0], title=title, body=body[:30]):
                        self.assertEqual(_read(_letter(head, title, body))['status'], 'not_offer_letter')

    def test_a_study_word_in_the_body_or_the_letterhead_is_not_enough(self):
        text = _letter('UNIVERSITI PUTRA MALAYSIA\nBahagian Hal Ehwal Pelajar', 'CONFIRMATION LETTER')
        self.assertEqual(_read(text)['status'], 'not_offer_letter')

    def test_the_staff_letter_is_no_confirmation(self):
        # no identity-card line: not confirmation-shaped, so it stays `not_offer_letter` (staff in the body
        # alone never blocks: `NOW_SUSPECT`)
        for head in ('UNIVERSITI PUTRA MALAYSIA', 'KOLEJ KOMUNITI KLANG\nMINISTRY OF HIGHER EDUCATION',
                     'KOLEJ MATRIKULASI PERAK\nMINISTRY OF EDUCATION MALAYSIA', 'UNIVERSITI MALAYA',
                     'POLITEKNIK UNGKU OMAR\nMINISTRY OF HIGHER EDUCATION'):
            with self.subTest(head=head.splitlines()[0]):
                self.assertEqual(_read(STAFF_LETTER.format(head=head))['status'], 'not_offer_letter')


class NoBodyWordBlocks(SimpleTestCase):
    """(M) CHANGED by lead 16 Nov: body-word blocks removed. A former student, a graduate, a dismissal or a failed
    application said in the BODY reads suspect under a specific title - a person checks."""

    def test_a_clear_not_studying_sentence_reads_suspect(self):
        for head in NEW_HEADS:
            for title, body in NOT_STUDYING:
                for crest in (False, True):
                    with self.subTest(head=head.splitlines()[0], body=body[:50], crest=crest):
                        self.assertEqual(_read(_letter(head, title, body), crest)['status'], _expected(title))

    def test_no_clear_phrase_reads_suspect_review_7(self):
        for head in NEW_HEADS:
            for title, body in NOW_SUSPECT:
                for crest in (False, True):
                    with self.subTest(head=head.splitlines()[0], body=body[:50], crest=crest):
                        self.assertEqual(_read(_letter(head, title, body), crest)['status'], _expected(title))

    def test_the_expected_end_date_label_is_no_completion(self):
        for label in ('Tarikh Tamat Pengajian : 30 Jun 2028', 'Jangkaan Tamat Pengajian : Jun 2028',
                      'Tempoh Tamat Belajar : 2028'):
            for head in (KK_HEAD, UPM_HEAD):
                with self.subTest(head=head.splitlines()[0], label=label):
                    text = _confirm(head).replace('Bidang : Sains', f'Bidang : Sains\n{label}')
                    self.assertEqual(_read(text)['status'], 'suspect')

    def test_mains_live_polytechnic_path_reads_suspect_td_636_closed(self):
        # CHANGED by help H2 owner 16 Nov: all confirmations suspect - main read this genuine (TD-636); now a
        # person checks it. Main's recognition rule is unchanged, and nothing on it moves to not_offer_letter
        text = _letter(POLY_HEAD, 'PENGESAHAN PELAJAR', 'Dengan ini disahkan bahawa penama di bawah telah '
                                                        'DIBERHENTIKAN pengajian.')
        for crest in (False, True):
            with self.subTest(crest=crest):
                self.assertEqual(_verdict(text, crest), ('suspect', 'confirmation_polytechnic', 'confirmation_check'))
        self.assertEqual(confirmation_kind(text), 'confirmation_polytechnic')


class ACampusLineUnderTheNameIsDropped(SimpleTestCase):
    """(M, review 7) a KAMPUS / CAMPUS line under the name is the institution's own campus and is dropped; it
    stays and fails only when it names an organisation or a private body."""

    def test_a_campus_line_reads_suspect(self):
        for head in (f'KOLEJ KOMUNITI KLANG\nKAMPUS KLANG\n{KPT}', f'KOLEJ KOMUNITI KLANG\nKAMPUS SELANGOR\n{KPT}',
                     f'KOLEJ MATRIKULASI PERAK\nKAMPUS PERAK\n{KPM}', f'KOLEJ MATRIKULASI PERAK\nKAMPUS GOPENG\n{KPM}',
                     f'KOLEJ KOMUNITI KLANG\nKAMPUS MERCU PRESTIGE\n{KPT}', f'KOLEJ KOMUNITI KLANG\nKAMPUS MERCU\n{KPT}',
                     f'KOLEJ KOMUNITI KLANG\nKAMPUS KLANG MERCU\n{KPT}'):
            for crest in (False, True):
                with self.subTest(head=head, crest=crest):
                    self.assertEqual(_read(_confirm(head), crest)['status'], 'suspect')

    def test_a_campus_line_naming_an_organisation_or_a_private_body_fails(self):
        for head in (f'KOLEJ MATRIKULASI PERAK\nKAMPUS MERCU COLLEGE\n{KPM}',
                     f'KOLEJ MATRIKULASI PERAK\nKAMPUS MERCU SDN BHD\n{KPM}',
                     f'KOLEJ MATRIKULASI PERAK\nKAMPUS SWASTA MERCU\n{KPM}',
                     f'KOLEJ MATRIKULASI PERAK\nCAMPUS MERCU PRIVATE\n{KPM}',
                     f'KOLEJ KOMUNITI KLANG\nCAMPUS MERCU BERHAD\n{KPT}'):
            for crest in (False, True):
                with self.subTest(head=head, crest=crest):
                    self.assertEqual(_read(_confirm(head), crest)['status'], 'not_offer_letter')

    def test_an_english_campus_line_reads_suspect_never_genuine(self):
        for crest in (False, True):
            with self.subTest(crest=crest):
                self.assertEqual(_read(_confirm(f'KOLEJ KOMUNITI KLANG\nCAMPUS SEGI SUBANG\n{KPT}'), crest)['status'],
                                 'suspect')


#: The reviewer's English matric letters that are no offer (L): an appeal / application on the TITLE line, a
#: status-check page above the Division, a private letterhead.
_REGISTER = 'You must register on the date set by the college.'
NOT_A_MATRIC_OFFER = (
    ('appeal result', MATRIC_EN.replace('OFFER OF ADMISSION', 'APPEAL RESULT: OFFER OF ADMISSION')),
    ('status check', 'SEMAKAN STATUS PERMOHONAN\n' + MATRIC_EN),
    ('application', MATRIC_EN.replace('OFFER OF ADMISSION TO THE MATRICULATION PROGRAMME',
                                      'APPLICATION FOR ADMISSION TO THE MATRICULATION PROGRAMME OFFER')),
    ('a private foundation under the Division', MATRIC_EN.replace('MATRICULATION DIVISION\nRef',
                                                                  'MATRICULATION DIVISION\nMERCU FOUNDATION CENTRE\nRef')),
    ('a university first', 'UNIVERSITI MALAYA\n' + MATRIC_EN),
)


#: CHANGED by lead 16 Nov: body-word blocks removed - a refusal or a results word in the BODY reads suspect.
BODY_ONLY_SUSPECT = (
    ('unsuccessful', MATRIC_EN.replace(_REGISTER, 'We regret that your application for the OFFER OF ADMISSION TO THE '
                                                  'MATRICULATION PROGRAMME was UNSUCCESSFUL.')),
    ('not offered', MATRIC_EN.replace(_REGISTER, 'You have NOT been offered a place this session.')),
    ('a results slip', MATRIC_EN.replace('Stream : Science', 'Stream : Science\nKeputusan Peperiksaan Semester : 3.80')),
)


class TheEnglishMatricOfferRefusesNonOffers(SimpleTestCase):
    def test_a_body_word_reads_suspect(self):
        for name, text in BODY_ONLY_SUSPECT:
            for crest in (False, True):
                with self.subTest(name, crest=crest):
                    self.assertEqual(_read(text, crest)['status'], 'suspect')

    def test_none_is_recognised_or_reads_better_than_not_an_offer(self):
        for name, text in NOT_A_MATRIC_OFFER:
            with self.subTest(name):
                self.assertFalse(english_matric_offer(_folded_lines(text)))
                for crest in (False, True):
                    self.assertEqual(_read(text, crest)['status'], 'not_offer_letter')

    def test_a_company_signature_or_a_private_college_never_reads_genuine(self):
        for text in (MATRIC_EN.replace('Director\nMatriculation Division', 'Director\nMercu Education Sdn. Bhd.'),
                     MATRIC_EN.replace('College : Kolej Matrikulasi Contoh', 'College : Mercu International College Sdn Bhd')):
            for crest in (False, True):
                with self.subTest(text=text[-60:], crest=crest):
                    self.assertNotEqual(_read(text, crest)['status'], 'genuine')

    def test_the_plain_offer_still_reads_suspect(self):
        self.assertEqual(_read(MATRIC_EN)['status'], 'suspect')


#: The reviewer's private colleges and private wings (round 6), under each title: never genuine, and a fail
#: unless the line names a public body (`PUBLIC_SUSPECT`: a person checks it, main's letterhead rule).
PRIVATE_HEADS = (
    'KOLEJ UNIVERSITI MERCU\nDiluluskan oleh Kementerian Pendidikan Tinggi', 'MERCU UNIVERSITY COLLEGE\nKOLEJ KOMUNITI',
    'KOLEJ MERCU\nKAMPUS KOLEJ KOMUNITI KLANG', 'MERCU COLLEGE\nMINISTRY OF HIGHER EDUCATION',
    'KOLEJ KOMUNITI MERCU SDN BHD\nKEMENTERIAN PENDIDIKAN TINGGI', 'UNIVERSITI TEKNOLOGI MALAYSIA\nUTM SPACE',
    'UNIVERSITI PUTRA MALAYSIA\nUPM HOLDINGS', 'UNIVERSITI MALAYA\nUM SATU',
    'KOLEJ VOKASIONAL MERCU\nMERCU EDUCATION SDN BHD\nKEMENTERIAN PENDIDIKAN MALAYSIA',
    'IPG KAMPUS MERCU\nMERCU TRAINING CENTRE\nKEMENTERIAN PENDIDIKAN MALAYSIA',
    'INSTITUT KEMAHIRAN BELIA NEGARA DUSUN TUA\nMERCU SKILLS ACADEMY\nKEMENTERIAN BELIA DAN SUKAN',
    'UNIVERSITI KUALA LUMPUR\nKEMENTERIAN PENDIDIKAN TINGGI', 'UNIVERSITI TUN ABDUL RAZAK\nKEMENTERIAN PENDIDIKAN TINGGI',
    'MAHSA UNIVERSITY\nKEMENTERIAN PENDIDIKAN TINGGI',
    'SALURAN TERBUKA UNIVERSITI MALAYA (SATU)\nUNIVERSITI MALAYA', 'UNIVERSITI MALAYA\nSALURAN TERBUKA (SATU)',
    'UNIVERSITI MALAYSIA SABAH\nPUSAT PENDIDIKAN PROFESIONAL DAN LANJUTAN (PPPL)',
    'UNIVERSITI KEBANGSAAN MALAYSIA\nPUSAT PENDIDIKAN BERTERUSAN', 'UNIVERSITI TEKNOLOGI MARA\nINSTITUT PENDIDIKAN NEO',
    'UNIVERSITI PUTRA MALAYSIA\nUPM ACADEMY', 'UNIVERSITI TEKNOLOGI MALAYSIA\nSCHOOL OF PROFESSIONAL AND CONTINUING EDUCATION',
    'INTERNATIONAL ISLAMIC UNIVERSITY MALAYSIA\nIIUM ACADEMY', 'INTERNATIONAL ISLAMIC UNIVERSITY MALAYSIA\nCENPACE',
    'UNIVERSITI UTARA MALAYSIA\nUUM PROFESSIONAL AND CONTINUING EDUCATION',
    'UNIVERSITI MALAYA\nUM CENTRE FOR CONTINUING EDUCATION (UMCCed)',
)
#: A public body's own unit on the line (decisions.md, option B): suspect, a person checks; never genuine.
PUBLIC_SUSPECT = ('UNIVERSITI PUTRA MALAYSIA\nSCHOOL OF GRADUATE STUDIES', 'UNIVERSITI SAINS MALAYSIA\nPUSAT PENGAJIAN JARAK JAUH',
                  f'KOLEJ KOMUNITI KLANG\nKOLEJ KEJURURAWATAN MERCU\n{KPT}')
_TITLES = ('PENGESAHAN PELAJAR', 'CONFIRMATION OF STUDIES', 'CONFIRMATION LETTER')
#: The titles that make a confirmation (a generic one needs a study word: lead, 16 Nov 2026).
_CONFIRMING = ('PENGESAHAN PELAJAR', 'CONFIRMATION OF STUDIES', 'CONFIRMATION LETTER (STUDENT STATUS)')


class TheReviewersPrivateIssuers(SimpleTestCase):
    def test_a_private_college_or_wing_fails_under_every_title(self):
        for head in PRIVATE_HEADS:
            for title in _TITLES:
                for crest in (False, True):
                    with self.subTest(head=head, title=title, crest=crest):
                        self.assertEqual(_read(_letter(head, title), crest)['status'], 'not_offer_letter')

    def test_a_public_bodys_own_unit_reads_suspect_never_genuine(self):
        for head in PUBLIC_SUSPECT:
            for title in _CONFIRMING:
                with self.subTest(head=head, title=title):
                    self.assertEqual(_read(_letter(head, title))['status'], 'suspect')

    def test_satu_in_the_body_is_one_not_the_wing(self):
        text = _confirm('UNIVERSITI MALAYA\nJabatan Pendaftar').replace('Bidang : Sains', 'Bidang : Sains\nSemester Satu')
        self.assertEqual(_verdict(text), ('suspect', 'confirmation_ua', 'confirmation_ua'))

    def test_a_results_slip_titled_as_a_confirmation_is_no_confirmation(self):
        slip = f"""KOLEJ MATRIKULASI PERAK
{KPM}
SLIP KEPUTUSAN PEPERIKSAAN SEMESTER
PENGESAHAN PELAJAR
Nama : Ali bin Abu
Program : Matrikulasi Sains
PNGK : 3.50
Rujukan : KMPk/2026
Tarikh : 1 Jun 2026
Disahkan oleh,
PENGARAH
"""
        for text in (slip, slip.replace('PENGESAHAN PELAJAR', 'CONFIRMATION OF STUDIES')):
            with self.subTest(title=text.splitlines()[3]):
                self.assertEqual(_read(text)['status'], 'not_offer_letter')
