"""Staff invitations — inviting, listing and revoking an admin of any role.

Moved verbatim from the package root at code health H12. Part of the `views_admin`
package: every name below is re-exported from `views_admin/__init__.py`, so `urls.py`
and every importer are unchanged.
"""
from rest_framework import status
from rest_framework.response import Response

from .gift_programmes import AdminProgrammeListView

from .reviewers import _ReviewersBase


class AdminInvitationsView(_ReviewersBase):
    """GET admin/invitations/[?kind=][&all=1] — who has been asked and **has not answered yet**.

    The Invitations page (owner's shape, 2026-08-03) is organised into FOUR kinds — admins,
    reviewers, source, sponsors — with one table on screen at a time, so this serves one kind plus
    the waiting counts for all four (the badge on each button; without it an invitation waiting
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
        qs = Invitation.objects.select_related('partner_admin', 'invited_by', 'programme').all()
        if org_id is not None:
            qs = qs.filter(organisation_id=org_id)

        counts = inv_service.waiting_counts(qs)
        totals = inv_service.kind_totals(qs)
        kind = (request.GET.get('kind') or inv_service.KIND_ADMINS).strip()
        if kind not in inv_service.KINDS:
            kind = inv_service.KIND_ADMINS

        # ⚠ WAITING-ONLY IS THE DEFAULT, AND THAT IS THE POINT OF THIS PAGE (2026-09-09).
        # It used to list every invitation ever sent, which on this tenant meant 18 accepted rows
        # and 2 waiting ones — a page named "Invitations" that was really a staff roster, and one
        # that would have got WORSE on its own as each waiting sponsor registered. Who is already
        # in is answered by the People directory; this endpoint answers who has not replied.
        # `?all=1` keeps the full history reachable for a caller that genuinely wants it.
        listed = inv_service.for_kind(qs, kind)
        if (request.GET.get('all') or '').strip() not in ('1', 'true'):
            listed = inv_service.open_only(listed)

        rows = []
        for i in listed.order_by('-created_at'):
            pa = i.partner_admin
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
                # Which gift this invitation was for (S-ASSIGN). NULL means EVERY gift — the
                # honest reading for every row written before the column existed, and for a
                # staff invitation, which carries none. Never render a blank as a gift name.
                'programme': i.programme.code if i.programme_id else '',
                'programme_name': (i.programme.name_en or i.programme.code)
                                  if i.programme_id else '',
            })

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
            # The gift choices for the sponsor invite form. ACTIVE only, matching exactly what
            # the POST accepts — an invitation is a prompt to register TODAY, so offering a gift
            # that is not open yet would invite somebody into a door that does not open. (The
            # accept panel on the sponsor detail page is the opposite case and takes inactive
            # ones, because a gift is staffed before it is switched on.)
            'programmes': [
                {'id': p.id, 'code': p.code, 'name': p.name_en or p.code}
                for p in AdminProgrammeListView()._programmes_for(admin)
                                                 .filter(is_active=True).order_by('code')
            ],
        })

    def post(self, request):
        """Invite a SPONSOR. The other kinds go through `AdminInviteView`, which provisions an
        account; this one deliberately provisions nothing.

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
        audience = (request.data.get('audience') or '').strip()
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

        # ⚠ WHICH GIFT ARE YOU INVITING THEM INTO? (S-ASSIGN, 2026-09-04.) Until now this form
        # asked for an email, a name and a note, derived the organisation, and never asked — so a
        # benefactor invited for Sabah would have registered straight into the flagship, silently,
        # and their credit would then have been refused `sponsor_not_in_programme`.
        #
        # ⚠ ONE GIFT ASKS NOTHING. Omitted + the organisation runs exactly one → that one, so the
        # existing form is unchanged for BrightPath and nothing is sent. More than one and none
        # named → 400 `programme_required` carrying the choices, never a silent pick (the P2b /
        # PF-1 rule). A gift outside the caller's organisation is 404, never 403.
        #
        # It GRANTS nothing either way: a sponsor invitation creates no account and is a prompt to
        # the ordinary public registration, where they still consent, sign the terms and are
        # vetted. This only records which gift the organisation meant.
        programmes = AdminProgrammeListView()._programmes_for(admin).filter(is_active=True)
        asked = request.data.get('programme_id')
        if asked:
            programme = programmes.filter(pk=asked).first()
            if programme is None:
                return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        else:
            live = list(programmes.order_by('code')[:2])
            if len(live) > 1:
                return Response(
                    {'error': 'programme_required', 'code': 'programme_required',
                     'programmes': [{'id': p.id, 'code': p.code, 'name': p.name_en}
                                    for p in programmes.order_by('code')]},
                    status=status.HTTP_400_BAD_REQUEST)
            programme = live[0] if live else None

        inv = inv_service.create_or_refresh(
            audience='sponsor', email=email, name=(request.data.get('name') or '').strip(),
            organisation=org, invited_by=admin, programme=programme,
            ttl_days=inv_service.PII_RETENTION_DAYS)

        from ..emails import send_sponsor_invitation_email
        ok, error = send_sponsor_invitation_email(
            email, org_name=(org.name if org else ''), note=(request.data.get('note') or ''),
            code=inv.code, invited_by=admin.name)
        inv_service.record_send(inv, ok, error)
        return Response({'id': inv.id, 'emailed': ok},
                        status=status.HTTP_201_CREATED if ok else status.HTTP_502_BAD_GATEWAY)
