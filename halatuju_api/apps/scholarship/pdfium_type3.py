"""The Type3 glyph rules for the pdfium child (moved out of `pdfium_worker`, which was over the line limit).

Pure Python plus pypdf (imported inside the function): no pdfium. `pdfium_worker` re-exports `T3_TOLERANCE`,
`T3_MAX_BYTES` and `_type3_ok`, and loads this file by path when it runs as a script. `page_flags` (the ink op's
pypdf flags) lives here too since the OCR-9 rebase."""

#: Type3 glyph procedures (review round 2, B2): a glyph whose procedure paints outside its own ``d1`` box draws
#: ink where pdfium's char box is not (a tiny /space glyph placed far away painting boxes over a white word), so
#: the overlap and stray rules miss it. Every Type3 font page 1 can reach must keep each path coordinate inside its
#: glyph's ``d1`` box (`T3_TOLERANCE` of the box's longer side), use only the operators below, and a ``d0`` glyph
#: (coloured: anything goes) may not paint at all. Genuine cost: the 6 UiTM letters with Type3 fonts pass; 0 of
#: the 58 UMS use one. Fix round 3 (review round 3's BLOCKER): the tolerance is a share of the box's LONGER side,
#: so a flat 1000 x 1 glyph may paint 20 units (20x its height) above and below its box, onto a white value. While
#: the rules lane is UMS-only, ANY Type3 font page 1 can reach refuses (`pdf_ink.TYPE3_LANES` is empty); this
#: check only matters once a lane allows Type3, and before that the tolerance must change (decisions.md).
T3_TOLERANCE = 0.02
#: Path construction: the operator and its operand count (each pair an x, y to check).
_T3_PATH = {'m': 2, 'l': 2, 'c': 6, 'v': 4, 'y': 4}
#: Operators that paint nothing outside the path: filling, closing, ending or clipping a path, graphics state with
#: no matrix, colour (ignored under d1), marked content. Not here, so refused: cm, gs, Do, an inline image, sh,
#: any text operator, a stroke (it paints past the path by the line width; no genuine glyph strokes), anything else.
_T3_FILL_OPS = frozenset(('f', 'F', 'f*'))
_T3_STATE_OPS = frozenset('h n W W* q Q w J j M d ri i g G rg RG k K cs CS sc SC scn SCN BMC BDC EMC MP DP BX EX'
                          .split())
#: The most bytes of glyph procedures read for one page (a genuine letter's Type3 fonts: well under 1 MB).
T3_MAX_BYTES = 4_000_000


def type3_ok(font, budget: list) -> bool:
    """True when every glyph procedure of the Type3 ``font`` keeps to the rules above (`T3_TOLERANCE`)."""
    from pypdf.generic import ContentStream
    procs = _val(font, '/CharProcs')
    if not hasattr(procs, 'values'):
        return False
    for ref in procs.values():
        proc = ref.get_object()
        budget[0] -= len(proc.get_data())
        if budget[0] < 0:
            return False
        try:
            ops = [(args, _op_name(op)) for args, op in ContentStream(proc, None).operations]
        except Exception:                         # a glyph pypdf cannot parse is not one it can vouch for
            return False
        if not _glyph_ok(ops):
            return False
    return True


def _glyph_ok(ops: list) -> bool:
    """`type3_ok` for one glyph procedure's operations ``ops`` ((operands, operator name) pairs)."""
    if not ops:
        return True
    head_args, head = ops[0]
    if head == 'd0':                              # a coloured glyph: it may set state, never paint
        return all(name in _T3_STATE_OPS for _a, name in ops[1:])
    if head != 'd1' or len(head_args) != 6:
        return False
    llx, lly, urx, ury = (float(v) for v in head_args[2:])
    llx, urx, lly, ury = min(llx, urx), max(llx, urx), min(lly, ury), max(lly, ury)
    tol = T3_TOLERANCE * max(urx - llx, ury - lly)
    for args, name in ops[1:]:
        if name in _T3_PATH or name == 're':
            nums = [float(v) for v in args]
            if name == 're':
                if len(nums) != 4:
                    return False
                x, y, w, h = nums
                pts = [(x, y), (x + w, y + h)]
            else:
                if len(nums) != _T3_PATH[name]:
                    return False
                pts = list(zip(nums[0::2], nums[1::2]))
            if any(not (llx - tol <= px <= urx + tol and lly - tol <= py <= ury + tol) for px, py in pts):
                return False
        elif name not in _T3_FILL_OPS and name not in _T3_STATE_OPS:
            return False
    return True


