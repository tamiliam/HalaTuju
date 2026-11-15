"""Help H2, review 7 (2026-11-15): the lead's rule for the newly covered confirmations (option B, suspect at most).

Every suspect is checked by a person, so a wrong block of a real student's letter hurts more than a non-study
letter reaching a person. CHANGED by lead 16 Nov: body-word blocks removed - no body sentence blocks (a former
student, a refusal, a dismissal, an offer withdrawn all read suspect under a confirmation title); a hostel /
staff / convocation / interview letter, or an internship with no study word, blocks only when that is its
SUBJECT (the title line or a PERKARA / RE / SUBJECT / "Per:" / "Tajuk:" line). A generic English title needs a
study word in its title block. A KAMPUS / CAMPUS line under the name is dropped (it fails only when it names an
organisation or a private body). KPM's English matric offer refuses only a cancellation, a rejection form or
the like on its TITLE line; a body refusal reads suspect. Main's live polytechnic / UMS /
Form-6 recognition is unchanged, but - CHANGED by help H2 owner 16 Nov: all confirmations suspect - a POLITEKNIK
head under the Malay title reads SUSPECT (genuine on main; TD-636 closed), never `not_offer_letter`.

Every case of the reviewer's round-7 script is below. Synthetic twins only (`test_no_gitignored_corpus.py`).
"""
from django.test import SimpleTestCase

from apps.scholarship.genuineness.offer_reading import _folded_lines
from apps.scholarship.genuineness.offer_rulings import english_matric_offer
from apps.scholarship.tests.test_offer_h2_confirmations import KPM, KPT, _read

STD = 'Dengan ini disahkan bahawa penama di bawah adalah pelajar yang sedang mengikuti pengajian.'


def conf(head, title='PENGESAHAN PELAJAR', body=STD, extra=''):
    return f"""{head}
Jalan Contoh, 31600 Bandar Contoh
{title}
Rujukan : CONTOH/600-1/2
Tarikh : 1 Jun 2026
{body}
Nama : Ali bin Abu
No. Kad Pengenalan : 080808-10-5566
Program : Diploma Contoh
Institusi : Contoh
Bidang : Sains
{extra}
Sekian, terima kasih.
Yang benar,
PENGARAH
"""


def en(head, title, body):
    return f"""{head}
Jalan Contoh, 31600 Bandar Contoh
{title}
Ref : CONTOH/600-1/2
Date : 1 June 2026
{body}
Name : Ali bin Abu
I.C. No. : 080808-10-5566
Programme : Diploma Contoh
Faculty : Contoh

Thank you.
Yours faithfully,
REGISTRAR
"""


POLY = f'POLITEKNIK UNGKU OMAR\n{KPT}'
HEADS = (f'KOLEJ MATRIKULASI PERAK\n{KPM}', f'KOLEJ KOMUNITI KLANG\n{KPT}', f'INSTITUT PENDIDIKAN GURU KAMPUS IPOH\n{KPM}',
         f'KOLEJ VOKASIONAL KUANTAN\n{KPM}', POLY, 'UNIVERSITI PUTRA MALAYSIA\nBahagian Akademik',
         'INSTITUT KEMAHIRAN BELIA NEGARA DUSUN TUA\nKEMENTERIAN BELIA DAN SUKAN')


def _expected(head, title, want, name=''):
    """Main's live polytechnic path (its recognition rule unchanged) reads the Malay title SUSPECT whatever the body
    says - CHANGED by help H2 owner 16 Nov: all confirmations suspect (it was genuine on main, TD-636, closed);
    nothing on it moves to `not_offer_letter`. A "tawaran kemasukan" under a university head is main's UA-offer
    scorer (suspect, unchanged)."""
    if head == POLY and title == 'PENGESAHAN PELAJAR':
        return 'suspect'
    if name == 'tawaran dibatalkan' and head.startswith('UNIVERSITI'):
        return 'suspect'
    return want


