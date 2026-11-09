"""Every Gemini read this package makes: the structured-JSON seam, the field read of one
document, and the IC second opinion (moved verbatim from ``vision.py``, audit sprint A3.1).

``halatuju/ai_registry.py`` registers this file as the ``doc_read`` job."""

import json
import logging
from typing import Optional

from django.conf import settings

from ..gemini import cascade_failure, document_failure
from ..read_errors import UNPARSEABLE_RESPONSE, model_rejected_document
from .schemas import _DOC_HINTS, _FIELD_SCHEMAS
from .sanitize import _drop_expected_warnings, _sanitize_extracted_fields
from .. import vision as _v   # seams resolve on the package: one patch target reaches every caller

logger = logging.getLogger(__package__)   # 'apps.scholarship.vision', one name as before the split


# ── IC Gemini second-opinion (cost-gated) ──────────────────────────────────────
# The deterministic MyKad read (extract_mykad) is free but brittle: it can truncate
# marker-less names, leak card labels into the address, and trip on a single
# blurry/misread NRIC digit. When the cheap read is SHAKY (a core field missing, or
# it disagrees with what the student typed), we ask Gemini to read the card IMAGE as
# a clean second opinion. Cost-gated: it fires only on low-confidence reads, so the
# common clean upload stays free. Reuses the mockable ``_call_gemini_json`` seam.
_IC_GEMINI_SCHEMA = {'type': 'object', 'properties': {
    'nric': {'type': 'string'}, 'name': {'type': 'string'}, 'address': {'type': 'string'}}}

_IC_GEMINI_PROMPT = (
    'This is a photo of a Malaysian MyKad identity card. Read it carefully and return: '
    '"nric" = the holder\'s identity number (12 digits, formatted ######-##-####); '
    '"name" = their FULL name EXACTLY as printed, including any parentage marker '
    '(A/L, A/P, BIN, BINTI, S/O, D/O) AND the surname that follows it; '
    '"address" = their home address only (street, postcode, city, state) WITHOUT card '
    'labels such as "MyKad", "WARGANEGARA", "ISLAM", "LELAKI" or "PEREMPUAN". '
    'If a field is unclear, leave it empty. Do NOT invent or guess.'
)

# ── Genuineness fingerprint (verification-assurance roadmap, Sprint 1) ─────────
# A SEPARATE concern from field extraction: does the image look like a genuine photo/scan
# of a physical MyKad, or a typed sheet / screenshot / printout? Multimodal — Gemini inspects
# the picture for the card's standard fingerprints: the header words it can't omit AND the
# physical face/chip/card-look a typed fake can't carry. We don't claim certainty — we read a
# handful of independent markers and call it "highly probable" or not. SOFT: never blocks; the
# reviewer is the authority. Validated on our real ICs 2026-06-12 (genuine = all 8 markers; a
# typed fake carried only the words someone typed and failed every physical one → 'suspect').
# IC genuineness (constants + ic_genuineness) now lives in genuineness/ic.py and is
# re-exported at the end of this module (see the genuineness/ package).


def _as_image_for_gemini(data: bytes, content_type: str):
    """Return ``(image_bytes, mime_type)`` Gemini can read, or ``(None, '')``. A PDF
    (scanned MyKad) is rasterised to PNG page 1 first."""
    if not data:
        return None, ''
    if _v._is_pdf(content_type, data):
        png = _v._pdf_first_page_png(data)
        return (png, 'image/png') if png else (None, '')
    ct = (content_type or '').lower().split(';')[0].strip()
    return data, (ct if ct.startswith('image/') else 'image/jpeg')


def _gemini_ic_second_opinion(data: bytes, content_type: str) -> dict:
    """Ask Gemini to re-read the MyKad image → {'nric','name','address'} or {'_error'}.
    Never raises (the seam degrades gracefully)."""
    img, mime = _as_image_for_gemini(data, content_type)
    if img is None:
        return {'_error': 'no image for gemini'}
    return _v._call_gemini_json(_IC_GEMINI_PROMPT, _IC_GEMINI_SCHEMA, image=img, mime_type=mime)