def _op_name(op) -> str:
    return op.decode('latin-1') if isinstance(op, bytes) else str(op)


def _val(d, key):
    """``d[key]`` with an indirect reference resolved; None when absent or ``d`` is no dictionary. TD-740 review
    round 3 (Finding 2): pdfium (and pypdf's ``[]``) resolve every value, pypdf's ``get`` does not, so a compare
    on the unresolved value missed a form whose /Subtype is ``9 0 R`` that both readers draw and read."""
    v = d.get(key) if hasattr(d, 'get') else None
    return v.get_object() if v is not None else None


#: TD-740 review round 1: the most bytes of page content (the page's and its forms') `shown_ok` reads.
SHOWN_MAX_BYTES = 16_000_000
#: TD-740 review round 2 (Finding 1): a Type3 glyph must really ink, MEASURED by pdfium, not read from its operators
#: (a zero-area ``re``, ``re n f``, a filled line, an even-odd pair that cancels, an empty clip, a speck all "paint"
#: by their words and put no real ink down). Each (font, code) shown is drawn alone on a glyph sheet (`glyph_sheet`),
#: black, at `INK_PX_EM` pixels an em and again at twice that, and the AREA it fills inside its d1 box must be at
#: least `INK_MIN_SHARE` of an em square (a full stop fills about 1-2%). Area grows with the square of the scale; a
#: hairline (pdfium draws a zero-area fill one pixel wide) and edge residue (an even-odd pair) grow with the scale
#: only, so the area is (ink at 2s - 2 x ink at s) / 2 (`glyph_ink`): the hairline cancels out.
INK_PX_EM = 32
INK_MIN_SHARE = 0.005
#: A d1 box longer than this (ems) is drawn smaller, its minimum scaled with it; the space between cells (points).
INK_MAX_EM = 3.0
INK_GAP = 16
#: Cells a side on one sheet page, and the most (font, code) pairs one page may show in Type3 (10 sheet pages).
INK_GRID = 12
INK_MAX_GLYPHS = 1440
#: The codes a Type3 glyph that draws nothing may show. pdfium's text page reads a Type3 code with no ToUnicode as
#: its own byte (probe pages_node_layout: a /space glyph under code 76 reads 'L' in the words op), so only a
#: whitespace byte that every candidate font also reads as blank is blank to both readers.
BLANK_CODES = frozenset((9, 10, 13, 32))
#: The text sheet's font size (points), its page 8x that a side, and the run each code is shown in: `RUN` copies
#: spread `RUN_TC` points apart by character spacing (r4, edge (j): pdfium drops a text OBJECT whose whole box is
#: degenerate, so a zero-box code shown alone read nothing on the sheet while ``(LL) Tj`` read on the page).
TEXT_PT, RUN, RUN_TC = 1000, 3, 500


