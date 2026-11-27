"""OCR-14b-3 (owner decision B1, 27 Nov): the UniMAP lane's ONE excuse — a FULLY blank page 2 (no text, no image, no
drawing, no annotation; `pdf_rules_pages.fully_blank_page2`). Page 1, page 3 on, a 1-page letter and every other lane
are checked as before. The PDFs here are built in the test (made-up text only); the owner's real samples are checked
by the eval replay, not here (they are local only)."""
import io
import types
from unittest import mock

from django.test import SimpleTestCase, override_settings

from apps.scholarship import offer_exact, offer_parse, offer_parse_unimap, offer_parse_unisza, pdf_rules_pages
from apps.scholarship.offer_parse_unimap import LANE
from apps.scholarship.pdf_pages import MAX_LAYER_PAGES
from apps.scholarship.pdf_rules_pages import fully_blank_page2, pdf_rules_page_texts
from apps.scholarship.tests import test_offer_parse_unimap as um
from apps.scholarship.tests import test_offer_parse_unisza as us

_PINS = um.synthetic_pins()     # review round 2: the synthetic letter's footer and venue pinned, as in `um`


def setUpModule():
    _PINS.start()


def tearDownModule():
    _PINS.stop()


def _page1() -> bytes:
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(595, 842))
    c.setFont('Courier', 9)
    for i, ln in enumerate(('Tawaran kemasukan ke universiti contoh', 'Program Pengajian : Sarjana Muda Contoh',
                            'Sekian, terima kasih')):
        c.drawString(30, 800 - 14 * i, ln)
    c.showPage()
    c.save()
    return buf.getvalue()


def _stream(w, data: bytes, **keys):
    from pypdf.generic import DecodedStreamObject, NameObject
    s = DecodedStreamObject()
    s.set_data(data)
    for k, v in keys.items():
        s[NameObject('/' + k)] = v
    return w._add_object(s)


def _later(w, spec):
    """Add one later page: ``spec`` {ops: content bytes (None: no /Contents), xobjects: {name: ('form', ops) or
    ('image',)}, font: True (Helvetica as /F1), annots: a list of annotation dicts}."""
    from pypdf.generic import (ArrayObject, DictionaryObject, FloatObject, NameObject, NumberObject)
    page = w.add_blank_page(595, 842)
    res = DictionaryObject()
    if spec.get('font'):
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'),
                                 NameObject('/BaseFont'): NameObject('/Helvetica')})
        res[NameObject('/Font')] = DictionaryObject({NameObject('/F1'): w._add_object(font)})
    xo = DictionaryObject()
    box = ArrayObject([FloatObject(0), FloatObject(0), FloatObject(10), FloatObject(10)])
    for name, x in (spec.get('xobjects') or {}).items():
        if x[0] == 'form':
            xo[NameObject(name)] = _stream(w, x[1], Type=NameObject('/XObject'), Subtype=NameObject('/Form'), BBox=box)
        else:
            xo[NameObject(name)] = _stream(w, b'\xff', Type=NameObject('/XObject'), Subtype=NameObject('/Image'),
                                           Width=NumberObject(1), Height=NumberObject(1),
                                           ColorSpace=NameObject('/DeviceGray'), BitsPerComponent=NumberObject(8))
    if xo:
        res[NameObject('/XObject')] = xo
    page[NameObject('/Resources')] = res
    if spec.get('ops') is not None:
        page[NameObject('/Contents')] = _stream(w, spec['ops'])
    if spec.get('annots') is not None:
        page[NameObject('/Annots')] = ArrayObject([w._add_object(DictionaryObject(a)) for a in spec['annots']])


def letter(*later) -> bytes:
    """Page 1 drawn text (reportlab), then one page per ``later`` spec (`_later`)."""
    from pypdf import PdfReader, PdfWriter
    w = PdfWriter()
    w.add_page(PdfReader(io.BytesIO(_page1())).pages[0])
    for spec in later:
        _later(w, spec)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def blank(data) -> bool:
    return fully_blank_page2(data, pdf_rules_page_texts(data, MAX_LAYER_PAGES))


