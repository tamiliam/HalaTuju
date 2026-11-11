"""Mentors — the Mentors page's list, the mentor invite, and the staff actions (student maintenance
Sprint 7a, 2026-10-31). The rules are in `apps/scholarship/mentor_invite.py`; this module is only the
HTTP shapes:

- `invite_mentor` — `POST admin/invitations/` with `audience='mentor'` `{name, email, programme_ids?}`,
  routed here by `AdminInvitationsView.post` (the source invite's door; a super names the organisation
  with `?org=`). I4: `programme_ids` are the gifts they mentor in (`[]` / absent = every gift);
- `AdminMentorsView` — `GET admin/mentors/`: every mentor of the caller's organisation (a super:
  every organisation's, narrowed by `?org=`), with the status counts;
- `AdminMentorView` — `PATCH admin/mentors/<id>/` `{name?, email?}`: staff correct a name or an
  address until the first sign-in (409 `managed_by_mentor` after it);
- `AdminMentorView.delete` — Sprint T2 (D6): `DELETE admin/mentors/<id>/` a pure mentor with no work;
- `AdminMentorActionView` — `POST admin/mentors/<id>/<resend|revoke|deactivate|reactivate|stop|resume>/`;
- `AdminStaffMentorsView` — S7d (2026-11-01): `GET admin/mentors/staff/` the staff the "Add a staff member
  as mentor" sheet may offer; `POST admin/mentors/staff/` `{admin_id}` adds one (`staff_mentor.py`).

⚠ S7d: A STAFF MENTOR's login is their STAFF login. Their row carries `staff_role`; only `stop` ("Stop
mentoring") and `resume` ("Mentor again") act on it — Resend, Revoke, Deactivate, Reactivate and the
name / email edit answer 400 `staff_mentor` (their sign-in is People's). `stop` / `resume` on a pure
mentor answer 400 `not_staff`.

⚠ WHO: reading — super, org_admin, admin (read-only); acting — super, org_admin. Anyone else 403;
another organisation's mentor 404, never 403. ⚠ MENTORS NEVER REACH SPONSORS OR PARTNERS: nothing
here is on a sponsor, partner or source surface. Each action writes an AUDIT line and, for the
invitation doors, the `Invitation` record — the source pattern's trail.
"""
import logging

from rest_framework import status
from rest_framework.response import Response

from apps.courses.models import PartnerAdmin

from .base import _AdminBase, scholars_scope
from .source_users import _error, _iso
from .sources import _SourcesBase, text_of

# ⚠ THE PACKAGE'S name, never `__name__` — an audit line must stay on the scrape metric (H11).
logger = logging.getLogger('apps.scholarship.views_admin')

#: 409 for an address that already has an ADMIN sign-in (staff, source or another mentor). One
#: sentence for every case, so it confirms nothing about the other account. A student's or sponsor's
#: login is not refused (owner ruling 2026-10-31; `mentor_invite`).
ALREADY_STAFF = ("This email address already has a HalaTuju admin sign-in, so it can't be invited as "
                 "a mentor. Ask HalaTuju support.")

#: Request #57 (wording only): the same 409 refusal, but when the address is a team member of THIS
#: organisation who could be added as a mentor on their own sign-in, the message says where to go.
ALREADY_TEAM = ('This person is already on your team. To make them a mentor, go to Mentors, press '
                '"Add Mentor" and choose them from the list (no invitation is needed).')

#: M1a: the address is an ARCHIVED staff member of this organisation; they come back by the staff invite.
USE_STAFF_INVITE = ('This person was on your team before. Invite them again from Team, with the staff invite, '
                    'to bring them back.')

_FLUENT = ('conversational', 'fluent')


def _is_addable_team_member(email, organisation):
    """True when ``email`` is an eligible staff login of ``organisation`` that is not a mentor yet
    (the people the "Add a staff member as mentor" sheet offers). Only their OWN organisation's
    caller learns this, so nothing leaks across organisations."""
    from .. import staff_mentor
    login = PartnerAdmin.objects.filter(email__iexact=email).order_by('id').first()
    return (staff_mentor.eligible(login) and login.mentor_id is None
            and login.owning_organisation_id == organisation.pk)


