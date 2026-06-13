"""Course-data dashboard support: record per-source run status + compute live coverage.

`record_status` is called by the refresh/validate/audit management commands when they finish,
so the admin Course Data dashboard can show freshness without re-running anything.
`coverage_snapshot` computes the current have/available picture LIVE from the DB (no stored state).

Kept import-light and side-effect-free at module load (safe to import from commands + views).
"""
from django.db.models import Count

# Status keys (mirror CourseDataStatus.KEY_CHOICES)
EPANDUAN_STPM = 'epanduan_stpm'
EPANDUAN_SPM = 'epanduan_spm'
UPTVET = 'uptvet'
EMASCO = 'emasco'
LINK_HEALTH = 'link_health'
AUDIT = 'audit'


def record_status(key, summary=None, detail=''):
    """Upsert the last-run status for a course-data source/check.

    Best-effort: never let status-recording break the tool that calls it (e.g. table missing
    on an un-migrated dev DB). Returns the row or None.
    """
    from django.utils import timezone
    from .models import CourseDataStatus
    try:
        row, _ = CourseDataStatus.objects.update_or_create(
            key=key,
            defaults={'last_run_at': timezone.now(), 'summary': summary or {}, 'detail': detail or ''},
        )
        return row
    except Exception:  # pragma: no cover - defensive (un-migrated DB / transient)
        return None


def coverage_snapshot():
    """Live coverage counts per source, computed from the DB (no persisted state).

    Returns a dict the dashboard renders directly. 'available'/'gap' are only known where we
    have an external reference: UP_TVET's ~catalogue size comes from the last stored inventory
    (CourseDataStatus['uptvet'].summary), else None (unknown until an inventory runs).
    """
    from .models import Course, StpmCourse, CourseRequirement, MascoOccupation, CourseDataStatus

    # SPM-side (the `courses` table) counts by requirement source_type.
    spm_by_source = dict(
        CourseRequirement.objects.values_list('source_type')
        .annotate(n=Count('source_type'))
        .values_list('source_type', 'n')
    )
    spm_total = Course.objects.count()

    # STPM-side.
    stpm_total = StpmCourse.objects.count()
    stpm_active = StpmCourse.objects.filter(is_active=True).count()

    emasco_total = MascoOccupation.objects.count()

    # UP_TVET available size from the last inventory run, if any.
    uptvet_available = None
    row = CourseDataStatus.objects.filter(key=UPTVET).first()
    if row and isinstance(row.summary, dict):
        uptvet_available = row.summary.get('total') or row.summary.get('scraped')

    tvet_have = spm_by_source.get('tvet', 0)
    uptvet_gap = (uptvet_available - tvet_have) if isinstance(uptvet_available, int) else None

    return {
        'spm_total': spm_total,
        'spm_by_source': spm_by_source,
        'stpm_total': stpm_total,
        'stpm_active': stpm_active,
        'tvet_have': tvet_have,
        'uptvet_available': uptvet_available,
        'uptvet_gap': uptvet_gap,
        'emasco_total': emasco_total,
    }
