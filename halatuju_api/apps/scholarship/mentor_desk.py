"""The MENTOR's own door (student maintenance Sprint 7c, 2026-11-01; owner rulings in docs/decisions.md the
same day): a signed-in mentor sees their CURRENT students and logs meetings with them.

The HTTP shapes are `views_admin/mentor_students.py`; the meeting validation and write are 7b's own
(`mentoring.clean_meeting` / `mentoring.write_session`) — one rule for staff and mentor.

- WHO IS A MENTOR'S STUDENT (`current_assignments`): an OPEN `MentorAssignment` whose mentor is the
  caller's own (`PartnerAdmin.mentor`), on an application of the MENTOR'S OWN organisation that is in
  maintenance, and NEVER the mentor's own application (`mentoring.is_the_student`, read at every read
  — treated as no access). A deactivated mentor reads nothing (their login is off too, so `get_admin`
  already refuses them). When mentoring ends, the student leaves the list and every per-student door
  answers 404 — ONE answer for another mentor's student, an ended assignment, another organisation's
  file and an id that does not exist.
- WHAT THE MENTOR SEES (`student_payload`) IS AN ALLOWLIST: the student's name; programme and
  institution (`card_display`, what the scholar file shows); their email and phone; "your student
  since"; what they asked for help with (`mentoring_read.help_asked`); the LATEST accepted result only —
  CGPA and term — and the standing (`standing.standing_of`), or none. NEVER money, documents, slips,
  family or income, letters, the contract, other mentors, history, staff notes, the activity log, a
  photo, the sub-state or a hold.
- MEETINGS: those of the CURRENT assignment, newest first. A meeting THIS mentor logged
  (`logged_by_mentor`) shows in full (notes, next step, minutes, concern); one STAFF logged shows date
  and how only — never its notes, next step, minutes or who.
- THE MENTOR LOGS (`log_own_session`) with 7b's validation, under 7b's row lock on the application
  and the open assignment, RE-CHECKED inside the transaction: a staff End or a Deactivate that commits
  first leaves nothing open of theirs, and the log is refused (`not_found`, the same 404). A saved
  meeting is never edited. A CONCERN ("Tell the team I am worried about this student") rides on the
  meeting and logs `mentor_concern_raised`; staff clear it (`mentoring.handle_concern`).
- NO EMAIL to anyone, ever, from this door (the system never emails a mentor; the student is not told).
"""
from django.db import transaction
from django.utils import timezone

from . import card_display, maintenance_scope, mentoring, standing
from .mentoring import MentoringError
from .mentoring_read import help_asked
from .models import MentorAssignment, MentoringSession, ScholarshipApplication
from .models.activity import EVENT_MENTOR_CONCERN_RAISED
from .results_review import latest_accepted


def mentor_of(login):
    """The caller's own `Mentor`, or None (not a mentor login, or deactivated)."""
    if login is None or not login.is_mentor or login.mentor_id is None:
        return None
    mentor = login.mentor
    return mentor if mentor.deactivated_at is None else None


def current_assignments(login):
    """The caller's OPEN assignments on their own organisation's files in maintenance, oldest
    first, minus any whose student IS the mentor (see the module docstring)."""
    mentor = mentor_of(login)
    if mentor is None:
        return []
    # org-fence: the mentor's OWN organisation's files only, in maintenance (the predicate's one home).
    live = ScholarshipApplication.objects.filter(maintenance_scope.in_maintenance_q(),
                                                 owning_organisation_id=mentor.organisation_id)
    rows = (MentorAssignment.objects.filter(mentor=mentor, ended_at__isnull=True, application__in=live)
            .select_related('application__profile', 'application__owning_organisation', 'mentor')
            .order_by('started_at', 'id'))
    return [a for a in rows if not mentoring.is_the_student(login, a.application)]


def assignment_for(login, application_id):
    """The caller's current assignment for ``application_id``, or None (→ 404)."""
    return next((a for a in current_assignments(login) if a.application_id == application_id), None)


def _student_bits(app):
    """Who the student is and how to reach them — the list card and the page share these."""
    prof = getattr(app, 'profile', None)
    return {
        'id': app.pk,
        'name': getattr(prof, 'name', '') or '',
        'course': card_display.resolve_course(app),
        'institution': card_display.resolve_institution(app),
        'email': (app.notify_email or getattr(prof, 'contact_email', '') or '').strip(),
        'phone': (getattr(prof, 'contact_phone', '') or '').strip(),
    }


