"""ONE lock around every use of pdfium (pypdfium2) in the api (S-visible fix round 6, 2026-11-19).

pypdfium2 4.30 is not thread-safe (pdfium keeps global state) and gunicorn runs 4 threads per worker, so two
uploads read at once could corrupt each other. Every pdfium use in the request path opens its document through
`pdfium_document`, which holds `PDFIUM_LOCK` for that ONE document: open, use, close — never longer. Users:
``pdf_pages`` (the page rasterisers and the page count), ``pdf_pdfium_check`` (the painted-text check) and
``spm_cert_parse`` (page 1's word boxes). ``eval/capture_ocr.py`` is an offline tool, outside the request path.
"""
import threading
from contextlib import contextmanager

#: Re-entrant, so a pdfium user that calls another under the lock cannot deadlock its own thread.
PDFIUM_LOCK = threading.RLock()


@contextmanager
def pdfium_document(data: bytes):
    """A pypdfium2 ``PdfDocument`` of ``data``, open only while `PDFIUM_LOCK` is held (closed on the way out)."""
    import pypdfium2 as pdfium
    with PDFIUM_LOCK:
        pdf = pdfium.PdfDocument(data)
        try:
            yield pdf
        finally:
            pdf.close()
