"""S-visible fix round 7 (2026-11-19): what a pdfium RENDER of a page costs, judged BEFORE pdfium renders it.

Every pdfium use holds `pdfium_lock.PDFIUM_LOCK` (pypdfium2 is not thread-safe), so a slow render stalls every
upload in that gunicorn worker, not one thread: a page drawing a 20,000 x 20,000 image took 323 s, a 60 MB tiling
cell 21.6 s, 20,000 full-page fills 32 s, 2,000 full-page draws of a small image 16 s. Before any page is rendered
(`pdf_pages`: the Vision route's page 1, the offer reader's pages, the stacked declaration pages) its content is
walked here WITHOUT pdfium and charged; a page outside the whitelist or past a cap is refused (the renderer
returns None: the upload's existing "cannot read" path). The caps are the 533 real corpus PDFs' maxima with
headroom (measured 2026-11-19, `docs/decisions.md`). pdfium also LOADS the page first: `pdf_pdfium_load`'s
check runs here too.

Charged per page, forms' contents on every call: operations; painted device pixels (the bounding box of each
fill, stroke, image, shading and form group, clipped to the page, at the render scale; a paint under a soft mask
also pays the mask's own paint); decoded image bytes on EVERY draw (pdfium resamples the whole source each time);
tiling cells (their pixels and the number of tiles); Type 3 glyphs on every glyph shown. Inline images, image
filters, shadings and Type 3 glyph operations outside the corpus's, and an image or cell past its own cap, are
refused. Content is read by this module's own tokenizer, so the verdict does not depend on the pypdf version.
"""
import math
import re
import zlib

from pypdf.generic import StreamObject

from .pdf_layer_guards import OverBudget, _get

# ── Caps: about 2x the corpus maximum. Each "corpus" figure is the real maximum over the 533 PDFs' pages 1-3 and
#    last (778 pages), measured 2026-11-19 on pypdf 5.9.0 and 6.21.4 alike.
#: One image, decoded (width x height x components x bits / 8). corpus: 107,298,900 (a phone photo).
MAX_IMAGE_BYTES = 215_000_000
#: Decoded image bytes summed over every image DRAW on one page. corpus: 107,298,900.
MAX_PAGE_IMAGE_BYTES = 215_000_000
#: The same in pixels, one image and summed over a page's draws (a 1-bit scan is small in bytes, not in
#: pixels). corpus: 35,766,300 (the same phone photo).
MAX_IMAGE_PX = 72_000_000
MAX_PAGE_IMAGE_PX = 72_000_000
#: Device pixels painted on one page (an A4 page at 200 DPI is 3.87 million). corpus: 66,684,674.
MAX_PAGE_PAINT_PX = 135_000_000
#: Content operations walked on one page, a form's on each call. corpus: 52,913.
MAX_PAGE_OPS = 110_000
#: Content tokens (operands + operators) read on one page. corpus: 257,493.
MAX_PAGE_TOKENS = 520_000
#: Type 3 glyph operations on one page: each glyph shown x the most operations in one glyph of its font.
#: corpus: 198,009.
MAX_PAGE_GLYPH_OPS = 400_000
#: Objects painted under a blend mode other than Normal on one page (corpus: 0; pdfium's cost grows with the
#: square: 16 full-page fills took 4.7 s, 32 took 20 s).
MAX_BLEND_PAINTS = 8
#: One tiling cell in device pixels (corpus: 3,866,977), and the tiles one page draws (corpus: 1; the cap
#: leaves room for a real background pattern, still well under a second of rendering).
MAX_CELL_PX = 8_000_000
MAX_TILES = 1_000
#: Image filters the corpus uses. Anything else (JBIG2, JPX, LZW, ...): refused.
IMAGE_FILTERS = frozenset(('/DCTDecode', '/FlateDecode', '/CCITTFaxDecode', '/RunLengthDecode', '/ASCII85Decode'))
#: Shadings (shading type: function types) the corpus uses: axial, exponential or stitched exponential.
SHADINGS = frozenset(('2:2', '2:3[2,2,2]'))
#: A Type 3 font's glyph procedures (corpus: at most 68 in a font, 9,040 bytes and 189 operations in one,
#: a path only).
MAX_TYPE3_GLYPHS = 256
MAX_GLYPH_BYTES = 20_000
#: The round 6 load whitelist (pdf_pdfium_load.GLYPH_OPS) without q Q cm, so a glyph box is its path box.
_GLYPH_OPS = frozenset(b'd0 d1 m l c v y h re f* f n W* W'.split())
_COMPONENTS = {'/DeviceGray': 1, '/CalGray': 1, '/Indexed': 1, '/Separation': 1, '/DeviceRGB': 3, '/CalRGB': 3,
               '/Lab': 3, '/DeviceCMYK': 4}
