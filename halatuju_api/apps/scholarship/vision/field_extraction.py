"""Field extraction for one document: the deterministic-first read, the verdict, the
genuineness fingerprint and the clobber guard (moved from ``vision.py``, audit sprint A3.1;
the one long read is now a helper per document family, same calls in the same order)."""

import logging

from django.utils import timezone

from ..genuineness.bands import keep_stored_authenticity
from ..higher_results import extract as _higher_extract
from ..income_declaration import read_approval as _read_approval
from ..read_errors import OCR_SERVICE_FAILED, is_ai_service_error, is_ocr_service_error, read_deferred
from .authenticity import add_read_authenticity
from .judge import doc_student_verdict
from .ocr import _doc_usage_ctx
from .. import vision as _v   # seams resolve on the package: one patch target reaches every caller

logger = logging.getLogger(__package__)   # 'apps.scholarship.vision', one name as before the split


def _extract_slip_deterministic(doc, image, words=None):
    """``(result|None, diag)``. Positional OCR parse of an SPM results slip →
    ``{fields, warnings, error}``, or None to fall back to Gemini (no image, a student who HOLDS
    STPM results, or no parse). ``diag`` says WHY (incl. a sample of what Vision read), so a
    Gemini-fallback slip can be diagnosed later. Y/X geometry pairs each subject with the grade on
    its own row, which Gemini mis-transposes on a watermark. ``words`` (a prior read of the SAME
    blob) skips a second billable Vision call. The gate reads `results_held` (owner, 2026-10-02,
    TD-324: 1 live Form Six explorer's SPM slip had been skipped, 0 live the other way)."""
    if image is None:
        return None, {'reason': 'no_image'}
    from apps.courses.exam_questions import results_held
    exam_type = results_held(getattr(doc.application, 'profile', None)).lower()
    if exam_type and exam_type != 'spm':
        return None, {'reason': 'not_spm_exam', 'exam_type': exam_type}
    wd = {'words': words, 'error': None} if words is not None else _v._vision_words(image, doc.content_type)
    if wd.get('error'):
        return None, {'reason': 'vision_error', 'error': wd['error']}
    if not wd.get('words'):
        return None, {'reason': 'no_words'}
    from ..academic_engine import parse_spm_slip
    parsed = parse_spm_slip(wd['words'])
    if not parsed:
        # The deterministic parse couldn't lock onto the table (a format/orientation the
        # parser doesn't yet handle, or an unreadable photo) → Gemini reads it instead.
        # Keep the FULL word geometry (text + box + angle) on the fallback diag so this
        # slip can be frozen as a regression fixture and the parser extended — exactly how
        # the rotated-slip support was built. Only stored on failure, so no success bloat.
        capture = [{'text': w['text'], 'cx': round(w['cx'], 1), 'cy': round(w['cy'], 1),
                    'h': w['h'],
                    'angle': (round(w['angle'], 1) if w.get('angle') is not None else None)}
                   for w in wd['words']]
        return None, {'reason': 'parse_none', 'word_count': len(wd['words']), 'capture': capture}
    return {'fields': parsed, 'warnings': [], 'error': ''}, {'reason': 'ok'}


def run_field_extraction_for_document(doc, *, names, postcode='', city='', street='', check_address=False, ocr=None) -> dict:
    """Billing-metered wrapper: every Vision/Gemini seam called during field extraction is
    attributed to the document's organisation + application (source=doc_extract)."""
    with _doc_usage_ctx(doc):
        return _run_field_extraction_impl(
            doc, names=names, postcode=postcode, city=city, street=street,
            check_address=check_address, ocr=ocr)


def _offer_context(doc, page1_text):
    """What the offer reader's IC guard needs (`offer_ic`): the student's own IC and page 1's text. For a
    photo or a scan ``page1_text`` IS page 1 (`_vision_words` rasterises page 1 only); for a digital PDF it
    is the whole text layer, but the reader then uses its OWN page-1 layer and falls back to this only when
    page 1 has none (S4 re-review L3: there it can only make the cross-check more lenient, never refill)."""
    profile = getattr(getattr(doc, 'application', None), 'profile', None)
    return {'profile_nric': getattr(profile, 'nric', '') or '', 'page1_ocr': page1_text or ''}


#: Keys of a read kept on the stored record beside its fields (S4: the offer reader's version + inputs).
_EX_KEPT = ('parser_version', 'stpm_rows_from_entry', 'stpm_rows_sign_from_point', 'approval_read_error',
            'approval_read_until', 'offer_reader_version', 'offer_reader_inputs')



