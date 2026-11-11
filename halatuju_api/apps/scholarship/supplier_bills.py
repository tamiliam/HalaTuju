"""The supplier bills folder in Drive: the cron door's source for `import_invoices --drive` (TD-247, A4.5).

Before A4.5 the Workspace, Supabase, Twilio and Anthropic bills reached the cost ledger only when the
owner ran `import_invoices --dir` on a folder on their laptop. The monthly invoice job then refused a
month whose bills nobody had imported (`invoicing.readiness`, `supplier_missing`) — a safe failure, but a
manual feed. This module lets the running service read the same PDFs from a Drive folder, the way the
spending import already reads its exports (`sheets.spending_reports_in`).

The folder is named by the env var ``SUPPLIER_BILLS_FOLDER`` — a '/'-separated path in the Drive of the
impersonated Workspace account (``MEET_ORGANISER_EMAIL``), e.g. ``05 Billing/Supplier bills``. It is
read straight from the environment rather than from ``settings`` because the settings module belongs
to another lane in A4.5; moving it there later changes nothing else.

Read-only in effect: only ``files().list`` and ``get_media`` — the same SA and ``drive`` scope as
``sheets.fetch_drive_pdf`` (``drive.readonly`` is not in the SA's delegation allowlist).

NEVER call this with a live network in tests — they patch ``_drive`` (the single seam) or ``drive_pdfs``.
"""
from __future__ import annotations

import io
import logging
import os

log = logging.getLogger(__name__)

FOLDER_ENV = 'SUPPLIER_BILLS_FOLDER'


def folder_path() -> str:
    """The configured Drive folder path, or '' when it is not set (the door then refuses)."""
    return (os.environ.get(FOLDER_ENV) or '').strip()


def _drive():
    """A Drive client, or None when Workspace is not configured. The seam tests patch."""
    from . import sheets
    return sheets._drive_for_upload()


def drive_pdfs(path):
    """Every PDF directly inside the Drive folder ``path`` → ``[(name, bytes)]``, sorted by name.

    Returns None when the folder could not be READ (Workspace off, folder missing, any API error) —
    deliberately different from ``[]`` (the folder was read and holds no PDFs). Never raises; the
    failure is logged without any credential in it.
    """
    from . import sheets
    try:
        drive = _drive()
        if drive is None:
            return None
        folder_id = sheets._find_folder_path(drive, path)
        if not folder_id:
            log.warning('Supplier bills: folder path %r not found in Drive', path)
            return None
        q = f"'{folder_id}' in parents and mimeType='application/pdf' and trashed=false"
        listed, page = [], None
        while True:
            res = drive.files().list(q=q, fields='nextPageToken, files(id,name)',
                                     orderBy='name', pageSize=200, pageToken=page).execute()
            listed.extend(res.get('files') or [])
            page = res.get('nextPageToken')
            if not page:
                break
        from googleapiclient.http import MediaIoBaseDownload
        out = []
        for item in listed:
            buf = io.BytesIO()
            downloader = MediaIoBaseDownload(buf, drive.files().get_media(fileId=item['id']))
            done = False
            while not done:
                _, done = downloader.next_chunk()
            out.append((item.get('name') or item['id'], buf.getvalue()))
        return sorted(out, key=lambda pair: pair[0])
    except Exception as exc:  # best-effort read; the caller reports None as "could not read"
        # The class name only: an auth error's text is not echoed into the logs.
        log.warning('Supplier bills: could not read %r (%s)', path, exc.__class__.__name__)
        return None
