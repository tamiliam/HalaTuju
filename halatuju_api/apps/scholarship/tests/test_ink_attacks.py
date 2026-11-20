"""S-visible 2 — the ink check through `exact_offer_read`, the ua:UMS lane ON, on REAL PDF bytes (reportlab;
made-up letter text from `ums()`). Each attack hides one owner phrase's line (phrase 9, "Sekiranya ...") so
that its text layer still holds it; every one must go to the AI with reason ``not_inked``. The controls lock."""
import io

from django.test import SimpleTestCase, override_settings
from unittest import mock

from apps.scholarship import pdf_pages, pdf_rules_pages, pdfium_run
from apps.scholarship.offer_exact import exact_offer_read
from apps.scholarship.offer_parse_university import LANE
from apps.scholarship.tests.test_offer_parse_university import ums

LINES = [ln for ln in ums().splitlines() if ln.strip()]
TARGET = next(ln for ln in LINES if ln.startswith('Sekiranya'))


def _white_png():
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (20, 20), 'white').save(buf, format='PNG')
    return buf.getvalue()


def _hit(c, mode, ln, y):
    """Draw the target line ``ln`` at ``y`` the ``mode`` way (True), or leave it to the caller (False)."""
    from reportlab.lib.utils import ImageReader
    colours = {'white': (1, 1, 1), 'grey': (0.93, 0.93, 0.93), 'samecolour': (0.2, 0.3, 0.8)}
    c.saveState()
    if mode == 'samecolour':
        c.setFillColorRGB(0.2, 0.3, 0.8)
        c.rect(25, y - 3, 560, 13, stroke=0, fill=1)
    if mode == 'clip':
        p = c.beginPath()
        p.rect(0, 0, 5, 5)
        c.clipPath(p, stroke=0, fill=0)
    c.setFillColorRGB(*colours.get(mode, (0, 0, 0)))
    if mode == 'alpha':
        c.setFillAlpha(0.05)
    c.setFont('Courier', 0.5 if mode == 'tiny' else 9)
    y = {'offpage': -200, 'cropbox': 50}.get(mode, y)
    if mode in ('form', 'formvisible'):
        c.beginForm(mode)
        c.setFillColorRGB(*((1, 1, 1) if mode == 'form' else (0, 0, 0)))
        c.setFont('Courier', 9)
        c.drawString(30, y, ln)
        c.endForm()
        c.doForm(mode)
    elif mode == 'squeeze':
        t = c.beginText(30, y)
        t.setFont('Courier', 9)
        t.setHorizScale(3)
        t.textLine(ln)
        c.drawText(t)
    else:
        c.drawString(30, y, ln)
    c.restoreState()
    if mode in ('covered', 'undertext'):
        c.setFillColorRGB(1, 1, 1)
        c.rect(25, y - 3, 560, 13, stroke=0, fill=1)
    if mode == 'undertext':                      # visible other text drawn over the hidden phrase
        c.setFillColorRGB(0, 0, 0)
        c.setFont('Courier', 9)
        c.drawString(30, y, 'Xyzzy plugh frobozz quux wibble wobble wubble flob')
    if mode == 'image':
        c.drawImage(ImageReader(io.BytesIO(_white_png())), 25, y - 3, 560, 13)


def build(mode='none', rotate=0):
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(595, 842))
    if mode == 'cropbox':
        c.setCropBox((0, 100, 595, 842))
    y = 800
    for ln in LINES:
        if ln == TARGET:
            _hit(c, mode, ln, y)
        else:
            c.setFont('Courier', 9)
            c.drawString(30, y, ln)
        y -= 14
    if mode == 'fullimage':
        c.drawImage(ImageReader(io.BytesIO(_white_png())), 0, 0, 595, 842)
    if mode == 'note':                           # an annotation other than a link (a viewer may draw it)
        c.textAnnotation('note', Rect=(30, 30, 60, 60))
    if mode == 'link':
        c.linkURL('https://www.ums.edu.my', (30, 30, 90, 40))
    c.showPage()
    c.save()
    return _rotated(buf.getvalue(), rotate) if rotate else buf.getvalue()


