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
    return not (len(words) >= 10 and sum(len(w) == 1 for w in words) > 0.6 * len(words))


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


def pdf_text_layer(data: bytes) -> str:
    """The concatenated text layer of a PDF (all pages). '' if none / encrypted /
    library missing — caller then falls back to rasterise+OCR. The RAW layer: a caller deciding
    whether to trust it passes it through `usable_text_layer` first (TD-411)."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                reader.decrypt('')
            except Exception:  # noqa: BLE001
                return ''
        return '\n'.join((p.extract_text() or '') for p in reader.pages).strip()
    except Exception as e:  # noqa: BLE001
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
    except Exception as e:  # noqa: BLE001
        logger.warning('PDF rasterise failed: %s', e)
        return None


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