_PAINT = frozenset((b'f', b'F', b'f*', b'B', b'B*', b'b', b'b*', b'S', b's'))
_STROKE = frozenset((b'B', b'B*', b'b', b'b*', b'S', b's'))
_MAX_DEPTH = 8
_MAX_CONTENT_BYTES = 8_000_000


class Refused(ValueError):
    """The page's render is refused (outside the whitelist or past a cap)."""


def render_refusal(data: bytes, pick) -> tuple:
    """(pypdf's page count, None) when every page index ``pick(count)`` names may be rendered; (count, reason)
    when one may not. Never raises: an unreadable PDF is refused (``(0, reason)``)."""
    from .pdf_pages import _open_pdf
    from .pdf_pdfium_load import load_check
    try:
        reader = _open_pdf(data)
        n, load_state = len(reader.pages), {}
        for i in pick(n):
            if 0 <= i < n:
                load_check(reader.pages[i], reader, load_state)
                page_cost(reader.pages[i], reader)
        return n, None
    except Exception as e:  # anything the check cannot follow is refused, never rendered
        return 0, f'{type(e).__name__}: {e}'[:200]


def page_cost(page, reader, limits: bool = True) -> dict:
    """Walk one page and return what its render costs; raise `Refused` / `OverBudget` past a cap."""
    from .pdf_pages import _resources, raster_scale
    box = [float(v) for v in page.cropbox]
    x0, y0, x1, y1 = min(box[0], box[2]), min(box[1], box[3]), max(box[0], box[2]), max(box[1], box[3])
    scale = raster_scale(x1 - x0, y1 - y0)
    if scale is None:
        raise Refused('a page box outside the render bounds')
    cost = _Cost((x0, y0, x1, y1), scale, limits)
    contents = page.get('/Contents')
    contents = contents.get_object() if contents is not None else None
    streams = [c.get_object() for c in contents] if isinstance(contents, list) else [contents] if contents else []
    cost.walk(b'\n'.join(_content_bytes(s, cost) for s in streams), _resources(page), reader, (1, 0, 0, 1, 0, 0), 0)
    return cost.stats


def _content_bytes(stream, cost) -> bytes:
    """A content stream decoded, charged to the page's content budget (Flate, none, or ASCII85 then Flate)."""
    from .pdf_pdfium_load import _inflated
    if not isinstance(stream, StreamObject):
        raise Refused('a content stream that is not a stream')
    filters = _get(stream, '/Filter')
    if isinstance(filters, list) and [str(f) for f in filters] == ['/ASCII85Decode', '/FlateDecode']:
        from pypdf.filters import ASCII85Decode
        data = zlib.decompressobj().decompress(ASCII85Decode.decode(stream._data), cost.content_left + 1)
        if len(data) > cost.content_left:
            raise OverBudget('content past the render budget')
    else:
        data = _inflated(stream, cost.content_left)
    cost.content_left -= len(data)
    return data


def _mul(a, b):
    """The matrix product a x b (PDF order: a applied first)."""
    return (a[0] * b[0] + a[1] * b[2], a[0] * b[1] + a[1] * b[3], a[2] * b[0] + a[3] * b[2],
            a[2] * b[1] + a[3] * b[3], a[4] * b[0] + a[5] * b[2] + b[4], a[4] * b[1] + a[5] * b[3] + b[5])


def _det(m) -> float:
    return m[0] * m[3] - m[1] * m[2]


def _ctm_point(m, x, y):
    return m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]


#: One content token: white space, a comment, a dictionary bracket, a hex string, an array bracket, a name, a
#: literal string's start (skipped by `_LITERAL`), or a regular token (a number or an operator).
_WS = b'\x00\t\n\x0c\r '
_TOKEN = re.compile(rb'[' + _WS + rb']+|%[^\r\n]*|<<|>>|<[^<>]*>|[\[\]{}]|/[^' + _WS + rb'()<>\[\]{}/%]*|\(|'
                    rb'[^' + _WS + rb'()<>\[\]{}/%]+|[)>]')