#: Real campus lines under a public name (the reviewer's list): suspect, a person checks.
CAMPUS = (f'KOLEJ MATRIKULASI PERAK\nKAMPUS GOPENG\n{KPM}', f'KOLEJ MATRIKULASI PERAK\nKAMPUS PERAK\n{KPM}',
          f'KOLEJ MATRIKULASI JOHOR\nKAMPUS TANGKAK\n{KPM}', f'KOLEJ MATRIKULASI SELANGOR\nKAMPUS BANTING\n{KPM}',
          f'INSTITUT PENDIDIKAN GURU MALAYSIA\nKAMPUS IPOH\n{KPM}', f'INSTITUT PENDIDIKAN GURU\nKAMPUS TUANKU BAINUN\n{KPM}',
          f'INSTITUT PENDIDIKAN GURU\nKAMPUS PULAU PINANG\n{KPM}', f'KOLEJ KOMUNITI KUALA LANGAT\nKAMPUS BANTING\n{KPT}',
          f'KOLEJ KOMUNITI KLANG\nKAMPUS KLANG\n{KPT}', f'KOLEJ KOMUNITI SELAYANG\nCAWANGAN RAWANG\n{KPT}',
          f'POLITEKNIK SULTAN AZLAN SHAH\nKAMPUS BEHRANG\n{KPT}', f'POLITEKNIK UNGKU OMAR\nKAMPUS IPOH\n{KPT}',
          'UNIVERSITI TEKNOLOGI MALAYSIA\nKAMPUS KUALA LUMPUR', 'UNIVERSITI SAINS MALAYSIA\nKAMPUS KESIHATAN',
          'UNIVERSITI SAINS MALAYSIA\nKAMPUS KEJURUTERAAN', 'UNIVERSITI MALAYSIA SABAH\nKAMPUS ANTARABANGSA LABUAN',
          'UNIVERSITI TEKNOLOGI MARA\nKAMPUS SHAH ALAM', 'UNIVERSITI PENDIDIKAN SULTAN IDRIS\nKAMPUS SULTAN AZLAN SHAH',
          f'KOLEJ VOKASIONAL KUANTAN\nKAMPUS INDERA MAHKOTA\n{KPM}', f'INSTITUT PENDIDIKAN GURU KAMPUS IPOH\n{KPM}',
          f'KOLEJ MATRIKULASI PERAK\n{KPM}')
_CAMPUS_EN = 'This is to confirm that the person below is currently studying at this college.'