def _rotated(data, degrees):
    """The same page with /Rotate ``degrees`` (reportlab's own page rotation swaps the MediaBox: the top lines
    of a portrait letter then really lie off the page, and the ink check rightly refuses them)."""
    from pypdf import PdfReader, PdfWriter
    writer = PdfWriter()
    writer.add_page(PdfReader(io.BytesIO(data)).pages[0])
    writer.pages[0].rotate(degrees)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


ATTACKS = ('white', 'grey', 'alpha', 'covered', 'image', 'clip', 'tiny', 'offpage', 'cropbox', 'samecolour',
           'fullimage', 'undertext', 'squeeze')


def _read(data):
    why = {}
    ex = exact_offer_read(pdf_pages.pdf_text_layer(data), image=data, content_type='application/pdf', why=why)
    return ex, why


@override_settings(OCR_FIRST_LANES=(LANE,))
class TheLaneOn(SimpleTestCase):
    def setUp(self):
        pdf_pages._layer_memo_clear()

    def test_the_controls_lock(self):
        for mode, rotate in (('none', 0), ('link', 0), ('none', 90), ('none', 180), ('none', 270)):
            with self.subTest(mode=mode, rotate=rotate):
                ex, why = _read(build(mode, rotate))
                self.assertEqual((ex or {}).get('rules_lane'), LANE, why)
                self.assertEqual(why, {})

    def test_every_attack_goes_to_the_ai(self):
        for mode in ATTACKS:
            with self.subTest(mode=mode):
                ex, why = _read(build(mode))
                self.assertIsNone(ex)
                self.assertEqual((why.get('lane'), why.get('reason')), (LANE, 'not_inked'), why)
                self.assertTrue(why['ink_missing'])
                self.assertTrue(all(lab.startswith(('p', 'v:', 'page:')) for lab in why['ink_missing']))

    def test_text_inside_a_form_never_reaches_the_lock(self):
        """A line drawn inside a form XObject, white or black: S-visible 1 already refuses the text layer (the
        letter is no text-layer read), so neither locks and the ink check is not needed."""
        for mode in ('form', 'formvisible'):
            with self.subTest(mode=mode):
                self.assertIsNone(_read(build(mode))[0])

    def test_attacks_on_a_rotated_page(self):
        for mode in ('white', 'covered'):
            for rotate in (90, 180, 270):
                with self.subTest(mode=mode, rotate=rotate):
                    ex, why = _read(build(mode, rotate))
                    self.assertIsNone(ex)
                    self.assertEqual(why.get('reason'), 'not_inked')

    def test_a_note_annotation_refuses_the_page(self):
        ex, why = _read(build('note'))
        self.assertIsNone(ex)
        self.assertEqual(why['ink_missing'], ['page:annots'])

    def test_no_answer_from_the_child_is_no_lock(self):
        real = pdfium_run.ask

        def ask(data, ops):
            got = real(data, ops)
            return [{'error': 'x'} if o['op'] == 'ink' else g for o, g in zip(ops, got)] if got else got
        with mock.patch.object(pdfium_run, 'ask', side_effect=ask):
            ex, why = _read(build())
        self.assertIsNone(ex)
        self.assertEqual(why['ink_missing'], ['no_answer'])

    def test_one_child_answers_the_layout_and_the_ink(self):
        data = build()
        _read(data)
        with mock.patch.object(pdfium_run, '_spawn', wraps=pdfium_run._spawn) as spawned:
            ex, _why = _read(data)                 # every answer remembered: nothing spawns again
        self.assertEqual(ex['rules_lane'], LANE)
        self.assertEqual(spawned.call_count, 0)


# ── Review round 1: the reviewer's working attacks (B1 borrowed ink, B2 thin strip, B3 values never checked) ──
ICLINE = next(ln for ln in LINES if ln.startswith('No. Kad'))
KAMPUS = next(ln for ln in LINES if ln.startswith('Kampus'))
TITLE = next(ln for ln in LINES if ln.startswith('TAWARAN'))
DATED = next(ln for ln in LINES if ln.startswith('Tarikh :'))
VENUE = next(ln for ln in LINES if ln.startswith('Tempat'))
SPLIT = {KAMPUS: ':', TITLE: 'SABAH', DATED: ':', VENUE: ':'}


