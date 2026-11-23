"""S1c UMS fix round 5 (20 Nov): the review round 3 short-check fixes. MED A invisible formatting characters
inside a refusal word; MED B accented and stroke / hook look-alikes (and any non-ASCII letter in a digital
letter); LOW C the status title and TERBATAL in any spacing or dotting; LOW D deferral words, "akan dimaklumkan"
and the wider page-2 date shapes. Every attack string the short check found is tried as a digital page 1, a
scan and (where it applies) a page 2; the genuine shapes still lock.

Synthetic twins only: invented names, ICs and places (`test_no_gitignored_corpus.py`)."""
from django.test import SimpleTestCase

from apps.scholarship.offer_parse import diagnose
from apps.scholarship.offer_parse_university import read_ums
from apps.scholarship.offer_ums_refusal import (fold_lookalikes, foreign_letters, later_pages_refusal, letter_refusal,
                                                status_said)
from apps.scholarship.tests.test_offer_owner_words import LATER, PAGE2, _digital
from apps.scholarship.tests.test_offer_parse_university import ums

SHY, WJ = '­', '⁠'


def _digital_p1(tail):
    """A one-page digital letter with ``tail`` printed at the end of page 1."""
    page = ums() + tail + '\n'
    d = _digital(page, [page])
    return d['guard'] or d['empty_required'] or 'LOCK'


def _scan(tail):
    d = diagnose(ums() + tail + '\n')
    return d['guard'] or d['empty_required'] or 'LOCK'


def _digital_p2(tail):
    """A two-page digital letter with ``tail`` printed on page 2 (the text layer holds both pages)."""
    page2 = PAGE2 + tail + '\n'
    d = _digital(ums(), [ums(), page2], text=ums() + page2)
    return d['guard'] or d['empty_required'] or 'LOCK'


class RefusesEverywhere(SimpleTestCase):
    """Each attack string must refuse on a digital page 1, a scan and a digital page 2."""

    def assert_refused(self, tail, page2=True):
        for name, run in (('digital', _digital_p1), ('scan', _scan)) + ((('page2', _digital_p2),) if page2 else ()):
            with self.subTest(where=name, tail=ascii(tail)):
                self.assertNotEqual(run(tail), 'LOCK')


class TestGenuineShapesStillLock(SimpleTestCase):

    def test_the_template_locks_digital_scanned_and_on_two_pages(self):
        self.assertEqual(_digital_p1(''), 'LOCK')
        self.assertEqual(_scan(''), 'LOCK')
        self.assertEqual(_digital_p2(''), 'LOCK')

    def test_genuine_page_two_prose_still_locks(self):
        """All 36 genuine page 2s print "penangguhan" in a condition and the label in prose after a comma; 2 print
        a time; none of them refuses (deadlines: `test_offer_ums_round3`)."""
        for tail in ('3. Permohonan penangguhan pengajian hendaklah dibuat secara bertulis.',
                     'Tarikh Lapor Diri, sila bawa dokumen asal.',
                     'Pendaftaran bermula jam 8:30:00 pagi.',
                     '4. Tawaran ini akan terbatal sekiranya saudara tidak mendaftar.'):
            with self.subTest(tail=tail):
                self.assertEqual(_digital_p2(tail), 'LOCK')
                self.assertEqual(later_pages_refusal([PAGE2 + tail], *LATER), '')

    def test_a_scan_with_an_accented_ocr_letter_still_locks(self):
        """Scans are never asked about foreign letters (4 of 22 genuine scans hold one): only the fold is read."""
        self.assertEqual(_scan('Sekian, terima kasih. Kota Kinabalú'), 'LOCK')

    def test_a_status_word_on_its_own_does_not_refuse(self):
        self.assertFalse(status_said('Surat ini adalah cetakan komputer. Tiada tandatangan diperlukan.'))
        self.assertEqual(_scan('Surat ini adalah cetakan komputer.'), 'LOCK')


class TestMedAInvisibleFormatting(RefusesEverywhere):
    """MED A: a soft hyphen or word joiner inside a refusal word."""

    def test_soft_hyphen_and_word_joiner_in_terbatal(self):
        for tail in (f'Status : TERBA{SHY}TAL', f'Status : TERBA{WJ}TAL', f'Tawaran ini DIBA{SHY}TALKAN'):
            self.assert_refused(tail)

    def test_soft_hyphen_in_the_status_title(self):
        self.assert_refused(f'SURAT PENGE{SHY}SAHAN')
        self.assertEqual(read_ums(ums() + f'SURAT PENGE{SHY}SAHAN\n')[1], 'status_letter')
        self.assertEqual(letter_refusal(ums() + f'SURAT PENGE{SHY}SAHAN\n'), 'status_letter')

    def test_any_format_character_is_foreign_in_a_digital_letter(self):
        for ch in (SHY, WJ, '‎', '⁡', '⁣', '؜'):
            with self.subTest(ch=ascii(ch)):
                self.assertTrue(foreign_letters('Kota Kina' + ch + 'balu'))
                self.assertEqual(_digital_p1('Kota Kina' + ch + 'balu'), 'foreign_letters')

    def test_the_fold_strips_format_characters(self):
        self.assertEqual(fold_lookalikes(f'TERBA{SHY}TAL TERBA{WJ}TAL'), 'TERBATAL TERBATAL')


