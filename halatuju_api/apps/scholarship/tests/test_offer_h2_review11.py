"""Help H2 review 11 (16 Nov 2026, the last layout round): confirmation title LINES the review-10 reading missed.

H1: a long title ("PENGESAHAN SEBAGAI PELAJAR SEPENUH MASA DI UNIVERSITI ... 2025/2026") or a long name glued on
before the IC ran past the 8-word rest limit; the limit is now 14, as `_cut`. H2: "SURAT AKUAN" / "BORANG" /
"SIJIL" / "NOTIS" / "PERIHAL:" before the title, or a leading number ("1. PENGESAHAN PELAJAR"). H3: a reference line
citing an offer ("Ruj. Tuan : Surat Tawaran bertarikh ...") was read as the offer title line and ended the search.
Also: the title stops at a glued body word ("PENGESAHAN PELAJAR Adalah dimaklumkan ..."), and a title split over
THREE short lines joins ("PENGESAHAN / STATUS / PELAJAR"). Each such letter reads suspect with a confirmation code
(never a course pick); a body sentence still never caps. The reviewer's letters (h2r11/p5.py), synthetic only
(`test_no_gitignored_corpus.py`): every name and number is invented.
"""
from django.test import SimpleTestCase

from apps.scholarship.genuineness.offer_confirm_checks import offer_title_line, page_titled
from apps.scholarship.genuineness.offer_confirmations import CONFIRMATION_SEEN
from apps.scholarship.genuineness.offer_reading import _folded_lines
from apps.scholarship.tests.test_corpus_gaps_c2 import UITM_OFFER
from apps.scholarship.tests.test_offer_h2_confirmations import _read, _verdict

_STD = 'Dengan ini disahkan bahawa penama di bawah adalah pelajar yang sedang mengikuti pengajian.'
_SIG = ('Tawaran Kemasukan Ke Program Ijazah Sarjana Muda\nSesi Akademik 2025/2026\nNo. Matrik : BS25110001\n'
        'Yuran Pengajian RM 500\nTarikh Pendaftaran : 1 Julai 2025\nNaib Canselor\nBahagian Pengurusan Akademik\n'
        'Program Pengajian : Ijazah\nKampus Utama\nwww.upm.edu.my')
HEADS = ('UNIVERSITI PUTRA MALAYSIA\nBahagian Akademik',
         'INSTITUT KEMAHIRAN BELIA NEGARA DUSUN TUA\nKEMENTERIAN BELIA DAN SUKAN',
         'UNIVERSITI KEBANGSAAN MALAYSIA\nPusat Pengurusan Akademik')
_ADDR = ('Kepada:\nEncik Abu bin Bakar\nNo. 12, Jalan Melati 3/4\nTaman Bunga Raya Indah Fasa Dua\n'
         'Kampung Baru Sungai Buloh\n47000 Sungai Buloh\nSelangor Darul Ehsan\nMalaysia\nTuan/Puan,')
OFFER_REF = 'Ruj. Tuan : Surat Tawaran bertarikh 1 Mei 2025'


def letter(head, title, pre='', ref='Rujukan : CONTOH/600-1/2'):
    return (f'{head}\nJalan Contoh, 31600 Bandar Contoh\n{ref}\nTarikh : 1 Jun 2026\n{pre}\n{title}\n{_STD}\n'
            f'Nama : Ali bin Abu\nNo. Kad Pengenalan : 080808-10-5566\nProgram : Ijazah Contoh\n{_SIG}\n'
            'Sekian, terima kasih.\nYang benar,\nPENDAFTAR\n')


class _Caps(SimpleTestCase):
    def assert_caps(self, title, **kw):
        for head in HEADS:
            text = letter(head, title, **kw)
            self.assertTrue(page_titled(_folded_lines(text)), title)
            for crest in (False, True):
                with self.subTest(title, head=head[:12], crest=crest):
                    out = _read(text, crest)
                    self.assertEqual(out['status'], 'suspect')
                    self.assertIn(out['type'], CONFIRMATION_SEEN)       # never a course pick