def _read_results_slip(doc, ocr, _o, image_fn, pre_words):
    """``(ex, image)``. The results slip is read DETERMINISTICALLY by positional OCR first (the
    standardised SPM table parses by geometry, immune to row-transposition); only if that can't lock
    onto the table does it fall back to the IMAGE with Gemini."""
    image = image_fn()
    from ..spm_cert_parse import parse_spm_cert, ensure_exam_year
    # OCR text for the CERTIFICATE parse (the slip parse below reads word boxes). Prefer the text
    # from the single ocr_document_full read on the upload path; else fetch it once.
    _text = _o.get('text')
    if _text is None:
        _r = ocr if ocr is not None else _v.ocr_document(doc)
        _text = (_r or {}).get('text', '') or ''
    # CERTIFICATE first — self-identifying ('layak dianugerahi'), so it runs for ANY student
    # (an STPM student's SPM cert included), NOT gated on the profile exam_type. The cert's
    # rows are read from the word boxes (a digital PDF: its text layer's boxes) by spm_cert_parse.
    cert = parse_spm_cert(_text, pre_words, image)
    if cert is not None:
        ex = {'fields': cert, 'warnings': [], 'error': '', 'capture': 'deterministic'}
    else:
        ex, diag = _v._extract_slip_deterministic(doc, image, words=pre_words)  # OCR-first (SPM slip); None → Gemini
        if ex is None:
            if image is not None:
                ex = _v.extract_document_fields('', doc.doc_type, image=image, content_type=doc.content_type)
            else:
                ex = _v.extract_document_fields(_text, doc.doc_type)
            ex['capture'] = 'ai'
            # Record WHY we fell back (+ what Vision read) so the slip can be diagnosed.
            if isinstance(ex.get('fields'), dict):
                ex['fields']['_slip_ocr_diag'] = diag
                # Backfill the exam YEAR from the OCR text — Gemini's `exam` field drops a
                # certificate's foot-of-page year, silently killing the exam-year chip.
                ex['fields']['exam'] = ensure_exam_year(ex['fields'].get('exam', ''), _text)
        else:
            ex['capture'] = 'deterministic'
    return ex, image


def _read_offer_letter(doc, ocr, _o, image_fn):
    """``(ex, image)``. STANDARDISED government offers (STPM / Matrikulasi / Polytechnic) read
    DETERMINISTICALLY from the OCR text — `offer_exact` (S5): the parser, the IC guard, the merge over
    the prior read; None unless it locks. Every other letter goes to the Gemini IMAGE read —
    `offer_reader` (S4)."""
    from ..offer_exact import exact_offer_read
    image = image_fn()
    _r = ocr if (ocr is not None) else _v.ocr_document(doc)
    _otext = (_o.get('text') if _o.get('text') is not None else (_r or {}).get('text', '')) or ''
    _ctx = _offer_context(doc, _otext)
    ex = exact_offer_read(_otext, prior=getattr(doc, 'vision_fields', None), image=image,
                          content_type=doc.content_type, **_ctx)
    if ex is None:
        ex = (_v.extract_document_fields('', doc.doc_type, image=image, content_type=doc.content_type, **_ctx)
              if image is not None else _v.extract_document_fields(_otext, doc.doc_type, **_ctx))
        ex['capture'] = 'ai'
    return ex, image


def _read_birth_certificate(doc, ocr, image_fn, pre_words):
    """Geometry-first, like the results slip. The BC's KANAK-KANAK / BAPA / IBU blocks place the
    child's "Nama" far from the parents'; flattened OCR cross-wires them (#10 read the father's
    name as the child). `parse_bc` re-linearises the Vision WORD BOXES by position, classifies
    the version (bilingual / mono), and reads each field from its label brackets — and returns
    None for a cropped/odd doc (so it can't invent a missing section, #27). On None → the gated
    Gemini-image fallback; OCR-text only if the image can't be fetched."""
    from ..bc_parse import parse_bc
    image = image_fn()
    if pre_words is not None:
        wd = {'words': pre_words, 'error': None}
    else:
        wd = _v._vision_words(image, doc.content_type) if image is not None else {'words': [], 'error': 'no image'}
    parsed = parse_bc(wd.get('words') or []) if not wd.get('error') else None
    if parsed is not None:
        ex = {'fields': parsed, 'warnings': [], 'error': '', 'capture': 'deterministic'}
    elif image is not None:
        ex = _v.extract_document_fields('', doc.doc_type, image=image, content_type=doc.content_type)
        ex['capture'] = 'ai'
    else:
        r = ocr if ocr is not None else _v.ocr_document(doc)
        ex = _v.extract_document_fields(r.get('text', ''), doc.doc_type)
        ex['capture'] = 'ai'
    return ex