def _bad_email(email):
    return '@' not in email or '.' not in email.rsplit('@', 1)[-1]


def _name_and_email(data, *, required):
    """`(name, email, error)` from a request body: text, trimmed, the email lowercased and shaped."""
    name, bad_name = text_of(data.get('name'))
    email, bad_email = text_of(data.get('email'))
    if bad_name or bad_email:
        return None, None, bad_name or bad_email
    name, email = name.strip()[:200], email.strip().lower()
    if (required or 'email' in data) and _bad_email(email):
        return None, None, _error('bad_email', status.HTTP_400_BAD_REQUEST)
    if (required or 'name' in data) and not name:
        return None, None, _error('name_required', status.HTTP_400_BAD_REQUEST)
    return (name if (required or 'name' in data) else None,
            email if (required or 'email' in data) else None, None)


def invite_mentor(request, admin):
    """`POST admin/invitations/` `{audience: 'mentor', name, email, programme_ids?}` → 201 `{id, mentor,
    emailed, google, already_registered, message}`. Refusals: 403 not super / org_admin; 400 `bad_email`,
    `name_required`, `organisation_required`, `gift_required` (I4: not a list); 404 an `?org=` outside the
    fence, or (I4) a gift that is not one of the organisation's ACTIVE gifts; 409 `already_staff`;
    500 `not_configured`; 502 `create_failed`."""
    from .. import mentor_gift, mentor_invite
    if not mentor_invite.may_invite(admin):
        return Response({'error': 'Your admin role cannot perform this action.'},
                        status=status.HTTP_403_FORBIDDEN)
    data = request.data if isinstance(request.data, dict) else {}
    name, email, bad = _name_and_email(data, required=True)
    if bad:
        return bad
    # The same rule a new source follows: the caller's own organisation; a super may name one.
    owner, err = _SourcesBase()._new_source_owner(request, admin)
    if err:
        if err.status_code == status.HTTP_404_NOT_FOUND:
            return err
        return _error('organisation_required', status.HTTP_400_BAD_REQUEST,
                      'Say which organisation this mentor belongs to.')
    gifts, refusal = mentor_gift.choose(data.get('programme_ids'), owner, active_only=True)
    if refusal is not None:
        return refusal
    from apps.courses import supabase_admin
    if supabase_admin.supabase_config() is None:
        return _error('not_configured', status.HTTP_500_INTERNAL_SERVER_ERROR,
                      'Supabase service role key not configured')
    done = mentor_invite.invite(admin, organisation=owner, email=email, name=name, gifts=gifts)
    if done.error == 'use_staff_invite':   # M1a: an archived staff member comes back by the staff invite
        return _error(done.error, status.HTTP_409_CONFLICT, USE_STAFF_INVITE)
    if done.error == 'already_staff':
        if _is_addable_team_member(email, owner):
            return _error('already_team', status.HTTP_409_CONFLICT, ALREADY_TEAM)
        return _error('already_staff', status.HTTP_409_CONFLICT, ALREADY_STAFF)
    if done.error:
        return _error('create_failed', status.HTTP_502_BAD_GATEWAY,
                      'Could not create their sign-in just now. Nothing was saved; try again.')
    logger.info('AUDIT mentor_invited mentor=%s account=%s org=%s gifts=%s by=%s',
                done.mentor.pk, done.account.pk, owner.pk,
                ','.join(g.code for g in gifts) or '(every gift)', admin.email or '')
    row = mentor_rows(admin, [done.mentor])[0]
    return Response({
        'id': done.invitation.id, 'mentor': row, 'emailed': done.emailed, 'google': done.google,
        'already_registered': done.already_registered,
        'message': (f'{name} invited. Sign-in details emailed to {email}.' if done.emailed
                    else f'{name} was added, but the email could not be sent. Use Resend to try again.'),
    }, status=status.HTTP_201_CREATED)


