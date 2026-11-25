"""The ONLY place the api runs pdfium (pypdfium2) on an upload: a short-lived CHILD process (S-visible fix round 8).

Run as ``python -I <this file>`` by `pdfium_run` — never imported with pdfium by the web process. It reads one
request from stdin (a JSON line, then the PDF's bytes), opens the PDF ONCE, runs each requested operation in order
and writes the answers to stdout (a JSON line, then the PNG bytes it names). Operations: ``count`` (pages),
``paints`` (pdf_pdfium_check's per-object painted-text check), ``render`` (each page its own PNG), ``stack`` (pages
stacked into one PNG), ``words`` (page 1's word boxes for the SPM certificate reader), ``layout`` (page 1's pypdf
layout text for the UMS offer reader), ``ink`` (each page-1 character's own ink on the rendered page, S-visible 2:
`pdf_ink`).

Why a child: rounds 5-7 modelled what pdfium costs (load whitelists, render caps) and ran it under one process-wide
lock, and every review still found a tiny crafted PDF that kept pdfium busy for 10-40 s — freezing every upload in
the gunicorn worker. Here a slow or crashing pdfium is killed at its time limit (`pdfium_run`: at most `TIMEOUT_S`
and the document's budget left) and its memory and CPU time are capped (Linux), so the worst case is one upload
getting the safe answer. The module's top level imports only the standard
library: the web process imports it for `raster_scale` alone.
"""
import ctypes
import functools
import io
import json
import sys

try:                                           # imported as part of the app (the web process, the tests)
    from . import pdfium_ink_own as _own, pdfium_place as _pl, pdfium_type3 as _t3
