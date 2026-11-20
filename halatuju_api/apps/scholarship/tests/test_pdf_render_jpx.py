"""TD-692: what a genuine scanned letter's page may hold that the render pre-filter used to refuse.

A JPEG2000 (JPX) image (charged by its own header; an unread header refused) and an ASCIIHex stream (decoded and
charged). JBIG2 is NOT allowed (TD-697): an image or mask using it is refused. Synthetic PDFs only.
"""
import io
import math
import zlib

from django.test import SimpleTestCase

from apps.scholarship import pdf_jpx, pdf_pages, pdf_pdfium_load, pdf_render_check
from apps.scholarship.pdf_layer_guards import ascii_hex
from apps.scholarship.tests.test_ocr_visible import SPM_TEXT, _show, _stream
from apps.scholarship.tests.test_pdf_render_check import FULL_PAGE, _a4, _annotated, _image


def _cost(pdf):
    reader = pdf_pages._open_pdf(pdf)
    return pdf_render_check.page_cost(reader.pages[0], reader)


def _refusal(pdf):
    return pdf_render_check.render_refusal(pdf, lambda n: [0])[1]



# ── TD-692: a JPEG2000 (JPX) image on page content was refused as "an image filter outside the whitelist", so a
#    genuine scanned letter got no page image and was stored unreadable. It is now charged like any image, by the
#    LARGER of its dictionary's size and its own header's (never decoded here), and by its decode work (review 3,
#    `ADecodeWork` below); the child's time limit stays the backstop.
_RED = (200, 10, 10)


def _jpx_bytes(w, h, codestream=False):
    """A real JPEG2000 file written by Pillow (OpenJPEG): a JP2 file, or a bare codestream."""
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (w, h), _RED).save(buf, 'JPEG2000', **({'no_jp2': True} if codestream else {}))
    return buf.getvalue()


def _claiming(data, x, y, comps=None):
    """``data`` (a real JPX file) with its SIZ marker claiming ``x`` x ``y`` pixels in one tile (and ``comps``
    components); a JP2 file's ihdr box is left as it was."""
    at = data.index(b'\xff\x4f\xff\x51')
    siz = bytearray(data)
    for off, v in ((8, x), (12, y), (24, x), (28, y)):              # Xsiz, Ysiz, XTsiz, YTsiz
        siz[at + off:at + off + 4] = v.to_bytes(4, 'big')
    if comps is not None:
        siz[at + 40:at + 42] = comps.to_bytes(2, 'big')
    return bytes(siz)


def _jpx(w, h, data, filters=b'/JPXDecode', extra=b'', cs=b'/DeviceRGB'):
    """A JPX image XObject whose dictionary says ``w`` x ``h``."""
    return _stream(b'<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace ' % (w, h) + cs
                   + b' /BitsPerComponent 8 /Filter ' + filters + b' ' + extra, data)


def _jpx_page(img, draws=1, objs=None):
    return _a4(b'q ' + FULL_PAGE + b'/Im0 Do\n' * draws + b'Q', b'/XObject << /Im0 6 0 R >>', {6: img, **(objs or {})})


