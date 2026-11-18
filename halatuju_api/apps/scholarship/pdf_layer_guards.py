"""S-visible fix round 4 (2026-11-19): what pypdf's text extraction reads that the content-stream walk in
``pdf_pages`` must also judge — operand counts, every font's maps, and optional content.

1. OPERAND COUNTS. pdfium (the renderer) takes an operator's LAST operands; the walk and pypdf take the
   FIRST. ``0 3 Tr`` is drawn to the walk and invisible on the page; ``/Fm1 /Fm2 Do`` is extracted from
   Fm1 and drawn from Fm2. Any operator whose operand count is not its fixed arity, and any text-showing
   operand of the wrong kind, makes the page hidden (`bad_operands`).
2. FONT MAPS. pypdf rebuilds the maps of EVERY font listed in the resources of each extraction call (a page,
   and each form on every call): /ToUnicode (up to 100,000 entries in 6.x, no cap in 5.9), /Encoding
   /Differences, /Widths over /FirstChar../LastChar, CID /W, and a Type1 font file when there is no
   /ToUnicode. `charge_fonts` charges each listed font's cost (`_font_cost`, worked out once per font) to
   the document budget per font NAME per call, BEFORE pypdf extracts anything.
3. OPTIONAL CONTENT. Text in a layer a viewer may switch off is not seen. When the document's default
   configuration switches anything off (or might: /BaseState not /ON, a non-empty /OFF or /AS), every
   ``/OC`` marked content and every form with an /OC entry hides its text; otherwise only a plain /OCG
   counts as shown (an /OCMD, or anything unresolvable, is hidden) — `oc_hides`.
"""

#: Fixed operand counts (ISO 32000 operator summary), for EVERY such operator — not one of the 533 corpus
#: PDFs breaks one. ``sc``/``scn`` (variable) and inline images are not here.
_ARITY = {op.encode(): n for n, ops in enumerate((
    'b B b* B* BT BX EMC ET EX f F f* h n q Q s S T* W W*',
    'BMC CS cs Do g G gs i j J M MP ri sh Tc TJ Tj TL Tr Ts Tw Tz w \'',
    'BDC d d0 DP l m Td TD Tf',
    'rg RG "',
    'k K re v y', '', 'c cm d1 Tm')) for op in ops.split()}

#: Font-map work per DOCUMENT, in units (a map entry, an array element, or 4 bytes of a stream read; pypdf
#: spends ~2-4 µs a unit). Real corpus max (533 PDFs, 2026-11-19): 792,972, one 12-call statement.
_MAX_DOC_FONT_COST = 1_200_000
#: One font past this is refused outright (pypdf 6 refuses a 100,000-entry /ToUnicode; 5.9 would try a
#: range of four billion). Also bounds the one-off scan `_font_cost` makes of each font. Real max: 66,175.
_MAX_FONT_COST = 200_000
#: Bytes of one font's /ToUnicode or font file read before its cost is known. Real max: 4,639.
_MAX_FONT_STREAM = 800_000
#: pypdf 5.9 walks a CID /W array by slicing (quadratic): one longer than this is refused. Real max: 198.
_MAX_W_ARRAY = 10_000


class OverBudget(Exception):
    """A PDF asked for more than one of the document budgets: hostile or broken, never read as text."""


def bad_operands(operator: bytes, operands) -> bool:
    """True when the operand count is not the operator's arity, or a text-showing operand is the wrong kind
    (pdfium shows only strings: a name or a bare string in TJ, or a non-string Tj, is not what it draws)."""
    n = _ARITY.get(operator)
    if n is None or len(operands) != n:
        return n is not None
    if operator not in (b'Tj', b"'", b'"', b'TJ', b'Do'):
        return False
    from pypdf.generic import NameObject
    if operator in (b'Tj', b"'", b'"'):
        s = operands[-1]
        return not isinstance(s, (str, bytes)) or isinstance(s, NameObject)
    if operator == b'TJ':
        arr = operands[0]
        return not isinstance(arr, list) or any(
            isinstance(x, NameObject) or not isinstance(x, (str, bytes, int, float)) for x in arr)
    return operator == b'Do' and not isinstance(operands[0], NameObject)


def _get(obj, key):
    v = obj.get(key) if isinstance(obj, dict) else None
    return v.get_object() if v is not None else None


def _stream_data(stream) -> bytes:
    from pypdf.generic import StreamObject
    if not isinstance(stream, StreamObject):
        return b''
    length = stream.get('/Length')
    if isinstance(length, int) and length > _MAX_FONT_STREAM:
        raise OverBudget('a font stream past the size limit')
    data = stream.get_data()
    if len(data) > _MAX_FONT_STREAM:
        raise OverBudget('a font stream past the size limit')
    return data if isinstance(data, bytes) else data.encode('latin-1', 'replace')


