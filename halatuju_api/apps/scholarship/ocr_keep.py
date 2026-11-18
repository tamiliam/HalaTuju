"""OCR-first S0b: keep the text a read saw on a document (``ApplicantDocumentOcrText``).

The read pipeline used to throw the OCR text away once it had read the fields, so a new rule could only be
tried on live documents by paying for a second read. ``keep`` stores it at the two places every read already
has it (``vision.ocr.ocr_document_full`` and ``vision.ocr.ocr_document``): no new OCR or model call.

PRIVATE: no serializer, admin or export names the table (a test pins the modules that may), and the text is
never copied into ``vision_fields``. Deleted with the document (CASCADE).

``keep`` never raises and never changes the read: a failed write is logged (the document id and the error
type, never the text) and the read carries on. The write runs in its own savepoint, so a database error
cannot poison the read's transaction.
"""
import logging

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

PDF_TEXT_LAYER = 'pdf_text_layer'
VISION_OCR = 'vision_ocr'
OTHER = 'other'


def keep(doc, text, *, source, reader: str = '') -> bool:
    """Store ``text`` as the OCR text of ``doc``; True when a row was written.

    ``source`` is a source name, or a no-argument callable returning one (asked only when there is text
    to keep). Blank text stores nothing, so a failed or empty re-read keeps the text an earlier read
    stored; a read with text replaces it."""
    try:
        text = (text or '').replace('\x00', '')   # Postgres text cannot hold NUL
        doc_id = getattr(doc, 'pk', None)
        if not text.strip() or not isinstance(doc_id, int):
            return False
        src = source() if callable(source) else source
        from .models import ApplicantDocumentOcrText
        with transaction.atomic():
            ApplicantDocumentOcrText.objects.update_or_create(
                document_id=doc_id,
                defaults={'text': text, 'source': src or OTHER, 'reader': (reader or '')[:40],
                          'stored_at': timezone.now()},
            )
        return True
    except Exception as e:   # best-effort on purpose: keeping the text must never fail the read
        logger.warning('ocr_keep: could not keep the OCR text for doc %s (%s)',
                       getattr(doc, 'pk', None), type(e).__name__)
        return False