class TestMedBAccentsAndStrokes(RefusesEverywhere):
    """MED B: accented look-alikes and stroke / hook letters below U+0250."""

    def test_accented_and_stroke_withdrawal_words(self):
        for tail in ('Tawaran ini DIBÁTALKAN', 'Tawaran ini ÐIBATALKAN', 'Tawaran ini ƊIBATALKAN',
                     'Tawaran ini ĐIBATALKAN', 'Status : TERBÄTAL', 'Tawaran ini DİBATALKAN'):
            self.assert_refused(tail)

    def test_accented_status_title(self):
        self.assert_refused('SURAT PENGESÁHAN')
        self.assertEqual(read_ums(ums() + 'SURAT PENGESÁHAN\n')[1], 'status_letter')

    def test_the_fold_drops_accents_and_strokes(self):
        self.assertEqual(fold_lookalikes('DIBÁTALKAN ÐIBATALKAN ƊIBATALKAN ĐŁØĦŦ SURAT PENGESÁHAN'),
                         'DIBATALKAN DIBATALKAN DIBATALKAN DLOHT SURAT PENGESAHAN')

    def test_any_non_ascii_letter_refuses_a_digital_letter(self):
        """No genuine UMS PDF has any non-ASCII letter: even an innocent one refuses a text-layer PDF."""
        for word in ('Kinabalú', 'Pengenalán', 'ā', 'é', 'ß', 'Æ', 'ª', '²'):
            with self.subTest(word=ascii(word)):
                self.assertTrue(foreign_letters('Kota ' + word))
                self.assertEqual(_digital_p1('Kota ' + word), 'foreign_letters')

    def test_non_ascii_punctuation_is_not_foreign(self):
        self.assertFalse(foreign_letters('Kota Kinabalu – ’ “ ” • …', ums()))


class TestLowCSpacingAndDots(RefusesEverywhere):
    """LOW C: the status title with wide spacing, spaced letters; TERBATAL with dots or dashes."""

    def test_status_title_in_any_spacing(self):
        for tail in ('SURAT    PENGESAHAN', 'SURAT    PENGESAHAN', 'S U R A T  P E N G E S A H A N',
                     'SURAT          PENGESAHAN', 'S.U.R.A.T P.E.N.G.E.S.A.H.A.N', 'SURAT\n\n\n\nPENGESAHAN'):
            self.assert_refused(tail)
            with self.subTest(tail=ascii(tail)):
                self.assertTrue(status_said(tail))
                self.assertEqual(read_ums(ums() + tail + '\n')[1], 'status_letter')

    def test_terbatal_with_dots_or_dashes(self):
        for tail in ('Status : T.E.R.B.A.T.A.L', 'Status : T . E . R . B . A . T . A . L', 'Status : TERBA-TAL',
                     'Status : TER.BA.TAL', 'Status : T-E-R-B-A-T-A-L', 'Tawaran ini telah DI.TARIK BALIK',
                     'Status : T_E_R_B_A_T_A_L', 'Tawaran ini D.I.T.O.L.A.K'):
            self.assert_refused(tail)
            with self.subTest(tail=tail):
                self.assertEqual(letter_refusal(ums() + tail + '\n'), 'not_an_offer')


class TestLowDDeferralAndDates(RefusesEverywhere):
    """LOW D: deferral words and "akan dimaklumkan" on every page; year-first and other-separator dates."""

    def test_deferral_words_on_every_page(self):
        for tail in ('Tawaran ini telah ditangguhkan', 'Tawaran ini ditunda', 'Tawaran ini DITANGGUH',
                     'Tawaran ini tertangguh', 'Tawaran ini di tunda', 'Tawaran ini d i t a n g g u h k a n',
                     'Tawaran ini D.I.T.U.N.D.A'):
            self.assert_refused(tail)
            with self.subTest(tail=tail):
                self.assertEqual(read_ums(ums() + tail + '\n')[1], 'not_an_offer')
                self.assertEqual(later_pages_refusal([PAGE2 + tail], *LATER), 'second_offer')

    def test_a_date_still_to_be_announced_refuses(self):
        for tail in ('Tarikh Lapor Diri, akan dimaklumkan kemudian.', 'Tarikh pendaftaran akan diumumkan kelak.',
                     'Tarikh Lapor Diri, akan ditetapkan kemudian.', 'Tarikh Lapor Diri, akan diberitahu.',
                     'Tarikh Lapor Diri, AKAN DI MAKLUMKAN kemudian.'):
            self.assert_refused(tail)
            with self.subTest(tail=tail):
                self.assertEqual(later_pages_refusal([PAGE2 + tail], *LATER), 'second_offer')

    def test_year_first_and_other_separator_dates_on_page_two(self):
        for date in ('2031-10-05', '2031/10/05', '2031.10.5', '5 10 2031', '5,10,2031', '5:10:2031', '5_10_2031',
                     '5·10·2031', '5102031', '0510231', '5 , 10 , 2031', '5;10;2031', '2031 10 05'):
            with self.subTest(date=ascii(date)):
                self.assertEqual(later_pages_refusal([PAGE2 + 'Hadir pada ' + date], *LATER), 'second_offer')
                self.assertNotEqual(_digital_p2('Hadir pada ' + date), 'LOCK')
