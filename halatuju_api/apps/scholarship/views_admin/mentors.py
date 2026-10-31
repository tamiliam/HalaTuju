"""Mentors — the Mentors page's list, the mentor invite, and the staff actions (student maintenance
Sprint 7a, 2026-10-31). The rules are in `apps/scholarship/mentor_invite.py`; this module is only the
HTTP shapes:

- `invite_mentor` — `POST admin/invitations/` with `audience='mentor'` `{name, email}`, routed here by
  `AdminInvitationsView.post` (the source invite's door; a super names the organisation with `?org=`);
- `AdminMentorsView` — `GET admin/mentors/`: every mentor of the caller's organisation (a super:
  every organisation's, narrowed by `?org=`), with the status counts;
- `AdminMentorView` — `PATCH admin/mentors/<id>/` `{name?, email?}`: staff correct a name or an
  address until the first sign-in (409 `managed_by_mentor` after it);
- `AdminMentorActionView` — `POST admin/mentors/<id>/<resend|revoke|deactivate|reactivate>/`.

⚠ WHO: reading — super, org_admin, admin (read-only); acting — super, org_admin. Anyone else 403;
another organisation's mentor 404, never 403. ⚠ MENTORS NEVER REACH SPONSORS OR PARTNERS: nothing
here is on a sponsor, partner or source surface. Each action writes an AUDIT line and, for the
invitation doors, the `Invitation` record — the source pattern's trail.
"""
import logging

from rest_framework import status
from rest_framework.response import Response

from apps.courses.models import PartnerAdmin

from .base import _AdminBase
from .source_users import _error, _iso
from .sources import _SourcesBase, text_of

# ⚠ THE PACKAGE'S name, never `__name__` — an audit line must stay on the scrape metric (H11).
logger = logging.getLogger('apps.scholarship.views_admin')

#: 409 for an address that already has any sign-in here. One sentence for every case, so it confirms
#: nothing about the other account.
ALREADY_STAFF = ("This email address already has a HalaTuju sign-in, so it can't be invited as a "
                 "mentor. Ask HalaTuju support.")

_FLUENT = ('conversational', 'fluent')


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
    """`POST admin/invitations/` `{audience: 'mentor', name, email}` → 201 `{id, mentor, emailed,
    google, already_registered, message}`. Refusals: 403 not super / org_admin; 400 `bad_email`,
    `name_required`, `organisation_required`; 404 an `?org=` outside the fence; 409 `already_staff`;
    500 `not_configured`; 502 `create_failed`."""
    from .. import mentor_invite
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
    from apps.courses import supabase_admin
    if supabase_admin.supabase_config() is None:
        return _error('not_configured', status.HTTP_500_INTERNAL_SERVER_ERROR,
                      'Supabase service role key not configured')
    done = mentor_invite.invite(admin, organisation=owner, email=email, name=name)
    if done.error == 'already_staff':
        return _error('already_staff', status.HTTP_409_CONFLICT, ALREADY_STAFF)
    if done.error:
        return _error('create_failed', status.HTTP_502_BAD_GATEWAY,
                      'Could not create their sign-in just now. Nothing was saved; try again.')
    logger.info('AUDIT mentor_invited mentor=%s account=%s org=%s by=%s',
                done.mentor.pk, done.account.pk, owner.pk, admin.email or '')
    row = mentor_rows(admin, [done.mentor])[0]
    return Response({
        'id': done.invitation.id, 'mentor': row, 'emailed': done.emailed, 'google': done.google,
        'already_registered': done.already_registered,
        'message': (f'{name} invited. Sign-in details emailed to {email}.' if done.emailed
                    else f'{name} was added, but the email could not be sent. Use Resend to try again.'),
    }, status=status.HTTP_201_CREATED)


