"""Source users — inviting a source's person, listing them, Resend and Revoke (source sign-in S2).

Roadmap: `docs/plans/2026-10-30-source-sign-in-roadmap.md`. The rules are in
`apps/scholarship/source_invite.py`; this module is only the HTTP shapes:

- `invite_source` — `POST admin/invitations/` with `audience='source_partner'`, routed here by
  `AdminInvitationsView.post` (the page's Source tab is invitation-first, and that POST already
  takes `audience='sponsor'`);
- `source_kind_extras` — what `GET admin/invitations/?kind=source` adds: the roster of source users
  and the sources the form may pick;
- `AdminSourceUserResendView` / `AdminSourceUserRevokeView` — `POST admin/source-users/<id>/resend/`
  and `.../revoke/`. NEW endpoints rather than the staff ones (`admin/admins/<id>/…`): those are
  fenced by `_staff_target_manageable`, which refuses every source user since S1 on purpose, and
  a second check inside them would be a second place for the staff rules to drift. Cancel of a
  WAITING invitation is the existing `admin/invitations/<id>/cancel/`, which takes a source one.

⚠ WHO: a super (any organisation's source) or an organisation admin (its OWN organisation's
sources). Admin, finance, reviewer, QC: 403. Another organisation's source or source user: 404.
"""
import logging

from rest_framework import status
from rest_framework.response import Response

from apps.courses.models import PartnerAdmin

from .base import _AdminBase
from .sources import _SourcesBase, _one_source_dict, new_source_fields, new_source_refusal

# ⚠ THE PACKAGE'S name, never `__name__` — an audit line must stay on the scrape metric (H11).
logger = logging.getLogger('apps.scholarship.views_admin')

#: 409 for an address that already has a staff or source row (roadmap C7). One sentence for every
#: case — a colleague, a referral partner, another source's user, another organisation's — so it
#: confirms nothing about the other account.
ALREADY_STAFF = ("This email address already has a HalaTuju staff or source sign-in, so it can't "
                 "be invited for a source. Ask HalaTuju support.")


def _error(code, http, message=None):
    return Response({'error': message or code, 'code': code}, status=http)


def _bad_email(email):
    return '@' not in email or '.' not in email.rsplit('@', 1)[-1]