class H1LongTitleRest(_Caps):
    def test_a_long_title_line_caps(self):
        for title in ('PENGESAHAN SEBAGAI PELAJAR SEPENUH MASA DI UNIVERSITI KEBANGSAAN MALAYSIA BAGI SESI '
                      'AKADEMIK 2025/2026',
                      'SURAT PENGESAHAN STATUS PELAJAR PROGRAM IJAZAH SARJANA MUDA SAINS SEMESTER 1 SESI 2025/2026'):
            self.assert_caps(title)
            self.assert_caps(title, pre=_ADDR)

    def test_a_long_name_glued_before_the_ic_caps(self):
        for title in ('PENGESAHAN PELAJAR MUHAMMAD HAFIZ BIN ABDUL RAHMAN A/L MUTHU KRISHNAN 080808-10-5566',
                      'PENGESAHAN STATUS PELAJAR SITI NUR AISYAH BINTI MOHD FAIZAL HAKIMI BIN ABDULLAH'):
            self.assert_caps(title)


class H2TitlePrefixesAndNumbers(_Caps):
    def test_each_new_prefix_caps(self):
        for title in ('SURAT AKUAN PENGESAHAN PELAJAR', 'BORANG PENGESAHAN PELAJAR', 'SIJIL PENGESAHAN PELAJAR',
                      'NOTIS PENGESAHAN STATUS PELAJAR', 'PERIHAL : PENGESAHAN PELAJAR'):
            self.assert_caps(title)

    def test_a_numbered_title_caps(self):
        self.assert_caps('1. PENGESAHAN PELAJAR')


class H3AReferenceLineIsNoOfferTitle(_Caps):
    def test_reference_lines_are_never_offer_title_lines(self):
        for ln in (OFFER_REF, 'Ruj. Kami : Surat Tawaran UPM/1', 'Rujukan : Surat Tawaran 1 Mei 2025',
                   'Your Ref : Offer Letter dated 1 May 2025', 'Our Ref : Offer of Admission'):
            with self.subTest(ln):
                self.assertFalse(offer_title_line(_folded_lines(ln)[0]))
        self.assertTrue(offer_title_line(_folded_lines('SURAT TAWARAN')[0]))

    def test_a_confirmation_under_a_reference_to_an_offer_caps(self):
        self.assert_caps('PENGESAHAN PELAJAR', ref=OFFER_REF)
        self.assert_caps('PENGESAHAN PELAJAR', pre=_ADDR, ref=OFFER_REF)

    def test_an_offer_with_such_a_reference_line_reads_as_without_it(self):
        text = UITM_OFFER.replace('SURAT TAWARAN\n', f'{OFFER_REF}\nSURAT TAWARAN\n')
        self.assertFalse(page_titled(_folded_lines(text)))
        for crest in (False, True):
            self.assertEqual(_verdict(text, crest)[:2], _verdict(UITM_OFFER, crest)[:2])


class GluedBodyAndThreeLineTitles(_Caps):
    def test_the_title_stops_at_a_glued_body_word(self):
        self.assert_caps('PENGESAHAN PELAJAR Adalah dimaklumkan bahawa penama di bawah ialah pelajar kami')

    def test_a_title_over_three_short_lines_caps(self):
        self.assert_caps('PENGESAHAN\nSTATUS\nPELAJAR')
        self.assert_caps('SURAT\nPENGESAHAN\nSTATUS PELAJAR')

    def test_a_sentence_over_three_short_lines_still_never_caps(self):
        for sentence in ('Pengesahan\nPelajar akan dibuat\noleh pihak kolej.',
                         'Confirmation of\nstudies will be issued\nafter registration.'):
            text = UITM_OFFER.replace('SURAT TAWARAN\n', f'{sentence}\nSURAT TAWARAN\n')
            with self.subTest(sentence):
                self.assertFalse(page_titled(_folded_lines(text)))
