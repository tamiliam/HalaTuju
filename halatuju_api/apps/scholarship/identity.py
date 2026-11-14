"""The IC lock — one rule, one home (2026-07-29).

**Why this module exists.** Whether a student's IC number is settled has to be answered in
three places at once: the profile screen (draw a padlock or an editable box), the write path
(refuse a change), and the moment the lock is first taken. Three copies of "is it confirmed?"
would drift — that is the standing lesson from the income gate, where "what counts as
evidence" lived in an assessment path and a submission path and the two disagreed for months.
So the rule lives here, is named, and every caller asks it.

**The rule** (owner, 2026-07-29): a student's IC number locks when their uploaded MyKad is
GENUINE, the number on it matches what they typed, and the name matches too. All three, and
only then. Until that moment they may correct it themselves.

Three deliberate choices inside that sentence, each easy to get wrong:

* **An unscored card is NOT genuine.** Elsewhere in this codebase an absent genuineness verdict
  fails OPEN (``income_engine`` treats an empty status as passing), and that is right for a soft
  signal an officer can overrule. This is not that: the lock is one-way, so "we could not check
  the card" must mean "not confirmed", never "confirmed". Same shape as the Layer 0 rule that an
  empty catalogue means NOT CONFIGURED rather than "requires nothing".
* **The name may differ by whole parts, never by spelling.** A missing middle name is the same
  person (``name_match`` → ``partial``); a one-letter difference might not be (→ ``mismatch``).
  There IS a tolerant matcher in this codebase — ``relationship_name_match``, which folds w↔v,
  doubled letters and a trailing h — built for cross-checking income documents. **Do not reach
  for it here.** It is deliberately kept off identity, on the reasoning that a lenient matcher
  can only ever weaken an identity check.
* **The number is exact.** ``nric_close`` (a single-digit edit) exists and is used to WORD the
  student's nudge more precisely. It must never widen the lock — its own docstring says so.

**The lock is STORED, never re-derived.** ``locks_now()`` answers "should it lock?", and the
caller writes ``nric_verified``. Recomputing it on every read would make the lock reversible by
deleting the evidence: upload a matching card, lock; delete the card, unlock; change the number.
A lock you can undo by removing the proof is not a lock.

**The name follows the card** (request #67 scope 3, 2026-11-14) — the second half of this module:
``align_name_to_ic`` makes the IC's name the profile name when that is safe, and
``name_change_allowed`` holds it there once the IC is locked. See the note above those functions.
"""
import logging
import re

from .genuineness.bands import canonical_status, stored_status
from .read_errors import IC_SECOND_OPINION_ERROR, ic_second_opinion_deferred
from .vision import canonical_name_tokens, name_match, nric_close, nric_match

# The name comparisons that mean "the same person". ``partial`` is one set being a strict
# subset of the other — a name typed shorter or longer than the card carries.
_SAME_PERSON = frozenset({'match', 'partial'})


def _authenticity_status(doc):
    """The stored genuineness verdict for a document, or '' when it was never scored."""
    return stored_status(getattr(doc, 'vision_fields', None)).strip()       # TD-293


def card_is_genuine(doc):
    """True only on a POSITIVE genuineness verdict.

    Folded through ``genuineness.bands.canonical_status`` rather than compared to a string: the
    IC scorer emits ``likely_genuine`` as well as ``genuine`` (32 and 34 of production's live
    cards respectively), and a bare ``== 'genuine'`` would silently exclude a third of them.
    The fold also maps the legacy words (``low_confidence``, ``wrong_type``, ``not_an_ic``), and
    returns ``''`` for a card that was never scored — which is NOT genuine, per the module note.
    """
    return canonical_status(_authenticity_status(doc), 'ic') == 'genuine'


