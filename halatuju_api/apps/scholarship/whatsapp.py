"""Outbound WhatsApp comms via Twilio — Sprint 1 of the WhatsApp channel.

DARK by default: every send is a no-op unless ``settings.WHATSAPP_ENABLED`` is true
AND the three Twilio creds are configured (mirrors the project's "ship a billable API
disabled first" rule). Comms are **best-effort** — a WhatsApp failure NEVER raises into
the caller; email stays the system of record.

No Twilio SDK dependency: we POST to the Twilio REST API with ``urllib`` (stdlib), so
there is no requirements bump. Every attempt is logged to ``WhatsAppMessage`` for an
audit trail + delivery status.

NOTE (Sprint 2): there is no per-recipient consent gate yet. The flag stays OFF in prod,
so no real applicant is messaged until Sprint 2 adds the ``whatsapp_opt_in`` gate.
"""
from __future__ import annotations

import base64
import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

_TWILIO_MESSAGES_URL = 'https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json'
_DEFAULT_CC = '60'  # Malaysia


def normalise_msisdn(raw, *, default_cc=_DEFAULT_CC):
    """Normalise a Malaysian phone number to E.164 (``+60…``); '' if it can't.

    Handles the shapes the apply form stores (98/99 prod applicants are ``0XX…``,
    one is already ``+60``): '012-345 6789', '0123456789', '+60123456789',
    '60123456789', '0060…'. Deterministic + side-effect free (unit-tested).
    """
    if not raw:
        return ''
    digits = re.sub(r'[^\d+]', '', str(raw))
    if digits.startswith('+'):
        rest = digits[1:]
        return digits if (rest.isdigit() and len(rest) >= 8) else ''
    if digits.startswith('00'):              # international access code
        digits = digits[2:]
    elif digits.startswith('0'):             # local '0XX…' → drop the trunk 0
        digits = default_cc + digits[1:]
    elif not digits.startswith(default_cc):  # bare national number → assume local MY
        digits = default_cc + digits
    return ('+' + digits) if (digits.isdigit() and len(digits) >= 10) else ''


def send_whatsapp(to, body, *, application=None, kind='', log=True):
    """Best-effort outbound WhatsApp message. Returns the ``WhatsAppMessage`` row, or None.

    No-op (returns None) unless ``WHATSAPP_ENABLED`` and all Twilio creds are set.
    Never raises: a bad number or a transport/Twilio error is caught, logged, and
    recorded on the row as ``failed``.
    """
    from .models import WhatsAppMessage  # local import: avoids app-loading cycles

    enabled = getattr(settings, 'WHATSAPP_ENABLED', False)
    sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
    token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
    sender = getattr(settings, 'TWILIO_WHATSAPP_FROM', '')
    if not (enabled and sid and token and sender):
        logger.info('WhatsApp send skipped (disabled/unconfigured): kind=%s', kind)
        return None

    to_e164 = normalise_msisdn(to)
    if not to_e164:
        logger.warning('WhatsApp send skipped (invalid number): kind=%s', kind)
        if log:
            return WhatsAppMessage.objects.create(
                application=application, kind=kind, to_number=str(to or ''),
                body=body, status='failed', error='invalid_number')
        return None

    row = None
    if log:
        row = WhatsAppMessage.objects.create(
            application=application, kind=kind, to_number=to_e164,
            body=body, status='queued')
    try:
        msg_sid, status, err = _post_to_twilio(sid, token, sender, to_e164, body)
        if row:
            row.provider_sid = msg_sid or ''
            row.status = status or ('sent' if msg_sid else 'failed')
            row.error = (err or '')[:500]
            row.save(update_fields=['provider_sid', 'status', 'error', 'updated_at'])
    except Exception as exc:  # never let comms break the caller
        logger.exception('WhatsApp send failed: kind=%s', kind)
        if row:
            row.status = 'failed'
            row.error = str(exc)[:500]
            row.save(update_fields=['status', 'error', 'updated_at'])
    return row


def _post_to_twilio(sid, token, sender, to_e164, body):
    """POST one message to Twilio. Returns ``(message_sid, status, error)``.

    Kept as a separate seam so tests mock THIS (no network) rather than urllib.
    """
    url = _TWILIO_MESSAGES_URL.format(sid=urllib.parse.quote(sid, safe=''))
    from_addr = sender if sender.startswith('whatsapp:') else f'whatsapp:{sender}'
    data = urllib.parse.urlencode({
        'To': f'whatsapp:{to_e164}',
        'From': from_addr,
        'Body': body,
    }).encode()
    req = urllib.request.Request(url, data=data, method='POST')
    creds = base64.b64encode(f'{sid}:{token}'.encode()).decode()
    req.add_header('Authorization', f'Basic {creds}')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode() or '{}')
            return payload.get('sid', ''), payload.get('status', 'sent'), ''
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors='replace')[:400]
        return '', 'failed', f'HTTP {e.code}: {detail}'