def _call_gemini_json(prompt: str, schema: dict, *, image: Optional[bytes] = None,
                      mime_type: str = 'image/jpeg', images=None, media_resolution=None,
                      with_model: bool = False) -> dict:
    """Structured-output Gemini call → parsed JSON dict, or {'_error': msg}. This is
    the single seam tests @patch. Reuses profile_engine's model cascade + key guard.
    Pass ``image`` (raw bytes) for a multimodal read — Gemini sees the picture, not
    just OCR text (used by the IC second-opinion to recover blurry digits). ``images`` =
    [(bytes, mime), …] for several (images first, then the prompt); ``media_resolution`` sets
    the image detail (the offer reader, S4 — the default sends every image as 258 tokens);
    ``with_model`` adds ``_model`` (the cascade model that answered) to the answer."""
    api_key = getattr(settings, 'GEMINI_API_KEY', '') or ''
    if not api_key:
        return {'_error': 'AI service not configured (missing API key)'}
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return {'_error': 'AI module not installed'}
    from ..profile_engine import MODEL_CASCADE
    client = genai.Client(api_key=api_key)
    parts = list(images or []) + ([(image, mime_type)] if image is not None else [])
    contents = [types.Part.from_bytes(data=d, mime_type=m) for d, m in parts] + [prompt] if parts else prompt
    extra = {'media_resolution': media_resolution} if media_resolution else {}
    ours, document = [], []          # why each model failed: OUR side, or the document (2026-10-24)
    for model_name in MODEL_CASCADE:
        try:
            resp = client.models.generate_content(
                model=model_name, contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type='application/json', response_schema=schema, temperature=0.1,
                    **extra),
            )
        except Exception as e:  # noqa: BLE001 — graceful: never propagate to a 500
            (document if model_rejected_document(e) else ours).append((model_name, str(e)))
            logger.warning('Gemini JSON call failed with %s: %s', model_name, e)
            continue
        from .. import usage   # billable Gemini call — best-effort meter (tokens from usage_metadata)
        _it, _ot = usage.gemini_tokens(resp)
        usage.record_usage(usage.GEMINI, model=model_name, input_tokens=_it, output_tokens=_ot)
        try:
            out = json.loads(resp.text)
            return {**out, '_model': model_name} if with_model and isinstance(out, dict) else out
        except (TypeError, ValueError) as e:   # answered (billed) with nothing usable: try the next
            document.append((model_name, f'{UNPARSEABLE_RESPONSE}: {e}'))
            logger.warning('Gemini JSON call: %s returned no parseable JSON: %s', model_name, e)
    # Any model failing on OUR side makes the read ours (a healthy fallback never really answered);
    # only when every model looked and none could use the document is it the document's problem.
    return {'_error': cascade_failure(ours + document) if ours else document_failure(document)}


# The `warnings` are shown to a NON-TECHNICAL officer in the cockpit (docsDrawer). Steer Gemini to
# write them in reviewer language, not extraction/engineer register — no field names, no reference to
# these instructions, no OCR mechanics, no "which figure I picked" bookkeeping (owner 2026-07-10).
_WARNING_VOICE = (' Write each warning as ONE short plain-language sentence for a NON-TECHNICAL '
                  'reviewer — say what looks unclear or unusual ON THE DOCUMENT in everyday words. '
                  'Do NOT mention field names, the word "field", these instructions, code, or OCR, '
                  'and do NOT explain which figure you picked.')


def extract_document_fields(ocr_text: str, doc_type: str, *, image: Optional[bytes] = None,
                            content_type: str = '', **offer_context) -> dict:
    """Gemini extracts the per-doc-type fields. Pass ``image`` to read the document
    VISUALLY (the model sees the real 2-D layout — used for the results slip, whose
    table can't survive being flattened to OCR text); otherwise it reads ``ocr_text``.
    Returns {fields, warnings, error}. Never raises. An OFFER LETTER goes to `offer_reader.read_offer`
    (its pages, text layer, prompt and version; ``image`` is then the uploaded file's bytes);
    ``offer_context`` (profile_nric, page1_ocr — `_offer_context`) feeds only its IC guard."""
    if doc_type == 'offer_letter':
        from ..offer_reader import read_offer
        return read_offer(ocr_text, image=image, content_type=content_type, **offer_context)
    schema = _FIELD_SCHEMAS.get(doc_type)
    if schema is None:
        return {'fields': {}, 'warnings': [], 'error': f'no extractor for {doc_type}'}
    hint = _DOC_HINTS.get(doc_type, '')
    doc_label = doc_type.replace('_', ' ')
    if image is not None:
        img, mime = _as_image_for_gemini(image, content_type)
        if img is None:
            return {'fields': {}, 'warnings': [], 'error': 'no image for extraction'}
        prompt = (
            f'This is an image of a Malaysian {doc_label}. Read it carefully and extract '
            'the listed fields exactly as printed. If a field is missing or unclear, leave '
            f'it empty and add a short note to "warnings". Do NOT invent values.{_WARNING_VOICE}{hint}'
        )
        data = _v._call_gemini_json(prompt, schema, image=img, mime_type=mime)
    else:
        if not (ocr_text or '').strip():
            return {'fields': {}, 'warnings': [], 'error': 'no text'}
        prompt = (
            f'Here is the OCR text from a Malaysian {doc_label}. Extract the listed fields '
            'exactly as printed. If a field is missing or unclear, leave it empty and add a '
            f'short note to "warnings". Do NOT invent values.{_WARNING_VOICE}{hint}\n\nOCR TEXT:\n{(ocr_text or "")[:6000]}'
        )
        data = _v._call_gemini_json(prompt, schema)
    if '_error' in data:
        return {'fields': {}, 'warnings': [], 'error': data['_error']}
    warnings = _drop_expected_warnings(doc_type, data.pop('warnings', []) or [])
    data = _sanitize_extracted_fields(doc_type, data)
    return {'fields': data, 'warnings': warnings, 'error': ''}
