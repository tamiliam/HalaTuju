"""Spending and Vircle wallet alert mail.

Moved here VERBATIM from `emails.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from django.conf import settings
from django.core.mail import EmailMessage
from .shared import _PROG_EN, _TEAM_EN, logger


def send_spending_alert_email(lines, *, subject_hint=''):
    """Tell a human that the spending import needs one. Best-effort → bool.

    ⚠ **SENT ONLY WHEN `IngestReport.needs_attention` IS TRUE** (owner ruling, 2026-09-10). There
    is deliberately **no weekly all-clear**: a message that arrives every week regardless is a
    message nobody opens, and the week it matters it gets skimmed with the rest. Silence means
    nothing to report.

    ⚠ **IT NAMES WALLETS AND APPLICATION IDS, NEVER A STUDENT'S NAME.** Those two are what a person
    needs to fix the problem; a name is not, and this mail gets forwarded. It carries no merchant
    and no amount for the same reason.

    ⚠ **PLAIN `EmailMessage` WITH AN EXPLICIT `from_email`, NOT `_send_html`.** `_send_html`
    DEFAULTS its sender to the interview alias because interview mail is its main caller — the
    correct call and the wrong call look identical and the wrong one is shorter, which is how a
    student email once went out from `interview@` (2026-08-01). Internal alerts name their sender
    outright, as this one does.
    """
    recipient = (getattr(settings, 'ADMIN_NOTIFY_EMAIL', '') or '').strip()
    if not recipient or not lines:
        return False
    from django.utils import timezone
    today = timezone.localdate()
    body = (
        'The bursary spending import needs a person to look at something.\n\n'
        + '\n'.join(lines)
        + '\n\nThis message is sent only when something needs attention. A run that finds '
          'nothing wrong sends nothing at all.\n\n'
          'Thank you,\n'
        + _TEAM_EN
    )
    try:
        EmailMessage(
            subject=(f'{_PROG_EN} — spending import needs attention'
                     f'{": " + subject_hint if subject_hint else ""} — {today:%d %B %Y}'),
            body=body, from_email=settings.DEFAULT_FROM_EMAIL, to=[recipient]).send()
        return True
    except Exception:
        logger.warning('Failed to send the spending alert email', exc_info=True)
        return False


def send_vircle_wallet_alert_email(application_id, outcome, wallet, *, stored=''):
    """Tell a human that the Vircle Airtable door moved — or tried to move — a WALLET ID.

    ⚠⚠ **THIS EXISTS BECAUSE THAT DOOR CAN REDIRECT MONEY AND ONLY WHISPERED ABOUT IT.** The
    inbound webhook (`VircleAirtableUpdateView`) is a public route held shut by one shared secret.
    Anybody holding that secret *and* a student's NRIC can set `vircle_id` on a student who does
    not have one yet — which is the field that decides where that student's bursary is paid. The
    write was already audited to the application log, and nobody reads an application log. An
    email is the difference between finding out the same day and never (owner, 2026-09-11, after
    the secret was exposed in a session transcript; nothing had come through the door).

    ⚠ **TWO OUTCOMES, NOT ONE, AND THE REFUSED ONE MATTERS MOST.** `set` is the door working. But
    `mismatch` — an attempt to change a wallet id we already hold — is the door being pushed at,
    and it is precisely what an attacker aiming at a funded student produces. It is refused in
    code and must still reach a person.

    ⚠ **IT NAMES A WALLET AND AN APPLICATION ID, NEVER A STUDENT'S NAME** — the same rule as
    `send_spending_alert_email`. Those two are what a person needs to check the row; a name is not,
    and internal alerts get forwarded.

    ⚠ **BEST-EFFORT, LIKE EVERY ALERT ON THIS PATH.** It returns a bool and never raises: Vircle's
    automation must still get its 200, or their side goes into retries over our mail server.
    """
    recipient = (getattr(settings, 'ADMIN_NOTIFY_EMAIL', '') or '').strip()
    if not recipient or outcome not in ('set', 'mismatch'):
        return False
    from django.utils import timezone
    today = timezone.localdate()

    if outcome == 'set':
        headline = (
            'A student wallet ID was SET by Vircle\'s Airtable automation.\n\n'
            f'  application : {application_id}\n'
            f'  wallet now  : {wallet}\n\n'
            'This is the normal way a wallet arrives, and it is almost certainly routine.\n'
            'It is emailed because this field decides where that student\'s bursary is paid,\n'
            'and the only other record of it is a server log.\n\n'
            'If you were not expecting a wallet for this application, check it today.'
        )
    else:
        headline = (
            'An attempt to CHANGE a wallet ID we already hold was REFUSED.\n\n'
            f'  application : {application_id}\n'
            f'  we hold     : {stored}\n'
            f'  they sent   : {wallet}\n\n'
            'Nothing was overwritten. The stored ID still decides where the money goes.\n\n'
            'This is either Vircle correcting their own record — in which case a person\n'
            'should update ours deliberately — or something that should not be happening.'
        )

    body = (headline + '\n\nThank you,\n' + _TEAM_EN)
    try:
        EmailMessage(
            subject=(f'{_PROG_EN} — wallet ID '
                     f'{"set" if outcome == "set" else "change REFUSED"} '
                     f'(application {application_id}) — {today:%d %B %Y}'),
            body=body, from_email=settings.DEFAULT_FROM_EMAIL, to=[recipient]).send()
        return True
    except Exception:
        logger.warning('Failed to send the Vircle wallet alert email', exc_info=True)
        return False
