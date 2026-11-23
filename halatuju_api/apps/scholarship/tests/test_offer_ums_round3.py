"""S1c owner words, review round 3 (20 Nov): Part A, the reviewer's fixes (MED-1 NFKC fold and the wider
foreign-letter rule, MED-2 raw OR folded, MED-3 the later-page reporting label and date shapes, LOW-1 the
programme label's separators, LOW-2 the squeezed stems, LOW-3 the page-tree leaf types); Part B, the owner's
anchors (each value read right after its phrase on page 1). Every rule refuses MORE; the genuine-shape letters
still lock.

Synthetic twins only: invented names, ICs and places (`test_no_gitignored_corpus.py`)."""
import io
from unittest import mock

from django.test import SimpleTestCase

from apps.scholarship import offer_ums_refusal as R
from apps.scholarship.offer_parse import diagnose
from apps.scholarship.offer_parse_university import read_ums
from apps.scholarship.offer_ums_refusal import (anchor_refusal, fold_lookalikes, foreign_letters, later_pages_refusal,
                                                letter_refusal)
from apps.scholarship.tests.test_offer_owner_words import LATER, PAGE2, _digital
from apps.scholarship.tests.test_offer_parse_university import NAME, NRIC, ums

#: The template letter's read fields (what the anchors check against).
FIELDS = read_ums(ums())[0]


def _guard(page1, scan=False):
    d = diagnose(page1) if scan else _digital(page1, [page1])
    return d['guard'] or d['empty_required'] or 'LOCK'


class TestFoldAndForeign(SimpleTestCase):
    """MED-1 (and LOW-4): NFKC inside the fold; any letter NFKC changes, or beyond Latin Extended-B, is
    foreign."""

    def test_nfkc_folds_fullwidth_and_math_letters(self):
        self.assertEqual(fold_lookalikes('ＤＩＢＡＴＡＬＫＡＮ'), 'DIBATALKAN')
        self.assertEqual(fold_lookalikes('DIB\U0001d400TALKAN'), 'DIBATALKAN')
        self.assertEqual(fold_lookalikes('DIBАTALKAN'), 'DIBATALKAN')
        self.assertEqual(fold_lookalikes('plain ascii'), 'plain ascii')

    def test_foreign_letters_cover_the_reviewers_shapes(self):
        for ch in ('Ａ', '\U0001d400', 'Ꭺ', 'Ա', '́', '҃', 'ᴦ', '٩', '１',
                   'а', 'λ'):
            with self.subTest(ch=ascii(ch)):
                self.assertTrue(foreign_letters('Tawaran ' + ch))

    def test_punctuation_is_not_foreign_but_accents_are(self):
        """Round 5 (MED B): no genuine UMS PDF holds a non-ASCII letter, so an accented one is foreign too."""
        self.assertFalse(foreign_letters('Kota Kinabalu – ’', ums()))
        for word in ('Pengenalán', 'ā', 'é'):
            with self.subTest(word=ascii(word)):
                self.assertTrue(foreign_letters(word))

    def test_a_cherokee_letter_refuses_a_digital_letter(self):
        page = ums() + 'Tawaran ini DIBᎪTALKAN\n'
        self.assertEqual(_guard(page), 'foreign_letters')


class TestRawOrFolded(SimpleTestCase):
    """MED-2: a check refuses when the raw OR the folded text refuses."""

    def test_folded_withdrawal_refuses(self):
        tail = 'Tawaran ini ＤＩＢＡＴＡＬＫＡＮ\n'
        self.assertEqual(letter_refusal(ums() + tail), 'not_an_offer')
        self.assertEqual(_guard(ums() + tail, scan=True), 'not_an_offer')

    def test_raw_withdrawal_refuses_even_when_the_fold_would_hide_it(self):
        with mock.patch.object(R, 'fold_lookalikes', return_value=ums()):
            self.assertEqual(letter_refusal(ums() + 'Tawaran ini DIBATALKAN\n'), 'not_an_offer')
            self.assertEqual(later_pages_refusal([PAGE2 + 'No. KP : 020304-15-6789'], *LATER), 'second_offer')

    def test_folded_later_page_refuses(self):
        page = PAGE2 + 'No KP ０２０３０４１５６７８９'
        self.assertEqual(later_pages_refusal([page], *LATER), 'second_offer')


