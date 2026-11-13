"""Request #67 (scope 2): the MyKad name and address read from the card's LAYOUT.

The line-order read lost a name's second line (or first) to the address whenever the name had a
mid-line A/L / A/P / BIN, or none at all — 15 BrightPath students. The card prints a blank line
between the name and the address; the word boxes from the same Vision call show it. These cards
are synthetic: made-up names, laid out as a MyKad prints them (IC number, name lines, blank
line, address; WARGANEGARA / LELAKI / ISLAM in the right-hand column)."""
import math
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.scholarship import vision
from apps.scholarship.vision.mykad import _extract_address, _layout_read

NRIC = '030101-14-1234'
H = 12.0          # letter height (px)
PITCH = 18.0      # ordinary line spacing
LEFT = 40.0


def _words(line_text, x0, y, h=H):
    """One printed line → Vision-style word boxes (upright)."""
    out, x = [], x0
    for t in line_text.split():
        wlen = 0.8 * h * len(t)
        out.append({'text': t, 'cx': x + wlen / 2, 'cy': y, 'h': h, 'angle': 0.0,
                    'wlen': wlen, 'wh': h})
        x += wlen + 0.4 * h
    return out


def card(name_lines, address_lines, *, gap=True, labels=True, nric=NRIC):
    """A MyKad face: (words, flattened text in Vision's line order)."""
    printed = [('KAD PENGENALAN MALAYSIA', LEFT, 60, 16), (nric, LEFT, 200, 16)]
    y = 240.0
    for ln in name_lines:
        printed.append((ln, LEFT, y, H))
        y += PITCH
    y += PITCH if gap else 0          # the blank line
    for ln in address_lines:
        printed.append((ln, LEFT, y, H))
        y += PITCH
    if labels:                        # right-hand column, level with the address
        printed += [('WARGANEGARA', 430, 240 + PITCH * (len(name_lines) + 1), H),
                    ('LELAKI', 430, 240 + PITCH * (len(name_lines) + 2), H)]
    words = [w for t, x, yy, h in printed for w in _words(t, x, yy, h)]
    text = '\n'.join(t for t, *_ in printed) + '\n'
    return words, text


def rotate(words, deg, origin=(300.0, 300.0)):
    """The same card photographed turned by ``deg`` degrees."""
    r = math.radians(deg)
    ox, oy = origin
    out = []
    for w in words:
        dx, dy = w['cx'] - ox, w['cy'] - oy
        out.append(dict(w, cx=ox + dx * math.cos(r) - dy * math.sin(r),
                        cy=oy + dx * math.sin(r) + dy * math.cos(r), angle=deg))
    return out


ADDRESS = ['NO 12 JALAN MAWAR 3', 'TAMAN SRI MUDA', '47000 SUNGAI BULOH', 'SELANGOR']


def read(words, text):
    with patch.object(vision, '_vision_document_text',
                      return_value={'text': text, 'words': words, 'error': None}):
        return vision.extract_mykad(b'img', 'image/jpeg')


class TestLayoutRecoversTheWholeName(SimpleTestCase):

    def test_second_line_after_a_mid_line_marker(self):
        # The commonest shape (11 of 15): the marker is mid-line, the father's name runs on.
        r = read(*card(['KAVITHA A/P MUNUSAMY', 'NAIDU'], ADDRESS))
        self.assertEqual(r['name'], 'KAVITHA A/P MUNUSAMY NAIDU')
        self.assertEqual(r['address'], 'NO 12 JALAN MAWAR 3, TAMAN SRI MUDA, 47000 SUNGAI BULOH, SELANGOR')

    def test_line_order_read_alone_drops_it(self):
        # The fault, pinned: with no word boxes the old read is unchanged (and short).
        words, text = card(['KAVITHA A/P MUNUSAMY', 'NAIDU'], ADDRESS)
        r = read([], text)
        self.assertEqual(r['name'], 'KAVITHA A/P MUNUSAMY')
        self.assertTrue(r['address'].startswith('NAIDU'))

    def test_name_with_no_marker(self):
        # Christian / Chinese names carry no A/L, A/P or BIN (apps 305, 581).
        r = read(*card(['JOSEPHINE MARY', 'ANTHONY DASS'], ADDRESS))
        self.assertEqual(r['name'], 'JOSEPHINE MARY ANTHONY DASS')
        self.assertNotIn('ANTHONY', r['address'])

    def test_first_line_before_a_marked_second_line(self):
        # The leading part was lost (apps 442, 530): the marker sits on the SECOND line.
        r = read(*card(['MUHAMMAD HAKIM', 'SHAH BIN ISMAIL'], ADDRESS))
        self.assertEqual(r['name'], 'MUHAMMAD HAKIM SHAH BIN ISMAIL')

    def test_at_sign_line(self):
        r = read(*card(['SELVI A/P RAMAN', '@ SELVAM'], ADDRESS))
        self.assertEqual(r['name'], 'SELVI A/P RAMAN @ SELVAM')
        self.assertNotIn('SELVAM', r['address'])

    def test_short_one_word_second_line(self):
        r = read(*card(['TAN MEI', 'LIM'], ADDRESS))
        self.assertEqual(r['name'], 'TAN MEI LIM')

    def test_slash_boxed_as_its_own_word(self):
        # Vision can box "A", "/", "L" separately; they sit flush and are closed up.
        words, text = card(['DEVAN A/L KANNAN', 'PERUMAL'], ADDRESS)
        split = []
        for w in words:
            if w['text'] == 'A/L':
                x0 = w['cx'] - w['wlen'] / 2
                for i, t in enumerate(('A', '/', 'L')):
                    split.append(dict(w, text=t, cx=x0 + H * 0.4 * (2 * i + 1), wlen=0.8 * H))
            else:
                split.append(w)
        r = read(split, text.replace('A/L', 'A / L'))
        self.assertEqual(r['name'], 'DEVAN A/L KANNAN PERUMAL')

    def test_dropped_slash_is_closed_up(self):
        r = read(*card(['THEEPA AP', 'SELVARAJ'], ADDRESS))
        self.assertEqual(r['name'], 'THEEPA A/P SELVARAJ')

    def test_rotated_photo_reads_the_same(self):
        words, text = card(['KAVITHA A/P MUNUSAMY', 'NAIDU'], ADDRESS)
        for deg in (90, -90, 8, 180):
            with self.subTest(deg=deg):
                self.assertEqual(read(rotate(words, deg), text)['name'], 'KAVITHA A/P MUNUSAMY NAIDU')


