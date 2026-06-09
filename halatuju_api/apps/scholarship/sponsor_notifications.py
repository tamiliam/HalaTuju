"""F3 — sponsor notifications: real-time alerts + weekly digests of newly-published
anonymised students.

Allowlist-safe by construction: every email body is built from
``SponsorPoolDetailSerializer`` dicts only, so a student's identity can never reach a
sponsor. Two scheduled entry points (run via the cron endpoint / management commands):

  * ``send_sponsor_realtime``  — hourly; batches students published since the last run
    to every ``realtime`` sponsor (one email per sponsor, not per student).
  * ``send_sponsor_digests``   — weekly; per-sponsor digest of students published since
    that sponsor's ``last_digest_sent_at``.

Both respect a soft per-run cap (``SPONSOR_NOTIFY_MAX_PER_RUN``, default 250) so a run
never blows the Brevo daily quota; the overflow is logged and picked up next run.
"""
import logging

from django.conf import settings
from django.utils import timezone

from . import pool
from .emails import send_sponsor_digest_email, send_sponsor_new_student_email
from .models import ScholarshipApplication, Sponsor, SponsorProfile

logger = logging.getLogger(__name__)


def _max_per_run():
    return int(getattr(settings, 'SPONSOR_NOTIFY_MAX_PER_RUN', 250) or 250)


def _serialise_cards(apps, sponsor):
    """Anonymised cards for these apps, honouring the sponsor's trust level
    (institution crosses to trusted sponsors only — the Boundary decision)."""
    from .serializers import SponsorPoolDetailSerializer
    return SponsorPoolDetailSerializer(
        apps, many=True, context={'is_trusted': sponsor.is_trusted}
    ).data


def send_sponsor_realtime():
    """Alert every approved ``realtime`` sponsor about students published since the
    last run (pool-eligible + not yet real-time-notified). One batched email per
    sponsor. Idempotent: each student is stamped ``realtime_notified_at`` so a later
    run never re-sends them. Returns a summary dict."""
    new_apps = list(
        pool.eligible_pool_queryset(ScholarshipApplication)
        .filter(sponsor_profile__realtime_notified_at__isnull=True)
    )
    if not new_apps:
        return {'students': 0, 'sponsors': 0, 'sent': 0}

    sponsors = list(Sponsor.objects.filter(status='approved', notify_frequency='realtime'))
    cap = _max_per_run()
    if len(sponsors) > cap:
        logger.warning('send_sponsor_realtime: %d realtime sponsors exceeds cap %d; '
                       'sending to the first %d this run', len(sponsors), cap, cap)
        sponsors = sponsors[:cap]

    sent = 0
    for s in sponsors:
        if send_sponsor_new_student_email(s.email, _serialise_cards(new_apps, s)):
            sent += 1

    # Stamp the whole batch as real-time-notified (whether or not any sponsor is
    # currently subscribed) so these students are never re-alerted in real time.
    SponsorProfile.objects.filter(
        application__in=new_apps, realtime_notified_at__isnull=True
    ).update(realtime_notified_at=timezone.now())
    return {'students': len(new_apps), 'sponsors': len(sponsors), 'sent': sent}


def send_sponsor_digests():
    """Send each approved ``weekly`` sponsor a digest of students published since
    their ``last_digest_sent_at`` (or all currently-eligible if never sent). A
    sponsor with nothing new is skipped (no empty digest). ``last_digest_sent_at``
    advances whenever there were students to report, so a digest is never duplicated.
    Returns a summary dict."""
    sponsors = list(Sponsor.objects.filter(status='approved', notify_frequency='weekly'))
    cap = _max_per_run()
    if len(sponsors) > cap:
        logger.warning('send_sponsor_digests: %d weekly sponsors exceeds cap %d; '
                       'sending to the first %d this run', len(sponsors), cap, cap)
        sponsors = sponsors[:cap]

    base = pool.eligible_pool_queryset(ScholarshipApplication)
    now = timezone.now()
    sent = 0
    for s in sponsors:
        qs = base
        if s.last_digest_sent_at:
            qs = qs.filter(sponsor_profile__anon_published_at__gt=s.last_digest_sent_at)
        apps = list(qs)
        if not apps:
            continue
        send_sponsor_digest_email(s.email, _serialise_cards(apps, s))
        sent += 1
        # Advance the clock whether or not the best-effort send succeeded, so the
        # sponsor is never sent the same digest twice (the students remain browsable
        # in the pool regardless).
        s.last_digest_sent_at = now
        s.save(update_fields=['last_digest_sent_at', 'updated_at'])
    return {'sponsors': len(sponsors), 'sent': sent}