def _link(**extra):
    from pypdf.generic import ArrayObject, DictionaryObject, NameObject, NumberObject
    a = {NameObject('/Type'): NameObject('/Annot'), NameObject('/Subtype'): NameObject('/Link'),
         NameObject('/Rect'): ArrayObject([NumberObject(0), NumberObject(0), NumberObject(10), NumberObject(10)])}
    if extra.get('ap'):
        a[NameObject('/AP')] = DictionaryObject()
    return a


class FullyBlankPage2Test(SimpleTestCase):
    """What counts as FULLY blank, on real PDF bytes."""

    def test_a_page_with_no_content_or_empty_content_is_fully_blank(self):
        for case, spec in (('no_contents', {'ops': None}), ('empty', {'ops': b''}), ('spaces', {'ops': b'\n  \n'})):
            with self.subTest(case=case):
                data = letter(spec)
                self.assertEqual(pdf_rules_page_texts(data, MAX_LAYER_PAGES)[1:], [''])
                self.assertTrue(blank(data))

    def test_state_only_operators_paint_nothing(self):
        self.assertTrue(blank(letter({'ops': b'q 1 0 0 1 0 0 cm 0 g 1 w Q'})))

    def test_an_empty_form_is_a_page_object_to_pdfium(self):
        """Review round 1: pypdf finds nothing painted, but pdfium lists the form as a page object: not blank."""
        for case, spec in (('empty_form', {'ops': b'/X0 Do', 'xobjects': {'/X0': ('form', b'')}}),
                           ('state_form', {'ops': b'q /X0 Do Q', 'xobjects': {'/X0': ('form', b'q 0 g Q')}})):
            with self.subTest(case=case):
                data = letter(spec)
                self.assertEqual(pdf_rules_page_texts(data, MAX_LAYER_PAGES)[1:], [''])
                self.assertTrue(pdf_rules_pages._paints_nothing(*self._page2(data)))   # pypdf alone: blank
                self.assertFalse(blank(data))

    @staticmethod
    def _page2(data):
        from apps.scholarship import pdf_pages
        reader = pdf_pages._open_pdf(data)
        page = reader.pages[1]
        return page['/Contents'].get_object(), pdf_pages._resources(page), reader, {}, pdf_pages._Budget(), 0

    def test_pdfium_must_see_page_2_empty_too(self):
        """Review round 1: the second, independent check. pdfium missing, failing or spent (`pdfium_run.ask` None),
        or seeing anything on page 2, is not blank."""
        data = letter({'ops': b''})
        self.assertTrue(blank(data))
        real, asked = pdf_rules_pages.pdfium_run.ask, []

        def only_empty(answer):            # the shared S-visible read (``paints``) still asks the real child
            def ask(data_, ops):
                if ops[0]['op'] != 'empty':
                    return real(data_, ops)
                asked.append(ops)
                if isinstance(answer, Exception):
                    raise answer
                return answer
            return ask
        for case, answer in (('none', None), ('nothing', []), ('not_empty', [{'empty': []}]), ('error', [{}]),
                             ('other_page', [{'empty': [0]}]), ('raises', RuntimeError('no pdfium'))):
            asked.clear()
            with self.subTest(case=case), mock.patch.object(pdf_rules_pages.pdfium_run, 'ask', only_empty(answer)):
                self.assertFalse(blank(data))
                self.assertEqual(asked, [[{'op': 'empty', 'pages': [1], 'count': 2}]])

    def test_the_pdfium_child_counts_objects_and_annotations(self):
        from apps.scholarship import pdfium_run
        ops = [{'op': 'empty', 'pages': [0, 1], 'count': 2}]
        self.assertEqual(pdfium_run.ask(letter({'ops': b''}), ops), [{'empty': [1]}])
        self.assertEqual(pdfium_run.ask(letter({'ops': b'0 0 1 1 re f'}), ops), [{'empty': []}])
        self.assertEqual(pdfium_run.ask(letter({'ops': b'', 'annots': [_link()]}), ops), [{'empty': []}])
        self.assertEqual(pdfium_run.ask(letter({'ops': b''}), [{'op': 'empty', 'pages': [1], 'count': 3}]),
                         [{'empty': []}])                                  # another page count than pypdf's

    def test_empty_pages_refuses_on_any_pdfium_doubt(self):
        from apps.scholarship.pdfium_place import empty_pages

        class Page:
            raw = 'p'

            def close(self):
                pass

        def fake_raw(objects, annots=0):                         # pdfium's own call names, as attributes
            def count(page):
                if isinstance(objects, Exception):
                    raise objects
                return objects
            return types.SimpleNamespace(**{'FPDFPage_CountObjects': count,
                                            'FPDFPage_GetAnnotCount': lambda page: annots})

        pdf = [Page(), Page()]
        req = {'pages': [1], 'count': 2}
        self.assertEqual(empty_pages(fake_raw(0), pdf, req), {'empty': [1]})
        for case, raw in (('objects', fake_raw(1)), ('annots', fake_raw(0, 1)),
                          ('error', fake_raw(ValueError('x'))), ('minus', fake_raw(-1))):
            with self.subTest(case=case):
                self.assertEqual(empty_pages(raw, pdf, req), {'empty': []})
        self.assertEqual(empty_pages(fake_raw(0), pdf, {'pages': [5], 'count': 2}), {'empty': []})   # no such page
        self.assertEqual(empty_pages(fake_raw(0), pdf, {'pages': [1], 'count': 3}), {'empty': []})
        with self.assertRaises(MemoryError):
            empty_pages(fake_raw(MemoryError()), pdf, req)

    def test_one_tiny_white_rectangle_is_not_blank(self):
        for ops in (b'1 g 0 0 0.1 0.1 re f', b'1 1 1 rg 0 0 1 1 re f', b'0 0 m 1 1 l S', b'0 0 1 1 re W n',
                    b'0 0 1 1 re n', b'/Sh0 sh'):
            with self.subTest(ops=ops):
                self.assertFalse(blank(letter({'ops': ops})))

    def test_invisible_or_whitespace_text_is_not_blank(self):
        for ops in (b'BT /F1 9 Tf 3 Tr 30 30 Td (hidden words) Tj ET', b'BT /F1 9 Tf 30 30 Td (   ) Tj ET',
                    b'BT /F1 9 Tf 30 30 Td ET', b'BT ET'):
            with self.subTest(ops=ops):
                self.assertFalse(blank(letter({'ops': ops, 'font': True})))

    def test_an_image_is_not_blank(self):
        self.assertFalse(blank(letter({'ops': b'q 10 0 0 10 0 0 cm /Im0 Do Q', 'xobjects': {'/Im0': ('image',)}})))
        self.assertFalse(blank(letter({'ops': b'BI /W 1 /H 1 /CS /G /BPC 8 ID \xff EI'})))

    def test_a_form_that_draws_is_not_blank(self):
        for form in (b'0 0 1 1 re f', b'/X1 Do', b'BT /F1 9 Tf (a) Tj ET'):
            with self.subTest(form=form):
                self.assertFalse(blank(letter({'ops': b'/X0 Do', 'xobjects': {'/X0': ('form', form)}})))
        self.assertFalse(blank(letter({'ops': b'/Nope Do'})))          # a Do naming nothing

    def test_any_annotation_is_not_blank(self):
        for case, annots in (('link', [_link()]), ('link_ap', [_link(ap=True)]), ('empty_list', [])):
            with self.subTest(case=case):            # a plain label: pypdf objects do not cross pytest-xdist
                self.assertFalse(blank(letter({'ops': b'', 'annots': annots})))

    def test_only_page_2_is_judged(self):
        self.assertFalse(fully_blank_page2(letter(), pdf_rules_page_texts(letter(), MAX_LAYER_PAGES)))  # 1 page
        drawn2 = letter({'ops': b'BT /F1 9 Tf 30 30 Td (Lampiran A) Tj ET', 'font': True}, {'ops': b''})
        self.assertFalse(blank(drawn2))                                # a blank page 3 is never excused
        self.assertFalse(fully_blank_page2(letter({'ops': b''}), ['page one', 'not blank']))
        self.assertFalse(fully_blank_page2(b'%PDF-1.4 not a pdf', ['page one', '']))