def shown_ok(data: bytes, index: int, sheet=None, chars=None) -> bool:
    """TD-740 review round 1 (pdfium child, `pdfium_worker._paints`): True when every character page ``index``
    shows in a Type3 font has a glyph that keeps its ink inside its ``d1`` box (`_glyph_ok`, the `type3_ok` rules)
    and really inks (round 2: measured by pdfium on a glyph sheet, `glyph_ink`; ``sheet`` renders it, None: no
    Type3 character can pass), or (a glyph that inks nothing, or none) shows a code every font the name could
    resolve to reads as blank to pdfium's own text page (r3: `pdfium_blank`, read by ``chars``; None: no such code
    can pass) and to pypdf, and is not refused by `_blank_to_both`. pdfium boxes a Type3 char by its ``d1`` box,
    not its ink: a box the ink leaves (probes t3_d1_lie_*, t3_cm_ink_offpage) or an empty glyph (t3_onpage_empty,
    zero_re ... tiny_ink) puts a box on the page while pypdf reads a letter drawn elsewhere or nowhere. Read with
    pypdf from the request's bytes, walking the page's content and forms (``Do``) as the text state flows: a ``Tf``
    name is looked up in EVERY enclosing resource dictionary (pdfium lends a form the page's). A form with no
    /Resources but a /Parent (round 2, Finding 2: two resource views) is False. Fails closed: a walk past 15 forms
    deep or `SHOWN_MAX_BYTES`, past `INK_MAX_GLYPHS`, or anything pypdf or the sheet cannot do, is False."""
    import io
    from pypdf import PdfReader
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            reader.decrypt('')
        page = reader.pages[index]
        uses = {}
        if not _shown_walk(reader, page.get('/Contents'), [page.get('/Resources')], (), [SHOWN_MAX_BYTES], uses,
                           set()):
            return False
        return _uses_ok(uses, sheet, chars)
    except MemoryError:
        raise
    except Exception:
        return False


def _shown_walk(reader, contents, chain: list, fonts: tuple, budget: list, uses: dict, done: set) -> bool:
    """`shown_ok` over one content stream (``chain``: its resource dictionaries, innermost first; ``fonts``: the
    font candidates the text state carries in). Records in ``uses`` each candidate tuple holding a Type3 font with
    the codes shown in it."""
    from pypdf.generic import ContentStream
    if len(chain) > 16:
        return False
    contents = contents.get_object() if contents is not None else None
    if contents is None:
        return True
    parts = contents if isinstance(contents, list) else [contents]
    budget[0] -= sum(len(p.get_object().get_data()) for p in parts)
    if budget[0] < 0:
        return False
    stack = []
    for args, op in ContentStream(contents, reader, 'bytes').operations:
        name = _op_name(op)
        if name == 'q':
            stack.append(fonts)
        elif name == 'Q':
            fonts = stack.pop() if stack else fonts
        elif name == 'Tf' and args:
            fonts = tuple(_in_resources(chain, '/Font', args[0]))
        elif name == 'gs' and args:                 # a font set by a graphics state: not followed, so refused
            if any(hasattr(g, 'get') and '/Font' in g for g in _in_resources(chain, '/ExtGState', args[0])):
                return False
        elif name in ('Tj', 'TJ', "'", '"'):
            if any(_is_t3(f) for f in fonts):
                uses.setdefault(tuple(id(f) for f in fonts), (fonts, set()))[1].update(b''.join(_strings(args)))
        elif name == 'Do' and args:
            for xo in _in_resources(chain, '/XObject', args[0]):
                if not hasattr(xo, 'get') or _val(xo, '/Subtype') != '/Form':     # r3 Finding 2: resolved
                    continue
                if not hasattr(_val(xo, '/Resources'), 'get') and '/Parent' in xo:   # r2 Finding 2: two views
                    return False
                inner = [_val(xo, '/Resources')] + chain
                # r2 Finding 3: the same form under other resources is another walk
                key = (id(xo), tuple(id(r.get_object()) if r is not None else 0 for r in inner),
                       tuple(id(f) for f in fonts))
                if key in done:                    # this form, these resources, this text state: already walked
                    continue
                done.add(key)
                if not _shown_walk(reader, xo, inner, fonts, budget, uses, done):
                    return False
    return True


