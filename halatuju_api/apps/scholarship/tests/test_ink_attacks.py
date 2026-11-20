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
SPLIT = {KAMPUS: ':', TITLE: 'SABAH', DATED: ':', VENUE: ':', ICLINE: ':'}


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


def _type3_allowed():
    """The S2 path (a lane in `pdf_ink.TYPE3_LANES`): the ua:UMS lane allowed to carry Type3, for these tests only."""
    from apps.scholarship import pdf_ink
    return mock.patch.object(pdf_ink, 'TYPE3_LANES', frozenset((LANE,)))


WELL_BEHAVED = (b'1 0 0 0 1 1 d1 0 0 1 1 re f', b'1 0 0 0 1 1 d1 0 0 m 1 0 l 0.5 1 l h f')


@override_settings(OCR_FIRST_LANES=(LANE,))
class TheReviewRound2Attacks(SimpleTestCase):
    """Review round 2, B2: a Type3 glyph painting outside its own ``d1`` box (a tiny glyph in the margin drawing
    boxes over a white word) puts ink where no char box is. Every Type3 glyph page 1 can reach is checked. Fix
    round 3: a UMS letter refuses ANY Type3 font, so these run with the lane allowed (`_type3_allowed`)."""

    def setUp(self):
        pdf_pages._layer_memo_clear()
        allowed = _type3_allowed()
        allowed.start()
        self.addCleanup(allowed.stop)

    def test_a_well_behaved_type3_font_locks_where_type3_is_allowed(self):
        for glyph in WELL_BEHAVED:
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


def build_t3tol(iso=False):
    """Review round 3's BLOCKER: the IC line's label black, its value white, and under it one Type3 glyph whose
    ``d1`` box is FLAT (1000 x 1 units). `T3_TOLERANCE` is a share of the box's longer side, so the glyph may paint
    20 units above it: one block over each digit's box, which pdfium credits to the white digits. ``iso``: the same
    glyph at an equal x / y scale (FontMatrix) instead of one stretched to the value's width."""
    from apps.scholarship import pdf_ink
    base = build_r1('whitetail', ICLINE)
    value = ICLINE.split(':', 1)[1].strip()
    chars = pdf_ink.page1_ink(base)['chars']
    at = ''.join(chr(int(r[0])) for r in chars).index(value)
    box = chars[at:at + len(value)]
    left, right = min(r[2] for r in box), max(r[4] for r in box)
    bottom, top = min(r[3] for r in box), max(r[5] for r in box)
    sy = (top - bottom) / 20.0
    sx = sy if iso else (right - left) / 1000.0
    rects = b''.join(b'%.3f 1 %.3f 20 re ' % ((r[2] - left) / sx, (r[4] - r[2]) / sx)
                     for k, r in enumerate(box) if value[k] != '-')
    shown = b'q 0 g BT /T3 1 Tf 1 0 0 1 %.4f %.4f Tm (a) Tj ET Q\n' % (left, bottom - sy)
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import ArrayObject, FloatObject, NameObject
    data = _with_type3(base, b'0 0 0 0 1000 1 d1 ' + rects + b'f', shown)
    w = PdfWriter()                                  # the font's own matrix, box and width (`_with_type3`: 1 unit)
    w.append(PdfReader(io.BytesIO(data)))
    font = w.pages[0]['/Resources']['/Font']['/T3'].get_object()
    font[NameObject('/FontMatrix')] = ArrayObject([FloatObject(v) for v in (sx, 0, 0, sy, 0, 0)])
    font[NameObject('/FontBBox')] = ArrayObject([FloatObject(v) for v in (0, 0, 1000, 21)])
    font[NameObject('/Widths')] = ArrayObject([FloatObject(0)])
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()