def run(page_texts, blank_page2, lay=None):
    lay = lay if lay is not None else um.layout()
    p1 = um.plain(lay)
    pages = [p1] + list(page_texts)
    return offer_parse.diagnose('\n'.join(pages), p1, lay, pages, blank_page2=blank_page2)


class UnimapExcuseTest(SimpleTestCase):
    """The excuse in `diagnose_unimap`: page 2 only, and only when the bytes proved it fully blank."""

    def test_a_proven_blank_page_2_locks(self):
        d = run([''], True)
        self.assertIsNotNone(d['locked'], um.why(d))
        self.assertEqual(d['locked']['rules_lane'], LANE)

    def test_an_unproven_blank_page_2_still_refuses(self):
        self.assertEqual(run([''], False)['guard'], 'hidden_page')

    def test_everything_else_is_checked_as_before(self):
        self.assertEqual(run(['Lampiran A'], True)['guard'], 'later_page')       # page 2 with text
        self.assertEqual(run(['', ''], True)['guard'], 'hidden_page')            # two blank pages
        self.assertEqual(run(['Lampiran A', ''], True)['guard'], 'hidden_page')  # a blank page 3
        self.assertEqual(run(['', 'Lampiran A'], True)['guard'], 'later_page')   # page 3 with text
        self.assertEqual(run(['', '', ''], True)['guard'], 'too_many_pages')
        self.assertIsNotNone(run([], True)['locked'])                            # a 1-page letter, as before
        self.assertIsNotNone(run([], False)['locked'])
        self.assertEqual(run([''], True, lay=um.layout(dated='31 Februari 2026'))['guard'],
                         run([], False, lay=um.layout(dated='31 Februari 2026'))['guard'])   # page 1 as before

    def test_another_lane_ignores_the_flag(self):
        lay = us.layout()
        p1 = us.plain(lay)
        d = offer_parse.diagnose(p1 + '\n', p1, lay, [p1, ''], blank_page2=True)
        self.assertEqual((d['family'], d['guard']), ('unisza', 'hidden_page'))


