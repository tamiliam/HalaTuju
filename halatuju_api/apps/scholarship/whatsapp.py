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
import hashlib
import hmac
import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

_TWILIO_MESSAGES_URL = 'https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json'
# Twilio Verify (roadmap S4, TD-136): Twilio holds the one-time code + its lifecycle
# (expiry, max-attempts, per-number rate limits), so we keep NO code in our DB — we just
# ask Verify to send + later to check. WhatsApp channel (owner decision 2026-06-21).
_TWILIO_VERIFY_START_URL = 'https://verify.twilio.com/v2/Services/{svc}/Verifications'
_TWILIO_VERIFY_CHECK_URL = 'https://verify.twilio.com/v2/Services/{svc}/VerificationCheck'
_DEFAULT_CC = '60'  # Malaysia
# Twilio's shared WhatsApp **sandbox** sender. Free-text business-initiated messages are allowed
# only from the sandbox (to numbers that joined it); a real sender REQUIRES an approved template.
# So a caller with no approved template can safely free-text in the sandbox but must stay dark in prod.
SANDBOX_FROM = 'whatsapp:+14155238886'


def is_sandbox_sender():
    """True when the configured WhatsApp sender is Twilio's shared sandbox number."""
    return getattr(settings, 'TWILIO_WHATSAPP_FROM', '') == SANDBOX_FROM


def verify_twilio_signature(url, params, signature, *, token=None):
    """Validate Twilio's ``X-Twilio-Signature`` so only Twilio can hit our inbound webhook.

    Twilio signs: the full request URL + each POST param appended as ``key+value`` sorted by key,
    HMAC-SHA1 with the account auth token, base64-encoded. (stdlib; no Twilio SDK.) ``params`` is the
    parsed form dict (DRF ``request.data`` / a QueryDict)."""
    token = token or getattr(settings, 'TWILIO_AUTH_TOKEN', '')
    if not token or not signature:
        return False
    payload = url + ''.join(f'{k}{params[k]}' for k in sorted(params.keys()))
    digest = hmac.new(token.encode(), payload.encode('utf-8'), hashlib.sha1).digest()
    expected = base64.b64encode(digest).decode()
    return hmac.compare_digest(expected, signature)


def apply_opt_out(from_number, *, opted_in):
    """Sync ``StudentProfile.whatsapp_opt_in`` from an inbound STOP/START (roadmap S5, TD-135).

    Maps the sender's E.164 number back to a profile via the messages we've SENT it (``to_number`` is
    stored normalised), so we don't need a normalised-phone column. Returns True if a profile changed.
    If no message maps to the number, there's nothing we ever sent it → nothing to opt out."""
    e164 = (from_number or '').replace('whatsapp:', '').strip()
    if not e164:
        return False
    from .models import WhatsAppMessage  # local import: avoids app-loading cycles
    msg = (WhatsAppMessage.objects
           .filter(to_number=e164)
           .select_related('application__profile')
           .order_by('-created_at').first())
    profile = getattr(getattr(msg, 'application', None), 'profile', None)
    if profile is None:
        logger.info('WhatsApp opt-sync: no profile mapped to %s', e164)
        return False
    if profile.whatsapp_opt_in != opted_in:
        profile.whatsapp_opt_in = opted_in
        profile.save(update_fields=['whatsapp_opt_in'])
        logger.info('WhatsApp opt-sync: %s → opted_in=%s', e164, opted_in)
    return True


def verify_configured():
    """True when Twilio Verify can be used (account creds + a Verify Service SID)."""
    return bool(getattr(settings, 'TWILIO_ACCOUNT_SID', '')
                and getattr(settings, 'TWILIO_AUTH_TOKEN', '')
                and getattr(settings, 'TWILIO_VERIFY_SERVICE_SID', ''))


def start_phone_verification(phone, *, channel='whatsapp'):
    """Ask Twilio Verify to send a one-time code to ``phone`` over ``channel``.

    Returns ``(ok, status, error)``. ``ok`` is False (never raises) on an unconfigured
    service, an unusable number, or a transport/Twilio error — the caller maps that to an
    HTTP status. The code itself is generated + held by Twilio (we store nothing)."""
    sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
    token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
    svc = getattr(settings, 'TWILIO_VERIFY_SERVICE_SID', '')
    if not (sid and token and svc):
        return False, 'unconfigured', ''
    to_e164 = normalise_msisdn(phone)
    if not to_e164:
        return False, 'invalid_number', ''
    url = _TWILIO_VERIFY_START_URL.format(svc=urllib.parse.quote(svc, safe=''))
    try:
        payload = _post_to_verify(url, sid, token, {'To': to_e164, 'Channel': channel})
        return True, payload.get('status', 'pending'), ''
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors='replace')[:300]
        logger.warning('Verify start failed (HTTP %s): %s', e.code, detail)
        return False, 'failed', f'HTTP {e.code}'
    except Exception as exc:  # never let comms break the caller
        logger.exception('Verify start error')
        return False, 'failed', str(exc)[:200]


