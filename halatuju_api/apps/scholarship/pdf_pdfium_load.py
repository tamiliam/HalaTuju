"""S-visible fix round 6 (2026-11-19): what pdfium LOADS with a page, judged BEFORE pdfium loads it — a WHITELIST.

pdfium parses a page's whole content when it loads the page, and with it each Type3 glyph procedure the text
uses — afresh for EVERY character code naming it. None of that was charged by the walk's budgets: a 670 KB file
of 120 Type3 glyphs, each inflating to 2.8 MB, took pdfium 13.5 s to load one page (one 2.8 MB glyph named by
256 codes, a 10 KB file: 9.7 s here). Font programs, ICC profiles and shading functions are inflated on load
too (60 MB each measured 0.05-0.2 s here), so their streams are charged as well. Six
review rounds each found one more place where our reading of a PDF and pdfium's differ, so this check no longer
lists what is bad. It allows ONLY the shapes the 533 real corpus PDFs use (measured 2026-11-19), with a little
headroom, and charges every stream pdfium may decode while loading to ONE byte budget per document, measured
without ever inflating past it. Anything else hides the page (the Vision route) before pdfium sees it.

Image data is not charged: a 400 MB (decoded) image loaded in 0.00 s — pdfium decodes it only when painting,
on the Vision route. Soft-mask forms and tiling cells also load in 0.00 s, but they are content pdfium may
parse, so their streams are charged and whitelisted like a form's.
"""
import re
import zlib

from .pdf_layer_guards import OverBudget, _get

#: Decompressed bytes of font programs, Type3 glyph procedures, forms, ICC profiles, Indexed tables, function
#: and pattern streams reachable from the judged pages of ONE document, a Type3 glyph once per code naming it.
#: Corpus max (533 PDFs, 2026-11-19): 1,158,420 (doc 871). pdfium parses glyphs at ~25 MB/s: 2.5 MB is ~0.1 s.
MAX_LOAD_BYTES = 2_500_000
#: One such stream. Corpus max: 422,708 (a TrueType font program).
MAX_LOAD_STREAM = 1_000_000
#: Resource entries visited per document (fonts, glyph uses, colour spaces, ...). Corpus max: 1,841 (doc 708).
MAX_LOAD_NODES = 4_000
#: Resource dictionaries nest (a form's, a Type3 font's, a pattern's); deeper is not a document page.
_MAX_DEPTH = 8

# ── The whitelist: every shape one of the 533 real PDFs uses (headroom marked +). ──
FONT_SUBTYPES = frozenset(('/Type1', '/TrueType', '/Type0', '/Type3'))
CID_SUBTYPES = frozenset(('/CIDFontType0', '/CIDFontType2'))
#: Font programs and their /Subtype (None: none expected). /FontFile (+) is a Type1 program.
FONT_FILES = {'/FontFile2': (None,), '/FontFile3': ('/Type1C', '/OpenType', '/CIDFontType0C'), '/FontFile': (None,)}
#: Colour-space families. /DeviceCMYK, /CalGray (+): no stream behind them. Separation, DeviceN, Lab: hidden.
COLOUR_SPACES = frozenset(('/DeviceGray', '/DeviceRGB', '/DeviceCMYK', '/CalRGB', '/CalGray', '/ICCBased',
                           '/Indexed', '/Pattern'))
PATTERN_TYPES = frozenset((1, 2))
#: Axial (2) and radial (3, +): no stream of their own. Function-based (1) and mesh (4-7) shadings: hidden.
SHADING_TYPES = frozenset((2, 3))
#: Exponential (2) and stitching (3). Sampled (0: a stream pdfium inflates on load) and PostScript (4): hidden.
FUNCTION_TYPES = frozenset((2, 3))
#: /D, /RI, /FL, /TK (+) are plain numbers or names. /Font, /TR, /BG, /UCR, /HT and anything else: hidden.
EXTGSTATE_KEYS = frozenset(('/Type', '/ca', '/CA', '/BM', '/SMask', '/SA', '/LC', '/LJ', '/LW', '/ML', '/AIS',
                            '/SM', '/OPM', '/OP', '/op', '/D', '/RI', '/FL', '/TK'))
SMASK_KEYS = frozenset(('/Type', '/S', '/G', '/BC'))
_INLINE_IMAGE = re.compile(rb'(?<![^\s\x00)\]>}])BI(?![^\s\x00/])')
#: A Type3 glyph procedure: numbers and path operators only — no name, string or array, so it can call no
#: resource (pdfium lends a glyph the PAGE's). The corpus's 4,366 glyphs (17 PDFs, at most 9,040 bytes each) use
#: d1 m l c h f re and nothing else; d0 v y f* n q Q cm W W* (+) draw nothing more.
GLYPH_OPS = frozenset(b'd0 d1 m l c v y h re f* f n q Q cm W* W'.split())
#: A Type3 font's /Encoding: the corpus's 140 are all a dictionary of /Type and /Differences (no /BaseEncoding).
TYPE3_ENCODING_KEYS = frozenset(('/Type', '/Differences'))
_PDF_SPACE = re.compile(rb'[\x00\t\n\x0c\r ]+')