class ExcuseWiringTest(SimpleTestCase):
    """`offer_exact.blank_page2_excused`: only a lane that makes the excuse reads the bytes for it."""

    def test_only_the_unimap_lane_asks(self):
        self.assertTrue(offer_parse_unimap.BLANK_PAGE2_EXCUSE)
        self.assertFalse(hasattr(offer_parse_unisza, 'BLANK_PAGE2_EXCUSE'))
        with mock.patch.object(pdf_rules_pages, 'fully_blank_page2', return_value=True) as proof:
            self.assertFalse(offer_exact.blank_page2_excused(offer_parse_unisza, b'%PDF', ['p1', '']))
            self.assertFalse(offer_exact.blank_page2_excused(None, b'%PDF', ['p1', '']))
            proof.assert_not_called()
            self.assertTrue(offer_exact.blank_page2_excused(offer_parse_unimap, b'%PDF', ['p1', '']))

    def test_unisza_still_refuses_a_real_blank_page_2(self):
        data = letter({'ops': b''})
        self.assertTrue(blank(data))                                     # fully blank, yet no excuse there
        self.assertFalse(offer_exact.blank_page2_excused(offer_parse_unisza, data,
                                                         pdf_rules_page_texts(data, MAX_LAYER_PAGES)))

    def _offer_read(self, proven, why_):
        lay = um.layout()
        p1 = um.plain(lay)
        with mock.patch.object(offer_exact, 'pdf_layers', return_value=(p1, p1)), \
                mock.patch('apps.scholarship.pdf_rules_pages.pdf_page1_layout', return_value=lay), \
                mock.patch('apps.scholarship.pdf_rules_pages.pdf_rules_page_texts', return_value=[p1, '']), \
                mock.patch('apps.scholarship.pdf_rules_pages.fully_blank_page2', return_value=proven), \
                mock.patch.object(offer_exact, '_not_inked', return_value=[]):
            return offer_exact.exact_offer_read(p1, image=b'%PDF', content_type='application/pdf',
                                                profile_nric=um.NRIC, why=why_)

    @override_settings(OCR_FIRST_LANES=[LANE])
    def test_exact_offer_read_passes_the_proof(self):
        self.assertEqual(self._offer_read(True, {})['rules_lane'], LANE)
        why_ = {}
        self.assertIsNone(self._offer_read(False, why_))
        self.assertEqual(why_, {'lane': LANE, 'reason': 'read_hidden_page'})