@override_settings(OCR_FIRST_LANES=(LANE,))
class TheReviewRound3Type3Attack(SimpleTestCase):
    """Review round 3, BLOCKER (fix round 3, owner 20 Nov: "refuse home-made fonts on UMS letters"): a flat Type3
    glyph painting blocks onto a white IC value locked. A UMS letter now refuses ANY Type3 font on page 1
    (``page:type3``; `pdf_ink.TYPE3_LANES` is empty), so neither the attack nor a well-behaved Type3 font locks."""

    def setUp(self):
        pdf_pages._layer_memo_clear()

    def test_the_flat_glyph_attack_refuses(self):
        for iso in (False, True):
            with self.subTest(iso=iso):
                ex, why = _read(build_t3tol(iso))
                self.assertIsNone(ex, (ex or {}).get('fields'))
                self.assertEqual((why.get('lane'), why.get('reason')), (LANE, 'not_inked'), why)
                self.assertIn('page:type3', why['ink_missing'])

    def test_a_well_behaved_type3_font_refuses_a_ums_letter(self):
        for glyph in WELL_BEHAVED:
            with self.subTest(glyph=glyph):
                ex, why = _read(_with_type3(build('none'), glyph))
                self.assertIsNone(ex)
                self.assertEqual(why.get('ink_missing'), ['page:type3'], why)

    def test_the_static_check_still_passes_the_flat_glyph(self):
        """Why `TYPE3_LANES` stays empty: `_type3_ok` alone passes the attack (its tolerance scales with the box's
        longer side). Before a lane allows Type3 (S2, UiTM), the tolerance must be ~0 or about one device pixel
        after FontMatrix and text matrix, or Type3 ink credited to the glyph outline (decisions.md, 20 Nov), and
        this test turned round."""
        from pypdf import PdfReader
        from apps.scholarship import pdfium_worker
        for iso in (False, True):
            with self.subTest(iso=iso):
                font = PdfReader(io.BytesIO(build_t3tol(iso))).pages[0]['/Resources']['/Font']['/T3'].get_object()
                self.assertIs(pdfium_worker._type3_ok(font, [pdfium_worker.T3_MAX_BYTES]), True)

    def test_the_child_says_type3(self):
        from apps.scholarship import pdf_ink
        self.assertIs(pdf_ink.page1_ink(build('none'))['type3'], False)
        self.assertIs(pdf_ink.page1_ink(_with_type3(build('none'), WELL_BEHAVED[0]))['type3'], True)


def build_t3deep(chain=15):
    """Review of fix round 3: `build_t3tol`'s flat glyph moved into a form Y the page draws as page -> /S Do ->
    /Y Do. The page lists /S, then /A: A1 .. A``chain`` are forms never drawn, A_k lists A_(k+1) and the last lists
    Y, so the Type3 walk (depth first, last listed first) meets Y first at depth ``chain`` + 1. S also lists
    A``chain`` .. A2 (that order), so the load check (depth first, in listed order) meets each at depth 2. ``chain`` 0: page -> S -> Y alone (the control)."""
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import (ArrayObject, DecodedStreamObject, DictionaryObject, FloatObject, NameObject,
                               NumberObject)
    w = PdfWriter()
    w.append(PdfReader(io.BytesIO(build_t3tol())))
    page = w.pages[0]
    res = page['/Resources'].get_object()
    fonts = res['/Font'].get_object()
    t3 = fonts.raw_get('/T3')
    del fonts['/T3']
    cmap = DecodedStreamObject()                     # the glyph's text a space: pypdf's layout, which cannot see
    cmap.set_data(b'/CIDInit /ProcSet findresource begin 12 dict begin begincmap /CMapName /T3U def '  # Y's font,
                  b'1 begincodespacerange <00> <FF> endcodespacerange 1 beginbfchar <61> <0020> endbfchar '  # then
                  b'endcmap CMapName currentdict /CMap defineresource pop end end')    # holds the same characters
    t3.get_object()[NameObject('/ToUnicode')] = w._add_object(cmap)
    contents = list(page['/Contents'].get_object())
    shown = contents[-1].get_object().get_data()

    def form(body, xobjects=None, font=None):
        s = DecodedStreamObject()
        s.set_data(body)
        s.update({NameObject('/Type'): NameObject('/XObject'), NameObject('/Subtype'): NameObject('/Form'),
                  NameObject('/BBox'): ArrayObject([NumberObject(v) for v in (0, 0, 595, 842)]),
                  NameObject('/Matrix'): ArrayObject([FloatObject(v) for v in (1, 0, 0, 1, 0, 0)])})
        r = DictionaryObject()
        if font is not None:
            r[NameObject('/Font')] = DictionaryObject({NameObject('/T3'): font})
        if xobjects:
            r[NameObject('/XObject')] = DictionaryObject({NameObject(k): v for k, v in xobjects})
        s[NameObject('/Resources')] = r
        return w._add_object(s)
    y = form(shown, font=t3)
    chain_refs, nxt = [], y
    for k in range(chain, 0, -1):                     # A_chain lists Y; A_k lists A_(k+1)
        nxt = form(b'', [('/N', nxt)])
        chain_refs.insert(0, nxt)
    later = [('/A%d' % (k + 2), ref) for k, ref in enumerate(chain_refs[1:])]
    s = form(b'/Y Do', [('/Y', y)] + later[::-1])    # deepest first: the load check meets each at depth 2
    xo = DictionaryObject({NameObject('/S'): s})
    if chain_refs:
        xo[NameObject('/A')] = chain_refs[0]
    res[NameObject('/XObject')] = xo
    body = DecodedStreamObject()
    body.set_data(b'q /S Do Q')
    page[NameObject('/Contents')] = ArrayObject(contents[:-1] + [w._add_object(body)])
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()