def mentor_rows(caller, mentors, *, team=False):
    """The Mentors page's rows for ``mentors`` — ONE query each for the logins, their profiles and
    their invitations, whatever the page size. An ALLOWLIST: name, email (never the phone: no group table
    shows one, M1a O16; the person page's `person` block has it, `staff_person.phone_of`), status, area,
    languages, invited / signed-in times, `manageable` (the endpoints' own rule, so the screen never offers a
    refused button), `scholars_now` (S7b: their open mentoring assignments) and (I4) `gifts`
    `[{id, code, name}]` with `every_gift` (no gifts = every gift) — ONE more query (`mentor_gift.gifts_by_mentor`).

    ``team`` (Team tables T3, the Team -> Mentors table): also `tables` / `lead` (the "Also in" chips,
    `staff_tables.tables`) and the work columns `meetings_90`, `last_meeting`, `concerns_open`
    (`mentor_detail.team_columns`, ONE more query)."""
    from .. import mentor_gift, mentor_invite, staff_footprint
    from ..mentoring import scholars_now
    from ..models import Invitation, ReviewerProfile
    # The mentor rides along: `status_of` / `mentors_now` read `login.mentor` (no query per row).
    logins = {a.mentor_id: a for a in PartnerAdmin.objects.filter(mentor__in=mentors)
              .select_related('mentor')}
    # Sprint T2, review S1: every login's footprint in ONE query for the page (`footprints`).
    footprints = staff_footprint.footprints(list(logins.values()))
    now = scholars_now([m.pk for m in mentors])   # S7b: ONE query for every row's open assignments
    gifts = mentor_gift.gifts_by_mentor([m.pk for m in mentors])   # I4: ONE query
    profiles = {p.partner_admin_id: p for p in ReviewerProfile.objects.filter(
        partner_admin__in=list(logins.values()))}
    newest = {}
    for inv in (Invitation.objects.filter(audience=mentor_invite.AUDIENCE, mentor__in=mentors)
                .order_by('mentor_id', '-created_at', '-id')):
        newest.setdefault(inv.mentor_id, inv)
    rows = []
    for m in mentors:
        login = logins.get(m.pk)
        rp = profiles.get(login.pk) if login else None
        inv = newest.get(m.pk)
        # Review fix: "signed in" is `mentor_invite.has_signed_in`, fed the newest invitation's
        # `credential_issued` so the list reads it without a query per row.
        issued = bool(inv and inv.credential_issued)
        staff = login is not None and login.is_staff_mentor
        rows.append({
            'id': m.pk,
            # S7d: the staff role of a staff member who also mentors ("Staff · <role>"); None for a
            # mentor login. Their status is active / inactive only — their sign-in is People's.
            'staff_role': login.role if staff else None,
            'name': login.name if login else '',
            'email': login.email if login else '',
            'status': mentor_invite.status_of(m, login, issued),
            'area': m.area,
            'languages': {'en': getattr(rp, 'english_fluency', '') or '',
                          'ms': getattr(rp, 'bm_fluency', '') or '',
                          'ta': getattr(rp, 'tamil_fluency', '') or ''},
            # Only when spoken conversationally or better (`ReviewerProfile.spoken_other_language`).
            'other_language': rp.spoken_other_language() if rp else '',
            'invited_at': _iso((inv.last_sent_at or inv.created_at) if inv else m.created_at),
            'signed_in': mentor_invite.has_signed_in(login, issued),
            'last_seen_at': _iso(login.last_seen_at) if login else None,
            'deactivated_at': _iso(m.deactivated_at),
            'manageable': mentor_invite.manageable(caller, m),
            'scholars_now': now.get(m.pk, 0),   # S7b
            'gifts': gifts.get(m.pk, []),        # I4: none = every gift
            'every_gift': m.pk not in gifts,
            **_delete_fields(caller, m, login, staff, footprints),
        })
    if team:
        from apps.courses import staff_permissions as sp
        from apps.courses import staff_tables
        from ..mentor_detail import empty_columns, team_columns
        work = team_columns([m.pk for m in mentors])
        for m, row in zip(mentors, rows):
            login = logins.get(m.pk)
            row['tables'] = list(staff_tables.tables(login)) if login else []
            row['lead'] = bool(login and sp.is_lead_tier(login))
            row.update(work.get(m.pk, empty_columns()))
    return rows


