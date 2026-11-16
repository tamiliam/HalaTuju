"""Help H2 review 10 (16 Nov 2026): a confirmation TITLE is a LINE, not a phrase in a sentence.

The CAP (and widened recognition) count a confirmation title only when it starts its own short line (after an optional
SURAT / PERKARA: / RE:) and comes before the first offer title line (TAWARAN / OFFER / KEPUTUSAN PERMOHONAN /
KEMASUKAN KE PROGRAM, incl. OCR-glued SURATTAWARAN). A confirmation phrase inside a body sentence never caps.
H1: a body sentence on a matric offer ("Sila kembalikan Borang Pengesahan Pelajar ...") turned a genuine offer into a
suspect confirmation, and a short letter's whole page was its "title block" (the 400-character floor).
H2: an offer titled KEPUTUSAN PERMOHONAN / KEMASUKAN KE PROGRAM / SURATTAWARAN with such a sentence in its top half
was capped or recoded. L: a genuine result carrying a confirmation code was returned uncapped.
Synthetic twins only (`test_no_gitignored_corpus.py`): every letter is invented, no real name or IC.
"""
from django.test import SimpleTestCase

from apps.scholarship.genuineness.offer_confirm_checks import cap_confirmation, page_titled, title_block
from apps.scholarship.genuineness.offer_confirmations import CONFIRMATION_SEEN
from apps.scholarship.genuineness.offer_reading import _folded_lines
from apps.scholarship.tests.test_corpus_gaps_c2 import UITM_OFFER
from apps.scholarship.tests.test_offer_h2_confirmations import MATRIC_MS, _read, _verdict
from apps.scholarship.tests.test_offer_rulings import IKM, _confirm

#: The reviewer's two body sentences (h2r10/syn.py).
RETURN_FORM = 'Sila kembalikan Borang Pengesahan Pelajar yang telah dilengkapkan.'
LATER_LETTER = 'Surat Pengesahan Status Pengajian akan dikeluarkan selepas pendaftaran.'
BODY = (RETURN_FORM, LATER_LETTER, 'Sila bawa Surat Pengesahan Pengajian semasa pendaftaran.',
        'Borang Status Pengajian hendaklah diisi oleh pelajar.', 'Pengesahan Pelajar akan dibuat oleh pihak kolej.')
_KOLEJ = 'Kolej : Kolej Matrikulasi Contoh\n'
#: The three offer titles the old CAP read past (review 10 H2), in place of UiTM's "SURAT TAWARAN".
OFFER_TITLES = ('KEPUTUSAN PERMOHONAN KEMASUKAN', 'KEMASUKAN KE PROGRAM DIPLOMA SESI 2026/2027', 'SURATTAWARAN')


def _shape(text):
    out = _read(text)
    return out['status'], out['type']


class H1ABodySentenceOnAMatricOfferIsNoCap(SimpleTestCase):
    def test_the_reviewers_two_sentences_leave_the_offer_genuine(self):
        for text in (MATRIC_MS.replace(_KOLEJ, _KOLEJ + RETURN_FORM + '\n'), MATRIC_MS + LATER_LETTER + '\n'):
            for crest in (False, True):
                with self.subTest(text[-60:], crest=crest):
                    self.assertEqual(_verdict(text, crest)[:2], _verdict(MATRIC_MS, crest)[:2])
                    self.assertEqual(_read(text, crest)['status'], 'genuine')

    def test_every_body_sentence_anywhere_leaves_the_offer_as_it_was(self):
        lines = MATRIC_MS.splitlines(keepends=True)
        for sentence in BODY:
            for at in range(3, len(lines) + 1):
                text = ''.join(lines[:at]) + sentence + '\n' + ''.join(lines[at:])
                with self.subTest(sentence, at=at):
                    self.assertFalse(page_titled(_folded_lines(text)))
                    self.assertEqual(_shape(text), _shape(MATRIC_MS))

    def test_a_short_letters_title_block_is_not_its_whole_page(self):
        lines = _folded_lines(MATRIC_MS + LATER_LETTER + '\n')
        block = title_block(lines)
        self.assertLess(len(block), sum(len(ln) for ln in lines))
        self.assertNotIn(' DIKELUARKAN ', block)

    def test_the_same_sentences_on_a_tvet_offer_change_nothing(self):
        for sentence in BODY:
            text = IKM.replace('Nama : Ali bin Abu\n', f'Nama : Ali bin Abu\n{sentence}\n')
            with self.subTest(sentence):
                self.assertEqual(_shape(text), _shape(IKM))


