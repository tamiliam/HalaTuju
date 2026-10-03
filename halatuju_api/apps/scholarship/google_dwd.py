"""The ONE home for the Google Workspace credentials that act as ``MEET_ORGANISER_EMAIL``.

Meet (``meeting.py``) and the Drive / Sheets seams (``sheets.py``) all act inside the Workspace as
the organiser mailbox, through **domain-wide delegation (DWD)** granted to the service account
``halatuju-meet``. This module builds those credentials; nothing else may.

Two ways to sign the DWD assertion (TD-125, 2026-10-03):

  * **Keyless — the target.** ``settings.GOOGLE_DWD_SERVICE_ACCOUNT`` names the DWD service account
    (its email). The api's own runtime identity (``google.auth.default()`` — on Cloud Run, the
    service's runtime SA) asks the IAM Credentials API to sign the assertion AS that account
    (``google.auth.iam.Signer`` → ``signBlob``), which needs ``roles/iam.serviceAccountTokenCreator``
    on it. No private key exists anywhere in our config. The DWD identity is unchanged — the
    Workspace delegation entry is keyed on that account's client id, so the Workspace needs no edit.
  * **The key — DEPRECATED.** ``settings.GOOGLE_MEET_SA_JSON`` holds the account's private-key
    JSON. Kept during the transition so a rollback is one env var; removed once production reads
    the keyless path (see the register for the removal entry).

The keyless setting WINS when both are set.

⚠ **THIS FUNCTION RAISES ON A BROKEN CONFIGURATION, AND THAT IS DELIBERATE.** Every caller builds
its credentials inside its own ``try/except Exception`` and turns a failure into its own
best-effort answer (``None`` / ``False`` / ``[]``), so nothing here can reach a booking, an email
send or a payment. Swallowing here instead would erase the difference ``sheets._sheet_values_or_none``
exists to keep: a read that FAILED is a finding (TD-242), a sheet that is empty is not. ``None`` is
returned only when neither setting is present — "not configured", which each caller has already
checked with ``dwd_available()``.

NEVER call this with a live network in CI — tests patch ``google.auth.default`` and the signer.
"""
from __future__ import annotations

from django.conf import settings

#: The Google OAuth token endpoint the DWD assertion is exchanged at (what the key file's own
#: ``token_uri`` says; the keyless path has no file to read it from).
_TOKEN_URI = 'https://oauth2.googleapis.com/token'

#: What the runtime identity needs to call the IAM Credentials API. On Cloud Run the runtime SA's
#: token already carries it; stated so a local ADC user credential is asked for the same thing.
_SIGNER_SCOPES = ['https://www.googleapis.com/auth/cloud-platform']


def _keyless_email() -> str:
    return (getattr(settings, 'GOOGLE_DWD_SERVICE_ACCOUNT', '') or '').strip()


def _key_json() -> str:
    return getattr(settings, 'GOOGLE_MEET_SA_JSON', '') or ''


def dwd_available() -> bool:
    """True when either way of acting as the organiser is configured. The "is Google wired?"
    question every feature gate asks — it says nothing about whether a call will SUCCEED."""
    return bool(_keyless_email() or _key_json())


def dwd_credentials(scopes):
    """Credentials impersonating ``settings.MEET_ORGANISER_EMAIL`` with exactly ``scopes``.

    Keyless (``GOOGLE_DWD_SERVICE_ACCOUNT``) first, then the deprecated key
    (``GOOGLE_MEET_SA_JSON``), else ``None``. Raises on a broken configuration — see the module
    docstring for why the CALLER owns the best-effort catch.
    """
    subject = settings.MEET_ORGANISER_EMAIL
    sa_email = _keyless_email()
    if sa_email:
        # Lazy: no metadata-server probe at import, and none at all unless this branch is taken.
        import google.auth
        from google.auth import iam
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account

        source, _project = google.auth.default(scopes=_SIGNER_SCOPES)
        signer = iam.Signer(Request(), source, sa_email)
        return service_account.Credentials(
            signer, sa_email, _TOKEN_URI, scopes=list(scopes), subject=subject,
        )
    key = _key_json()
    if key:
        import json

        from google.oauth2 import service_account

        return service_account.Credentials.from_service_account_info(
            json.loads(key), scopes=list(scopes),
        ).with_subject(subject)
    return None