def _delete_fields(caller, mentor, login, staff, footprints):
    """Sprint T2 (D6): `work` (the login's footprint, `{}` for none), `deletable` — a PURE mentor
    this caller manages with no work — and `delete_never` (review N2): no Delete is ever drawn for
    a row nobody may delete here. A staff mentor is never deleted here (their row is deleted from
    Team -> Admins / Reviewers, where mentoring counts as work); nor is a row with no login, or one
    this caller does not manage."""
    from .. import mentor_invite
    work = footprints.get(login.pk, {}) if login is not None else {}
    never = login is None or staff or not mentor_invite.manageable(caller, mentor)
    return {'work': work, 'deletable': not never and not work, 'delete_never': never}


def mentor_kind_extras(caller, mentor_ids):
    """The Invitations page's Mentor tab (S7b follow-up): `{mentors: [...]}` — the Mentors page's own
    rows (`mentor_rows`, with `manageable`) for the mentors behind the waiting invitations. The ids
    come from invitations already fenced to the caller's organisation; the mentors are fenced again
    here (a super: any organisation)."""
    from .. import mentor_invite
    from ..models import Mentor
    if not mentor_invite.may_read(caller):     # review fix 1: the roster's own readers only
        return {'mentors': []}
    qs = Mentor.objects.filter(pk__in=list(mentor_ids))
    if not getattr(caller, 'is_super', False):
        qs = qs.filter(organisation_id=caller.owning_organisation_id)
    return {'mentors': mentor_rows(caller, list(qs.order_by('id')))}


class _MentorsBase(_AdminBase):
    """The fence every Mentors endpoint shares."""

    def sees_scholars(self, admin):
        """T3 review (2026-11-03): may ``admin`` see the SCHOLAR side of a mentor (who they mentor, the
        standing, the meetings per scholar, the concerns)? The Scholars list's own read rule: since sprint
        S1 the `scholars` key (`scholars_scope` 'all'; a super, the org admin, an admin preset or a saved
        set naming it), no longer `see_all`. An admin holding only money keys, or only `see_all`, reads the
        Mentors table (its gate is the role) but never a scholar's data through it."""
        return scholars_scope(admin) == 'all'

    def _reader(self, request):
        from .. import mentor_invite
        admin = self.get_admin(request)
        if not admin:
            return None, self._deny()
        if not mentor_invite.may_read(admin):
            return None, self._deny_role()
        return admin, None

    def _in_scope(self, request, admin):
        """`(the mentors this caller may see, error)`: its own organisation's (an organisation-less
        caller: none); a super every organisation's, narrowed by `?org=`."""
        from ..models import Mentor
        # M1a: a mentor whose login is ARCHIVED is on no list and out of reach by id (every door reads
        # this scope); the way back is the mentor invite (`mentor_archive.reinvite`).
        live = Mentor.objects.exclude(users__archived_at__isnull=False)
        if not self.has_role(admin, 'super'):
            org_id = admin.owning_organisation_id
            return (live.filter(organisation_id=org_id) if org_id
                    else Mentor.objects.none()), None
        org, err = self._org_narrowing(request, admin)
        if err:
            return None, err
        qs = live
        return (qs.filter(organisation=org) if org is not None else qs), None

    def _target(self, request, pk):
        """`(caller, mentor, login, error)` for an ACTION: super / org_admin (else 403), and a mentor
        this caller may manage (else 404)."""
        from .. import mentor_invite
        admin = self.get_admin(request)
        if not admin:
            return None, None, None, self._deny()
        if not mentor_invite.may_invite(admin):
            return None, None, None, self._deny_role()
        scope, err = self._in_scope(request, admin)
        if err:
            return None, None, None, err
        mentor = scope.select_related('organisation').filter(pk=pk).first()
        if not mentor_invite.manageable(admin, mentor):
            return None, None, None, _error('not_found', status.HTTP_404_NOT_FOUND)
        return admin, mentor, mentor_invite.login_of(mentor), None