def compare(doc, profile):
    """How the uploaded MyKad reads against what the student typed.

    Returns ``{'name': …, 'nric': …, 'genuine': bool, 'card_name': str, 'card_nric': str}``
    where each comparison is ``match`` / ``partial`` / ``mismatch`` / ``unknown`` (nothing to
    compare). ``nric`` additionally reports ``near`` — a single-digit difference — which exists
    ONLY so the student's nudge can say "differs by one digit" instead of something vague. It is
    not a softer kind of match and must never reach the lock decision.

    This is the one place the two sides are compared, so the padlock, the flag and the lock can
    never disagree about what the card says.
    """
    card_name = (getattr(doc, 'vision_name', '') or '').strip() if doc else ''
    card_nric = (getattr(doc, 'vision_nric', '') or '').strip() if doc else ''
    typed_name = (getattr(profile, 'name', '') or '').strip() if profile else ''
    typed_nric = (getattr(profile, 'nric', '') or '').strip() if profile else ''

    if card_name and typed_name:
        name = name_match(card_name, typed_name)
    else:
        name = 'unknown'

    if card_nric and typed_nric:
        if nric_match(card_nric, typed_nric):
            nric = 'match'
        elif nric_close(card_nric, typed_nric):
            nric = 'near'
        else:
            nric = 'mismatch'
    else:
        nric = 'unknown'
    if doc is not None and ic_second_opinion_deferred(doc):
        # TD-390: the card needed Gemini's second look and our outage skipped it — a differing value
        # read off half a read is not something to tell the student about. A match still locks.
        name = 'unknown' if name in ('partial', 'mismatch') else name
        nric = 'unknown' if nric in ('near', 'mismatch') else nric

    return {
        'name': name,
        'nric': nric,
        'genuine': bool(doc) and card_is_genuine(doc),
        'card_name': card_name,
        'card_nric': card_nric,
    }


#: TD-400 (A2.8a): the refusal when a parent's typed name / NRIC differs from a parent IC whose read
#: our outage left half done (TD-390). "Try later", never "doesn't match": it is not the family's slip.
GUARANTOR_IC_PENDING = 'parent_ic_service_down'


def guarantor_mismatch(parent_ic, name, nric):
    """Why the typed parent/guardian name and NRIC fail the parent IC that was read, or ``''``.

    The one comparison behind the minor's consent (``ConsentView.post``) and the bursary guarantor
    (``bursary.guarantor_identity_check``). Exact NRIC, ``name_match == 'match'``, as before. Within
    the TD-390 window a DIFFERING value read off half a read answers ``GUARANTOR_IC_PENDING`` instead
    of a mismatch — the same rule as ``compare``: it delays a signal, never passes one, and a match
    still passes. After the window the stored read counts as complete again."""
    if parent_ic.vision_nric and not nric_match(nric, parent_ic.vision_nric):
        why = 'parent_ic_nric_mismatch'
    elif parent_ic.vision_name and name_match(parent_ic.vision_name, name) != 'match':
        why = 'parent_ic_name_mismatch'
    else:
        return ''
    return GUARANTOR_IC_PENDING if ic_second_opinion_deferred(parent_ic) else why


def locks_now(comparison):
    """Should the IC lock, given ``compare()``'s answer? Genuine card, exact number, same person.

    Deliberately takes the comparison rather than the document, so the decision and the thing
    shown to the student are provably the same reading.
    """
    return (comparison['genuine']
            and comparison['nric'] == 'match'
            and comparison['name'] in _SAME_PERSON)


def flags(comparison):
    """What to tell the student, as codes the screen turns into copy.

    Anything the card and the typed value disagree about, whether or not it blocked the lock —
    including a ``partial`` name on a record that DID lock, because aligning it is still worth
    doing and nothing else will ever ask them to.

    ``unknown`` is never flagged: no card, or nothing read off it, is not a disagreement.
    """
    out = []
    if comparison['nric'] == 'near':
        out.append('nric_one_digit')
    elif comparison['nric'] == 'mismatch':
        out.append('nric_differs')
    if comparison['name'] == 'partial':
        out.append('name_incomplete')
    elif comparison['name'] == 'mismatch':
        out.append('name_differs')
    return out


