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
import io
import logging
import re
from typing import Optional

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
#: Text render modes that paint nothing: 3 = invisible, 7 = add to the clipping path only.
_INVISIBLE_MODES = frozenset((3, 7))
_SHOW_OPS = frozenset((b'Tj', b'TJ', b"'", b'"'))
#: Form XObjects nest; deeper than this is not a document page (and a cycle must end).
_MAX_FORM_DEPTH = 8
#: Text-show + form-invoke operations walked per PAGE, shared across the form recursion. The depth cap
#: bounds nesting, not fan-out: a 2 KB file with 40 form calls per level, 4 levels deep, is 2.5 million
#: invocations. Past this budget the page reads as hidden (the Vision route) and pypdf's own
#: ``extract_text`` (which walks the same forms) is never run on that PDF. A real page is far below it.
_MAX_PAGE_OPS = 50_000


class _OverBudget(Exception):
    """A page asked for more than `_MAX_PAGE_OPS` operations: hostile or broken, never read as text."""


def _form_ops(xobj, reader, cache: dict):
    """A form XObject's parsed operations, parsed ONCE per walk (a fan-out calls one form many times).
    The cache holds the object too, so its ``id`` cannot be reused while the walk runs."""
    hit = cache.get(id(xobj))
    if hit is None:
        from pypdf.generic import ContentStream
        hit = cache[id(xobj)] = (xobj, ContentStream(xobj, reader).operations)
    return hit[1]


def _shown_chars(operator: bytes, operands) -> int:
    """How many non-blank characters one text-showing operator places (raw string units: what matters
    is whether any text is shown, not how it decodes)."""
    if not operands:
        return 0
    if operator == b'TJ':
        items = operands[0] if isinstance(operands[0], list) else []
    else:
        items = [operands[-1]]          # Tj / ' take (string); " takes (aw, ac, string)
    n = 0
    for s in items:
        if isinstance(s, bytes):
            n += sum(b not in b' \t\r\n\x00' for b in s)
        elif isinstance(s, str):
            n += sum(not c.isspace() for c in s)
    return n


def _walk_text_modes(content, resources, reader, mode: int, counts: list, depth: int,
                     budget: Optional[list] = None, cache: Optional[dict] = None) -> None:
    """Add to ``counts`` [drawn, invisible] the characters each text-showing operator places, by the
    render mode in force (``Tr``, saved and restored by ``q`` / ``Q``; a Form XObject starts from its
    caller's mode). ``budget`` [operations left] is shared by the whole page's recursion: each text show
    and each form call spends one, and an empty budget raises `_OverBudget`. Raises on anything it
    cannot parse — the caller treats that as invisible."""
    from pypdf.generic import ContentStream
    budget = [_MAX_PAGE_OPS] if budget is None else budget
    cache = {} if cache is None else cache
    if isinstance(content, ContentStream):
        ops = content.operations
    elif depth:
        ops = _form_ops(content, reader, cache)
    else:
        ops = ContentStream(content, reader).operations
    stack = []
    xobjects = (resources or {}).get('/XObject') if resources is not None else None
    xobjects = xobjects.get_object() if xobjects is not None else {}
    for operands, operator in ops:
        if operator == b'q':
            stack.append(mode)
        elif operator == b'Q':
            mode = stack.pop() if stack else mode
        elif operator == b'Tr':
            mode = int(operands[0])
        elif operator in _SHOW_OPS:
            _spend(budget)
            counts[1 if mode in _INVISIBLE_MODES else 0] += _shown_chars(operator, operands)
        elif operator == b'Do' and operands:
            xobj = xobjects.get(operands[0]) if xobjects else None
            xobj = xobj.get_object() if xobj is not None else None
            if xobj is not None and xobj.get('/Subtype') == '/Form':
                _spend(budget)
                if depth >= _MAX_FORM_DEPTH:
                    raise ValueError('form XObjects nested too deep')
                _walk_text_modes(xobj, xobj.get('/Resources') or resources, reader, mode, counts, depth + 1,
                                 budget, cache)


def _spend(budget: list) -> None:
    budget[0] -= 1
    if budget[0] < 0:
        raise _OverBudget(f'more than {_MAX_PAGE_OPS} text / form operations on one page')


#: What `_page_visibility` finds on one page.
DRAWN, HIDDEN, OVER_BUDGET = 'drawn', 'hidden', 'over_budget'


def _page_visibility(page, reader) -> str:
    """`DRAWN` when every character on the page is painted (or there is no text at all); `HIDDEN` when it
    places ANY invisible text (render mode 3 / 7) or that cannot be decided; `OVER_BUDGET` when deciding
    would take more than `_MAX_PAGE_OPS` operations (the whole PDF is then never text-extracted)."""
    try:
        contents = page.get_contents()
        if contents is None:
            return DRAWN                   # no content stream: no text at all, nothing hidden
        resources = page.get('/Resources')
        resources = resources.get_object() if resources is not None else None
        counts = [0, 0]
        _walk_text_modes(contents, resources, reader, 0, counts, 0)
        return HIDDEN if counts[1] > 0 else DRAWN
    except _OverBudget as e:
        logger.warning('PDF text visibility check stopped: %s', e)
        return OVER_BUDGET
    except Exception as e:  # noqa: BLE001 — undecidable is the Vision route (owner rule 2026-11-18), never the hidden text
        logger.warning('PDF text visibility check failed: %s', e)
        return HIDDEN


def page_text_hidden(page, reader) -> bool:
    """True when this page places ANY invisible text (render mode 3 / 7, an OCR overlay on a picture),
    or when that cannot be decided (an unreadable content stream, or past the operation budget). False
    only when every character on the page is drawn — the one case where its text layer is what the page
    shows."""
    return _page_visibility(page, reader) != DRAWN