class AdminMentorsView(_MentorsBase):
    """GET admin/mentors/ — `{mentors: [...], counts: {active, invited, inactive}, can_invite}`.
    super / org_admin / admin; org-fenced (see `_in_scope`). Each row carries `scholars_now` (S7b)."""

    def get(self, request):
        from .. import mentor_invite
        admin, err = self._reader(request)
        if err:
            return err
        scope, err = self._in_scope(request, admin)
        if err:
            return err
        # S7d: a mentor record with no login (a staff member who never mentored, then deleted) is
        # nobody's row any more: it is not listed.
        # T3: the Team -> Mentors table's own columns ride on the same rows (`team=True`).
        rows = mentor_rows(admin, list(scope.filter(users__isnull=False).select_related('organisation')
                                       .order_by('id')), team=True)
        rows.sort(key=lambda r: (r['name'] or '').lower())
        counts = {s: 0 for s in mentor_invite.STATUSES}
        for r in rows:
            counts[r['status']] += 1
        sees = self.sees_scholars(admin)
        if not sees:
            for r in rows:
                r['concerns_open'] = None   # T3 review: scholar data needs the Scholars list's read key
        return Response({'mentors': rows, 'counts': counts, 'sees_scholars': sees,
                         'can_invite': mentor_invite.may_invite(admin)})