def _in_resources(chain: list, kind: str, name) -> list:
    """Every object named ``name`` under ``kind`` in any resource dictionary of ``chain``."""
    found = []
    for res in chain:
        obj = _val(_val(res.get_object() if res is not None else None, kind), name)
        if obj is not None:
            found.append(obj)
    return found


def _strings(args):
    """Every string operand of a show-text operator, inside a TJ array too."""
    for arg in args:
        if isinstance(arg, list):
            yield from _strings(arg)
        elif isinstance(arg, (bytes, str)):
            yield arg if isinstance(arg, bytes) else arg.encode('latin-1', 'replace')


def _is_t3(font) -> bool:
    return _val(font, '/Subtype') == '/Type3'                    # r3 Finding 2: an indirect /Subtype resolved


def _uses_ok(uses: dict, sheet, chars) -> bool:
    """`shown_ok`'s verdict on the walk's ``uses``: no shown glyph breaks `_glyph_ok`, and each shown code either
    inks (`glyph_ink`) or, in every candidate font, is blank to pypdf and to our own /ToUnicode reading
    (`_blank_to_both`, now a refuse-only check) AND to pdfium's own text page (`pdfium_blank`, r3)."""
    fonts = {}
    for cands, codes in uses.values():
        for f in cands:
            if _is_t3(f):
                fonts.setdefault(id(f), (f, set()))[1].update(codes)
    budget, cells = [T3_MAX_BYTES], []
    for font, codes in fonts.values():
        boxes, broken = _glyph_boxes(font, codes, budget)
        if broken:
            return False
        cells.extend((font, c, boxes[c]) for c in sorted(boxes))
    inked = glyph_ink(cells, sheet)
    if inked is None:
        return False
    memo, need = {}, {}
    for cands, codes in uses.values():
        for f in cands:
            for c in (codes if _is_t3(f) else ()):
                if (id(f), c) in inked:
                    continue
                for g in cands:                  # r3 Finding 1: pdfium decides; `_blank_to_both` only refuses
                    if not _blank_to_both(g, c, memo):
                        return False
                    need[(id(g), c)] = (g, c)
    blank = pdfium_blank(list(need.values()), chars)
    return blank is not None and set(need) <= blank


def pdfium_blank(pairs: list, chars) -> set | None:
    """TD-740 review round 3 (Finding 1): {(id(font), code)} of the (font, code) ``pairs`` that pdfium's OWN text
    page reads as whitespace. Each pair is shown in a spread run on its own page of a text sheet (`text_sheet`)
    and read by ``chars`` (the child's `pdfium_place.sheet_text`): pdfium must read at least one character of its
    own (not generated) and only whitespace. r4 (edge (j)): reading nothing is NOT blank (a zero-box 'L' alone read
    nothing, but read in a run on the page); a run that collapses anyway is refused. Our own /ToUnicode parser is
    not pdfium (``/Xbeginbfchar``, a ``%`` comment, ``<00 20>``: pdfium reads 'L', the parser a space). None: past
    `INK_MAX_GLYPHS` pairs, no ``chars``, or a read that does not match the sheet (fails closed)."""
    if not pairs:
        return set()
    if chars is None or len(pairs) > INK_MAX_GLYPHS:
        return None
    pages = chars(text_sheet(pairs))
    if len(pages) != len(pairs):
        return None
    blank = set()
    for (font, code), read in zip(pairs, pages):
        if any(gen == 0 for _u, gen in read) and all(gen in (0, 1) and chr(u).isspace() for u, gen in read):
            blank.add((id(font), code))
    return blank


