"""Reading a PDF upload's pages — the text layer (pypdf) and page 1 as a PNG (pypdfium2).

Moved out of ``vision.py`` on 2026-10-02 (that file sits at its size ceiling); ``vision.py``
imports both helpers under their old private names, so every call site and ``patch()`` target
is unchanged.

⚠ THE PIXEL BUDGET (2026-10-02). Page 1 used to be rendered at 200 DPI with no bound on the
page's size. One 2 MB scan-to-PDF salary slip carries a page box so large that the render asked
for more than 2 GiB, and the hourly stuck-read sweep killed the api instance three hours running
(Cloud Run "Memory limit of 2048 MiB exceeded"). A raster now never exceeds
``MAX_RASTER_SIDE_PX`` on its longer side (an A4 page still gets the full 200 DPI: 1654×2339),
and a page box past ``MAX_PAGE_SIDE_PT`` is refused outright rather than rendered.
"""
import hashlib
import io
import logging
import re
import threading
from collections import OrderedDict
from typing import NamedTuple, Optional

from . import pdf_pdfium_check
from .pdfium_lock import pdfium_document
from .pdf_layer_guards import (_MAX_DOC_FONT_COST, OverBudget as _OverBudget, _doc_may_switch_off, bad_operands,
                               charge_fonts, longest_literal, oc_hides, page_tree_check, raw_state_check, shown_chars)

logger = logging.getLogger(__name__)

#: A PDF's text layer is trusted (read for free, no Vision call) only when at least this many
#: characters of REAL text survive `usable_text_layer`. vision.py reads it as ``_MIN_PDF_TEXT``.
MIN_TEXT_LAYER_CHARS = 25
#: A layer holding at least this many ordinary words (3+ letters) is never judged letter-spaced.
MIN_REAL_WORDS = 30

# ── TD-411 (2026-10-28): is this text layer the document, or only a scanner app's stamp? ─────────
# A phone scanner app (CamScanner above all) writes its OWN name into the text layer of a scanned PDF
# and nothing else: doc 3281, a real KWSP Penyata Ahli, had the 46-character layer "CamScanner" × 4, so
# it was "read" as that word, the Vision read never ran and every scorer saw nothing. The check below
# decides what is document text; a layer that fails it is treated as no layer, so the page image goes
# to Vision exactly as a scan with an empty layer always has. Every doc type that reads a PDF is served.
_SCANNER_APPS = (r'cam\s?scanner|adobe\s+scan|microsoft\s+lens|office\s+lens|genius\s+scan|'
                 r'tap\s?scanner|clear\s?scan(?:ner)?|tiny\s?scanner|simple\s?scan(?:ner)?|'
                 r'scanner\s+pro|notebloc|vflat|turboscan')
#: A NAMED app, alone or as "Scanned with / by / using <app>" (word-bounded). Only these are stamps:
#: "Scanned by Pegawai Kewangan" names a person, not an app, and stays.
_SCANNER_STAMP = re.compile(
    rf'\b(?:(?:scanned|digiti[sz]ed|created|made)\s+(?:with|by|using)\s+)?(?:{_SCANNER_APPS})\b', re.I)
#: pypdf's placeholder for a glyph it cannot map back to a character (a subset-encoded font).
_CID = re.compile(r'\(cid:\d+\)')


def _stamp_only(line: str) -> bool:
    """True for a line that is ONLY a scanner-app stamp: once the named stamp(s) are taken out, nothing
    but whitespace / punctuation is left. A stamp word inside a content line ("Simple Scan Enterprise
    Sdn Bhd") makes it a content line, kept whole."""
    return bool(_SCANNER_STAMP.search(line)) and not any(c.isalnum() for c in _SCANNER_STAMP.sub('', line))


def _without_scanner_stamp(text: str) -> str:
    """The text layer minus every line that is only a scanner-app stamp (`_stamp_only`). No stamp word is
    ever cut out of a content line. A layer with no stamp-only line comes back BYTE-FOR-BYTE as it was: it
    is split on '\\n' only (``splitlines`` would also break on the control characters a garbled layer
    carries, and the parsers that read such a layer must see what they saw)."""
    text = text or ''
    lines = text.split('\n')
    kept = [ln for ln in lines if not _stamp_only(ln)]
    return text if len(kept) == len(lines) else '\n'.join(kept).strip()