class AdminMentorView(_MentorsBase):
    """GET admin/mentors/<id>/ — Team tables T3: the MENTOR DETAIL page (`mentor_detail.py`). The Mentors
    table's own readers (super, org_admin, admin — `_reader`; else 403), the organisation fence (`_in_scope`:
    another organisation's mentor 404), and only a mentor the table lists (one with a login; else 404).
    `{mentor: <the table's row>, mentoring_since, figures, current, past, programmes}` — never a meeting
    note. I4: `programmes` are the organisation's gifts the details box may tick (`mentor_gift.choices`).

    PATCH admin/mentors/<id>/ `{name?, email?}` — staff correct a name or an address UNTIL the
    first sign-in. 200 the row; 400 `bad_email` / `name_required` / `not_active` / `bad_request`;
    404; 409 `managed_by_mentor` (signed in: the mentor's details are theirs) or `already_staff`;
    500 `not_configured`; 502 `create_failed` / `retire_failed`. A new address is a new sign-in and
    is sent the invitation (`mentor_invite.edit`)."""

    def get(self, request, pk):
        from .. import mentor_detail, mentor_gift
        admin, err = self._reader(request)
        if err:
            return err
        scope, err = self._in_scope(request, admin)
        if err:
            return err
        mentor = scope.filter(pk=pk, users__isnull=False).select_related('organisation').first()
        if mentor is None:
            return _error('not_found', status.HTTP_404_NOT_FOUND)
        row = mentor_rows(admin, [mentor], team=True)[0]
        # Sprint T3: the ONE person page's header and Profile tab (`staff_person`, the admin and reviewer
        # details' own block), and — for a mentor's own login (D8) — the tables this viewer could add
        # them to (`staff_tables_admin.addable_tables`, the Add sheet's own rule). ONE query: the login
        # with its profile and mentor.
        from .. import staff_person, staff_tables_admin
        login = (PartnerAdmin.objects.select_related('reviewer_profile', 'mentor')
                 .filter(mentor=mentor).order_by('id').first())
        # T3 review fix 1: the profile's background fields only for a viewer who could open this person by
        # the admin or reviewer route under those routes' fences (`staff_person.opens_elsewhere`).
        extra = {'person': staff_person.person(login, full=staff_person.opens_elsewhere(admin, login)),
                 'may_add': staff_tables_admin.addable_tables(admin, login) if login.is_mentor else [],
                 'programmes': mentor_gift.choices(mentor.organisation_id)}   # I4
        if not self.sees_scholars(admin):
            # T3 review: the mentor's own row only — no scholar, figure or concern (`sees_scholars`).
            row['concerns_open'] = None
            return Response({'mentor': row, 'mentoring_since': _iso(mentor.created_at),
                             'sees_scholars': False, 'figures': None, 'current': [], 'past': [], **extra})
        figures, current, past = mentor_detail.scholars_of(mentor)
        return Response({'mentor': row, 'mentoring_since': _iso(mentor.created_at), 'sees_scholars': True,
                         'figures': figures, 'current': current, 'past': past, **extra})

    def delete(self, request, pk):
        """DELETE admin/mentors/<id>/ — Sprint T2 (D6): a pure mentor with NO work (`mentor_invite.
        delete_mentor`). super / org_admin of the mentor's own organisation (else 403 / 404). 200
        `{message, login}`; 400 `staff_mentor`; 409 `has_work` with `work`; 502 `login_cleanup_failed`;
        503 `delete_failed` (nothing removed)."""
        from django.db import DatabaseError
        from .. import mentor_invite
        admin, mentor, login, err = self._target(request, pk)
        if err:
            return err
        from apps.courses.staff_archive import archive_asked
        from .. import mentor_archive
        try:   # M1a: `{"archive": true}` archives a mentor with records (`mentor_archive`); else today's
            refusal, detail = ((archive_asked(request.data) and mentor_archive.archive(admin, mentor, login))
                               or mentor_invite.delete_mentor(admin, mentor, login))
        except DatabaseError:
            logger.exception('mentor delete of %s failed in the database; nothing was removed', pk)
            return _error('delete_failed', status.HTTP_503_SERVICE_UNAVAILABLE,
                          'Could not delete them just now. Nothing was removed; try again.')
        if refusal == 'staff_mentor':
            return _error(refusal, status.HTTP_400_BAD_REQUEST)
        if refusal == 'not_found':
            return _error(refusal, status.HTTP_404_NOT_FOUND)
        if refusal == 'archived':
            return Response({'message': 'Mentor archived. Their name stays on past records.', 'archived': True,
                             'login': detail})
        if refusal == 'has_unfinished_work':
            return Response({'error': 'This mentor still has scholars. Move them to another mentor first.',
                             'code': refusal, 'work': detail}, status=status.HTTP_409_CONFLICT)
        if refusal == 'has_work':
            return Response({'error': 'This mentor has work on record and can only be deactivated.',
                             'code': 'has_work', 'work': detail}, status=status.HTTP_409_CONFLICT)
        if refusal:
            return _error(refusal, status.HTTP_502_BAD_GATEWAY,
                          'Could not check their sign-in. Nothing was deleted; try again.')
        if detail == 'failed':
            return Response({'message': 'Mentor deleted, but their sign-in could not be removed — tell '
                             'support.', 'login': detail})
        return Response({'message': 'Mentor deleted.', 'login': detail})

    def patch(self, request, pk):
        from .. import mentor_invite
        admin, mentor, login, err = self._target(request, pk)
        if err:
            return err
        if login is not None and login.is_staff_mentor:   # S7d: their details are their staff account's
            return _error('staff_mentor', status.HTTP_400_BAD_REQUEST)
        data = request.data if isinstance(request.data, dict) else None
        if data is None or set(data) - {'name', 'email'}:
            return _error('bad_request', status.HTTP_400_BAD_REQUEST)
        name, email, bad = _name_and_email(data, required=False)
        if bad:
            return bad
        changed, emailed, refusal = mentor_invite.edit(admin, mentor, login, name=name, email=email)
        if refusal in ('managed_by_mentor', 'already_staff'):
            return _error(refusal, status.HTTP_409_CONFLICT,
                          ALREADY_STAFF if refusal == 'already_staff' else
                          'This mentor has signed in, so their details are their own now.')
        if refusal == 'not_active':
            return _error('not_active', status.HTTP_400_BAD_REQUEST)
        if refusal == 'not_configured':
            return _error('not_configured', status.HTTP_500_INTERNAL_SERVER_ERROR)
        if refusal:
            return _error(refusal, status.HTTP_502_BAD_GATEWAY)
        if changed:
            logger.info('AUDIT mentor_edited mentor=%s account=%s new_address=%s by=%s',
                        mentor.pk, login.pk, email is not None, admin.email or '')
        login.refresh_from_db()
        return Response({**mentor_rows(admin, [mentor])[0], 'emailed': emailed})