@override_settings(OCR_FIRST_LANES=(LANE,))
class TheType3WalkCutShort(SimpleTestCase):
    """Review of fix round 3: the Type3 walk dropped resources past depth 15 silently, and a form marked seen when
    first LISTED deep in a never-drawn chain was never walked from the shallow path that draws it, so a Type3 font
    in it went unseen (the chain-15 attack LOCKED a UMS letter). A walk cut short now counts as Type3 that fails
    (``type3`` True, ``type3_ok`` False); chain 0 is the control."""

    def setUp(self):
        pdf_pages._layer_memo_clear()

    def test_a_type3_font_past_the_depth_limit_counts_as_type3(self):
        from apps.scholarship import pdf_ink
        for chain in (0, 15):
            with self.subTest(chain=chain):
                ink = pdf_ink.page1_ink(build_t3deep(chain))
                self.assertIs(ink['type3'], True)
                if chain:
                    self.assertIs(ink['type3_ok'], False)

    def test_the_deep_attack_refuses_a_ums_letter(self):
        for chain in (0, 15):
            with self.subTest(chain=chain):
                ex, why = _read(build_t3deep(chain))
                self.assertIsNone(ex, (ex or {}).get('fields'))
                self.assertEqual((why.get('lane'), why.get('reason')), (LANE, 'not_inked'), why)
                self.assertIn('page:type3', why['ink_missing'])

    def test_the_deep_attack_refuses_even_where_type3_is_allowed(self):
        with _type3_allowed():
            ex, why = _read(build_t3deep(15))
        self.assertIsNone(ex, (ex or {}).get('fields'))
        self.assertIn('page:type3', why.get('ink_missing') or [], why)


def _wrapped(data, head: bytes, tail: bytes, zapf=False):
    """``data`` with page 1's content between ``head`` and ``tail`` (and /FZ, ZapfDingbats, among its fonts)."""
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject, NameObject
    w = PdfWriter()
    w.append(PdfReader(io.BytesIO(data)))
    page = w.pages[0]

    def stream(body):
        s = DecodedStreamObject()
        s.set_data(body)
        return w._add_object(s)
    if zapf:
        page['/Resources'].get_object()['/Font'].get_object()[NameObject('/FZ')] = w._add_object(DictionaryObject({
            NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'),
            NameObject('/BaseFont'): NameObject('/ZapfDingbats')}))
    old = page['/Contents'].get_object()
    page[NameObject('/Contents')] = ArrayObject([stream(head)] + (list(old) if isinstance(old, ArrayObject)
                                                                  else [page.raw_get('/Contents')]) + [stream(tail)])
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()