def _r1_line(c, mode, ln, y, strip):
    c.saveState()
    c.setFont('Courier', 9)
    if mode == 'whitetail':                          # the label black, its value white
        head, tail = ln.split(SPLIT[ln], 1)
        c.drawString(30, y, head + SPLIT[ln])
        c.setFillColorRGB(1, 1, 1)
        c.drawString(30 + 5.4 * len(head + SPLIT[ln]), y, tail)
    elif mode in ('squares', 'hyphens', 'white'):
        c.setFillColorRGB(1, 1, 1)                   # the line itself white: never visible
        c.drawString(30, y, ln)
    elif mode in ('strip', 'sliver'):                # Courier-Bold, filled (strip) or fill + stroke (sliver)
        t = c.beginText(30, y)
        t.setFont('Courier-Bold', 9)
        if mode == 'sliver':
            t.setTextRenderMode(2)
            c.setLineWidth(0.9)
        t.textLine(ln)
        c.drawText(t)
    elif mode == 'ocmark':                           # the line in optional content (a viewer may hide it)
        c._code.append('/OC <</Type /OCMD>> BDC')
        c.drawString(30, y, ln)
        c._code.append('EMC')
    else:
        c.drawString(30, y, ln)
    c.restoreState()
    c.saveState()                                    # what is drawn over the line leaves the rest of the page as is
    _r1_over(c, mode, y, strip)
    c.restoreState()


def _r1_over(c, mode, y, strip):
    if mode == 'squares':                            # a row of 60 pt black squares, text glyphs, over the line
        c.setFont('ZapfDingbats', 60)
        for k in range(14):
            c.drawString(24 + 42 * k, y - 15, 'n')
    elif mode == 'hyphens':                          # stroked hyphens, 16 pt wide, over the line
        t = c.beginText(26, y + 9)
        t.setFont('Courier', 9)
        t.setTextRenderMode(1)
        c.setLineWidth(16)
        t.textLine('-' * 64)
        c.drawText(t)
    elif mode in ('strip', 'sliver'):                # all but a ``strip`` pt band at the foot covered white
        c.setFillColorRGB(1, 1, 1)
        c.rect(25, y + strip, 565, 8.5 - strip, stroke=0, fill=1)
    elif mode == 'ocimage':
        from reportlab.lib.utils import ImageReader
        c.drawImage(ImageReader(io.BytesIO(_white_png())), 500, 30, 20, 20)


def build_r1(mode, target=TARGET, strip=1.0):
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(595, 842))
    y = 800
    for ln in LINES:
        if ln == target:
            _r1_line(c, mode, ln, y, strip)
        else:
            c.setFont('Courier', 9)
            c.drawString(30, y, ln)
        y -= 14
    c.showPage()
    c.save()
    data = buf.getvalue()
    return _edited(data, mode, 800 - 14 * LINES.index(target)) if mode in ('linkap', 'ocimage', 'xfa') else data


