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


def is_pool_eligible(application):
    """A single application is poolable iff its SponsorProfile is anon-published
    AND it has an active share_with_sponsors consent."""
    sp = getattr(application, 'sponsor_profile', None)
    if sp is None or not sp.anon_published:
        return False
    return has_active_share_consent(application)


def eligible_pool_queryset(model):
    """All applications currently visible in the pool (anon-published + active
    share consent). ``model`` is ``ScholarshipApplication`` (passed in to avoid a
    circular import). Caller adds any sponsor-facing filters."""
    return (
        model.objects
        .filter(
            sponsor_profile__anon_published=True,
            consents__consent_type=SHARE_CONSENT_TYPE,
            consents__is_active=True,
        )
        .select_related('sponsor_profile', 'profile')
        .distinct()
    )
