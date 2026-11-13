"""The OCR and PDF seams: Cloud Vision text / word boxes, the Storage fetch, a PDF's free text
layer, and the reads built on them (moved verbatim from ``vision.py``, audit sprint A3.1)."""

import logging
import math
from typing import Optional

from django.conf import settings
from django.utils import timezone

from ..pdf_pages import MIN_TEXT_LAYER_CHARS as _MIN_PDF_TEXT, usable_text_layer as _usable_text_layer
from .mykad import _compact, _extract_address, _extract_name, _extract_nric, _layout_read
from .gemini_read import _as_image_for_gemini
from .. import vision as _v   # seams resolve on the package: one patch target reaches every caller

logger = logging.getLogger(__package__)   # 'apps.scholarship.vision', one name as before the split


# ── PDF document intake (document-intake hardening) ────────────────────────────
# Students upload scan-to-PDF (CamScanner) and native digital PDFs (EPF, payslip,
# offer letter). Google Vision's inline image OCR cannot decode PDF bytes ("Bad
# image data."), so we handle PDFs ourselves:
#   - DIGITAL PDF → read the embedded text layer (pypdf) — free, perfect fidelity.
#   - SCANNED PDF → rasterise page 1 (pypdfium2 + Pillow) → feed the image to Vision.
# Both libs are OPTIONAL: if absent (or the PDF is corrupt/encrypted), a PDF
# degrades to "unreadable" — today's behaviour — rather than crashing.
_PDF_MAGIC = b'%PDF-'
# The page readers live in pdf_pages.py (page 1 within a pixel budget, 2026-10-02), and so does TD-411's
# _usable_text_layer: a layer that is only a scanner app's stamp ("CamScanner") is no layer → Vision.


def _is_pdf(content_type: str, data: bytes) -> bool:
    if (content_type or '').lower().split(';')[0].strip() == 'application/pdf':
        return True
    return bool(data) and data[:5] == _PDF_MAGIC


def _vision_document_text(image_bytes: bytes) -> dict:
    """Google Vision DOCUMENT_TEXT_DETECTION on *image* bytes → ``{'text', 'error'}``.
    The single seam the OCR functions share (and tests patch). Graceful — returns
    an error dict, never raises. ``error`` is None on success."""
    try:
        from google.cloud import vision
    except ImportError:
        return {'text': '', 'error': 'AI module not installed'}
    api_key = getattr(settings, 'GOOGLE_CLOUD_VISION_API_KEY', '') or ''
    try:
        client = (vision.ImageAnnotatorClient(client_options={'api_key': api_key})
                  if api_key else vision.ImageAnnotatorClient())
        resp = client.document_text_detection(image=vision.Image(content=image_bytes))
        from .. import usage
        usage.record_usage(usage.VISION_OCR)   # billable Cloud Vision call — best-effort meter
        if resp.error and resp.error.message:
            return {'text': '', 'error': resp.error.message[:200]}
        # Request #67: the SAME response carries the word boxes. The MyKad read uses them to see
        # the blank line between the name and the address; every other caller reads 'text' only.
        return {'text': resp.full_text_annotation.text if resp.full_text_annotation else '',
                'words': _words_of(resp), 'error': None}
    except Exception as e:  # noqa: BLE001 — graceful: never propagate to a 500
        logger.warning('Vision OCR failed: %s', e)
        return {'text': '', 'error': str(e)[:200]}


def _words_of(resp) -> list:
    """Per-word boxes from a Vision response: ``{text, cx, cy, h, angle, wlen, wh}``.
    ``text_annotations[0]`` is the whole text; ``[1:]`` are the words. ``angle`` is the
    baseline (vertex0→vertex1, degrees): 0 upright, ~±90 when the photo is sideways.
    ``wlen`` / ``wh`` are the word's length and height along its OWN baseline, so they
    stay right on a rotated photo (``h`` is the plain vertical extent, kept as it was)."""
    words = []
    for ann in resp.text_annotations[1:]:
        vs = ann.bounding_poly.vertices
        xs = [v.x for v in vs]
        ys = [v.y for v in vs]
        if not xs or not ys:
            continue
        angle = wlen = wh = None
        if len(vs) >= 2:
            angle = math.degrees(math.atan2(vs[1].y - vs[0].y, vs[1].x - vs[0].x))
            wlen = math.hypot(vs[1].x - vs[0].x, vs[1].y - vs[0].y)
        if len(vs) >= 3:
            wh = math.hypot(vs[2].x - vs[1].x, vs[2].y - vs[1].y)
        words.append({'text': ann.description,
                      'cx': sum(xs) / len(xs), 'cy': sum(ys) / len(ys),
                      'h': max(ys) - min(ys), 'angle': angle, 'wlen': wlen, 'wh': wh})
    return words


