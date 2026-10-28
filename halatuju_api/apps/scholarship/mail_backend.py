"""The production mail backend: Django's own SMTP backend (Brevo's relay), plus one line of
bookkeeping for the admin System health light (2026-10-28).

Every email the service sends — `send_mail`, `EmailMessage.send`, `EmailMultiAlternatives` — goes
through `settings.EMAIL_BACKEND`, so this is the single choke-point the light needs. The sending
itself is the parent class's, untouched: same connection handling, same `fail_silently`, same
return value, same exceptions.

What is recorded (`system_health_store.record_email`): whether the call delivered every message it
was given, and on failure the exception's CLASS name. ⚠ Never an address, a subject, a body or an
exception's message — an `SMTPRecipientsRefused` message lists the recipients.
"""
from django.core.mail.backends.smtp import EmailBackend


class RecordingSMTPBackend(EmailBackend):
    def send_messages(self, email_messages):
        from . import system_health_store as store
        messages = list(email_messages or [])
        try:
            sent = super().send_messages(messages)
        except Exception as exc:
            store.record_email(False, store.error_name(exc))
            raise
        # A message with no recipients is skipped by Django without an attempt (it is never counted
        # as sent), so it says nothing about the relay and is neither a success nor a failure.
        addressed = sum(1 for m in messages if m.recipients())
        if addressed:
            # `fail_silently` swallows the error and returns how many went; fewer than asked = a failure.
            if (sent or 0) >= addressed:
                store.record_email(True)
            else:
                store.record_email(False, 'not all sent (silenced)')
        return sent