def _edited(data, mode, y):
    """linkap: a /Link whose own appearance is a white box over the line at ``y``; ocimage: the page's image in
    optional content; xfa: the document carries an XFA form."""
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import (ArrayObject, DecodedStreamObject, DictionaryObject, FloatObject, NameObject,
                               NumberObject, TextStringObject)
    w, n = PdfWriter(), NameObject
    w.append(PdfReader(io.BytesIO(data)))
    if mode == 'linkap':
        ap = DecodedStreamObject()
        ap.set_data(b'1 g 0 0 560 13 re f')
        ap.update({n('/Type'): n('/XObject'), n('/Subtype'): n('/Form'),
                   n('/BBox'): ArrayObject([FloatObject(0), FloatObject(0), FloatObject(560), FloatObject(13)])})
        annot = DictionaryObject({
            n('/Type'): n('/Annot'), n('/Subtype'): n('/Link'), n('/F'): NumberObject(4),
            n('/Rect'): ArrayObject([FloatObject(25), FloatObject(y - 3), FloatObject(585), FloatObject(y + 10)]),
            n('/Border'): ArrayObject([NumberObject(0)] * 3), n('/AP'): DictionaryObject({n('/N'): w._add_object(ap)})})
        w.pages[0][n('/Annots')] = ArrayObject([w._add_object(annot)])
    elif mode == 'ocimage':
        ocg = w._add_object(DictionaryObject({n('/Type'): n('/OCG'), n('/Name'): TextStringObject('x')}))
        for ref in w.pages[0]['/Resources']['/XObject'].values():
            ref.get_object()[n('/OC')] = ocg
    else:
        w._root_object[n('/AcroForm')] = DictionaryObject({n('/Fields'): ArrayObject(), n('/XFA'): ArrayObject()})
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()


@override_settings(OCR_FIRST_LANES=(LANE,))
class TheReviewRound1Attacks(SimpleTestCase):
    def setUp(self):
        pdf_pages._layer_memo_clear()

    def _refused(self, data, label=None):
        ex, why = _read(data)
        self.assertIsNone(ex)
        self.assertEqual((why.get('lane'), why.get('reason')), (LANE, 'not_inked'), why)
        if label:
            self.assertIn(label, why['ink_missing'])
        return why

    def test_the_controls_still_lock(self):
        for mode, strip in (('none', 1.0), ('strip', 9.0)):    # Courier-Bold with no box over it locks
            with self.subTest(mode=mode):
                ex, why = _read(build_r1(mode, strip=strip))
                self.assertEqual((ex or {}).get('rules_lane'), LANE, why)

    def test_b1_large_black_squares_over_a_white_line(self):
        for target in (TARGET, ICLINE):
            with self.subTest(target=target[:8]):
                self._refused(build_r1('squares', target))

    def test_b1_stroked_text_lends_no_ink(self):
        for mode in ('hyphens', 'sliver'):
            with self.subTest(mode=mode):
                self._refused(build_r1(mode), 'page:modes')

    def test_b2_a_thin_strip_left_uncovered(self):
        for target in (TARGET, ICLINE):
            for strip in (0.5, 1.0, 1.5, 2.0):
                with self.subTest(target=target[:8], strip=strip):
                    self._refused(build_r1('strip', target, strip))

    def test_b3_a_hidden_value_is_never_read_unchecked(self):
        for mode, target, label in (('white', KAMPUS, None), ('whitetail', KAMPUS, 'v:campus'),
                                    ('whitetail', TITLE, 'v:intake'), ('whitetail', DATED, 'v:offer_date'),
                                    ('whitetail', VENUE, 'v:venue')):
            with self.subTest(mode=mode, target=target[:8]):
                ex, why = _read(build_r1(mode, target))
                self.assertIsNone(ex, (ex or {}).get('fields'))
                if label:
                    self.assertIn(label, why.get('ink_missing') or [], why)

    def test_a_link_drawing_its_own_appearance(self):
        self._refused(build_r1('linkap'), 'p9')        # pdfium draws the white box: no ink under it

    def test_optional_content_and_xfa(self):
        for mode, label in (('ocimage', 'page:optional'), ('xfa', 'page:xfa')):
            with self.subTest(mode=mode):
                self._refused(build_r1(mode), label)
        data = build_r1('ocmark')                   # S-visible 1 may refuse it first; the child flags it too
        self.assertIsNone(_read(data)[0])
        from apps.scholarship import pdf_ink
        self.assertIs(pdf_ink.page1_ink(data)['optional'], True)