def text_sheet(pairs: list) -> bytes:
    """PDF bytes: one page per (font, code) of ``pairs``, the code shown `RUN` times in one string in a copy of the
    font (`_copy_font`) at `TEXT_PT` points, `RUN_TC` of character spacing apart, inside the page (`pdfium_blank`)."""
    import io
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
    writer, refs = PdfWriter(), {}
    for font, code in pairs:
        name, ref = _copy_font(writer, refs, font)
        page = writer.add_blank_page(TEXT_PT * 8, TEXT_PT * 8)
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject(
            {NameObject(name.decode()): ref})})
        stream = DecodedStreamObject()
        stream.set_data(b'BT %s %d Tf %d Tc %d %d Td <%s> Tj ET' % (
            name, TEXT_PT, RUN_TC, TEXT_PT * 2, TEXT_PT * 2, (b'%02x' % code) * RUN))
        page[NameObject('/Contents')] = writer._add_object(stream)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _copy_font(writer, refs: dict, font) -> tuple:
    """(resource name, reference) of ``font`` copied into ``writer`` with pypdf (its glyph procedures, /ToUnicode
    and own resources come with it), once per font (``refs``)."""
    if id(font) not in refs:
        copy = font.clone(writer)
        refs[id(font)] = (b'/G%d' % len(refs), copy.indirect_reference or writer._add_object(copy))
    return refs[id(font)]


def _blank_to_both(font, code: int, memo: dict) -> bool:
    """True when ``code`` in ``font`` reads as whitespace to pypdf (`_reads_blank`) AND to pdfium: pdfium reads
    a code through the font's /ToUnicode first (`_tounicode_blank`), and with no entry for it through the
    encoding, where only a `BLANK_CODES` byte is taken as blank (a Type3 code with no ToUnicode reads as its own
    byte). TD-740 r2: genuine letters show zero-box Type3 glyphs under codes their /ToUnicode maps to a space."""
    if not _reads_blank(font, code, memo):
        return False
    mapped = _tounicode_blank(font, code, memo)
    return mapped if mapped is not None else code in BLANK_CODES


def _tounicode_blank(font, code: int, memo: dict):
    """True / False when the font's /ToUnicode maps ``code`` (every entry for it) to whitespace / to anything else;
    None when there is no /ToUnicode or no entry for ``code``. A /ToUnicode this reader cannot parse is False for
    every code (fails closed). Read here, not with pypdf: pypdf keys its map by decoded text, and two codes can
    fold to one key (a high byte reads as U+FFFD), so it is not pdfium's view."""
    key = ('tu', id(font))
    if key not in memo:
        memo[key] = _tounicode_map(font)
    found = memo[key]
    if found is False:
        return False
    if found is None or code not in found:
        return None
    return all(t and t.isspace() for t in found[code])


def _tounicode_map(font):
    """{code: [text, ...]} from the font's /ToUnicode bfchar and bfrange entries (None: no /ToUnicode; False: one
    this reader cannot parse, or a range or value it does not take, such as an array range)."""
    import re
    tu = _val(font, '/ToUnicode')
    if tu is None:
        return None
    try:
        text = tu.get_data().decode('latin-1')
        found = {}
        for kind, body in re.findall(r'begin(bfchar|bfrange)(.*?)end\1', text, re.S):
            if not re.fullmatch(r'(\s*<[0-9A-Fa-f\s]*>)*\s*', body):
                return False
            nums = [re.sub(r'\s', '', h) for h in re.findall(r'<([^>]*)>', body)]
            step = 2 if kind == 'bfchar' else 3
            if len(nums) % step:
                return False
            for k in range(0, len(nums), step):
                lo, hi = int(nums[k], 16), int(nums[k + step - 2], 16)
                dst = bytes.fromhex(nums[k + step - 1])
                if hi < lo or hi - lo > 255 or len(dst) % 2 or (hi > lo and len(dst) != 2):
                    return False
                for c in range(lo, hi + 1):
                    out = dst.decode('utf-16-be') if c == lo else chr(int.from_bytes(dst, 'big') + c - lo)
                    found.setdefault(c, []).append(out)
        return found
    except MemoryError:
        raise
    except Exception:
        return False


