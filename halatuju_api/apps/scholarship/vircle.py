"""Vircle eWallet — the shared logic behind the setup email, the Action-Centre task, and the
relay sheet.

Vircle is the eWallet the bursary is paid through. The flow:

    email (install Vircle)  →  student confirms in the Action Centre  →  relay sheet  →  Vircle
                                                                                switches them on

**The confirmation is a CLAIM, not a verification.** Vircle gives us nothing back, so we know only
what the student tells us. Ground truth arrives when the first payment succeeds or bounces. No
function here may present a confirmation as "verified".

The mobile number the student gives is the ONLY join key between our record and their Vircle
account, which is why it is captured explicitly rather than assumed from the profile.
"""
from __future__ import annotations

import logging

from .resolution import VIRCLE_CODE, VIRCLE_SETUP_STATES
from .sheets import (STATUS_CONFIRMED, STATUS_NOT_EMAILED, STATUS_PARENT_ACCOUNT,
                     STATUS_PENDING, write_relay_sheet)

logger = logging.getLogger(__name__)

# Vircle's own rule, confirmed by the owner against the in-app screens: eligibility is by birth
# YEAR, not birthday — "you must be an Adult, 18 years and above" is applied as "born in this year
# or earlier". A student born later CANNOT create an account at all, so we must not email them an
# instruction they physically cannot follow.
VIRCLE_MAX_BIRTH_YEAR = 2008


def birth_year_from_nric(nric) -> int | None:
    """The birth year encoded in a Malaysian NRIC (``YYMMDD-PB-###G``), or None if unreadable.

    Only the first two digits are needed. The century is inferred the same way the rest of this
    codebase treats applicant NRICs: a two-digit year at or below the current decade's applicants
    is 2000s, otherwise 1900s. (An applicant to a school-leaver bursary is never a 1930s birth, so
    the boundary is not load-bearing — and erring towards 1900s only ever makes someone ELIGIBLE,
    never wrongly excluded.)
    """
    digits = ''.join(ch for ch in str(nric or '') if ch.isdigit())
    if len(digits) < 6:
        return None
    yy = int(digits[:2])
    return 2000 + yy if yy <= 30 else 1900 + yy


def can_register(application) -> bool:
    """Can this student hold a Vircle account in their OWN name today?

    False does NOT mean excluded. A student born after 2008 is paid through a parent: the parent
    registers the (adult) account and the student is added to it as a child. They still get the
    setup email — it carries that instruction and points them at help@ — and they still appear on
    the relay sheet, under their own status.

    Conservative on an unreadable/absent NRIC (returns True): we never quietly reroute someone we
    merely can't read, and the email tells every reader the birth-year rule anyway.
    """
    profile = getattr(application, 'profile', None)
    year = birth_year_from_nric(getattr(profile, 'nric', ''))
    if year is None:
        return True
    return year <= VIRCLE_MAX_BIRTH_YEAR


def raise_setup_task(application):
    """Put the Vircle confirmation task in the student's Action Centre. Idempotent.

    Called ONLY after the award email has actually been sent (see sponsorship.py + the two
    commands) — a task must never appear for a student who was never told what it's for. The task
    is still gated by VIRCLE_SETUP_ENABLED at read time, so creating it while the flag is off is
    harmless: it simply stays invisible until the flag flips.
    """
    from .models import ResolutionItem
    item, _ = ResolutionItem.objects.get_or_create(
        application=application, code=VIRCLE_CODE,
        defaults={'source': 'system', 'fact': 'other', 'kind': 'confirm', 'params': {}},
    )
    return item


def confirmation(application):
    """The student's Vircle confirmation item, or None if they haven't confirmed."""
    return application.resolution_items.filter(code=VIRCLE_CODE, status='resolved').first()


def _date(value):
    return value.strftime('%d/%m/%Y') if value else ''


def setup_task(application):
    """The Vircle task, whatever its state — or None if the student was never emailed. It is raised
    ONLY on a successful send, so its existence (and created_at) is our record of "we asked"."""
    return application.resolution_items.filter(code=VIRCLE_CODE).first()


def relay_bucket(application):
    """Which pile a student is in. The sheet no longer prints this (owner dropped the Status
    column) — it survives as the ROW ORDER, so the rows you must act on come first."""
    if confirmation(application) is not None:
        # A confirmation wins even for an under-18: if a parent registered and the student gave us
        # the mobile, that IS the account we relay.
        return STATUS_CONFIRMED
    if not can_register(application):
        return STATUS_PARENT_ACCOUNT
    if setup_task(application) is not None:
        return STATUS_PENDING
    return STATUS_NOT_EMAILED


