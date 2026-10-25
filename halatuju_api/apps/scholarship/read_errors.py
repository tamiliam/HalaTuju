"""Is a failed document read OUR fault or the document's? — the one home for that question.

2026-10-24: Gemini's prepaid credit ran out (402) for ~20 hours. Every read failed and was stored as
the student's `unreadable`, so families were told to re-take good photos and the consent gate
blocked them. The rule since then: a read that failed on OUR side (an AI or OCR service down,
unconfigured or throttled) is a DEFERRED read — `student_verdict='review_manually'` plus
`service_error: True` — which every reader treats as "not read yet", never as "unreadable". A
failure that IS about the file (no text on it, a corrupt image, a fetch of a missing blob) stays
`unreadable`, exactly as before.

Imports nothing from the app, so `vision` (which must not import `services`) and `services` can
both read it.
"""

#: The stored error strings that mean OUR side of a read failed — no key, no client library, every
#: model in the cascade refused, our own hourly throttle deferred the read, or Google Vision OCR
#: itself failed on a supporting document (`OCR_SERVICE_FAILED`, written by `vision`). None of these
#: says anything about the document. Document-level failures ('no text', 'no image for extraction',
#: 'no extractor for …', 'could not fetch image', 'unparseable model response') are deliberately
#: absent: those ARE about the file (or what the model made of it).
CASCADE_FAILED = 'All AI models failed'
OCR_SERVICE_FAILED = 'OCR service failed'
SERVICE_ERROR_PREFIXES = (CASCADE_FAILED, 'AI service not configured', 'AI module not installed',
                          OCR_SERVICE_FAILED)
RATE_LIMITED = 'rate_limited'
#: A model answered, was billed, and returned nothing usable (a safety block, a truncated or
#: malformed JSON body). The model DID look at the document — the one model's note, not an outage.
UNPARSEABLE_RESPONSE = 'unparseable model response'
#: Prefix of a read in which EVERY model looked at the document and none could use it (each one
#: answered unparseably, or refused the FILE — see `model_rejected_document`). The document's
#: problem: stored `unreadable`, never retried. If even ONE model failed on our side instead, the
#: read is a service failure (`CASCADE_FAILED`): a healthy fallback never gave a real answer, so we
#: cannot say the document is at fault (round-2 review, 2026-10-24).
DOCUMENT_FAILED = 'No model could read this document'
#: The HTTP codes a refusal of the CONTENT arrives with. Necessary, never sufficient: a revoked key
#: ("API key not valid", reason API_KEY_INVALID), our own malformed config or schema, and a
#: region/billing FAILED_PRECONDITION are 400s too — and each of those is the incident all over
#: again if it is blamed on the student (round-3 review, 2026-10-24).
_DOCUMENT_LEVEL_CODES = (400, 413)
#: …so the MESSAGE must name the file. Kept to phrasings Gemini is known to send about content; an
#: unrecognised 400 is ours, because a wrong "ours" costs a retry and a wrong "theirs" costs a student.
_CONTENT_REJECTIONS = ('unable to process input image', 'the document has no pages',
                       'request payload size exceeds the limit', 'provided image is not valid')
#: Any of these anywhere in the error makes it ours, whatever else it says.
_OURS_MARKERS = ('api key', 'api_key', 'failed_precondition', 'permission_denied', 'billing',
                 'quota', 'model')


def model_rejected_document(exc) -> bool:
    """True only when a model call failed because the provider refused the FILE we sent: an HTTP
    400/413 (the SDK's `code`, else the message's leading number) whose message names the content
    (`_CONTENT_REJECTIONS`) and mentions nothing of ours (`_OURS_MARKERS`). Everything else — a
    key, a quota, billing, a model, our request shape, an unrecognised 400 — is OURS."""
    code = getattr(exc, 'code', None)
    text = ' '.join(str(p) for p in (exc, getattr(exc, 'message', '') or '')).lower()
    if not isinstance(code, int):
        head = text.strip().split(' ', 1)[0]
        code = int(head) if head.isdigit() else None
    return (code in _DOCUMENT_LEVEL_CODES
            and any(p in text for p in _CONTENT_REJECTIONS)
            and not any(m in text for m in _OURS_MARKERS))

