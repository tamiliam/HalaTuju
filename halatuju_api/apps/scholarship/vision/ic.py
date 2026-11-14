"""The IC (MyKad) read: Vision first, the gated Gemini second opinion, the outage marks, and
the NRIC lock (moved verbatim from ``vision.py``, audit sprint A3.1)."""

import hashlib
import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from ..genuineness.bands import keep_stored_authenticity
from ..read_errors import IC_SECOND_OPINION_ERROR, IC_SECOND_OPINION_UNTIL, is_ai_service_error
from .names import canonical_name_tokens, name_match, nric_match, same_raw_words
from .ocr import _doc_usage_ctx
from .. import vision as _v   # seams resolve on the package: one patch target reaches every caller

logger = logging.getLogger(__package__)   # 'apps.scholarship.vision', one name as before the split


def _short_of_typed(read_name: str, typed_name: str) -> bool:
    """#67 scope 3 (D4): the card's name read as a strict SUBSET of the typed one — fewer canonical
    words, every one of them in the typed name (``partial`` in the short direction). The shape of a
    two-line MyKad name whose second line the layout read refused (application 559)."""
    a, b = canonical_name_tokens(read_name), canonical_name_tokens(typed_name)
    return bool(a) and a < b and name_match(read_name, typed_name) == 'partial'


def _signatures(profile) -> list:
    """The truthfulness-declaration names this student signed (``declaration_name`` on each of
    their applications) — D4's second reference on their OWN card: a profile name edited short
    after signing must not make a short read look complete (#67 scope 3, review). [] for anything
    that is not a saved student profile (a parent's reference, a test stand-in)."""
    apps = getattr(profile, 'scholarship_applications', None) if getattr(profile, 'pk', None) else None
    if apps is None:
        return []
    try:
        return [n.strip() for n in apps.exclude(declaration_name='')
                .values_list('declaration_name', flat=True) if (n or '').strip()]
    except Exception:      # a reference lookup never costs the read
        logger.warning('ic read: could not list signatures', exc_info=True)
        return []


def _should_gemini_ic(result: dict, profile, own_card: bool = False) -> bool:
    """Escalate to the Gemini second opinion only when the deterministic read is
    low-confidence: a core field is missing, OR it disagrees with the profile the
    student typed (a likely OCR misread, not necessarily a real mismatch). A clean
    read that matches the profile never escalates — keeping most uploads free.

    ``own_card`` (the student's own ``ic``, never a parent's — D4, #67 scope 3): a read whose
    name is SHORTER than the typed name (a strict subset) escalates too, because a lost second
    line of the name reads exactly like that — and so does one SHORTER than a name the student
    signed (``_signatures``), however short the profile name was later edited. A read LONGER than
    the typed name does not."""
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
    if own_card and p_name and _short_of_typed(name, p_name):
        return True
    if own_card and any(_short_of_typed(name, sig) for sig in _signatures(profile)):
        return True
    return False


def _merge_ic_reads(det: dict, g: dict, profile, own_card: bool = False) -> dict:
    """Fold the Gemini read into the deterministic one — conservatively. Gemini wins a
    CORE field (nric/name) only when it agrees with the profile and the deterministic
    read did not (or the deterministic read was empty); the soft address always prefers
    the cleaner Gemini value when present. So a confident deterministic match is never
    overridden by the model. #59: a parent's card passes ``parent_ic_reference`` (that parent's
    ``names``, ANY of which may agree), never the student's profile — same bar, the right person.

    ``own_card`` (D4, #67 scope 3 — the student's own ``ic`` only): Gemini's name ALSO wins when it
    is an exact ``match`` for a reference name AND the deterministic read is a strict SUBSET of
    that name (``_short_of_typed``) — the short, ``partial`` read of application 559. Never when
    the deterministic read is LONGER than the typed name (a superset): a longer read is never
    replaced by a shorter one, whatever made the read escalate. A deterministic ``match`` still
    stands. Also on the own card: Gemini's name wins when it is the SAME WORDS as a name the
    student signed (``same_raw_words``) and the deterministic read is a strict subset of that
    signature — even if the read matches a profile name edited short after signing. Every branch
    lengthens the read; none shortens it. Parent cards (``own_card`` False) keep the rule above
    exactly."""
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
        elif (own_card
              and any(name_match(gname, n) == 'match' and _short_of_typed(out['name'], n)
                      for n in p_names)
              and all(name_match(out['name'], n) != 'match' for n in p_names)):
            out['name'] = gname   # D4: the whole name, where the deterministic read was short
        elif (own_card
              and any(same_raw_words(gname, sig) and _short_of_typed(out['name'], sig)
                      for sig in _signatures(profile))):
            out['name'] = gname   # D4: the signed name, where the read and the profile were short
    gaddr = (g.get('address') or '').strip()
    if gaddr:
        out['address'] = gaddr   # cleaner read (no card labels / truncation)
    return out


#: Where an IC read keeps the second reader's own answer (#67 scope 3, second pass L5): the hash of
#: the image it read, the model that answered and the prompt version, so an AUTOMATIC re-run of the
#: same image, to the same model with the same question, reuses it instead of paying again. A reused
#: answer is marked ``reused`` so the outage alert and the health light never count it as Gemini
#: answering (third pass L1).
IC_SECOND_READING = 'ic_second_reading'


def _image_hash(image: bytes) -> str:
    return hashlib.sha256(image).hexdigest()


