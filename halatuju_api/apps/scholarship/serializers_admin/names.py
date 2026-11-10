"""Display names for the admin views: the reviewer name looked up by email (PartnerAdmin), the applicant full name and the verified email."""

from apps.courses.utils import tidy_parentage_marker


def _admin_name_by_email(email):
    """Resolve a stored reviewer email → their full name (for the audit lines).
    Returns '' if no match (the cockpit then falls back to showing the email)."""
    email = (email or '').strip()
    if not email:
        return ''
    from apps.courses.models import PartnerAdmin
    return PartnerAdmin.objects.filter(email__iexact=email).values_list('name', flat=True).first() or ''


def _full_name(application):
    """The applicant's full legal name, UPPER-CASED for the admin views (students
    type their signature inconsistently — some lowercase). Prefer the declaration
    signature (typed at submit, e.g. 'SHARMILA A/P SANGGAR') over profile.name —
    the latter is often the Google display name / handle ('Sharmila 1204').

    ⚠ THIS READS THE SIGNATURE, SO NORMALISING `profile.name` DOES NOT REACH THIS SURFACE.
    Application #20 typed 'SHARVANI A/ P KANAGEVELLU'; her canonical name was corrected to the
    MyKad spelling on 2026-07-30 and the cockpit header still showed the stray space, because
    the signature wins here by design. The signature is a dated legal record and stays verbatim
    in the database — so the marker is tidied at DISPLAY time instead, alongside the upper-casing
    this function already does for the same reason (students type it inconsistently).
    Marker-only: it cannot alter a letter or the spacing between name words."""
    declared = (getattr(application, 'declaration_name', '') or '').strip()
    name = declared or (getattr(application.profile, 'name', '') if application.profile else '')
    return tidy_parentage_marker(name.upper())


def _verified_email(application):
    """The applicant's VERIFIED email, for admin display. A typed contact email
    is only trusted once the student clicks "Verify" (contact_email_verified);
    until then we show the Google/Supabase login email, which is always verified.
    Returns '' if neither is available (admin then sees a dash) — we never show an
    unverified address here. NOTE: `notify_email` is deliberately NOT a fallback —
    it captures the comms email at submit and CAN be a custom unverified one."""
    p = getattr(application, 'profile', None)
    if p is None:
        return ''
    if p.contact_email and p.contact_email_verified:
        return p.contact_email
    # Fall back to the verified login email from Supabase auth.users. The admin is
    # the caller here (not the student), so the login email isn't on the JWT — we
    # look it up by the profile's supabase_user_id. One query, detail view only.
    if getattr(p, 'supabase_user_id', None):
        try:
            from apps.courses.views_admin import _fetch_auth_data
            auth = _fetch_auth_data([p.supabase_user_id], purpose='the applicant login email'
                                    ).get(p.supabase_user_id, {})
            login_email = (auth.get('email') or '').strip()
            if login_email:
                return login_email
        except Exception:  # pragma: no cover - auth.users absent in unit-test DB
            pass
    return ''