_LITERAL = re.compile(rb'\\.|[()]', re.S)
_NUMBER = re.compile(rb'[+-]?(?:\d+\.?\d*|\.\d+)')
_HEX_ESCAPE = re.compile(rb'#([0-9A-Fa-f]{2})')


def _operations(data: bytes, cost):
    """(operands, operator, string bytes) of a content stream, read by OUR tokenizer, not pypdf's parser
    (pypdf 5.9 fails on strings pdfium renders fine; the cost must not depend on the pypdf version). Operands
    keep numbers and names (#xx decoded, as pdfium does); strings, arrays and dictionaries are placeholders.
    Every token and operation is charged to the page."""
    operands, nest, i, n, text = [], 0, 0, len(data), 0
    while i < n:
        m = _TOKEN.match(data, i)
        if m is None:
            raise Refused('content the check cannot read')
        tok, i = m.group(), m.end()
        first = tok[:1]
        if first in _WS + b'%':
            continue
        cost.add('tokens', 1, MAX_PAGE_TOKENS)
        if tok == b'(':
            depth = 1
            for lit in _LITERAL.finditer(data, i):
                depth += {b'(': 1, b')': -1}.get(lit.group(), 0)
                if depth == 0:
                    text, i = text + lit.start() - i, lit.end()
                    break
            else:
                raise Refused('an unterminated string')
            if not nest:
                operands.append(None)
        elif tok in (b'[', b'<<', b'{'):
            nest += 1
        elif tok in (b']', b'>>', b'}'):
            nest = max(nest - 1, 0)
            if not nest:
                operands.append(None)
        elif nest and first == b'<':
            text += (len(tok) - 2) // 2
        elif nest:
            continue
        elif first == b'<':
            text += (len(tok) - 2) // 2
            operands.append(None)
        elif first == b'/':
            operands.append(_pdf_name(tok))
        elif _NUMBER.fullmatch(tok):
            operands.append(float(tok))
        else:
            cost.add('ops', 1, MAX_PAGE_OPS)
            yield operands, tok, text
            operands, text = [], 0


def _pdf_name(tok: bytes) -> str:
    raw = _HEX_ESCAPE.sub(lambda m: bytes((int(m.group(1), 16),)), tok)
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        return raw.decode('latin-1')


def _named(res, category, name):
    """The resource ``name`` of ``category``; a name the page does not define is refused (never skipped
    uncharged: pdfium might resolve it another way)."""
    entries = _get(res, category)
    obj = _get(entries, name) if isinstance(name, str) else None
    if obj is None:
        raise Refused(f'a {category[1:]} name the check cannot resolve')
    return obj


def _function_tag(fn, depth) -> str:
    """A shading function's type, with a stitching function's parts: '3[2,2,2]'."""
    parts = _get(fn, '/Functions') if depth < 3 else None
    tag = str(_get(fn, '/FunctionType'))
    return tag + '[' + ','.join(_function_tag(f.get_object(), depth + 1) for f in parts) + ']' if parts else tag


def _numbers(operands, n):
    if len(operands) != n or not all(isinstance(v, (int, float)) for v in operands):
        raise Refused('operands the check cannot read')
    vals = [float(v) for v in operands]
    if not all(math.isfinite(v) and abs(v) < 1e9 for v in vals):
        raise Refused('a number out of range')
    return vals


