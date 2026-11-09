"""The IC (MyKad) read: Vision first, the gated Gemini second opinion, the outage marks, and
the NRIC lock (moved verbatim from ``vision.py``, audit sprint A3.1)."""

import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from ..genuineness.bands import keep_stored_authenticity
from ..read_errors import IC_SECOND_OPINION_ERROR, IC_SECOND_OPINION_UNTIL, is_ai_service_error
from .names import name_match, nric_match
from .ocr import _doc_usage_ctx
from .. import vision as _v   # seams resolve on the package: one patch target reaches every caller

logger = logging.getLogger(__package__)   # 'apps.scholarship.vision', one name as before the split


def _should_gemini_ic(result: dict, profile) -> bool:
    """Escalate to the Gemini second opinion only when the deterministic read is
    low-confidence: a core field is missing, OR it disagrees with the profile the
    student typed (a likely OCR misread, not necessarily a real mismatch). A clean
    read that matches the profile never escalates — keeping most uploads free."""
    if not getattr(settings, 'IC_GEMINI_FALLBACK_ENABLED', True):
        return False
    nric = (result.get('nric') or '').strip()
    name = (result.get('name') or '').strip()
    if not nric or not name:
        return True
    p_nric = (getattr(profile, 'nric', '') or '') if profile else ''
    p_name = (getattr(profile, 'name', '') or '') if profile else ''
    if p_nric and not nric_match(nric, p_nric):
        return True
    if p_name and name_match(name, p_name) == 'mismatch':
        return True
    return False


def _merge_ic_reads(det: dict, g: dict, profile) -> dict:
    """Fold the Gemini read into the deterministic one — conservatively. Gemini wins a
    CORE field (nric/name) only when it agrees with the profile and the deterministic
    read did not (or the deterministic read was empty); the soft address always prefers
    the cleaner Gemini value when present. So a confident deterministic match is never
    overridden by the model. #59: a parent's card passes ``parent_ic_reference`` (that parent's
    ``names``, ANY of which may agree), never the student's profile — same bar, the right person."""
    p_nric = (getattr(profile, 'nric', '') or '') if profile else ''
    p_names = [n for n in (getattr(profile, 'names', None) or [getattr(profile, 'name', '') or '']) if n] if profile else []
    out = dict(det)
    gn = (g.get('nric') or '').strip()
    if gn:
        if not out.get('nric'):
            out['nric'] = gn
        elif p_nric and nric_match(gn, p_nric) and not nric_match(out['nric'], p_nric):
            out['nric'] = gn   # Gemini recovered a digit the OCR misread
    gname = (g.get('name') or '').strip()
    if gname:
        if not out.get('name'):
            out['name'] = gname
        elif (any(name_match(gname, n) != 'mismatch' for n in p_names)
              and all(name_match(out['name'], n) == 'mismatch' for n in p_names)):
            out['name'] = gname
    gaddr = (g.get('address') or '').strip()
    if gaddr:
        out['address'] = gaddr   # cleaner read (no card labels / truncation)
    return out


# Supporting-document genuineness (str / birth_certificate / epf) now lives in
# genuineness/supporting_doc.py and is re-exported at the end of this module.