#: A current student's letter with an end date, a completion word or a footnote: suspect (never blocked).
BENIGN = (
    ('jangka', STD, 'Tarikh Jangka Tamat Pengajian : Jun 2027'),
    ('akan tamat', STD + ' Pengajian beliau akan tamat pada Jun 2027.', ''),
    ('dijangka tamat', STD + ' Beliau dijangka tamat pengajian pada Jun 2027.', ''),
    ('sehingga tamat', 'Dengan ini disahkan bahawa penama di bawah adalah pelajar sepenuh masa yang sedang mengikuti '
                       'pengajian sehingga tamat pengajian pada Jun 2027.', ''),
    ('label tamat', STD, 'Tamat Pengajian : Jun 2027'),
    ('mula dan tamat', STD, 'Tarikh Mula dan Tamat Pengajian : Jul 2025 - Jun 2027'),
    ('mula/tamat', STD, 'Tarikh Mula / Tamat Pengajian : Jul 2025 / Jun 2027'),
    ('tempoh mula-tamat', STD, 'Tempoh Pengajian : Jul 2025 hingga tamat pengajian Jun 2027'),
    ('semester result', STD + ' Beliau telah menduduki peperiksaan semester 1 dengan PNGK 3.50.', ''),
    ('void if withdraw', STD, 'Surat ini terbatal sekiranya pelajar menarik diri atau diberhentikan.'),
    ('void if berhenti', STD, 'Pengesahan ini tidak sah jika pelajar berhenti atau ditamatkan pengajian.'),
    ('telah tamat spm', STD + ' Beliau telah tamat SPM pada tahun 2024.', ''),
    ('alumni unit', STD, 'Bahagian Hal Ehwal Pelajar dan Alumni'),
    ('kakitangan contact', STD, 'Sila hubungi kakitangan kami untuk sebarang pertanyaan.'),
    ('staff email', STD, 'Emel : hep@staff.contoh.edu.my'),
    ('completed en', STD + ' The programme is expected to be completed in June 2027.', ''),
    ('graduated spm', STD + ' He graduated from SPM in 2024.', ''),
    ('sem completed', STD + ' Beliau telah completed semester 1.', ''),
    ('berhenti bas', STD, 'Pelajar menginap di asrama dan berhenti bas di hadapan kolej.'),
    ('void if graduated', STD, 'If the student has graduated, this letter is void.'),
    ('void sekiranya tamat', STD, 'Surat ini terbatal sekiranya pelajar telah tamat pengajian.'),
    ('formerly known', STD + ' The college was formerly known as Kolej Contoh.', ''),
)
#: Fully English current-student letters under a generic title (TD-635: no Malay identity labels, so they stay
#: `not_offer_letter` on main and here) - never genuine.
ENB = (
    ('CONFIRMATION LETTER', 'This is to confirm that the person below is currently studying at this college.'),
    ('LETTER OF CONFIRMATION', 'This is to confirm that the person below is a registered student of this college.'),
    ('CONFIRMATION LETTER', 'This is to confirm that the person below is a student of this college.'),
    ('CONFIRMATION LETTER', 'This is to confirm that the person below is currently studying at this college and '
                            'stays in the hostel.'),
    ('CONFIRMATION LETTER', 'This is to confirm that the person below is currently studying here. Expected '
                            'completion: June 2027.'),
    ('LETTER OF CONFIRMATION', 'This is to confirm that the person below is currently pursuing the programme, to be '
                               'completed in June 2027.'),
)
#: A generic English title with a study word in it (a bare "CONFIRMATION LETTER" is no confirmation: review 6).
GL, GO = 'CONFIRMATION LETTER (STUDENT STATUS)', 'LETTER OF CONFIRMATION - STUDENT'
#: (name, title, body, status): CHANGED by lead 16 Nov: body-word blocks removed - every body wording reads suspect
#: under a confirmation title (a person checks); only a bare generic title is no confirmation.
BAD = (
    ('hostel-currently', GL, 'This is to confirm that the person below is currently staying at '
     'the residential college (Kolej Kediaman) and has paid the fees.', 'suspect'),
    ('kediaman', 'PENGESAHAN PELAJAR', 'Dengan ini disahkan bahawa penama di bawah sedang menginap di kolej '
     'kediaman dan telah menjelaskan yuran penginapan.', 'suspect'),
    ('latihan amali', 'PENGESAHAN PELAJAR', 'Dengan ini disahkan bahawa penama di bawah sedang menjalani latihan '
     'amali di syarikat kami.', 'suspect'),
    ('praktikal', 'PENGESAHAN PELAJAR', 'Dengan ini disahkan bahawa penama di bawah sedang menjalani latihan '
     'praktikal di jabatan ini.', 'suspect'),
    ('attachment', GL, 'This is to confirm that the student below is currently undergoing an '
     'attachment programme at our office.', 'suspect'),
    ('placement', GO, 'This is to confirm that the student below is currently on placement '
     'with our company.', 'suspect'),
    ('convocation', GL, 'This is to confirm that the person below is eligible to attend the '
     'convocation ceremony and has finished the programme.', 'suspect'),
    ('lulus', 'PENGESAHAN PELAJAR', 'Dengan ini disahkan bahawa penama di bawah telah lulus dan layak '
     'dianugerahkan Diploma pada Konvokesyen 2025.', 'suspect'),
    ('sudah tamat', 'PENGESAHAN PELAJAR', 'Dengan ini disahkan bahawa penama di bawah sudah tamat pengajian pada '
     'tahun 2024.', 'suspect'),
    ('tamat (no telah)', 'PENGESAHAN PELAJAR', 'Dengan ini disahkan bahawa penama di bawah tamat pengajian pada '
     'tahun 2024.', 'suspect'),
    ('finished', 'CONFIRMATION OF STUDIES', 'This is to confirm that the person below finished the programme in '
     '2024.', 'suspect'),
    ('was a student', 'CONFIRMATION OF STUDIES', 'This is to confirm that the person below was a student of this '
     'college from 2021 to 2023.', 'suspect'),
    ('was formerly', 'CONFIRMATION OF STUDIES', 'This is to confirm that the person below was formerly enrolled '
     'at this college.', 'suspect'),
    ('pernah belajar', 'PENGESAHAN PELAJAR', 'Dengan ini disahkan bahawa penama di bawah pernah belajar di kolej '
     'ini dari 2021 hingga 2023.', 'suspect'),
    ('gagal', 'PENGESAHAN PELAJAR', 'Dengan ini dimaklumkan bahawa permohonan penama di bawah gagal dan tidak '
     'ditawarkan tempat.', 'suspect'),
    ('not offered', 'CONFIRMATION OF STUDIES', 'We regret to inform that the applicant below was not offered a '
     'place.', 'suspect'),
    ('offer withdrawn', 'CONFIRMATION OF STUDIES', 'This is to confirm that the offer of admission of the person '
     'below has been withdrawn.', 'suspect'),
    ('tawaran dibatalkan', 'PENGESAHAN PELAJAR', 'Dengan ini dimaklumkan bahawa tawaran kemasukan penama di bawah '
     'telah dibatalkan.', 'suspect'),
    ('quit', 'CONFIRMATION OF STUDIES', 'This is to confirm that the person below has quit the programme.', 'suspect'),
    ('deferred', 'PENGESAHAN PELAJAR', 'Dengan ini disahkan bahawa penama di bawah telah menangguhkan pengajian.',
     'suspect'),
    ('pensyarah', 'PENGESAHAN PELAJAR', 'Dengan ini disahkan bahawa penama di bawah adalah pensyarah tetap di '
     'kolej ini.', 'suspect'),
    ('lecturer', 'CONFIRMATION OF STUDIES', 'This is to confirm that the person below is a lecturer at this '
     'college.', 'suspect'),
    ('pegawai', 'PENGESAHAN PELAJAR', 'Dengan ini disahkan bahawa penama di bawah adalah pegawai yang berkhidmat '
     'di kolej ini.', 'suspect'),
    ('parent', 'PENGESAHAN PELAJAR', 'Dengan ini disahkan bahawa anak penama di bawah adalah pelajar yang sedang '
     'mengikuti pengajian di sini.', 'suspect'),
    ('applicant interview', 'PENGESAHAN PELAJAR', 'Dengan ini disahkan bahawa penama di bawah dipanggil untuk '
     'temuduga kemasukan.', 'suspect'),
    ('generic en no studying', 'CONFIRMATION LETTER', 'This is to confirm that the person below attended the '
     'course.', 'not_offer_letter'),
    ('generic en with a study word', GL, 'This is to confirm that the person below attended the course.', 'suspect'),
    ('studying elsewhere', 'CONFIRMATION LETTER', 'This is to confirm that the person below is currently studying '
     'at Mercu College Sdn Bhd and is our sponsored student.', 'not_offer_letter'),
    ('hostel en studying', GO, 'This is to confirm that the person below is currently '
     'studying here and has been given a room at the Residential College.', 'suspect'),
    ('intern ms generic', GO, 'This is to confirm that the person below is currently '
     'studying here and will do latihan industri.', 'suspect'),
)
#: The SUBJECT of the letter is a hostel / staff / convocation / interview matter, or an internship with no study
#: word: it blocks.
SUBJECTS = ('Perkara : Pengesahan Penginapan Asrama', 'RE: CONFIRMATION OF INTERNSHIP', 'Per: Konvokesyen 2026',
            'SUBJECT: STAFF CONFIRMATION', 'PERKARA : TEMUDUGA KEMASUKAN', 'Tajuk : Latihan Industri')