def _differences(font) -> dict:
    """code -> glyph name, from the Type3 font's /Encoding /Differences."""
    diffs = _val(_val(font, '/Encoding'), '/Differences')
    names, code = {}, 0
    for item in (diffs if diffs is not None else ()):
        item = item.get_object() if hasattr(item, 'get_object') else item
        if isinstance(item, (int, float)) and not isinstance(item, bool):
            code = int(item)
        else:
            names[code], code = str(item), code + 1
    return names


def _glyph_boxes(font, codes, budget: list) -> tuple:
    """({code: its d1 box in text space at size 1 (through the /FontMatrix)} for each of ``codes`` whose glyph is a
    ``d1`` glyph keeping `_glyph_ok`, {codes whose glyph breaks `_glyph_ok`}). A code with no glyph, or a ``d0``
    glyph, is in neither: it draws nothing. Every code is broken past ``budget``."""
    from pypdf.generic import ContentStream
    fm = [float(v.get_object()) for v in _val(font, '/FontMatrix')]
    if len(fm) != 6:
        return {}, set(codes) or {0}
    names = _differences(font)
    procs = _val(font, '/CharProcs')
    procs = procs if procs is not None else {}
    boxes, broken, parsed = {}, set(), {}
    for c in codes:
        proc = procs.get(names[c]) if c in names and hasattr(procs, 'get') else None
        if proc is None:
            continue
        if names[c] not in parsed:
            proc = proc.get_object()
            budget[0] -= len(proc.get_data())
            if budget[0] < 0:
                return {}, set(codes)
            parsed[names[c]] = [(a, _op_name(o)) for a, o in ContentStream(proc, None, 'bytes').operations]
        ops = parsed[names[c]]
        if not _glyph_ok(ops):
            broken.add(c)
        elif ops and ops[0][1] == 'd1' and len(ops[0][0]) == 6:
            boxes[c] = _corners(tuple(float(v) for v in ops[0][0][2:]), fm)
    return boxes, broken


def _corners(box: tuple, m: list) -> tuple:
    """The box (left, bottom, right, top) around ``box``'s corners (llx lly urx ury) taken through ``m``."""
    xs = [x * m[0] + y * m[2] + m[4] for x in (box[0], box[2]) for y in (box[1], box[3])]
    ys = [x * m[1] + y * m[3] + m[5] for x in (box[0], box[2]) for y in (box[1], box[3])]
    return min(xs), min(ys), max(xs), max(ys)


def glyph_sheet(cells: list) -> tuple:
    """(PDF bytes, [(crop box in the page's picture, least ink), ...] per cell, or None for a cell that cannot be
    drawn): each (font, code, text-space box) of ``cells`` shown alone, black, fill only, in its own cell of
    `INK_GRID` x `INK_GRID` cells a page, its box scaled to `INK_PX_EM` points an em (smaller past `INK_MAX_EM`).
    The fonts are copied with pypdf (their glyph procedures and own resources come with them)."""
    import io
    import math
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
    pitch = INK_PX_EM * INK_MAX_EM + INK_GAP
    side = INK_GRID * pitch + INK_GAP
    per, writer, refs, spots, pages = INK_GRID * INK_GRID, PdfWriter(), {}, [], []
    for k, (font, code, box) in enumerate(cells):
        if k % per == 0:
            pages.append([b'0 g 0 Tr'])
        name = _copy_font(writer, refs, font)[0]
        left, bottom, right, top = box
        longer = max(right - left, top - bottom)
        if not all(math.isfinite(v) for v in box) or not longer > 0:
            spots.append(None)
            continue
        scale = INK_PX_EM if longer <= INK_MAX_EM else INK_PX_EM * INK_MAX_EM / longer
        x0, y0 = INK_GAP + (k % per) % INK_GRID * pitch, INK_GAP + (k % per) // INK_GRID * pitch
        pages[-1].append(b'BT %s 1 Tf %.6f 0 0 %.6f %.6f %.6f Tm <%02x> Tj ET' % (
            name, scale, scale, x0 - scale * left, y0 - scale * bottom, code))
        crop = (math.floor(x0) - 3, math.floor(side - y0 - scale * (top - bottom)) - 3,
                math.ceil(x0 + scale * (right - left)) + 3, math.ceil(side - y0) + 3)
        spots.append((crop, INK_MIN_SHARE * scale * scale))
    fonts = DictionaryObject({NameObject(name.decode()): ref for name, ref in refs.values()})
    for ops in pages:
        page = writer.add_blank_page(side, side)
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): fonts})
        stream = DecodedStreamObject()
        stream.set_data(b'\n'.join(ops))
        page[NameObject('/Contents')] = writer._add_object(stream)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue(), spots


