"""OCR-first S0b: keep the text a read saw on a document (``ApplicantDocumentOcrText``).

The read pipeline used to throw the OCR text away once it had read the fields, so a new rule could only be
tried on live documents by paying for a second read. ``keep`` stores it at the places every read already
has it (``vision.ocr.ocr_document_full`` and ``vision.ocr.ocr_document``; since OCR-15 also the IC and
parent IC read, ``vision.ic.run_vision_for_document``): no new OCR or model call. The one exception is
OCR-15's owner-approved one-off ``capture_parent_ic_text`` command (Cloud Vision only, never Gemini).

PRIVATE: no serializer, admin or export names the table (a test pins the modules that may), and the text is
never copied into ``vision_fields``. Deleted with the document (CASCADE).

``keep`` never raises and never changes the read: a failed write is logged (the document id and the error
type, never the text) and the read carries on.

AFTER THE CALLER'S COMMIT (fix round, 2026-11-18). The foreign key to the document is DEFERRABLE INITIALLY
DEFERRED, so inside a caller's transaction a savepoint does NOT cover it: a bad row would only fail at the
caller's COMMIT, and take the caller's own work down with it. So the write is handed to
``transaction.on_commit(..., robust=True)``: outside a transaction it runs at once (as every read does
today); inside one it runs only once the caller has committed, in its own transaction, where the key is
checked at our COMMIT and caught here. It also means text is never kept for a read that rolled back.
(``SET CONSTRAINTS ... IMMEDIATE`` would also work, but only on Postgres, it names a generated constraint,
and it would stay IMMEDIATE for the rest of the caller's transaction.)

THE ONE READ PATH (OCR-16, owner's choice 28 Nov 2026). Only the model and this module name the table: the
owner-approved jobs that read the stored text call ``kept_texts``, ``ids_with_kept_text`` or
``ids_with_kept_text_containing`` (a test pins exactly which modules may). Each takes the caller's document ids (a list, a set or an id
queryset), so none reads the whole table, and returns only ids or the texts of the ids asked for. They never
log or print text. ``writes_refused`` is the read-only jobs' write guard: inside it ``keep`` stores nothing
and a direct save of the table raises.
"""
import logging
from contextlib import contextmanager
from unittest import mock

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)

#: Open ``writes_refused`` blocks; while above 0, ``keep`` and ``_write`` store nothing.
_refusing = 0

PDF_TEXT_LAYER = 'pdf_text_layer'
VISION_OCR = 'vision_ocr'
OTHER = 'other'

#: The most text kept for one document. A real document reads to a few thousand characters; a cap keeps a
#: pathological text layer (a huge digital PDF) from writing megabytes per row. The head is kept.
MAX_CHARS = 200_000
CUT_MARKER = '\n[ocr_keep: text cut at {kept} of {total} characters]'


def capped(text: str) -> str:
    """``text`` cut to ``MAX_CHARS``, with a marker saying it was cut; unchanged when it fits."""
    if len(text) <= MAX_CHARS:
        return text
    return text[:MAX_CHARS] + CUT_MARKER.format(kept=MAX_CHARS, total=len(text))


def keep(doc, text, *, source, reader: str = '') -> bool:
    """Keep ``text`` as the OCR text of ``doc``, once the caller's transaction has committed (at once when
    there is none). True when the write was handed on; whether it landed is logged, never raised.

    Blank text stores nothing, so a failed or empty re-read keeps the text an earlier read stored; a read
    with text replaces it."""
    try:
        text = (text or '').replace('\x00', '')   # Postgres text cannot hold NUL
        doc_id = getattr(doc, 'pk', None)
        if _refusing or not text.strip() or not isinstance(doc_id, int):
            return False
        values = {'text': capped(text), 'source': source or OTHER, 'reader': (reader or '')[:40]}
        transaction.on_commit(lambda: _write(doc_id, values), robust=True)
        return True
    except Exception as e:   # best-effort on purpose: keeping the text must never fail the read
        _log_failure(getattr(doc, 'pk', None), e)
        return False


def _write(doc_id: int, values: dict) -> None:
    """The write itself, in its own transaction. A document deleted before this ran stores nothing."""
    if _refusing:
        return    # handed on before a writes_refused block opened: still nothing is stored inside it
    try:
        from .models import ApplicantDocument, ApplicantDocumentOcrText
        with transaction.atomic():
            if not ApplicantDocument.objects.filter(pk=doc_id).exists():
                return
            ApplicantDocumentOcrText.objects.update_or_create(
                document_id=doc_id, defaults=dict(values, stored_at=timezone.now()))
    except Exception as e:   # best-effort on purpose: keeping the text must never fail the read
        _log_failure(doc_id, e)


def _log_failure(doc_id, error) -> None:
    logger.warning('ocr_keep: could not keep the OCR text for doc %s (%s)', doc_id, type(error).__name__)


def _kept_rows(doc_ids):
    """The stored rows of the caller's documents only; a missing filter is refused, never read as 'all'."""
    if doc_ids is None or isinstance(doc_ids, (str, bytes, int)):
        raise TypeError('ocr_keep reads need the document ids to read (a list, a set or an id queryset)')
    from .models import ApplicantDocumentOcrText
    return ApplicantDocumentOcrText.objects.filter(document_id__in=doc_ids)


def kept_texts(doc_ids) -> dict:
    """``{document id: stored text}`` for those of ``doc_ids`` that have text stored. The text stays in the
    caller's memory: never log, print or save it."""
    return dict(_kept_rows(doc_ids).values_list('document_id', 'text'))


def ids_with_kept_text(doc_ids, *, reader: str = '') -> set:
    """The ids of ``doc_ids`` that have text stored (by ``reader`` only, when given)."""
    rows = _kept_rows(doc_ids)
    if reader:
        rows = rows.filter(reader=reader)
    return set(rows.values_list('document_id', flat=True))


def ids_with_kept_text_containing(words, doc_ids) -> set:
    """The ids of ``doc_ids`` whose stored text holds any of ``words`` (ignoring case). No words, no ids."""
    q = Q()
    for word in words:
        q |= Q(text__icontains=word)
    if not q:
        return set()
    return set(_kept_rows(doc_ids).filter(q).values_list('document_id', flat=True))


@contextmanager
def writes_refused(who: str):
    """A read-only job's guard: inside it ``keep`` stores nothing (returns False) and a direct save of the
    table raises ``RuntimeError`` naming ``who``. Nests; the save is restored on the way out."""
    from .models import ApplicantDocumentOcrText

    def refuse(*a, **k):
        raise RuntimeError(f'{who} writes no OCR text')

    global _refusing
    _refusing += 1
    try:
        with mock.patch.object(ApplicantDocumentOcrText, 'save', refuse):
            yield
    finally:
        _refusing -= 1
