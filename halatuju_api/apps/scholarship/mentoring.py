"""Mentoring — who mentors a scholar now, the change, the end, and the meetings staff log (student
maintenance Sprint 7b, 2026-11-01; owner rulings in docs/decisions.md the same day).

EVERY RULE IS HERE; the HTTP shapes are `views_admin/mentoring.py` (staff) and `views_bursary.py`
(the student's own tab).

- WHO ACTS (`may_act`): the roles that may read the Mentors roster — a super, an organisation admin, an
  admin — inside the organisation fence (`views_admin/mentoring.py` 404s another organisation's file).
  A reviewer, QC, finance, a source user and a mentor are refused (mentors see their students in 7c).
- ONE MENTOR AT A TIME. `assign` ends the open assignment (it stays, the history) and starts the new
  one in ONE transaction, holding a row lock on the application; a partial unique index
  (`mentor_assignment_one_open`) refuses a second open row even if two requests race past the lock.
- WHO MAY BE ASSIGNED (`refusal_for_mentor`): the application's OWN organisation's mentor, not
  deactivated (invited or active — an invited mentor is allowed), and NEVER the student themselves: a
  student's login may hold a mentor role (owner, 2026-10-31), so a mentor whose login is the student's
  — the same Supabase UID as the profile or one of its claimed aliases, or the same email as the
  profile's contact email or the application's notify email, case-blind — is refused `own_application`.
- A CLOSED FILE IS READ-ONLY (`maintenance_scope.is_in_maintenance`): no assign, end or meeting.
- MEETINGS: only while an assignment is open, with that assignment's mentor; `met_on` neither in the
  future nor before the assignment started (local dates).
- THE STUDENT IS EMAILED, NEVER THE MENTOR: "You have a mentor" (`student_comms` kind
  `mentor_assigned`; switchable per organisation, `student_email_catalogue.may_send`), sent after the
  transaction commits, only when staff left "Email the student" on. Its phone line only when the
  mentor shares their phone with students.
- ENDED BY OTHER DOORS, with no email: Deactivate / Revoke of a mentor (`end_for_mentor`, reason
  "Mentor deactivated", from `mentor_invite._switch_off`) and closing the file (`end_for_closure`,
  "File closed", from `closure.close_application`). Reactivating a mentor restores nothing.
- STAFF ONLY: meeting notes, next step, the end / change reason, the history. The student's payload
  (`student_payload`) is an ALLOWLIST. Mentors and meetings never reach sponsors or partners.

Every write logs to the student's file (`activity.log_event`: `mentor_assigned`, `mentor_changed`,
`mentor_ended`, `session_logged`) in the same transaction.
"""
import datetime
import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

from . import activity
from .maintenance_scope import is_in_maintenance
from .models import MentorAssignment, MentoringSession, Mentor, ScholarshipApplication
from .models.activity import (
    EVENT_MENTOR_ASSIGNED, EVENT_MENTOR_CHANGED, EVENT_MENTOR_ENDED, EVENT_SESSION_LOGGED,
)

logger = logging.getLogger('apps.scholarship.mentoring')

#: The email's catalogue key and `student_comms` kind.
EMAIL_KEY = 'mentor_assigned'
#: What an end by another door records as the (staff-only) reason.
REASON_DEACTIVATED = 'Mentor deactivated'
REASON_CLOSED = 'File closed'
#: The `cause` on a `mentor_ended` activity row.
CAUSE_STAFF, CAUSE_DEACTIVATED, CAUSE_CLOSED = 'staff', 'mentor_deactivated', 'file_closed'

MODES = tuple(code for code, _ in MentoringSession.MODE_CHOICES)
NOTES_MAX = 5000
NEXT_STEP_MAX = 500
REASON_MAX = 500
MINUTES_MAX = 1440
_FLUENT = ('conversational', 'fluent')