class _Cost:
    def __init__(self, page_box, scale, limits):
        self.box, self.scale, self.limits = page_box, scale, limits
        self.content_left = _MAX_CONTENT_BYTES
        self.fonts, self.blend = {}, False
        self.page_px = (page_box[2] - page_box[0]) * (page_box[3] - page_box[1]) * scale * scale
        self.stats = dict.fromkeys(('tokens', 'ops', 'paint_px', 'image_bytes', 'max_image', 'image_px', 'max_image_px',
                                    'cell_px', 'tiles', 'type3', 'glyph_ops', 'glyph_work', 'blend_paints', 'smasks',
                                    'patterns', 'groups'), 0)
        self.stats.update(filters=set(), shadings=set())

    def add(self, key, n, cap):
        self.stats[key] += n
        if self.limits and self.stats[key] > cap:
            raise OverBudget(f'past the render {key} cap')

    def area_px(self, points, ctm, pad=0.0) -> float:
        """Device pixels of the bounding box of ``points`` (user space) under ``ctm``, padded, on the page."""
        pts = [_ctm_point(ctm, x, y) for x, y in points]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        w = min(max(xs) + pad, self.box[2]) - max(min(xs) - pad, self.box[0])
        h = min(max(ys) + pad, self.box[3]) - max(min(ys) - pad, self.box[1])
        return max(w, 0.0) * max(h, 0.0) * self.scale * self.scale

    def paint(self, px, extra, objects=1):
        self.add('paint_px', px + extra, MAX_PAGE_PAINT_PX)
        if self.blend:                                  # pdfium composes each blended object with all before it
            self.add('blend_paints', objects, MAX_BLEND_PAINTS)

    def walk(self, data, resources, reader, ctm, depth, base=None):
        """Charge one content stream's operations (``data``, decoded) drawn under ``ctm``."""
        if depth > _MAX_DEPTH:
            raise Refused('content nested too deep')
        res = resources if isinstance(resources, dict) else {}
        base = ctm if base is None else base             # patterns map to the stream's own starting space
        stack, path, lw, mask, pattern = [], [], 1.0, 0.0, [None, None]
        t3, size, th, tm = None, 1.0, 1.0, (1, 0, 0, 1, 0, 0)
        for operands, op, text in _operations(data, self):
            if op == b'q':
                stack.append((ctm, lw, mask, list(pattern), t3, size, th, self.blend))
            elif op == b'Q':
                ctm, lw, mask, pattern, t3, size, th, self.blend = (
                    stack.pop() if stack else (ctm, lw, mask, pattern, t3, size, th, self.blend))
            elif op == b'BT':
                tm = (1, 0, 0, 1, 0, 0)
            elif op == b'Tm':
                tm = _numbers(operands, 6)
            elif op == b'Tz':
                th = abs(_numbers(operands, 1)[0]) / 100
            elif op == b'Tf':
                size = abs(_numbers(operands[1:], 1)[0])
                t3 = self.font(_get(_get(res, '/Font'), operands[0]) if isinstance(operands[0], str) else None)
            elif op in (b'Tj', b'TJ', b"'", b'"') and self.blend and t3 is None:
                self.paint(0, 0)
            elif op in (b'Tj', b'TJ', b"'", b'"') and t3 is not None and text:
                glyph = abs(_det(_mul(tm, ctm))) * size * size * th * t3[1] * self.scale * self.scale
                self.add('glyph_work', text * t3[0], MAX_PAGE_GLYPH_OPS)
                self.paint(text * min(glyph, self.page_px), text * mask, text)
            elif op == b'cm':
                ctm = _mul(_numbers(operands, 6), ctm)
            elif op == b'w':
                lw = abs(_numbers(operands, 1)[0])
            elif op in (b'm', b'l', b'c', b'v', b'y'):
                vals = _numbers(operands, len(operands))
                path.extend(zip(vals[::2], vals[1::2]))
            elif op == b're':
                x, y, w, h = _numbers(operands, 4)
                path.extend(((x, y), (x + w, y + h)))
            elif op in _PAINT or op == b'n':
                if op != b'n' and path:
                    pad = lw * math.sqrt(abs(ctm[0] * ctm[3] - ctm[1] * ctm[2])) if op in _STROKE else 0.0
                    px = self.area_px(path, ctm, pad)
                    self.paint(px, mask)
                    for p in pattern if op in _STROKE else pattern[:1]:
                        if p is not None:
                            self.add('tiles', px / p, MAX_TILES)
                path = []
            elif op in (b'scn', b'SCN'):
                if operands and isinstance(operands[-1], str):
                    pattern[op == b'SCN'] = self.pattern(_named(res, '/Pattern', operands[-1]), reader, base, depth)
            elif op in (b'sc', b'SC', b'g', b'G', b'rg', b'RG', b'k', b'K', b'cs', b'CS'):
                pattern[op in (b'SC', b'G', b'RG', b'K', b'CS')] = None
            elif op == b'sh':
                self.shading(_named(res, '/Shading', operands[-1] if operands else None))
                self.paint(self.area_px(((self.box[0], self.box[1]), (self.box[2], self.box[3])),
                                        (1, 0, 0, 1, 0, 0)), mask)
            elif op == b'gs':
                mask = self.gstate(_named(res, '/ExtGState', operands[-1] if operands else None), reader, ctm,
                                   depth, mask)
            elif op == b'Do':
                self.xobject(_named(res, '/XObject', operands[-1] if operands else None), reader, ctm, depth,
                             mask, res)
            elif op in (b'BI', b'ID', b'EI'):
                raise Refused('an inline image')

    def gstate(self, gs, reader, ctm, depth, mask):
        bm = _get(gs, '/BM') if isinstance(gs, dict) else None
        bm = bm[0].get_object() if isinstance(bm, list) and bm else bm
        if bm is not None:
            self.blend = bm not in ('/Normal', '/Compatible')
        smask = _get(gs, '/SMask') if isinstance(gs, dict) else None
        if smask is None:
            return mask
        if not isinstance(smask, dict):
            return 0.0                                  # /None switches the mask off
        group = _get(smask, '/G')
        before = self.stats['paint_px']
        self.stats['smasks'] += 1
        self.form(group, reader, ctm, depth + 1, 0.0)
        # every later paint under this mask renders the mask again, plus one compose of the page
        return self.stats['paint_px'] - before + self.area_px(((self.box[0], self.box[1]),
                                                               (self.box[2], self.box[3])), (1, 0, 0, 1, 0, 0))

    def xobject(self, xobj, reader, ctm, depth, mask, res):
        if not isinstance(xobj, StreamObject):
            return
        kind = _get(xobj, '/Subtype')
        if kind == '/Image':
            self.image(xobj, res)
            self.paint(self.area_px(((0, 0), (1, 0), (0, 1), (1, 1)), ctm), mask)
        elif kind == '/Form':
            self.form(xobj, reader, ctm, depth + 1, mask)

    def form(self, form, reader, ctm, depth, mask):
        if not isinstance(form, StreamObject) or _get(form, '/Subtype') != '/Form':
            raise Refused('a soft mask or form the check cannot follow')
        matrix = _get(form, '/Matrix')
        m = _numbers(list(matrix), 6) if matrix is not None else (1, 0, 0, 1, 0, 0)
        ctm = _mul(m, ctm)
        bbox = _numbers(list(_get(form, '/BBox') or ()), 4)
        if _get(form, '/Group') is not None:            # a transparency group: one off-screen bitmap, composed
            self.stats['groups'] += 1
            self.paint(self.area_px(((bbox[0], bbox[1]), (bbox[2], bbox[3]), (bbox[0], bbox[3]),
                                     (bbox[2], bbox[1])), ctm), mask)
        self.walk(_content_bytes(form, self), _get(form, '/Resources'), reader, ctm, depth)

    def pattern(self, pat, reader, base, depth):
        """A tiling pattern's cell is charged (pixels, and its content once); returns one tile's device pixels,
        so a paint with it counts its tiles. A shading pattern returns None (its area is charged as a paint)."""
        if not isinstance(pat, dict) or _get(pat, '/PatternType') not in (1, 2):
            raise Refused('a pattern outside the whitelist')
        if _get(pat, '/PatternType') == 2:
            self.shading(_get(pat, '/Shading'))
            return None
        matrix = _get(pat, '/Matrix')
        m = _mul(_numbers(list(matrix), 6) if matrix is not None else (1, 0, 0, 1, 0, 0), base)
        det = abs(m[0] * m[3] - m[1] * m[2]) * self.scale * self.scale
        bbox = _numbers(list(_get(pat, '/BBox') or ()), 4)
        xstep, ystep = (abs(_numbers([_get(pat, k)], 1)[0]) for k in ('/XStep', '/YStep'))
        cell = abs(bbox[2] - bbox[0]) * abs(bbox[3] - bbox[1]) * det
        self.stats['patterns'] += 1
        self.stats['cell_px'] = max(self.stats['cell_px'], cell)
        if self.limits and cell > MAX_CELL_PX:
            raise OverBudget('a tiling cell past the render cap')
        step = xstep * ystep * det
        if step <= 0:
            raise Refused('a tiling step of zero')
        if not isinstance(pat, StreamObject):
            raise Refused('a tiling pattern that is not a stream')
        self.walk(_content_bytes(pat, self), _get(pat, '/Resources'), reader, m, depth + 1, m)
        return step

    def font(self, font):
        """A Type 3 font's glyphs are content streams pdfium runs for EVERY glyph shown: each may only draw a
        path (as the corpus's do). Returns (most operations in one glyph, the largest glyph's area in text
        space) so each shown glyph is charged; any other font: None (its glyphs are cheap)."""
        if _get(font, '/Subtype') != '/Type3':
            return None
        if id(font) in self.fonts:
            return self.fonts[id(font)]
        self.stats['type3'] += 1
        procs = _get(font, '/CharProcs')
        if not isinstance(procs, dict) or len(procs) > MAX_TYPE3_GLYPHS:
            raise Refused('a Type 3 font the check cannot follow')
        most, area = 0, 0.0
        for proc in procs.values():
            data = _content_bytes(proc.get_object(), self)
            if len(data) > MAX_GLYPH_BYTES:
                raise OverBudget('a Type 3 glyph past the render cap')
            ops, pts = 0, []
            for operands, op, _ in _operations(data, self):
                if op not in _GLYPH_OPS:
                    raise Refused('a Type 3 glyph outside the whitelist')
                ops += 1
                vals = _numbers(operands, len(operands))
                if op == b're' and len(vals) == 4:
                    vals = [vals[0], vals[1], vals[0] + vals[2], vals[1] + vals[3]]
                elif op == b'd1':
                    vals = vals[2:]
                elif op == b'd0':
                    vals = []
                pts.extend(zip(vals[::2], vals[1::2]))
            if pts:
                xs, ys = [p[0] for p in pts], [p[1] for p in pts]
                area = max(area, (max(xs) - min(xs)) * (max(ys) - min(ys)))
            most = max(most, ops)
        self.stats['glyph_ops'] = max(self.stats['glyph_ops'], most)
        self.fonts[id(font)] = (most, area * abs(_det(_numbers(list(_get(font, '/FontMatrix') or ()), 6))))
        return self.fonts[id(font)]

    def shading(self, sh):
        """A shading's type and function types must be ones the corpus uses."""
        kind = _get(sh, '/ShadingType')
        funcs = _get(sh, '/Function')
        funcs = [f.get_object() for f in funcs] if isinstance(funcs, list) else [funcs] if funcs is not None else []
        tag = f'{kind}:' + ','.join(_function_tag(f, 0) for f in funcs)
        self.stats['shadings'].add(tag)
        if self.limits and tag not in SHADINGS:
            raise Refused('a shading outside the whitelist')

    def image(self, img, res):
        filters = _get(img, '/Filter')
        filters = list(filters) if isinstance(filters, list) else [filters] if filters is not None else []
        for f in filters:
            f = f.get_object() if hasattr(f, 'get_object') else f
            self.stats['filters'].add(str(f))
            if f not in IMAGE_FILTERS:
                raise Refused('an image filter outside the whitelist')
        w, h = _get(img, '/Width'), _get(img, '/Height')
        if not (isinstance(w, int) and isinstance(h, int) and w > 0 and h > 0):
            raise Refused('an image without a size')
        if _get(img, '/ImageMask'):
            bits = 1
        else:
            bpc = _get(img, '/BitsPerComponent')
            bpc = bpc if isinstance(bpc, int) and 0 < bpc <= 16 else 8
            bits = bpc * self.components(_get(img, '/ColorSpace'), res)
        size = math.ceil(w * h * bits / 8)
        self.stats['max_image'] = max(self.stats['max_image'], size)
        if self.limits and size > MAX_IMAGE_BYTES:
            raise OverBudget('an image past the render cap')
        self.add('image_bytes', size, MAX_PAGE_IMAGE_BYTES)
        # pdfium expands every pixel (a 1-bit scan too), so pixels are charged as well as bytes
        self.stats['max_image_px'] = max(self.stats['max_image_px'], w * h)
        if self.limits and w * h > MAX_IMAGE_PX:
            raise OverBudget('an image past the render pixel cap')
        self.add('image_px', w * h, MAX_PAGE_IMAGE_PX)
        for key in ('/SMask', '/Mask'):
            sub = _get(img, key)
            if isinstance(sub, StreamObject):
                self.image(sub, res)

    def components(self, cs, res, depth=0) -> int:
        if isinstance(cs, str) and cs not in _COMPONENTS:
            cs = _get(_get(res, '/ColorSpace'), cs) if depth < 2 else None
            return self.components(cs, res, depth + 1) if cs is not None else 4
        if isinstance(cs, str):
            return _COMPONENTS[cs]
        family = cs[0].get_object() if isinstance(cs, list) and cs else None
        if family == '/ICCBased':
            n = _get(cs[1].get_object(), '/N') if len(cs) > 1 else None
            return n if isinstance(n, int) and 0 < n <= 4 else 4
        if family == '/DeviceN':
            names = cs[1].get_object() if len(cs) > 1 else None
            return min(len(names), 32) if isinstance(names, list) else 32
        return _COMPONENTS.get(family, 4)