# ── One name: align it to the IC, then hold it there (request #67 scope 3, 2026-11-14) ─────────
#
# The owner's rule (decisions D1-D6, 14 Nov 2026): the name read off the student's own MyKad becomes
# the ONE name. The truthfulness-declaration signature (``declaration_name``) is NEVER rewritten — it
# is a dated legal record — but ``profile.name`` follows the card, and once the IC lock is taken
# (``nric_verified``) the student may change the name only to something the card agrees with.
#
# Why here: the same question ("may this name stand?") is asked by the IC read, the /profile PUT,
# the apply-form sync and the submit-time signature promotion. Four copies would drift, exactly as
# the lock rule above would have. Both halves read the same card through ``latest_live_ic``.

_logger = logging.getLogger(__name__)

#: The outcomes of ``align_name_to_ic`` (the backfill command counts them; nothing else reads them).
ALIGNED = 'aligned'                  # profile.name rewritten to the card's name
ALREADY = 'already'                  # it already was the card's name: nothing to write
NOT_STUDENT_IC = 'not_student_ic'    # a parent's card, or not an IC at all: never the student's name
NO_PROFILE = 'no_profile'
NOT_LATEST = 'not_latest'            # an older or replaced card does not speak for the student
READ_NOT_CLEAN = 'read_not_clean'    # an errored read, or one missing / failing its second opinion
NRIC_DIFFERS = 'nric_differs'        # not exactly the typed number: maybe not this student's card
NO_NAME_MATCH = 'no_name_match'      # neither the typed name nor any signature is the card's name


def latest_live_ic(profile):
    """The student's own IC read that speaks for them now: their newest ``ic`` document, not
    replaced (``superseded_at``), with a name read off it. The same card ``/profile`` shows the
    flags for, so the padlock, the flags and the name lock read one card."""
    if profile is None or getattr(profile, 'pk', None) is None:
        return None
    from .models import ApplicantDocument
    return (ApplicantDocument.objects
            .filter(application__profile=profile, doc_type='ic', superseded_at__isnull=True)
            .exclude(vision_name='').order_by('-id').first())


def _same_text(a, b):
    """The stored name and a typed one are the same text: case, runs of spaces and the space a
    student leaves around a slash marker ("A/ P") are not changes (``StudentProfile.save`` stores
    every one of those the same way)."""
    def norm(s):
        return re.sub(r'\s*/\s*', '/', ' '.join(str(s or '').split())).upper()
    return norm(a) == norm(b)


def name_locked(profile):
    """Is the student's name held to their IC? Exactly when the IC lock is (D3: no new column) —
    the stored, one-way ``nric_verified``."""
    return bool(getattr(profile, 'nric_verified', False))


def name_change_allowed(profile, new_name):
    """May a STUDENT write ``new_name`` as their profile name? (D3.)

    Always, while the IC is unlocked, and always when the name is unchanged. Once locked, only a
    name that ``name_match == 'match'`` the latest live IC read — so a student can always set the
    card's own name, and anything else goes through support. No card, nothing read: refused (a
    lock with no card is an admin's lock, and the admin path is the way to change it).

    Callers: ``ProfileView.put`` (refuses 403 ``name_locked``), ``ProfileSyncView.post``,
    ``services.profile_sync.sync_profile_fields`` and the signature promotion in
    ``services.intake.create_application`` (those three keep the stored name silently). Admin and
    staff edit paths never ask."""
    if profile is None or _same_text(new_name, getattr(profile, 'name', '')):
        return True
    if not name_locked(profile):
        return True
    ic = latest_live_ic(profile)
    card = (getattr(ic, 'vision_name', '') or '').strip() if ic else ''
    return bool(card) and bool((new_name or '').strip()) and name_match(card, new_name) == 'match'