def _looks_like_text(text: str) -> bool:
    """False for a layer that is not readable document text: dominated by ``(cid:NN)`` glyph codes, with
    under a quarter of its visible characters letters or digits, or letter-spaced ("K W S P P E N Y A T A").

    The floors are deliberately LOW (calibrated 2026-10-28 on the 169 eval PDFs that carry a layer): a real
    payslip with dot leaders sits at 0.42 letters-or-digits and a half-garbled STPM layer that the STPM
    parser reads today at 0.42 too — both keep their layer; every other real one is 0.78 or more. The
    highest single-letter share of any real layer is 0.20 (grades "A", "B" on a results slip)."""
    cid_chars = sum(len(m) for m in _CID.findall(text))
    rest = _CID.sub('', text)
    visible = [c for c in rest if not c.isspace()]
    if cid_chars >= len(visible):
        return False
    if sum(c.isalnum() for c in visible) < 0.25 * len(visible):
        return False
    words = [w for w in rest.split() if w.isalpha()]
    # Letter-spaced only when it is ALL the layer holds: a Canva-style CV/statement spaces its headings
    # ("S K I L L S", doc 3919: 82% single letters) around paragraphs of real prose that must be kept.
    real_words = sum(len(w) >= 3 for w in words)
    return not (len(words) >= 10 and sum(len(w) == 1 for w in words) > 0.6 * len(words)
                and real_words < MIN_REAL_WORDS)


def usable_text_layer(text: str) -> str:
    """The text layer to read in place of a Vision call, or '' when it is not real document text.

    A stamp-ONLY line is REMOVED from what is returned (not merely ignored): it is not part of the
    document, it can never be a signature, and leaving it in would put "CamScanner" into every name
    and label match downstream. A real digital PDF carries no stamp, so its layer comes back unchanged;
    a real layer that merely carries a "Scanned with CamScanner" footer line keeps all its own text. What is
    left must then look like text (`_looks_like_text`) and hold `MIN_TEXT_LAYER_CHARS` characters."""
    cleaned = _without_scanner_stamp(text)
    if len(cleaned) < MIN_TEXT_LAYER_CHARS or not _looks_like_text(cleaned):
        return ''
    return cleaned


RASTER_DPI = 200
#: Longest side of a rendered page, in pixels. 4,000 px square is 16 MP — 64 MB as RGBA, far
#: under the instance's 2 GiB — and A3 at 200 DPI (3308 px) still renders at full resolution.
MAX_RASTER_SIDE_PX = 4000
#: A page side past this (in PDF points; 20,000 pt is about 7 metres) is not a document page.
MAX_PAGE_SIDE_PT = 20000


def raster_scale(width_pt: float, height_pt: float) -> Optional[float]:
    """The render scale for a page of this size: 200 DPI, shrunk so the longer side stays within
    ``MAX_RASTER_SIDE_PX``. None for a page box that is empty or absurd — the caller refuses it."""
    longer = max(width_pt, height_pt)
    if not (width_pt > 0 and height_pt > 0) or longer > MAX_PAGE_SIDE_PT:
        return None
    return min(RASTER_DPI / 72.0, MAX_RASTER_SIDE_PX / longer)