def check_phone_verification(phone, code):
    """Check a one-time ``code`` against Twilio Verify. Returns ``(approved, error)``.

    ``approved`` is True only when Twilio reports status ``approved``. A wrong/expired code
    is ``(False, '')``; an unconfigured service or transport error is ``(False, '<reason>')``.
    Twilio returns 404 once the verification has expired or hit max attempts — treated as a
    plain wrong-code (``incorrect``) so the student just gets a friendly retry message."""
    sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
    token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
    svc = getattr(settings, 'TWILIO_VERIFY_SERVICE_SID', '')
    if not (sid and token and svc):
        return False, 'unconfigured'
    to_e164 = normalise_msisdn(phone)
    if not (to_e164 and code):
        return False, 'invalid'
    url = _TWILIO_VERIFY_CHECK_URL.format(svc=urllib.parse.quote(svc, safe=''))
    try:
        payload = _post_to_verify(url, sid, token, {'To': to_e164, 'Code': str(code).strip()})
        return payload.get('status') == 'approved', ''
    except urllib.error.HTTPError as e:
        if e.code == 404:           # verification expired / consumed / max attempts
            return False, 'incorrect'
        logger.warning('Verify check failed (HTTP %s)', e.code)
        return False, 'failed'
    except Exception:
        logger.exception('Verify check error')
        return False, 'failed'


def _post_to_verify(url, sid, token, fields):
    """POST to a Twilio Verify endpoint, returning the parsed JSON. Separate seam so tests
    mock THIS (no network), mirroring ``_post_to_twilio``."""
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=data, method='POST')
    creds = base64.b64encode(f'{sid}:{token}'.encode()).decode()
    req.add_header('Authorization', f'Basic {creds}')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode() or '{}')


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


def send_whatsapp(to, body='', *, application=None, kind='', content_sid='', content_variables=None, log=True):
    """Best-effort outbound WhatsApp message. Returns the ``WhatsAppMessage`` row, or None.

    No-op (returns None) unless ``WHATSAPP_ENABLED`` and all Twilio creds are set.
    Never raises: a bad number or a transport/Twilio error is caught, logged, and
    recorded on the row as ``failed``.

    Production business-initiated messages MUST use a Meta-approved template: pass
    ``content_sid`` (the template's ``HX…``) + ``content_variables`` ({'1': …, '2': …}).
    The free-text ``body`` path is only for the sandbox/dev (no template needed there).
    """
    from .models import WhatsAppMessage  # local import: avoids app-loading cycles

    enabled = getattr(settings, 'WHATSAPP_ENABLED', False)
    sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
    token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
    sender = getattr(settings, 'TWILIO_WHATSAPP_FROM', '')
    if not (enabled and sid and token and sender):
        logger.info('WhatsApp send skipped (disabled/unconfigured): kind=%s', kind)
        return None

    # What we record for audit: the literal body, or a marker for a template send.
    log_body = body or (f'[template:{content_sid}]' if content_sid else '')
    to_e164 = normalise_msisdn(to)
    if not to_e164:
        logger.warning('WhatsApp send skipped (invalid number): kind=%s', kind)
        if log:
            return WhatsAppMessage.objects.create(
                application=application, kind=kind, to_number=str(to or ''),
                body=log_body, status='failed', error='invalid_number')
        return None

    row = None
    if log:
        row = WhatsAppMessage.objects.create(
            application=application, kind=kind, to_number=to_e164,
            body=log_body, status='queued')
    # Billable Twilio send (valid number + configured) — best-effort meter, org from the
    # passed application (NULL when none). NEVER breaks the send.
    from . import usage
    usage.record_usage(
        usage.WHATSAPP, source=kind or 'whatsapp', quantity=1,
        organisation_id=getattr(application, 'owning_organisation_id', None),
        application_id=getattr(application, 'id', None))
    try:
        msg_sid, status, err = _post_to_twilio(sid, token, sender, to_e164, body, content_sid, content_variables)
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


def _post_to_twilio(sid, token, sender, to_e164, body, content_sid='', content_variables=None):
    """POST one message to Twilio. Returns ``(message_sid, status, error)``.

    Kept as a separate seam so tests mock THIS (no network) rather than urllib.
    With ``content_sid`` it sends the approved template (+ ContentVariables JSON);
    otherwise it sends the free-text ``Body`` (sandbox/dev).
    """
    url = _TWILIO_MESSAGES_URL.format(sid=urllib.parse.quote(sid, safe=''))
    from_addr = sender if sender.startswith('whatsapp:') else f'whatsapp:{sender}'
    fields = {'To': f'whatsapp:{to_e164}', 'From': from_addr}
    if content_sid:
        fields['ContentSid'] = content_sid
        if content_variables:
            fields['ContentVariables'] = json.dumps(content_variables)
    else:
        fields['Body'] = body
    data = urllib.parse.urlencode(fields).encode()
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
