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
Fix round 5: 4. RAW TOKENS (`raw_state_check`): a Tr operand must be written as a clean 0-7 (pypdf reads
   ``3-0`` as 0, pdfium as 3) and no resource name may decode to a byte under 0x10 (a bad ``#`` escape);
   any inline image hides the page (the two read its data to different lengths). An /OCG with a /Usage
   (or any key but /Type and /Name) is never provably shown (pdfium hides ``/ViewState /OFF``).
Fix round 6: 3 became a WHITELIST (`_doc_may_switch_off`). The layers count as all ON only when /OCProperties
   holds just the keys the corpus uses (/OCGs, /D: no /Configs, which pdfium may pick for viewing), /D just
   /ON /OFF /Order /RBGroups /BaseState, /BaseState absent or /ON, /OFF empty, no /AS, and every OCG only
   /Type and /Name. Anything else makes all OC-marked text and every OC form hidden.
"""
import re

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


_BARE = rb'[^\x00\t\n\x0c\r ()<>\[\]{}/%]'
_TR_OP = re.compile(rb'(?<!' + _BARE + rb')Tr(?!' + _BARE + rb')')
_CLEAN_TR = re.compile(rb'(?<!' + _BARE + rb')[0-7][\x00\t\n\x0c\r ]+Tr(?!' + _BARE + rb')')
#: Operators whose name operand picks a resource or a layer. pypdf 6 reads a malformed ``#`` escape in a name
#: (``#+4``, a lone ``#4``) as one byte under 0x10 where pdfium keeps the ``#``: the two look up different keys.
_NAMED_OPS = frozenset((b'Do', b'Tf', b'BDC', b'BMC', b'gs'))


def raw_state_check(data: bytes, inline_images: int) -> None:
    """Raise (the page is then hidden) when a content stream's raw bytes hold state pypdf and pdfium may read
    differently: a ``Tr`` not preceded by a clean single digit 0-7 (also counts ``Tr`` inside strings: safe),
    or any inline image. Not one of the 533 corpus PDFs has either."""
    if inline_images:
        raise ValueError('an inline image')
    if len(_TR_OP.findall(data)) != len(_CLEAN_TR.findall(data)):
        raise ValueError('a Tr operand that is not a clean 0-7')


def bad_operands(operator: bytes, operands) -> bool:
    """True when the operand count is not the operator's arity, or a text-showing operand is the wrong kind
    (pdfium shows only strings: a name or a bare string in TJ, or a non-string Tj, is not what it draws)."""
    n = _ARITY.get(operator)
    if n is None or len(operands) != n:
        return n is not None
    from pypdf.generic import NameObject
    if operator in _NAMED_OPS and any(isinstance(x, NameObject) and min(x) < '\x10' for x in operands):
        return True                              # a name pypdf and pdfium may decode differently
    if operator not in (b'Tj', b"'", b'"', b'TJ', b'Do'):
        return False
    if operator in (b'Tj', b"'", b'"'):
        s = operands[-1]
        return not isinstance(s, (str, bytes)) or isinstance(s, NameObject)
    if operator == b'TJ':
        arr = operands[0]
        return not isinstance(arr, list) or any(
            isinstance(x, NameObject) or not isinstance(x, (str, bytes, int, float)) for x in arr)
    return operator == b'Do' and not isinstance(operands[0], NameObject)


#: Pages a PDF may have for its text layer to be read (fix round 5): a longer one is the Vision route, its
#: page tree never flattened (99,000 pages took pypdf 3.5 s). Corpus max: 5.
MAX_PDF_PAGES = 500
#: Objects packed in object streams (the sum of their /N) a PDF may hold: pypdf 6 parses a WHOLE object stream
#: the first time any one object in it is read (99,000 page nodes: 2.5 s), 5.9 scans it per object. Checked
#: before any object is read. Corpus max (533 PDFs): 507 listed in the cross-reference; 792 objects in all.
MAX_PACKED_OBJECTS = 20_000


def _packed_objects_check(reader) -> None:
    """Raise `OverBudget` when the object streams the cross-reference names declare more than
    `MAX_PACKED_OBJECTS` objects between them (pypdf reads each stream's /N objects)."""
    from pypdf.generic import IndirectObject
    streams = {num for num, _ in reader.xref_objStm.values()}
    if len(streams) > MAX_PACKED_OBJECTS:
        raise OverBudget('object streams past the cap')
    total = 0
    for num in streams:
        if num in reader.xref_objStm:
            raise ValueError('an object stream inside an object stream')
        n = _get(IndirectObject(num, 0, reader).get_object(), '/N')
        total += n if isinstance(n, int) and n > 0 else 0
        if total > MAX_PACKED_OBJECTS:
            raise OverBudget('objects in object streams past the cap')


def page_tree_check(reader) -> None:
    """Before pypdf flattens the page tree: raise `OverBudget` when the object streams hold too many objects
    (`_packed_objects_check`), when /Root /Pages /Count is not an integer up to `MAX_PDF_PAGES` or the /Kids
    tree holds more than twice that many nodes (a /Count may lie), and ValueError on a node met twice. Walks
    the nodes the way pypdf's ``_flatten`` does (/Type, else /Kids)."""
    _packed_objects_check(reader)
    pages = _get(reader.trailer['/Root'].get_object(), '/Pages')
    count = _get(pages, '/Count')
    if not isinstance(count, int) or not 0 < count <= MAX_PDF_PAGES:
        raise OverBudget('a page count past the cap')
    seen, todo, nodes = set(), [pages], 0
    while todo:
        ref = todo.pop()
        key = (ref.idnum, ref.generation) if hasattr(ref, 'idnum') else id(ref)
        node = ref.get_object() if ref is not None else None
        if key in seen:
            raise ValueError('a page tree that meets one node twice')
        seen.add(key)
        nodes += 1
        if nodes > 2 * MAX_PDF_PAGES:
            raise OverBudget('a page tree past the node cap')
        kind = node.get('/Type') if isinstance(node, dict) else None
        if isinstance(node, dict) and (kind == '/Pages' or (kind is None and '/Kids' in node)):
            kids = _get(node, '/Kids')
            todo.extend(kids if isinstance(kids, list) else ())


_PAREN = re.compile(rb'[()\\]')


def longest_literal(data: bytes) -> int:
    """An upper bound on the longest ``( ... )`` string (nested parentheses, backslash escapes)."""
    longest = depth = start = 0
    skip = -1
    for m in _PAREN.finditer(data):
        i = m.start()
        if i == skip:
            continue
        if data[i] == 92:
            skip = i + 1
        elif data[i] == 40:
            start = i if not depth else start
            depth += 1
        elif depth:
            depth -= 1
            longest = longest if depth else max(longest, i - start)
    return max(longest, len(data) - start if depth else 0)


def shown_chars(operands) -> int:
    """EVERY character handed to a text-showing operator: each string operand and each string in an array
    operand, blanks included. A superset of what pypdf extracts (operands[0] of Tj and ', operands[2] of ",
    every string of a TJ array; 5.9 also reads a TJ string operand). A font's Encoding / ToUnicode can map ANY
    byte, a space too, to a letter, so no string is too blank to carry hidden text."""
    n = 0
    for o in operands:
        for s in (o if isinstance(o, list) else (o,)):
            if isinstance(s, (str, bytes)):
                n += len(s)
    return n


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


#: Fix round 6 — a WHITELIST. pdfium takes the layer state from /Configs (an entry with /Intent /View) as well as
#: /D, so a blacklist of /D's switches missed it. Optional content is "provably all ON" only in the exact shape
#: the corpus uses (11 of 533 PDFs carry /OCProperties, measured 2026-11-19): /OCProperties keys, /D keys (the
#: corpus has /ON, /OFF — always empty —, /Order, /RBGroups, and /AS only beside a /Usage), /BaseState only
#: /ON (+), and every listed /OCG plain (`PLAIN_OCG_KEYS`). No /Configs, /AS, /Intent, /Locked: never shown.
OC_PROPERTIES_KEYS = frozenset(('/OCGs', '/D'))
OC_DEFAULT_KEYS = frozenset(('/ON', '/OFF', '/Order', '/RBGroups', '/BaseState'))
_MAX_OCGS = 1_000


def _doc_may_switch_off(reader) -> bool:
    """False only when the document has no optional content, or its configuration is provably all ON (the
    whitelist above); True for anything else (pdfium may then hide a layer pypdf reads)."""
    try:
        root = reader.trailer['/Root'].get_object()
    except KeyError:
        return False
    props = _get(root, '/OCProperties')
    if props is None:
        return False
    default = _get(props, '/D')
    if not (isinstance(props, dict) and set(props) <= OC_PROPERTIES_KEYS and isinstance(default, dict)
            and set(default) <= OC_DEFAULT_KEYS and _get(default, '/BaseState') in (None, '/ON')):
        return True
    off, ocgs = _get(default, '/OFF'), _get(props, '/OCGs')
    if not (off is None or (isinstance(off, list) and not off)) or not isinstance(ocgs, list) or len(ocgs) > _MAX_OCGS:
        return True
    return not all(isinstance(o, dict) and o.get('/Type') == '/OCG' and set(o) <= PLAIN_OCG_KEYS
                   for o in (x.get_object() if x is not None else None for x in ocgs))


def oc_hides(prop, resources, reader, cache: dict) -> bool:
    """True when optional content ``prop`` (a ``/OC`` BDC's property — a name in /Properties or a dict — or
    a form's /OC entry) may hide what it marks; False only for a plain /OCG (no key but /Type and /Name: a
    /Usage may hide it even with no /OCProperties) in a document that switches nothing off. Anything else,
    or anything that cannot be resolved, hides."""
    if 'oc doc' not in cache:
        cache['oc doc'] = _doc_may_switch_off(reader)
    if cache['oc doc']:
        return True
    if isinstance(prop, str):
        prop = _get(_get(resources, '/Properties'), prop)
    elif prop is not None:
        prop = prop.get_object()
    return not (isinstance(prop, dict) and prop.get('/Type') == '/OCG' and set(prop) <= PLAIN_OCG_KEYS)


#: The only keys a provably shown /OCG may carry (pdfium's mark parameters use the same names, unslashed).
PLAIN_OCG_KEYS = frozenset(('/Type', '/Name'))
