"""Phase E2 — the anonymised sponsor discovery pool.

Pure, deterministic helpers for *who* is in the pool and *what non-identifying*
summary a sponsor may see. The hard safety boundary is here + in the allowlist
serializers: a sponsor never sees a name/NRIC/address/phone/email/school/photo.

Eligibility (decided with the user): a student appears in the pool when their
``SponsorProfile`` is **anon-published** AND the application has an **active
share_with_sponsors consent** (consent IS the opt-in). The whole pool is also
gated behind the ``SPONSOR_POOL_ENABLED`` flag (off until lawyer sign-off).
"""
import hashlib
import re

from .shortlisting import count_spm_a_grades

# Fixed salt so a student's public alias is stable across deploys but not a
# guessable/sequential id (avoids leaking pool size or application order).
_REF_SALT = 'halatuju-sponsor-pool-v1'

SHARE_CONSENT_TYPE = 'share_with_sponsors'


def pool_ref(application_id):
    """A stable, non-sequential, non-identifying alias for a pooled student,
    e.g. ``S-A3F9C1``. Derived from the application id via a salted hash."""
    digest = hashlib.sha256(f'{_REF_SALT}:{application_id}'.encode()).hexdigest()
    return f'S-{digest[:6].upper()}'


def academic_band(profile):
    """A coarse, non-identifying academic summary string for the card.
    SPM → A-count; STPM → PNGK. Returns '' when unknown."""
    if profile is None:
        return ''
    if (getattr(profile, 'exam_type', '') or '') == 'stpm':
        cgpa = getattr(profile, 'stpm_cgpa', None)
        return f'STPM · PNGK {cgpa}' if cgpa is not None else 'STPM'
    a = count_spm_a_grades(getattr(profile, 'grades', None) or {})
    return f"SPM · {a} A{'' if a == 1 else 's'}"


def has_active_share_consent(application):
    """True if an active share_with_sponsors consent exists for this application."""
    return application.consents.filter(
        consent_type=SHARE_CONSENT_TYPE, is_active=True,
    ).exists()


# F2/F9a: a coarse, non-identifying progress signal a sponsor sees for a student
# they fund. A student isn't "in progress" until they're actually sponsored; once
# sponsored, the band is DERIVED from their latest SemesterResult (F9a) — the
# uploaded slip stays myNADI-only, only this coarse band crosses. This is the single
# source of truth for the band (no stored column to drift). Reading the model
# directly (not via in_programme) keeps the allowlist serializer free of any
# in_programme import.
PROGRESS_STATES = ('on_track', 'semester_completed', 'needs_attention', 'graduated')

# A CGPA at or below this is the coarse "needs attention" threshold (Malaysian 4.0
# scale; 2.00 is the usual minimum good-standing line).
_NEEDS_ATTENTION_CGPA = 2.0

# Post-award lifecycle (roadmap docs/scholarship/post-award-lifecycle-plan.md):
# A funder has committed (or the student is in-programme / closed) → no longer in the sponsor
# DISCOVERY pool. A 'recommended' student is still poolable, awaiting a funder.
IN_PROGRAMME_OR_BEYOND = ('awarded', 'active', 'maintenance', 'closed')
# The funded in-programme states a progress band applies to (active = executed/pre-payout;
# maintenance = funded).
FUNDED_STATES = ('active', 'maintenance')


def derive_progress_state(application):
    """The student's progress band, or None when there's nothing to report yet
    (not in-programme). Bands (from the latest SemesterResult, non-identifying):
    ``graduated`` (the result marks graduation) > ``needs_attention`` (CGPA at/below
    2.00) > ``semester_completed`` (a CGPA is recorded) > ``on_track`` (in-programme,
    no result yet, or a result with no CGPA)."""
    if application is None or application.status not in FUNDED_STATES:
        return None
    latest = application.semester_results.order_by('-created_at').first()
    if latest is None:
        return 'on_track'
    if latest.graduated:
        return 'graduated'
    if latest.cgpa is not None and float(latest.cgpa) <= _NEEDS_ATTENTION_CGPA:
        return 'needs_attention'
    if latest.cgpa is not None:
        return 'semester_completed'
    return 'on_track'


