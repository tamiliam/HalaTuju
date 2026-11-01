"""What the student has ALREADY done towards signing her bursary agreement, read back for the award page
(Mobile M4, owner ruling 2026-11-01) — so a reload (an iOS tab kill) does not make her retake the
comprehension quiz or send her parent a second, paid SMS.

Its own module only because ``bursary.py`` is on the oversize ledger (code health: split first). The two
rules it reads stay in ``bursary`` — this module states nothing of its own.
"""
from .bursary import guarantor_phone_for, guarantor_phone_verification_fresh, same_phone


def signing_progress(application, template):
    """READ-ONLY, and each flag is EXACTLY the rule `bursary.sign_agreement` enforces — the page
    skipping a step can never let a signature through that the server refuses:

      * ``comprehension_passed`` — the quiz was passed on THIS template (`comprehension_stale`);
      * ``guarantor_phone_verified`` — the PIN check is inside its freshness window AND vouched for
        the number on file now (`guarantor_phone_unverified` / `guarantor_phone_changed`).

    Both go False on their own: a redeployed template, a stale stamp, a corrected number."""
    phone_now = guarantor_phone_for(application)
    return {
        'comprehension_passed': bool(template is not None
                                     and application.comprehension_template_id == template.id),
        'guarantor_phone_verified': bool(phone_now
                                         and guarantor_phone_verification_fresh(application)
                                         and same_phone(application.guarantor_phone, phone_now)),
    }
