"""The ONE home for the Google Workspace credentials that act as ``MEET_ORGANISER_EMAIL``.

Meet (``meeting.py``) and the Drive / Sheets seams (``sheets.py``) all act inside the Workspace as
the organiser mailbox, through **domain-wide delegation (DWD)** granted to the service account
``halatuju-meet``. This module builds those credentials; nothing else may.

**Keyless — the only way (TD-125, 2026-10-03; the key path deleted by TD-329, 2026-10-04).**
``settings.GOOGLE_DWD_SERVICE_ACCOUNT`` names the DWD service account (its email). The api's own
runtime identity (``google.auth.default()`` — on Cloud Run, the service's runtime SA) asks the IAM
Credentials API to sign the assertion AS that account (``google.auth.iam.Signer`` → ``signBlob``),
which needs ``roles/iam.serviceAccountTokenCreator`` on it. No private key exists anywhere in our
config, and the account's user-managed key was deleted in GCP on 2026-10-04. The DWD identity is
unchanged — the Workspace delegation entry is keyed on that account's client id. If the keyless
path ever breaks, recovery is the IAM grant (halatuju_api/CLAUDE.md, Environment Variables).

⚠ **THIS FUNCTION RAISES ON A BROKEN CONFIGURATION, AND THAT IS DELIBERATE.** Every caller builds
its credentials inside its own ``try/except Exception`` and turns a failure into its own
best-effort answer (``None`` / ``False`` / ``[]``), so nothing here can reach a booking, an email
send or a payment. Swallowing here instead would erase the difference ``sheets._sheet_values_or_none``
exists to keep: a read that FAILED is a finding (TD-242), a sheet that is empty is not. ``None`` is
returned only when the setting is absent — "not configured", which each caller has already
checked with ``dwd_available()``.

NEVER call this with a live network in CI — tests patch ``google.auth.default`` and the signer.
"""
from __future__ import annotations

from django.conf import settings

#: The Google OAuth token endpoint the DWD assertion is exchanged at.
_TOKEN_URI = 'https://oauth2.googleapis.com/token'

#: What the runtime identity needs to call the IAM Credentials API. On Cloud Run the runtime SA's
#: token already carries it; stated so a local ADC user credential is asked for the same thing.
_SIGNER_SCOPES = ['https://www.googleapis.com/auth/cloud-platform']


def _keyless_email() -> str:
    return (getattr(settings, 'GOOGLE_DWD_SERVICE_ACCOUNT', '') or '').strip()


def dwd_available() -> bool:
    """True when the keyless DWD account is configured. The "is Google wired?" question every
    feature gate asks — it says nothing about whether a call will SUCCEED."""
    return bool(_keyless_email())


def dwd_credentials(scopes):
    """Credentials impersonating ``settings.MEET_ORGANISER_EMAIL`` with exactly ``scopes``.

    Keyless (``GOOGLE_DWD_SERVICE_ACCOUNT``), else ``None``. Raises on a broken configuration —
    see the module docstring for why the CALLER owns the best-effort catch.
    """
    sa_email = _keyless_email()
    if not sa_email:
        return None
    # Lazy: no metadata-server probe at import, and none at all unless configured.
    import google.auth
    from google.auth import iam
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    source, _project = google.auth.default(scopes=_SIGNER_SCOPES)
    signer = iam.Signer(Request(), source, sa_email)
    return service_account.Credentials(
        signer, sa_email, _TOKEN_URI, scopes=list(scopes), subject=settings.MEET_ORGANISER_EMAIL,
    )
