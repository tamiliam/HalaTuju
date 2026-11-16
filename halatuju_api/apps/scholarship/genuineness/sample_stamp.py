"""H9: spot an uploaded SAMPLE (our own sample drawing, or any document stamped SAMPLE / CONTOH /
SPECIMEN across it) and never accept it.

Where it sits: ``upload_read._read_copy`` calls ``check_uploaded_sample`` once, AFTER the type's own
read and BEFORE ``judge()``. That is the one place every read document type passes, and it is
outside ``vision/`` (a money path, not touched). The decision is the MODEL's ("is a SAMPLE stamp
printed across the document?"); the word list below is only a cheap gate that decides whether to ask
the model at all, so a real document that merely has the word "contoh" in its ordinary text is NOT
flagged (the model is told to ignore ordinary text, and answers per image).

Outcome: the stored authenticity becomes ``not_<doc_type>`` (the existing wrong-document path, the
same soft treatment as any not-genuine document) with ``doc_seen='sample_document'`` and a reviewer
reason. An outage, a model error or a disabled flag means NO flag (we never penalise the student for
our failure). Soft: the reviewer stays the authority.
"""
import logging
import re

logger = logging.getLogger(__name__)

SAMPLE_CHECK_VERSION = '1.0.0'
SAMPLE_DOC_SEEN = 'sample_document'
SAMPLE_REASON = 'Looks like a sample document (stamped SAMPLE / CONTOH), not a real one.'

# Cheap gate only. Never decides on its own.
_SAMPLE_WORD = re.compile(r'\b(sample|contoh|specimen|spesimen)\b', re.I)

_SCHEMA = {'type': 'object', 'properties': {
    'is_sample': {'type': 'boolean'}, 'reason': {'type': 'string'}},
    'required': ['is_sample', 'reason']}
_PROMPT = (
    'Look at this image of an uploaded document. Is a large SAMPLE, CONTOH, SPECIMEN or SPESIMEN '
    'stamp, watermark or banner printed ACROSS the document, marking it as a sample, specimen or '
    'example rather than a real, issued document? Answer is_sample = true ONLY for such a stamp, '
    'watermark or banner (or an obviously drawn mock-up carrying one). Answer false for an ordinary '
    'document, even if the word "contoh" or "sample" appears in its normal printed text (for example '
    '"contoh tandatangan" next to a signature box). reason = one short sentence.')


def check_enabled() -> bool:
    """The sample check runs only when the genuineness check is on AND its own kill switch
    env var ``SAMPLE_CHECK_ENABLED`` (default ON; set it to 0 on the service with --update-env-vars to stop it at
    once, no code deploy; read per call, kept out of settings/base.py, which is at its size allowance)."""
    import os
    from django.conf import settings
    on = os.environ.get('SAMPLE_CHECK_ENABLED', '1').strip().lower() not in ('0', 'false', 'no', 'off')
    return bool(getattr(settings, 'DOC_GENUINENESS_CHECK_ENABLED', False) and on)


def _record_clean(doc):
    """Checked and clean: stamp the version so "checked, not a sample" differs from "never checked"."""
    vf = dict(doc.vision_fields or {})
    vf['sample_check_version'] = SAMPLE_CHECK_VERSION
    doc.vision_fields = vf
    doc.save(update_fields=['vision_fields'])


def has_sample_word(text: str) -> bool:
    return bool(text and _SAMPLE_WORD.search(text))


def _ask_model(image: bytes, content_type: str):
    """True / False from the model, or None when there is no answer (outage, unsupported image)."""
    from apps.scholarship import vision
    from apps.scholarship.profile_engine import FLASH_25_CASCADE
    img, mime = vision._as_image_for_gemini(image, content_type)
    if img is None:
        return None
    r = vision._call_gemini_json(_PROMPT, _SCHEMA, image=img, mime_type=mime, models=FLASH_25_CASCADE)
    if not isinstance(r, dict) or r.get('_error') or 'is_sample' not in r:
        return None
    return bool(r.get('is_sample'))


def check_uploaded_sample(doc, image, text=None):
    """Ask the model whether ``image`` is a stamped sample and, if so, mark ``doc`` not genuine.
    ``text`` is the OCR text when we have it: with text and no sample word the model is not asked.
    Returns True when the document was flagged. NEVER raises."""
    try:
        if not check_enabled() or not image:
            return False
        if text and not has_sample_word(text):
            _record_clean(doc)
            return False
        from apps.scholarship import usage
        with usage.usage_context(application=getattr(doc, 'application', None),
                                 source='genuineness'):
            verdict = _ask_model(image, doc.content_type or '')
        if verdict is None:     # no answer (outage, unsupported image): not checked, nothing recorded
            return False
        if not verdict:
            _record_clean(doc)
            return False
        vf = dict(doc.vision_fields or {})
        from .bands import stored_authenticity
        auth = dict(stored_authenticity(vf))
        auth.setdefault('scored_status', auth.get('status', ''))
        auth.update({'status': 'not_' + doc.doc_type, 'doc_seen': SAMPLE_DOC_SEEN,
                     'reason': SAMPLE_REASON, 'sample': True,
                     'sample_check_version': SAMPLE_CHECK_VERSION})
        vf['authenticity'] = auth
        doc.vision_fields = vf
        doc.save(update_fields=['vision_fields'])
        return True
    except Exception:       # an upload never fails over this check
        logger.exception('sample check failed for document %s', getattr(doc, 'id', None))
        return False


def is_sample_flagged(doc) -> bool:
    from .bands import stored_authenticity
    return bool(stored_authenticity(getattr(doc, 'vision_fields', None)).get('sample'))