def read_is_clean(doc):
    """D2's "the read is clean": no read error, and no second opinion pending or failed (an outage
    mark, inside or past its window, or a second opinion that came back unusable). The stale-kept
    re-run never reaches the aligner (``run_vision_for_document`` returns before it)."""
    if (getattr(doc, 'vision_error', '') or '').strip():
        return False
    vf = getattr(doc, 'vision_fields', None)
    vf = vf if isinstance(vf, dict) else {}
    if vf.get(IC_SECOND_OPINION_ERROR) or ic_second_opinion_deferred(doc):
        return False
    return vf.get('ic_second_opinion') in (None, '', 'ok')


def _same_words(card_name, typed_name):
    """D2's name test: the card and the typed name carry the SAME canonical words (equal token
    sets; order and A/L / BIN markers aside), and ``name_match`` agrees (which keeps its TD-408
    reversed-patronymic guard). Stricter than ``name_match == 'match'`` on purpose: that also
    passes a word glued or split by OCR (MUHAMMAD AMIN against MUHAMMADAMIN), and an alignment
    must never rewrite a correctly typed name into the card's OCR spacing."""
    words = canonical_name_tokens(card_name)
    return (bool(words) and words == canonical_name_tokens(typed_name)
            and name_match(card_name, typed_name) == 'match')


def name_alignment(doc):
    """What D2 says about this card, WITHOUT writing: ``(outcome, card_name)``.

    Aligns only when it is safe — the student's own, newest live card; a clean read; the card's
    number exactly the typed one; and the card's name has exactly the SAME WORDS as the typed
    profile name or the signature on any of this profile's applications (``_same_words``).
    Anything less: no change."""
    if getattr(doc, 'doc_type', '') != 'ic':
        return NOT_STUDENT_IC, ''
    profile = getattr(getattr(doc, 'application', None), 'profile', None)
    if profile is None:
        return NO_PROFILE, ''
    latest = latest_live_ic(profile)
    if latest is None or latest.pk != getattr(doc, 'pk', None) or getattr(doc, 'superseded_at', None):
        return NOT_LATEST, ''
    card_name = (getattr(doc, 'vision_name', '') or '').strip()
    card_nric = (getattr(doc, 'vision_nric', '') or '').strip()
    if not card_name or not read_is_clean(doc):
        return READ_NOT_CLEAN, card_name
    if not nric_match(card_nric, getattr(profile, 'nric', '') or ''):
        return NRIC_DIFFERS, card_name
    typed = [(getattr(profile, 'name', '') or '').strip()]
    typed += list(profile.scholarship_applications.exclude(declaration_name='')
                  .values_list('declaration_name', flat=True))
    if not any(t and _same_words(card_name, t) for t in typed):
        return NO_NAME_MATCH, card_name
    if _same_text(card_name, getattr(profile, 'name', '')):
        return ALREADY, card_name
    return ALIGNED, card_name


def align_name_to_ic(doc, *, write=True, source='ic_read'):
    """D2: make the card's name the profile name when ``name_alignment`` says it is safe.

    The old value is kept on an INTERNAL ``name_aligned_to_ic`` activity row (``meta`` old/new, the
    same place a mentor change keeps names) and a log line with ids only. The signature is never
    touched. ``write=False`` answers the outcome and changes nothing (the backfill's dry run).
    Called by ``vision.ic.run_vision_for_document`` just before the IC lock (D6) and by the
    ``align_profile_names_to_ic`` command (D5). Returns the outcome code."""
    outcome, card_name = name_alignment(doc)
    if outcome != ALIGNED or not write:
        return outcome
    from django.db import transaction
    from . import activity
    from .models.activity import EVENT_NAME_ALIGNED_TO_IC
    application = doc.application
    profile = application.profile
    old = profile.name or ''
    with transaction.atomic():
        profile.name = card_name
        profile.save(update_fields=['name', 'updated_at'])     # save() upper-cases and tidies it
        activity.log_event(application, EVENT_NAME_ALIGNED_TO_IC, internal=True, meta={
            'old': old, 'new': profile.name, 'document_id': doc.pk, 'source': source})
    _logger.info('AUDIT name_aligned_to_ic profile_id=%s app_id=%s doc_id=%s source=%s',
                 profile.pk, application.pk, doc.pk, source)
    return outcome
