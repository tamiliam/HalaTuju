"""Help H2 review 12 (16 Nov 2026): a body SENTENCE that starts with a confirmation phrase is no title line.

Review 11 let any single body word (`_BODY_CUTS`: ADALAH, KAMI, PIHAK, PLEASE, WE, HEREBY ...) end a confirmation
title's rest BEFORE the sentence-word check, so "Pengesahan pelajar kami akan dikeluarkan selepas pendaftaran" on an
ordinary offer read as a confirmation title and capped it (the reviewer's insert probe: 885 offers genuine ->
suspect). Now only a MULTI-WORD glued opening ends the rest (`_GLUED_BODY`: "ADALAH DIMAKLUMKAN", "DENGAN
HORMATNYA", "THIS IS TO CERTIFY" ...), so such a sentence reads as a sentence again and the offer reads as on main.
Synthetic letters only (`test_no_gitignored_corpus.py`): every name and number is invented.
"""
from django.test import SimpleTestCase

from apps.scholarship.genuineness.offer_confirm_checks import page_titled
from apps.scholarship.genuineness.offer_reading import _folded_lines
from apps.scholarship.tests.test_corpus_gaps_c2 import UITM_OFFER
from apps.scholarship.tests.test_doc_signatures import GENUINE_MATRIC_OFFER, GENUINE_POLY_OFFER, UNIVERSITY_OFFER
from apps.scholarship.tests.test_offer_h2_confirmations import _verdict
from apps.scholarship.tests.test_offer_h2_review11 import _Caps

#: The reviewer's four sentences (review 12), then the rest of the h2r12 insert probe's phrases.
REVIEW12 = ('Pengesahan pelajar kami akan dikeluarkan selepas pendaftaran',
            'Pengesahan pelajar adalah diperlukan bagi tujuan permohonan pinjaman pendidikan',
            'Confirmation of Study please contact the registrar after registration',
            'Pengesahan Status Pengajian pihak universiti akan dikeluarkan selepas pendaftaran')
MORE = ('Pengesahan pelajar adalah diperlukan', 'Pengesahan pelajar disahkan oleh Pendaftar selepas pendaftaran',
        '3. Pengesahan pelajar adalah diperlukan bagi tujuan pinjaman',
        'Confirmation of enrolment we will issue upon registration',
        'Confirmation of studies hereby issued upon request after registration')
#: Ordinary offers and their offer title line (the sentence goes above it, under it and on line 2).
OFFERS = ((UITM_OFFER, 'SURAT TAWARAN'),
          (GENUINE_MATRIC_OFFER, 'TAWARAN KEMASUKAN PROGRAM MATRIKULASI'),
          (GENUINE_POLY_OFFER, 'SURAT TAWARAN PENGAJIAN'),
          (UNIVERSITY_OFFER, 'TAWARAN KEMASUKAN PROGRAM ASASI'))


def _inserted(offer, title, sentence):
    lines = offer.splitlines()
    at = next(i for i, ln in enumerate(lines) if ln.startswith(title))
    return {pos: '\n'.join(lines[:q] + [sentence] + lines[q:]) + '\n'
            for pos, q in (('line2', 1), ('above_title', at), ('under_title', at + 1))}


class ABodySentenceStartingWithAConfirmationPhraseIsNoTitle(SimpleTestCase):
    def test_each_sentence_leaves_an_ordinary_offer_as_it_reads_without_it(self):
        for offer, title in OFFERS:
            plain = {crest: _verdict(offer, crest) for crest in (False, True)}
            for sentence in REVIEW12 + MORE:
                for pos, text in _inserted(offer, title, sentence).items():
                    with self.subTest(sentence, offer=offer[:24], pos=pos):
                        self.assertFalse(page_titled(_folded_lines(text)))
                        for crest in (False, True):
                            self.assertEqual(_verdict(text, crest), plain[crest])


class AMultiWordGluedOpeningStillEndsTheTitle(_Caps):
    def test_each_glued_opening_caps(self):
        for opening in ('Adalah dimaklumkan bahawa penama di bawah ialah pelajar kami',
                        'Adalah dengan ini disahkan bahawa penama di bawah ialah pelajar kami',
                        'Adalah dengan ini dimaklumkan bahawa penama di bawah ialah pelajar kami',
                        'Dengan ini dimaklumkan bahawa penama di bawah ialah pelajar kami',
                        'Sukacita dimaklumkan bahawa penama di bawah ialah pelajar kami',
                        'Dengan hormatnya saya merujuk perkara di atas',
                        'This is to certify that the student named below is enrolled'):
            self.assert_caps(f'PENGESAHAN PELAJAR {opening}')

    def test_a_single_body_word_glued_on_no_longer_ends_the_title(self):
        for title in ('PENGESAHAN PELAJAR kami akan dikeluarkan', 'PENGESAHAN PELAJAR adalah diperlukan'):
            text = UITM_OFFER.replace('SURAT TAWARAN\n', f'{title}\nSURAT TAWARAN\n')
            with self.subTest(title):
                self.assertFalse(page_titled(_folded_lines(text)))