# ── S-visible (owner decision 2026-11-18, "what we see is what we can defend") ───────────────────────
# A phone scanner app's PDF is a PHOTO of the page plus an INVISIBLE text layer from the app's own OCR
# (PDF text render mode 3: the glyphs are placed but never painted). That layer often misses the
# letterhead and key lines, so it is not what the page shows. A page whose text is invisible is treated
# as a picture: it has NO text layer here, so every reader rasterises it and Cloud Vision reads it —
# the route a scanned PDF with no layer has always taken. Text that is drawn (a bank e-statement, an
# official downloaded PDF) is what we see and keeps being read for free. Detection that fails counts as
# invisible (the Vision route: safe, one call), never as the hidden text.
#
# ONE SOURCE OF TRUTH (fix round 2, 2026-11-19): `_layer_read` walks a PDF ONCE — the first
# `MAX_LAYER_PAGES` pages, one operation budget for the whole document, stopping as soon as page 1 is
# not drawn — and extracts the drawn pages ONCE; `first_page_drawn`, `pdf_text_layer` and
# `pdf_page_texts` all answer from that one result, memoised per upload (`_LAYER_MEMO`).
#
# MIRRORS pypdf's plain `extract_text` (read in 5.9.0 and 6.21.4, fix round 3): text comes ONLY from the page's
# /Contents and from every XObject a `Do` names that is not an /Image (resources inherited up /Parent), out of
# the string operands of Tj, ', " and TJ. Annotations, Type3 CharProcs, ActualText, patterns: never extracted.
# Fix round 4 (`pdf_layer_guards`): exact operand counts, every font's maps charged, optional content judged.
#: Text render modes that paint: 0-2 and 4-6. 3 (invisible), 7 (clip only) and any other value hide the text.
_DRAWN_MODES = frozenset((0, 1, 2, 4, 5, 6))
_SHOW_OPS = frozenset((b'Tj', b'TJ', b"'", b'"'))
#: Form XObjects nest; deeper than this is not a document page (and a cycle must end).
_MAX_FORM_DEPTH = 8
#: A /Parent chain longer than this (pypdf inherits /Resources up it) is broken or hostile.
_MAX_PARENT_DEPTH = 64
#: Content-stream operations walked per DOCUMENT: EVERY operation, each time it is walked — a page's own
#: stream once per page (pages may share one stream) and a form's whole stream on every call (a form of
#: 10,000 operations called 20,000 times is 200 million). Real corpus maximum (533 PDFs, measured
#: 2026-11-19): 87,726 operations, one 2-page offer letter. A walked operation costs ~0.2 µs, but a drawn
#: page's later text extraction costs ~5-10 µs per operation of its stream, so the budget also bounds that.
#: Past it the PDF has no layer (the Vision route) and none of it is text-extracted.
_MAX_DOC_OPS = 500_000
#: Fix round 5: one call of a form (``Do``) costs the walk and pypdf's extraction far more than one plain
#: operation, so each is charged this many operations on top of the form's own (measured below).
_DO_COST = 20
# Fix round 3: the costs below are charged BEFORE a stream is parsed (each stream every time it is walked, as
# pypdf's extraction re-reads a form on every call), so one huge operation can no longer stall the parse.
#: Decompressed content-stream bytes per document. Real corpus max (533 PDFs): 3,421,060.
_MAX_DOC_BYTES = 8_000_000
#: Token boundaries (whitespace and delimiter bytes) per document: a cheap upper bound on the tokens the
#: parser will read, so a stream of tiny operations is refused unparsed. Real max: 467,000.
_MAX_DOC_TOKENS = 700_000
#: ... and per stream: pypdf parses one stream in worse than linear time past ~400,000. Real max: 234,030.
_MAX_STREAM_TOKENS = 400_000
#: Characters handed to text-showing operators per document (pypdf decodes each). Real max: 7,373.
_MAX_DOC_SHOWN_CHARS = 200_000
_TOKEN_BOUNDARIES = bytes((0, 9, 10, 12, 13, 32)) + b'()<>[]{}/%'
_INLINE_IMAGE = re.compile(rb'(?<![^\s\x00)\]>}])BI(?![^\s\x00/])')
#: One string or ``<...>`` longer than this (raw, so never under its decoded length) is refused unparsed: pdfium
#: keeps only a string's first 32,767 bytes (fix round 6), and pypdf parses a huge one in worse than linear time.
#: Real max: 1,893 bytes. A bare token (name, number, operator) is quadratic in pypdf 5.9: 1,024 bytes. Real: 692.
_MAX_TOKEN_BYTES = 32_767
_MAX_BARE_TOKEN = 1_024
_BARE = rb'[^\x00\t\n\x0c\r ()<>\[\]{}/%]'
_LONG_BARE = re.compile(rb'(?<!' + _BARE + rb')' + _BARE + b'{%d}' % _MAX_BARE_TOKEN)
_LONG_ANGLED = re.compile(b'<[^<>]{%d}' % _MAX_TOKEN_BYTES)
#: Pages checked AND text-extracted per PDF. Callers need far fewer: the offer reader 3 (its MAX_PAGES),
#: the slip gate and Exact offer read page 1; corpus max 5 pages. Kept (fix round 4: uncapped, 2,000 pages took
#: 3 s); a longer PDF gives its first and LAST `_TAIL_PAGES` (`_layer_pages`): a KWSP statement ends on its latest.
MAX_LAYER_PAGES = 20
_TAIL_PAGES = 10


