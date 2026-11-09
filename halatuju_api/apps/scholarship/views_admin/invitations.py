"""Staff invitations — inviting, listing and revoking an admin of any role.

Moved verbatim from the package root at code health H12. Part of the `views_admin`
package: every name below is re-exported from `views_admin/__init__.py`, so `urls.py`
and every importer are unchanged.
"""
import logging

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from apps.courses import staff_gift

from .reviewers import _ReviewersBase

# ⚠ THE PACKAGE'S name, never `__name__` — an audit line must stay on the scrape metric (H11).
logger = logging.getLogger('apps.scholarship.views_admin')


class AdminInvitationsView(_ReviewersBase):
    """GET admin/invitations/[?kind=][&all=1] — who has been asked and **has not answered yet**.

    The Invitations page (owner's shape, 2026-08-03) is organised into FIVE kinds — admins,
    reviewers, source, mentor (S7b follow-up), sponsors — with one table on screen at a time, so this
    serves one kind plus the waiting counts for all five (the badge on each button; without it an invitation waiting
    under an unselected kind is invisible, which is what the page exists to prevent).

    ⚠ **IT LISTS THE WAITING ONES ONLY (2026-09-09).** `invitations.open_only` is the single
    definition of waiting, shared with `waiting_counts`, so the table and its own badge can never
    disagree. Everybody who has already accepted belongs to the People directory, not here.
    `?all=1` returns the full history for a caller that genuinely wants it; nothing in the console
    passes it today.

    ⚠ **FENCED ON `Invitation.organisation`, NOT through `PartnerAdmin`.** A sponsor invitation has
    no staff row to fence through — that is the whole point of a sponsor invitation, which creates
    no account — so fencing through the invitee would silently drop the sponsor kind entirely.

    ⚠ **`org_admin` IS LISTED AND NOT INVITABLE.** See `invitations.KIND_ROLES` vs
    `KIND_INVITABLE_ROLES`: an organisation admin is an admin and belongs in the table, but
    appointing one is a platform act a super performs, never something an org_admin does here.
    """

    def get(self, request):
        admin, org_id, err = self._side(request)
        if err:
            return err
        from .. import invitations as inv_service
        from ..models import Invitation

        # org-fence: an invitation belongs to the organisation that sent it. A super sees all.
        qs = Invitation.objects.select_related(
            'partner_admin', 'invited_by', 'programme', 'referral_source').all()
        from .. import sponsor_invite_gifts
        if org_id is not None:
            qs = qs.filter(organisation_id=org_id)

        counts = inv_service.waiting_counts(qs)
        totals = inv_service.kind_totals(qs)
        kind = (request.GET.get('kind') or inv_service.KIND_ADMINS).strip()
        if kind not in inv_service.KINDS:
            kind = inv_service.KIND_ADMINS
        # S7b follow-up review fix 1: this screen admits finance (`may_read_team`), the Mentors
        # roster does not (`mentor_invite.may_read`). A caller outside it gets NOTHING of the Mentor
        # kind — no rows, no mentor rows, a count of 0 — so a mentor's name never reaches finance.
        from .. import mentor_invite
        reads_mentors = mentor_invite.may_read(admin)
        if not reads_mentors:
            counts[inv_service.KIND_MENTOR] = 0
            totals[inv_service.KIND_MENTOR] = 0

        # ⚠ WAITING-ONLY IS THE DEFAULT, AND THAT IS THE POINT OF THIS PAGE (2026-09-09).
        # It used to list every invitation ever sent, which on this tenant meant 18 accepted rows
        # and 2 waiting ones — a page named "Invitations" that was really a staff roster, and one
        # that would have got WORSE on its own as each waiting sponsor registered. Who is already
        # in is answered by the People directory; this endpoint answers who has not replied.
        # `?all=1` keeps the full history reachable for a caller that genuinely wants it.
        listed = inv_service.for_kind(qs, kind) if (reads_mentors or kind != inv_service.KIND_MENTOR) \
            else qs.none()
        if (request.GET.get('all') or '').strip() not in ('1', 'true'):
            listed = inv_service.open_only(listed)

        rows = []
        for i in listed.order_by('-created_at').prefetch_related('gift_rows__programme'):
            pa = i.partner_admin
            gifts = sponsor_invite_gifts.row_payload(i)
            rows.append({
                'id': i.id,
                'name': i.name or (pa.name if pa else ''),
                'email': i.email,
                'role': i.role,
                'status': inv_service.status_of(i),
                'sent_at': i.last_sent_at.isoformat() if i.last_sent_at else None,
                'send_count': i.send_count,
                'last_send_ok': i.last_send_ok,
                'last_send_error': i.last_send_error,
                'accepted_at': i.accepted_at.isoformat() if i.accepted_at else None,
                # The staff row behind a staff invitation, so the Action column can offer the right
                # verb — Resend while waiting, Revoke once somebody is actually in. Absent for a
                # sponsor invitation, which has no account by design.
                'admin_id': pa.id if pa else None,
                'is_active': pa.is_active if pa else None,
                'paused': (pa.paused_at is not None) if pa else None,
                # Which gifts a sponsor invitation names (I3): `gifts` [{id, code, name}] and
                # `every_gift`. `programme` / `programme_name` stay for ONE gift (blank for
                # several, Every gift, none stated, and every staff invitation). Never render a
                # blank as a gift name.
                **gifts,
                'programme': gifts['gifts'][0]['code'] if len(gifts['gifts']) == 1 else '',
                'programme_name': gifts['gifts'][0]['name'] if len(gifts['gifts']) == 1 else '',
                # Which SOURCE a source invitation signs somebody in for (source sign-in S2). None
                # for every other kind.
                'source_id': i.referral_source_id,
                'source_name': i.referral_source.name if i.referral_source_id else None,
                'source_code': i.referral_source.code if i.referral_source_id else None,
                # Which MENTOR a mentor invitation signs somebody in as (S7b follow-up): the Mentor
                # tab's Resend / Revoke act on the mentor (`admin/mentors/<id>/<action>/`).
                'mentor_id': i.mentor_id,
            })

        extras = {}
        if kind == inv_service.KIND_SOURCE:
            # The Source tab's roster and the invite form's choices (source sign-in S2).
            from .source_users import source_kind_extras
            extras = source_kind_extras(admin, org_id)
        elif kind == inv_service.KIND_MENTOR and reads_mentors:
            # The Mentor tab's roster (S7b follow-up): the Mentors page's own rows for the waiting
            # invitations' mentors, so the tab offers exactly the actions those endpoints take.
            from .. import mentor_gift
            from .mentors import mentor_kind_extras
            extras = mentor_kind_extras(admin, [r['mentor_id'] for r in rows if r['mentor_id']])
            # I4: a mentor invitation's gifts ARE its mentor's (`mentor_gifts`, written at the invite; no
            # gifts = every gift), so the waiting row names them under the name, as a sponsor's does.
            held = mentor_gift.gifts_by_mentor([r['mentor_id'] for r in rows if r['mentor_id']])
            for r in rows:
                if r['mentor_id']:
                    named = held.get(r['mentor_id'], [])
                    r.update(gifts=named, every_gift=not named,
                             programme=named[0]['code'] if len(named) == 1 else '',
                             programme_name=named[0]['name'] if len(named) == 1 else '')
            # I4: the mentor invite's gift choices — the ACTIVE gifts of the organisation the invite binds
            # to (`invite_mentor`'s own owner rule), so a super is never offered a gift the POST 404s.
            from .sources import _SourcesBase
            owner, _err = _SourcesBase()._new_source_owner(request, admin)
            extras['mentor_programmes'] = [] if owner is None else [
                {'id': p.id, 'code': p.code, 'name': p.name_en or p.code}
                for p in owner.programmes.filter(is_active=True).order_by('code')]

        return Response({
            'kind': kind,
            'invitations': rows,
            'waiting': counts,
            # Every invitation ever sent, per kind. The page needs it to tell an empty table
            # apart: nobody asked yet, or everybody asked has arrived. See `kind_totals`.
            'totals': totals,
            # What this caller may actually grant here. The FE renders the sub-selection from it
            # rather than keeping its own copy, so the two cannot drift.
            'invitable_roles': list(inv_service.KIND_INVITABLE_ROLES.get(kind, ())),
            # T2: what an org admin may still CANCEL here (old finance / qc invitations included).
            'cancellable_roles': list(inv_service.KIND_CANCELLABLE_ROLES.get(kind, ())),
            # The gift choices for the sponsor invite form. ACTIVE only, matching exactly what
            # the POST accepts — an invitation is a prompt to register TODAY, so offering a gift
            # that is not open yet would invite somebody into a door that does not open. (The
            # accept panel on the sponsor detail page is the opposite case and takes inactive
            # ones, because a gift is staffed before it is switched on.)
            # I3 review: `nameable` — an admin with an organisation is offered only its gifts.
            'programmes': [
                {'id': p.id, 'code': p.code, 'name': p.name_en or p.code}
                for p in sponsor_invite_gifts.nameable(admin).order_by('code')
            ],
            # TD-501 (A1.3 review): the REVIEWER invite's gift choices — only the gifts of the
            # organisation the invite binds to, the same home `staff_gift.for_invite` checks, so
            # a super is no longer offered another organisation's gift that the POST then 404s.
            'reviewer_programmes': [
                {'id': p.id, 'code': p.code, 'name': p.name_en or p.code}
                for p in staff_gift.reviewer_gift_choices(admin)
            ],
            **extras,
        })

    def post(self, request):
        """Invite a SPONSOR — or, since source sign-in S2, a SOURCE's person
        (`audience='source_partner'`, `source_users.invite_source`, which provisions their account
        through the staff invite's own branches). Staff go through `AdminInviteView`; a sponsor
        invitation deliberately provisions nothing.

        ⚠ **AN INVITATION IS A PROMPT, NEVER A WAY ROUND THE FRONT DOOR.** Owner's constraint:
        *"invite, but nothing is skipped."* No `Sponsor` row is created, no account, no vetting
        shortcut — the email carries a link to the ordinary public registration, where they give
        consent, sign the terms and are vetted like anybody else. The invitation closes itself when
        a sponsor account appears for that address (`views_sponsor._attribute_referral`).

        ⚠ Staff invitations are NOT accepted here. They create Supabase accounts and carry
        passwords, and that logic already has one home; a second door into it would be a second
        place for the role rules to drift.
        """
        admin, org_id, err = self._side(request)
        if err:
            return err
        if not (admin.is_super or self.has_role(admin, 'org_admin')):
            return self._deny_role()

        from .. import invitations as inv_service
        audience = request.data.get('audience')
        audience = audience.strip() if isinstance(audience, str) else ''   # review L3: never a 500
        if audience == 'source_partner':
            from .source_users import invite_source
            return invite_source(request, admin)
        if audience == 'mentor':
            # Student maintenance S7a: a mentor's sign-in (`views_admin/mentors.py`).
            from .mentors import invite_mentor
            return invite_mentor(request, admin)
        if audience != 'sponsor':
            return Response({'error': 'unsupported_audience', 'code': 'unsupported_audience'},
                            status=status.HTTP_400_BAD_REQUEST)

        email = (request.data.get('email') or '').strip().lower()
        if '@' not in email or '.' not in email.rsplit('@', 1)[-1]:
            return Response({'error': 'bad_email', 'code': 'bad_email'},
                            status=status.HTTP_400_BAD_REQUEST)

        from apps.scholarship.models import Sponsor
        if Sponsor.objects.filter(email__iexact=email).exists():
            # Not an error worth a stack trace — they are already here. Say so plainly.
            return Response({'error': 'already_a_sponsor', 'code': 'already_a_sponsor'},
                            status=status.HTTP_400_BAD_REQUEST)

        org = admin.owning_organisation

        # ⚠ WHICH GIFTS ARE YOU INVITING THEM INTO? (S-ASSIGN 2026-09-04; several or Every gift
        # since Invitations I3, 2026-11-08.) `sponsor_invite_gifts.choose` is the one rule: the
        # gifts named, Every gift (`[]`), the old one-gift `programme_id`, or nothing — the sole
        # active gift, or 400 `programme_required` with several. A RESEND (nothing named, already
        # waiting) keeps what was asked: never re-homed. A gift outside the caller's reach is 404.
        # It GRANTS nothing either way: they still register, consent, sign the terms and are vetted.
        from .. import sponsor_invite_gifts
        choice, refusal = sponsor_invite_gifts.choose(admin, request.data, email)
        if refusal is not None:
            return refusal
        # A RESEND (`choice` None) keeps the row's organisation as well as its gifts: a super's
        # Resend on another organisation's row must not move it to theirs (I3 second review).
        with transaction.atomic():
            inv = inv_service.create_or_refresh(
                audience='sponsor', email=email, name=(request.data.get('name') or '').strip(),
                organisation=None if choice is None else org, invited_by=admin,
                ttl_days=inv_service.PII_RETENTION_DAYS)
            if choice is not None:
                sponsor_invite_gifts.set_gifts(inv, *choice)

        from ..emails import send_sponsor_invitation_email
        ok, error = send_sponsor_invitation_email(
            email, org_name=(inv.organisation.name if inv.organisation else ''), note=(request.data.get('note') or ''),
            code=inv.code, invited_by=admin.name)
        inv_service.record_send(inv, ok, error, actor=admin)
        return Response({'id': inv.id, 'emailed': ok},
                        status=status.HTTP_201_CREATED if ok else status.HTTP_502_BAD_GATEWAY)