except ImportError:                            # run as a script by `python -I`: load the siblings by path
    import importlib.util
    import os

    def _sibling(name):
        spec = importlib.util.spec_from_file_location(
            name, os.path.join(os.path.dirname(os.path.abspath(__file__)), name + '.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    _t3, _own, _pl = _sibling('pdfium_type3'), _sibling('pdfium_ink_own'), _sibling('pdfium_place')
T3_TOLERANCE, T3_MAX_BYTES, _type3_ok = _t3.T3_TOLERANCE, _t3.T3_MAX_BYTES, _t3.type3_ok
# TD-740: where pdfium places each text object (`pdfium_place`)
EDGE_PT, _IDENTITY, _page_box, _bounds, _matrix = _pl.EDGE_PT, _pl.IDENTITY, _pl.page_box, _pl.bounds, _pl.matrix
_times, _through, _outside = _pl.times, _pl.through, _pl.outside

#: Text render modes that paint (as ``pdf_pages._DRAWN_MODES``).
DRAWN_MODES = frozenset((0, 1, 2, 4, 5, 6))
#: The exit code of a child that ran out of memory (Python's MemoryError under the Linux address-space cap; fix
#: round 10): nothing is written, and the parent logs it as its own reason.
OUT_OF_MEMORY = 86


def raster_scale(width_pt: float, height_pt: float, dpi: float, max_side_px: float, max_page_pt: float):
    """The render scale for a page: ``dpi``, shrunk so the longer side stays within ``max_side_px``; None for a page
    box that is empty or past ``max_page_pt`` (``pdf_pages.raster_scale`` passes its constants)."""
    longer = max(width_pt, height_pt)
    if not (width_pt > 0 and height_pt > 0) or longer > max_page_pt:
        return None
    return min(dpi / 72.0, max_side_px / longer)


# ── The painted-text check (moved from pdf_pdfium_check; the rules are its docstring's a-d) ──

class _OverObjects(Exception):
    pass


def _paints(pdf, index: int, has_alnum: bool, oc_may_be_off: bool, budget: list, plain: frozenset,
            blank: bool = False, words: bool = False) -> bool:
    """True when every text object pdfium places on the page paints, outside optional content, and (when pypdf
    found letters or digits there) pdfium places at least one text object. OCR-20: and every annotation pdfium
    lists on the page is a /Link with no /AP (`_plain_link`; each charged one object). Review round 1: ``blank``
    (pypdf's text of the page is blank): pdfium must place NO text object at all. Review round 2: and no XObject
    the page draws carries /OC (`pdfium_type3.page_flags`, as `_op_ink`): an OC mark is not all optional content.
    Review round 3 part 2 (``words``, the SPM words op): and no text or form object under a mark carrying
    /ActualText (`_own_text`). TD-740: and every text object lies on the page box pdfium draws (`_outside`); review
    round 1: a Type3 box is its glyphs' d1 boxes, so every Type3 glyph shown keeps its ink inside its box and
    paints, unless pypdf reads it as blank (`pdfium_type3.shown_ok`)."""
    import pypdfium2.raw as raw
    page = pdf[index]
    try:
        annots = raw.FPDFPage_GetAnnotCount(page.raw)
        budget[0] -= max(annots, 0)
        if budget[0] < 0:
            raise _OverObjects('past the pdfium page-object cap')
        if annots < 0 or not all(_plain_link(page.raw, k) for k in range(annots)):
            return False
        oc_xobject, _xfa, _t3_ok, t3_any = _t3.page_flags(_DATA[0], index)   # OCR-20 r2: an XObject with /OC
        sheet = functools.partial(_pl.render_gray, type(pdf))               # TD-740 r2: glyph ink
        if oc_xobject or (t3_any and not _t3.shown_ok(_DATA[0], index, sheet)):   # TD-740 r1: Type3 glyph boxes
            return False
        area = _page_box(raw, page.raw)                            # TD-740: where pdfium draws the page
        # (page or form object, is a form, under an OC mark, the holder's space to page space)
        texts, todo = 0, [(page.raw, False, False, _IDENTITY)]
        while todo:
            holder, is_form, under_oc, to_page = todo.pop()
            count = raw.FPDFFormObj_CountObjects(holder) if is_form else raw.FPDFPage_CountObjects(holder)
            if count < 0:
                raise ValueError('pdfium cannot count the objects')
            budget[0] -= count
            if budget[0] < 0:
                raise _OverObjects('past the pdfium page-object cap')
            for j in range(count):
                obj = raw.FPDFFormObj_GetObject(holder, j) if is_form else raw.FPDFPage_GetObject(holder, j)
                if not obj:
                    raise ValueError('pdfium lost a page object')
                kind = raw.FPDFPageObj_GetType(obj)
                if kind == raw.FPDF_PAGEOBJ_TEXT:
                    texts += 1
                    if (blank or under_oc or _oc_marked(obj, oc_may_be_off, plain)
                            or raw.FPDFTextObj_GetTextRenderMode(obj) not in DRAWN_MODES or (words and _own_text(obj))
                            or _outside(_through(_bounds(raw, obj), to_page), area)):
                        return False
                elif kind == raw.FPDF_PAGEOBJ_FORM:
                    if words and _own_text(obj):
                        return False
                    todo.append((obj, True, under_oc or _oc_marked(obj, oc_may_be_off, plain),
                                 _times(_matrix(raw, obj), to_page)))
        return texts > 0 or not has_alnum
    finally:
        page.close()


def _plain_link(page, k: int) -> bool:
    """True when the page's annotation ``k`` is a /Link with no /AP: the one kind that paints nothing (OCR-20)."""
    import pypdfium2.raw as raw
    annot = raw.FPDFPage_GetAnnot(page, k)
    try:
        return (bool(annot) and raw.FPDFAnnot_GetSubtype(annot) == raw.FPDF_ANNOT_LINK
                and not raw.FPDFAnnot_HasKey(annot, b'AP'))
    finally:
        if annot:
            raw.FPDFPage_CloseAnnot(annot)


def _oc_marked(obj, oc_may_be_off: bool, plain: frozenset) -> bool:
    """True when a page object carries an ``OC`` mark that may hide it, or a mark pdfium cannot read."""
    import pypdfium2.raw as raw
    for m in range(raw.FPDFPageObj_CountMarks(obj)):
        mark = raw.FPDFPageObj_GetMark(obj, m)
        name = _mark_text(raw.FPDFPageObjMark_GetName, mark) if mark else None
        if name is None:
            return True
        if name != 'OC':
            continue
        keys = {_mark_text(raw.FPDFPageObjMark_GetParamKey, mark, k) for k in range(raw.FPDFPageObjMark_CountParams(mark))}
        if (oc_may_be_off or keys != plain
                or raw.FPDFPageObjMark_GetParamValueType(mark, b'Type') != raw.FPDF_OBJECT_NAME):
            return True
    return False


def _own_text(obj) -> bool:
    """True when a mark on the object (a BDC property list, inline or a /Properties resource) holds /ActualText,
    or a mark pdfium cannot read in full: pdfium's text page then gives that text, not the glyphs drawn (probes
    p4a, p4b: drawn 'D', words 'A+'). OCR-20 review round 3 part 2."""
    import pypdfium2.raw as raw
    for m in range(raw.FPDFPageObj_CountMarks(obj)):
        mark = raw.FPDFPageObj_GetMark(obj, m)
        count = raw.FPDFPageObjMark_CountParams(mark) if mark else -1
        if count < 0 or any(_mark_text(raw.FPDFPageObjMark_GetParamKey, mark, k) in (None, 'ActualText')
                            for k in range(count)):
            return True
    return False


def _mark_text(call, mark, *index):
    """A mark's name or parameter key; None when pdfium cannot give it whole."""
    buf, size = ctypes.create_string_buffer(64), ctypes.c_ulong()
    if not call(mark, *index, buf, len(buf), ctypes.byref(size)) or size.value > len(buf):
        return None
    return buf.raw[:size.value].decode('utf-16-le', 'replace').rstrip('\x00')


# ── The operations ──

def _op_paints(pdf, req, blobs):
    """{hidden: [page index, ...]}: every judged page pdfium does not paint in full, or cannot judge."""
    pages = [(int(p[0]), bool(p[1]), len(p) > 2 and bool(p[2])) for p in req['pages']]   # [index, has_alnum, blank]
    if len(pdf) != req['count']:
        return {'hidden': [p[0] for p in pages]}
    budget, hidden, plain = [int(req['max_objects'])], [], frozenset(req['plain'])
    for i, has_alnum, blank in pages:
        try:
            if not _paints(pdf, i, has_alnum, bool(req['oc_off']), budget, plain, blank):
                hidden.append(i)
        except MemoryError:  # the whole child stops (`OUT_OF_MEMORY`): every judged page is then hidden
            raise
        except Exception:   # a page pdfium cannot judge is hidden (the object cap included)
            hidden.append(i)
    return {'hidden': hidden}


def _png(image) -> bytes:
    buf = io.BytesIO()
    image.convert('RGB').save(buf, format='PNG')
    return buf.getvalue()


# ── The blank-page guard (2026-11-21) ──
# Under the Linux memory cap (`_limit_memory`) pdfium can fail to decode a big JPEG 2000 image and draw NOTHING,
# with no error: an A4 400 dpi colour JPX scan at 1:7 (6.6 MB) rendered mean 255, spread 0. A white page then went
# to the AI read as if it were the letter (an empty offer read is stored as 'ok'). A page that renders PURE white
# while it draws a JPX image whose data cannot be pure white is a failed render ("cannot read"), never a picture.
BLANK_STOP = 'render came back blank although the page draws a JPEG 2000 image'
#: A JPX image counts when its encoded data holds at least this many bytes per pixel AND `JPX_MIN_BYTES`. A
#: pure-white JPX is far under the ratio at any size (Pillow, A4 400 dpi colour: 448 B, about 0.00003 B/px; with
#: 128 px tiles about 0.003 B/px, the worst measured), so a genuinely blank scanned page never trips; a colour scan
#: at 1:200 is 0.015 B/px, and the failed letter 0.43 B/px. The floor keeps a tiny image, whose fixed header alone
#: passes the ratio, out: a decode that runs out of memory is megabytes of data.
JPX_MIN_BYTES_PER_PX = 0.01
JPX_MIN_BYTES = 16 * 1024
#: Page objects walked looking for that image (forms included); past it the page is not judged (kept as drawn).
_BLANK_WALK_MAX = 10_000


def _pure_white(image) -> bool:
    """True when every pixel of a render is 255 in every colour band (one C pass, about 10 ms for 4 MP)."""
    bands, extrema = image.getbands(), image.getextrema()
    extrema = (extrema,) if len(bands) == 1 else extrema
    return all(lo == 255 for band, (lo, _hi) in zip(bands, extrema) if band not in ('A', 'X'))


def _filters(obj) -> list:
    import pypdfium2.raw as raw
    names = []
    for k in range(max(0, raw.FPDFImageObj_GetImageFilterCount(obj))):
        buf = ctypes.create_string_buffer(64)
        size = raw.FPDFImageObj_GetImageFilter(obj, k, buf, len(buf))
        names.append(buf.raw[:max(0, size - 1)].decode('latin-1') if 0 < size <= len(buf) else '?')
    return names


def _dense_jpx(obj) -> bool:
    """True for an image object filtered by /JPXDecode whose encoded data reaches `JPX_MIN_BYTES` and
    `JPX_MIN_BYTES_PER_PX` (the floor alone when pdfium cannot give its pixel size)."""
    import pypdfium2.raw as raw
    if 'JPXDecode' not in _filters(obj):
        return False
    size = raw.FPDFImageObj_GetImageDataRaw(obj, None, 0)
    w, h = ctypes.c_uint(), ctypes.c_uint()
    if not raw.FPDFImageObj_GetImagePixelSize(obj, ctypes.byref(w), ctypes.byref(h)):
        return size >= JPX_MIN_BYTES
    return size >= max(JPX_MIN_BYTES, JPX_MIN_BYTES_PER_PX * w.value * h.value)


def draws_dense_jpx(page) -> bool:
    """True when the page (or a form on it, at any depth) draws a `_dense_jpx` image."""
    import pypdfium2.raw as raw
    todo, walked = [(page.raw, False)], 0
    while todo:
        holder, is_form = todo.pop()
        count = raw.FPDFFormObj_CountObjects(holder) if is_form else raw.FPDFPage_CountObjects(holder)
        walked += max(0, count)
        if walked > _BLANK_WALK_MAX:
            return False
        for j in range(max(0, count)):
            obj = raw.FPDFFormObj_GetObject(holder, j) if is_form else raw.FPDFPage_GetObject(holder, j)
            kind = raw.FPDFPageObj_GetType(obj) if obj else None
            if kind == raw.FPDF_PAGEOBJ_IMAGE and _dense_jpx(obj):
                return True
            if kind == raw.FPDF_PAGEOBJ_FORM:
                todo.append((obj, True))
    return False


def blank_render(page, image) -> bool:
    """The guard: the render is pure white (`_pure_white`) AND the page draws a dense JPX image. The page objects are
    walked only for a pure-white render, so an ordinary page pays one pass over its pixels."""
    return _pure_white(image) and draws_dense_jpx(page)


def _op_render(pdf, req, blobs):
    """Each page in ``pages`` its own PNG, in order, stopping at the first page box out of bounds, failure or
    `blank_render` (what was rendered before it is kept). Nothing when pdfium sees another page count than pypdf."""
    out = {'pngs': [], 'stop': None}
    if len(pdf) == 0 or len(pdf) != req['count']:
        out['stop'] = 'page count'
        return out
    for i in req['pages']:
        try:
            page = pdf[i]
            width, height = page.get_width(), page.get_height()
            scale = raster_scale(width, height, *req['scale'])
            if scale is None:
                out['stop'] = 'page box %.0f x %.0f pt' % (width, height)
                break
            image = page.render(scale=scale).to_pil()
            if blank_render(page, image):
                out['stop'] = BLANK_STOP
                break
            blobs.append(_png(image))
            out['pngs'].append(len(blobs) - 1)
        except Exception as e:   # the rest of the pages are not rendered; the caller logs it
            out['stop'] = type(e).__name__
            break
    return out


def _op_stack(pdf, req, blobs):
    """{png: blob index or None}: ``pages`` rendered to ONE vertical PNG within the pixel budget; None (with
    ``stop``) when any page is a `blank_render`, so the caller's read is not made rather than made on a gap."""
    from PIL import Image
    indices = list(req['pages'])
    if len(pdf) == 0 or len(pdf) != req['count']:
        return {'png': None}
    pages = {i: pdf[i] for i in indices}
    boxes = [(pages[i].get_width(), pages[i].get_height()) for i in indices]
    dpi, max_side, max_page = req['scale']
    if any(raster_scale(w, h, dpi, max_side, max_page) is None for w, h in boxes):
        return {'png': None}
    total_h = sum(h for _w, h in boxes)
    scale = min(dpi / 72.0, max_side / max(total_h, max(w for w, _h in boxes)))
    images = []
    for i in indices:
        image = pages[i].render(scale=scale).to_pil()
        if blank_render(pages[i], image):
            return {'png': None, 'stop': BLANK_STOP}
        images.append(image.convert('RGB'))
    sheet = Image.new('RGB', (max(im.width for im in images), sum(im.height for im in images)), 'white')
    y = 0
    for im in images:
        sheet.paste(im, (0, y))
        y += im.height
    buf = io.BytesIO()
    sheet.save(buf, format='PNG')
    blobs.append(buf.getvalue())
    return {'png': len(blobs) - 1}


#: Page objects the ``words`` op walks on page 1 (forms included) before it reads a word (as `_op_paints`' cap).
WORDS_MAX_OBJECTS = 20_000


def _op_words(pdf, req, blobs):
    """{words: [...]}: page 1 of a digital PDF as word boxes in the Vision shape (top-left origin, points).
    OCR-20 review round 1, its own backstop: NO words (``refused``) unless page 1 passes `_paints` strictly — every
    annotation a /Link with no /AP, every text object (forms' too) in a mode that paints (never 3 / 7) and under no
    optional-content mark at all (any OC mark may be off) and no XObject with /OC (review round 2), within
    `WORDS_MAX_OBJECTS`; and no text under /ActualText (`_own_text`, review round 3 part 2); and no text object off
    the page box (`_outside`, TD-740: pdfium's text page lists a word placed off the page too). The whole page is
    refused, not its hidden characters dropped: pdfium's text page (pypdfium2 4.30) does not say which object drew a character."""
    try:
        drawn = len(pdf) > 0 and _paints(pdf, 0, True, True, [WORDS_MAX_OBJECTS], frozenset(), words=True)
    except MemoryError:
        raise
    except Exception:            # a page pdfium cannot judge gives no words
        drawn = False
    if not drawn:
        return {'words': [], 'refused': True}
    page = pdf[0]
    height, tp = page.get_height(), page.get_textpage()
    out, cur = [], []

    def flush():
        if cur:
            le, bo = min(c[1] for c in cur), min(c[2] for c in cur)
            ri, to = max(c[3] for c in cur), max(c[4] for c in cur)
            out.append({'text': ''.join(c[0] for c in cur), 'cx': (le + ri) / 2,
                        'cy': height - (bo + to) / 2, 'h': to - bo, 'angle': 0.0})
            cur.clear()
    for i in range(tp.count_chars()):
        ch = tp.get_text_range(i, 1)
        if not ch or ch.isspace():
            flush()
            continue
        cur.append((ch, *tp.get_charbox(i)))
    flush()
    return {'words': out}


def _op_layout(pdf, req, blobs):
    """{text}: page 1's pypdf LAYOUT text (`pdf_rules_pages.pdf_page1_layout`, OCR-first S1 review round 1) — here, not
    in the web process, because layout mode pads every line by x-position: a crafted page is bounded by this
    child's time limit and memory cap. pypdf reads the same bytes pdfium opened (``_DATA``)."""
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(_DATA[0]))
    if reader.is_encrypted:
        reader.decrypt('')
    return {'text': reader.pages[0].extract_text(extraction_mode='layout') or ''}


#: The most characters the ``ink`` op reports on one page (a dense genuine page 1: about 5,000). Past it: an error.
MAX_INK_CHARS = 20_000
#: Text render modes the ``ink`` op allows on its page: fill only (review round 1, B1). A stroke (1, 2) paints
#: past the glyph's own box, so another line's stroke could lend its ink to a hidden word (0 of the 49 lockable
#: genuine UMS, UiTM, UUM, UPSI and UM letters strokes any page-1 text); 4-6 add a clip (the second render is then
#: not "the page minus its text"), 3 / 7 paint nothing: refused (`modes_ok` False).
INK_MODES = frozenset((0,))
#: Ink farther than this (pixels) from every character's box is "stray" (``stray_px``): text drawing outside the
#: box pdfium gives it (genuine: 0 pixels on every lockable letter; within 1 px: up to 17, antialiasing).
STRAY_PAD = 2
#: Review round 2b (the ring attack): how far (pixels, along and across the line) ANOTHER character's box reaches
#: when it explains a pixel's change (`_ink`). Across the line: 0.5 (antialiasing past the box's edge). Along it:
#: 0 — pdfium places a glyph up to ~0.6 px off its box along the line, so any reach there takes a narrow letter's
#: own stem (an 'l' 1.1 px wide sits 0.14 px from its neighbour on genuine letters: 0.5 cost 5 of 33 UMS locks).
OWN_PAD_X = 0.0
OWN_PAD_Y = 0.5
#: The neighbour grid and its caps (`pdfium_ink_own`: ``_CELL``, ``MAX_INK_CELLS``, ``MAX_INK_NEIGHBOURS``).


def _op_ink(pdf, req, blobs):
    """S-visible 2 (`pdf_ink`): what each character of page ``page`` adds to the picture. The page is rendered as
    is (A, greyscale, annotations drawn), then with EVERY text object (page level and inside forms) set to render
    mode 3 (B); the diff |A - B| is the text's own ink — white, covered, clipped or same-colour text adds ~0.
    -> ``{chars: [[codepoint, generated, l, b, r, t, ink_px, area_px, inside, cover_h, cover_w], ...], modes_ok,
    annots_ok, stray_px, optional, xfa}``: the char box in points (pdfium's tight box), ``ink_px`` the pixels of
    the box (+1 px) whose luminance the text changes by at least ``delta`` once what the OTHER characters' boxes
    can explain is taken off (review round 2b, the ring attack; a space: its own box, as is), ``area_px`` the
    box's pixels, ``inside`` the box within the rendered page, ``cover_h`` / ``cover_w`` the share of the box's
    height / width its ink's bounding box spans (review round 1, B2: a strip left uncovered). ``modes_ok``: every text object
    fills (`INK_MODES`); ``annots_ok``: every annotation is a /Link with no /AP; ``stray_px``: ink pixels more than
    `STRAY_PAD` from every character's box; ``optional``: page content in optional content (an OC mark, or an
    XObject with /OC: a viewer may show what pdfium hides, or hide what it shows); ``xfa``: an XFA form;
    ``type3_ok``: every Type3 glyph page 1 can draw paints only inside its own box (`_type3_ok`, review round 2);
    ``type3``: page 1 can reach a Type3 font at all (fix round 3: refused unless the lane allows Type3,
    `pdf_ink.TYPE3_LANES`);
    ``px_pt``: one rendered pixel in points (`pdf_ink` widens each box by its +1 px ring when it asks who lends ink).
    ``{error}`` on a page count other than pypdf's, a page box out of bounds, too many characters, or any pdfium
    or pypdf failure."""
    try:
        return _ink(pdf, req)
    except MemoryError:                     # the whole child stops (`OUT_OF_MEMORY`)
        raise
    except Exception as e:                  # refused by the caller (`pdf_ink.ink_missing`: 'no_answer')
        return {'error': type(e).__name__}


def _ink(pdf, req):
    import pypdfium2.raw as raw
    from PIL import Image, ImageChops, ImageDraw
    if len(pdf) == 0 or len(pdf) != req['count']:
        return {'error': 'page count'}
    page = pdf[int(req['page'])]
    scale = raster_scale(page.get_width(), page.get_height(), *req['scale'])
    if scale is None:
        return {'error': 'page box'}
    tp = page.get_textpage()
    n = tp.count_chars()
    if n < 0 or n > MAX_INK_CHARS:
        return {'error': 'chars'}
    a = page.render(scale=scale, grayscale=True).to_pil().convert('L')
    modes_ok, optional = True, False
    for obj in page.get_objects(max_depth=15):
        optional = optional or _oc_marked(obj.raw, True, frozenset())    # any OC mark, or one pdfium cannot read
        if raw.FPDFPageObj_GetType(obj.raw) == raw.FPDF_PAGEOBJ_TEXT:
            modes_ok = modes_ok and raw.FPDFTextObj_GetTextRenderMode(obj.raw) in INK_MODES
            if not raw.FPDFTextObj_SetTextRenderMode(obj.raw, raw.FPDF_TEXTRENDERMODE_INVISIBLE):
                return {'error': 'mode'}
    b = page.render(scale=scale, grayscale=True).to_pil().convert('L')
    if a.size != b.size:
        return {'error': 'size'}
    width, height = a.size
    delta = ImageChops.difference(a, b)
    mask = delta.point(lambda v: 255 if v >= int(req['delta']) else 0)
    dx, dy = ctypes.c_int(), ctypes.c_int()

    def dev(x, y):
        raw.FPDF_PageToDevice(page.raw, 0, 0, width, height, 0, x, y, dx, dy)
        return dx.value, dy.value
    devf = _own.device_map(raw, page.raw, width, height)

    chars, turned = [], page.get_rotation() in (90, 270)
    pad_x, pad_y = (OWN_PAD_Y, OWN_PAD_X) if turned else (OWN_PAD_X, OWN_PAD_Y)   # the line runs down the picture
    near = Image.new('L', a.size, 0)          # every character's box, widened by STRAY_PAD
    draw = ImageDraw.Draw(near)
    seen = []                                  # per char: None (generated) or (device box, ring box, space, boxed)
    for i in range(n):
        gen = raw.FPDFText_IsGenerated(tp.raw, i) == 1
        cp = 32 if gen else int(raw.FPDFText_GetUnicode(tp.raw, i) or 32)
        if gen:                                 # pdfium's own space or line break: nothing drawn
            chars.append([cp, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0])
            seen.append(None)
            continue
        # A space in the text (review round 2, #3) is measured too, so a glyph that ToUnicode maps to a space but
        # that draws is in the overlap rules (`pdf_ink`). Its ink is counted in its OWN box, not +1 px (a genuine
        # space's ring holds its neighbours' edges; its own box holds no ink); it joins the near-mask only with a
        # real box.
        l, bo, r, t = tp.get_charbox(i)
        space = chr(cp).isspace()
        boxed = not space or (r > l and t > bo)
        ring = 0 if space else 1
        (x0, y0), (x1, y1) = dev(l, t), dev(r, bo)
        x0, x1, y0, y1 = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
        inside = x0 >= -1 and y0 >= -1 and x1 <= width + 1 and y1 <= height + 1
        box = (max(0, x0 - ring), max(0, y0 - ring), min(width, x1 + ring), min(height, y1 + ring))
        if boxed:
            draw.rectangle((x0 - STRAY_PAD, y0 - STRAY_PAD, x1 + STRAY_PAD - 1, y1 + STRAY_PAD - 1), fill=255)
        chars.append([cp, 0, round(l, 2), round(bo, 2), round(r, 2), round(t, 2), 0, 0, int(inside), 0.0, 0.0])
        fx = [devf(px, py) for px in (l, r) for py in (bo, t)]
        reach = (min(p[0] for p in fx) - pad_x, min(p[1] for p in fx) - pad_y,
                 max(p[0] for p in fx) + pad_x, max(p[1] for p in fx) + pad_y)
        seen.append((reach, box, space, boxed))
    for i, s in enumerate(seen):                # a space: its own box's ink, as is (`pdf_ink._drawn_space`)
        if s and s[2] and s[3] and s[1][2] > s[1][0] and s[1][3] > s[1][1]:
            box = s[1]
            chars[i][6], chars[i][7] = mask.crop(box).histogram()[255], (box[2] - box[0]) * (box[3] - box[1])
    # Review round 2b (the ring attack): only ink the OTHER characters cannot explain (`pdfium_ink_own.own_ink`).
    if not _own.own_ink(delta, seen, chars, width, height, int(req['delta']), turned):
        return {'error': 'cells'}
    stray =ImageChops.subtract(mask, near).histogram()[255]
    annots_ok = all(_plain_link(page.raw, k) for k in range(raw.FPDFPage_GetAnnotCount(page.raw)))   # OCR-20: no /AP
    oc_xobject, xfa, type3_ok, type3 = _t3.page_flags(_DATA[0], int(req['page']))
    return {'chars': chars, 'modes_ok': modes_ok, 'annots_ok': annots_ok, 'stray_px': stray,
            'optional': bool(optional or oc_xobject), 'xfa': xfa, 'type3_ok': bool(type3_ok), 'type3': bool(type3),
            'px_pt': round(1.0 / scale, 4)}


_OPS ={'count': lambda pdf, req, blobs: {'count': len(pdf)}, 'paints': _op_paints, 'render': _op_render,
        'stack': _op_stack, 'words': _op_words, 'layout': _op_layout, 'ink': _op_ink}
#: The request's PDF bytes, for an operation that reads them with pypdf (``layout``, ``ink``).
_DATA = [b'']


def _limit_memory(budget: int) -> None:
    """Linux: cap this process's address space at what it holds now (interpreter, pypdfium2, Pillow) plus
    ``budget`` bytes, so a PDF that asks pdfium for more fails here (MemoryError / a pdfium error -> the safe
    answer) instead of pushing the instance past its memory. Elsewhere (Windows dev and tests): no cap."""
    if not budget or not sys.platform.startswith('linux'):
        return
    import os
    import resource
    try:
        with open('/proc/self/statm') as fh:
            held = int(fh.read().split()[0]) * os.sysconf('SC_PAGE_SIZE')
        resource.setrlimit(resource.RLIMIT_AS, (held + budget, held + budget))
    except (OSError, ValueError):   # no /proc or a hard limit already lower: the time limit still holds
        pass


def _limit_cpu(seconds: int) -> None:
    """Linux (fix round 9): the kernel kills this process after ``seconds`` of CPU (the parent passes a little more
    than the child's time limit), so an orphan dies even if the web process that would have killed it is gone."""
    if not seconds or not sys.platform.startswith('linux'):
        return
    import resource
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (seconds, seconds + 1))
    except (OSError, ValueError):
        pass