def is_pool_eligible(application):
    """A single application is poolable iff its SponsorProfile is anon-published, it is in
    the QC-cleared ``recommended`` stage, AND it has an active share_with_sponsors consent.

    A student is sponsor-visible ONLY at ``recommended`` — the single stage between QC
    clearance and a funder committing. Before QC (under review / awaiting QC) they are held
    back even if a profile was generated; once funded (awarded/active/maintenance/closed)
    they have left the discovery pool. Publishing is bound to the QC-Accept transition
    (``publish_profile_to_pool``); this status check is the belt-and-suspenders read gate so a
    stray publish can never leak a not-yet-cleared case."""
    sp = getattr(application, 'sponsor_profile', None)
    if sp is None or not sp.anon_published:
        return False
    if application.status != 'recommended':
        return False
    return has_active_share_consent(application)


def publish_profile_to_pool(application):
    """Make a QC-cleared student's already-generated anon profile visible to sponsors.

    Publishing is bound to the QC-Accept transition (→ ``recommended``) — the SINGLE point a
    student becomes sponsor-visible. The reviewer's verdict only PREPARES the profile
    (``final_markdown``/``anon_markdown`` + the card blurb); it does NOT publish, so a case
    AWAITING QC is never shown to sponsors.

    Idempotent and PII-backstopped: a no-op when there is no profile, it is already published,
    or the redaction scan finds a leak (left unpublished for a super to regenerate). The card
    blurb is generated here only as a fallback (the reviewer's finalise usually made it).
    Returns True iff it published now."""
    from django.utils import timezone
    from .models import SponsorProfile
    from .profile_engine import generate_anon_blurb
    sp = SponsorProfile.objects.filter(application=application).first()
    if sp is None or not (sp.anon_markdown or '').strip() or sp.anon_published:
        return False
    if scan_profile_pii(sp.anon_markdown, getattr(application, 'profile', None)):
        return False
    fields = ['anon_published', 'anon_published_at', 'realtime_notified_at', 'updated_at']
    sp.anon_published = True
    sp.anon_published_at = timezone.now()
    sp.realtime_notified_at = None
    if not (sp.anon_blurb or '').strip():
        blurb = generate_anon_blurb(application, sp.anon_markdown)
        sp.anon_blurb = blurb if (blurb and not scan_anon_for_identifiers(
            blurb, getattr(application, 'profile', None))) else ''
        fields.append('anon_blurb')
    sp.save(update_fields=fields)
    return True


# ── TD-074b: pre-publish identifier backstop ─────────────────────────────────
# The anonymous blurb is GENERATED from non-identifying inputs, but it is fed the
# student's free-text narrative, so a name/school/place could slip through despite
# the prompt instruction. This scan is the STRUCTURAL gate: an admin cannot publish
# an anonymous profile that contains the student's own identifying tokens.

# Connectors/short tokens that are not identifying on their own.
_NAME_CONNECTORS = {'bin', 'binti', 'a/l', 'a/p', 's/o', 'd/o', 'al', 'ap', 'so', 'do'}
# Generic school-type words — common to thousands of schools, not identifying alone.
_GENERIC_SCHOOL = {
    'sekolah', 'menengah', 'kebangsaan', 'rendah', 'smk', 'smjk', 'sjk',
    'sjkc', 'sjkt', 'college', 'kolej', 'school', 'agama', 'teknik', 'vokasional',
    'islam', 'integrasi', 'harian', 'asrama', 'penuh',
}


def _distinct_tokens(value, stop):
    """Lowercased word tokens (>=3 chars) from a name/school, minus generic stop words."""
    out = []
    for raw in re.split(r'[\s/]+', (value or '').lower()):
        tok = raw.strip('.,()-\'"')
        if len(tok) >= 3 and tok not in stop:
            out.append(tok)
    return out


def scan_anon_for_identifiers(text, profile):
    """Return the list of identifying FIELDS that appear in the blurb (e.g. ['name',
    'city']). Empty when clean. STRICT anonymity — used by the graduation-message relay,
    where a student's note to sponsors must reveal nothing (name/school/city/NRIC/phone/
    email). (The sponsor PROFILE uses the looser ``scan_profile_pii`` below.)"""
    if not text or profile is None:
        return []
    low = text.lower()
    digits = re.sub(r'\D', '', low)
    found = []

    for tok in _distinct_tokens(getattr(profile, 'name', ''), _NAME_CONNECTORS):
        if re.search(rf'\b{re.escape(tok)}\b', low):
            found.append('name')
            break
    for tok in _distinct_tokens(getattr(profile, 'school', ''), _GENERIC_SCHOOL):
        if re.search(rf'\b{re.escape(tok)}\b', low):
            found.append('school')
            break

    city = (getattr(profile, 'city', '') or '').strip().lower()
    if len(city) >= 3 and re.search(rf'\b{re.escape(city)}\b', low):
        found.append('city')

    for field, attr, minlen in (('nric', 'nric', 6), ('phone', 'contact_phone', 7)):
        d = re.sub(r'\D', '', getattr(profile, attr, '') or '')
        if len(d) >= minlen and d in digits:
            found.append(field)

    email = (getattr(profile, 'contact_email', '') or '').strip().lower()
    if email and email in low:
        found.append('email')
    return found