def _current_ic_model() -> str:
    """The model an IC second opinion asks first now (the cascade's lead)."""
    from ..profile_engine import MODEL_CASCADE
    return MODEL_CASCADE[0] if MODEL_CASCADE else ''


def _stored_second_reading(doc, image: bytes):
    """The second reader's answer this document already holds for THIS image, model and prompt, or
    None. Only an answer that came back usable (``ic_second_opinion`` 'ok') is reused: an errored or
    deferred one (an outage mark) is asked again, and a card never asked (no stored answer, e.g. a
    card read before this was kept) asks as before. A model or prompt change (Gemini Phase 2, a
    prompt fix) asks again: the stored answer was the old model's to the old question."""
    vf = doc.vision_fields if isinstance(doc.vision_fields, dict) else {}
    stored = vf.get(IC_SECOND_READING)
    if (vf.get('ic_second_opinion') != 'ok' or vf.get(IC_SECOND_OPINION_ERROR)
            or not isinstance(stored, dict) or stored.get('image') != _image_hash(image)
            or not stored.get('model') or stored.get('model') != _current_ic_model()
            or stored.get('prompt') != _v.IC_SECOND_OPINION_PROMPT_VERSION):
        return None
    return {k: stored.get(k) or '' for k in ('nric', 'name', 'address')}


def _prior_reading(doc) -> dict:
    """The stored second reading, without its ``reused`` mark (a copy)."""
    vf = doc.vision_fields if isinstance(doc.vision_fields, dict) else {}
    stored = vf.get(IC_SECOND_READING)
    return {k: v for k, v in (stored if isinstance(stored, dict) else {}).items() if k != 'reused'}


# Supporting-document genuineness (str / birth_certificate / epf) now lives in
# genuineness/supporting_doc.py and is re-exported at the end of this module.


def run_vision_for_document(doc, *, fresh=False) -> dict:
    """
    Run Vision on an ``ApplicantDocument`` (expected ``doc_type='ic'``) and
    persist the result on the row. Returns the result dict. Never raises;
    failures land in ``vision_error`` and the doc still saves.

    When the deterministic read is low-confidence (see ``_should_gemini_ic``), a
    cost-gated Gemini second opinion re-reads the card image and is merged in.
    An automatic re-run reuses a stored answer for the same image, model and prompt
    (``_stored_second_reading``); ``fresh=True`` (an officer's Re-run, ``reextract_document``,
    a re-read or eval command) always asks again.

    Flag-gated genuineness fingerprint (``DOC_GENUINENESS_CHECK_ENABLED``): a soft
    "does this look like a real MyKad?" multimodal read, stored in
    ``vision_fields['authenticity']`` (no migration). Never blocks.
    """
    from .. import usage
    _ctx = _doc_usage_ctx(doc)
    image = _v._fetch_image_bytes(doc.storage_path)
    used_gemini = False
    second_reading = None           # L5: the second reader's usable answer, kept for a re-run
    second, second_error = '', ''   # TD-390: the second opinion was 'ok' / failed on 'ours' / 'theirs'
    with _ctx:
        if image is None:
            result = {'nric': '', 'name': '', 'address': '', 'error': 'could not fetch image'}
        else:
            result = _v.extract_mykad(image, doc.content_type)   # Cloud Vision OCR (doc_extract)
            if not result.get('error'):
                profile = getattr(doc.application, 'profile', None)
                own_card = getattr(doc, 'doc_type', '') == 'ic'   # D4: the student's own card only
                if _v._should_gemini_ic(result, profile, own_card=own_card):
                    # L5: an automatic re-run of the same image reuses the answer it already paid
                    # for (same model, same question); a deliberate re-read asks again.
                    g = None if fresh else _stored_second_reading(doc, image)
                    reused = g is not None
                    if g is None:
                        with usage.usage_context(source='ic_fallback'):  # inherits org/app
                            g = _v._gemini_ic_second_opinion(image, doc.content_type)
                    if not g.get('_error'):
                        if reused:      # the stored answer as it was, its model and prompt kept
                            second_reading = {**_prior_reading(doc), 'reused': True}
                        else:
                            second_reading = {k: (g.get(k) or '') for k in ('nric', 'name', 'address')}
                            second_reading.update(image=_image_hash(image), model=g.get('_model') or '',
                                                  prompt=_v.IC_SECOND_OPINION_PROMPT_VERSION)
                        from ..income_engine import parent_ic_reference   # #59: a parent's card, its own person
                        ref = parent_ic_reference(doc) if getattr(doc, 'doc_type', '') == 'parent_ic' else profile
                        result = _v._merge_ic_reads(result, g, ref, own_card=own_card)
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
        if second_reading is not None:
            vf[IC_SECOND_READING] = second_reading
        else:
            vf.pop(IC_SECOND_READING, None)
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
    # D6 (#67 scope 3): align the name to the card FIRST, so the lock below compares the card with
    # the name it will hold. Two separate never-raise blocks: a failed alignment never costs the
    # lock. A STAGED upload is not the live card yet, so it aligns on promotion instead
    # (``upload_read.judge``); a card read in place (Re-run, re-extract) aligns here.
    try:
        from .. import identity
        identity.align_name_to_ic(doc)          # a parent's card is refused inside (NOT_STUDENT_IC)
    except Exception:               # an upload must survive a failed alignment
        logger.exception('ic name alignment failed for document %s', getattr(doc, 'id', None))
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
