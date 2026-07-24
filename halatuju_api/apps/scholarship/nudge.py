"""The "you haven't submitted yet" nudge.

A shortlisted student who has given consent but never pressed the final Review & submit sits in
a silent limbo: everything is done, the guardian has consented, but the application is still a
draft with us (``profile_completed_at IS NULL``). This module drives the recovery:

  * a ONE-TIME AUTOMATIC nudge, ~30 minutes after consent (a cron sweep), while the student is
    likely still at their device — the highest-chance moment to recover the submission; then
  * MANUAL org-admin re-nudges from the cockpit Blockers box, unlocked only after the auto nudge
    has been sent, and rate-limited by a cooldown.

The auto nudge sits ALONGSIDE the existing generic completion reminders (R1 +2d … R4 +53d), it
does not replace them. Pure-ish: reads the application + its consent, sends via ``emails`` and
stamps ``nudge_sent_at``. ``nudge_state`` is the single source of truth the cockpit renders.
"""
from datetime import timedelta

from django.conf import settings
from django.utils import timezone


def _auto_delay():
    return timedelta(minutes=getattr(settings, 'NUDGE_AUTO_DELAY_MINUTES', 30))


def _cooldown():
    return timedelta(hours=getattr(settings, 'NUDGE_COOLDOWN_HOURS', 24))


def _consent_granted_at(application):
    """When the student's active consent was given, or None if not consented."""
    c = application.consents.filter(is_active=True).order_by('-granted_at').first()
    return c.granted_at if c else None


def _has_blockers(application):
    """True if the student still has outstanding submission items (services.consent_blockers).

    A student can only consent once everything is clear, but if they then edit something back
    into an incomplete/mismatched state the consent row stays active while blockers reappear.
    Such a student is genuinely STUCK, not one-press-from-submitting — the "you haven't submitted
    yet" nudge would be the wrong message, so it deliberately does not apply. The generic
    completion reminders (send_application_reminders) own that case instead."""
    from .services import consent_blockers
    return bool(consent_blockers(application))


def is_applicable(application):
    """True for the exact state a nudge belongs to: a SHORTLISTED student who has an active
    consent, has NOT pressed the final submit (``profile_completed_at`` is still NULL), AND has
    nothing outstanding — i.e. genuinely one press from submitting. A consented student who has
    since fallen back into an incomplete/blocked state is excluded (see ``_has_blockers``)."""
    return (application.status == 'shortlisted'
            and application.profile_completed_at is None
            and _consent_granted_at(application) is not None
            and not _has_blockers(application))


def nudge_state(application, now=None):
    """Server-computed state for the cockpit button (the FE only renders this — no rule lives on
    the client). Shape:
      applicable   — is this the consented-but-unsubmitted shortlisted state?
      sent_at      — ISO time of the most recent nudge, or null (never nudged)
      available    — may an org admin send a manual nudge right now?
      available_at — ISO time it next becomes available (the auto-due time before the first nudge,
                     or the cooldown end after one), or null when available now / not applicable.
    """
    now = now or timezone.now()
    if not is_applicable(application):
        return {'applicable': False, 'sent_at': None, 'available': False, 'available_at': None}
    sent = application.nudge_sent_at
    if sent is None:
        # Before the one-time AUTO nudge fires, the manual button is deliberately blocked (so an
        # org admin can't double-send just ahead of the automatic one). It unlocks once the auto
        # has gone out. available_at = when the auto is due (consent granted + delay).
        auto_at = _consent_granted_at(application) + _auto_delay()
        return {'applicable': True, 'sent_at': None, 'available': False,
                'available_at': auto_at.isoformat()}
    cd_end = sent + _cooldown()
    available = now >= cd_end
    return {'applicable': True, 'sent_at': sent.isoformat(), 'available': available,
            'available_at': None if available else cd_end.isoformat()}


def send_nudge(application, *, manual, now=None):
    """Send the nudge email and stamp ``nudge_sent_at``. Returns True only on a real send.

    Guards: the application must be ``is_applicable``; a MANUAL send additionally honours the
    availability/cooldown (``nudge_state`` — belt-and-suspenders with the endpoint). The stamp is
    written ONLY when the mail actually went out, so a transient ESP failure lets the auto sweep
    retry on its next run instead of silently marking the student as nudged."""
    now = now or timezone.now()
    if not is_applicable(application):
        return False
    if manual and not nudge_state(application, now=now)['available']:
        return False
    from .emails import english_only_email, send_application_nudge_email
    name = getattr(application.profile, 'name', '') if application.profile else ''
    sent = send_application_nudge_email(
        application.notify_email, student_name=name,
        english_only=english_only_email(application))
    if sent:
        application.nudge_sent_at = now
        application.save(update_fields=['nudge_sent_at'])
    return bool(sent)


def send_application_nudges(now=None):
    """Cron sweep — the ONE-TIME automatic nudge. Every shortlisted, consented-but-unsubmitted
    application whose consent was given at least the auto-delay ago AND which has never been
    nudged gets exactly one email. Idempotent + burst-proof: ``nudge_sent_at`` is stamped on
    send, so the same student is never swept twice. Returns ``{'nudged': n}``."""
    from .models import ScholarshipApplication
    now = now or timezone.now()
    cutoff = now - _auto_delay()
    qs = (ScholarshipApplication.objects
          .filter(status='shortlisted', profile_completed_at__isnull=True,
                  nudge_sent_at__isnull=True,
                  consents__is_active=True, consents__granted_at__lte=cutoff)
          .select_related('profile').distinct())
    nudged = 0
    for app in qs:
        if send_nudge(app, manual=False, now=now):
            nudged += 1
    return {'nudged': nudged}
