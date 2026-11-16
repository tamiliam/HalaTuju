"""Help H2, the lead's decision of 16 Nov 2026: a confirmation of studies is read on its TITLE BLOCK only, and a
confirmation title there CAPS the verdict at suspect, whatever ruled it genuine (gate (d), `cap_confirmation`).

Closes the two leaks the replay found: a TVET / agency lift (real snapshot d3494, a TVETMARA "PENGESAHAN PELAJAR"
under the salutation) and a genuine `ua_offer` baseline. Synthetic twins only (`test_no_gitignored_corpus.py`).
"""
from django.test import SimpleTestCase

from apps.scholarship.genuineness.offer_confirmations import CONFIRMATION_SEEN
from apps.scholarship.genuineness.offer_reading import _folded_lines
from apps.scholarship.genuineness.offer_confirm_checks import non_study_subject, page_titled
from apps.scholarship.tests.test_corpus_gaps_c2 import UITM_OFFER
from apps.scholarship.tests.test_offer_h2_confirmations import KPT, _read, _verdict
from apps.scholarship.tests.test_offer_rulings import IKM, _confirm

#: d3494's shape: a TVET letterhead, a salutation, then the confirmation title (genuine by the TVET lift alone).
#: Review 10: no offer title line above it (d3494 has none; a title below an offer title line is no cap).
TVET_CONFIRM = 'TVETMARA\n' + IKM.replace('SURAT TAWARAN\n', 'Tuan / Puan,\nPENGESAHAN PELAJAR\n').replace(
    'PENGARAH\n', 'Rujuk SURAT TAWARAN asal.\nPENGARAH\n')
#: A university's offer shape under a confirmation title (the genuine `ua_offer` baseline: genuine without the CAP).
UA_CONFIRM = UITM_OFFER.replace('SURAT TAWARAN\n', 'SURAT PENGESAHAN PELAJAR\n')


class TheCapHoldsEveryConfirmationAtSuspect(SimpleTestCase):
    def test_the_offers_they_copy_are_still_genuine(self):
        self.assertEqual(_read(IKM)['status'], 'genuine')
        self.assertEqual(_read(UITM_OFFER)['status'], 'genuine')

    def test_a_tvet_confirmation_after_the_salutation_reads_suspect(self):
        for text in (TVET_CONFIRM, TVET_CONFIRM.replace('TVETMARA\n', '')):
            for crest in (False, True):
                with self.subTest(crest=crest):
                    self.assertEqual(_verdict(text, crest), ('suspect', 'confirmation_tvet', 'confirmation_check'))

    def test_a_genuine_university_baseline_under_a_confirmation_title_reads_suspect(self):
        for crest in (False, True):
            with self.subTest(crest=crest):
                status, seen, _ruling = _verdict(UA_CONFIRM, crest)
                self.assertEqual(status, 'suspect')
                self.assertIn(seen, CONFIRMATION_SEEN)         # never a course pick

    def test_a_confirmation_word_in_an_offers_body_is_no_cap(self):
        text = UITM_OFFER.replace('PENGARAH\n', 'Sila bawa surat PENGESAHAN PELAJAR sekolah semasa mendaftar.\n'
                                              'PENGARAH\n')
        self.assertFalse(page_titled(_folded_lines(text)))
        self.assertEqual(_read(text)['status'], 'genuine')


class TheNewTitlesReadSuspect(SimpleTestCase):
    def test_every_specific_title_reads_suspect(self):
        for title in ('SURAT PENGESAHAN PENGAJIAN', 'SURAT PENGESAHAN BELAJAR', 'PENGESAHAN STATUS PELAJAR',
                      'CONFIRMATION OF STUDY', 'CONFIRMATION OF ENROLMENT', 'LETTER OF ENROLMENT VERIFICATION'):
            for head in (f'KOLEJ KOMUNITI KLANG\n{KPT}', 'UNIVERSITI PUTRA MALAYSIA\nBahagian Akademik'):
                with self.subTest(title, head=head.splitlines()[0]):
                    self.assertEqual(_read(_confirm(head).replace('PENGESAHAN PELAJAR', title))['status'], 'suspect')


class OnlyTheSubjectLineIsRead(SimpleTestCase):
    def _with(self, subject, body_extra=''):
        text = _confirm('UNIVERSITI PUTRA MALAYSIA\nBahagian Akademik')
        text = text.replace('Tarikh : 1 Jun 2026\n', f'Tarikh : 1 Jun 2026\n{subject}\n')
        return text.replace('Sekian, terima kasih.', f'{body_extra}\nSekian, terima kasih.')

    def test_a_non_study_subject_is_no_confirmation(self):
        for subject in ('PERKARA : PENGESAHAN KEDIAMAN ASRAMA', 'RE : STAFF CONFIRMATION', 'PERKARA : LATIHAN INDUSTRI',
                        'SUBJECT : CONVOCATION 2026', 'PERKARA : TEMUDUGA KEMASUKAN', 'PERKARA : CUTI BELAJAR'):
            with self.subTest(subject):
                self.assertTrue(non_study_subject(_folded_lines(self._with(subject))))
                self.assertEqual(_read(self._with(subject))['status'], 'not_offer_letter')

    def test_a_students_internship_subject_reads_suspect(self):
        text = self._with('PERKARA : PENGESAHAN PELAJAR SEDANG MENJALANI LATIHAN INDUSTRI')
        self.assertEqual(_read(text)['status'], 'suspect')

    def test_the_same_words_in_the_body_never_block(self):
        text = self._with('PERKARA : PENGESAHAN PELAJAR', 'Beliau tinggal di asrama, akan menjalani latihan industri '
                                                         'dan bukan kakitangan kami.')
        self.assertFalse(non_study_subject(_folded_lines(text)))
        self.assertEqual(_read(text)['status'], 'suspect')