SUBJECT_TITLES = ('CONFIRMATION LETTER - HOSTEL', 'CONFIRMATION LETTER - STUDENT HOSTEL',
                  'LETTER OF CONFIRMATION OF INTERNSHIP', 'PENGESAHAN PELAJAR BAGI TUJUAN KONVOKESYEN')
#: CHANGED by lead 16 Nov: an internship title WITH a study word is the student's own confirmation: suspect.
STUDENT_INTERNSHIP_TITLES = ('PENGESAHAN PELAJAR (LATIHAN INDUSTRI)', 'PENGESAHAN PELAJAR SEDANG MENJALANI LATIHAN '
                             'INDUSTRI', 'CONFIRMATION OF STUDENT STATUS - INTERNSHIP')


class TheReviewersCampusLines(SimpleTestCase):
    def test_every_campus_line_under_a_public_name_reads_suspect(self):
        for head in CAMPUS:
            for title, body in (('PENGESAHAN PELAJAR', STD), ('CONFIRMATION OF STUDIES', _CAMPUS_EN)):
                with self.subTest(head=head, title=title):
                    self.assertEqual(_read(conf(head, title, body))['status'], 'suspect')


class CurrentStudentsAreNeverBlocked(SimpleTestCase):
    def test_end_dates_completion_words_and_footnotes_read_suspect(self):
        for name, body, extra in BENIGN:
            for head in HEADS:
                with self.subTest(name, head=head.splitlines()[0]):
                    want = _expected(head, 'PENGESAHAN PELAJAR', 'suspect')
                    self.assertEqual(_read(conf(head, 'PENGESAHAN PELAJAR', body, extra))['status'], want)

    def test_the_student_affairs_and_alumni_letterhead_reads_suspect(self):
        for head in ('UNIVERSITI PUTRA MALAYSIA\nBahagian Hal Ehwal Pelajar dan Alumni',
                     f'KOLEJ KOMUNITI KLANG\nUnit Hal Ehwal Pelajar dan Alumni\n{KPT}'):
            with self.subTest(head=head):
                self.assertEqual(_read(conf(head))['status'], 'suspect')

    def test_a_fully_english_letter_never_reads_genuine_td_635(self):
        for title, body in ENB:
            for head in HEADS:
                for crest in (False, True):
                    with self.subTest(body=body[:40], head=head.splitlines()[0], crest=crest):
                        self.assertNotEqual(_read(en(head, title, body), crest)['status'], 'genuine')


