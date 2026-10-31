"""Mentoring — the READERS (student maintenance Sprint 7b, 2026-11-01): the staff Mentoring tab's
payload, the student's own tab and whether it shows, and "asked for help". Moved verbatim out of
`mentoring.py` (which holds every RULE and every write) to keep both under the 600-line standard.

⚠ READS NEVER WRITE. A current mentor who is, by now, the student (`mentoring.current_is_the_student`)
is shown to nobody as the student's mentor and is flagged for staff; ending it is a write's job.
"""
from django.utils import timezone

from .maintenance_scope import is_in_maintenance
from .mentoring import (
    assignable_mentors, current_is_the_student, email_switch_on, may_assign, mentor_facts,
)
from .models import MentorAssignment, MentoringSession, Mentor


def _people(emails):
    """``{email: {name, role}}`` for the staff who assigned or logged — ONE query."""
    from apps.courses.models import PartnerAdmin
    emails = {e for e in emails if e}
    if not emails:
        return {}
    return {a.email.lower(): {'name': a.name or '', 'role': a.role or ''}
            for a in PartnerAdmin.objects.filter(email__in=list(emails))}


def _who(people, email):
    p = people.get((email or '').lower())
    return {'email': email or '', 'name': (p or {}).get('name', ''), 'role': (p or {}).get('role', '')}


def help_asked(application):
    """What the scholar asked for when applying (`help_university` / `help_scholarship` yes or not
    sure) and whether staff flagged them for mentoring — the Scholars list's "Asked for help"."""
    yes = ('yes', 'unsure')
    return {'university': application.help_university in yes,
            'scholarship': application.help_scholarship in yes,
            'flagged': bool(application.mentoring_candidate)}


def file_payload(caller, application):
    """The staff Mentoring tab for ONE application the view has fenced: the current mentor (staff
    always see the phone), the history (ended, with reasons), every meeting with its notes, what the
    scholar asked for, the mentors the picker may offer, `can_act` and the email switch."""
    rows = list(MentorAssignment.objects.filter(application_id=application.pk)
                .select_related('mentor').order_by('-started_at', '-id'))
    sessions = list(MentoringSession.objects.filter(application_id=application.pk)
                    .select_related('mentor').order_by('-met_on', '-id'))
    mentors = {r.mentor_id: r.mentor for r in rows}
    mentors.update({s.mentor_id: s.mentor for s in sessions})
    facts = mentor_facts(mentors.values())
    people = _people([r.started_by_email for r in rows] + [r.ended_by_email for r in rows]
                     + [s.logged_by_email for s in sessions])
    counts, last = {}, {}
    for s in sessions:
        if s.assignment_id:
            counts[s.assignment_id] = counts.get(s.assignment_id, 0) + 1
            last.setdefault(s.assignment_id, s.met_on)

    def mentor_bits(mid):
        f = facts.get(mid) or {}
        return {'mentor_id': mid, 'name': f.get('name', ''), 'email': f.get('email', ''),
                'phone': f.get('phone', ''), 'area': mentors[mid].area, 'languages': f.get('languages', []),
                'other_language': f.get('other_language', ''), 'status': f.get('status', '')}

    current = next((r for r in rows if r.ended_at is None), None)
    can_act = may_assign(caller, application)
    return {
        'current': ({**mentor_bits(current.mentor_id), 'id': current.pk, 'since': current.started_at,
                     'assigned_by': _who(people, current.started_by_email),
                     'meetings': counts.get(current.pk, 0), 'last_meeting': last.get(current.pk),
                     'emailed': current.emailed_student,
                     # Review fix 1b: the mentor is, by now, the student — the tab says "end it".
                     'is_the_student': current_is_the_student(current, application)}
                    if current else None),
        'history': [{'id': r.pk, 'mentor_id': r.mentor_id, 'name': (facts.get(r.mentor_id) or {}).get('name', ''),
                     'started_at': r.started_at, 'ended_at': r.ended_at, 'end_reason': r.end_reason,
                     'ended_by': _who(people, r.ended_by_email), 'meetings': counts.get(r.pk, 0)}
                    for r in rows if r.ended_at is not None],
        'meetings': [{'id': s.pk, 'met_on': s.met_on, 'mode': s.mode, 'minutes': s.minutes,
                      'notes': s.notes, 'next_step': s.next_step,
                      'mentor_name': (facts.get(s.mentor_id) or {}).get('name', ''),
                      'logged_by': _who(people, s.logged_by_email), 'created_at': s.created_at}
                     for s in sessions],
        'asked_for_help': help_asked(application),
        'assignable': assignable_mentors(application) if can_act else [],
        'can_act': can_act,
        'file_closed': not is_in_maintenance(application),
        'email_switch_on': email_switch_on(application),
    }


def tab_shown(application):
    """The student's Mentoring tab appears when they have (or had) an assignment, or their
    organisation has at least one mentor who is not deactivated ("a tab appears only when its
    module is switched on")."""
    if MentorAssignment.objects.filter(application_id=application.pk).exists():
        return True
    return Mentor.objects.filter(organisation_id=application.owning_organisation_id,
                                 deactivated_at__isnull=True).exists()


def student_payload(application):
    """The STUDENT's Mentoring tab — an ALLOWLIST: the CURRENT mentor's name, area, languages, About, email, the
    phone ONLY when the mentor shares it with students, since when, and the meetings with this mentor
    as date + how. Never notes, next step, minutes, history, a reason, who logged it, or a photo."""
    current = (MentorAssignment.objects.filter(application_id=application.pk, ended_at__isnull=True)
               .select_related('mentor').first())
    if current is None or current_is_the_student(current, application):
        return {'mentor': None, 'meetings': []}
    f = mentor_facts([current.mentor]).get(current.mentor_id) or {}
    meetings = (MentoringSession.objects.filter(assignment_id=current.pk)
                .order_by('-met_on', '-id').values('met_on', 'mode'))
    return {
        'mentor': {'name': f.get('name', ''), 'area': current.mentor.area,
                   'languages': f.get('languages', []), 'other_language': f.get('other_language', ''),
                   'about': f.get('about', ''), 'email': f.get('email', ''),
                   'phone': f.get('phone', '') if f.get('share_phone') else '',
                   'since': timezone.localdate(current.started_at)},
        'meetings': [{'met_on': m['met_on'], 'mode': m['mode']} for m in meetings],
    }