def relay_row(application):
    """One sheet row: Application · Name · NRIC · Email · Emailed on · Confirmed on · Mobile ·
    eWallet ID.

    The two dates are load-bearing and mean DIFFERENT things when blank. Blank "Emailed on" = we
    never asked this student. Blank "Confirmed on" = they haven't answered. Reading one as the
    other is how someone gets chased who was never contacted — or, worse, is never chased at all.

    eWallet ID is the student's PRINCIPAL Vircle wallet id — the one we pay into and Vircle reports
    on (never the parent's supplementary/transfer-only wallet). It's the last GENERATED column;
    the owner's own columns (e.g. "Activated On") live to the right of it and are preserved on sync.
    """
    profile = getattr(application, 'profile', None)
    task = setup_task(application)
    done = confirmation(application)
    return [
        application.id,
        getattr(profile, 'name', '') or '',
        getattr(profile, 'nric', '') or '',
        application.notify_email or '',
        _date(getattr(task, 'created_at', None)),   # blank → never emailed
        _date(getattr(done, 'resolved_at', None)),  # blank → not yet confirmed
        (done.resolution_text or '') if done else '',
        application.vircle_id or '',                 # eWallet ID (principal) — column H
    ]


def relay_rows(applications):
    """Sheet rows for the cohort, ordered by AWARDED DATE — first come, first served (owner,
    2026-07-13).

    Deliberately NOT sorted by status. A status sort re-shuffles the whole sheet every time a
    student confirms, which would drag any notes the owner keeps in the columns to the RIGHT out of
    line with their student. Awarded-date order is append-only and stable: a new student lands at
    the bottom, and nobody else moves.

    An application with no awarded_at (shouldn't happen for this cohort) sorts last rather than
    crashing; ties break on id.
    """
    def key(app):
        awarded = getattr(app, 'awarded_at', None)
        return (awarded is None, awarded, app.id)
    return [relay_row(app) for app in sorted(applications, key=key)]


# ── 48h activation request ───────────────────────────────────────────────────
# Reads the SAME relay sheet BACK (the one net-new inbound read) to find accounts the student has
# installed (eWallet ID present) but that Vircle hasn't switched on yet — tracked by the owner's
# MANUAL "Activated On" column (I). That column is the prune signal: once the owner fills it, the
# account drops out of the request. Activation is never known to the app itself, so the sheet is
# the only source of truth for it.

def pending_activation_rows():
    """Accounts INSTALLED but NOT yet activated, read from the relay sheet: rows with an eWallet ID
    AND a blank 'Activated On'. Each → {name, nric, installed_on, phone, ewallet}. [] if unreadable.
    Columns are located by header name (case-insensitive) so a reorder can't silently misread."""
    from django.conf import settings
    from . import sheets
    values = sheets.read_sheet_values(getattr(settings, 'VIRCLE_SHEET_ID', ''), 'A1:I1000')
    if not values:
        return []
    header = [str(h).strip().lower() for h in values[0]]

    def idx(name):
        try:
            return header.index(name.lower())
        except ValueError:
            return None

    i_name, i_nric = idx('name'), idx('nric')
    i_installed = idx('confirmed on')                    # 'Installed Date' ← 'Confirmed on'
    i_phone = idx('mobile registered with vircle')
    i_ewallet, i_activated = idx('ewallet id'), idx('activated on')

    def cell(row, i):
        return (str(row[i]).strip() if (i is not None and i < len(row)) else '')

    out = []
    for row in values[1:]:
        ewallet = cell(row, i_ewallet)
        if ewallet and not cell(row, i_activated):       # installed, not activated
            out.append({
                'name': cell(row, i_name),
                'nric': cell(row, i_nric),
                'installed_on': cell(row, i_installed),
                'phone': cell(row, i_phone),
                'ewallet': ewallet,
            })
    return out


def activation_csv_text(rows):
    """The activation-request CSV — the owner's headers, one line per pending account."""
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['Name', 'NRIC', 'Installed Date', 'Phone number', 'eWallet ID'])
    for r in rows:
        # Excel-safe: a bare 13-digit id renders as 8.0004E+12; ="…" keeps it text.
        ewallet = f'="{r["ewallet"]}"' if r.get('ewallet') else ''
        w.writerow([r.get('name', ''), r.get('nric', ''), r.get('installed_on', ''),
                    r.get('phone', ''), ewallet])
    return buf.getvalue()


def awarded_applications():
    """Every student the bursary is (or is about to be) paying — the relay sheet's population."""
    from .models import ScholarshipApplication
    return (ScholarshipApplication.objects
            .filter(status__in=VIRCLE_SETUP_STATES)
            .select_related('profile')
            .prefetch_related('resolution_items')
            .order_by('id'))


def sync_relay_sheet(applications=None):
    """Rewrite the relay sheet from the database. Returns its URL, or None if Drive is
    unreachable/unconfigured (logged, never raised — the DB stays the record either way)."""
    apps = list(applications if applications is not None else awarded_applications())
    return write_relay_sheet(relay_rows(apps))