class TestLaterPageDates(SimpleTestCase):
    """MED-3: a reporting label with an unreadable value, and the wider numeric / word date shapes."""

    def test_a_label_with_an_unreadable_value_refuses(self):
        for line in ('Tarikh Lapor Diri : TBD', 'Tarikh Lapor Diri ∶ X', 'Tarikh Lapor Diri : 5 Okt. 2031',
                     'Tarikh Lapor Diri\nakan dimaklumkan'):
            with self.subTest(line=line):
                self.assertEqual(later_pages_refusal([PAGE2 + line], *LATER), 'second_offer')

    def test_numeric_dates_in_any_separator_spacing_or_digits_refuse(self):
        for date in ('5–10–2031', '5 – 10 – 2031', '5∕10∕2031', '5 . 10 .    2031',
                     '５．１０．２０３１', '05102031', '5⁄10⁄2031'):
            with self.subTest(date=ascii(date)):
                self.assertEqual(later_pages_refusal([PAGE2 + 'Hadir pada ' + date], *LATER), 'second_offer')

    def test_english_and_short_months_refuse(self):
        for date in ('5 Oct 2031', '5 October 2031', '5 Okt 2031', 'Oktober 5, 2031', 'Sep. 28'):
            with self.subTest(date=date):
                self.assertEqual(later_pages_refusal([PAGE2 + 'Hadir pada ' + date], *LATER), 'second_offer')

    def test_the_genuine_prose_and_deadline_shapes_pass(self):
        """Genuine page 2s print the label in prose after a comma and day-month deadlines (Malay month)."""
        for line in ('Tarikh Lapor Diri, sila bawa dokumen asal.', 'Tarikh\nLapor Diri :\n28 September 2031'):
            with self.subTest(line=line):
                self.assertEqual(later_pages_refusal([PAGE2 + line], *LATER), '')
        self.assertEqual(later_pages_refusal(['Bayaran sebelum 26 Ogos 2031.\n' + PAGE2], *LATER), '')


class TestProgrammeLabelSeparators(SimpleTestCase):
    """LOW-1: another programme label with any separator."""

    def test_any_separator_refuses(self):
        for sep in ('∶', '꞉', '=', '-', '\t', '–'):
            with self.subTest(sep=ascii(sep)):
                self.assertEqual(later_pages_refusal([PAGE2 + f'Program {sep} Diploma Sains Marin'], *LATER),
                                 'second_offer')
        self.assertEqual(later_pages_refusal([PAGE2 + 'Program\tDiploma Sains Marin'], *LATER), 'second_offer')


class TestSqueezedStems(SimpleTestCase):
    """LOW-2: DAPAT / BOLEH / LAGI / AKAN between TIDAK and DITERUSKAN, however spaced or dotted."""

    def test_each_stem_refuses(self):
        for tail in ('TIDAK DAPAT DITERUSKAN', 'tidak boleh diteruskan', 'T.I.D.A.K. D.A.P.A.T. D.I.T.E.R.U.S.K.A.N',
                     'tidak dapat lagi diteruskan', 'tidak boleh lagi diteruskan', 'tidak akan lagi diteruskan',
                     'T-I-D-A-K-B-O-L-E-H-D-I-T-E-R-U-S-K-A-N'):
            with self.subTest(tail=tail):
                self.assertEqual(letter_refusal(ums() + 'Tawaran ini ' + tail + '\n'), 'not_an_offer')
                self.assertEqual(read_ums(ums() + 'Tawaran ini ' + tail + '\n')[1], 'not_an_offer')


def _tree_pdf(edit):
    """A 2-page pypdf PDF whose page tree ``edit(writer)`` changes before it is written."""
    from pypdf import PdfWriter
    w = PdfWriter()
    w.add_blank_page(100, 100)
    w.add_blank_page(100, 100)
    edit(w)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