def build_ring(sides='tb', gap=0.0, shift=0.0, bar=2.0, mode='whitetail'):
    """The IC line's label black, its value white (``mode`` 'whitetail'; 'none': all black), the whole page moved
    ``shift`` pt (another pixel phase), and each value character ringed by black bars ``gap`` pt off its box on
    ``sides`` (t/b/l/r): ZapfDingbats 'n' (a square) squeezed to the character's width, or ``bar`` pt wide and as
    tall as the character at its left and right."""
    from apps.scholarship import pdf_ink
    data = _wrapped(build_r1(mode, ICLINE), b'q 1 0 0 1 %.3f %.3f cm\n' % (shift, shift), b'Q\n')
    value = ICLINE.split(':', 1)[1].strip()
    chars = pdf_ink.page1_ink(data)['chars']
    at = ''.join(chr(int(r[0])) for r in chars).index(value)
    size, bars = 8.0, b'q 0 g BT /FZ 8 Tf '
    for r in chars[at:at + len(value)]:
        l, b, rt, t = r[2], r[3], r[4], r[5]
        kz = (rt - l) * 100 / (0.692 * size)                 # ZapfDingbats 'n': 0.692 x 0.705 em, from x 0.035 em
        x0 = l - 0.035 * size * kz / 100
        if 't' in sides:
            bars += b'%.3f Tz 1 0 0 1 %.3f %.3f Tm (n) Tj ' % (kz, x0, t + gap)
        if 'b' in sides:
            bars += b'%.3f Tz 1 0 0 1 %.3f %.3f Tm (n) Tj ' % (kz, x0, b - gap - 0.705 * size)
        tall = (t - b) / 0.705
        kz2 = bar * 100 / (0.692 * tall)
        for side, xs in (('l', l - gap - bar), ('r', rt + gap)):
            if side in sides:
                bars += b'/FZ %.3f Tf %.3f Tz 1 0 0 1 %.3f %.3f Tm (n) Tj /FZ 8 Tf ' % (
                    tall, kz2, xs - 0.035 * tall * kz2 / 100, b)
    return _wrapped(data, b'', bars + b'ET Q\n', zapf=True)


@override_settings(OCR_FIRST_LANES=(LANE,))
class TheReviewRound2bRingAttack(SimpleTestCase):
    """Review round 2b: black glyphs TOUCHING a white character put their edge pixels in its box (+1 px), and a
    white IC value under a black label locked. A pixel is now a character's ink only when the other drawn
    characters cannot explain its change (`pdfium_worker._ink`). Rules and paths are in both pictures, so only
    text can lend ink; the rings here are ZapfDingbats glyphs."""

    def setUp(self):
        pdf_pages._layer_memo_clear()

    def test_bars_near_a_black_value_still_lock(self):
        """Bars TOUCHING a black value refuse it too (no lock, the AI reads it): their boxes explain its edges."""
        for sides, gap in (('tb', 0.36), ('tb', 1.0)):
            with self.subTest(sides=sides, gap=gap):
                ex, why = _read(build_ring(sides, gap, mode='none'))
                self.assertEqual((ex or {}).get('rules_lane'), LANE, why)

    def test_a_ring_around_a_white_value_refuses(self):
        for sides, gap, shift, bar in (('tb', 0.0, 0.0, 2.0), ('tb', -0.1, 0.0, 2.0), ('tb', 0.36, 0.0, 2.0),
                                       ('tb', 0.5, 0.0, 2.0), ('tb', 0.72, 0.0, 2.0), ('tb', 0.0, 0.54, 2.0),
                                       ('tb', 0.2, 0.54, 2.0), ('t', 0.0, 0.0, 2.0), ('t', 0.0, 0.54, 2.0),
                                       ('lr', 0.0, 0.0, 0.5), ('lr', 0.0, 0.54, 1.0), ('tblr', 0.0, 0.0, 2.0),
                                       ('tblr', 0.36, 0.66, 0.5)):
            with self.subTest(sides=sides, gap=gap, shift=shift, bar=bar):
                ex, why = _read(build_ring(sides, gap, shift, bar))
                self.assertIsNone(ex, (ex or {}).get('fields'))
                self.assertEqual((why.get('lane'), why.get('reason')), (LANE, 'not_inked'), why)
                self.assertIn('v:nric', why['ink_missing'])


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