def load_check(page, reader, state: dict) -> None:
    """Raise (the page is then hidden, never loaded by pdfium) when anything reachable from the page's resources
    is outside the whitelist, or the document's load budgets run out. ``state``: one per document."""
    from .pdf_pages import _resources
    if not state:
        state.update(bytes=MAX_LOAD_BYTES, nodes=MAX_LOAD_NODES, seen={}, sizes={})
    _resources_check(_resources(page), state, 0)


def _spend(state: dict, what: str, n: int) -> None:
    state[what] -= n
    if state[what] < 0:
        raise OverBudget(f'past the pdfium load {what} budget')


def _first_visit(obj, state: dict) -> bool:
    """True the first time ``obj`` is met in this document (pdfium loads a font or a stream once); each visit
    costs a node."""
    _spend(state, 'nodes', 1)
    if id(obj) in state['seen']:
        return False
    state['seen'][id(obj)] = obj                   # held, so its id cannot be reused during the check
    return True


def _stream(stream, state: dict, content: bool = False, every_use: bool = False) -> None:
    """Charge one stream's decompressed size, once per document — or on EVERY use (``every_use``: a Type3
    glyph procedure, which pdfium parses for each glyph name that points at it). Measured once, never inflating
    past what is left; only no filter or /FlateDecode is measured, any other filter is hidden. ``content``: a
    content stream (a form, a pattern cell), refused when it holds an inline image (pdfium inflates those
    while parsing, and the walk never reads a stream that is only in the resources)."""
    from pypdf.generic import StreamObject
    if not isinstance(stream, StreamObject):
        raise ValueError('not a stream')
    if not _first_visit(stream, state) and not every_use:
        return
    size = state['sizes'].get(id(stream))
    if size is None:
        data = _inflated(stream, min(MAX_LOAD_STREAM, max(0, state['bytes'])))
        if content and _INLINE_IMAGE.search(data):
            raise ValueError('an inline image in a stream the walk does not read')
        if every_use and not _is_glyph(data):
            raise ValueError('a glyph procedure outside the whitelist')
        size = state['sizes'][id(stream)] = len(data)
    _spend(state, 'bytes', size)


def _is_glyph(data: bytes) -> bool:
    """True when ``data`` is only numbers and `GLYPH_OPS` between PDF white-space (linear time: no regex
    backtracking over a long run of digits)."""
    for token in _PDF_SPACE.split(data):
        if not token or token in GLYPH_OPS:
            continue
        digits = token[1:] if token[:1] in (b'+', b'-') else token
        if digits.count(b'.') > 1 or not digits.replace(b'.', b'').isdigit():
            return False
    return True


def _inflated(stream, cap: int) -> bytes:
    """The stream's data, decoded only up to ``cap`` + 1 bytes (`OverBudget` past ``cap``)."""
    filters = _get(stream, '/Filter')
    filters = list(filters) if isinstance(filters, list) else [filters] if filters is not None else []
    if filters == ['/FlateDecode']:
        data = zlib.decompressobj().decompress(stream._data, cap + 1)
    elif not filters:
        data = stream.get_data()
    else:
        raise ValueError('a stream filter outside the whitelist')
    if len(data) > cap:
        raise OverBudget('a stream past the pdfium load budget')
    return data


def _resources_check(res, state: dict, depth: int) -> None:
    if res is None:
        return
    if not isinstance(res, dict) or depth > _MAX_DEPTH:
        raise ValueError('resources the check cannot follow')
    if not _first_visit(res, state):
        return
    for key, check in (('/Font', _font), ('/XObject', _xobject), ('/ExtGState', _extgstate),
                       ('/ColorSpace', _colour_space), ('/Pattern', _pattern), ('/Shading', _shading)):
        entries = _get(res, key)
        if entries is None:
            continue
        if not isinstance(entries, dict):
            raise ValueError('a resource category that is not a dictionary')
        for name in entries:
            check(_get(entries, name), state, depth)


def _font(font, state: dict, depth: int) -> None:
    if not isinstance(font, dict) or font.get('/Subtype') not in FONT_SUBTYPES:
        raise ValueError('a font outside the whitelist')
    if not _first_visit(font, state):
        return
    encoding = _get(font, '/Encoding')
    if hasattr(encoding, 'get_data') or not isinstance(encoding, (str, dict, type(None))):
        raise ValueError('an embedded encoding CMap')
    descriptors = [_get(font, '/FontDescriptor')]
    for d in _get(font, '/DescendantFonts') or ():
        d = d.get_object()
        if not isinstance(d, dict) or d.get('/Subtype') not in CID_SUBTYPES:
            raise ValueError('a descendant font outside the whitelist')
        descriptors.append(_get(d, '/FontDescriptor'))
        gid_map = _get(d, '/CIDToGIDMap')
        if gid_map is not None and gid_map != '/Identity':
            _stream(gid_map, state)
    for descriptor in descriptors:
        for key, subtypes in FONT_FILES.items():
            program = _get(descriptor, key)
            if program is None:
                continue
            if _get(program, '/Subtype') not in subtypes:
                raise ValueError('a font program outside the whitelist')
            _stream(program, state)
    if font.get('/Subtype') == '/Type3':
        _type3(font, encoding, state)


