"""Help H2 review 9 (16 Nov 2026): the CAP reads the whole page, a suspect confirmation never keeps a pick-writing
code, and the English matric title line is the line holding its title.

H1: a line above the title ("Kepada:", "Pihak Yang Berkenaan", "Tuan/Puan,", "Kami ...", "WE ...", "I") ended the
title block, and a title split over two lines was never seen, so the CAP was skipped and a TVET lift or a genuine
`ua_offer` baseline stayed genuine. The CAP now reads the page as main's `_confirm_titled` does (`page_titled`).
H2: a confirmation-titled page that reads suspect on its own score, but that no confirmation rule names, kept
`ua_offer` and could write a pick: the CAP now gives it the confirmation code and leaves its status alone.
M1: an "OFFER LETTER" header above the English matric title was taken as its title line.
Synthetic twins only (`test_no_gitignored_corpus.py`): every letter is invented, no real name or IC.
"""
from django.test import SimpleTestCase, TestCase

from apps.scholarship.genuineness.offer_confirm_checks import cap_confirmation, page_titled
from apps.scholarship.genuineness.offer_confirmations import CONFIRMATION_SEEN, MATRIC_OFFER_EN
from apps.scholarship.genuineness.offer_reading import _folded_lines
from apps.scholarship.pathway_engine import is_confirmation_letter, student_offer_check
from apps.scholarship.tests.factories import make_application
from apps.scholarship.tests.test_offer_h2_confirmations import KPM, KPT, MATRIC_EN, MATRIC_MS, _read, _verdict
from apps.scholarship.tests.test_offer_rulings import IKM
from apps.scholarship.tests.test_offer_s6_doors import _offer

#: The real TVET MARA shape (snapshot d3494): the agency's line, the title near the top, the offer words below.
TVET_TWIN = 'TVETMARA\n' + IKM.replace('SURAT TAWARAN\n', 'PENGESAHAN PELAJAR\n').replace(
    'PENGARAH\n', 'Rujuk SURAT TAWARAN asal.\nPENGARAH\n')
#: Lines that ended the title block above the title (review 9).
ABOVE = ('Kepada:\nPihak Yang Berkenaan\nTuan/Puan,', 'Kami Sedia Membantu', 'WE CARE WE SHARE', 'I',
         'Adalah Dimaklumkan', 'Kepada Sesiapa Yang Berkenaan\nTuan/Puan,', 'TO WHOM IT MAY CONCERN\nDear Sir/Madam,',
         'Saya Yang Menurut Perintah')
SPLIT = ('SURAT PENGESAHAN\nSTATUS PELAJAR', 'CONFIRMATION OF\nSTUDENT STATUS')
#: A university's offer words below a confirmation title (the reviewer's p3 shape: a genuine `ua_offer` without it).
_SIG = ('Tawaran Kemasukan Ke Program Ijazah Sarjana Muda\nSesi Akademik 2025/2026\nNo. Matrik : BS25110001\n'
        'Yuran Pengajian RM 500\nTarikh Pendaftaran : 1 Julai 2025\nNaib Canselor\nBahagian Pengurusan Akademik\n'
        'Program Pengajian : Ijazah\nKampus Utama\nwww.contoh.edu.my')
HEADS = {'UPM': 'UNIVERSITI PUTRA MALAYSIA\nBahagian Akademik', 'UM': 'UNIVERSITI MALAYA\nJabatan Pendaftar',
         'UMS': 'UNIVERSITI MALAYSIA SABAH\nJabatan Hal Ehwal Akademik',
         'IKBN': 'INSTITUT KEMAHIRAN BELIA NEGARA DUSUN TUA\nKEMENTERIAN BELIA DAN SUKAN'}


def _ua(head, pre, title, body='Dengan ini disahkan bahawa penama di bawah adalah pelajar yang sedang mengikuti '
                               'pengajian.'):
    return (f'{head}\nJalan Contoh, 31600 Bandar Contoh\nRujukan : CONTOH/600-1/2\nTarikh : 1 Jun 2026\n{pre}\n'
            f'{title}\n{body}\nNama : Ali bin Abu\nNo. Kad Pengenalan : 080808-10-5566\nProgram : Ijazah Contoh\n'
            f'{_SIG}\nSekian, terima kasih.\nYang benar,\nPENDAFTAR\n')


