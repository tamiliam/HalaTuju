"""Google Sheets seam for the Vircle relay sheet.

Mirrors ``meeting.py``: the same Workspace **service account with domain-wide delegation**
(``GOOGLE_MEET_SA_JSON``, impersonating ``MEET_ORGANISER_EMAIL``), the same best-effort
contract, the same lazy imports so the module loads without the Google client libraries.

What it writes: one sheet in ``My Drive / <VIRCLE_DRIVE_FOLDER>`` (default "03 Vircle") of the
impersonated account, listing every awarded student and whether they have confirmed their Vircle
account. That sheet is the list handed to Vircle to switch accounts on, and the chase list for
those who haven't done it.

Two rules this module exists to enforce:
  * **The database is the source of truth; the sheet is a generated mirror.** Every run REWRITES
    the value range, so the sheet can never drift, is safe to hand-edit (nothing reads it back),
    and can be deleted and regenerated. Never read a decision back out of it.
  * **The confirmation is a CLAIM, not a verification.** Vircle tells us nothing back, so no
    column here may be labelled "verified".

Scopes needed on the SA's domain-wide delegation (beyond Meet's ``calendar.events``):
``drive`` (find the folder, create the file) + ``spreadsheets`` (write the values). Without them
the API returns ``unauthorized_client`` — which this module logs and swallows, so a misconfigured
Workspace can never break the email send it rides along with.

NEVER call this with a live network in CI — tests patch ``_services`` (the single seam).
"""
from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)

# Drive: locate "03 Vircle" + create the spreadsheet inside it. Sheets: write the rows.
_SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets',
]

_HEADER = ['Application', 'Name', 'Email', 'Mobile registered with Vircle',
           'Confirmed on', 'Status']

# The three buckets a student can be in. Deliberately plain language: this sheet is read by us
# and by Vircle, not by the code.
STATUS_CONFIRMED = 'Confirmed by student'
STATUS_PENDING = 'Emailed, not confirmed'
# Born after 2008 → Vircle won't let them hold their own account. They are NOT excluded: a parent
# registers, the student is added to that account as a child, and they email help@ so we can
# arrange it. They still get the email (it carries that instruction) — this label just tells us
# to expect them via help@ rather than through the normal confirmation.
STATUS_PARENT_ACCOUNT = 'Parent must register — student added as a child (born after 2008)'


def sheets_enabled() -> bool:
    """True only when the Workspace credentials are present. (There is no separate on/off flag:
    if we can reach Drive, we mirror; if we can't, the DB is still the record.)"""
    return bool(getattr(settings, 'GOOGLE_MEET_SA_JSON', ''))


def _services():
    """Build authorised (drive, sheets) API clients impersonating the Workspace account.

    Returns ``(drive, sheets)``, or ``(None, None)`` if disabled / misconfigured / the client
    libraries are unavailable. This is the single seam tests patch.
    """
    if not sheets_enabled():
        return None, None
    try:
        import json

        from google.oauth2 import service_account  # type: ignore
        from googleapiclient.discovery import build  # type: ignore

        info = json.loads(settings.GOOGLE_MEET_SA_JSON)
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=_SCOPES,
        ).with_subject(settings.MEET_ORGANISER_EMAIL)
        # cache_discovery=False — no file cache on Cloud Run's read-only FS.
        drive = build('drive', 'v3', credentials=creds, cache_discovery=False)
        sheets = build('sheets', 'v4', credentials=creds, cache_discovery=False)
        return drive, sheets
    except Exception:
        logger.warning('Vircle sheet: could not build Drive/Sheets services', exc_info=True)
        return None, None


def _escape_query(name: str) -> str:
    """Escape a name for a Drive `q` string literal (a folder called O'Brien would break it)."""
    return name.replace('\\', '\\\\').replace("'", "\\'")


def _find_folder(drive, name):
    """The folder's id, or None. Searched in the impersonated account's own Drive."""
    q = (f"mimeType='application/vnd.google-apps.folder' and name='{_escape_query(name)}' "
         f"and trashed=false")
    res = drive.files().list(q=q, fields='files(id,name)', pageSize=10).execute()
    files = res.get('files') or []
    if not files:
        return None
    return files[0]['id']


def _find_or_create_sheet(drive, folder_id, title):
    """The relay spreadsheet's id — reused if it already exists in the folder, else created.
    Find-or-create (not create-always) so re-running never litters the folder with duplicates."""
    q = (f"mimeType='application/vnd.google-apps.spreadsheet' and "
         f"name='{_escape_query(title)}' and '{folder_id}' in parents and trashed=false")
    res = drive.files().list(q=q, fields='files(id,name)', pageSize=10).execute()
    files = res.get('files') or []
    if files:
        return files[0]['id']
    created = drive.files().create(
        body={'name': title,
              'mimeType': 'application/vnd.google-apps.spreadsheet',
              'parents': [folder_id]},
        fields='id',
    ).execute()
    return created['id']


def write_relay_sheet(rows):
    """Rewrite the Vircle relay sheet from ``rows`` (a list of lists, matching ``_HEADER``).

    Returns the spreadsheet URL on success, or None (logged, never raised) — a Drive failure must
    never break the caller, which is usually mid-email-send.

    The whole value range is CLEARED then rewritten, so a student who drops out of the cohort
    disappears from the sheet rather than lingering as a stale row.
    """
    drive, sheets = _services()
    if drive is None or sheets is None:
        return None
    try:
        sheet_id = getattr(settings, 'VIRCLE_SHEET_ID', '')
        if not sheet_id:
            folder = getattr(settings, 'VIRCLE_DRIVE_FOLDER', '03 Vircle')
            folder_id = _find_folder(drive, folder)
            if not folder_id:
                logger.warning(
                    'Vircle sheet: folder %r not found in the Drive of %s — create it, or set '
                    'VIRCLE_SHEET_ID to an existing sheet.',
                    folder, getattr(settings, 'MEET_ORGANISER_EMAIL', ''),
                )
                return None
            title = getattr(settings, 'VIRCLE_SHEET_NAME', 'Vircle relay')
            sheet_id = _find_or_create_sheet(drive, folder_id, title)

        values = [list(_HEADER)] + [list(r) for r in rows]
        sheets.spreadsheets().values().clear(
            spreadsheetId=sheet_id, range='A:Z', body={},
        ).execute()
        sheets.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range='A1',
            valueInputOption='RAW',
            body={'values': values},
        ).execute()
        return f'https://docs.google.com/spreadsheets/d/{sheet_id}/edit'
    except Exception:
        logger.warning('Vircle sheet: write failed', exc_info=True)
        return None