class AdminMentorActionView(_MentorsBase):
    """POST admin/mentors/<id>/<action>/ — `resend` (invited only: 400 `already_joined` /
    `not_active`), `revoke` (invited only: withdraws the invitation, switches the login off, kills
    the emailed password, stamps the mentor inactive), `deactivate` (any not-inactive mentor; never a
    delete; 409 `has_scholars` with `scholars_now` while they mentor anybody — owner O18, TD-606, the
    staff Revoke's body) and `reactivate` (inactive only: 400 `active`; a never-signed-in mentor is sent the
    invitation again). 200 the row + `emailed`; 404 an unknown action or another organisation's
    mentor; 500 `not_configured`; 502 `reset_failed` / `send_failed`."""
    ACTIONS = ('resend', 'revoke', 'deactivate', 'reactivate', 'stop', 'resume', 'remove')   # M1a: + remove
    STAFF_ACTIONS = ('stop', 'resume')   # S7d: the only two that act on a staff mentor

    def post(self, request, pk, action):
        from .. import mentor_invite
        if action not in self.ACTIONS:
            return _error('not_found', status.HTTP_404_NOT_FOUND)
        admin, mentor, login, err = self._target(request, pk)
        if err:
            return err
        staff = login is not None and login.is_staff_mentor
        if staff != (action in self.STAFF_ACTIONS):
            return _error('staff_mentor' if staff else 'not_staff', status.HTTP_400_BAD_REQUEST)
        if staff:
            return self._staff_action(admin, mentor, login, action)
        if action == 'remove':
            return self._remove_login(request, admin, mentor, login)
        emailed = None
        if action == 'resend':
            emailed, refusal = mentor_invite.resend_invite(admin, mentor, login)
        elif action == 'reactivate':
            _, emailed, refusal = mentor_invite.reactivate(admin, mentor, login)
        elif action == 'revoke':
            _, refusal = mentor_invite.revoke_invite(admin, mentor, login)
        else:
            n, refusal = mentor_invite.deactivate(admin, mentor, login)
            if refusal == 'has_scholars':                 # O18: nothing ended, nothing switched off
                return _has_scholars(login, n)
        if refusal in ('already_joined', 'not_active', 'active', 'no_login', 'not_arrived',
                       'staff_mentor'):   # M1b review: made staff after the read above
            return _error(refusal, status.HTTP_400_BAD_REQUEST)
        if refusal == 'not_configured':
            return _error('not_configured', status.HTTP_500_INTERNAL_SERVER_ERROR,
                          'Supabase service role key not configured')
        if refusal:
            return _error('reset_failed', status.HTTP_502_BAD_GATEWAY, 'Failed to reset the password')
        logger.info('AUDIT mentor_%s mentor=%s account=%s emailed=%s by=%s', action, mentor.pk,
                    login.pk if login else '-', emailed, admin.email or '')
        row = mentor_rows(admin, [mentor])[0]
        if action == 'resend' and not emailed:
            return Response({**row, 'emailed': False, 'error': 'Failed to send the email',
                             'code': 'send_failed'}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({**row, 'emailed': emailed})

    def _staff_action(self, admin, mentor, login, action):
        """S7d: "Stop mentoring" / "Mentor again" for a staff member — no email, their login untouched.
        400 `not_active` (already stopped), `active` (not stopped), `not_eligible` (Mentor again for a
        revoked login or a role that may not mentor)."""
        from .. import staff_mentor
        if action == 'stop':
            ended, refusal = staff_mentor.stop(admin, mentor, login)
        else:
            ended, refusal = 0, staff_mentor.resume(admin, mentor, login)
        if refusal == staff_mentor.HAS_SCHOLARS:      # M1a (owner O5): nothing ended
            return _has_scholars(login, ended)
        if refusal:
            return _error(refusal, status.HTTP_400_BAD_REQUEST)
        return Response({**mentor_rows(admin, [mentor])[0], 'emailed': None, 'ended': ended})

    def _remove_login(self, request, admin, mentor, login):
        """M1a: Remove a MENTOR LOGIN from Mentors, its only group — so only with ``{to_no_group: true}``
        (400 `last_table` without it), and it stays on as "No group" (`staff_mentor.remove_mentor_login`)."""
        from .. import staff_mentor
        body = request.data if isinstance(request.data, dict) else {}
        if body.get('to_no_group') is not True:
            return _error('last_table', status.HTTP_400_BAD_REQUEST)
        n, refusal = staff_mentor.remove_mentor_login(admin, mentor, login)
        if refusal == staff_mentor.HAS_SCHOLARS:
            return _has_scholars(login, n)
        if refusal:
            return _error(refusal, status.HTTP_400_BAD_REQUEST)
        return Response({**mentor_rows(admin, [mentor])[0], 'emailed': None, 'becomes_member': True})


def _has_scholars(login, n):
    from .. import staff_mentor
    # M1b review: a Mentor has no name of its own (`mentoring.mentor_name` reads this same login), so a
    # missing login or a blank name reads "This mentor", never a sentence that starts with a space.
    name = (login.name if login is not None else '') or 'This mentor'
    return Response(staff_mentor.has_scholars_body(name, n), status=status.HTTP_409_CONFLICT)


class AdminStaffMentorsView(_MentorsBase):
    """S7d — "Add a staff member as mentor" (super / org_admin; an organisation admin within its OWN
    organisation, a super any, narrowed by `?org=`). No email is sent.

    GET admin/mentors/staff/ → `{staff: [{id, name, email, role, organisation}]}`: the eligible staff
    (`staff_mentor.candidates` — org_admin, admin, reviewer, qc; active; not a mentor yet).
    POST admin/mentors/staff/ `{admin_id}` → 201 the new Mentors row. Refusals: 403 another role;
    400 `bad_request`; 404 not a staff member this caller may see (another organisation's, unknown —
    one answer); 400 `not_eligible` (finance, a super, a source, a mentor login, a revoked row);
    409 `already_mentor`."""

    def _actor(self, request):
        from .. import mentor_invite
        admin = self.get_admin(request)
        if not admin:
            return None, None, self._deny()
        if not mentor_invite.may_invite(admin):
            return None, None, self._deny_role()
        if not admin.is_super:
            org_id = admin.owning_organisation_id
            return admin, ([org_id] if org_id else []), None
        org, err = self._org_narrowing(request, admin)
        if err:
            return None, None, err
        return admin, ([org.pk] if org is not None else None), None

    def get(self, request):
        from .. import staff_mentor
        admin, orgs, err = self._actor(request)
        if err:
            return err
        return Response({'staff': [
            {'id': a.pk, 'name': a.name, 'email': a.email, 'role': a.role,
             'organisation': a.owning_organisation.name if a.owning_organisation_id else ''}
            for a in staff_mentor.candidates(orgs)]})

    def post(self, request):
        from .. import staff_mentor
        admin, orgs, err = self._actor(request)
        if err:
            return err
        data = request.data if isinstance(request.data, dict) else {}
        target_id = data.get('admin_id')
        if isinstance(target_id, bool) or not isinstance(target_id, int):
            return _error('bad_request', status.HTTP_400_BAD_REQUEST)
        # org-fence: only a staff member of the caller's own organisation (a super: any, or `?org=`).
        qs = PartnerAdmin.objects.filter(pk=target_id, owning_organisation__isnull=False, archived_at__isnull=True)
        if orgs is not None:
            qs = qs.filter(owning_organisation_id__in=orgs)
        target = qs.first()
        if target is None:
            return _error('not_found', status.HTTP_404_NOT_FOUND)
        # M1a: a "No group" member joins Mentors as a mentor login (`add_member`).
        mentor, refusal = (staff_mentor.add_member if target.is_member else staff_mentor.add)(admin, target)
        if refusal == 'already_mentor':
            return _error(refusal, status.HTTP_409_CONFLICT)
        if refusal:
            return _error(refusal, status.HTTP_400_BAD_REQUEST)
        return Response({**mentor_rows(admin, [mentor])[0]}, status=status.HTTP_201_CREATED)
