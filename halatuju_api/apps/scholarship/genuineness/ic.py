"""IC (MyKad) genuineness fingerprint — moved here from vision.py (behaviour unchanged).

A soft, multimodal "does this look like a real MyKad?" read: report a handful of independent
markers and call it 'likely_genuine' or not. SOFT: never blocks; the reviewer is the authority.
Validated on real ICs 2026-06-12 (genuine = all 8 markers; a typed fake carried only the words
someone typed and failed every physical one → 'suspect').

The Gemini seam is reached via ``vision._call_gemini_json`` (imported lazily inside the function
so the module-level import isn't circular and the test patch target stays valid).
"""
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

# Gemini verdict word → our stored status. 'likely_genuine' is the honest ceiling — never "verified".
_GENUINENESS_STATUS = {'genuine': 'likely_genuine', 'suspect': 'low_confidence', 'not_an_ic': 'not_an_ic'}


def ic_genuineness(data: bytes, content_type: str = '') -> dict:
    """Soft genuineness fingerprint for an IC image → ``{status, markers, reason}`` or ``{}``.
    ``status`` ∈ ``likely_genuine`` / ``low_confidence`` / ``not_an_ic`` (or '' if unclassified).
    NEVER raises; an AI outage / unreadable image returns ``{}`` — NO signal, because we must not
    penalise a student for OUR failure. This only informs the Identity prediction + a pre-interview
    flag; the reviewer is the authority (verification-assurance roadmap)."""
    from apps.scholarship import vision   # lazy: avoids a circular import; keeps the patch seam
    img, mime = vision._as_image_for_gemini(data, content_type)
    if img is None:
        return {}
    r = vision._call_gemini_json(_IC_GENUINENESS_PROMPT, _IC_GENUINENESS_SCHEMA, image=img, mime_type=mime)
    if not isinstance(r, dict) or r.get('_error'):
        return {}
    return {
        'status': _GENUINENESS_STATUS.get((r.get('verdict') or '').strip().lower(), ''),
        'markers': {m: bool(r.get(m)) for m in _IC_GENUINENESS_MARKERS},
        'reason': (r.get('reason') or '')[:300],
    }