def _type3(font, encoding, state: dict) -> None:
    """pdfium parses a Type3 glyph's procedure afresh for EACH character code that names it, so each procedure
    is charged once per code in /Differences that names it (one 2.8 MB procedure named by 256 codes is 717 MB
    of parsing). Without a /BaseEncoding no other code reaches a procedure."""
    procs = _get(font, '/CharProcs')
    if (not isinstance(procs, dict) or '/Resources' in font or not isinstance(encoding, dict)
            or not set(encoding) <= TYPE3_ENCODING_KEYS):
        raise ValueError('a Type3 font outside the whitelist')
    differences = _get(encoding, '/Differences') or []
    if not isinstance(differences, list):
        raise ValueError('a Type3 encoding outside the whitelist')
    _spend(state, 'nodes', len(differences) // 16)
    for name in differences:
        name = name.get_object() if hasattr(name, 'get_object') else name
        if isinstance(name, str) and name in procs:
            _stream(_get(procs, name), state, every_use=True)


def _xobject(xobj, state: dict, depth: int) -> None:
    subtype = _get(xobj, '/Subtype')
    if subtype == '/Image':
        return                                     # image data is decoded when painted, not on load
    if subtype != '/Form':
        return                                     # pdfium paints nothing else (the walk hides its text)
    _stream(xobj, state, content=True)
    _resources_check(_get(xobj, '/Resources'), state, depth + 1)


def _extgstate(gs, state: dict, depth: int) -> None:
    if not isinstance(gs, dict) or not set(gs) <= EXTGSTATE_KEYS:
        raise ValueError('a graphics state outside the whitelist')
    smask = _get(gs, '/SMask')
    if isinstance(smask, dict):
        if not set(smask) <= SMASK_KEYS:
            raise ValueError('a soft mask outside the whitelist')
        _xobject(_get(smask, '/G'), state, depth)
    elif smask not in (None, '/None'):
        raise ValueError('a soft mask outside the whitelist')


def _colour_space(cs, state: dict, depth: int) -> None:
    family = cs if isinstance(cs, str) else cs[0].get_object() if isinstance(cs, list) and cs else None
    if family not in COLOUR_SPACES:
        raise ValueError('a colour space outside the whitelist')
    if not isinstance(cs, list) or depth > _MAX_DEPTH:
        return
    _spend(state, 'nodes', len(cs))
    if family == '/ICCBased':
        _stream(cs[1].get_object() if len(cs) > 1 else None, state)
    elif family == '/Indexed' and len(cs) == 4:
        _colour_space(cs[1].get_object(), state, depth + 1)
        lookup = cs[3].get_object()
        if not isinstance(lookup, (str, bytes)):
            _stream(lookup, state)
    elif family == '/Pattern' and len(cs) > 1:
        _colour_space(cs[1].get_object(), state, depth + 1)
    elif family in ('/Indexed', '/ICCBased'):
        raise ValueError('a colour space the check cannot follow')


def _pattern(pattern, state: dict, depth: int) -> None:
    kind = _get(pattern, '/PatternType')
    if kind not in PATTERN_TYPES:
        raise ValueError('a pattern outside the whitelist')
    if kind == 1:
        _xobject_like_cell(pattern, state, depth)
    else:
        _shading(_get(pattern, '/Shading'), state, depth)


def _xobject_like_cell(pattern, state: dict, depth: int) -> None:
    _stream(pattern, state, content=True)
    _resources_check(_get(pattern, '/Resources'), state, depth + 1)


def _shading(shading, state: dict, depth: int) -> None:
    if not isinstance(shading, dict) or _get(shading, '/ShadingType') not in SHADING_TYPES:
        raise ValueError('a shading outside the whitelist')
    if not _first_visit(shading, state):
        return
    _colour_space(_get(shading, '/ColorSpace'), state, depth)
    _function(_get(shading, '/Function'), state, depth)


def _function(fn, state: dict, depth: int) -> None:
    if depth > _MAX_DEPTH:
        raise ValueError('functions nested too deep')
    for f in fn if isinstance(fn, list) else (fn,):
        f = f.get_object() if f is not None else None
        _spend(state, 'nodes', 1)
        if not isinstance(f, dict) or hasattr(f, 'get_data') or _get(f, '/FunctionType') not in FUNCTION_TYPES:
            raise ValueError('a function outside the whitelist')
        if _get(f, '/FunctionType') == 3:
            _function(_get(f, '/Functions'), state, depth + 1)