def _vision_words(data: bytes, content_type: str = '') -> dict:
    """Google Vision DOCUMENT_TEXT_DETECTION → per-WORD boxes (kept, not flattened) for
    positional table parsing — used by the results-slip deterministic reader to pair
    each subject with the grade on its own row. Returns ``{'words': [see _words_of], 'text',
    'error'}``; rasterises a PDF first. Graceful — never raises. (A separate seam from
    ``_vision_document_text`` so tests can patch it independently.)"""
    img, _mime = _as_image_for_gemini(data, content_type)
    if img is None:
        return {'words': [], 'text': '', 'error': 'no image'}
    try:
        from google.cloud import vision
    except ImportError:
        return {'words': [], 'text': '', 'error': 'AI module not installed'}
    api_key = getattr(settings, 'GOOGLE_CLOUD_VISION_API_KEY', '') or ''
    try:
        client = (vision.ImageAnnotatorClient(client_options={'api_key': api_key})
                  if api_key else vision.ImageAnnotatorClient())
        resp = client.document_text_detection(image=vision.Image(content=img))
        from .. import usage
        usage.record_usage(usage.VISION_OCR)   # billable Cloud Vision call — best-effort meter
        if resp.error and resp.error.message:
            return {'words': [], 'text': '', 'error': resp.error.message[:200]}
        # The SAME response carries the flattened text (full_text_annotation) — return it
        # too, so one billable call can serve both the positional parsers (words) and the
        # text consumers (name/address match, label parsers). See ocr_document_full.
        text = resp.full_text_annotation.text if resp.full_text_annotation else ''
        # The baseline angle lets the deterministic slip parser de-rotate a sideways photo
        # instead of falling back to Gemini (which transposes).
        return {'words': _words_of(resp), 'text': text, 'error': None}
    except Exception as e:  # noqa: BLE001 — graceful
        logger.warning('Vision word OCR failed: %s', e)
        return {'words': [], 'text': '', 'error': str(e)[:200]}


def extract_mykad(data: bytes, content_type: str = '') -> dict:
    """
    OCR a MyKad and return ``{'nric', 'name', 'address', 'error'}``. Accepts an
    image OR a PDF (a scanned MyKad — never a text PDF, so it is rasterised to an
    image first). Never raises.
    """
    if not data:
        return {'nric': '', 'name': '', 'address': '', 'error': 'empty image'}
    if _v._is_pdf(content_type, data):
        img = _v._pdf_first_page_png(data)
        if img is None:
            return {'nric': '', 'name': '', 'address': '', 'error': 'Bad image data.'}
        data = img
    r = _v._vision_document_text(data)
    if r['error']:
        return {'nric': '', 'name': '', 'address': '', 'error': r['error']}
    text = r['text']
    nric = _extract_nric(text)
    name = _extract_name(text, nric)
    address = _extract_address(text)
    # Request #67: where the word boxes came back, read the card's layout — the name runs from
    # the IC number down to the blank line, the address follows it. This recovers a name's
    # second line (or first) that the line-order read drops into the address. The layout read
    # is only taken when it CONTAINS the line-order name, so it can add name parts, never swap
    # the name for another line.
    layout = _layout_read(r.get('words') or [], text, nric)
    if layout and _compact(name) in _compact(layout['name']):
        name = layout['name']
        address = _extract_address(text, skip=layout['name_lines']) or layout['address']
    return {
        'nric': nric,
        'name': name,
        'address': address,
        'error': None,
    }


def _fetch_image_bytes(storage_path: str) -> Optional[bytes]:
    """Download a document's raw bytes from Supabase Storage (image OR PDF).
    Returns None on failure."""
    if not storage_path:
        return None
    try:
        from urllib.request import urlopen
        from ..storage import create_signed_download_url
        url = create_signed_download_url(storage_path)
        if not url:
            return None
        with urlopen(url, timeout=10) as r:
            return r.read()
    except Exception as e:  # noqa: BLE001 — a failed image fetch is logged and the caller handles None
        logger.warning('IC image fetch failed for %s: %s', storage_path, e)
        return None


# ── Generic supporting-document soft checks (S: results slip / income / bills) ──
# Arbitrary documents aren't MyKad-structured, so instead of field extraction we
# do a *presence* check on the full OCR text: does an expected name (or address)
# appear anywhere? Tolerant + naturally soft — exactly right for a non-blocking
# nudge to the student + the interviewer.

