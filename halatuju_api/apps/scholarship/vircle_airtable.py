"""Vircle Airtable integration — we tell Vircle WHO, Vircle tells us the WALLET.

Why this exists (2026-08-27 → 2026-09-09): the student used to TYPE their eWallet ID into the
Action Centre, copying a number Vircle already holds. Every wallet-ID defect this platform has
had — the three DuitNow truncations (2026-07-29), the 4-digit box that could not hold the rolled-
over `800040018xxxx` block, Revina's dropped digit — was a corruption of that copy. Vircle now
runs an Airtable of bursary recipients and agreed (Gokula, 2026-09-08/09) to a two-webhook flow:

  OUTBOUND  student confirms "installed" in the Action Centre
            → we POST {Name, NRIC, Type} to Vircle's Airtable inbound webhook
              (their guide: Student_Bursary_Webhook_Integration_Guide, 2026-09; Type is
              "Principal", or "Supplementary" when the student registers as a CHILD — Gokula
              confirmed that mapping, which is exactly our `vircle.can_register` birth-year rule)
  INBOUND   Vircle's update automation POSTs the row back to us when the wallet id / activation
            lands → we store `vircle_id` + `vircle_activated_at`.

Rules that must not be "tidied":
  * The outbound push is BEST-EFFORT and can never fail the student's own confirmation — the
    same fault-injection contract as the usage meter. A failed push is logged and recorded on
    the resolution item's params; the 48h activation email (still running in V1) is the backstop.
  * The inbound write is guarded by `payments.valid_vircle_id` and NEVER overwrites a stored id.
    A mismatch is logged loudly and left for a human — an automated overwrite of the field that
    decides where money goes is how a wrong id becomes a wrong payment with no witness.
  * Matching is by NRIC (Vircle's join key — their webhook carries no mobile). We compare on
    DIGITS so `080805-08-1489` and `080805081489` are the same student.
  * Both URLs/secrets live in env vars only (Secrets Policy): `VIRCLE_AIRTABLE_PUSH_URL`
    (confidential — Vircle's guide says the URL is the credential) and `VIRCLE_AIRTABLE_SECRET`
    (ours, checked constant-time on the inbound endpoint).
  * Known limit, accepted: Rishvin's (#114) Vircle account is under his FATHER's IC, so an
    inbound row for him will not match his NRIC — it logs `no_match` and a human reconciles.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Aliases for the fields Vircle's automation may send back. Their Airtable columns are named by
# people, not by a schema we control, so the inbound reader accepts the spellings we have SEEN
# (Recipients table headers + the webhook guide) rather than demanding one.
_NRIC_KEYS = ('NRIC', 'nric', 'MYKAD', 'MyKad', 'mykad', 'ic', 'IC')
_WALLET_KEYS = ('Wallet ID', 'wallet_id', 'Principal Wallet ID', 'principal_wallet_id',
                'eWallet ID', 'ewallet_id', 'ewallet', 'wallet')
_ACTIVATED_KEYS = ('Activated', 'activated', 'Activated On', 'activated_on', 'Activated Date',
                   'activated_date', 'QR Activated Date', 'qr_activated_date')
# Their Recipients table carries a Status column whose DONE value means the account is live
# (the other observed value is "Pending Vircle Activation"). Owner ruling 2026-09-11 off their own
# screenshots: treat the moment we receive a row reading Done as the activation date, because
# `QR Activated Date` is blank on every row they have sent so far. A status we do not recognise —
# including the pending one — must NEVER stamp an activation.
_STATUS_KEYS = ('Status', 'status')
_ACTIVE_STATUS = 'done'


def _digits(value) -> str:
    return ''.join(ch for ch in str(value or '') if ch.isdigit())


def format_nric(value) -> str:
    """`080805081489` → `080805-08-1489` (the shape Vircle's guide shows). A value that is not
    12 digits is passed through untouched — better to send what we hold than to mangle it."""
    d = _digits(value)
    if len(d) == 12:
        return f'{d[:6]}-{d[6:8]}-{d[8:]}'
    return str(value or '').strip()


def recipient_payload(application) -> dict:
    """The exact three fields Vircle's inbound webhook takes. Type derives from the SAME
    birth-year rule the setup email uses (`vircle.can_register`): a student who cannot hold
    their own account registers as a child under a parent = Supplementary (Gokula, 2026-09-08)."""
    from .vircle import can_register
    profile = getattr(application, 'profile', None)
    return {
        'Name': (getattr(profile, 'name', '') or '').strip(),
        'NRIC': format_nric(getattr(profile, 'nric', '')),
        'Type': 'Principal' if can_register(application) else 'Supplementary',
    }


def push_recipient(item) -> str:
    """POST the student to Vircle's Airtable on their Action-Centre "installed" confirmation.

    Returns 'sent' / 'failed' / 'disabled' and records the outcome (with a timestamp) on the
    resolution item's params, so the cockpit's raw record says whether Vircle was told. Never
    raises — the student's confirmation must succeed whatever this does.
    """
    url = getattr(settings, 'VIRCLE_AIRTABLE_PUSH_URL', '') or ''
    if not url:
        return 'disabled'
    app = item.application
    outcome = 'failed'
    try:
        import requests
        payload = recipient_payload(app)
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code < 300:
            outcome = 'sent'
            logger.info('Vircle Airtable push: app_id=%s type=%s ok', app.id, payload['Type'])
        else:
            logger.warning('Vircle Airtable push: app_id=%s HTTP %s', app.id, resp.status_code)
    except Exception as e:  # noqa: BLE001 — best-effort by contract
        logger.warning('Vircle Airtable push failed: app_id=%s %s', app.id, e)
    try:
        item.params = {**(item.params or {}),
                       'airtable_push': outcome,
                       'airtable_push_at': timezone.now().isoformat()}
        item.save(update_fields=['params'])
    except Exception:  # noqa: BLE001 — the stamp is a courtesy, never a failure
        logger.warning('Vircle Airtable push: could not stamp item %s', item.id)
    return outcome


def _first(payload: dict, keys) -> str:
    for k in keys:
        if k in payload and payload[k] not in (None, ''):
            return str(payload[k]).strip()
    return ''


def _match_application(nric: str):
    """The awarded/active student this NRIC belongs to, matched on DIGITS, newest first.
    Restricted to `VIRCLE_SETUP_STATES` — the relay population — so a webhook row can never
    write onto a rejected or expired file."""
    from .models import ScholarshipApplication
    from .resolution import VIRCLE_SETUP_STATES
    want = _digits(nric)
    if len(want) != 12:
        return None
    candidates = (ScholarshipApplication.objects
                  .filter(status__in=VIRCLE_SETUP_STATES)
                  .select_related('profile')
                  .order_by('-id'))
    for app in candidates:
        if _digits(getattr(app.profile, 'nric', '')) == want:
            return app
    return None


def _alert(application_id, outcome, wallet, *, stored=''):
    """Email a human about a wallet write on this door. **Never raises, never blocks the reply.**

    ⚠ **THE WHOLE CONTRACT IS THAT VIRCLE STILL GETS ITS 200.** This endpoint answers somebody
    else's automation; an exception escaping here would turn our mail server's bad afternoon into
    their retry storm, about our data question. Same fault-injection contract as the outbound push
    and the usage meter: it fails alone.

    ⚠ **A `set` IS ALERTED AFTER THE SAVE, NOT BEFORE.** Emailing "wallet now 8000400170001" and
    then failing to save it would hand a person a fact that is not true and no way to tell — the
    email is a claim ABOUT stored state, so it waits for the state. A `mismatch` writes nothing,
    so it alerts where it happens.
    """
    try:
        from . import emails
        emails.send_vircle_wallet_alert_email(application_id, outcome, wallet, stored=stored)
    except Exception:  # noqa: BLE001 — an alert must never cost Vircle their 200
        logger.warning('Vircle wallet alert failed (app_id=%s, %s)',
                       application_id, outcome, exc_info=True)


def apply_update(payload: dict) -> dict:
    """One inbound Airtable row → at most two writes on the matched application.

    wallet: 'set' | 'kept' (already identical) | 'mismatch' (stored differs — logged, NOT
            overwritten) | 'invalid' (fails `valid_vircle_id` — logged, not written) | 'none'
    activated: 'set' | 'kept' | 'none'

    ⚠ WE READ `Principal Wallet ID` AND NEVER `Supp Wallet ID`, AND THAT IS A MONEY RULE, NOT AN
    OVERSIGHT. Owner, 2026-09-11: money can only be paid into the PRINCIPAL wallet; on a Child
    account the parent holds it and passes the money on, and the spending reports are keyed to the
    principal too. Adding the supplementary column here would pay a wallet nobody reconciles.
    """
    from . import payments
    from .vircle import _parse_activated_date

    nric = _first(payload, _NRIC_KEYS)
    app = _match_application(nric)
    if app is None:
        logger.warning('Vircle Airtable inbound: no_match nric_digits=%s…', _digits(nric)[:6])
        return {'ok': False, 'reason': 'no_match'}

    result = {'ok': True, 'application': app.id, 'wallet': 'none', 'activated': 'none'}
    fields = []
    pending_alert = None

    wallet = _digits(_first(payload, _WALLET_KEYS))
    if wallet:
        if app.vircle_id and app.vircle_id == wallet:
            result['wallet'] = 'kept'
        elif app.vircle_id:
            # The field that decides where money goes: never auto-overwrite. A human resolves.
            logger.error('Vircle Airtable inbound: WALLET MISMATCH app_id=%s stored=%s vircle=%s',
                         app.id, app.vircle_id, wallet)
            result['wallet'] = 'mismatch'
            _alert(app.id, 'mismatch', wallet, stored=app.vircle_id)
        elif not payments.valid_vircle_id(wallet):
            logger.warning('Vircle Airtable inbound: invalid wallet app_id=%s value=%s',
                           app.id, wallet)
            result['wallet'] = 'invalid'
        else:
            logger.info('AUDIT vircle_id_set app_id=%s by=%s was=%s now=%s',
                        app.id, 'vircle-airtable', '-', wallet)
            app.vircle_id = wallet
            fields.append('vircle_id')
            result['wallet'] = 'set'
            # ⚠ Queued here, SENT after the save below — see `_alert`'s note. A wallet emailed
            # about and then not saved would be worse than no email at all.
            pending_alert = (app.id, 'set', wallet, '')

    activated_raw = _first(payload, _ACTIVATED_KEYS)
    if activated_raw.lower() in ('false', '0', 'no'):
        activated_raw = ''
    status_done = _first(payload, _STATUS_KEYS).strip().lower() == _ACTIVE_STATUS
    if activated_raw or status_done:
        if app.vircle_activated_at:
            result['activated'] = 'kept'
        else:
            # Presence is the signal; an unparseable date still counts as activated NOW —
            # the rule the retired relay-sheet column followed before this became the one writer.
            app.vircle_activated_at = _parse_activated_date(activated_raw) or timezone.now()
            fields.append('vircle_activated_at')
            result['activated'] = 'set'

    if fields:
        app.save(update_fields=fields)
    if pending_alert:
        _alert(*pending_alert[:3], stored=pending_alert[3])
    return result