def glyph_ink(cells: list, sheet) -> set | None:
    """{(id(font), code)} of the ``cells`` (`glyph_sheet`) whose glyph pdfium draws with at least its least ink
    inside its box; None when there are too many (`INK_MAX_GLYPHS`), no ``sheet`` to render them, or the render
    does not match the sheet."""
    if not cells:
        return set()
    if sheet is None or len(cells) > INK_MAX_GLYPHS:
        return None
    data, spots = glyph_sheet(cells)
    per = INK_GRID * INK_GRID
    once, twice = sheet(data, 1), sheet(data, 2)
    if not len(once) == len(twice) == (len(cells) + per - 1) // per:
        return None
    inked = set()
    for k, (font, code, _box) in enumerate(cells):
        if spots[k] is not None:
            crop, least = spots[k]
            area = (_ink(twice[k // per], tuple(2 * v for v in crop)) - 2 * _ink(once[k // per], crop)) / 2
            if area >= least:
                inked.add((id(font), code))
    return inked


def _ink(image, crop: tuple) -> float:
    """The ink (in fully black pixels) of the greyscale ``image`` inside ``crop`` (cut to the picture)."""
    crop = (max(crop[0], 0), max(crop[1], 0), min(crop[2], image.width), min(crop[3], image.height))
    if crop[2] <= crop[0] or crop[3] <= crop[1]:
        return 0.0
    return sum((255 - v) * n for v, n in enumerate(image.crop(crop).histogram()[:256])) / 255.0


def _reads_blank(font, code: int, memo: dict) -> bool:
    """True when pypdf reads ``code`` in ``font`` as whitespace (its own decoding: `Font.encoding`, then the
    ToUnicode map); False on anything pypdf cannot decode."""
    key = (id(font), code)
    if key not in memo:
        try:
            from pypdf.generic._font import Font
            if ('font', id(font)) not in memo:
                memo[('font', id(font))] = Font.from_font_resource(font)
            reader_font = memo[('font', id(font))]
            enc = reader_font.encoding
            text = bytes([code]).decode(enc, 'replace') if isinstance(enc, str) else enc.get(code, chr(code))
            memo[key] = not str(reader_font.character_map.get(text, text)).strip()
        except Exception:
            memo[key] = False
    return memo[key]


def page_flags(data: bytes, index: int) -> tuple:
    """(an XObject the page draws, at any depth, carries /OC; the document has an XFA form; every Type3 font page
    1 can reach keeps its glyphs inside their boxes, `type3_ok`; page 1 can reach a Type3 font at all — a walk cut
    short says True), read with pypdf from the request's bytes ``data`` (moved here from `pdfium_worker` with
    no change, OCR-9 rebase: the worker was over the line limit). Fonts are reached through the page's resources
    and, at any depth, those of its form XObjects, tiling patterns and ExtGState /Font entries. Genuine cost: 0 of
    the 49 lockable letters (a document-level /OCProperties alone is NOT refused: every UUM letter carries one,
    with no optional content on page 1)."""
    import io
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        reader.decrypt('')
    acro = reader.trailer['/Root'].get_object().get('/AcroForm')
    xfa = bool(acro is not None and '/XFA' in acro.get_object())
    if _font_names_clash(reader.pages[index]):  # TD-740 r2 (Finding 4): counted as optional (refused)
        return True, xfa, False, True
    seen, todo, budget = set(), [(reader.pages[index].get('/Resources'), 0)], [T3_MAX_BYTES]
    t3_ok, t3_any = True, False

    def new(ref) -> bool:
        key = ('r', ref.idnum) if hasattr(ref, 'idnum') else ('o', id(ref))
        if key in seen:
            return False
        seen.add(key)
        return True
    while todo:
        res, depth = todo.pop()
        res = res.get_object() if res is not None else None
        if res is None and depth <= 15:          # no resources of its own: it can name no font, form or pattern
            continue
        if not hasattr(res, 'get') or depth > 15:
            # Fix round 3b: a walk cut short (too deep, or resources that are not a dictionary) may hide a Type3
            # font, so it counts as one that fails. Each resource is marked seen when first LISTED, not walked:
            # still safe, as every listed one is walked from that path or trips this same rule.
            t3_ok, t3_any = False, True
            continue
        if len(seen) >= 5000:
            return True, xfa, False, True        # past any genuine page: counted as optional (refused)
        # TD-740 r3 (Finding 2): every value compared or walked is resolved first (`_val`)
        fonts = _val(res, '/Font')
        fonts = list(fonts.values()) if fonts is not None else []
        states = _val(res, '/ExtGState')
        for gs in (states.values() if states is not None else ()):
            font = _val(gs.get_object(), '/Font')
            if font is not None and len(font) > 0:
                fonts.append(font[0])
        for ref in fonts:
            if not new(ref):
                continue
            font = ref.get_object()
            if _is_t3(font):
                t3_any = True
                t3_ok = t3_ok and type3_ok(font, budget)        # its glyphs draw no XObject or text: not walked
        patterns = _val(res, '/Pattern')
        for ref in (patterns.values() if patterns is not None else ()):
            if new(ref):
                pat = ref.get_object()
                if _val(pat, '/PatternType') == 1:
                    todo.append((_val(pat, '/Resources'), depth + 1))
        xobjects = _val(res, '/XObject')
        for ref in (xobjects.values() if xobjects is not None else ()):
            if not new(ref):
                continue
            xo = ref.get_object()
            if '/OC' in xo:
                return True, xfa, False, True    # refused as optional; the walk stops, so Type3 is unknown
            if _val(xo, '/Subtype') == '/Form' and not hasattr(_val(xo, '/Resources'), 'get') and '/Parent' in xo:
                return True, xfa, False, True    # TD-740 r2 (Finding 2): pypdf reads it through its /Parent's
                #                                  resources, pdfium through its caller's: refused the same way
            if _val(xo, '/Subtype') == '/Form':
                todo.append((_val(xo, '/Resources'), depth + 1))
    return False, xfa, t3_ok, t3_any


def _font_names_clash(page) -> bool:
    """TD-740 review round 2 (Finding 4): True when a /Pages node above ``page`` names a font in its /Resources that
    the page's own /Resources do not name as the very same object. pypdf's LAYOUT mode (`_layout_mode_fonts`) lays
    every ancestor's fonts OVER the page's, while pdfium and pypdf's plain read use the page's (probe
    pages_node_layout). A page with no /Resources of its own inherits them (pypdf copies them onto the page): no
    clash. Past 64 ancestors (a loop): True."""
    def fonts_of(node) -> dict:
        res = node.get('/Resources')
        res = res.get_object() if res is not None else None
        group = res.get('/Font') if hasattr(res, 'get') else None
        group = group.get_object() if group is not None else None
        return group if hasattr(group, 'items') else {}
    own = fonts_of(page)
    node = page.get('/Parent')
    for _ in range(64):
        node = node.get_object() if node is not None else None
        if not hasattr(node, 'get'):
            return False
        for name, ref in fonts_of(node).items():
            mine = own.get(name)
            if mine is None or mine.get_object() is not ref.get_object():
                return True
        node = node.get('/Parent')
    return True