def extract_text(data: bytes, content_type: str = '') -> dict:
    """Generic full-text OCR. Accepts an image OR a PDF: a DIGITAL PDF is read via
    its text layer (no Vision call — free); a SCANNED PDF is rasterised (page 1) →
    Vision. ``{'text': str, 'error': str|None}``. Never raises."""
    if not data:
        return {'text': '', 'error': 'empty image'}
    if _v._is_pdf(content_type, data):
        text = _usable_text_layer(_v._pdf_text_layer(data))
        if len(text) >= _MIN_PDF_TEXT:
            return {'text': text, 'error': None}   # digital PDF — no billable Vision call
        img = _v._pdf_first_page_png(data)
        if img is None:
            return {'text': '', 'error': 'Bad image data.'}
        data = img
    r = _v._vision_document_text(data)
    return {'text': r.get('text', ''), 'error': r.get('error')}   # text only: the boxes are the MyKad read's


def _doc_usage_ctx(doc, source='doc_extract'):
    """Billing attribution for a doc-driven Vision/Gemini pipeline: org + application come
    from the document's application; every billable seam called within is tagged ``source``."""
    from .. import usage
    return usage.usage_context(application=getattr(doc, 'application', None), source=source)


def ocr_document(doc) -> dict:
    """Fetch + OCR a document once. Returns {text, error}. Pass the result to
    run_vision_match_for_document / run_field_extraction_for_document as ``ocr=``
    so the same upload OCRs only once."""
    with _doc_usage_ctx(doc):
        image = _v._fetch_image_bytes(doc.storage_path)
        return {'text': '', 'error': 'could not fetch image'} if image is None else _v.extract_text(image, doc.content_type)


def ocr_document_full(doc) -> dict:
    """Fetch + OCR a document ONCE for the whole upload/re-run pipeline: at most one
    download and one billable Vision call serve every consumer. Returns
    ``{'text', 'words', 'image', 'error'}``:

    - ``text`` — flattened OCR text (name/address match, label parsers, genuineness).
    - ``words`` — per-word boxes for the positional slip/BC parsers, or **None when not
      computed** (digital-PDF text-layer path, or a pre-OCR failure) — a consumer that
      needs words then makes its own read, exactly as before.
    - ``image`` — the fetched bytes, so downstream never re-downloads the blob.

    A DIGITAL PDF keeps the free text-layer path (no Vision call at all — the historic
    behaviour of ``ocr_document``); one Vision ``document_text_detection`` response
    otherwise carries both the text and the word boxes (previously two identical
    billable calls per slip/BC upload — code-health S2 #22)."""
    with _doc_usage_ctx(doc):
        image = _v._fetch_image_bytes(doc.storage_path)
        if image is None:
            return {'text': '', 'words': None, 'image': None, 'error': 'could not fetch image'}
        if _v._is_pdf(doc.content_type, image):
            text = _usable_text_layer(_v._pdf_text_layer(image))
            if len(text) >= _MIN_PDF_TEXT:
                return {'text': text, 'words': None, 'image': image, 'error': None}
        r = _v._vision_words(image, doc.content_type)
        return {'text': r.get('text') or '', 'words': r.get('words'), 'image': image,
                'error': r.get('error')}


def read_text_document(doc, *, ocr=None) -> dict:
    """OCR a FREE-TEXT document (e.g. the statement_of_intent / letter of intent) and store
    its plain text in ``vision_fields['text']`` for downstream analysis (Check 2 reads it for
    motivation + clues the structured form doesn't capture). Soft — never blocks an upload.

    Clobber guard (code-health S2 #5): the blob on a row is immutable, so a run that reads
    NOTHING where a previous run read text is OUR failure (Storage/OCR outage) — keep the
    stored text instead of wiping it."""
    from django.utils import timezone
    ocr = ocr if ocr is not None else _v.ocr_document(doc)
    new_text = (ocr.get('text') or '').strip()
    prior = doc.vision_fields if isinstance(doc.vision_fields, dict) else {}
    if not new_text and (prior.get('text') or '').strip():
        logger.warning('read_text_document: kept stored text for doc %s (re-run read nothing: %s)',
                       doc.id, ocr.get('error') or 'empty read')
        return prior
    doc.vision_fields = {'text': new_text,
                         'student_verdict': 'read', 'error': ocr.get('error', '') or ''}
    doc.vision_fields_run_at = timezone.now()
    doc.save(update_fields=['vision_fields', 'vision_fields_run_at'])
    return doc.vision_fields