def run_vision_for_document(doc) -> dict:
    """
    Run Vision on an ``ApplicantDocument`` (expected ``doc_type='ic'``) and
    persist the result on the row. Returns the result dict. Never raises;
    failures land in ``vision_error`` and the doc still saves.

    When the deterministic read is low-confidence (see ``_should_gemini_ic``), a
    cost-gated Gemini second opinion re-reads the card image and is merged in.

    Flag-gated genuineness fingerprint (``DOC_GENUINENESS_CHECK_ENABLED``): a soft
    "does this look like a real MyKad?" multimodal read, stored in
    ``vision_fields['authenticity']`` (no migration). Never blocks.
    """
    from .. import usage
    _ctx = _doc_usage_ctx(doc)
    image = _v._fetch_image_bytes(doc.storage_path)
    used_gemini = False
    second, second_error = '', ''   # TD-390: the second opinion was 'ok' / failed on 'ours' / 'theirs'
    with _ctx:
        if image is None:
            result = {'nric': '', 'name': '', 'address': '', 'error': 'could not fetch image'}
        else:
            result = _v.extract_mykad(image, doc.content_type)   # Cloud Vision OCR (doc_extract)
            if not result.get('error'):
                profile = getattr(doc.application, 'profile', None)
                if _v._should_gemini_ic(result, profile):
                    with usage.usage_context(source='ic_fallback'):  # inherits org/app
                        g = _v._gemini_ic_second_opinion(image, doc.content_type)
                    if not g.get('_error'):
                        from ..income_engine import parent_ic_reference   # #59: a parent's card, its own person
                        ref = parent_ic_reference(doc) if getattr(doc, 'doc_type', '') == 'parent_ic' else profile
                        result = _v._merge_ic_reads(result, g, ref)
                        used_gemini, second = True, 'ok'
                    else:
                        second_error = g['_error']
                        second = 'ours' if is_ai_service_error(second_error) else 'theirs'
    prior = doc.vision_fields if isinstance(doc.vision_fields, dict) else {}
    had_read = not doc.vision_error and (doc.vision_nric or doc.vision_name)
    if had_read and ((second == 'ours' and prior.get('capture') == 'ai')
                     or (result.get('error') and prior.get(IC_SECOND_OPINION_ERROR))):
        # TD-390: a re-run during an outage never replaces a read the second opinion completed, and
        # a re-run of a half-read card that fails at Vision keeps the half it had (and its mark).
        logger.warning('run_vision: kept stored IC read for doc %s (re-run failed: %s)',
                       doc.id, second_error or result.get('error'))
        return {'nric': doc.vision_nric, 'name': doc.vision_name, 'address': doc.vision_address,
                'error': second_error or result.get('error'), 'stale_kept': True}
    doc.vision_nric = result['nric'] or ''
    doc.vision_name = result['name'] or ''
    doc.vision_address = result.get('address', '') or ''
    doc.vision_error = result['error'] or ''
    doc.vision_run_at = timezone.now()
    update_fields = ['vision_nric', 'vision_name', 'vision_address', 'vision_error', 'vision_run_at']
    vf = doc.vision_fields if isinstance(doc.vision_fields, dict) else {}
    vf_changed = False
    if image is not None and not result.get('error'):
        # Capture-confidence tag (mirrors the field-extracted docs): the MyKad NRIC/name is read by
        # deterministic Vision OCR unless the low-confidence Gemini second opinion was merged in.
        vf['capture'] = 'ai' if used_gemini else 'deterministic'
        vf_changed = True
        # TD-390: a REQUIRED second opinion that failed on OUR side leaves only half a read — mark it
        # (the gate says "service down", readers say "pending", the hourly sweep re-runs it); any
        # other outcome clears the mark. `ic_second_opinion` is the outcome the outage alert counts.
        if second == 'ours':
            vf[IC_SECOND_OPINION_ERROR] = second_error[:600]
            now = timezone.now()
            if not (vf.get(IC_SECOND_OPINION_UNTIL) or 0) > now.timestamp():   # absent or lapsed: a NEW
                vf[IC_SECOND_OPINION_UNTIL] = int((now + timedelta(hours=72)).timestamp())   # outage
        else:
            vf.pop(IC_SECOND_OPINION_ERROR, None)
            vf.pop(IC_SECOND_OPINION_UNTIL, None)
        if second:
            vf['ic_second_opinion'] = second
        else:
            vf.pop('ic_second_opinion', None)
    if image is not None and getattr(settings, 'DOC_GENUINENESS_CHECK_ENABLED', False):
        with usage.usage_context(application=getattr(doc, 'application', None), source='genuineness'):
            auth = _v.ic_genuineness(image, doc.content_type)
        if auth:
            vf['authenticity'] = auth
            vf_changed = True
    keep_stored_authenticity(doc, prior, vf)   # TD-407: the merge keeps it; say so when nothing fresh came
    if vf_changed:
        doc.vision_fields = vf
        update_fields.append('vision_fields')
    doc.save(update_fields=update_fields)
    try:
        _lock_nric_if_confirmed(doc)
    except Exception:               # noqa: BLE001 — an upload must survive a failed lock
        logger.exception('ic lock failed for document %s', getattr(doc, 'id', None))
    return result


def _lock_nric_if_confirmed(doc):
    """Take the IC lock the first time the card confirms what the student typed (2026-07-29).

    Sits at the END of the IC read so every route in — first upload, the cockpit's Re-run, the
    bulk re-extract — takes the lock at the same moment. The alternative was three call sites
    each remembering to, which is how the sponsor-membership gap happened a day earlier: a rule
    with no single home is a rule waiting to be forgotten at one of its edges.

    **Stored, one-way, never re-derived.** A lock recomputed on every page load would disappear
    the moment the student deleted the document that earned it — upload a matching card, lock,
    delete it, unlock, change the number. That is not a lock.

    Never raises. This runs inside the upload request, and nobody should lose an upload because
    we could not take a lock.
    """
    # A parent's card is uploaded through this same function (minor consent). It must never
    # lock the STUDENT's number — different person, different card.
    if getattr(doc, 'doc_type', '') != 'ic':
        return
    profile = getattr(getattr(doc, 'application', None), 'profile', None)
    if profile is None or profile.nric_verified:
        return          # already locked — one-way, so nothing to do and nothing to undo
    from .. import identity
    if not identity.locks_now(identity.compare(doc, profile)):
        return
    # Locking ARMS the partial unique index on nric (WHERE nric_verified). If another profile
    # already holds this number verified, the save would raise — and a student would lose their
    # upload over somebody else's duplicate. Leave it unlocked instead: verify-&-accept already
    # surfaces the clash to an admin as `nric_conflict`, which is where a human settles it.
    from apps.courses.models import StudentProfile
    clash = (StudentProfile.objects
             .filter(nric=profile.nric, nric_verified=True)
             .exclude(pk=profile.pk).exists())
    if clash:
        logger.warning('ic lock skipped — nric already verified on another profile (app=%s)',
                       getattr(doc, 'application_id', None))
        return
    profile.nric_verified = True
    profile.save(update_fields=['nric_verified'])
