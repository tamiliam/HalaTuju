"""THE BURSARY SIGNING WINDOW — one definition, read by the signing views AND the guardian-contact freeze.

Request #26 (2026-10-05). `award_application` was `views._award_application`, a private helper
the guarantor-PIN views and the award views called. It is LIFTED here, byte-for-byte in its
query, so the rule "may this student's parent be sent a signing PIN right now?" has exactly one
home. `views.py` imports it back under its old private name, so every call site there is
unchanged.

WHY A SECOND READER NEEDED IT. The parent/guardian phone (`profile.guardians[0].phone`) is the
only number the signing PIN goes to (`bursary.guarantor_phone_for`). A student may correct that
number themselves (owner ruling R1) EXCEPT while a PIN could be sent to it (R2) — otherwise a
dishonest student could put their own number in and verify in the parent's place. "While a PIN
could be sent" must mean exactly what the PIN views mean by it, and a hand-copied
`status == 'awarded'` would drift from them the first time either changed (docs/lessons.md:
`adminLanding` duplicating `defaultRoute`). `test_guardian_contact.py` drives the real send view
across states and asserts the two agree.

WHAT THE WINDOW IS, in the code's own terms:
  * `BURSARY_AGREEMENT_ENABLED` is on — with it off, the PIN views refuse (`bursary_disabled`)
    and nobody is in the window. That is production today.
  * AND the student has an application with an OFFERED sponsorship — the award they have not yet
    accepted. Accepting is the in-session student + guarantor signature (`respond_to_award` →
    `bursary.sign_agreement`, which requires a FRESH PIN check); the sponsorship then leaves
    'offered', the PIN views answer `no_offer`, and the window is shut. The number that was
    verified is stamped on the application (`guarantor_phone`), so a later edit of the profile
    cannot rewrite what was checked.
"""
from django.conf import settings


def award_application(user_id):
    """The caller's application that currently has an OFFERED award (independent of
    the editable-funnel scoping — an awardable student may be at 'recommended')."""
    from .models import ScholarshipApplication
    return (
        ScholarshipApplication.objects
        .filter(profile_id=user_id, sponsorships__status='offered')
        .select_related('profile').distinct().first()
    )


def signing_enabled():
    """The bursary contract flag, read the way every signing path reads it."""
    return bool(getattr(settings, 'BURSARY_AGREEMENT_ENABLED', False))


def in_signing_window(user_id):
    """True when a signing PIN could be sent for this student RIGHT NOW: the flag is on AND
    they hold an offered award. Exactly the two refusals the PIN views make, in their order."""
    return signing_enabled() and award_application(user_id) is not None