def _matric_en(pre='', ic=True):
    """MATRIC_EN with the reviewer's extra lines (the Malay Division name, an IC line): the family reads it."""
    text = MATRIC_EN.replace('MATRICULATION DIVISION\nRef', 'MATRICULATION DIVISION\nBAHAGIAN MATRIKULASI\nRef')
    if ic:
        text = text.replace('Name : Ali bin Abu\n', 'Name : Ali bin Abu\nI.C. No. : 080808-10-5566\n')
    return text.replace('OFFER OF ADMISSION TO THE', pre + 'OFFER OF ADMISSION TO THE', 1)


class TheCapReadsTheWholePage(SimpleTestCase):
    """H1."""

    def test_the_tvet_twin_is_genuine_without_its_title(self):
        self.assertEqual(_read(TVET_TWIN.replace('PENGESAHAN PELAJAR\n', 'MAKLUMAN\n'))['status'], 'genuine')

    def test_a_line_above_the_title_never_skips_the_cap(self):
        for above in ABOVE:
            text = TVET_TWIN.replace('PENGESAHAN PELAJAR\n', f'{above}\nPENGESAHAN PELAJAR\n')
            for crest in (False, True):
                with self.subTest(above, crest=crest):
                    self.assertTrue(page_titled(_folded_lines(text)))
                    self.assertEqual(_verdict(text, crest), ('suspect', 'confirmation_tvet', 'confirmation_check'))

    def test_a_title_split_over_two_lines_never_skips_the_cap(self):
        for title in SPLIT:
            text = TVET_TWIN.replace('PENGESAHAN PELAJAR\n', f'{title}\n')
            for crest in (False, True):
                with self.subTest(title, crest=crest):
                    self.assertEqual(_verdict(text, crest), ('suspect', 'confirmation_tvet', 'confirmation_check'))

    def test_a_university_or_ikbn_confirmation_is_never_genuine_and_never_a_pick_code(self):
        for name, head in HEADS.items():
            for pre in ('',) + ABOVE:
                for title in ('PENGESAHAN PELAJAR', 'CONFIRMATION OF STUDENT STATUS') + SPLIT:
                    text = _ua(head, pre, title)
                    with self.subTest(name, pre=pre, title=title):
                        out = _read(text, True)
                        self.assertEqual(out['status'], 'suspect')
                        self.assertIn(out['type'], CONFIRMATION_SEEN)

    def test_the_university_offer_without_a_title_is_still_genuine(self):
        self.assertEqual(_read(_ua(HEADS['UPM'], '', 'MAKLUMAN'), True)['status'], 'genuine')

    def test_a_title_below_the_offer_title_or_low_on_the_page_is_no_cap(self):
        text = _ua(HEADS['UPM'], '', 'MAKLUMAN').replace('PENDAFTAR\n', 'PENDAFTAR\nsk: PENGESAHAN PELAJAR\n')
        self.assertFalse(page_titled(_folded_lines(text)))
        self.assertEqual(_read(text, True)['status'], 'genuine')


#: The reviewer's p4 shape: a matric college / polytechnic letterhead, a confirmation title, a subject line.
def _own_score(head, subject='', ident=True):
    idl = 'Nama : Ali bin Abu\nNo. Kad Pengenalan : 080808-10-5566\n' if ident else 'Penama: Ali bin Abu\n'
    return (f'{head}\nJalan Contoh, 31600 Bandar Contoh\nRujukan : CONTOH/600-1/2\nTarikh : 1 Jun 2026\n'
            f'PENGESAHAN PELAJAR\n{subject}\nDengan ini disahkan bahawa penama di bawah adalah pelajar yang sedang '
            f'mengikuti pengajian.\n{idl}Program : Ijazah Contoh\n{_SIG}\nSekian, terima kasih.\nYang benar,\n'
            'PENDAFTAR\n')


OWN_SCORE = [(f'KOLEJ MATRIKULASI PERAK\n{KPM}', s, i) for s in ('', 'PERKARA: PENEMPATAN LATIHAN INDUSTRI',
                                                                 'PERKARA: PERMOHONAN ASRAMA') for i in (True, False)
             if s or not i] + [(f'POLITEKNIK UNGKU OMAR\n{KPT}', s, False)
                               for s in ('', 'PERKARA: PENEMPATAN LATIHAN INDUSTRI', 'PERKARA: PERMOHONAN ASRAMA')]


