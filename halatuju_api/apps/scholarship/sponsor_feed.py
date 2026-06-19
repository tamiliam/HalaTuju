"""R3 — the My Giving activity feed + community stats.

Both are SYNTHESISED on the fly from existing models (no event-log table, no
migration) and are **allowlist-safe**: an activity event carries only the
anonymous ``ref`` + a type + a timestamp — never the student's identity — and the
community stats are programme-wide counts. The view layer gates them behind
``SPONSOR_POOL_ENABLED`` + approved-sponsor.
"""
from . import pool
from .models import (
    GraduationMessage, ScholarshipApplication, SemesterResult, Sponsor, Sponsorship,
)


def sponsor_activity(sponsor, *, limit=20):
    """A time-ordered feed of THIS sponsor's own students' lifecycle events —
    funded / accepted / semester completed / graduated / thank-you — each tagged
    with the anonymous ``ref`` only. Newest first, capped at ``limit``."""
    events = []
    sps = list(
        sponsor.sponsorships.filter(status__in=('offered', 'active')).select_related('application')
    )
    active_ids = []
    for sp in sps:
        ref = pool.pool_ref(sp.application_id)
        if sp.offered_at:
            events.append({'type': 'funded', 'ref': ref, 'at': sp.offered_at})
        if sp.status == 'active':
            active_ids.append(sp.application_id)
            if sp.decided_at:
                events.append({'type': 'accepted', 'ref': ref, 'at': sp.decided_at})

    if active_ids:
        for r in SemesterResult.objects.filter(application_id__in=active_ids):
            events.append({
                'type': 'graduated' if r.graduated else 'semester',
                'ref': pool.pool_ref(r.application_id),
                'at': r.created_at,
            })
        for m in GraduationMessage.objects.filter(application_id__in=active_ids, status='approved'):
            if m.reviewed_at:
                events.append({'type': 'thank_you', 'ref': pool.pool_ref(m.application_id), 'at': m.reviewed_at})

    events = [e for e in events if e['at'] is not None]
    events.sort(key=lambda e: e['at'], reverse=True)
    return events[:limit]


def community_stats():
    """Programme-wide belonging numbers for the My Giving community strip — counts
    only, nothing identifying: approved sponsors, students currently supported
    (distinct active sponsorships), and students still waiting in the pool."""
    return {
        'sponsors': Sponsor.objects.filter(status='approved').count(),
        'students_supported': (
            Sponsorship.objects.filter(status='active').values('application_id').distinct().count()
        ),
        'students_waiting': pool.eligible_pool_queryset(ScholarshipApplication).count(),
    }
