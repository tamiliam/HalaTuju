"""R6 — AutoSponsor: allocate standing gifts to matching pool students.

A sponsor sets a ``StandingGift`` (field/state prefs + an optional per-student cap);
this module auto-funds matching, currently-fundable pool students from their balance.
Each allocation goes through ``sponsorship.fund_student`` → an OFFERED sponsorship the
student must accept (no real money moves) — the same safety model as a manual fund.

Event-driven via an HOURLY cron (``auto_sponsor`` command → the cron endpoint), which
processes every currently-fundable student. It is naturally idempotent + self-limiting:
``fund_student`` creates a holding sponsorship, so a funded student immediately leaves
the fundable set, and the DB partial-unique allows only one holding sponsor per student.
Insufficient balance → the student is simply skipped (retried next run once topped up).
Inert unless ``SPONSOR_POOL_ENABLED`` (standing gifts can only be set via the flag-gated
endpoint, so none exist while the programme is dark anyway).
"""
import logging

from django.conf import settings
from django.db.models import F
from django.utils import timezone

from . import pool
from . import sponsorship as sponsorship_service
from .models import ScholarshipApplication, StandingGift

logger = logging.getLogger(__name__)


def matching_gifts(application):
    """Yield the active standing gifts that match this student AND can currently
    afford the award, least-recently-allocated first (fair spread). Pref empty =
    matches any; ``max_amount`` null = no cap. Balance is checked live."""
    award = application.award_amount
    if award is None or award <= 0:
        return
    field = application.field_of_study or ''
    state = (getattr(application.profile, 'preferred_state', '') or '') if application.profile else ''
    gifts = (StandingGift.objects.filter(active=True, sponsor__status='approved')
             .select_related('sponsor')
             .order_by(F('last_allocated_at').asc(nulls_first=True), 'created_at'))
    for g in gifts:
        if g.field_pref and g.field_pref != field:
            continue
        if g.state_pref and g.state_pref != state:
            continue
        if g.max_amount is not None and award > g.max_amount:
            continue
        if sponsorship_service.sponsor_balance(g.sponsor) < award:
            continue  # skip silently — retried next run once topped up
        yield g


def run_standing_gifts():
    """Fund every currently-fundable pool student with the first matching standing
    gift (one sponsor per student). Returns a summary dict. Inert when the pool flag
    is off. Best-effort per student — a single failure never aborts the run."""
    if not getattr(settings, 'SPONSOR_POOL_ENABLED', False):
        return {'students': 0, 'funded': 0}
    funded = 0
    considered = 0
    for app in pool.eligible_pool_queryset(ScholarshipApplication):
        if not sponsorship_service.is_fundable(app):
            continue
        considered += 1
        for g in matching_gifts(app):
            try:
                sponsorship_service.fund_student(g.sponsor, app)
            except sponsorship_service.SponsorshipError:
                continue  # race / state change — try the next gift
            g.last_allocated_at = timezone.now()
            g.save(update_fields=['last_allocated_at', 'updated_at'])
            funded += 1
            break  # one holding sponsor per student
    return {'students': considered, 'funded': funded}