def mentor_rows(caller, mentors):
    """The Mentors page's rows for ``mentors`` — ONE query each for the logins, their profiles and
    their invitations, whatever the page size. An ALLOWLIST: name, email, the mentor's own phone (the
    profile tells them the inviting organisation sees it), status, area, languages, invited / signed-in
    times, and `manageable` (the endpoints' own rule, so the screen never offers a refused button)."""
    from .. import mentor_invite
    from ..models import Invitation, ReviewerProfile
    logins = {a.mentor_id: a for a in PartnerAdmin.objects.filter(mentor__in=mentors)}
    profiles = {p.partner_admin_id: p for p in ReviewerProfile.objects.filter(
        partner_admin__in=list(logins.values()))}
    newest = {}
    for inv in (Invitation.objects.filter(audience=mentor_invite.AUDIENCE, mentor__in=mentors)
                .order_by('mentor_id', '-created_at')):
        newest.setdefault(inv.mentor_id, inv)
    rows = []
    for m in mentors:
        login = logins.get(m.pk)
        rp = profiles.get(login.pk) if login else None
        inv = newest.get(m.pk)
        rows.append({
            'id': m.pk,
            'name': login.name if login else '',
            'email': login.email if login else '',
            'phone': (rp.phone or '') if rp else '',
            'status': mentor_invite.status_of(m, login),
            'area': m.area,
            'languages': {'en': getattr(rp, 'english_fluency', '') or '',
                          'ms': getattr(rp, 'bm_fluency', '') or '',
                          'ta': getattr(rp, 'tamil_fluency', '') or ''},
            # Only when spoken conversationally or better (`ReviewerProfile.spoken_other_language`).
            'other_language': rp.spoken_other_language() if rp else '',
            'invited_at': _iso((inv.last_sent_at or inv.created_at) if inv else m.created_at),
            'signed_in': bool(login and login.first_seen_at),
            'last_seen_at': _iso(login.last_seen_at) if login else None,
            'deactivated_at': _iso(m.deactivated_at),
            'manageable': mentor_invite.manageable(caller, m),
        })
    return rows


class _MentorsBase(_AdminBase):
    """The fence every Mentors endpoint shares."""

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
        if not self.has_role(admin, 'super'):
            org_id = admin.owning_organisation_id
            return (Mentor.objects.filter(organisation_id=org_id) if org_id
                    else Mentor.objects.none()), None
        org, err = self._org_narrowing(request, admin)
        if err:
            return None, err
        qs = Mentor.objects.all()
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
    super / org_admin / admin; org-fenced (see `_in_scope`). Never a "Scholars now" column (S7b)."""

    def get(self, request):
        from .. import mentor_invite
        admin, err = self._reader(request)
        if err:
            return err
        scope, err = self._in_scope(request, admin)
        if err:
            return err
        rows = mentor_rows(admin, list(scope.select_related('organisation').order_by('id')))
        rows.sort(key=lambda r: (r['name'] or '').lower())
        counts = {s: 0 for s in mentor_invite.STATUSES}
        for r in rows:
            counts[r['status']] += 1
        return Response({'mentors': rows, 'counts': counts,
                         'can_invite': mentor_invite.may_invite(admin)})


class AdminMentorView(_MentorsBase):
    """PATCH admin/mentors/<id>/ `{name?, email?}` — staff correct a name or an address UNTIL the
    first sign-in. 200 the row; 400 `bad_email` / `name_required` / `not_active` / `bad_request`;
    404; 409 `managed_by_mentor` (signed in: the mentor's details are theirs) or `already_staff`;
    500 `not_configured`; 502 `create_failed` / `retire_failed`. A new address is a new sign-in and
    is sent the invitation (`mentor_invite.edit`)."""

    def patch(self, request, pk):
        from .. import mentor_invite
        admin, mentor, login, err = self._target(request, pk)
        if err:
            return err
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
    delete) and `reactivate` (inactive only: 400 `active`; a never-signed-in mentor is sent the
    invitation again). 200 the row + `emailed`; 404 an unknown action or another organisation's
    mentor; 500 `not_configured`; 502 `reset_failed` / `send_failed`."""
    ACTIONS = ('resend', 'revoke', 'deactivate', 'reactivate')

    def post(self, request, pk, action):
        from .. import mentor_invite
        if action not in self.ACTIONS:
            return _error('not_found', status.HTTP_404_NOT_FOUND)
        admin, mentor, login, err = self._target(request, pk)
        if err:
            return err
        emailed = None
        if action == 'resend':
            emailed, refusal = mentor_invite.resend_invite(admin, mentor, login)
        elif action == 'reactivate':
            _, emailed, refusal = mentor_invite.reactivate(admin, mentor, login)
        elif action == 'revoke':
            _, refusal = mentor_invite.revoke_invite(admin, mentor, login)
        else:
            _, refusal = mentor_invite.deactivate(admin, mentor, login)
        if refusal in ('already_joined', 'not_active', 'active', 'no_login'):
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
