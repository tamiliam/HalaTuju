"""Re-run a document's automatic read — the shared core of the cockpit's per-doc
'Re-run' (AdminRunVisionView) and the bulk `reextract_documents` command, so the two
can't drift. Mirrors the upload-time processing per doc type and FORCES the (billable)
read (no cost-knob / throttle gate — it's a deliberate action). Best-effort on the
offer-letter pathway autofill (never fails the read)."""
import logging

from . import vision as _vision

logger = logging.getLogger(__name__)


def reextract_document(doc) -> bool:
    """Re-run the automatic read for one document, dispatched by type. Returns True when a
    known read ran, False for a type with no automatic check (caller decides what to do)."""
    from .views import BILL_DOC_TYPES, SUPPORTING_NAME_CHECK_TYPES, TEXT_READ_DOC_TYPES
    app = doc.application
    if doc.doc_type in ('ic', 'parent_ic'):
        _vision.run_vision_for_document(doc)               # MyKad OCR → vision_nric/name columns
    elif doc.doc_type in TEXT_READ_DOC_TYPES:
        _vision.read_text_document(doc)                    # letter of intent → vision_fields['text']
    elif doc.doc_type in SUPPORTING_NAME_CHECK_TYPES:
        profile = getattr(app, 'profile', None)
        names = [getattr(profile, 'name', '') or '']
        names += [g.get('name', '') for g in (getattr(profile, 'guardians', None) or [])
                  if isinstance(g, dict)]
        names = [n for n in names if n]
        postcode = getattr(profile, 'postal_code', '') or ''
        city = getattr(profile, 'city', '') or ''
        check_address = doc.doc_type in BILL_DOC_TYPES
        ocr = _vision.ocr_document(doc)                    # OCR once, shared by both checks
        _vision.run_vision_match_for_document(
            doc, names=names, postcode=postcode, city=city, check_address=check_address, ocr=ocr)
        if doc.doc_type in _vision.GEMINI_EXTRACT_DOC_TYPES:
            _vision.run_field_extraction_for_document(
                doc, names=names, postcode=postcode, city=city, check_address=check_address, ocr=ocr)
        if doc.doc_type == 'offer_letter':
            try:
                from .services import autofill_pathway_from_offer
                autofill_pathway_from_offer(app)
            except Exception:
                logger.warning('autofill_pathway_from_offer failed for app %s', app.id, exc_info=True)
    else:
        return False
    return True