# Vision errors that mean the FILE couldn't be decoded/fetched (a PDF/video/corrupt
# upload, or a storage-fetch glitch) — re-uploading a clear photo/scan fixes it.
# Distinct from a genuine OCR-SERVICE outage (quota/network/unconfigured), where
# re-uploading won't help. Drives the ic_unreadable vs ic_service_down split AND is
# excluded from the outage detector's service-failure count. (TD-080; moved here from
# `services/blockers.py` on 2026-10-24 so the supporting-document path can use the same split.)
_IC_DECODE_ERROR_MARKERS = ('empty image', 'bad image data', 'could not fetch')
#: `vision._vision_words` says this when the bytes could not be turned into an image at all (a PDF
#: that will not rasterise) — the file's problem, like the decode markers above.
_OCR_NO_IMAGE = 'no image'
#: Our own words on a row, never Vision's: OCR ran and found no text (the file's problem), or the
#: hourly sweep's in-flight / crash markers (`blockers.REPROCESS_ATTEMPTED`, 'reprocess_failed').
_OCR_NOT_A_SERVICE_ERROR = (_OCR_NO_IMAGE, 'no text read', 'reprocess_attempted', 'reprocess_failed')


def is_ic_decode_error(err: str) -> bool:
    e = (err or '').lower()
    return any(m in e for m in _IC_DECODE_ERROR_MARKERS)


def is_ocr_service_error(err) -> bool:
    """True when a Google Vision OCR error is the SERVICE failing (quota, billing, network, a
    missing SDK), by the same decode-vs-service split the IC gate has used since TD-080. Vision's
    own messages are free text, so this is the complement of the known file-level markers."""
    e = (err or '').strip()
    return bool(e) and not is_ic_decode_error(e) and e.lower() not in _OCR_NOT_A_SERVICE_ERROR


def is_ai_service_error(err) -> bool:
    """True when a stored read error is our read service failing, not the document."""
    e = (err or '').strip()
    return e == RATE_LIMITED or e.startswith(SERVICE_ERROR_PREFIXES)


def read_deferred(vision_fields) -> bool:
    """True when the stored field read has not JUDGED the document — it never ran (no verdict yet)
    or our AI deferred it (`review_manually`) — and so holds no fields. Every reader that would
    otherwise call such a document "unreadable" and ask the student for a clearer copy asks this
    first. A row carrying read fields is judged, whatever its verdict key says."""
    vf = vision_fields if isinstance(vision_fields, dict) else {}
    return not vf.get('fields') and (vf.get('student_verdict') or '') in ('', 'review_manually')


#: TD-390 (2026-10-25). An IC / parent_ic whose deterministic MyKad read was low-confidence NEEDED the
#: Gemini second opinion, and the second opinion failed on OUR side: the stored read is only half a
#: read. The marker holds the error; the epoch is the hourly sweep's 72-hour window (`read_retry`).
IC_SECOND_OPINION_ERROR = 'ic_second_opinion_error'
IC_SECOND_OPINION_UNTIL = 'ic_second_opinion_until'


def ic_second_opinion_deferred(doc) -> bool:
    """True when this IC's stored read is missing a REQUIRED second opinion our outage skipped. Every
    reader that would turn the read into a mismatch or "unreadable" asks this first and says
    "pending" / "service down" instead — never "match": a deferred IC must not pass identity.

    ⚠ ONLY WITHIN ITS WINDOW (review, 2026-10-25). Once `IC_SECOND_OPINION_UNTIL` has passed the
    sweep has given up, and the stored read is treated as COMPLETE again: its mismatches, its
    "unreadable" and its anomalies all show, exactly as before TD-390. A deferral can delay a signal;
    it can never hide one. A mark with no window (never written by the code) counts as expired."""
    from django.utils import timezone
    vf = getattr(doc, 'vision_fields', None)
    if not (isinstance(vf, dict) and vf.get(IC_SECOND_OPINION_ERROR)):
        return False
    until = vf.get(IC_SECOND_OPINION_UNTIL)
    return isinstance(until, (int, float)) and until > timezone.now().timestamp()


def deferred_by_us(vision_fields) -> bool:
    """The narrower case: a read was ATTEMPTED and our service deferred it (`review_manually`, no
    fields) — the state the hourly sweep re-reads. Check 2 HOLDS its document requests while such a
    copy is live (`check2_deferred`): no new ask, no auto-resolve. A document that was never read
    at all is not held, because nothing else will ever read it."""
    vf = vision_fields if isinstance(vision_fields, dict) else {}
    return not vf.get('fields') and vf.get('student_verdict') == 'review_manually'