class MentoringError(Exception):
    """A refusal, with a machine code the view maps to a status."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


# ── who may act ──────────────────────────────────────────────────────────────────────────────
def may_act(caller):
    """The roles that act on (and read) a scholar's Mentoring tab: super, org_admin, admin — the
    Mentors roster's readers (`mentor_invite.may_read`). The ORGANISATION fence is the view's."""
    from .mentor_invite import may_read
    return may_read(caller)


def _same_org(caller, application):
    return bool(caller.is_super) or (caller.owning_organisation_id is not None
                                     and caller.owning_organisation_id == application.owning_organisation_id)


def may_assign(caller, application):
    """True when ``caller`` may assign, change or end a mentor, or log a meeting, on ``application``
    now: an actor of its own organisation (a super: any), and the file is in maintenance."""
    return (caller is not None and application is not None and may_act(caller)
            and _same_org(caller, application) and is_in_maintenance(application))


def _check_caller(caller, application):
    if caller is None or not may_act(caller):
        raise MentoringError('forbidden')
    if not _same_org(caller, application):
        raise MentoringError('not_found')
    if not is_in_maintenance(application):
        raise MentoringError('file_closed')


# ── who may be assigned ──────────────────────────────────────────────────────────────────────
def _login(mentor):
    from .mentor_invite import login_of
    return login_of(mentor)


def is_the_student(login, application):
    """True when this mentor LOGIN belongs to the student of ``application`` (see the module
    docstring): the same Supabase UID as the profile or a claimed alias, or the same email."""
    if login is None or application is None:
        return False
    profile_id = application.profile_id
    uid = (login.supabase_user_id or '').strip()
    if uid and profile_id:
        if uid == profile_id:
            return True
        from apps.courses.models_claim import ProfileLoginAlias
        if ProfileLoginAlias.objects.filter(alias_uid=uid, profile_id=profile_id).exists():
            return True
    email = (login.email or '').strip().lower()
    if not email:
        return False
    profile = getattr(application, 'profile', None)
    theirs = {(getattr(profile, 'contact_email', '') or '').strip().lower(),
              (application.notify_email or '').strip().lower()} - {''}
    return email in theirs


def refusal_for_mentor(application, mentor):
    """None when ``mentor`` may be assigned to ``application``, else the refusal code:
    `mentor_not_found` (unknown, or another organisation's — one answer, so neither is confirmed),
    `mentor_inactive` (deactivated or revoked), `own_application` (the mentor is the student)."""
    if mentor is None or mentor.organisation_id != application.owning_organisation_id:
        return 'mentor_not_found'
    if mentor.deactivated_at is not None:
        return 'mentor_inactive'
    if is_the_student(_login(mentor), application):
        return 'own_application'
    return None


def assignable_mentors(application):
    """The mentors the picker may offer for ``application``: its organisation's, not deactivated, never
    the student themselves — each with name, area, languages, status and how many scholars they have
    now. Their own rule is `refusal_for_mentor`; this list is that rule applied to the roster."""
    mentors = list(Mentor.objects.filter(organisation_id=application.owning_organisation_id,
                                         deactivated_at__isnull=True).order_by('id'))
    facts = mentor_facts(mentors)
    now = scholars_now([m.pk for m in mentors])
    out = []
    for m in mentors:
        f = facts.get(m.pk) or {}
        if is_the_student(f.get('login'), application):
            continue
        out.append({'id': m.pk, 'name': f.get('name', ''), 'area': m.area,
                    'languages': f.get('languages', []), 'other_language': f.get('other_language', ''),
                    'status': f.get('status', ''), 'scholars_now': now.get(m.pk, 0)})
    out.sort(key=lambda r: (r['status'] != 'active', (r['name'] or '').lower()))
    return out


def scholars_now(mentor_ids):
    """``{mentor_id: open assignments}`` in ONE query (the Mentors page's "Scholars now")."""
    from django.db.models import Count
    if not mentor_ids:
        return {}
    return dict(MentorAssignment.objects.filter(mentor_id__in=list(mentor_ids), ended_at__isnull=True)
                .values('mentor_id').annotate(n=Count('id')).values_list('mentor_id', 'n'))


def mentor_facts(mentors):
    """``{mentor_id: {login, name, email, phone, share_phone, about, languages, other_language,
    status}}`` — one query each for the logins, their profiles and their newest invitations."""
    from apps.courses.models import PartnerAdmin
    from . import mentor_invite
    from .models import Invitation, ReviewerProfile
    mentors = list(mentors)
    logins = {a.mentor_id: a for a in PartnerAdmin.objects.filter(mentor__in=mentors)}
    profiles = {p.partner_admin_id: p for p in ReviewerProfile.objects.filter(
        partner_admin__in=list(logins.values()))}
    issued = {}
    for inv in (Invitation.objects.filter(audience=mentor_invite.AUDIENCE, mentor__in=mentors)
                .order_by('mentor_id', '-created_at', '-id')):
        issued.setdefault(inv.mentor_id, bool(inv.credential_issued))
    out = {}
    for m in mentors:
        login = logins.get(m.pk)
        rp = profiles.get(login.pk) if login else None
        out[m.pk] = {
            'login': login,
            'name': (login.name if login else '') or '',
            'email': (login.email if login else '') or '',
            'phone': (rp.phone or '') if rp else '',
            'share_phone': bool(rp and rp.share_phone_with_students and (rp.phone or '').strip()),
            'about': (rp.about or '') if rp else '',
            'languages': languages_of(rp),
            'other_language': rp.spoken_other_language() if rp else '',
            'status': mentor_invite.status_of(m, login, issued.get(m.pk, False)),
        }
    return out


def languages_of(profile):
    """The en / ms / ta codes this person speaks conversationally or better (the Mentors page rule)."""
    if profile is None:
        return []
    pairs = (('en', profile.english_fluency), ('ms', profile.bm_fluency), ('ta', profile.tamil_fluency))
    return [code for code, level in pairs if level in _FLUENT]


# ── the writes ───────────────────────────────────────────────────────────────────────────────
def _locked_open(application):
    """Lock the application row (serialises every mentoring write on one file; a no-op on SQLite,
    where the partial unique index still holds), re-read it, and return ``(row, open assignment)``."""
    # The ONE application the caller already resolved through the file's fence (`_file_for`;
    # `_check_caller` re-checks its organisation), re-read under a lock — never a lookup.
    # org-fence: the caller's fenced application, re-read by its own pk.
    row = ScholarshipApplication.objects.select_for_update().filter(pk=application.pk).first()
    if row is None:
        raise MentoringError('not_found')
    current = (MentorAssignment.objects.select_for_update().select_related('mentor')
               .filter(application_id=row.pk, ended_at__isnull=True).first())
    return row, current


def mentor_name(mentor):
    """The mentor's name (their login's)."""
    login = _login(mentor)
    return (login.name if login else '') or ''


def _clean_reason(reason):
    text = (reason if isinstance(reason, str) else '').strip()
    if len(text) > REASON_MAX:
        raise MentoringError('too_long')
    return text


def assign(caller, application, mentor, *, reason='', email_student=True):
    """Make ``mentor`` this scholar's mentor: the open assignment (if any) ends with ``reason`` (staff
    only) and the new one starts — one transaction. Then, outside it, the student is emailed when
    ``email_student`` and the organisation's switch allow. Returns ``(assignment, emailed)``.

    Refusals (`MentoringError`): forbidden, not_found, file_closed, mentor_not_found,
    mentor_inactive, own_application, already_assigned (the same mentor is already current),
    too_long, conflict (a racing request won)."""
    _check_caller(caller, application)
    refusal = refusal_for_mentor(application, mentor)
    if refusal:
        raise MentoringError(refusal)
    reason = _clean_reason(reason)
    by = (caller.email or '')[:254]
    try:
        with transaction.atomic():
            row, current = _locked_open(application)
            if not is_in_maintenance(row):
                raise MentoringError('file_closed')
            if current is not None and current.mentor_id == mentor.pk:
                raise MentoringError('already_assigned')
            now = timezone.now()
            if current is not None:
                MentorAssignment.objects.filter(pk=current.pk, ended_at__isnull=True).update(
                    ended_at=now, ended_by_email=by, end_reason=reason)
            new = MentorAssignment.objects.create(application=row, mentor=mentor, started_by_email=by)
            meta = {'mentor_id': mentor.pk, 'mentor': mentor_name(mentor)}
            if current is None:
                activity.log_event(row, EVENT_MENTOR_ASSIGNED, actor_email=by, meta=meta)
            else:
                meta.update({'was_id': current.mentor_id, 'was': mentor_name(current.mentor)})
                activity.log_event(row, EVENT_MENTOR_CHANGED, actor_email=by, meta=meta)
    except IntegrityError:
        # Another request opened an assignment between our read and our write (the partial unique
        # index refused the second open row). Nothing of ours was kept.
        raise MentoringError('conflict')
    logger.info('AUDIT mentor_assigned app=%s mentor=%s changed=%s by=%s',
                application.pk, mentor.pk, current is not None, by)
    emailed = False
    if email_student:
        emailed = _send_you_have_a_mentor(application, new, mentor)
    return new, emailed


def end(caller, application, *, reason=''):
    """End this scholar's mentoring (staff): the open assignment gets ``ended_at`` and ``reason``.
    Refusals: forbidden, not_found, file_closed, no_mentor, too_long. Returns the ended row."""
    _check_caller(caller, application)
    reason = _clean_reason(reason)
    by = (caller.email or '')[:254]
    with transaction.atomic():
        row, current = _locked_open(application)
        if not is_in_maintenance(row):
            raise MentoringError('file_closed')
        if current is None:
            raise MentoringError('no_mentor')
        _end_row(row, current, by=by, reason=reason, cause=CAUSE_STAFF)
    logger.info('AUDIT mentor_ended app=%s mentor=%s by=%s', application.pk, current.mentor_id, by)
    current.refresh_from_db()
    return current


def _end_row(application, assignment, *, by, reason, cause):
    """End ONE open assignment and log it, inside the caller's transaction. False when it had already
    ended (a concurrent end won)."""
    done = MentorAssignment.objects.filter(pk=assignment.pk, ended_at__isnull=True).update(
        ended_at=timezone.now(), ended_by_email=(by or '')[:254], end_reason=reason)
    if done:
        activity.log_event(application, EVENT_MENTOR_ENDED, actor_email=by,
                           meta={'mentor_id': assignment.mentor_id, 'mentor': mentor_name(assignment.mentor),
                                 'cause': cause})
    return bool(done)


def end_for_mentor(mentor, by=''):
    """Deactivate / Revoke of ``mentor`` (`mentor_invite._switch_off`, inside its transaction): every
    open assignment of theirs ends — reason "Mentor deactivated", an activity line on each file, no
    email. Returns how many ended. Reactivating restores none of them."""
    n = 0
    for a in (MentorAssignment.objects.select_for_update().select_related('application', 'mentor')
              .filter(mentor=mentor, ended_at__isnull=True)):
        n += _end_row(a.application, a, by=by, reason=REASON_DEACTIVATED, cause=CAUSE_DEACTIVATED)
    return n


def end_for_closure(application, by=''):
    """Closing the file (`closure.close_application`, inside its transaction): the open assignment
    ends — reason "File closed", no email. Returns True when one ended."""
    a = (MentorAssignment.objects.select_for_update().select_related('mentor')
         .filter(application_id=application.pk, ended_at__isnull=True).first())
    if a is None:
        return False
    return _end_row(application, a, by=by, reason=REASON_CLOSED, cause=CAUSE_CLOSED)


def _parse_day(value):
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.date.fromisoformat(str(value or '').strip())
    except ValueError:
        return None


def _parse_minutes(value):
    if value in (None, ''):
        return None
    if isinstance(value, bool):
        raise MentoringError('bad_minutes')
    try:
        n = int(str(value).strip())
    except ValueError:
        raise MentoringError('bad_minutes')
    if n < 1 or n > MINUTES_MAX:
        raise MentoringError('bad_minutes')
    return n


def log_session(caller, application, *, met_on, mode, minutes=None, notes='', next_step=''):
    """Log one meeting with the CURRENT mentor. Refusals: forbidden, not_found, file_closed, bad_date,
    future_date, bad_mode, bad_minutes, notes_required, too_long, no_mentor, before_assignment."""
    _check_caller(caller, application)
    day = _parse_day(met_on)
    if day is None:
        raise MentoringError('bad_date')
    if day > timezone.localdate():
        raise MentoringError('future_date')
    if mode not in MODES:
        raise MentoringError('bad_mode')
    mins = _parse_minutes(minutes)
    notes = (notes if isinstance(notes, str) else '').strip()
    next_step = (next_step if isinstance(next_step, str) else '').strip()
    if not notes:
        raise MentoringError('notes_required')
    if len(notes) > NOTES_MAX or len(next_step) > NEXT_STEP_MAX:
        raise MentoringError('too_long')
    by = (caller.email or '')[:254]
    with transaction.atomic():
        row, current = _locked_open(application)
        if not is_in_maintenance(row):
            raise MentoringError('file_closed')
        if current is None:
            raise MentoringError('no_mentor')
        if day < timezone.localdate(current.started_at):
            raise MentoringError('before_assignment')
        session = MentoringSession.objects.create(
            application=row, mentor_id=current.mentor_id, assignment=current, met_on=day, mode=mode,
            minutes=mins, notes=notes, next_step=next_step, logged_by_email=by)
        activity.log_event(row, EVENT_SESSION_LOGGED, actor_email=by, meta={
            'mentor_id': current.mentor_id, 'mentor': mentor_name(current.mentor), 'mode': mode,
            'minutes': mins, 'met_on': day.isoformat()})
    return session


# ── the email ────────────────────────────────────────────────────────────────────────────────
def email_switch_on(application):
    """Whether the organisation sends "You have a mentor" (the Student communications switch)."""
    from .student_email_catalogue import may_send
    return may_send(application, EMAIL_KEY)


def _send_you_have_a_mentor(application, assignment, mentor):
    """To the STUDENT only (`application.notify_email`), never the mentor. Best-effort: a failure
    logs and answers False. Marks `emailed_student` when it went."""
    from . import student_comms
    if not email_switch_on(application):
        return False
    f = mentor_facts([mentor]).get(mentor.pk) or {}
    lang = student_comms.language_of(application)
    contact = ' · '.join(x for x in (f.get('email', ''), f.get('phone', '') if f.get('share_phone') else '') if x)
    try:
        ok = student_comms.send_student_email(
            application, EMAIL_KEY, mentor_name=f.get('name') or '—', mentor_area=mentor.area or '—',
            mentor_languages=languages_words(f.get('languages', []), f.get('other_language', ''), lang) or '—',
            mentor_contact=contact or '—')
    except Exception:   # an email never undoes the assignment
        logger.exception('mentor email failed (app %s)', application.pk)
        return False
    if ok:
        MentorAssignment.objects.filter(pk=assignment.pk).update(emailed_student=True)
        assignment.emailed_student = True
    return bool(ok)


#: Language names in the student's language, for the email (the web words its own).
LANGUAGE_WORDS = {
    'en': {'en': 'English', 'ms': 'Malay', 'ta': 'Tamil'},
    'ms': {'en': 'Bahasa Inggeris', 'ms': 'Bahasa Melayu', 'ta': 'Bahasa Tamil'},
    'ta': {'en': 'ஆங்கிலம்', 'ms': 'மலாய்', 'ta': 'தமிழ்'},
}


def languages_words(codes, other, lang):
    words = [LANGUAGE_WORDS.get(lang, LANGUAGE_WORDS['en'])[c] for c in codes]
    if other:
        words.append(other)
    return ', '.join(words)


# ── the readers ──────────────────────────────────────────────────────────────────────────────
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
                     'emailed': current.emailed_student} if current else None),
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
    if current is None:
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
