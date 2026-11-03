"""Team -> Mentors: the table's work columns and the MENTOR DETAIL page (Team tables T3, 2026-11-03; the
TeamMentors board the owner approved; roadmap ruling 6). The HTTP shapes are `views_admin/mentors.py`
(`AdminMentorsView` for the table, `AdminMentorView.get` for the page).

WHO READS: exactly who reads the Mentors table today — `mentor_invite.may_read` (a super, an organisation
admin, an admin; `staff_tables.may_do_admin_work`), fenced to the caller's organisation by the view (another
organisation's mentor answers 404). Nothing here widens that.

WHAT IS COUNTED (one rule each, in ONE place, so the table and the page cannot disagree):
- **Scholars now** — the mentor's OPEN assignments (`mentoring.scholars_now`, the old page's figure).
- **Meetings (90 days)** — meetings logged with this mentor (`MentoringSession.mentor`, by staff or by the
  mentor) whose `met_on` is within the last 90 days, today included (the organisation's local date).
- **Last meeting** — the latest `met_on` of any meeting with this mentor.
- **Average gap between meetings** — PER SCHOLAR: the days between each meeting and that scholar's
  previous meeting with this mentor, over every scholar and all time, averaged and rounded to whole days.
  None (the screen's '-') until some scholar has had two meetings: gaps between two DIFFERENT scholars'
  meetings say nothing about how often a scholar is seen.
- **Concerns raised / open** — meetings carrying the mentor's concern; OPEN = not marked handled AND the
  scholar's file still in maintenance. A closed file is read-only, so its concern can never be handled:
  it is not counted open — the Scholars list's own rule ("Mentor concerned", S7c review).
- **Per scholar** (current, then past): since / ended (the assignment), meetings and last meeting of THAT
  assignment, the standing chip (`scholars.rows` -> `standing.standing_for`, the Scholars list's own reading;
  None where the student has no maintenance file, e.g. an award reverted) and the concern state
  (`open` / `handled` / `closed` — raised on a file now closed).

⚠ AN ALLOWLIST. Never meeting notes, next steps, minutes, the end reason, who logged a meeting, documents,
money or anything else from the file. Fixed query budget whatever the number of scholars (tested).
"""
import datetime

from django.db.models import Count, Max, Q
from django.utils import timezone

from . import maintenance_scope
from .models import MentorAssignment, MentoringSession, ScholarshipApplication

WINDOW_DAYS = 90
OPEN, HANDLED, CLOSED = 'open', 'handled', 'closed'


def _since(today=None):
    return (today or timezone.localdate()) - datetime.timedelta(days=WINDOW_DAYS - 1)


def team_columns(mentor_ids, *, today=None):
    """``{mentor_id: {meetings_90, last_meeting, concerns_open}}`` for the Team -> Mentors table, in ONE
    query whatever the number of mentors. A mentor with no meeting is absent (the view fills zeros)."""
    ids = [i for i in mentor_ids if i is not None]
    if not ids:
        return {}
    live = ScholarshipApplication.objects.filter(maintenance_scope.in_maintenance_q()).values('pk')
    rows = (MentoringSession.objects.filter(mentor_id__in=ids).values('mentor_id')
            .annotate(meetings_90=Count('id', filter=Q(met_on__gte=_since(today))),
                      last_meeting=Max('met_on'),
                      concerns_open=Count('id', filter=Q(concern=True, concern_handled_at__isnull=True,
                                                         application_id__in=live))))
    return {r['mentor_id']: {'meetings_90': r['meetings_90'], 'last_meeting': _day(r['last_meeting']),
                             'concerns_open': r['concerns_open']} for r in rows}


def empty_columns():
    return {'meetings_90': 0, 'last_meeting': None, 'concerns_open': 0}


def _day(value):
    return value.isoformat() if value else None


def _average_gap(sessions):
    """Whole days, or None: see the module docstring (per scholar, all time)."""
    by_app = {}
    for s in sessions:
        by_app.setdefault(s['application_id'], []).append(s['met_on'])
    gaps = []
    for days in by_app.values():
        days.sort()
        gaps.extend((b - a).days for a, b in zip(days, days[1:]))
    return round(sum(gaps) / len(gaps)) if gaps else None


def _standings(app_ids):
    """``{application_id: standing}`` for the files among ``app_ids`` — the Scholars list's own reading,
    on its own annotated queryset (a fixed number of queries). No file, no entry."""
    from . import scholars
    if not app_ids:
        return {}
    apps = list(scholars.annotate(scholars.base_queryset(closed=None).filter(pk__in=list(app_ids))))
    return {r['id']: r['standing'] for r in scholars.rows(apps)}


def scholars_of(mentor, *, today=None):
    """``(figures, current, past)`` for the mentor detail page. See the module docstring."""
    # org-fence: the mentor's OWN organisation's files only (the view fenced the mentor itself).
    assignments = list(MentorAssignment.objects.filter(
        mentor=mentor, application__owning_organisation_id=mentor.organisation_id)
        .select_related('application__profile').order_by('-started_at', '-id'))
    sessions = list(MentoringSession.objects.filter(
        mentor=mentor, application__owning_organisation_id=mentor.organisation_id)
        .values('assignment_id', 'application_id', 'met_on', 'concern', 'concern_handled_at'))
    live = {a.application_id: maintenance_scope.is_in_maintenance(a.application) for a in assignments}
    standing = _standings({a.application_id for a in assignments})
    since = _since(today)

    per = {}
    for s in sessions:
        row = per.setdefault(s['assignment_id'], {'meetings': 0, 'last': None, 'raised': 0, 'unhandled': 0})
        row['meetings'] += 1
        row['last'] = max(row['last'], s['met_on']) if row['last'] else s['met_on']
        if s['concern']:
            row['raised'] += 1
            row['unhandled'] += s['concern_handled_at'] is None

    def concern_state(assignment):
        p = per.get(assignment.pk)
        if not p or not p['raised']:
            return None
        if not p['unhandled']:
            return HANDLED
        return OPEN if live.get(assignment.application_id) else CLOSED

    current, past = [], []
    for a in assignments:
        p = per.get(a.pk, {})
        prof = getattr(a.application, 'profile', None)
        row = {
            'application_id': a.application_id,
            'name': getattr(prof, 'name', '') or '',
            'since': a.started_at.isoformat() if a.started_at else None,
            'ended': a.ended_at.isoformat() if a.ended_at else None,
            'meetings': p.get('meetings', 0),
            'last_meeting': _day(p.get('last')),
            'standing': standing.get(a.application_id),
            'has_file': a.application_id in standing,
            'concern': concern_state(a),
        }
        (past if a.ended_at else current).append(row)

    raised = [s for s in sessions if s['concern']]
    figures = {
        'scholars_now': len(current),
        'meetings_90': sum(1 for s in sessions if s['met_on'] >= since),
        'average_gap_days': _average_gap(sessions),
        'concerns_raised': len(raised),
        'concerns_open': sum(1 for s in raised if s['concern_handled_at'] is None
                             and live.get(s['application_id'])),
        'last_meeting': _day(max((s['met_on'] for s in sessions), default=None)),
    }
    return figures, current, past