def _visibilities(reader, max_pages: Optional[int] = None) -> list:
    """`_page_visibility` of each page (the first ``max_pages``), stopping at the first `OVER_BUDGET`
    page: the list then ENDS with it, and the caller extracts no text from this PDF at all."""
    out = []
    pages = reader.pages if max_pages is None else reader.pages[:max(0, max_pages)]
    for p in pages:
        out.append(_page_visibility(p, reader))
        if out[-1] == OVER_BUDGET:
            break
    return out


def first_page_drawn(data: bytes) -> bool:
    """True only when a PDF's page 1 is DRAWN (no invisible text, check passed): the one case where a
    reader of page 1's own characters (`spm_cert_parse._pdf_words`) sees what the page shows."""
    try:
        reader = _open_pdf(data)
        return bool(len(reader.pages)) and _visibilities(reader, 1) == [DRAWN]
    except Exception as e:   # pypdf raises many kinds on a damaged file; unopenable is not drawn (no layer read)
        logger.warning('PDF page-1 visibility check failed: %s', e)
        return False


def _open_pdf(data: bytes):
    """A pypdf reader for ``data`` (an empty password tried on an encrypted file). Raises on failure."""
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        reader.decrypt('')
    return reader


def pdf_text_layer(data: bytes) -> str:
    """The concatenated VISIBLE text layer of a PDF: the text of its DRAWN pages only, joined. '' if
    none / encrypted / library missing — caller then falls back to rasterise+OCR (page 1). S-visible
    (owner decision 2026-11-18, fix round): '' when PAGE 1's text is invisible or cannot be checked, as
    the Vision route reads page 1; otherwise a later hidden page is simply left out (its text is never
    returned) and the drawn pages are kept. '' too when any page is past the operation budget (no text
    is extracted from such a file). A caller deciding whether to trust it still passes it through
    `usable_text_layer` (TD-411)."""
    try:
        reader = _open_pdf(data)
        seen = _visibilities(reader)
        if not seen or seen[0] != DRAWN or OVER_BUDGET in seen:
            return ''                      # page 1 a picture with an OCR overlay: read what is seen (Vision)
        return '\n'.join((p.extract_text() or '') for p, v in zip(reader.pages, seen) if v == DRAWN).strip()
    except Exception as e:  # noqa: BLE001 — a corrupt PDF has no text layer; logged, the caller falls back to OCR
        logger.warning('PDF text-layer extraction failed: %s', e)
        return ''


def pdf_first_page_png(data: bytes) -> Optional[bytes]:
    """Rasterise page 1 of a PDF to PNG bytes (~200 DPI, within the pixel budget above). None on
    failure / library missing / an absurd page box. Page 1 only — bounds the Vision cost to 1 unit
    per doc."""
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(data)
        try:
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
        finally:
            pdf.close()
    except Exception as e:  # noqa: BLE001 — a PDF that will not rasterise is logged; the caller handles None
        logger.warning('PDF rasterise failed: %s', e)
        return None


def pdf_page_pngs(data: bytes, max_pages: int) -> list:
    """The first ``max_pages`` pages of a PDF, each its OWN PNG (within the pixel budget) — the offer
    reader shows Gemini one image per page, so no page is shrunk to share one raster (offer exact-read
    S4, 2026-11-01). A page that cannot be rendered ends the list there; [] on any failure."""
    out = []
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(data)
        try:
            for i in range(min(len(pdf), max(0, max_pages))):
                page = pdf[i]
                scale = raster_scale(page.get_width(), page.get_height())
                if scale is None:
                    break
                buf = io.BytesIO()
                page.render(scale=scale).to_pil().convert('RGB').save(buf, format='PNG')
                out.append(buf.getvalue())
        finally:
            pdf.close()
    except (ImportError, OSError, ValueError, RuntimeError) as e:   # pdfium's errors are RuntimeErrors
        logger.warning('PDF page render failed: %s', e)
    return out


def pdf_page_count(data: bytes) -> int:
    """The number of pages in a PDF; 0 when it cannot be opened."""
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(data)
        try:
            return len(pdf)
        finally:
            pdf.close()
    except (ImportError, OSError, ValueError, RuntimeError):
        return 0


def pdf_page_texts(data: bytes, max_pages: int) -> list:
    """The VISIBLE text layer of each of the first ``max_pages`` pages, one string per page ([] if none /
    encrypted / unreadable): a page whose text is invisible or cannot be checked is '' — decided PER
    PAGE (S-visible, 2026-11-18), so it reads as a scanned page; every page is '' when one is past the
    operation budget. Pass a page through `usable_text_layer`
    before trusting it. pypdf raises many kinds on a damaged file (its own, struct / zlib / recursion
    errors…), so any failure is no layer — the safe answer: the images are still shown."""
    try:
        reader = _open_pdf(data)
        pages = reader.pages[:max(0, max_pages)]
        seen = _visibilities(reader, max_pages)
        if OVER_BUDGET in seen:            # a hostile file: no page of it is text-extracted
            return [''] * len(pages)
        return [((p.extract_text() or '').strip() if v == DRAWN else '') for p, v in zip(pages, seen)]
    except Exception as e:   # a damaged PDF's layer is simply absent (review L2)
        logger.warning('PDF page text extraction failed: %s', e)
        return []


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
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(data)
        try:
            n = len(pdf)
            if n == 0:
                return None
            indices = list(range(n)) if n <= MAX_STACKED_PAGES else [0, 1, n - 1]
            pages = {i: pdf[i] for i in indices}
            return _stack_pages(indices, pages)
        finally:
            pdf.close()
    except (ImportError, OSError, ValueError, RuntimeError) as e:   # pdfium's errors are RuntimeErrors
        logger.warning('PDF page stack failed: %s', e)
        return None
