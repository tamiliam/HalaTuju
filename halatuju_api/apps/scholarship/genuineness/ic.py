"""IC (MyKad) genuineness fingerprint — moved here from vision.py (behaviour unchanged).

A soft, multimodal "does this look like a real MyKad?" read: report a handful of independent
markers and call it 'likely_genuine' or not. SOFT: never blocks; the reviewer is the authority.
Validated on real ICs 2026-06-12 (genuine = all 8 markers; a typed fake carried only the words
someone typed and failed every physical one → 'suspect').

The Gemini seam is reached via ``vision._call_gemini_json`` (imported lazily inside the function
so the module-level import isn't circular and the test patch target stays valid).
"""
# Version of the IC genuineness model, stored on every result as ``model_version``. History:
#   1.0.0 (2026-11-19, LL3) — first stamped version; the behaviour in use since 2026-06-12 (8 markers,
#                        2.5 Flash first). Results stored before this carry no version (no back-fill).
#   1.1.0 (2026-11-28, OCR-16) — the read goes through `ai_model.ask`: behind `GENUINENESS_MODEL` (default
#                        empty = the 2.5 call exactly as before), or on 3.8 Flash with the answer checked, the
#                        verdict a closed enum and one retry. Prompt, markers and the status map unchanged.
# Guarded by `tests/test_model_versions.py`: a logic change here needs a bump + a `model_versions/ic.json` entry.
MODEL_VERSION = '1.1.0'

_IC_GENUINENESS_MARKERS = ('has_kad_pengenalan', 'has_malaysia', 'has_identity_card',
                           'has_mykad', 'has_warganegara', 'has_face_photo', 'has_chip',
                           'looks_like_physical_card')
_IC_GENUINENESS_SCHEMA = {'type': 'object', 'properties': {
    **{m: {'type': 'boolean'} for m in _IC_GENUINENESS_MARKERS},
    'verdict': {'type': 'string'}, 'reason': {'type': 'string'}},
    'required': list(_IC_GENUINENESS_MARKERS) + ['verdict', 'reason']}

_IC_GENUINENESS_PROMPT = (
    'Inspect this image. It was uploaded as a Malaysian MyKad (national identity card). '
    'Decide if it is a genuine PHOTO or SCAN of a physical MyKad, NOT a typed document, a '
    'screenshot of text, or a printout. Report which standard MyKad features are present: the '
    "header text 'KAD PENGENALAN', 'MALAYSIA', 'IDENTITY CARD'; the 'MyKad' wordmark; the "
    "'WARGANEGARA' field; a portrait FACE PHOTO of a person; an embedded gold CHIP; and whether "
    'the overall image looks like a photograph/scan of a physical plastic card (colour, layout, '
    "design) rather than plain text on white. verdict = 'genuine' (clearly a real MyKad), "
    "'suspect' (missing key physical features - likely typed/printed/screenshot), or 'not_an_ic' "
    '(not an identity card at all). reason = one short sentence.')

# Gemini verdict word → the CANONICAL genuineness outcome (genuine / suspect / not_<type>).
_GENUINENESS_STATUS = {'genuine': 'genuine', 'suspect': 'suspect', 'not_an_ic': 'not_ic'}


def ic_genuineness(data: bytes, content_type: str = '', *, model=None) -> dict:
    """Soft genuineness fingerprint for an IC image → ``{status, markers, reason, model_version}``
    or ``{}``.
    ``status`` ∈ canonical ``genuine`` / ``suspect`` / ``not_ic`` (or '' if unclassified).
    NEVER raises; an AI outage / unreadable image returns ``{}`` — NO signal, because we must not
    penalise a student for OUR failure. This only informs the Identity prediction + a pre-interview
    flag; the reviewer is the authority (verification-assurance roadmap). `model` forces a 3.8
    Flash model (the paid eval); None reads `GENUINENESS_MODEL` (`ai_model`)."""
    from apps.scholarship import vision   # lazy: avoids a circular import; keeps the patch seam
    from .ai_model import ask
    img, mime = vision._as_image_for_gemini(data, content_type)
    if img is None:
        return {}
    # OCR-16: 2.5 Flash by default (the model these verdicts were validated on); 3.8 Flash only once
    # `GENUINENESS_MODEL` names it, after the paid eval and the owner's yes.
    r = ask(_IC_GENUINENESS_PROMPT, _IC_GENUINENESS_SCHEMA, image=img, mime_type=mime, model=model,
            verdicts=set(_GENUINENESS_STATUS))
    if not isinstance(r, dict) or r.get('_error'):
        return {}
    return {
        'status': _GENUINENESS_STATUS.get((r.get('verdict') or '').strip().lower(), ''),
        'markers': {m: bool(r.get(m)) for m in _IC_GENUINENESS_MARKERS},
        'reason': (r.get('reason') or '')[:300],
        'model_version': MODEL_VERSION,
    }
