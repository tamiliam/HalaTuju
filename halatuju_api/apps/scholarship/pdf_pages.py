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
from typing import Optional

logger = logging.getLogger(__name__)

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
    library missing — caller then falls back to rasterise+OCR."""
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