def scan_profile_pii(text, profile):
    """Publish-time BACKSTOP for the sponsor PROFILE under the 2026-06-15 redaction policy:
    the profile is PII-redacted, NOT strictly anonymous — school + town/state are ALLOWED.
    So this blocks only the machine-checkable PII the policy forbids: the student's name,
    NRIC, phone and email. (Street address + photo are left to the generator's instruction —
    street tokens entangle with the now-allowed town/state, so flagging them here would
    false-positive.)"""
    if not text or profile is None:
        return []
    low = text.lower()
    digits = re.sub(r'\D', '', low)
    found = []

    for tok in _distinct_tokens(getattr(profile, 'name', ''), _NAME_CONNECTORS):
        if re.search(rf'\b{re.escape(tok)}\b', low):
            found.append('name')
            break
    for field, attr, minlen in (('nric', 'nric', 6), ('phone', 'contact_phone', 7)):
        d = re.sub(r'\D', '', getattr(profile, attr, '') or '')
        if len(d) >= minlen and d in digits:
            found.append(field)
    email = (getattr(profile, 'contact_email', '') or '').strip().lower()
    if email and email in low:
        found.append('email')
    return found


def eligible_pool_queryset(model):
    """The FUNDABLE pool — applications a sponsor may still fund (anon-published + active share
    consent + at the QC-cleared ``recommended`` stage). ``model`` is ``ScholarshipApplication``
    (passed in to avoid a circular import). This is the STRICT gate: the public waiting-count and
    the fundability read both use it, so a funded student is never double-funded nor counted as
    still-waiting. ``display_pool_queryset`` is the wider set the sponsor SEES."""
    return (
        model.objects
        .filter(
            sponsor_profile__anon_published=True,
            status='recommended',   # sponsor-visible ONLY at the QC-cleared stage (see is_pool_eligible)
            consents__consent_type=SHARE_CONSENT_TYPE,
            consents__is_active=True,
        )
        .select_related('sponsor_profile', 'profile')
        .distinct()
    )


# A just-funded student LINGERS in the sponsor's view as a read-only "Funded" card for
# POOL_FUNDED_GRACE_HOURS (owner 2026-07-21) — social proof of momentum — before dropping off.
# These are the funded lifecycle states the grace window shows (keyed on awarded_at, stamped by
# fund_student). 'closed' is excluded (a wrapped-up case, not a fresh win).
RECENTLY_FUNDED_STATES = ('awarded', 'active', 'maintenance')


def display_pool_queryset(model):
    """The DISPLAY pool — what an approved sponsor SEES: every fundable (``recommended``) student
    PLUS anyone funded within the last ``POOL_FUNDED_GRACE_HOURS`` (shown as a full-bar "Funded"
    card, not fundable). Same anon-published + active-share-consent privacy gate as the fundable
    set. The grace window is a pure query-time filter — a funded student simply falls out once the
    window passes, so nothing schedules or writes to "hide" them. Used by the pool LIST + DETAIL
    views only; fundability and the public count keep ``eligible_pool_queryset``."""
    from datetime import timedelta
    from django.conf import settings
    from django.db.models import Q
    from django.utils import timezone
    grace = getattr(settings, 'POOL_FUNDED_GRACE_HOURS', 48)
    cutoff = timezone.now() - timedelta(hours=grace)
    return (
        model.objects
        .filter(
            Q(status='recommended')
            | Q(status__in=RECENTLY_FUNDED_STATES, awarded_at__gte=cutoff),
            sponsor_profile__anon_published=True,
            consents__consent_type=SHARE_CONSENT_TYPE,
            consents__is_active=True,
        )
        .select_related('sponsor_profile', 'profile')
        .distinct()
    )