class TestLayoutLeavesGoodReadsAlone(SimpleTestCase):

    def test_one_line_name(self):
        r = read(*card(['NURUL AIN BINTI OMAR'], ADDRESS))
        self.assertEqual(r['name'], 'NURUL AIN BINTI OMAR')
        self.assertEqual(r['address'], 'NO 12 JALAN MAWAR 3, TAMAN SRI MUDA, 47000 SUNGAI BULOH, SELANGOR')

    def test_trailing_marker_break_already_read(self):
        r = read(*card(['THERESA ARUL MARY A/P', 'PHILIPS'], ADDRESS))
        self.assertEqual(r['name'], 'THERESA ARUL MARY A/P PHILIPS')

    def test_one_line_name_without_marker(self):
        r = read(*card(['WONG KAR WAI'], ADDRESS))
        self.assertEqual(r['name'], 'WONG KAR WAI')
        self.assertTrue(r['address'].startswith('NO 12 JALAN'))

    def test_no_blank_line_stops_at_the_address(self):
        # A photo where the blank line did not show: the address opener still stops the name.
        r = read(*card(['WONG KAR WAI'], ['JALAN MAWAR 3', 'TAMAN SRI MUDA', '47000 SUNGAI BULOH', 'SELANGOR'],
                       gap=False))
        self.assertEqual(r['name'], 'WONG KAR WAI')
        r = read(*card(['WONG KAR WAI'], ADDRESS, gap=False))
        self.assertEqual(r['name'], 'WONG KAR WAI')

    def test_right_column_labels_never_join(self):
        r = read(*card(['KAVITHA A/P MUNUSAMY', 'NAIDU'], ADDRESS, labels=True))
        self.assertNotIn('WARGANEGARA', r['name'] + r['address'])
        self.assertNotIn('LELAKI', r['name'] + r['address'])

    def test_layout_never_swaps_the_name(self):
        # The layout read only ADDS parts to the line-order name; a layout that reads another
        # name entirely is set aside.
        words, _ = card(['GAMMA DELTA', 'EPSILON'], ADDRESS)
        _, text = card(['KUMAR A/L RAJA'], ADDRESS)
        self.assertEqual(read(words, text)['name'], 'KUMAR A/L RAJA')

    def test_no_ic_number_on_the_card(self):
        words, text = card(['KAVITHA A/P MUNUSAMY', 'NAIDU'], ADDRESS, nric='ABCDEF')
        self.assertIsNone(_layout_read(words, text, ''))


class TestAddressWithoutAClearPostcode(SimpleTestCase):

    def test_postcode_glued_to_the_town(self):
        r = read(*card(['LEE MEI LING @', 'LEE MAY LYNN'],
                       ['NO 12 JALAN MAWAR 3', '47000SUNGAI BULOH', 'SELANGOR']))
        self.assertEqual(r['name'], 'LEE MEI LING @ LEE MAY LYNN')
        self.assertEqual(r['address'], 'NO 12 JALAN MAWAR 3, 47000SUNGAI BULOH, SELANGOR')

    def test_unreadable_postcode_falls_back_to_the_block_after_the_blank_line(self):
        r = read(*card(['ARUN A/L SAMY', 'VELU'], ['NO 12 JALAN MAWAR 3', '4TO0O SUNGAI BULOH', 'SELANGOR']))
        self.assertEqual(r['name'], 'ARUN A/L SAMY VELU')
        self.assertEqual(r['address'], 'NO 12 JALAN MAWAR 3, 4TO0O SUNGAI BULOH, SELANGOR')

    def test_skip_lines(self):
        text = 'NAIDU\nNO 1 JALAN A\n47000 SUNGAI BULOH\nSELANGOR\n'
        self.assertTrue(_extract_address(text).startswith('NAIDU'))
        self.assertEqual(_extract_address(text, skip=['NAIDU']), 'NO 1 JALAN A, 47000 SUNGAI BULOH, SELANGOR')

    def test_nric_digits_are_never_a_postcode(self):
        self.assertEqual(_extract_address('030101-14-12345\n'), '')


class TestOtherReadersSeeTextOnly(SimpleTestCase):

    def test_extract_text_returns_text_and_error(self):
        with patch.object(vision, '_vision_document_text',
                          return_value={'text': 'X', 'words': [{'text': 'X'}], 'error': None}):
            self.assertEqual(vision.extract_text(b'img', 'image/jpeg'), {'text': 'X', 'error': None})