class _Budget:
    """One PDF's walk budget: operations, bytes, tokens, shown characters, font maps left."""

    def __init__(self):
        self.left = {'operations': _MAX_DOC_OPS, 'bytes': _MAX_DOC_BYTES, 'tokens': _MAX_DOC_TOKENS,
                     'shown characters': _MAX_DOC_SHOWN_CHARS, 'font maps': _MAX_DOC_FONT_COST}

    def spend(self, what: str, n: int) -> None:
        self.left[what] -= n
        if self.left[what] < 0:
            raise _OverBudget(f'past the {what} budget of one PDF')


def _parsed_ops(content, reader, cache: dict, budget: _Budget):
    """A content stream's (a page's or a form's) operations. Every walk is charged: first the stream's
    decompressed bytes, token boundaries and inline images (BEFORE any parse), then its operations. Parsed
    ONCE per document (a fan-out calls one form many times; pages may share one stream); the cache holds the
    object too, so its ``id`` cannot be reused while the walk runs."""
    from pypdf.generic import ContentStream
    hit = cache.get(id(content))
    if hit is None:
        stream = content if isinstance(content, ContentStream) else ContentStream(content, reader)
        data = stream.get_data()          # decompressed (pypdf 6 caps one stream at 75 MB); not yet parsed
        hit = [content, stream, (len(data), len(data) - len(data.translate(None, _TOKEN_BOUNDARIES))
                                 + data.count(b'\\')), None]
        _charge(budget, hit[2])           # bounds the scan below: parens and backslashes are tokens
        if hit[2][1] > _MAX_STREAM_TOKENS:
            raise _OverBudget('a content stream past the token limit')
        if _LONG_BARE.search(data) or _LONG_ANGLED.search(data) or longest_literal(data) > _MAX_TOKEN_BYTES:
            raise _OverBudget('a token past the size limit of one PDF')
        raw_state_check(data, len(_INLINE_IMAGE.findall(data)))      # fix round 5: raises (hidden), unparsed
        hit[3] = stream.operations
        cache[id(content)] = hit
    else:
        _charge(budget, hit[2])
    budget.spend('operations', len(hit[3]))
    return hit[3]


def _charge(budget: _Budget, cost: tuple) -> None:
    for what, n in zip(('bytes', 'tokens'), cost):
        budget.spend(what, n)


def _resolved(obj, key):
    v = obj.get(key)
    return v.get_object() if v is not None else None


def _resources(obj):
    """The /Resources pypdf's extraction uses for a page or an XObject: its own, else inherited up /Parent."""
    for _ in range(_MAX_PARENT_DEPTH):
        if '/Resources' in obj:
            return _resolved(obj, '/Resources')
        obj = _resolved(obj, '/Parent')
        if not isinstance(obj, dict):
            return None
    raise ValueError('/Parent chain too long')