def _read_labelled_doc(doc, ocr, image_fn):
    """Every other type: the OCR text, read by its labels first, else by Gemini on the text."""
    from ..doc_parse import parse_by_labels      # deterministic-first for standardised docs
    r = ocr if ocr is not None else _v.ocr_document(doc)
    if r['error'] or not (r['text'] or '').strip():   # Vision OCR down → OUR outage (TD-392a), not the file
        return {'fields': {}, 'warnings': [], 'error': (f"{OCR_SERVICE_FAILED}: {r['error']}"
                if is_ocr_service_error(r['error']) else r['error'] or 'no text read')}
    # Deterministic label capture first (never raises); None → Gemini. TD-319: so does an EPF table read 'unknown'.
    from ..epf_contribution_fallback import deterministic_or_epf_fallback
    parsed = parse_by_labels(doc.doc_type, r['text'])
    if parsed is not None:
        ex = deterministic_or_epf_fallback(doc.doc_type, parsed, r['text'], _v.extract_document_fields)
    else:
        ex = _v.extract_document_fields(r['text'], doc.doc_type)
        ex['capture'] = 'ai'
    return _read_approval(doc, ex, r['text'], image_fn)   # #374: informal income docs — one image call


def _build_read_result(doc, ex, *, names, postcode, city, street, check_address):
    """The stored record of a read: its fields and the student-facing verdict, or the error."""
    if ex['error']:   # OUR AI outage is a deferred read ('review_manually'), never the student's 'unreadable'
        svc = is_ai_service_error(ex['error'])
        return {'fields': {}, 'warnings': [], 'student_verdict': 'review_manually' if svc else 'unreadable', **{k: ex[k] for k in ex if k in _EX_KEPT},
                'capture': ex.get('capture', 'ai'), 'error': ex['error'], 'service_error': svc}
    verdict = doc_student_verdict(doc.doc_type, ex['fields'], names=names,
                                  postcode=postcode, city=city, street=street,
                                  check_address=check_address)
    return {'fields': ex['fields'], 'warnings': ex['warnings'], **{k: ex[k] for k in ex if k in _EX_KEPT},
            'student_verdict': verdict, 'capture': ex.get('capture', 'ai'), 'error': ''}


def _store_field_read(doc, result):
    """Save ``result`` on the document — unless the clobber guard keeps the stored read.

    Clobber guard (code-health S2 #5): the blob on a row is immutable, so a FAILED run (fetch/OCR/model
    error → empty fields) where the row already holds a successful extraction is OUR failure — a Storage
    outage or a checkout without Storage access. Overwriting good fields with an empty error read is the
    incident mode that destroyed vision_fields before (memory: halatuju_never_reextract_locally).
    Keep the stored read; report the failure to the caller without persisting it.
    2026-10-24: nor does OUR outage overwrite a real stored verdict (a true 'unreadable' included)."""
    prior = doc.vision_fields if isinstance(doc.vision_fields, dict) else {}
    real_verdict = not read_deferred(prior) and not is_ai_service_error(prior.get('error'))
    if result['error'] and (prior.get('fields') or (prior.get('text') or '').strip()
                            or (result['service_error'] and real_verdict)):
        logger.warning('run_field_extraction: kept stored extraction for doc %s (re-run failed: %s)',
                       doc.id, result['error'])
        return {**result, 'stale_kept': True}
    keep_stored_authenticity(doc, prior, result)          # TD-407: never a score replaced by silence
    doc.vision_fields = result
    doc.vision_fields_run_at = timezone.now()
    doc.save(update_fields=['vision_fields', 'vision_fields_run_at'])
    return result


def _run_field_extraction_impl(doc, *, names, postcode='', city='', street='', check_address=False, ocr=None) -> dict:
    """Extract fields + a deterministic student-facing verdict, store on the doc. Never blocks,
    never raises. Pass ``ocr`` to reuse a prior OCR pass.

    The **results slip** is read DETERMINISTICALLY by positional OCR first (the standardised SPM
    table parses by geometry, immune to row-transposition); only if that can't lock onto the table
    does it fall back to the IMAGE with Gemini. Higher results: `higher_results.extract`."""
    # A full-pipeline ocr dict (ocr_document_full) may carry the fetched bytes + the word
    # boxes from its single Vision call — reuse them instead of re-downloading / re-billing.
    _o = ocr if isinstance(ocr, dict) else {}

    def _image():
        return _o['image'] if _o.get('image') is not None else _v._fetch_image_bytes(doc.storage_path)

    pre_words = _o.get('words')                 # None = not computed (compute if needed)
    image = None                                # the slip and the offer hand theirs on to the genuineness read
    if doc.doc_type == 'results_slip':
        ex, image = _read_results_slip(doc, ocr, _o, _image, pre_words)
    elif doc.doc_type == 'offer_letter':
        ex, image = _read_offer_letter(doc, ocr, _o, _image)
    elif doc.doc_type == 'higher_results':
        ex = _higher_extract(doc, ocr, _image, _v.extract_document_fields)
    elif doc.doc_type == 'birth_certificate':
        ex = _read_birth_certificate(doc, ocr, _image, pre_words)
    else:
        ex = _read_labelled_doc(doc, ocr, _image)

    result = _build_read_result(doc, ex, names=names, postcode=postcode, city=city, street=street,
                                check_address=check_address)
    add_read_authenticity(doc, result, ocr=ocr, image=image, image_fn=_image)
    return _store_field_read(doc, result)