def _cmap_entries(font) -> int:
    """The entries pypdf adds from a /ToUnicode: its own ``prepare_cm`` (both versions), then its line rules
    counted instead of built — bfchar pairs, bfrange spans (``<lo> <hi> <dst>``) and array elements."""
    from pypdf._cmap import prepare_cm
    n, in_range, in_char, multi = 0, False, False, False
    for line in prepare_cm(font).split(b'\n'):
        line = line.strip(b' \t').replace(b'\t', b' ')
        if not line or line[0] == 37:
            continue
        if b'beginbfrange' in line:
            in_range = True
        elif b'endbfrange' in line:
            in_range = False
        elif b'beginbfchar' in line:
            in_char = True
        elif b'endbfchar' in line:
            in_char = False
        elif in_range:
            lst = line.split()
            if multi or (len(lst) > 2 and lst[2] == b'['):
                items = lst if multi else lst[3:]
                closed = b']' in items
                n += items.index(b']') if closed else len(items)
                multi = not closed
                continue
            try:
                n += max(0, int(lst[1], 16) - int(lst[0], 16) + 1) if len(lst) > 2 else 0
            except ValueError:
                pass
        elif in_char:
            n += len(line.split()) // 2
        if n > _MAX_FONT_COST:
            break
    return n


def _font_cost(font) -> int:
    """An upper bound on the work pypdf (5.9 and 6.21.4) does building ONE font's maps. Raises past the
    per-font limits (the caller then treats the page as hidden)."""
    from pypdf.generic import StreamObject
    cost = 256                                                  # the base one-byte encoding table
    to_unicode = _get(font, '/ToUnicode')
    if isinstance(to_unicode, StreamObject):
        cost += len(_stream_data(to_unicode)) // 4
        if cost > _MAX_FONT_COST:                               # before the stream is scanned
            raise OverBudget('a font past the size limit')
        cost += _cmap_entries(font)
    elif to_unicode is None and font.get('/Subtype') == '/Type1':      # 6.x reads the embedded font file
        descriptor = _get(font, '/FontDescriptor')
        cost += sum(len(_stream_data(_get(descriptor, k))) // 4 for k in ('/FontFile', '/FontFile3'))
    for arr in (_get(_get(font, '/Encoding'), '/Differences'), _get(font, '/Widths'), _get(font, '/CharProcs')):
        cost += len(arr) if isinstance(arr, (list, dict)) else 0
    first, last = _get(font, '/FirstChar'), _get(font, '/LastChar')
    if isinstance(first, int) and isinstance(last, int):
        cost += max(0, last - first + 1)                        # 5.9 loops FirstChar..LastChar
    descendants = _get(font, '/DescendantFonts')
    for d in descendants if isinstance(descendants, list) else ():
        widths = _get(d.get_object(), '/W')
        if not isinstance(widths, list):
            continue
        if len(widths) > _MAX_W_ARRAY:
            raise OverBudget('a CID width array past the size limit')
        cost += len(widths) + _w_span(widths)
    if cost > _MAX_FONT_COST:
        raise OverBudget('a font past the size limit')
    return cost


def _w_span(widths) -> int:
    """Characters a CID /W array names: ``c [w ...]`` gives len, ``c1 c2 w`` gives c2 - c1 + 1."""
    n, i = 0, 0
    while i + 1 < len(widths):
        a, b = widths[i].get_object(), widths[i + 1].get_object()
        if isinstance(b, list):
            n, i = n + len(b), i + 2
        elif isinstance(a, int) and isinstance(b, int):
            n, i = n + max(0, b - a + 1), i + 3
        else:
            i += 1
        if n > _MAX_FONT_COST:
            break
    return n


def charge_fonts(resources, budget, cache: dict) -> None:
    """Charge the document ``budget`` for one extraction call over ``resources``: every font NAME listed
    costs its font's `_font_cost` (each font worked out once per document, held in ``cache``)."""
    fonts = _get(resources, '/Font')
    if not isinstance(fonts, dict):
        return
    for name in fonts:
        font = fonts[name].get_object() if fonts[name] is not None else None
        if not isinstance(font, dict):
            budget.spend('font maps', 256)
            continue
        hit = cache.get(('font', id(font)))
        if hit is None:
            budget.spend('font maps', 256)             # a font is never free to look at
            hit = cache[('font', id(font))] = (font, _font_cost(font))
        budget.spend('font maps', hit[1])


def _doc_may_switch_off(reader) -> bool:
    """True when the default optional-content configuration switches (or may switch) a layer off."""
    try:
        props = _get(reader.trailer['/Root'].get_object(), '/OCProperties')
    except KeyError:
        return False
    if props is None:
        return False
    default = _get(props, '/D')
    if not isinstance(default, dict):
        return True
    off, auto = _get(default, '/OFF'), _get(default, '/AS')
    return (_get(default, '/BaseState') not in (None, '/ON') or not isinstance(off, (list, type(None)))
            or bool(off) or bool(auto))


def oc_hides(prop, resources, reader, cache: dict) -> bool:
    """True when optional content ``prop`` (a ``/OC`` BDC's property — a name in /Properties or a dict — or
    a form's /OC entry) may hide what it marks; False only for a plain /OCG in a document that switches
    nothing off. Anything else, or anything that cannot be resolved, hides."""
    if 'oc doc' not in cache:
        cache['oc doc'] = _doc_may_switch_off(reader)
    if cache['oc doc']:
        return True
    if isinstance(prop, str):
        prop = _get(_get(resources, '/Properties'), prop)
    elif prop is not None:
        prop = prop.get_object()
    return not (isinstance(prop, dict) and prop.get('/Type') == '/OCG')