class ASuspectConfirmationTakesTheConfirmationCode(SimpleTestCase):
    """H2: the status stays (suspect on its own score); only the code changes."""

    def test_every_one_reads_suspect_with_a_confirmation_code(self):
        for head, subject, ident in OWN_SCORE:
            for crest in (False, True):
                with self.subTest(head.splitlines()[0], subject=subject, ident=ident, crest=crest):
                    out = _read(_own_score(head, subject, ident), crest)
                    self.assertEqual(out['status'], 'suspect')
                    self.assertIn(out['type'], CONFIRMATION_SEEN)

    def test_a_not_offer_letter_stays_one(self):
        lines = _folded_lines(_own_score(f'KOLEJ MATRIKULASI PERAK\n{KPM}'))
        result = {'status': 'not_offer_letter', 'type': 'ua_offer', 'reason': 'x'}
        self.assertTrue(page_titled(lines))
        self.assertIs(cap_confirmation(lines, result, {}, 'v'), result)

    def test_a_suspect_one_keeps_its_status_and_score(self):
        lines = _folded_lines(_own_score(f'KOLEJ MATRIKULASI PERAK\n{KPM}'))
        out = cap_confirmation(lines, {'status': 'suspect', 'type': 'ua_offer', 'probability': 0.4}, {}, 'v')
        self.assertEqual((out['status'], out['probability']), ('suspect', 0.4))
        self.assertIn(out['type'], CONFIRMATION_SEEN)
        self.assertTrue(out['reason'].startswith('[S6 ruling: confirmation_ua]'))


class TheEnglishMatricTitleLine(SimpleTestCase):
    """M1."""

    def test_a_header_above_the_title_is_not_its_title_line(self):
        for pre in ('OFFER LETTER\n', 'SURAT TAWARAN / OFFER LETTER\n', 'Congratulations! You have received an offer.\n'):
            for text in (MATRIC_EN.replace('OFFER OF ADMISSION TO THE', pre + 'OFFER OF ADMISSION TO THE'),
                         _matric_en(pre)):
                for crest in (False, True):
                    with self.subTest(pre, crest=crest):
                        self.assertEqual(_verdict(text, crest), ('suspect', MATRIC_OFFER_EN, 'matric_offer_en'))

    def test_a_refused_title_line_never_keeps_the_family_code(self):
        # the title line names an appeal: no English matric reading, but the family's suspect read takes the
        # never-a-pick code (settled rule: an English matric offer is suspect at most, never a pick)
        for crest in (False, True):
            with self.subTest(crest=crest):
                out = _read(_matric_en('APPEAL RESULT: '), crest)
                if out['status'] != 'not_offer_letter':
                    self.assertEqual((out['status'], out['type']), ('suspect', MATRIC_OFFER_EN))

    def test_the_malay_offer_is_unchanged(self):
        out = _read(MATRIC_MS)
        self.assertEqual((out['status'], out['type']), ('genuine', 'matriculation'))


class NoneWritesACoursePick(TestCase):
    def _no_pick(self, text, crest=True):
        from apps.scholarship.services.offer_link import plan_offer_link
        from apps.scholarship.services.offer_sync import autofill_pathway_from_offer
        out = _read(text, crest)
        self.assertEqual(out['status'], 'suspect')
        app = make_application('shortlisted', chosen_pathway='matric', chosen_programme={})
        doc = _offer(app, out['status'], doc_seen=out['type'], institution='KOLEJ MATRIKULASI PERAK',
                     programme='PROGRAM MATRIKULASI SAINS')
        self.assertTrue(is_confirmation_letter(doc))
        self.assertEqual(plan_offer_link(app, doc, student_offer_check(doc))[0], 'confirmation_letter')
        autofill_pathway_from_offer(app)
        app.refresh_from_db()
        cp = app.chosen_programme if isinstance(app.chosen_programme, dict) else {}
        self.assertFalse((cp.get('course_name') or '').strip())

    def test_the_review_9_letters_write_no_pick(self):
        for name, text in (('tvet, a line above', TVET_TWIN.replace('PENGESAHAN PELAJAR\n', 'Kepada:\nTuan/Puan,\n'
                                                                                           'PENGESAHAN PELAJAR\n')),
                           ('university, split title', _ua(HEADS['UM'], '', SPLIT[0])),
                           ('matric college, hostel subject', _own_score(f'KOLEJ MATRIKULASI PERAK\n{KPM}',
                                                                         'PERKARA: PERMOHONAN ASRAMA')),
                           ('polytechnic, no own IC line', _own_score(f'POLITEKNIK UNGKU OMAR\n{KPT}', ident=False)),
                           ('english matric, a header above', _matric_en('OFFER LETTER\n'))):
            with self.subTest(name):
                self._no_pick(text)
