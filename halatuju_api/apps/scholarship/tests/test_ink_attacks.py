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