def _die_with_parent(parent: int) -> None:
    """Linux (fix round 9): SIGKILL this process when the web process that spawned it dies (``prctl``
    PR_SET_PDEATHSIG), and exit at once when it is already gone. Elsewhere the parent closing stdin is enough:
    the request is read to its end before any pdfium work, and a cut request does not parse."""
    import os
    if not parent or not sys.platform.startswith('linux'):
        return
    try:
        ctypes.CDLL(None, use_errno=True).prctl(1, 9)      # PR_SET_PDEATHSIG, SIGKILL
    except (OSError, AttributeError):
        pass
    if os.getppid() != parent:
        sys.exit(2)


def main() -> int:
    try:
        return _main()
    except MemoryError:                    # past the address-space cap: say so by the exit code, write nothing
        import os
        os._exit(OUT_OF_MEMORY)


def _main() -> int:
    raw_in = sys.stdin.buffer.read()
    head, _, data = raw_in.partition(b'\n')
    request = json.loads(head)
    del raw_in
    _die_with_parent(int(request.get('parent') or 0))
    _limit_cpu(int(request.get('cpu') or 0))
    inks = any(op.get('op') == 'ink' for op in request['ops'])
    if inks:                               # the ink op's attribution (`_ink`, review round 2b) needs it
        __import__('numpy')            # loaded before the memory cap, like Pillow
    else:                                  # pypdfium2 imports numpy only for to_numpy (never used): ~90 ms saved
        sys.modules['numpy'] = None
    from PIL import Image
    Image.preinit()                        # Pillow's PNG writer loaded before the memory cap is set
    import pypdfium2 as pdfium
    if any(op.get('op') in ('layout', 'ink', 'paints', 'words') for op in request['ops']):   # OCR-20 r2: page_flags
        import pypdf  # noqa: F401  (loaded before the memory cap, like Pillow)
        _DATA[0] = data
    _limit_memory(int(request.get('memory') or 0))
    blobs, results = [], []
    pdf = pdfium.PdfDocument(data)
    try:
        for op in request['ops']:
            results.append(_OPS[op['op']](pdf, op, blobs))
    finally:
        pdf.close()
    out = sys.stdout.buffer
    out.write(json.dumps({'results': results, 'blobs': [len(b) for b in blobs]}).encode() + b'\n')
    for b in blobs:
        out.write(b)
    out.flush()
    return 0


if __name__ == '__main__':
    sys.exit(main())