def _walk_text_modes(content, resources, reader, mode, counts: list, depth: int, budget: _Budget,
                     cache: dict, undrawn: bool = False, font: bool = False) -> None:
    """Add to ``counts`` [drawn, hidden] the characters each text-showing operator places, by the render
    mode in force (``Tr``, saved and restored by ``q`` / ``Q``; an XObject starts from its caller's mode).
    ``undrawn``: inside an XObject a viewer never paints (not a /Form), or inside optional content that may
    be switched off (`oc_hides`), so all its text is hidden. ``font``: a ``Tf`` is in force (pdfium paints
    nothing before one; saved by ``q`` like the mode). ``budget`` is the WHOLE DOCUMENT's (`_Budget`),
    charged too for the font maps pypdf builds on this call (`charge_fonts`). Raises on anything it cannot
    parse or on an operand count the renderer reads differently (`bad_operands`): the caller's hidden."""
    from pypdf.generic import StreamObject
    ops = _parsed_ops(content, reader, cache, budget)
    charge_fonts(resources, budget, cache)
    stack, marked, off = [], [], 0          # off: open marked-content levels whose layer may be switched off
    xobjects = _resolved(resources, '/XObject') if isinstance(resources, dict) else None
    for operands, operator in ops:
        if bad_operands(operator, operands):
            raise ValueError(f'operands of {operator!r} the renderer reads differently')
        if operator == b'q':
            stack.append((mode, font))
        elif operator == b'Q':
            mode, font = stack.pop() if stack else (mode, font)
        elif operator == b'Tr':                # a float (3.0), non-number or out-of-range mode is not drawn
            mode = operands[0] if isinstance(operands[0], int) else -1     # the raw token: raw_state_check
        elif operator == b'Tf':
            font = True
        elif operator == b'INLINE IMAGE':
            raise ValueError('an inline image')
        elif operator in (b'BDC', b'BMC'):
            marked.append(operator == b'BDC' and operands[0] == '/OC' and oc_hides(operands[1], resources, reader,
                                                                                  cache))
            off += marked[-1]
        elif operator == b'EMC':
            off -= marked.pop() if marked else 0
        elif operator in _SHOW_OPS:
            n = shown_chars(operands)
            budget.spend('shown characters', n)
            counts[0 if mode in _DRAWN_MODES and font and not (undrawn or off) else 1] += n
        elif operator == b'Do':
            # pypdf reads text from EVERY XObject a Do names that is not an /Image; a non-stream gives it none
            xobj = xobjects.get(operands[0]) if xobjects else None
            xobj = xobj.get_object() if xobj is not None else None
            subtype = _resolved(xobj, '/Subtype') if isinstance(xobj, StreamObject) else '/Image'
            if subtype == '/Image':
                continue
            if depth >= _MAX_FORM_DEPTH:
                raise ValueError('XObjects nested too deep')
            budget.spend('operations', _DO_COST)
            _walk_text_modes(xobj, _resources(xobj) or resources, reader, mode, counts, depth + 1, budget, cache,
                             bool(undrawn or off or subtype != '/Form'
                                  or ('/OC' in xobj and oc_hides(xobj['/OC'], resources, reader, cache))), font)


#: What `_page_visibility` finds on one page.
DRAWN, HIDDEN, OVER_BUDGET = 'drawn', 'hidden', 'over_budget'


def _page_visibility(page, reader, budget: _Budget, cache: dict) -> str:
    """`DRAWN` when every character on the page is painted (or there is no text at all); `HIDDEN` when it
    places ANY hidden text (render mode not 0-2 / 4-6, or text in a non-Form XObject) or that cannot be
    decided; `OVER_BUDGET` when one of the document's budgets runs out on it (the whole PDF is then never
    text-extracted)."""
    try:
        contents = page.get('/Contents')
        contents = contents.get_object() if contents is not None else None
        if _is_null(contents):
            return DRAWN                   # no content stream: no text at all, nothing hidden
        counts = [0, 0]
        _walk_text_modes(contents, _resources(page), reader, 0, counts, 0, budget, cache)
        return HIDDEN if counts[1] > 0 else DRAWN
    except _OverBudget as e:
        logger.warning('PDF text visibility check stopped: %s', e)
        return OVER_BUDGET
    except Exception as e:  # noqa: BLE001 — undecidable is the Vision route (owner rule 2026-11-18), never the hidden text
        logger.warning('PDF text visibility check failed: %s', e)
        return HIDDEN


def _is_null(obj) -> bool:
    from pypdf.generic import is_null_or_none
    return is_null_or_none(obj)


def page_text_hidden(page, reader) -> bool:
    """True when this one page places ANY invisible text (render mode 3 / 7, an OCR overlay on a picture),
    or when that cannot be decided (an unreadable content stream, or past the operation budget, here a
    budget of its own). False only when every character on the page is drawn."""
    return _page_visibility(page, reader, _Budget(), {}) != DRAWN


def _visibilities(reader, per_page: int = 0) -> tuple:
    """`_page_visibility` of the `_layer_pages` under ONE budget and one parse cache. It
    stops at once when page 1 is not `DRAWN` (the PDF then has no layer at all) and at the first
    `OVER_BUDGET` page (the PDF is then never text-extracted): the tuple ENDS with that page.
    ``per_page`` (1 to `MAX_LAYER_PAGES`): the first that many pages, each judged on its own, with no stop
    at page 1 (`pdf_page_texts` only); still one budget and the same stop past it."""
    budget, cache, out = _Budget(), {}, []
    for i in _layer_pages(len(reader.pages), per_page):
        out.append(_page_visibility(reader.pages[i], reader, budget, cache))
        if out[-1] == OVER_BUDGET or (out[0] != DRAWN and not per_page):
            break
    return tuple(out)