def _result(app):
    """The LATEST accepted result only (CGPA and its term), or None — and the standing."""
    latest = latest_accepted(app)
    result = None
    if latest is not None and latest.cgpa is not None:
        from .scholars import _two
        result = {'cgpa': _two(latest.cgpa), 'semester': latest.semester or ''}
    return result, standing.standing_of(app)


def _meeting_counts(assignment_ids):
    counts, last = {}, {}
    for aid, met_on in (MentoringSession.objects.filter(assignment_id__in=list(assignment_ids))
                        .order_by('-met_on', '-id').values_list('assignment_id', 'met_on')):
        counts[aid] = counts.get(aid, 0) + 1
        last.setdefault(aid, met_on)
    return counts, last


def list_payload(login):
    """My students: one card per current student (allowlist — see the module docstring)."""
    rows = current_assignments(login)
    counts, last = _meeting_counts([a.pk for a in rows])
    mentor = mentor_of(login)
    out = []
    for a in rows:
        result, stand = _result(a.application)
        out.append({**_student_bits(a.application), 'since': timezone.localdate(a.started_at),
                    'meetings': counts.get(a.pk, 0), 'last_meeting': last.get(a.pk),
                    'latest_result': result, 'standing': stand,
                    'asked_for_help': help_asked(a.application)})
    return {'organisation': _org_name(mentor), 'students': out}


def _org_name(mentor):
    org = getattr(mentor, 'organisation', None) if mentor is not None else None
    return (getattr(org, 'name', '') or '') if org is not None else ''


def meeting_dict(session, mentor_id):
    """One meeting as the MENTOR sees it: in full when they logged it, date + how otherwise."""
    if session.logged_by_mentor and session.mentor_id == mentor_id:
        return {'id': session.pk, 'met_on': session.met_on, 'mode': session.mode, 'by_you': True,
                'minutes': session.minutes, 'notes': session.notes, 'next_step': session.next_step,
                'concern': bool(session.concern)}
    return {'id': session.pk, 'met_on': session.met_on, 'mode': session.mode, 'by_you': False}


def student_payload(login, assignment):
    """One student's page for the mentor (allowlist — see the module docstring)."""
    app = assignment.application
    result, stand = _result(app)
    sessions = (MentoringSession.objects.filter(assignment_id=assignment.pk).order_by('-met_on', '-id'))
    return {
        **_student_bits(app),
        'since': timezone.localdate(assignment.started_at),
        'asked_for_help': help_asked(app),
        'latest_result': result,
        'standing': stand,
        'organisation': _org_name(assignment.mentor),
        'meetings': [meeting_dict(s, assignment.mentor_id) for s in sessions],
    }


def log_own_session(login, application_id, *, met_on, mode, minutes=None, notes='', next_step='',
                    concern=False):
    """The MENTOR logs one meeting with their current student. Refusals (`MentoringError`): not_found
    (not their current student, now or by the time the lock is held), file_closed, and 7b's bad_date,
    future_date, bad_mode, bad_minutes, notes_required, too_long, before_assignment. Returns the row."""
    assignment = assignment_for(login, application_id)
    if assignment is None:
        raise MentoringError('not_found')
    meeting = mentoring.clean_meeting(met_on=met_on, mode=mode, minutes=minutes, notes=notes,
                                      next_step=next_step)
    by = (login.email or '')[:254]
    with transaction.atomic():
        # 7b's lock: the application row, then its open assignment — a staff End, a change or a
        # Deactivate that committed first leaves no open row of THIS mentor's, and nothing is written.
        row, current = mentoring._locked_open(assignment.application)
        if not maintenance_scope.is_in_maintenance(row):
            raise MentoringError('file_closed')
        if current is None or current.pk != assignment.pk or current.mentor_id != login.mentor_id:
            raise MentoringError('not_found')
        session = mentoring.write_session(row, current, meeting, by=by, by_mentor=True,
                                          concern=concern is True)
        if session.concern:
            from . import activity
            activity.log_event(row, EVENT_MENTOR_CONCERN_RAISED, actor_email=by, internal=True,
                               meta={'mentor_id': current.mentor_id,
                                     'mentor': mentoring.mentor_name(current.mentor),
                                     'session_id': session.pk})
    return session
