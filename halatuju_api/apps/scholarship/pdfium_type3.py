"""The Type3 glyph rules for the pdfium child (moved out of `pdfium_worker`, which was over the line limit).

Pure Python plus pypdf (imported inside the function): no pdfium. `pdfium_worker` re-exports `T3_TOLERANCE`,
`T3_MAX_BYTES` and `_type3_ok`, and loads this file by path when it runs as a script. `page_flags` (the ink op's
pypdf flags) lives here too since the OCR-9 rebase.
"""

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
    procs = font.get('/CharProcs')
    procs = procs.get_object() if procs is not None else None
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


#: TD-740 review round 1: the most bytes of page content (the page's and its forms') `shown_ok` reads.
SHOWN_MAX_BYTES = 16_000_000


def shown_ok(data: bytes, index: int) -> bool:
    """TD-740 review round 1 (pdfium child, `pdfium_worker._paints`): True when every character page ``index``
    shows in a Type3 font has a glyph that keeps its ink inside its ``d1`` box (`_glyph_ok`, the `type3_ok` rules)
    and paints, or (a glyph that paints nothing, or none) is one pypdf reads as blank (a space). pdfium boxes a
    Type3 character by its glyph's ``d1`` box, not its ink: a box that holds the ink is where `pdfium_place.outside`
    judges the ink to be, but a box the ink leaves (probes t3_d1_lie_*, t3_cm_ink_offpage), or an empty or missing
    glyph (t3_onpage_empty), places a box on the page while pypdf still reads a letter drawn elsewhere or nowhere.
    Only the glyphs shown are judged (a font listed in shared resources but not shown costs nothing). Read with pypdf from the request's bytes, walking the page's
    content and its forms (``Do``) as the text state flows: a ``Tf`` name is looked up in EVERY enclosing resource
    dictionary (pdfium lends a form the page's), and each Type3 font found is checked. Fails closed: a walk past
    15 forms deep or `SHOWN_MAX_BYTES`, or anything pypdf cannot parse, is False."""
    import io
    from pypdf import PdfReader
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            reader.decrypt('')
        page = reader.pages[index]
        return _shown_walk(reader, page.get('/Contents'), [page.get('/Resources')], (), [SHOWN_MAX_BYTES], {}, set())
    except MemoryError:
        raise
    except Exception:
        return False


def _shown_walk(reader, contents, chain: list, fonts: tuple, budget: list, tables: dict, done: set) -> bool:
    """`shown_ok` over one content stream (``chain``: its resource dictionaries, innermost first; ``fonts``: the
    font candidates the text state carries in)."""
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
            codes = b''.join(_strings(args))
            if not all(_codes_ok(f, codes, tables, budget) for f in fonts):
                return False
        elif name == 'Do' and args:
            for xo in _in_resources(chain, '/XObject', args[0]):
                if xo.get('/Subtype') != '/Form':
                    continue
                key = (id(xo), tuple(id(f) for f in fonts))
                if key in done:                    # this form with this text state: already walked
                    continue
                done.add(key)
                if not _shown_walk(reader, xo, [xo.get('/Resources')] + chain, fonts, budget, tables, done):
                    return False
    return True


def _in_resources(chain: list, kind: str, name) -> list:
    """Every object named ``name`` under ``kind`` in any resource dictionary of ``chain``."""
    found = []
    for res in chain:
        res = res.get_object() if res is not None else None
        group = res.get(kind) if hasattr(res, 'get') else None
        group = group.get_object() if group is not None else None
        obj = group.get(name) if hasattr(group, 'get') else None
        if obj is not None:
            found.append(obj.get_object())
    return found


def _strings(args):
    """Every string operand of a show-text operator, inside a TJ array too."""
    for arg in args:
        if isinstance(arg, list):
            yield from _strings(arg)
        elif isinstance(arg, (bytes, str)):
            yield arg if isinstance(arg, bytes) else arg.encode('latin-1', 'replace')