def invite_source(request, admin):
    """`POST admin/invitations/` `{audience: 'source_partner', name, email, source_id}` — or, for a
    NEW source, `{…, source_name, source_code, contact_person?, contact_email?, phone?,
    show_in_apply?}` (a super names the organisation with `?org=<code>`, as Sources did).

    201 `{id, admin_id, emailed, google, already_registered, reactivated, message, source}` —
    `source` is the Sources row (with `sign_in` / `user_count`). Refusals: 403 not super /
    org_admin; 400 `bad_email`, `name_required`, `source_inactive`, `code_and_name_required`,
    `code_reserved`, `code_taken`, `organisation_required`; 404 `not_found` (a source outside the
    caller's organisation); 409 `already_staff`; 500 `not_configured`; 502 `create_failed`.
    `source_id` wins when both shapes are sent.
    """
    from .. import source_invite
    if not source_invite.may_invite(admin):
        return Response({'error': 'Your admin role cannot perform this action.'},
                        status=status.HTTP_403_FORBIDDEN)
    data = request.data
    email = (data.get('email') or '').strip().lower()
    name = (data.get('name') or '').strip()[:200]
    if _bad_email(email):
        return _error('bad_email', status.HTTP_400_BAD_REQUEST)
    if not name:
        return _error('name_required', status.HTTP_400_BAD_REQUEST)

    sources = _SourcesBase()
    source = make_source = None
    if data.get('source_id') not in (None, ''):
        scope, err = sources._sources_in_scope(request, admin)
        if err:
            return err
        # Another organisation's source is a 404, never a 403 — it must not confirm it exists.
        source = scope.select_related('organisation').filter(pk=_int(data.get('source_id'))).first()
        if source is None:
            return _error('not_found', status.HTTP_404_NOT_FOUND)
        if not source.is_active:
            return _error('source_inactive', status.HTTP_400_BAD_REQUEST,
                          'This source is switched off. Switch it on in Sources first.')
    else:
        owner, err = sources._new_source_owner(request, admin)
        if err:
            return err
        fields = new_source_fields(data, code_key='source_code', name_key='source_name')
        refusal = new_source_refusal(owner, fields)
        if refusal:
            return _error(refusal, status.HTTP_400_BAD_REQUEST)

        def make_source():
            from ..models import ReferralSource
            # A new source joins NO gift (owner, 2026-10-08) — each gift switches it on itself.
            return ReferralSource.objects.create(organisation=owner, **fields)

    # As the staff invite: nothing is written while the login side cannot be reached.
    from apps.courses import supabase_admin
    if supabase_admin.supabase_config() is None:
        return _error('not_configured', status.HTTP_500_INTERNAL_SERVER_ERROR,
                      'Supabase service role key not configured')
    done = source_invite.invite(admin, email=email, name=name, source=source,
                                make_source=make_source)
    if done.error == 'already_staff':
        return _error('already_staff', status.HTTP_409_CONFLICT, ALREADY_STAFF)
    if done.error == 'code_taken':
        return _error('code_taken', status.HTTP_400_BAD_REQUEST)
    if done.error:
        return _error('create_failed', status.HTTP_502_BAD_GATEWAY,
                      'Could not create their sign-in just now. Nothing was saved; try again.')
    logger.info('AUDIT source_invited source=%s account=%s reactivated=%s by=%s',
                done.source.pk, done.account.pk, done.reactivated, admin.email or '')
    return Response({
        'id': done.invitation.id,
        'admin_id': done.account.id,
        'emailed': done.emailed,
        'google': done.google,
        'already_registered': done.already_registered,
        'reactivated': done.reactivated,
        'message': _invite_message(done, name, email),
        'source': _one_source_dict(admin, done.source),
    }, status=status.HTTP_201_CREATED)


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _invite_message(done, name, email):
    if not done.emailed:
        return f'{name} was added, but the email could not be sent. Use Resend to try again.'
    if done.reactivated:
        return f'{name} can sign in for {done.source.name} again. They sign in as they always did.'
    if done.google:
        return f'{name} added for {done.source.name} — they sign in with Google ({email}).'
    if done.already_registered:
        return (f'{name} already has an account — access granted for {done.source.name}. They can '
                f'sign in as they always do.')
    return f'{name} invited for {done.source.name}. Sign-in details emailed to {email}.'


def _iso(value):
    return value.isoformat() if value else None


def source_kind_extras(admin, org_id):
    """What `GET admin/invitations/?kind=source` adds to the shared payload.

    - `source_users` — EVERY source user of the caller's organisation (a super: every
      organisation's), signed in or not, switched off or not: the Source tab's roster, with the
      newest invitation's status, and `manageable` (may this caller Resend / Revoke — computed by
      the same `source_invite.manageable` the endpoints enforce, so the screen cannot offer a
      button the server refuses). Admin and finance may read the tab, and act on nothing.
    - `sources` — the ACTIVE sources the invite form may pick, with their sign-in state.

    Fenced like the invitations: `org_id` is the caller's organisation, None for a super.
    """
    from apps.courses.views_admin import _invitation_dict
    from .. import source_invite
    from ..models import Invitation, ReferralSource
    users = (PartnerAdmin.objects.filter(role=PartnerAdmin.SOURCE_ROLE)
             .select_related('source', 'owning_organisation').order_by('source__name', 'name'))
    sources = ReferralSource.objects.filter(is_active=True).select_related('organisation')
    if org_id is not None:
        users = users.filter(owning_organisation_id=org_id)
        sources = sources.owned_by(org_id)
    users = list(users)
    newest = {}
    for inv in (Invitation.objects.filter(audience=source_invite.AUDIENCE, partner_admin__in=users)
                .order_by('partner_admin_id', '-created_at')):
        newest.setdefault(inv.partner_admin_id, inv)
    signed = source_invite.sign_in_states(sources.values('pk'))
    return {
        'source_users': [{
            'id': u.id,
            'name': u.name,
            'email': u.email,
            'source_id': u.source_id,
            'source_name': u.source.name,
            'source_code': u.source.code,
            'organisation': u.owning_organisation.code if u.owning_organisation_id else None,
            'is_active': u.is_active,
            # NULL is "not signed in yet" for a source user: every one was created after
            # `first_seen_at` existed, so unlike staff it is never "not recorded".
            'first_seen_at': _iso(u.first_seen_at),
            'last_seen_at': _iso(u.last_seen_at),
            'manageable': source_invite.manageable(admin, u),
            'invitation': _invitation_dict(newest.get(u.id)),
        } for u in users],
        'sources': [{
            'id': s.id, 'code': s.code, 'name': s.name, 'organisation': s.organisation.code,
            'sign_in': signed.get(s.id, ('none', 0))[0],
            'user_count': signed.get(s.id, ('none', 0))[1],
        } for s in sources.order_by('name', 'pk')],
    }