class OnlyTheTitleBlockBlocks(SimpleTestCase):
    def test_the_reviewers_non_study_letters(self):
        for name, title, body, want in BAD:
            for head in HEADS:
                with self.subTest(name, head=head.splitlines()[0]):
                    self.assertEqual(_read(conf(head, title, body))['status'], _expected(head, title, want, name))

    def test_a_non_study_subject_blocks(self):
        for head in HEADS:
            for subject in SUBJECTS:
                with self.subTest(subject, head=head.splitlines()[0]):
                    text = conf(head).replace('Tarikh : 1 Jun 2026', f'Tarikh : 1 Jun 2026\n{subject}')
                    self.assertEqual(_read(text)['status'], _expected(head, 'PENGESAHAN PELAJAR', 'not_offer_letter'))
            for title in SUBJECT_TITLES:
                # main's live polytechnic rule recognises the Malay title: suspect (owner 16 Nov), never a block
                want = 'suspect' if head == POLY and title.startswith('PENGESAHAN PELAJAR') else 'not_offer_letter'
                with self.subTest(title, head=head.splitlines()[0]):
                    self.assertEqual(_read(conf(head, title))['status'], want)

    def test_a_students_internship_title_reads_suspect(self):
        for head in HEADS:
            for title in STUDENT_INTERNSHIP_TITLES:
                with self.subTest(title, head=head.splitlines()[0]):
                    self.assertEqual(_read(conf(head, title))['status'], 'suspect')

    def test_a_non_study_word_in_the_body_never_blocks(self):
        body = STD + ' Beliau menginap di asrama dan akan menjalani latihan industri. Hubungi kakitangan kami.'
        for head in HEADS:
            with self.subTest(head=head.splitlines()[0]):
                self.assertEqual(_read(conf(head, 'PENGESAHAN PELAJAR', body))['status'], 'suspect')