def _layer_pages(n: int, per_page: int = 0) -> list:
    """The page indices read: the first ``per_page``; else all up to `MAX_LAYER_PAGES`, else the first and last."""
    if per_page or n <= MAX_LAYER_PAGES:
        return list(range(min(n, per_page or MAX_LAYER_PAGES)))
    return list(range(MAX_LAYER_PAGES - _TAIL_PAGES)) + list(range(n - _TAIL_PAGES, n))


def _open_pdf(data: bytes):
    """A pypdf reader for ``data`` (an empty password tried on an encrypted file), its page tree checked
    (`page_tree_check`) before pypdf flattens it. Raises on failure."""
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        reader.decrypt('')
    page_tree_check(reader)
    return reader


class _LayerRead(NamedTuple):
    """One PDF's S-visible read. ``visible``: page 1 is drawn and nothing ran past the budget — the ONE
    condition under which any of its text is used. ``texts``: pypdf's raw text of each checked page ('' for
    a page that is not drawn); None when the PDF could not be opened or its extraction failed."""
    pages: int
    visible: bool
    seen: tuple
    texts: Optional[tuple]


def _layer_read(data: bytes, per_page: int = 0, opened: Optional[list] = None) -> _LayerRead:
    """Walk (`_visibilities`) and, only when the PDF is `visible` (or ``per_page`` and within budget),
    extract its drawn pages — once — and have pdfium judge each drawn page's own objects (`pdf_pdfium_check`):
    a page it does not paint in full becomes `HIDDEN` (page 1 so: the PDF is not `visible`). ``opened``: a
    list holding the reader once opened, so one call chain opens and parses the PDF once."""
    try:
        opened = [] if opened is None else opened
        if not opened:
            opened.append(_open_pdf(data))
        reader = opened[0]
        n, seen = len(reader.pages), _visibilities(reader, per_page)
    except Exception as e:   # pypdf raises many kinds on a damaged file; unopenable is no layer (OverBudget too)
        logger.warning('PDF text visibility check failed: %s', e)
        return _LayerRead(0, False, (), None)
    visible = bool(seen) and seen[0] == DRAWN and OVER_BUDGET not in seen
    if OVER_BUDGET in seen or not (visible or per_page):
        return _LayerRead(n, False, seen, ('',) * len(seen))
    pages = _layer_pages(n, per_page)
    try:
        texts = tuple((reader.pages[i].extract_text() or '') if v == DRAWN else '' for i, v in zip(pages, seen))
    except Exception as e:  # noqa: BLE001 — a corrupt PDF has no text layer; logged, the caller falls back to OCR
        logger.warning('PDF text-layer extraction failed: %s', e)
        return _LayerRead(n, visible, seen, None)
    try:
        oc_off = _doc_may_switch_off(reader)
    except Exception:  # an unreadable optional-content dictionary may switch anything off
        oc_off = True
    flipped = pdf_pdfium_check.hidden_pages(data, n, {i: t for i, t, v in zip(pages, texts, seen) if v == DRAWN},
                                            oc_off, reader)
    if flipped:
        logger.warning('PDF text that pdfium does not paint: %d page(s)', len(flipped))
        seen = tuple(HIDDEN if i in flipped else v for i, v in zip(pages, seen))
        texts = tuple('' if i in flipped else t for i, t in zip(pages, texts))
        visible = seen[0] == DRAWN
    return _LayerRead(n, visible, seen, texts if visible or per_page else ('',) * len(seen))


