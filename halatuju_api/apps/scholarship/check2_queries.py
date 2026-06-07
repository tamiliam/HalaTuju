"""
Check 2 — STEP 2: turn the STEP-1 submission review into a CONSOLIDATED query stream
on the existing ``ResolutionItem`` model (design ``check2-design.md`` §4).

Two kinds are added by Check 2:
  - ``clarify`` — an AI-raised, one-line, **non-sensitive** question for the STUDENT
    (Action Centre + email). Capped to the few most material so the queue doesn't
    suppress responses or burn the SLA clock.
  - ``human`` — reserved for items the AI triages to the human **reviewer**, never
    shown to the student. (The reviewer's broader suggested-questions list — the
    anomalies + interview gaps — is surfaced separately in the cockpit, so STEP 2
    does not duplicate it here.)

AI clarify queries carry ``source='check2'`` so the verdict-driven
``resolution.sync_resolution_items`` (which only reconciles ``source='system'``)
never touches them. A clarify query resolves on the student's typed answer, which
becomes a verified "resolved query answer" the profile generator may assert (§3).

**Triage (design §4).** Only *factual, one-line, non-sensitive* STEP-1 completeness
gaps become student clarify queries. Subjective / sensitive / motivational gaps
(``motivation_missing``) are the reviewer's, not the student's.
"""
from django.db import IntegrityError
from django.utils import timezone

from .models import ResolutionItem
from .submission_review import completeness_gaps

# Completeness-gap code → clarify-query spec. The gap code IS the query code (the
# frontend resolves the question copy from ``scholarship.check2.query.<code>``).
CLARIFY_SPECS = {
    'course_unspecified':     {'fact': 'pathway'},
    'sibling_level_unknown':  {'fact': 'income'},
    'device_status_unknown':  {'fact': 'other'},
    'transport_cost_unknown': {'fact': 'other'},
    # 'motivation_missing' is intentionally NOT here — motivation is reviewer texture
    # (§7), not a one-line factual answer.
}

# Priority order when capping — most material to a fundable profile first.
_CLARIFY_ORDER = [
    'course_unspecified', 'sibling_level_unknown',
    'device_status_unknown', 'transport_cost_unknown',
]

# The student is not the reviewer: a long list suppresses responses. Cap to the few
# most material (design §4).
MAX_CLARIFY = 3


def sync_check2_queries(application):
    """Reconcile the Check-2 AI clarify queries with the live STEP-1 completeness gaps.
    Idempotent + race-safe, mirroring ``resolution.sync_resolution_items``:

      - a clarify-able gap with no item yet → create an OPEN clarify item (capped)
      - an OPEN clarify item whose gap cleared → auto-resolve it (the data arrived)
      - an answered (resolved) item → left as-is (never re-asked)

    Gated on submission (``profile_completed_at``), same as the verdict queue. Returns
    the open Check-2 items. The cap counts every clarify code ever raised, so the
    student is never asked more than ``MAX_CLARIFY`` distinct questions in total.
    """
    if application.profile_completed_at is None:
        return ResolutionItem.objects.none()

    gaps = {g['code'] for g in completeness_gaps(application)}
    existing = {r.code: r for r in application.resolution_items.filter(source='check2')}
    now = timezone.now()

    raised = sum(1 for r in existing.values() if r.kind == 'clarify')
    for code in _CLARIFY_ORDER:
        if code not in gaps or code in existing:
            continue
        if raised >= MAX_CLARIFY:
            break
        try:
            ResolutionItem.objects.create(
                application=application, source='check2', code=code,
                fact=CLARIFY_SPECS[code]['fact'], kind='clarify',
            )
            raised += 1
        except IntegrityError:
            pass  # created concurrently — fine

    for code, item in existing.items():
        if item.status == 'open' and item.kind == 'clarify' and code not in gaps:
            item.status = 'resolved'
            item.resolved_by = 'system'
            item.resolved_at = now
            item.save(update_fields=['status', 'resolved_by', 'resolved_at'])

    return application.resolution_items.filter(source='check2', status='open')