def _codes_ok(font, codes: bytes, tables: dict, budget: list) -> bool:
    """True unless ``font`` is a Type3 font one of whose ``codes`` is bad (`_bad_codes`)."""
    if not hasattr(font, 'get') or font.get('/Subtype') != '/Type3':
        return True
    if id(font) not in tables:
        tables[id(font)] = _bad_codes(font, budget)
    bad = tables[id(font)]
    return not any(c in bad for c in codes)


def _bad_codes(font, budget: list) -> frozenset:
    """The codes of a Type3 font whose glyph breaks `_glyph_ok` (its ink may leave its d1 box), or is missing or
    paints nothing (a d0 glyph, a d1 box of no area, or no filled path) while pypdf reads the code as something
    other than whitespace (its own decoding: `Font.encoding`, then the ToUnicode map). Every code (0-255) when a
    glyph procedure is past ``budget`` or cannot be parsed."""
    from pypdf.generic import ContentStream
    from pypdf.generic._font import Font
    reader_font = Font.from_font_resource(font)
    enc = font.get('/Encoding')
    enc = enc.get_object() if enc is not None else None
    diffs = enc.get('/Differences') if hasattr(enc, 'get') else None
    names, code = {}, 0
    for item in (diffs.get_object() if diffs is not None else ()):
        item = item.get_object() if hasattr(item, 'get_object') else item
        if isinstance(item, (int, float)) and not isinstance(item, bool):
            code = int(item)
        else:
            names[code], code = str(item), code + 1
    procs = font.get('/CharProcs')
    procs = procs.get_object() if procs is not None else {}
    blank, parsed = set(), {}
    for c in range(256):
        proc = procs.get(names[c]) if c in names and hasattr(procs, 'get') else None
        if proc is not None:
            if names[c] not in parsed:
                proc = proc.get_object()
                budget[0] -= len(proc.get_data())
                if budget[0] < 0:
                    return frozenset(range(256))
                parsed[names[c]] = [(a, _op_name(o)) for a, o in ContentStream(proc, None, 'bytes').operations]
            ops = parsed[names[c]]
            if not _glyph_ok(ops):
                blank.add(c)
                continue
            if ops and ops[0][1] == 'd1' and len(ops[0][0]) == 6:
                llx, lly, urx, ury = (float(v) for v in ops[0][0][2:])
                if (urx != llx and ury != lly and any(n in _T3_PATH or n == 're' for _a, n in ops)
                        and any(n in _T3_FILL_OPS for _a, n in ops)):
                    continue                        # it paints (inside its box: `type3_ok`)
        enc_map = reader_font.encoding
        text = (bytes([c]).decode(enc_map, 'replace') if isinstance(enc_map, str) else enc_map.get(c, chr(c)))
        text = reader_font.character_map.get(text, text)
        if str(text).strip():
            blank.add(c)
    return frozenset(blank)


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
        fonts = res.get('/Font')
        fonts = list(fonts.get_object().values()) if fonts is not None else []
        states = res.get('/ExtGState')
        for gs in (states.get_object().values() if states is not None else ()):
            font = gs.get_object().get('/Font')
            font = font.get_object() if font is not None else None
            if font is not None and len(font) > 0:
                fonts.append(font[0])
        for ref in fonts:
            if not new(ref):
                continue
            font = ref.get_object()
            if hasattr(font, 'get') and font.get('/Subtype') == '/Type3':
                t3_any = True
                t3_ok = t3_ok and type3_ok(font, budget)        # its glyphs draw no XObject or text: not walked
        patterns = res.get('/Pattern')
        for ref in (patterns.get_object().values() if patterns is not None else ()):
            if new(ref):
                pat = ref.get_object()
                if hasattr(pat, 'get') and pat.get('/PatternType') == 1:
                    todo.append((pat.get('/Resources'), depth + 1))
        xobjects = res.get('/XObject')
        for ref in (xobjects.get_object().values() if xobjects is not None else ()):
            if not new(ref):
                continue
            xo = ref.get_object()
            if '/OC' in xo:
                return True, xfa, False, True    # refused as optional; the walk stops, so Type3 is unknown
            if xo.get('/Subtype') == '/Form':
                todo.append((xo.get('/Resources'), depth + 1))
    return False, xfa, t3_ok, t3_any