#: Every reader of one upload (ocr_document_full, the slip gate's page 1, the SPM certificate reader, the
#: Exact offer read, the AI offer reader) asks about the same bytes: they share ONE walk and ONE
#: extraction. Keyed on the SHA-256 of the bytes (and ``per_page``); a small LRU, safe under gunicorn threads.
#: Content-addressed, so it is never stale; it is CLEARED only under pytest (conftest autouse fixture) — in
#: production entries leave only by LRU eviction. A read with more than `_MEMO_MAX_TEXT` characters of text
#: is not kept (8 such reads would pin a lot of memory per worker).
_LAYER_MEMO_SIZE = 8
_MEMO_MAX_TEXT = 2_000_000
_LAYER_MEMO: 'OrderedDict[tuple, _LayerRead]' = OrderedDict()
_LAYER_MEMO_LOCK = threading.Lock()


def _layer(data: bytes, per_page: int = 0, opened: Optional[list] = None) -> _LayerRead:
    key = (hashlib.sha256(data).digest(), per_page)
    with _LAYER_MEMO_LOCK:
        hit = _LAYER_MEMO.get(key)
        if hit is not None:
            _LAYER_MEMO.move_to_end(key)
            return hit
    read = _layer_read(data, per_page, opened)   # outside the lock: two threads may both read; same answer
    if sum(map(len, read.texts or ())) > _MEMO_MAX_TEXT:
        return read
    with _LAYER_MEMO_LOCK:
        _LAYER_MEMO[key] = read
        while len(_LAYER_MEMO) > _LAYER_MEMO_SIZE:
            _LAYER_MEMO.popitem(last=False)
    return read


def _layer_memo_clear() -> None:
    with _LAYER_MEMO_LOCK:
        _LAYER_MEMO.clear()


def first_page_drawn(data: bytes) -> bool:
    """True only when the PDF's text is usable at all (`_LayerRead.visible`: page 1 drawn, the walk within
    budget) — exactly when `pdf_text_layer` may return text. The one case where a reader of page 1's own
    characters (`spm_cert_parse._pdf_words`) sees what the page shows."""
    return _layer(data).visible


def pdf_text_layer(data: bytes) -> str:
    """The concatenated VISIBLE text layer of a PDF: the text of its DRAWN pages (of `_layer_pages`)
    joined. '' when page 1's text is invisible or cannot be checked (the Vision route
    reads page 1), when the walk runs past the operation budget, or the PDF is none / encrypted / damaged —
    the caller then falls back to rasterise+OCR (page 1). A later hidden page is left out, never returned.
    A caller deciding whether to trust it still passes it through `usable_text_layer` (TD-411). Past
    `MAX_LAYER_PAGES` a blank line marks the pages left out, so page N-9 never runs on from page 10."""
    read = _layer(data)
    if not read.visible or read.texts is None:
        return ''
    texts = [t if v == DRAWN else None for t, v in zip(read.texts, read.seen)]
    if read.pages > MAX_LAYER_PAGES and len(texts) > MAX_LAYER_PAGES - _TAIL_PAGES:
        texts.insert(MAX_LAYER_PAGES - _TAIL_PAGES, '')      # the gap: '\n' + '' + '\n' is one blank line
    return '\n'.join(t for t in texts if t is not None).strip()


def pdf_first_page_png(data: bytes) -> Optional[bytes]:
    """Rasterise page 1 of a PDF to PNG bytes (~200 DPI, within the pixel budget above). None on
    failure / library missing / an absurd page box. Page 1 only — bounds the Vision cost to 1 unit
    per doc."""
    try:
        with pdfium_document(data) as pdf:
            if len(pdf) == 0:
                return None
            page = pdf[0]
            width, height = page.get_width(), page.get_height()
            scale = raster_scale(width, height)
            if scale is None:
                logger.warning('PDF rasterise refused: page box %.0f x %.0f pt', width, height)
                return None
            pil = page.render(scale=scale).to_pil()
            buf = io.BytesIO()
            pil.convert('RGB').save(buf, format='PNG')
            return buf.getvalue()
    except Exception as e:  # noqa: BLE001 — a PDF that will not rasterise is logged; the caller handles None
        logger.warning('PDF rasterise failed: %s', e)
        return None


