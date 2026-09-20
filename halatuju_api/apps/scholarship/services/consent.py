"""
Consent, minor detection from the NRIC, and post-award onboarding.

Moved here VERBATIM from `apps/scholarship/services.py` at code health H15 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from django.utils import timezone

from ..models import Consent, OnboardingResponse
from .constants import ONBOARDING_CONSENT_TYPE
from .errors import OnboardingError

# ── Consent / minor logic (Sprint 5a, hardened in S17) ──────────────────

# DRAFT — replace the version string when the lawyer-reviewed consent text lands.
# S19 (2026-05-29) — bumped to 2026-draft-3. The minor flow now interpolates
# student name/NRIC/pronoun into the consent body, captures the guardian's own
# NRIC, hard-gates on name+NRIC match against parent_ic OCR, and refines the
# relationship list (older_sibling → brother+sister; other_relative → relative).
# 0 existing consents on prod at bump time, so this is purely forward-looking.
# 2026-draft-6 (2026-07-22): the share-with-sponsors wording was CORRECTED — it promised away more
# than the platform does. Sponsors never receive documents, and what they see is an anonymised
# allowlist (no name/NRIC/photo/address/contact, for the student or the parents). The new text says
# so plainly. NARROWER than draft-5, so consents already given under the old wording permitted MORE
# than we do and need no re-consent; the version on each record still shows which wording was agreed.
CONSENT_VERSION = '2026-draft-7'  # draft-5 was bumped for the F9a promotional_use consent (18+ only)
# draft-7 (2026-07-26) is the first WIDENING: it adds what a sponsor sees DURING sponsorship
# (academic progress — already live — and how the bursary was spent). Every earlier version
# narrowed or held steady, so no version until now needed re-consent. This one does: an existing
# consenter has not agreed to the added disclosure. See docs/scholarship/consent-draft-7-proposal.md.
# ONE version is DISPLAYED (owner decision 2026-07-26): both the consent form and the read-only
# "What you agreed to" panel render the current wording, so an earlier consenter sees today's text —
# for draft-7 that is slightly broader than the one they gave. Per-version archived bodies were built
# and then removed as complexity buying a panel nuance rather than a real protection; questions are
# handled by hand. Sponsor visibility is likewise NOT gated on version (`pool.has_active_share_consent`
# checks type + is_active only), so a new disclosure reaches every consenter once it ships — that is
# the owner's call to make per feature, not something this constant enforces. See TD-166.


# S17/S19 — structured guardian relationship codes. Father/mother only need
# the parent's IC; everyone else also needs a guardianship_letter (pragmatic:
# parent's authorisation letter OR court-issued guardianship order — both
# accepted, the lawyer call). 'Other' was intentionally excluded.
_PARENT_RELATIONSHIPS = frozenset({'father', 'mother'})


def needs_guardianship_letter(relationship: str) -> bool:
    """True iff the relationship requires the additional guardianship_letter
    document on top of the parent_ic upload. Father/mother only need the IC;
    legal_guardian / grandparent / brother / sister / relative need both."""
    return bool(relationship) and relationship not in _PARENT_RELATIONSHIPS


# S19 — Malaysian NRIC last digit encodes sex: odd = male, even = female.
# Used to interpolate the right pronoun into the consent text without asking
# the student to pick again (the profile.gender field exists, but deriving
# from NRIC keeps the consent text self-consistent with the IC the parent
# is signing about — no possibility of a mismatch between "his/her" and the
# IC the admin reviews).
def gender_from_nric(nric: str):
    """Return 'male', 'female', or None when the NRIC is unparseable."""
    digits = ''.join(c for c in (nric or '') if c.isdigit())
    if len(digits) < 12:
        return None
    last = int(digits[-1])
    return 'male' if last % 2 == 1 else 'female'


def age_from_nric(nric):
    """Best-effort age from a Malaysian NRIC (YYMMDD-PB-###G). None if unparseable."""
    digits = ''.join(c for c in (nric or '') if c.isdigit())
    if len(digits) < 6:
        return None
    from datetime import date
    yy, mm, dd = int(digits[0:2]), int(digits[2:4]), int(digits[4:6])
    today = date.today()
    century = 2000 if (2000 + yy) <= today.year else 1900
    try:
        dob = date(century + yy, mm, dd)
    except ValueError:
        return None
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def is_minor(profile):
    """True if the profile's NRIC indicates an age under 18."""
    age = age_from_nric(getattr(profile, 'nric', '') if profile else '')
    return age is not None and age < 18


def record_consent(application, *, consent_type, locale, granted_by,
                   guardian_name, guardian_relationship, ip, guardian_nric=''):
    """Record a consent, superseding any prior active consent of the same type."""
    Consent.objects.filter(
        application=application, consent_type=consent_type, is_active=True,
    ).update(is_active=False)
    return Consent.objects.create(
        application=application,
        consent_type=consent_type,
        version=CONSENT_VERSION,
        locale=locale if locale in ('en', 'ms', 'ta') else 'en',
        granted_by=granted_by,
        guardian_name=guardian_name,
        guardian_relationship=guardian_relationship,
        guardian_nric=guardian_nric,
        ip_address=ip,
    )


def complete_onboarding(application, *, answers=None, locale='en', ip=None):
    """B40 Phase E/F (F8a): the student finishes post-award onboarding.

    Records the ``student_onboarding_ack`` consent (granted_by='self' — the award
    itself was accepted earlier, with the guardian gate for minors), stores the
    questionnaire answers on the (created-or-updated) OnboardingResponse, and stamps
    ``onboarded_at`` — the hard gate the disbursement flow checks. Re-running updates
    the answers and re-stamps (idempotent enough for a "save" button).

    Onboarding only makes sense once the award is accepted + executed, so it requires the
    application to be funded ('active' or 'maintenance'); else raises ``OnboardingError('not_awarded')``.
    """
    if application.status not in ('active', 'maintenance'):
        raise OnboardingError('not_awarded')
    consent = record_consent(
        application, consent_type=ONBOARDING_CONSENT_TYPE, locale=locale,
        granted_by='self', guardian_name='', guardian_relationship='', ip=ip,
    )
    response, _ = OnboardingResponse.objects.update_or_create(
        application=application,
        defaults={'answers': answers or {}, 'consent': consent},
    )
    application.onboarded_at = timezone.now()
    application.save(update_fields=['onboarded_at'])
    return response