def _with_type3(data, glyph: bytes, shown=b'BT /T3 9 Tf 30 30 Td (a) Tj ET'):
    """``data`` with a one-glyph Type3 font /T3 (code ``a``, procedure ``glyph`` in a 1-unit glyph space at Tf 9)
    shown by ``shown`` on page 1."""
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject, FloatObject, NameObject, NumberObject
    w = PdfWriter()
    w.append(PdfReader(io.BytesIO(data)))
    page = w.pages[0]

    def stream(body):
        s = DecodedStreamObject()
        s.set_data(body)
        return w._add_object(s)
    font = DictionaryObject({
        NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type3'),
        NameObject('/FontBBox'): ArrayObject([FloatObject(v) for v in (0, 0, 1, 1)]),
        NameObject('/FontMatrix'): ArrayObject([FloatObject(v) for v in (1, 0, 0, 1, 0, 0)]),
        NameObject('/CharProcs'): DictionaryObject({NameObject('/g'): stream(glyph)}),
        NameObject('/Encoding'): DictionaryObject({NameObject('/Type'): NameObject('/Encoding'),
                                                   NameObject('/Differences'): ArrayObject([NumberObject(97),
                                                                                            NameObject('/g')])}),
        NameObject('/FirstChar'): NumberObject(97), NameObject('/LastChar'): NumberObject(97),
        NameObject('/Widths'): ArrayObject([FloatObject(1)])})
    res = page['/Resources'].get_object()
    res['/Font'].get_object()[NameObject('/T3')] = w._add_object(font)
    old = page['/Contents'].get_object()
    page[NameObject('/Contents')] = ArrayObject((list(old) if isinstance(old, ArrayObject)
                                                 else [page.raw_get('/Contents')]) + [stream(shown)])
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()


@override_settings(OCR_FIRST_LANES=(LANE,))
class TheReviewRound2Attacks(SimpleTestCase):
    """Review round 2, B2: a Type3 glyph painting outside its own ``d1`` box (a tiny glyph in the margin drawing
    boxes over a white word) puts ink where no char box is. Every Type3 glyph page 1 can reach is checked."""

    def setUp(self):
        pdf_pages._layer_memo_clear()

    def test_a_well_behaved_type3_font_still_locks(self):
        for glyph in (b'1 0 0 0 1 1 d1 0 0 1 1 re f', b'1 0 0 0 1 1 d1 0 0 m 1 0 l 0.5 1 l h f'):
            with self.subTest(glyph=glyph):
                ex, why = _read(_with_type3(build('none'), glyph))
                self.assertEqual((ex or {}).get('rules_lane'), LANE, why)

    def test_a_glyph_painting_outside_its_box_refuses(self):
        for glyph in (b'1 0 0 0 1 1 d1 0 0 1 1 re f 0 70 60 1.5 re f',             # boxes far from the glyph
                      b'1 0 d0 0 0 1 1 re f',                                       # d0: may not paint at all
                      b'0 0 1 1 re f'):                                             # no d0 / d1 first
            with self.subTest(glyph=glyph):
                ex, why = _read(_with_type3(build('none'), glyph))
                self.assertIsNone(ex)
                self.assertEqual((why.get('lane'), why.get('reason')), (LANE, 'not_inked'), why)
                self.assertIn('page:type3', why['ink_missing'])

    def test_every_operator_outside_the_list_is_refused(self):
        """A matrix, shading, XObject, inline image or stroke in a glyph: S-visible 1's own Type3 whitelist refuses
        most of these first (no lock either way); `_type3_ok` refuses each by itself too."""
        from pypdf import PdfReader
        from apps.scholarship import pdfium_worker
        for glyph, ok in ((b'1 0 0 0 1 1 d1 0 0 1 1 re f', True), (b'1 0 d0 0.5 g', True),
                          (b'1 0 0 0 1 1 d1 60 0 0 60 0 70 cm 0 0 1 1 re f', False), (b'1 0 d0 0 0 1 1 re f', False),
                          (b'1 0 0 0 1 1 d1 /Sh sh', False), (b'1 0 0 0 1 1 d1 /X Do', False),
                          (b'1 0 0 0 1 1 d1 /G gs 0 0 1 1 re f', False),
                          (b'1 0 0 0 1 1 d1 BI /W 1 /H 1 /BPC 8 /CS /G ID \x00 EI', False),
                          (b'1 0 0 0 1 1 d1 0 0 m 1 1 l S', False), (b'1 0 0 0 1 1 d1 BT ET', False)):
            with self.subTest(glyph=glyph[:40]):
                data = _with_type3(build('none'), glyph)
                font = PdfReader(io.BytesIO(data)).pages[0]['/Resources']['/Font']['/T3'].get_object()
                self.assertIs(pdfium_worker._type3_ok(font, [pdfium_worker.T3_MAX_BYTES]), ok)
                if not ok:
                    self.assertIsNone(_read(data)[0])
        self.assertIs(pdfium_worker._type3_ok(font, [3]), False)        # past the byte budget

    def test_a_glyph_within_the_tolerance_of_its_box_passes(self):
        from apps.scholarship import pdfium_worker
        tol = pdfium_worker.T3_TOLERANCE
        inside = b'1 0 0 0 1 1 d1 0 0 %.3f %.3f re f' % (1 + tol / 2, 1 + tol / 2)
        outside = b'1 0 0 0 1 1 d1 0 0 %.3f 1 re f' % (1 + 2 * tol)
        self.assertEqual(_read(_with_type3(build('none'), inside))[1], {})
        self.assertIn('page:type3', _read(_with_type3(build('none'), outside))[1]['ink_missing'])


