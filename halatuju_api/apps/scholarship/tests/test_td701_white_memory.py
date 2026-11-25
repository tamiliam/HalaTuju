"""TD-701: the white check's transparency path pastes in greyscale (one 'L' page + 'L' mask), not four
full-size RGBA copies; HEIF is no longer opened. Verdicts are unchanged. Synthetic images only."""
import io
import tracemalloc

from django.test import SimpleTestCase


def _png(im, **kw):
    buf = io.BytesIO()
    im.save(buf, format='PNG', **kw)
    return buf.getvalue()


def _old_white(img: bytes) -> bool:
    """The pre-TD-701 transparency path, kept here only to measure against."""
    from PIL import Image
    from apps.scholarship.income_declaration import PAGE_INK_LEVEL, WHITE_PAGE_INK_SHARE
    with Image.open(io.BytesIO(img)) as im:
        rgba = im.convert('RGBA')
        page = Image.new('RGBA', rgba.size, (255, 255, 255, 255))
        page.alpha_composite(rgba)
        grey = page.convert('L')
    counts = grey.histogram()
    return sum(counts[:PAGE_INK_LEVEL]) < WHITE_PAGE_INK_SHARE * max(1, grey.width * grey.height)


class TransparencyVerdictsAreUnchanged(SimpleTestCase):

    def _cases(self):
        from PIL import Image, ImageDraw
        out = {}
        for mode, blank, ink in (('RGBA', (255, 255, 255, 255), (20, 20, 20, 255)),
                                 ('LA', (255, 255), (20, 255))):
            for inked in (False, True):
                im = Image.new(mode, (600, 800), blank)
                if inked:
                    ImageDraw.Draw(im).rectangle([50, 50, 550, 300], fill=ink)
                out[(mode, inked)] = _png(im)
        # fully transparent (black underneath) is a white page; a transparent hole in black is not ink
        out[('RGBA-clear', False)] = _png(Image.new('RGBA', (600, 800), (0, 0, 0, 0)))
        # P with transparency
        for inked in (False, True):
            p = Image.new('P', (600, 800), 0)
            p.putpalette([255, 255, 255, 10, 10, 10] + [0] * 250)
            if inked:
                ImageDraw.Draw(p).rectangle([50, 50, 550, 300], fill=1)
            out[('P-transp', inked)] = _png(p, transparency=5)   # index 5 unused: transparency present
        # opaque control
        for inked in (False, True):
            im = Image.new('RGB', (600, 800), 'white')
            if inked:
                ImageDraw.Draw(im).rectangle([50, 50, 550, 300], fill=(20, 20, 20))
            out[('RGB', inked)] = _png(im)
        return out

    def test_verdicts_match_the_expected_and_the_old_path(self):
        from apps.scholarship.income_declaration import approval_page_white
        for (name, inked), data in self._cases().items():
            with self.subTest(name=name, inked=inked):
                expected = not inked
                self.assertEqual(approval_page_white(data), expected)
                self.assertEqual(_old_white(data), expected)

    def test_a_transparent_page_over_white_is_white_and_opaque_ink_is_not(self):
        from PIL import Image
        from apps.scholarship.income_declaration import approval_page_white
        half = Image.new('RGBA', (600, 800), (0, 0, 0, 0))
        half.paste((0, 0, 0, 255), [0, 0, 600, 400])
        self.assertFalse(approval_page_white(_png(half)))


class TheWhiteCheckStaysSmall(SimpleTestCase):

    def test_heif_is_not_a_white_check_format(self):
        from apps.scholarship.income_declaration import WHITE_CHECK_FORMATS
        self.assertNotIn('HEIF', WHITE_CHECK_FORMATS)
        self.assertNotIn('HEIC', WHITE_CHECK_FORMATS)

    def test_the_pixel_buffers_built_are_far_fewer_than_the_old_path(self):
        """PIL allocates outside tracemalloc, so count the bytes of every image the check builds (new, convert,
        getchannel, copy) with those calls wrapped; 9 MP RGBA in, the old path built 2 RGBA + 1 L copies."""
        from unittest import mock
        from PIL import Image
        from apps.scholarship.income_declaration import approval_page_white
        data = _png(Image.new('RGBA', (3000, 3000), (255, 255, 255, 255)))
        total = [0]

        def counted(real):
            def wrap(*a, **k):
                out = real(*a, **k)
                if isinstance(out, Image.Image):
                    total[0] += out.width * out.height * len(out.getbands())
                return out
            return wrap

        def built(fn):
            total[0] = 0
            with mock.patch.object(Image, 'new', counted(Image.new)),                     mock.patch.object(Image.Image, 'convert', counted(Image.Image.convert)),                     mock.patch.object(Image.Image, 'getchannel', counted(Image.Image.getchannel)):
                fn(data)
            return total[0]
        new, old = built(approval_page_white), built(_old_white)
        print(f'TD-701 buffer bytes built: old={old} new={new}')
        self.assertLess(new, old * 0.5)
        self.assertLessEqual(new, 3 * 3000 * 3000)   # at most three single-byte planes
