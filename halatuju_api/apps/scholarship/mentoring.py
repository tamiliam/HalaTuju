"""Mentoring — who mentors a scholar now, the change, the end, and the meetings staff log (student
maintenance Sprint 7b, 2026-11-01; owner rulings in docs/decisions.md the same day).

EVERY RULE AND EVERY WRITE IS HERE; the readers (the two tabs' payloads) are `mentoring_read.py`; the
HTTP shapes are `views_admin/mentoring.py` (staff) and `views_bursary.py` (the student's own tab).

- WHO ACTS (`may_act`): the roles that may read the Mentors roster — a super, an organisation admin, an
  admin — inside the organisation fence (`views_admin/mentoring.py` 404s another organisation's file).
  A reviewer, QC, finance, a source user and a mentor are refused (a mentor has its own door since
  7c: `mentor_desk.py`, which reuses `clean_meeting` / `write_session` below).
- S7c CONCERNS: a mentor's meeting may carry a concern; staff (these same roles) clear every open one
  on a file with `handle_concern` (idempotent; a later concern is open again).
- ONE MENTOR AT A TIME. `assign` ends the open assignment (it stays, the history) and starts the new
  one in ONE transaction, holding a row lock on the application; a partial unique index
  (`mentor_assignment_one_open`) refuses a second open row even if two requests race past the lock.
- WHO MAY BE ASSIGNED (`refusal_for_mentor`): the application's OWN organisation's mentor, not
  deactivated (invited or active — an invited mentor is allowed), and NEVER the student themselves: a
  student's login may hold a mentor role (owner, 2026-10-31), so a mentor whose login is the student's
  — the same Supabase UID as the profile or one of its claimed aliases, or the same email as the
  profile's contact email or the application's notify email, case-blind — is refused `own_application`.
  I4 (2026-11-08): and a mentor whose GIFTS hold the scholar's (`mentor_gift`; no gifts = every gift).
- A CLOSED FILE IS READ-ONLY (`maintenance_scope.is_in_maintenance`): no assign, end or meeting.
- MEETINGS: only while an assignment is open, with that assignment's mentor; `met_on` neither in the
  future nor before the assignment started (local dates).
- THE STUDENT IS EMAILED, NEVER THE MENTOR: "You have a mentor" (`student_comms` kind
  `mentor_assigned`; switchable per organisation, `student_email_catalogue.may_send`), sent after the
  transaction commits, only when staff left "Email the student" on. Its phone line only when the
  mentor shares their phone with students.
- ENDED BY OTHER DOORS, with no email: Deactivate / Revoke of a mentor (`end_for_mentor`, reason
  "Mentor deactivated", from `mentor_invite._switch_off`), every way OUT of a STAFF member's mentoring
  (S7d, `staff_mentor.py`: reason "Mentor stopped mentoring"), closing the file (`end_for_closure`,
  "File closed", from `closure.close_application`) and an award reverted to the pool
  (`end_for_award_revert`, "Award reverted", from `maintenance.reset_on_leaving`). Reactivating a
  mentor restores nothing.
- THE MENTOR TURNS OUT TO BE THE STUDENT (adversarial review, 2026-11-01). The student's own SIGN-IN
  email is not stored, so a mentor invited at it passes the assign-time check with no UID. Two doors
  that can make it true END the assignment (`end_if_self`, "Mentor is the student"): `get_admin`
  linking a UID onto a mentor row (`courses.views_admin._mentor_linked`) and a successful
  `mentor_invite._move_address`. Anything else (an alias claimed later, an email changed) is caught
  at READ time (`current_is_the_student`): the student is shown no mentor, staff see
  `current.is_the_student` ("end it"), and the email never goes. Reads never write.
- RACES: `assign` re-reads the mentor UNDER A LOCK inside its transaction and judges it again
  (Deactivate updates the Mentor row first, so the two serialise); every `select_for_update` here locks
  `of=('self',)` so a join never takes a second table's lock.
- WHO READS THE LINES: the four mentoring activity events (`EVENTS`) are left out of the file's activity
  list for a role outside `may_act` (a reviewer, QC) — they name the mentor.
- STAFF ONLY: meeting notes, next step, the end / change reason, the history. The student's payload
  (`mentoring_read.student_payload`) is an ALLOWLIST. Mentors and meetings never reach sponsors or partners.

Every write logs to the student's file (`activity.log_event`: `mentor_assigned`, `mentor_changed`,
`mentor_ended`, `session_logged`) in the same transaction.
"""
import datetime
import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

