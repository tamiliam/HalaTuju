"""Reviewer-profile onboarding gate (2026-07-15).

A newly-invited reviewer lands on /admin/profile and is held there until their COMPULSORY
profile fields are filled, so we never assign a case to a reviewer with no credentials/contact
on file. The owner's compulsory set: professional credentials (qualification, university,
graduation year, field of study) + at least one language fluency + a phone number. The
reviewer's NAME (on PartnerAdmin) is compulsory too.

Reviewer-only: `role='reviewer'` is the only role that sees the reviewer-profile cards on
/admin/profile, so it's the only role the gate applies to. super / qc / viewer / partner / admin
are always complete (nothing to fill) — the flag is True for them.

`reviewer_profile_complete` is the single source of truth: surfaced on GET /api/v1/admin/role/ as
`reviewer_profile_complete`, which the login/callback landing + the admin layout guard branch on.
The FE mirrors REQUIRED_* only to paint `*` markers + list what's missing; this backend flag is the
real gate.
"""

# Compulsory text fields on ReviewerProfile (blank/'' = not filled).
REQUIRED_TEXT_FIELDS = ('highest_qualification', 'university', 'field_of_study', 'phone')
# The three language-fluency fields. '' ("None") is a legitimate per-language answer that is
# indistinguishable from "unset", so we require BREADTH — at least one language the reviewer can
# actually review in — rather than all three being non-empty (which would trap a monolingual
# reviewer who can't mark the others "None").
LANG_FIELDS = ('english_fluency', 'bm_fluency', 'tamil_fluency')
SPEAKS = ('conversational', 'fluent')


def reviewer_profile_complete(admin):
    """True unless `admin` is a reviewer whose compulsory profile fields are not all filled.

    Non-reviewers are always True (the gate is reviewer-only). A reviewer with no ReviewerProfile
    row yet, a blank name, any missing compulsory credential/phone, or no spoken language → False.
    """
    # Effective role, mirroring AdminRoleView: a super's `role` column defaults to 'reviewer', so
    # gate on the is_super bridge first (a super is never held on the profile page).
    if admin is None or getattr(admin, 'is_super', False):
        return True
    if getattr(admin, 'role', '') != 'reviewer':
        return True
    if not (getattr(admin, 'name', '') or '').strip():
        return False
    from .models import ReviewerProfile
    rp = ReviewerProfile.objects.filter(partner_admin=admin).first()
    if rp is None:
        return False
    if not rp.graduation_year:
        return False
    if any(not (getattr(rp, f) or '').strip() for f in REQUIRED_TEXT_FIELDS):
        return False
    if not any(getattr(rp, f) in SPEAKS for f in LANG_FIELDS):
        return False
    return True