#: KPM's English matric offer (the reviewer's script).
M = """KEMENTERIAN PENDIDIKAN MALAYSIA
MINISTRY OF EDUCATION MALAYSIA
MATRICULATION DIVISION
Ref : KPM.600-1/2/3
Date : 1 June 2026
OFFER OF ADMISSION TO THE MATRICULATION PROGRAMME, MINISTRY OF EDUCATION MALAYSIA
Name : Ali bin Abu
Stream : Science
College : Kolej Matrikulasi Contoh
Date of registration : 3 August 2026
You must register on the date set by the college.
This offer will be cancelled immediately if you fail to register.
Director
Matriculation Division
"""
_R = 'You must register on the date set by the college.'
#: A refusal, cancellation or rejection form on the TITLE line: no offer.
MATRIC_NOT_AN_OFFER = {
    'cancellation': M.replace('OFFER OF ADMISSION TO', 'CANCELLATION OF OFFER OF ADMISSION TO'),
    'rejection of offer form': M.replace('OFFER OF ADMISSION TO', 'FORM OF REJECTION OF OFFER OF ADMISSION TO'),
    'withdrawal': M.replace('OFFER OF ADMISSION TO', 'WITHDRAWAL OF OFFER OF ADMISSION TO'),
    'appeal': M.replace('OFFER OF ADMISSION TO', 'APPEAL FOR OFFER OF ADMISSION TO'),
    'unsuccessful': M.replace('OFFER OF ADMISSION TO', 'UNSUCCESSFUL APPLICATION FOR OFFER OF ADMISSION TO'),
}
#: CHANGED by lead 16 Nov: body-word blocks removed - a refusal or a waiting list said in the BODY reads suspect
#: (still recognised, never a course pick); a person checks.
MATRIC_BODY_SUSPECT = {
    'withdrawn': M.replace(_R, 'Your OFFER OF ADMISSION has been WITHDRAWN because you did not register.'),
    'not selected': M.replace(_R, 'We are sorry to inform you that you have not been selected.'),
    'waiting list': M.replace(_R, 'You have been placed on the waiting list (senarai menunggu).'),
    'declined': M.replace(_R, 'You have declined this offer. Your place is released.'),
    'sorry': M.replace(_R, 'We are sorry, your application did not succeed.'),
    'unfortunately': M.replace(_R, 'Unfortunately you are not eligible for the programme.'),
    'tidak layak': M.replace(_R, 'Anda tidak layak untuk program ini.'),
}
MATRIC_OFFER = {
    'plain': M,
    'reminder register': M.replace(_R, 'Reminder: please register; you have not yet registered.'),
    'congrats': M.replace(_R, 'Congratulations, we are pleased to offer you a place.'),
}


class TheEnglishMatricOffer(SimpleTestCase):
    def test_a_cancellation_or_rejection_title_is_no_offer(self):
        for name, text in MATRIC_NOT_AN_OFFER.items():
            with self.subTest(name):
                self.assertFalse(english_matric_offer(_folded_lines(text)))
                for crest in (False, True):
                    self.assertEqual(_read(text, crest)['status'], 'not_offer_letter')

    def test_a_refusal_in_the_body_reads_suspect_never_genuine(self):
        for name, text in MATRIC_BODY_SUSPECT.items():
            for crest in (False, True):
                with self.subTest(name, crest=crest):
                    out = _read(text, crest)
                    self.assertEqual((out['status'], out['type']), ('suspect', 'matric_offer_en'))

    def test_an_offer_and_its_footnote_read_suspect(self):
        # "cancelled immediately IF you fail to register" is a condition: it never blocks
        for name, text in MATRIC_OFFER.items():
            with self.subTest(name):
                out = _read(text)
                self.assertEqual((out['status'], out['type']), ('suspect', 'matric_offer_en'))