class EveryReturnedFieldIsInkChecked(SimpleTestCase):
    """Review round 1, B3: a field `read_ums` returns is an ink target, or named as not printed on the page."""

    def test_every_field(self):
        from apps.scholarship.offer_parse_university import INK_LABELS, NOT_PRINTED, ink_targets, read_ums
        fields, reason = read_ums(ums())
        self.assertEqual(reason, '')
        self.assertEqual(set(fields) - set(INK_LABELS) - set(NOT_PRINTED), set())
        _phrases, values = ink_targets(fields, ums())
        want = {INK_LABELS[k] for k, v in fields.items() if k in INK_LABELS and str(v).strip()}
        self.assertEqual(want - {lab for lab, _t in values}, set())
        self.assertEqual(len(want), len(INK_LABELS))            # the synthetic letter prints every one


class TestTheLayoutRunsInTheChild(SimpleTestCase):
    """Review round 1 #11 (moved from `test_offer_parse_university.py`): page 1's layout text comes from the pdfium
    child, under its limits; S-visible 2 asks the ink op in the same request."""

    def setUp(self):
        pdf_pages._layer_memo_clear()

    def test_the_child_reads_the_layout(self):
        from apps.scholarship.tests.test_ocr_visible import _pdf, _show
        self.assertEqual(pdf_rules_pages.pdf_page1_layout(_pdf([_show('Nama   ZORBEX QUENTARO')])), 'Nama   ZORBEX QUENTARO')

    def test_no_answer_from_the_child_is_no_layout(self):
        from apps.scholarship.tests.test_ocr_visible import _pdf, _show
        real, asked = pdfium_run.ask, []

        def ask(data, ops):                     # the visibility check runs as before; the layout op gets nothing
            asked.append(ops)
            return None if ops[:1] == [{'op': 'layout'}] else real(data, ops)
        with mock.patch('apps.scholarship.pdfium_run.ask', side_effect=ask):
            self.assertEqual(pdf_rules_pages.pdf_page1_layout(_pdf([_show('Nama   ZORBEX QUENTARO')])), '')
        layout_asks = [ops for ops in asked if ops[:1] == [{'op': 'layout'}]]
        self.assertEqual([[o['op'] for o in ops] for ops in layout_asks], [['layout', 'ink']])


class TheLaneOff(SimpleTestCase):
    @override_settings(OCR_FIRST_LANES=())
    def test_no_ink_op_is_asked(self):
        pdf_pages._layer_memo_clear()
        with mock.patch.object(pdfium_run, 'ask', wraps=pdfium_run.ask) as ask:
            ex, why = _read(build('white'))
        self.assertIsNone(ex)
        self.assertEqual(why, {'lane': LANE, 'reason': 'lane_off'})
        self.assertFalse([c for c in ask.call_args_list if any(o.get('op') in ('ink', 'layout') for o in c.args[1])])