def _png_centre(png):
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert('RGB')
    return im.getpixel((im.width // 2, im.height // 2))


def _jp2_after_a_free_box(n):
    """A JP2 file whose codestream box follows an ``n``-byte free box (no header box: the check only reads
    where the codestream starts)."""
    return (b'\x00\x00\x00\x0cjP  \r\n\x87\n' + (8 + n).to_bytes(4, 'big') + b'free' + b'\x00' * n
            + b'\x00\x00\x00\x00jp2c' + _jpx_bytes(40, 30, True))


class AJpeg2000Image(SimpleTestCase):
    def test_a_small_jpx_page_image_is_not_refused_and_pdfium_draws_it(self):
        for codestream in (False, True):
            with self.subTest(codestream=codestream):
                pdf = _jpx_page(_jpx(300, 200, _jpx_bytes(300, 200, codestream)))
                self.assertIsNone(_refusal(pdf))
                cost = _cost(pdf)
                self.assertEqual((cost['max_image_px'], cost['max_image']), (60_000, 180_000))
                png = pdf_pages.pdf_first_page_png(pdf)
                self.assertTrue(png and png.startswith(b'\x89PNG'))
                r, g, b = _png_centre(png)                           # the red image, decoded by pdfium
                self.assertTrue(r > 150 and g < 80 and b < 80, (r, g, b))

    def test_a_jpx_in_a_form_on_the_page_is_charged_and_not_refused(self):
        form = _stream(b'<< /Type /XObject /Subtype /Form /BBox [0 0 1 1] /Resources << /XObject << /Im0 7 0 R '
                       b'>> >>', b'/Im0 Do')
        pdf = _a4(FULL_PAGE + b'/Fm0 Do', b'/XObject << /Fm0 6 0 R >>',
                  {6: form, 7: _jpx(300, 200, _jpx_bytes(300, 200))})
        self.assertIsNone(_refusal(pdf))
        self.assertEqual(_cost(pdf)['max_image_px'], 60_000)

    def test_a_header_claiming_more_than_the_dictionary_is_charged_the_header(self):
        """The dictionary says 100 x 100; the JPX data's SIZ marker says 20,000 x 20,000: past a budget."""
        for codestream in (False, True):
            with self.subTest(codestream=codestream):
                pdf = _jpx_page(_jpx(100, 100, _claiming(_jpx_bytes(40, 30, codestream), 20_000, 20_000)))
                self.assertTrue(_refusal(pdf).startswith('OverBudget'), _refusal(pdf))

    def test_a_jp2_ihdr_claiming_more_is_charged_too(self):
        data = bytearray(_jpx_bytes(40, 30))
        at = data.index(b'ihdr') + 4
        data[at:at + 8] = (20_000).to_bytes(4, 'big') * 2                # HEIGHT, WIDTH
        self.assertTrue(_refusal(_jpx_page(_jpx(40, 30, bytes(data)))).startswith('OverBudget'))

    def test_a_jpx_past_the_pixel_budget_is_refused(self):
        side = math.isqrt(pdf_render_check.MAX_IMAGE_PX) + 1
        for name, img, reason in (
                ('by its dictionary', _jpx(side, side, _jpx_bytes(40, 30)), 'an image past the render cap'),
                ('by its header, one component of 8 bits',
                 _jpx(40, 30, _claiming(_jpx_bytes(40, 30, True), side, side, comps=1), cs=b'/DeviceGray'),
                 'an image past the render pixel cap')):
            with self.subTest(name):
                self.assertEqual(_refusal(_jpx_page(img)), 'OverBudget: ' + reason)
        # many draws of a small one: the page's sums still bind
        k = pdf_render_check.MAX_PAGE_IMAGE_PX // 60_000 + 1
        self.assertTrue(_refusal(_jpx_page(_jpx(300, 200, _jpx_bytes(300, 200)), draws=k)).startswith('OverBudget'))

    def test_flate_before_jpx_reads_the_header_from_a_window(self):
        flate_jpx = b'[/FlateDecode /JPXDecode]'
        small = _jpx_page(_jpx(300, 200, zlib.compress(_jpx_bytes(300, 200)), flate_jpx))
        self.assertIsNone(_refusal(small))
        self.assertEqual(_cost(small)['max_image_px'], 60_000)
        bomb = _jpx(100, 100, zlib.compress(_claiming(_jpx_bytes(40, 30), 20_000, 20_000)), flate_jpx)
        self.assertTrue(_refusal(_jpx_page(bomb)).startswith('OverBudget'))

    def test_a_header_that_cannot_be_read_is_refused(self):
        """Fix 1: a 10 x 10 dictionary may hide a 9000 x 9000 codestream, so an unread header is refused (it was
        charged a 4096 x 4096 floor). Fix 2: a Flate with a predictor first is not read as the JPX data's start."""
        past_window = _jp2_after_a_free_box(70_000)
        hidden = _claiming(_jpx_bytes(40, 30, True), 9000, 9000)
        two_flates = zlib.compress(zlib.compress(hidden))
        for name, img in (('no JPX data', _jpx(10, 10, b'\x00' * 64)),
                          ('the codestream past the inflated window',
                           _jpx(10, 10, zlib.compress(past_window), b'[/FlateDecode /JPXDecode]')),
                          ('another filter first', _jpx(10, 10, b'z' * 8 + b'~>', b'[/ASCII85Decode /JPXDecode]')),
                          ('two Flates first', _jpx(10, 10, two_flates, b'[/FlateDecode /FlateDecode /JPXDecode]')),
                          ('a Flate with a predictor first',
                           _jpx(40, 30, zlib.compress(_jpx_bytes(40, 30, True)), b'[/FlateDecode /JPXDecode]',
                                b'/DecodeParms [<< /Predictor 12 /Columns 4 >> null]')),
                          ('a SIZ marker of no size', _jpx(10, 10, _claiming(_jpx_bytes(40, 30, True), 0, 0)))):
            with self.subTest(name):
                self.assertEqual(_refusal(_jpx_page(img)), 'Refused: a JPEG2000 image whose header was not read')

    def test_a_predictor_of_1_is_no_predictor(self):
        img = _jpx(40, 30, zlib.compress(_jpx_bytes(40, 30, True)), b'[/FlateDecode /JPXDecode]',
                   b'/DecodeParms << /Predictor 1 >>')
        self.assertIsNone(_refusal(_jpx_page(img)))

    def test_the_same_codestream_inside_the_window_is_read(self):
        """The twin of 'the codestream past the inflated window': with fewer boxes before it, it is read."""
        near = _jp2_after_a_free_box(1_000)
        pdf = _jpx_page(_jpx(10, 10, zlib.compress(near), b'[/FlateDecode /JPXDecode]'))
        self.assertEqual(_cost(pdf)['max_image_px'], 1200)

    def test_a_siz_marker_cut_off_inside_its_components_charges_the_deepest(self):
        head = _jpx_bytes(40, 30, True)
        self.assertEqual(pdf_jpx._siz(head, 0), (1200, 24))
        self.assertEqual(pdf_jpx._siz(head[:45], 0), (1200, 3 * 38))     # 2 of 3 components cut off

    def test_jpx_only_as_the_last_filter(self):
        pdf = _jpx_page(_jpx(40, 30, _jpx_bytes(40, 30), b'[/JPXDecode /FlateDecode]'))
        self.assertEqual(_refusal(pdf), "Refused: an image filter outside the whitelist ('/JPXDecode')")

    def test_other_unlisted_filters_on_the_page_are_still_refused(self):
        for name, img in (('LZW', _image(10, 10).replace(b'/FlateDecode', b'/LZWDecode')),
                          ('ASCIIHex', _image(10, 10).replace(b'/FlateDecode', b'/ASCIIHexDecode')),
                          ('JBIG2 after another filter', _jbig2(10, 10).replace(
                              b'/Filter /JBIG2Decode', b'/Filter [/FlateDecode /JBIG2Decode]'))):
            with self.subTest(name):
                pdf = _jpx_page(img)
                self.assertTrue(_refusal(pdf).startswith("Refused: an image filter outside the whitelist ('/"))
                self.assertIsNone(pdf_pages.pdf_first_page_png(pdf))

    def test_an_unlisted_filter_name_is_logged_safely(self):
        """Fix 3: the attacker's filter name (pypdf turns #0A into a newline) is quoted and cut short."""
        img = _image(10, 10).replace(b'/FlateDecode', b'/Foo#0Aforged#20line' + b'X' * 200)
        reason = _refusal(_jpx_page(img))
        self.assertNotIn('\n', reason)
        self.assertTrue(reason.startswith("Refused: an image filter outside the whitelist ('/Foo\\nforged line"))
        self.assertLess(len(reason), 100)

    def test_a_jpx_in_an_annotation_is_charged(self):
        stamp = {6: b'<< /Type /Annot /Subtype /Stamp /Rect [100 100 300 200] /AP << /N 7 0 R >> >>',
                 7: _stream(b'<< /Type /XObject /Subtype /Form /BBox [0 0 200 100] /Resources << /XObject << /Im0 '
                            b'8 0 R >> >>', b'q 200 0 0 100 0 0 cm /Im0 Do Q'),
                 8: _jpx(300, 200, _jpx_bytes(300, 200))}
        pdf = _annotated(_show(SPM_TEXT), b'6 0 R', stamp)
        self.assertIsNone(_refusal(pdf))
        self.assertEqual(_cost(pdf)['max_image_px'], 60_000)


def _jpx_levels(w, h, levels, codestream=True, mode='RGB'):
    """A real JPEG2000 file (Pillow / OpenJPEG) with ``levels`` decomposition levels (NL in its COD marker)."""
    from PIL import Image
    buf = io.BytesIO()
    Image.new(mode, (w, h), 200).save(buf, 'JPEG2000', num_resolutions=levels + 1, no_jp2=codestream)
    return buf.getvalue()


def _grey_page(side, levels, images=1, pages=1):
    """``pages`` pages, each drawing ``images`` grey JPX images whose dictionary says 1600 x 2260 over a
    codestream whose SIZ claims ``side`` x ``side`` (one component) with ``levels`` decomposition levels: the
    shape of the review 3 probe (it was three 4890 x 4890 16-bit grey images with NL = 0 on each of 3 pages)."""
    data = _claiming(_jpx_levels(64, 64, levels, mode='L'), side, side)
    objs = {6 + i: _jpx(1600, 2260, data, cs=b'/DeviceGray') for i in range(images)}
    names = b''.join(b'/Im%d %d 0 R ' % (i, 6 + i) for i in range(images))
    content = b''.join(b'q ' + FULL_PAGE + b'/Im%d Do Q ' % i for i in range(images))
    one = _a4(content, b'/XObject << ' + names + b'>>', objs)
    if pages == 1:
        return one
    from pypdf import PdfReader, PdfWriter
    out, writer = io.BytesIO(), PdfWriter()
    for _ in range(pages):
        writer.add_page(PdfReader(io.BytesIO(one)).pages[0])
    writer.write(out)
    return out.getvalue()


def _cod_in_tile_part(data):
    """``data`` (a bare codestream) with its main header's COD marker copied into its first tile-part header."""
    cod_at, sot_at = data.index(b'\xff\x52'), data.index(b'\xff\x90')
    cod = data[cod_at:cod_at + 2 + int.from_bytes(data[cod_at + 2:cod_at + 4], 'big')]
    psot = int.from_bytes(data[sot_at + 6:sot_at + 10], 'big') + len(cod)
    return data[:sot_at + 6] + psot.to_bytes(4, 'big') + data[sot_at + 10:sot_at + 12] + cod + data[sot_at + 12:]


# ── TD-692 review 3: pixels did not bound the decode time. With one resolution level (NL = 0) OpenJPEG decodes
#    every pixel at full size: three 4890 x 4890 16-bit grey images on each of 3 pages passed the pixel caps and
#    took 15-18 s of the child's 20 s. A JPX image is now charged its decode work too (SIZ pixels x components, half
#    only when NL >= 1 is proved), capped per page and over the pages of one gate call.
class ADecodeWork(SimpleTestCase):
    def test_the_review_probe_shape_is_refused(self):
        for name, pdf in (('3 pages of three 4890 x 4890 images', _grey_page(4890, 0, images=3, pages=3)),
                          ('one page of three', _grey_page(4890, 0, images=3)),
                          ('one 4890 x 4890 image', _grey_page(4890, 0))):
            with self.subTest(name):
                self.assertEqual(pdf_render_check.render_refusal(pdf, lambda n: range(n))[1],
                                 'OverBudget: past the render jpx_work cap')

    def test_one_large_image_is_refused_with_one_level_or_five(self):
        for side in (7000, 7500):
            for levels in (0, 5):
                with self.subTest(side=side, levels=levels):
                    self.assertEqual(_refusal(_grey_page(side, levels)), 'OverBudget: past the render jpx_work cap')

    def test_the_work_is_full_at_one_level_and_half_with_more(self):
        for codestream in (True, False):
            with self.subTest(codestream=codestream):
                for levels, work in ((0, 180_000), (1, 90_000), (5, 90_000)):
                    pdf = _jpx_page(_jpx(300, 200, _jpx_levels(300, 200, levels, codestream)))
                    self.assertEqual(_cost(pdf)['jpx_work'], work)

    def test_levels_that_cannot_be_proved_count_as_one(self):
        data = _jpx_levels(300, 200, 5)
        self.assertEqual(pdf_jpx._levels(data, 0, True), 5)
        self.assertEqual(pdf_jpx._levels(_cod_in_tile_part(data), 0, True), 0)      # a tile may override
        self.assertEqual(pdf_jpx._levels(data[:-40], 0, False), 0)                 # cut short in a window
        no_cod = data.replace(b'\xff\x52', b'\xff\x64', 1)                          # COD renamed a comment
        self.assertEqual(pdf_jpx._levels(no_cod, 0, True), 0)
        grey = _jpx_levels(300, 200, 5, mode='L')
        pdf = _jpx_page(_jpx(300, 200, _cod_in_tile_part(grey), cs=b'/DeviceGray'))
        self.assertEqual(_cost(pdf)['jpx_work'], 60_000)

    def test_the_page_cap_and_the_call_cap(self):
        at_cap = math.isqrt(pdf_jpx.MAX_PAGE_JPX_WORK)                             # 3162 x 3162, one component
        self.assertIsNone(_refusal(_grey_page(at_cap, 0)))
        self.assertEqual(_refusal(_grey_page(at_cap + 1, 0)), 'OverBudget: past the render jpx_work cap')
        pages = pdf_jpx.MAX_DOC_JPX_WORK // pdf_jpx.MAX_PAGE_JPX_WORK                # 3, the most a renderer asks
        pdf = _grey_page(at_cap, 0, pages=pages + 1)
        self.assertIsNone(pdf_render_check.render_refusal(pdf, lambda n: range(pages))[1])
        self.assertEqual(pdf_render_check.render_refusal(pdf, lambda n: range(n))[1],
                         'OverBudget: past the render JPEG2000 document cap')

    def test_a_real_looking_a4_colour_scan_with_levels_passes_and_is_drawn(self):
        """200 DPI A4 RGB (1654 x 2339) with 5 levels: work 5.8 million, three such pages pass."""
        pdf = _jpx_page(_jpx(1654, 2339, _jpx_levels(1654, 2339, 5, codestream=False)))
        self.assertIsNone(_refusal(pdf))
        self.assertEqual(_cost(pdf)['jpx_work'], (1654 * 2339 * 3 + 1) // 2)
        self.assertTrue(pdf_pages.pdf_first_page_png(pdf).startswith(b'\x89PNG'))


def _jbig2(w, h, extra=b'', data=b'\x00' * 64, mask=False):
    """A JBIG2 image XObject (the check reads its dictionary and lengths only)."""
    kind = b'/ImageMask true' if mask else b'/ColorSpace /DeviceGray'
    return _stream(b'<< /Type /XObject /Subtype /Image /Width %d /Height %d ' % (w, h) + kind
                   + b' /BitsPerComponent 1 /Filter /JBIG2Decode ' + extra, data)



# ── TD-697: JBIG2 is not allowed (a byte cap does not bound pdfium's JBIG2 decode time).
class AJbig2Image(SimpleTestCase):
    def test_a_jbig2_image_or_mask_is_refused(self):
        refused = "Refused: an image filter outside the whitelist ('/JBIG2Decode')"
        mask = _jpx(40, 30, _jpx_bytes(40, 30), extra=b'/Mask 7 0 R')
        for name, pdf in (('an image', _jpx_page(_jbig2(800, 600))),
                          ('a mask on a JPX image', _jpx_page(mask, objs={7: _jbig2(400, 300, mask=True)}))):
            with self.subTest(name):
                self.assertEqual(_refusal(pdf), refused)
                self.assertIsNone(pdf_pages.pdf_first_page_png(pdf))

    def test_an_unlisted_filter_drawn_10000_times_is_refused_fast(self):
        self.assertTrue(_refusal(_jpx_page(_image(10, 10).replace(b'/FlateDecode', b'/LZWDecode'), draws=10_000))
                        .startswith("Refused: an image filter outside the whitelist ('/LZWDecode')"))


def _font_page(program):
    """A page whose TrueType font /F2 has the font program ``program`` (object 8)."""
    return _a4(b'BT /F2 12 Tf 20 100 Td (AB) Tj ET ' + _show(SPM_TEXT), b'/Font << /F1 3 0 R /F2 6 0 R >>', {
        6: b'<< /Type /Font /Subtype /TrueType /BaseFont /X /FirstChar 65 /LastChar 66 /Widths [500 500] '
           b'/FontDescriptor 7 0 R >>',
        7: b'<< /Type /FontDescriptor /FontName /X /Flags 32 /FontBBox [0 0 1 1] /ItalicAngle 0 /Ascent 1 '
           b'/Descent 0 /CapHeight 1 /StemV 1 /FontFile2 8 0 R >>',
        8: program})


def _hex_form(content, filters=b'/ASCIIHexDecode'):
    form = _stream(b'<< /Type /XObject /Subtype /Form /BBox [0 0 1 1] /Filter ' + filters, content)
    return _a4(FULL_PAGE + b'/Fm0 Do', b'/XObject << /Fm0 6 0 R >>', {6: form})


# ── TD-692: an ASCIIHex stream is decoded by the pre-filter (linear, at most half its input), in content streams
#    and in the pdfium load check, so the walk keeps charging what pdfium will decode.
class AnAsciiHexStream(SimpleTestCase):
    def test_the_decoder(self):
        self.assertEqual(ascii_hex(b'48 65\n6C\t6c 6>', 100), b'Hell`')
        self.assertEqual(ascii_hex(b'414243>junk', 100), b'ABC')
        self.assertEqual(len(ascii_hex(b'00' * 1_000_000, 10)), 11)     # never more than the cap + 1
        with self.assertRaises(ValueError):
            ascii_hex(b'4g>', 100)

    def test_an_asciihex_font_program_is_loaded_and_charged(self):
        self.assertIsNone(_refusal(_font_page(_stream(b'<< /Filter /ASCIIHexDecode', b'00 01 02>'))))
        big = _stream(b'<< /Filter /ASCIIHexDecode', b'00' * (pdf_pdfium_load.MAX_LOAD_STREAM + 1) + b'>')
        self.assertEqual(_refusal(_font_page(big)), 'OverBudget: a stream past the pdfium load budget')

    def test_asciihex_over_flate_bombs_in_a_font_are_still_refused_fast(self):
        bomb = zlib.compress(b'\x00' * 50_000_000)
        for name, filters, data in (('over a Flate bomb', b'[/ASCIIHexDecode /FlateDecode]', bomb.hex().encode()),
                                    ('nested', b'[/ASCIIHexDecode /ASCIIHexDecode /FlateDecode]',
                                     bomb.hex().encode().hex().encode())):
            with self.subTest(name):
                reason = _refusal(_font_page(_stream(b'<< /Filter ' + filters, data + b'>')))
                self.assertEqual(reason, 'ValueError: a stream filter outside the whitelist')

    def test_an_asciihex_content_stream_is_decoded_and_charged(self):
        self.assertIsNone(_refusal(_hex_form(b'0 0 1 1 re f'.hex().encode() + b'>')))
        over = b'20' * (pdf_render_check._MAX_CONTENT_BYTES + 1) + b'>'
        self.assertTrue(_refusal(_hex_form(over)).startswith('OverBudget'))