def pdf_page_pngs(data: bytes, max_pages: int) -> list:
    """The first ``max_pages`` pages of a PDF, each its OWN PNG (within the pixel budget) — the offer
    reader shows Gemini one image per page, so no page is shrunk to share one raster (offer exact-read
    S4, 2026-11-01). A page that cannot be rendered ends the list there; [] on any failure."""
    out = []
    try:
        with pdfium_document(data) as pdf:
            for i in range(min(len(pdf), max(0, max_pages))):
                page = pdf[i]
                scale = raster_scale(page.get_width(), page.get_height())
                if scale is None:
                    break
                buf = io.BytesIO()
                page.render(scale=scale).to_pil().convert('RGB').save(buf, format='PNG')
                out.append(buf.getvalue())
    except (ImportError, OSError, ValueError, RuntimeError) as e:   # pdfium's errors are RuntimeErrors
        logger.warning('PDF page render failed: %s', e)
    return out


def pdf_page_count(data: bytes) -> int:
    """The number of pages in a PDF; 0 when it cannot be opened."""
    try:
        with pdfium_document(data) as pdf:
            return len(pdf)
    except (ImportError, OSError, ValueError, RuntimeError):
        return 0


def pdf_page_texts(data: bytes, max_pages: int) -> list:
    """The VISIBLE text layer of each of the first ``max_pages`` pages (`_layer_pages`' first run), one
    string per page ([] if none / encrypted / unreadable): a page whose text is invisible or cannot be
    checked is '' — decided PER PAGE (S-visible, 2026-11-18), so it reads as a scanned page, and a drawn
    page after a hidden page 1 keeps its text (only then are those pages walked again, one by one: the
    shared read stops at a hidden page 1); EVERY page is '' when the walk ran past the operation budget.
    Pass a page through `usable_text_layer` before trusting it. pypdf raises many kinds on a damaged file,
    so any failure is no layer — the safe answer: the images are still shown."""
    opened = []                            # one open and parse of the PDF for both reads below
    read = _layer(data, 0, opened)
    n = min(read.pages, max(0, max_pages), MAX_LAYER_PAGES - (_TAIL_PAGES if read.pages > MAX_LAYER_PAGES else 0))
    if not read.visible and n > 1 and read.seen[:1] == (HIDDEN,):
        read = _layer(data, n, opened)     # page 1 hidden: the later pages are still judged one by one
    if read.texts is None:
        return []
    return [t.strip() for t in read.texts[:n]] + [''] * (n - len(read.texts[:n]))


def pdf_page_text(data: bytes, max_pages: int) -> str:
    """The text layer of the first ``max_pages`` pages, joined by a blank line ('' if none)."""
    return '\n\n'.join(pdf_page_texts(data, max_pages)).strip()


#: The pages `pdf_pages_png` stacks: the first two and the LAST — a declaration form's approval box
#: ("Tandatangan dan Cap Rasmi") is often on its final page (#374 review round 3).
MAX_STACKED_PAGES = 3


def _stack_pages(indices, pages):
    """Render page indices to one vertical PNG whose longer side stays within the pixel budget."""
    from PIL import Image
    boxes = [(pages[i].get_width(), pages[i].get_height()) for i in indices]
    if any(raster_scale(w, h) is None for w, h in boxes):
        return None
    total_h = sum(h for _w, h in boxes)
    scale = min(RASTER_DPI / 72.0, MAX_RASTER_SIDE_PX / max(total_h, max(w for w, _h in boxes)))
    images = [pages[i].render(scale=scale).to_pil().convert('RGB') for i in indices]
    sheet = Image.new('RGB', (max(im.width for im in images), sum(im.height for im in images)), 'white')
    y = 0
    for im in images:
        sheet.paste(im, (0, y))
        y += im.height
    buf = io.BytesIO()
    sheet.save(buf, format='PNG')
    return buf.getvalue()


def pdf_pages_png(data: bytes) -> Optional[bytes]:
    """ONE PNG of a PDF's pages stacked top to bottom — all of them up to `MAX_STACKED_PAGES`, else the
    first two and the last — so a single multimodal read sees the page that carries the approval. None on
    failure / library missing / an absurd page box (the caller then treats the read as not made)."""
    try:
        with pdfium_document(data) as pdf:
            n = len(pdf)
            if n == 0:
                return None
            indices = list(range(n)) if n <= MAX_STACKED_PAGES else [0, 1, n - 1]
            return _stack_pages(indices, {i: pdf[i] for i in indices})
    except (ImportError, OSError, ValueError, RuntimeError) as e:   # pdfium's errors are RuntimeErrors
        logger.warning('PDF page stack failed: %s', e)
        return None
