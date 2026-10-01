"""TD-207 — does this request carry a FRESH password-recovery session for this account?

`AdminSetPasswordView` sets a password server-side with the service role, because the project
requires re-authentication for a client-side password change and neither an invited partner nor
somebody who forgot their password has a current one to give. It used to accept ONLY the invite
case (`must_change_password`), so "Forgot password" mailed a working link, opened a valid recovery
session, and then failed at the last click for every admin who had finished onboarding.

A recovery link IS the re-authentication in GoTrue's own model: following it proves control of
the mailbox. GoTrue records it in the access token's `amr` claim (Authentication Methods
References) as an entry `{"method": "recovery", "timestamp": <unix seconds>}`, and the entry
rides on every token of that session, refreshes included, with its ORIGINAL timestamp — so the
timestamp, not the token's age, says how long ago the mailbox was proved.

⚠ ALL THREE MUST HOLD, and each is pinned by its own test in `tests/test_admin_auth.py`:
  1. a `recovery` method in `amr` — an ordinary password, Google or magic-link session is not one
     (GoTrue's `IsRecovery()` also counts OTP and magic link; deliberately not here: those prove
     a login, not a request to change the password);
  2. that entry no older than `RECOVERY_WINDOW` — an old recovery session left open in a browser
     must not become a standing password-change bypass;
  3. the token's `email` equal to the account being set. This is LOAD-BEARING, not belt and
     braces: the `amr` entry proves control of the mailbox the recovery mail went to, and only
     the email match ties that mailbox to the account whose password is about to change.
The view also requires the caller to be an admin (a `PartnerAdmin` row on the real JWT subject,
review F3) — a student or sponsor following their own reset link never gets this far.
A plain-string `amr` entry (GoTrue accepts both shapes) carries no timestamp and so can never
prove freshness: it is refused.

The claims are read from `request.auth_claims`, which `SupabaseAuthMiddleware` sets ONLY after it
has verified the signature and audience. Nothing here decodes a token.
"""
from datetime import timedelta

from django.utils import timezone

#: How long after following the reset link the new password may be set.
RECOVERY_WINDOW = timedelta(minutes=15)
#: Clock skew tolerated between GoTrue and this service for a timestamp in the future.
_SKEW = timedelta(minutes=1)


def _latest_recovery_at(claims):
    """The newest `recovery` timestamp in the verified `amr` claim, as unix seconds, or None."""
    amr = claims.get('amr') if isinstance(claims, dict) else None
    stamps = []
    for entry in amr if isinstance(amr, list) else []:
        if isinstance(entry, dict) and entry.get('method') == 'recovery':
            stamp = entry.get('timestamp')
            if isinstance(stamp, (int, float)) and not isinstance(stamp, bool):
                stamps.append(stamp)
    return max(stamps) if stamps else None


def is_fresh_recovery_for(request, account_email, now=None):
    """True when the request's verified token proves a recovery of ``account_email`` within
    ``RECOVERY_WINDOW``. See the module docstring for the three conditions."""
    claims = getattr(request, 'auth_claims', None)
    if not isinstance(claims, dict):
        return False
    stamp = _latest_recovery_at(claims)
    if stamp is None:
        return False
    now = (now or timezone.now()).timestamp()
    if not (now - RECOVERY_WINDOW.total_seconds() <= stamp <= now + _SKEW.total_seconds()):
        return False
    token_email = (claims.get('email') or '').strip().lower()
    return bool(token_email) and token_email == (account_email or '').strip().lower()