from . import activity, mentor_gift
from .maintenance_scope import is_in_maintenance
from .models import MentorAssignment, MentoringSession, Mentor, ScholarshipApplication
from .models.activity import (
    EVENT_MENTOR_ASSIGNED, EVENT_MENTOR_CHANGED, EVENT_MENTOR_CONCERN_HANDLED, EVENT_MENTOR_CONCERN_RAISED,
    EVENT_MENTOR_ENDED, EVENT_SESSION_LOGGED,
)

logger = logging.getLogger('apps.scholarship.mentoring')

#: The email's catalogue key and `student_comms` kind.
EMAIL_KEY = 'mentor_assigned'
#: What an end by another door records as the (staff-only) reason.
REASON_DEACTIVATED = 'Mentor deactivated'
REASON_CLOSED = 'File closed'
REASON_IS_STUDENT = 'Mentor is the student'
REASON_REVERTED = 'Award reverted'
#: S7d: a STAFF member's mentoring ended — Stop mentoring, or their staff account revoked, switched off,
#: deleted or moved to a role that may not mentor (`staff_mentor.py`). Never their staff login's doing.
REASON_STOPPED = 'Mentor stopped mentoring'
#: The `cause` on a `mentor_ended` activity row.
CAUSE_STAFF, CAUSE_DEACTIVATED, CAUSE_CLOSED = 'staff', 'mentor_deactivated', 'file_closed'
CAUSE_IS_STUDENT, CAUSE_REVERTED = 'mentor_is_student', 'award_reverted'
CAUSE_STOPPED = 'mentor_stopped'   # S7d
#: The activity events a role outside `may_act` is never served (they name the mentor; review fix 2) —
#: S7c adds the concern raised / handled lines.
EVENTS = (EVENT_MENTOR_ASSIGNED, EVENT_MENTOR_CHANGED, EVENT_MENTOR_ENDED, EVENT_SESSION_LOGGED,
          EVENT_MENTOR_CONCERN_RAISED, EVENT_MENTOR_CONCERN_HANDLED)

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
    """Who acts on (and reads) a scholar's Mentoring tab: the v2 key `mentoring.edit` (Team tables T5c;
    it implies `.view` — this one door both reads and acts). Holders as before: super, org_admin, the
    `admin` label — the same people as the Mentors roster's readers (`mentor_invite.may_read`), now by
    their own key (lead ruling T5a: `team.view` must never cover this tab). The ORGANISATION fence is
    the view's."""
    from apps.courses import staff_tables
    return staff_tables.opens_door(caller, 'mentoring')


def may_read_mentoring(caller):
    """Who READS a scholar's Mentoring tab and the mentor card on the file (A1.10a, TD-498): the v2 key
    `mentoring.view`. Today the same holders as `may_act`; the tab's `can_act` and every write still ask
    `may_act` (`may_assign`, `_check_caller`)."""
    from apps.courses import staff_tables
    return staff_tables.opens_door(caller, 'mentoring_read')


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