class H2OfferTitlesEndTheSearch(SimpleTestCase):
    def test_each_offer_title_with_a_body_sentence_reads_as_without_it(self):
        for title in OFFER_TITLES:
            base = UITM_OFFER.replace('SURAT TAWARAN\n', f'{title}\n')
            for sentence in BODY:
                text = base.replace('Program :\n', f'Program :\n{sentence}\n')
                for crest in (False, True):
                    with self.subTest(title, sentence=sentence, crest=crest):
                        self.assertFalse(page_titled(_folded_lines(text)))
                        self.assertEqual(_verdict(text, crest)[:2], _verdict(base, crest)[:2])

    def test_a_confirmation_title_line_below_an_offer_title_is_no_cap(self):
        for title in OFFER_TITLES:
            text = UITM_OFFER.replace('SURAT TAWARAN\n', f'{title}\nPENGESAHAN PELAJAR\n')
            with self.subTest(title):
                self.assertFalse(page_titled(_folded_lines(text)))

    def test_ditawarkan_in_a_sentence_is_not_an_offer_title(self):
        text = _confirm('UNIVERSITI PUTRA MALAYSIA\nBahagian Akademik').replace(
            'PENGESAHAN PELAJAR', 'Penama telah ditawarkan tempat.\nPENGESAHAN PELAJAR')
        self.assertTrue(page_titled(_folded_lines(text)))
        self.assertEqual(_read(text)['status'], 'suspect')


class ATitleIsALine(SimpleTestCase):
    def _lines(self, title):
        return _folded_lines(UITM_OFFER.replace('SURAT TAWARAN\n', f'{title}\nSURAT TAWARAN\n'))

    def test_a_short_title_line_caps(self):
        for title in ('PENGESAHAN PELAJAR', 'SURAT PENGESAHAN PELAJAR', 'PERKARA : PENGESAHAN STATUS PELAJAR',
                      'RE : CONFIRMATION OF STUDIES', 'SURAT PENGESAHAN\nSTATUS PELAJAR'):
            with self.subTest(title):
                self.assertTrue(page_titled(self._lines(title)))

    def test_a_confirmation_phrase_mid_sentence_never_caps(self):
        for sentence in BODY + ('Untuk Pengesahan Pelajar sila hubungi pejabat.',
                                'The Confirmation of Studies will be issued after registration.'):
            with self.subTest(sentence):
                self.assertFalse(page_titled(self._lines(sentence)))

    def test_a_sentence_starting_with_the_title_words_never_caps(self):
        for sentence in ('Pengesahan Pelajar akan dibuat oleh pihak kolej selepas pendaftaran.',
                         'Confirmation of studies will be issued after registration.'):
            with self.subTest(sentence):
                self.assertFalse(page_titled(self._lines(sentence)))


class LAGenuineConfirmationCodeIsAlwaysCapped(SimpleTestCase):
    def test_a_genuine_result_with_a_confirmation_code_reads_suspect_whatever_the_page(self):
        lines = _folded_lines(UITM_OFFER)                      # no confirmation title on the page at all
        r = {'probability': 0.9, 'present': [], 'missing': []}
        for seen in sorted(CONFIRMATION_SEEN):
            with self.subTest(seen):
                out = cap_confirmation(lines, {'status': 'genuine', 'type': seen, 'probability': 0.9}, r, 'v')
                self.assertEqual(out['status'], 'suspect')
                self.assertEqual(out['type'], seen)

    def test_a_suspect_confirmation_is_returned_as_it_is(self):
        result = {'status': 'suspect', 'type': 'confirmation_ua', 'probability': 0.4}
        self.assertIs(cap_confirmation(_folded_lines(UITM_OFFER), result, {}, 'v'), result)