class AdminInvitationCancelView(_ReviewersBase):
    """POST admin/invitations/<id>/cancel/ — withdraw an invitation nobody has answered (TD-214).

    ⚠ **A STATUS, NEVER A DELETE.** It sets `revoked_at` (the field `invitations.revoke` sets), so the row
    reads `revoked` for ever and the history of who was asked survives. (Who cancelled is on the
    AUDIT line; there is no `revoked_by` column, and adding one is a migration.) Only an OPEN invitation
    (`invitations.is_open`: not accepted, not already withdrawn) can be cancelled; anything else is
    `400 not_open`, and somebody who has arrived is revoked on Organisation → People instead.

    ⚠ **THE LINK STOPS WORKING.** A SPONSOR invitation carries no credential: once withdrawn it no
    longer closes on their registration (`views_sponsor._close_admin_invitation`) nor files them
    into its gifts (`sponsor_signup.signup_programmes_for`) — both skip withdrawn ones. A STAFF
    invitation provisioned an account with a temporary password up front, so withdrawing it also
    switches that never-used account off (`is_active=False`, exactly People → Revoke): otherwise
    the password in the letter would still open the console. Refused if they have signed in.
    Since 2026-10-09 the emailed password is also rotated dead at Supabase
    (`staff_lifecycle.kill_for_cancel`), and the address can be invited again (TD-335).

    Fenced like the list: an invitation of another organisation is 404, never 403. Only a super or
    an org_admin acts, and an org_admin only on what this page could have sent
    (`KIND_INVITABLE_ROLES`) — never an organisation-admin invitation, which a super appoints.
    A SOURCE invitation (source sign-in S2) is cancelled the same way — its never-used account
    switched off, its password killed — by a super or its own organisation's admin.
    Audited: the AUDIT line names who cancelled what.
    """

    def post(self, request, pk):
        admin, org_id, err = self._side(request)
        if err:
            return err
        if not (admin.is_super or self.has_role(admin, 'org_admin')):
            return self._deny_role()
        from .. import invitations as inv_service
        from ..models import Invitation

        # org-fence: an invitation belongs to the organisation that sent it. A super sees all.
        qs = Invitation.objects.select_related('partner_admin').filter(pk=pk)
        if org_id is not None:
            qs = qs.filter(organisation_id=org_id)
        inv = qs.first()
        invitable = {r for roles in inv_service.KIND_CANCELLABLE_ROLES.values() for r in roles}
        # ⚠ A SOURCE invitation provisioned an account too (source sign-in S2), so it is switched
        # off with the invitation exactly as a staff one is (`ACCOUNT_AUDIENCES`).
        account = (inv.partner_admin if inv is not None
                   and inv.audience in inv_service.ACCOUNT_AUDIENCES else None)
        # An org_admin acts only on what this page could have sent — judged on the invitation's
        # role AND the account's role NOW (a never-signed-in invitee a super has since promoted to
        # org_admin is not theirs to switch off; review fix 2026-10-05).
        if inv is None or (not admin.is_super and inv.audience == 'staff' and (
                inv.role not in invitable or (account is not None and account.role not in invitable))):
            return Response({'error': 'not_found', 'code': 'not_found'},
                            status=status.HTTP_404_NOT_FOUND)
        if account is not None and account.is_super:
            return Response({'error': 'not_found', 'code': 'not_found'},
                            status=status.HTTP_404_NOT_FOUND)
        # A source invitation: only a source user this caller may manage (`source_invite.manageable`
        # — a super, or the organisation admin of the source's own organisation).
        from .. import mentor_invite, source_invite
        if inv.audience == 'source_partner' and not source_invite.manageable(admin, account):
            return Response({'error': 'not_found', 'code': 'not_found'},
                            status=status.HTTP_404_NOT_FOUND)
        # A MENTOR invitation (S7a) is withdrawn on the Mentors page (Revoke), which also stamps the
        # mentor inactive; here it is not found, so the two can never leave different marks.
        if inv.audience == mentor_invite.AUDIENCE:
            return Response({'error': 'not_found', 'code': 'not_found'},
                            status=status.HTTP_404_NOT_FOUND)
        not_open = Response({'error': 'not_open', 'code': 'not_open'},
                            status=status.HTTP_400_BAD_REQUEST)
        # ⚠ CONDITIONAL WRITES, NOT A READ THEN A WRITE (review fix 2026-10-05): an acceptance or a
        # first sign-in landing between the read above and this block must win. Each UPDATE carries
        # its own "still open" condition; if either touches no row, nothing is written at all.
        now = timezone.now()
        with transaction.atomic():
            closed = Invitation.objects.filter(
                pk=inv.pk, accepted_at__isnull=True, revoked_at__isnull=True,
            ).update(revoked_at=now, updated_at=now)
            if not closed:
                return not_open
            if account is not None and not type(account).objects.filter(
                    pk=account.pk, first_seen_at__isnull=True).update(is_active=False):
                transaction.set_rollback(True)
                return not_open
            if account is not None:
                # S7d: a switched-off staff member who was also added as a mentor stops mentoring —
                # decided on the row re-read under a lock (`leave`), never on this copy (review fix 2).
                from .. import staff_mentor
                staff_mentor.leave(account, by=admin.email or '')
        inv.revoked_at = now
        # ⚠ AND THE PASSWORD IN THE LETTER STOPS WORKING AT SUPABASE TOO (staff lifecycle,
        # 2026-10-09). Switching the account off closed the console, but the emailed temporary
        # password still opened a Supabase session. AFTER the commit, so a cancel that loses the
        # race above never touches the login of somebody who is signing in right now.
        from .. import staff_lifecycle
        login = staff_lifecycle.kill_for_cancel(account, inv) if account is not None else '-'
        logger.info('AUDIT invitation_cancelled id=%s audience=%s role=%s account=%s login=%s by=%s',
                    inv.id, inv.audience, inv.role or '-', account.id if account else '-',
                    login, admin.email or '')
        return Response({'id': inv.id, 'status': inv_service.status_of(inv)})