class TestPageTreeLeaves(SimpleTestCase):
    """LOW-3: only /Page leaves (or leaves with no /Type) count; another leaf type or a null kid refuses."""

    def _refusal(self, data):
        from apps.scholarship.pdf_layer_guards import page_tree_refusal
        from apps.scholarship.pdf_pages import _open_pdf
        return page_tree_refusal(_open_pdf(data))

    def test_another_leaf_type_refuses(self):
        from pypdf.generic import NameObject

        def edit(w):
            w.pages[1].get_object()[NameObject('/Type')] = NameObject('/Template')
        self.assertEqual(self._refusal(_tree_pdf(edit)), 'page_count')

    def test_a_null_kid_refuses(self):
        from pypdf.generic import NameObject, NullObject, NumberObject

        def edit(w):
            pages = w._root_object['/Pages'].get_object()
            pages['/Kids'].append(NullObject())
            pages[NameObject('/Count')] = NumberObject(3)
        self.assertEqual(self._refusal(_tree_pdf(edit)), 'page_count')

    def test_page_leaves_pass(self):
        self.assertEqual(self._refusal(_tree_pdf(lambda w: None)), '')


class TestAnchors(SimpleTestCase):
    """Part B (owner, 20 Nov): each value the lock uses is read right after its phrase on page 1."""

    def test_the_template_still_locks_digital_and_scanned(self):
        self.assertEqual(_guard(ums()), 'LOCK')
        self.assertEqual(_guard(ums(), scan=True), 'LOCK')

    def test_an_anchor_printed_twice_refuses(self):
        for extra in ('Kod Program :      UH6481001\n', 'No. Kad Pengenalan :      010203-14-5678\n',
                      'TAWARAN KEMASUKAN KE UNIVERSITI MALAYSIA SABAH\n', 'Tarikh Lapor Diri :      28 September 2031\n'):
            with self.subTest(extra=extra[:12]):
                self.assertEqual(anchor_refusal(ums() + extra, FIELDS, True), 'anchor_once')
                self.assertEqual(anchor_refusal(ums() + extra, FIELDS, False), 'anchor_once')
                self.assertNotEqual(_guard(ums() + extra), 'LOCK')
                self.assertNotEqual(_guard(ums() + extra, scan=True), 'LOCK')

    def test_a_name_in_the_greeting_must_be_the_name_read(self):
        other = ums().replace('bahawa saudara telah', 'bahawa QUILBOR A/L VENTAKAR telah')
        self.assertEqual(_guard(other), 'anchor_name')
        self.assertEqual(_guard(other, scan=True), 'anchor_name')
        same = ums().replace('bahawa saudara telah', f'bahawa {NAME} telah')
        self.assertEqual(anchor_refusal(same, FIELDS, True), '')
        self.assertEqual(_guard(ums().replace('bahawa saudara telah', 'bahawa saudara/saudari telah')), 'LOCK')

    def test_another_ic_looking_value_on_page_one_refuses_a_digital_letter(self):
        for extra in ('No. Akaun :      020304-15-6789\n', 'Rujukan Bank :      1234 5678 9012\n'):
            with self.subTest(extra=extra[:8]):
                self.assertEqual(anchor_refusal(ums(extra_head=extra), FIELDS, True), 'anchor_ic')
                self.assertNotEqual(_guard(ums(extra_head=extra)), 'LOCK')

    def test_the_ic_off_its_label_line_refuses_a_digital_letter(self):
        moved = ums().replace(f'No. Kad Pengenalan :      {NRIC}', f'No. Kad Pengenalan :\n{NRIC}')
        self.assertNotEqual(_guard(moved), 'LOCK')

    def test_another_code_looking_value_refuses(self):
        for scan in (False, True):
            with self.subTest(scan=scan):
                self.assertEqual(_guard(ums(extra_head='Rujuk UH6481002\n'), scan=scan), 'anchor_code')

    def test_the_code_far_from_its_label_refuses(self):
        far = ums(code='Kod Program :').replace('Saudara/i akan', 'UH6481001\nSaudara/i akan')
        self.assertNotEqual(_guard(far), 'LOCK')
        self.assertNotEqual(_guard(far, scan=True), 'LOCK')

    def test_a_scan_code_a_few_lines_after_its_label_locks(self):
        near = ums(code='Kod Program :').replace('Fakulti :', 'UH6481001\nFakulti :')
        self.assertEqual(_guard(near, scan=True), 'LOCK')

    def test_read_ums_alone_is_unchanged_by_the_anchors(self):
        self.assertEqual(read_ums(ums())[1], '')