class _SourceUserBase(_AdminBase):
    """The gate both source-user endpoints share: super or org_admin (else 403), and a source user
    this caller may manage (else 404 — another organisation's id must confirm nothing)."""

    def _target(self, request, pk):
        from .. import source_invite
        admin = self.get_admin(request)
        if not admin:
            return None, None, self._deny()
        if not source_invite.may_invite(admin):
            return None, None, self._deny_role()
        target = (PartnerAdmin.objects.select_related('source', 'source__organisation')
                  .filter(pk=pk, role=PartnerAdmin.SOURCE_ROLE).first())
        if not source_invite.manageable(admin, target):
            return None, None, _error('not_found', status.HTTP_404_NOT_FOUND)
        return admin, target, None


class AdminSourceUserResendView(_SourceUserBase):
    """POST admin/source-users/<id>/resend/ — re-send a WAITING source user's invitation: a fresh
    temporary password (and TTL clock) where we issued one, else the "sign in as you always do"
    note. 200 `{message, emailed: true}`; 400 `not_active` / `already_joined`; 404; 500 when
    Supabase is not configured; 502 when the password could not be reset or the email failed."""

    def post(self, request, pk):
        from .. import source_invite
        admin, target, err = self._target(request, pk)
        if err:
            return err
        emailed, refusal = source_invite.resend(admin, target)
        if refusal == 'not_active':
            return _error('not_active', status.HTTP_400_BAD_REQUEST,
                          f'{target.name} is switched off. Invite them again instead.')
        if refusal == 'already_joined':
            return _error('already_joined', status.HTTP_400_BAD_REQUEST,
                          f'{target.name} has already signed in.')
        if refusal == 'not_configured':
            return _error('not_configured', status.HTTP_500_INTERNAL_SERVER_ERROR,
                          'Supabase service role key not configured')
        if refusal:
            return _error('reset_failed', status.HTTP_502_BAD_GATEWAY, 'Failed to reset the password')
        if not emailed:
            return Response({'error': 'Failed to send the email', 'code': 'send_failed',
                             'emailed': False}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({'message': f'Sign-in details re-sent to {target.email}.', 'emailed': True})


class AdminSourceUserRevokeView(_SourceUserBase):
    """POST admin/source-users/<id>/revoke/ — switch a source user off (an invitation still waiting
    is withdrawn with it). 200 `{id, is_active: false, message}`; 400 `not_active`; 404. The way
    back is to invite the same address again for the same source (`source_invite.invite`)."""

    def post(self, request, pk):
        from .. import source_invite
        admin, target, err = self._target(request, pk)
        if err:
            return err
        done, refusal = source_invite.revoke(target)
        if not done:
            return _error(refusal, status.HTTP_400_BAD_REQUEST, f'{target.name} is already switched off.')
        logger.info('AUDIT source_user_revoked account=%s source=%s by=%s',
                    target.pk, target.source_id, admin.email or '')
        return Response({'id': target.id, 'is_active': False,
                         'message': f'{target.name} can no longer sign in for {target.source.name}.'})