def is_the_student(login, application, aliased=None):
    """True when this mentor LOGIN belongs to the student of ``application`` (see the module
    docstring): the same Supabase UID as the profile or a claimed alias, or the same email.
    ``aliased`` (TD-500): the profile ids this login's UID is a claimed alias of, read for a whole
    list in one query; None asks the database for this one application, as before."""
    if login is None or application is None:
        return False
    profile_id = application.profile_id
    uid = (login.supabase_user_id or '').strip()
    if uid and profile_id:
        if uid == profile_id:
            return True
        from apps.courses.models_claim import ProfileLoginAlias
        if (profile_id in aliased if aliased is not None
                else ProfileLoginAlias.objects.filter(alias_uid=uid, profile_id=profile_id).exists()):
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
    `mentor_not_found` (unknown, another organisation's — one answer, so neither is confirmed — or, S7d,
    a mentor record with no login), `mentor_inactive` (deactivated or revoked; S7d: a login that is off,
    or a staff member who may not mentor now), `own_application` (the mentor is the student), and (I4)
    `mentor_not_in_gift` (the mentor's gifts do not include the scholar's — `mentor_gift.allows`)."""
    if mentor is None or mentor.organisation_id != application.owning_organisation_id:
        return 'mentor_not_found'
    if mentor.deactivated_at is not None:
        return 'mentor_inactive'
    login = _login(mentor)
    if login is None:
        return 'mentor_not_found'   # S7d review fix 2: a mentor record nobody signs in as
    if not login.is_active or _staff_not_mentoring(login):
        return 'mentor_inactive'
    if is_the_student(login, application):
        return 'own_application'
    return None if mentor_gift.allows(mentor, application) else 'mentor_not_in_gift'


def _staff_not_mentoring(login):
    """S7d, belt and braces: a STAFF member's mentor record whose login may not mentor now (revoked, or
    a role that may not mentor) is never assignable, even if a door out missed stamping the mentor."""
    return login is not None and login.is_staff_mentor and not login.mentors_now


def assignable_mentors(application):
    """The mentors the picker may offer for ``application``: its organisation's, not deactivated, never
    the student themselves — each with name, area, languages, status and how many scholars they have
    now. Their own rule is `refusal_for_mentor`; this list is that rule applied to the roster."""
    mentors = list(Mentor.objects.filter(organisation_id=application.owning_organisation_id,
                                         deactivated_at__isnull=True).order_by('id'))
    facts = mentor_facts(mentors)
    now = scholars_now([m.pk for m in mentors])
    in_gift = mentor_gift.allowed_ids([m.pk for m in mentors], application)   # I4: one query
    out = []
    for m in mentors:
        f = facts.get(m.pk) or {}
        login = f.get('login')
        # S7d review fix 2: the picker offers what `refusal_for_mentor` accepts — a login that exists,
        # is on, and (a staff member's) may mentor now; I4: and whose gifts hold the scholar's.
        if (login is None or not login.is_active or _staff_not_mentoring(login) or m.pk not in in_gift
                or is_the_student(login, application)):
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
    from .staff_contact import staff_screen_phone
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
            # S7d review fix 1: what STAFF screens show — a staff mentor's number only under the team
            # rule (`staff_contact.staff_screen_phone`). `phone` above is for the student's own rule.
            'staff_phone': staff_screen_phone(login, rp),
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
    # `of=('self',)`: lock the assignment row only, never the joined mentor (review fix 3 — a
    # Deactivate locks the MENTOR first, so a join lock here could cross it).
    current = (MentorAssignment.objects.select_for_update(of=('self',)).select_related('mentor')
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
    mentor_inactive, own_application, mentor_not_in_gift, already_assigned (the same mentor is current),
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
            # Review fix 3: the mentor is re-read UNDER A LOCK and judged again, so a Deactivate
            # committed since the check above (`mentor_invite._switch_off` updates the Mentor row
            # first, under the same row lock) can never be assigned past.
            mentor = Mentor.objects.select_for_update().filter(pk=mentor.pk).first()
            refusal = refusal_for_mentor(row, mentor)
            if refusal:
                raise MentoringError(refusal)
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


def _open_of_mentor(mentor):
    return (MentorAssignment.objects.select_for_update(of=('self',))
            .select_related('application__profile', 'mentor')
            .filter(mentor=mentor, ended_at__isnull=True))


def end_for_mentor(mentor, by='', *, reason=REASON_DEACTIVATED, cause=CAUSE_DEACTIVATED):
    """Deactivate / Revoke of ``mentor`` (`mentor_invite._switch_off`, inside its transaction): every
    open assignment of theirs ends — reason "Mentor deactivated", an activity line on each file, no
    email. Returns how many ended. Reactivating restores none of them. S7d: a staff member's way out
    (`staff_mentor.py`) passes "Mentor stopped mentoring" / `mentor_stopped`."""
    n = 0
    for a in _open_of_mentor(mentor):
        n += _end_row(a.application, a, by=by, reason=reason, cause=cause)
    return n


def end_if_self(mentor, by=''):
    """Review fix 1: end every open assignment of ``mentor`` whose application is now the MENTOR'S
    OWN (`is_the_student`: `get_admin` just linked the student's own UID onto a mentor row invited at
    the student's sign-in address, or `mentor_invite._move_address` moved an assigned mentor onto
    it). Reason "Mentor is the student", no email, an activity line on each file, in a transaction of
    its own (a savepoint inside the caller's). Returns how many ended."""
    if mentor is None:
        return 0
    login = _login(mentor)
    n = 0
    with transaction.atomic():
        for a in _open_of_mentor(mentor):
            if is_the_student(login, a.application):
                n += _end_row(a.application, a, by=by, reason=REASON_IS_STUDENT, cause=CAUSE_IS_STUDENT)
    if n:
        logger.warning('AUDIT mentor_is_student mentor=%s ended=%s', mentor.pk, n)
    return n


def _end_open_of_application(application, *, by, reason, cause):
    with transaction.atomic():   # a savepoint inside the caller's transaction; a lock needs one
        a = (MentorAssignment.objects.select_for_update(of=('self',)).select_related('mentor')
             .filter(application_id=application.pk, ended_at__isnull=True).first())
        if a is None:
            return False
        return _end_row(application, a, by=by, reason=reason, cause=cause)


def end_for_closure(application, by=''):
    """Closing the file (`closure.close_application`, inside its transaction): the open assignment
    ends — reason "File closed", no email. Returns True when one ended."""
    return _end_open_of_application(application, by=by, reason=REASON_CLOSED, cause=CAUSE_CLOSED)


def end_for_award_revert(application, by=''):
    """Review fix 4: an award that falls back to the pool (`maintenance.reset_on_leaving`, whose one
    caller is `award_revert.revert_to_pool`) ends the open assignment — reason "Award reverted", no
    email. Returns True when one ended."""
    return _end_open_of_application(application, by=by, reason=REASON_REVERTED, cause=CAUSE_REVERTED)


def current_is_the_student(assignment, application):
    """READ-TIME GUARD (review fix 1b): True when this open assignment's mentor is, by now, the
    student (an alias claimed, an email changed since the assign). Reads never write: the readers
    treat it as no mentor for the student, flag it for staff, and never send the email."""
    return assignment is not None and is_the_student(_login(assignment.mentor), application)


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


def clean_meeting(*, met_on, mode, minutes=None, notes='', next_step=''):
    """THE meeting validation, for staff (`log_session`) and the mentor (`mentor_desk`) alike:
    ``(day, mode, minutes, notes, next_step)``. Refusals: bad_date, future_date, bad_mode, bad_minutes,
    notes_required, too_long. (`before_assignment` needs the assignment: `write_session`.)"""
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
    return day, mode, mins, notes, next_step


def write_session(row, current, meeting, *, by, by_mentor=False, concern=False):
    """Write ONE meeting on the open assignment ``current`` of the LOCKED application ``row`` (the
    caller's transaction) and log it: `session_logged` (`by_mentor` in its meta when the mentor
    logged it). ``meeting`` is `clean_meeting`'s answer. Refuses `before_assignment`."""
    day, mode, mins, notes, next_step = meeting
    if day < timezone.localdate(current.started_at):
        raise MentoringError('before_assignment')
    session = MentoringSession.objects.create(
        application=row, mentor_id=current.mentor_id, assignment=current, met_on=day, mode=mode,
        minutes=mins, notes=notes, next_step=next_step, logged_by_email=by,
        logged_by_mentor=bool(by_mentor), concern=bool(concern))
    meta = {'mentor_id': current.mentor_id, 'mentor': mentor_name(current.mentor), 'mode': mode,
            'minutes': mins, 'met_on': day.isoformat()}
    if by_mentor:
        meta['by_mentor'] = True
    activity.log_event(row, EVENT_SESSION_LOGGED, actor_email=by, meta=meta)
    return session


def log_session(caller, application, *, met_on, mode, minutes=None, notes='', next_step=''):
    """STAFF log one meeting with the CURRENT mentor. Refusals: forbidden, not_found, file_closed, bad_date,
    future_date, bad_mode, bad_minutes, notes_required, too_long, no_mentor, before_assignment."""
    _check_caller(caller, application)
    meeting = clean_meeting(met_on=met_on, mode=mode, minutes=minutes, notes=notes, next_step=next_step)
    by = (caller.email or '')[:254]
    with transaction.atomic():
        row, current = _locked_open(application)
        if not is_in_maintenance(row):
            raise MentoringError('file_closed')
        if current is None:
            raise MentoringError('no_mentor')
        return write_session(row, current, meeting, by=by)


def handle_concern(caller, application):
    """S7c — staff's "Mark as handled": every OPEN concern on this file is stamped handled (who, when)
    and one `mentor_concern_handled` line is logged. IDEMPOTENT: nothing open → nothing written, 0.
    A later concern (a new meeting) is open again. Refusals: forbidden, not_found, file_closed."""
    _check_caller(caller, application)
    by = (caller.email or '')[:254]
    with transaction.atomic():
        row, _current = _locked_open(application)
        if not is_in_maintenance(row):
            raise MentoringError('file_closed')
        n = MentoringSession.objects.filter(application_id=row.pk, concern=True,
                                            concern_handled_at__isnull=True).update(
            concern_handled_at=timezone.now(), concern_handled_by_email=by)
        if n:
            activity.log_event(row, EVENT_MENTOR_CONCERN_HANDLED, actor_email=by, meta={'count': n},
                               internal=True)
    if n:
        logger.info('AUDIT mentor_concern_handled app=%s count=%s by=%s', application.pk, n, by)
    return n


# ── the email ────────────────────────────────────────────────────────────────────────────────
def email_switch_on(application):
    """Whether the organisation sends "You have a mentor" (the Student communications switch)."""
    from .student_email_catalogue import may_send
    return may_send(application, EMAIL_KEY)


def _send_you_have_a_mentor(application, assignment, mentor):
    """To the STUDENT only (`application.notify_email`), never the mentor. Best-effort: a failure
    logs and answers False. Marks `emailed_student` when it went."""
    from . import student_comms
    if not email_switch_on(application) or current_is_the_student(assignment, application):
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
