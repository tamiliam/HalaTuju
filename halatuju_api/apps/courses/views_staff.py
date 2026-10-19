"""Staff accounts: invite, re-send, list, revoke / restore, and delete.

`AdminDeleteView` moved here from `views_admin.py` with the staff lifecycle sprint (2026-10-09): that
sprint changed what a delete does (the Supabase login goes too), so the view moved to its own module
rather than grow the big one.

`AdminInviteView`, `AdminResendView`, `AdminListView` and `AdminRevokeView` moved here VERBATIM from
`views_admin.py` (staff permissions Sprint 1, request #39, 2026-10-19), a moves-only split in its own
commit: `views_admin.py` is in the oversize ledger and a hotspot, sat at 1161 of its 1165 allowance,
and Sprint 1 changes the invite's "already exists" answer. Not a line of the four bodies was
reworded. Their helpers (`_staff_target_manageable`, `_record_invitation`, the role sets, the
welcome-email seam, ...) stay in `views_admin.py` — other callers read them there — and are imported
here under the same names. `urls.py` imports all five views from here. (The one line changed since
the move, in the next commit: the invite's 409 is built by `already_exists_answer`.)

⚠ The logger keeps the OLD module's name, so the `AUDIT staff_deleted` line reads exactly as it did.
⚠ A test that patches the welcome email for an INVITE patches `apps.courses.views_staff.
send_partner_welcome_email` (the name this module calls); `apps.scholarship.emails.
send_partner_welcome_email` still bites from either module, through the seam.
"""
import logging

from django.conf import settings
from django.db import DatabaseError, transaction
from rest_framework.response import Response
from rest_framework.views import APIView

from . import referral_links, staff_reinvite, supabase_admin
from .models import PartnerAdmin, PartnerOrganisation
from .views_admin import (PROGRAMME_STAFF_ROLES, _DELETABLE_ROLES, _ORG_ADMIN_MANAGEABLE_ROLES,
                          PartnerAdminMixin, _deletable_now, _invitation_dict, _invitations_for,
                          _record_invitation, _record_invitation_send, _staff_target_manageable,
                          generate_temp_password, is_google_email, scholarship_staff,
                          send_partner_welcome_email)

logger = logging.getLogger('apps.courses.views_admin')

#: The ONE answer for an address that belongs to somebody this caller cannot see on People: another
#: organisation's staff, a platform account (super, referral partner). It confirms nothing about
#: the other account — not its organisation, its role, its name or whether it is switched off.
NOT_INVITABLE = "This email address can't be invited. Ask HalaTuju support."


def _listed_on_people(caller, target):
    """Whether ``caller`` already sees ``target`` on People — `AdminListView`'s own filter: a super
    lists every staff account; anyone else only their organisation's programme staff."""
    if caller.is_super:
        return True
    return (caller.owning_organisation_id is not None
            and target.owning_organisation_id == caller.owning_organisation_id
            and target.role in PROGRAMME_STAFF_ROLES
            and not target.is_super_admin and not target.is_super)


def already_exists_answer(caller, existing):
    """The 409 an invite answers when the address already has a staff account (request #39 S1).

    It used to say "Admin with this email already exists" to everybody, which told an org_admin
    that an address was in use SOMEWHERE and nothing they could act on. Now:

    - **the caller can already see them on People** (same organisation; or any account, for a
      super) → `already_on_team`, with their name and preset, and where to go. It names nothing
      the caller's own People page does not already show.
    - **anyone else** → `not_invitable` with ONE fixed sentence (`NOT_INVITABLE`). Another
      organisation's colleague, a super, a referral partner: all the same answer, so it cannot be
      used to learn which organisation an address belongs to (the S1 door list's question).

    Somebody listed but NOT manageable by the caller (`_staff_target_manageable` — a fellow
    organisation admin) is named, but never sent to People, where there is nothing they can do:
    "… Ask HalaTuju support to change this." (review fix 6).

    A student's or sponsor's own login is not a staff account and never reaches here: it is still
    invited on the already-registered 201 path — lead ruling 2026-10-19 (a person with a student
    login may legitimately become staff; the inviter learns only that the address has a HalaTuju
    login, which is pre-existing, accepted behaviour). The sentences are served; the web adds none.
    """
    if existing is None or not _listed_on_people(caller, existing):
        return Response({'error': NOT_INVITABLE, 'code': 'not_invitable'}, status=409)
    role = 'super' if existing.is_super else existing.role
    label = dict(PartnerAdmin.ROLE_CHOICES).get(role, role)
    name = existing.name
    if caller.is_super:
        org = existing.owning_organisation.name if existing.owning_organisation_id else 'no organisation'
        where = f'{name} already has a staff account ({label}, {org}).'
    elif existing.is_active:
        where = f'{name} is already on your team as {label}.'
    else:
        where = f'{name} is on your team as {label}, but switched off.'
    if not _staff_target_manageable(caller, existing):
        then = 'Ask HalaTuju support to change this.'
    elif existing.is_active:
        then = f'To change what they can do, open People → {name}.'
    else:
        then = f'To bring them back, open People → {name}.'
    return Response({'error': f'{where} {then}', 'code': 'already_on_team', 'name': name,
                     'preset': role, 'is_active': existing.is_active}, status=409)


class AdminDeleteView(PartnerAdminMixin, APIView):
    """DELETE /api/v1/admin/admins/<id>/ — remove a staff account that never started.

    ⚠ **REVOKE IS THE NORMAL ANSWER; THIS IS THE NARROW ONE.** Owner, 2026-09-09: an admin *"should
    only be deleted if they are not doing any work"*. Once somebody has done something, the record
    of who did it has to keep meaning something — so they are revoked, for ever, and this refuses.

    ⚠ **THE GUARD IS A FOOTPRINT, NOT THE DATABASE'S OWN PROTECTIONS**, and the difference is not
    academic. A `PaymentRun` stores its author as `created_by`, an EMAIL STRING with no foreign key:
    on production one admin had made 25 of the 27 runs and signed 8, and a foreign-key rule would
    have declared her safe to delete and left 25 runs naming an address with nobody behind it. See
    `apps.scholarship.staff_footprint`.

    ⚠ **REVIEWERS ARE NEVER DELETABLE** (`_DELETABLE_ROLES`), however empty their record looks —
    the owner scoped this to admins explicitly, and a reviewer is who a student's case passed
    through.

    ⚠ **THE LOGIN GOES TOO, BEFORE THE ROW** (2026-10-09). The row is the only record of which
    Supabase login is ours; deleting it and leaving the login made a re-invite of the same address
    take the "already registered" path and email no password — which happened to a real invitee.
    `staff_lifecycle.plan_login_retirement` decides (only when the login is ours and unused) and
    `retire_login` acts once the row is gone. If Supabase cannot be READ nothing is deleted (502);
    if the removal itself fails after the row is gone, that is logged at ERROR and the leftover
    unused login is adopted by the next invite of the address (`staff_lifecycle.adoptable_login`).
    The account's `Invitation` rows are deleted with it (`Invitation.partner_admin` is CASCADE).

    Refusals are separated on purpose: 404 for a row this caller may not touch (no existence leak),
    400 for a role that is never deletable, and **409 with the counts** when there is work — so the
    screen can say *what* is stopping it rather than greying a button for no visible reason.
    """

    def delete(self, request, admin_id):
        admin = self.get_admin(request)
        if not admin or not (admin.is_super or admin.role == 'org_admin'):
            return Response({'error': 'Super admin access required'}, status=403)
        staff_footprint, staff_lifecycle = scholarship_staff()

        # ⚠ LOCKED, RE-CHECKED, ROW FIRST, LOGIN LAST (review M2). The row is locked and every
        # refusal re-read on the locked copy, so work landing between the list and the click still
        # refuses; the login is only PLANNED inside the transaction (a read), and removed after the
        # row is gone — so a failed row delete can never leave a row naming a deleted login.
        try:
            return self._delete_locked(admin, admin_id, staff_footprint, staff_lifecycle)
        except DatabaseError:
            logger.exception('staff delete of %s failed in the database; nothing was removed',
                             admin_id)
            return Response({'error': 'Could not delete them just now. Nothing was removed; try '
                             'again.', 'code': 'delete_failed'}, status=503)

    def _delete_locked(self, admin, admin_id, staff_footprint, staff_lifecycle):
        with transaction.atomic():
            target = PartnerAdmin.objects.select_for_update().filter(id=admin_id).first()
            if target is None or not _staff_target_manageable(admin, target):
                return Response({'error': 'Admin not found'}, status=404)
            if target.is_super_admin or target.is_super:
                return Response({'error': 'Cannot delete a super admin', 'code': 'not_deletable'},
                                status=400)
            if target.role not in _DELETABLE_ROLES:
                return Response({'error': 'Only an admin account can be deleted',
                                 'code': 'not_deletable'}, status=400)
            work = staff_footprint.footprint(target)
            if work:
                return Response({'error': f'{target.name} has work on record and can only be '
                                 'revoked.', 'code': 'has_work', 'work': work}, status=409)
            plan, account = staff_lifecycle.plan_login_retirement(target)
            if plan == 'failed':
                return Response({'error': 'Could not check their sign-in. Nothing was deleted; '
                                 'try again.', 'code': 'login_cleanup_failed'}, status=502)
            name, email, uid = target.name, target.email, target.supabase_user_id
            target.delete()
        login = staff_lifecycle.retire_login(uid, plan, account)
        logger.info('AUDIT staff_deleted by=%s target=%s email=%s login=%s',
                    admin.email, admin_id, email, login)
        # ⚠ SAID HONESTLY (review round 2, N3): the row is gone either way, but a login we meant to
        # remove or close may still be there. `retire_login` has logged it at ERROR with the UID.
        if login == 'failed':
            return Response({'message': f'{name} deleted, but their sign-in could not be removed '
                             '— tell support.', 'login': login})
        return Response({'message': f'{name} deleted.', 'login': login})


class AdminInviteView(PartnerAdminMixin, APIView):
    """POST /api/v1/admin/invite/ — invite staff. A platform super may add any staff role
    (incl. a new organisation admin = add-tenant); an org_admin may add programme staff
    (reviewer/admin/qc/finance) to their OWN organisation only."""

    def post(self, request):
        admin = self.get_admin(request)
        if not admin:
            return Response({'error': 'Admin access required'}, status=403)
        # Who may invite: the PLATFORM super (any staff role incl. a new org admin), OR an
        # ORGANISATION admin (org_admin) delegating programme staff within their OWN org.
        caller_super = admin.is_super
        caller_org_admin = (admin.role == 'org_admin')
        if not (caller_super or caller_org_admin):
            return Response({'error': 'Super admin access required'}, status=403)

        email = request.data.get('email', '').strip().lower()
        name = request.data.get('name', '').strip()
        org_id = request.data.get('org_id')
        new_org_name = request.data.get('new_org_name', '').strip()
        new_org_code = request.data.get('new_org_code', '').strip().lower()

        # Roles this caller may grant. A super may create any staff role including a new
        # ORGANISATION admin (add-tenant); an org_admin may add only programme staff to
        # their own org (never partner/super/org_admin — no privilege escalation).
        if caller_super:
            invitable = {'admin', 'partner', 'reviewer', 'qc', 'org_admin', 'finance'}
        else:
            invitable = _ORG_ADMIN_MANAGEABLE_ROLES
        role = request.data.get('role', 'reviewer')
        if role not in invitable:
            if caller_super:
                role = 'reviewer'   # forgiving default (unchanged super behaviour)
            else:
                return Response({'error': 'You cannot grant that role.', 'code': 'role_not_allowed'}, status=403)

        if not email or not name:
            return Response({'error': 'email and name are required'}, status=400)

        # TD-335: a switched-off invitee who never signed in is invited AGAIN (`staff_reinvite`).
        reuse = PartnerAdmin.objects.filter(email__iexact=email).order_by('id').first()  # any case
        exists = already_exists_answer(admin, reuse)   # request #39: says only what People shows
        if reuse is not None and not staff_reinvite.may_reuse(admin, reuse):
            return exists

        # ── Resolve the referral org (`org`, partner only) + the B40 tenant fence
        #    (`owning_organisation`). The two are DISTINCT: referral ≠ ownership. ──
        org = None
        owning_org = None
        if caller_org_admin:
            # An org_admin's invites ALWAYS land in the caller's own organisation; any org
            # inputs are ignored (role already restricted to reviewer/admin/qc above).
            owning_org = admin.owning_organisation
            if owning_org is None:
                return Response({'error': 'Your account is not bound to an organisation.',
                                 'code': 'no_owning_org'}, status=400)
        elif role == 'partner':
            # A REFERRAL partner (a platform concept — roadshow orgs of the course selector),
            # scoped to their referral org's students. No B40 tenant access (owning_org stays None).
            # Sources Sprint B: only onto a REFERRAL-PARTNER row, never a tenant or a source.
            org, refusal = referral_links.partner_invite_org(
                org_id, new_org_code, new_org_name,
                request.data.get('contact_person', ''), request.data.get('org_phone', ''))
            if refusal:
                return Response({'error': referral_links.INVITE_REFUSALS[refusal], 'code': refusal},
                                status=404 if refusal == 'org_not_found' else 400)
        elif role == 'org_admin':
            # A5 — a super installs a new organisation's ADMIN, creating/selecting its TENANT
            # (the owning_organisation, NOT the referral `org`) and switching the scholarship
            # module on. This is the thin add-tenant slice of the superadmin portal.
            if new_org_name and new_org_code:
                owning_org, _ = PartnerOrganisation.objects.get_or_create(
                    code=new_org_code,
                    defaults={
                        'name': new_org_name,
                        'contact_person': request.data.get('contact_person', ''),
                        'phone': request.data.get('org_phone', ''),
                        'module_scholarship': True,
                    },
                )
            elif org_id:
                try:
                    owning_org = PartnerOrganisation.objects.get(id=org_id)
                except PartnerOrganisation.DoesNotExist:
                    return Response({'error': 'Organisation not found'}, status=404)
            if owning_org is None:
                return Response({'error': 'A tenant organisation is required.', 'code': 'tenant_required'}, status=400)
            # Sources Sprint B: never turns a referral partner or a source's old row into a tenant.
            refusal = referral_links.tenant_invite_refusal(
                owning_org, new=bool(new_org_name and new_org_code))
            if refusal:
                return Response({'error': referral_links.INVITE_REFUSALS[refusal], 'code': refusal},
                                status=400)
            if not owning_org.module_scholarship:
                owning_org.module_scholarship = True
                owning_org.save(update_fields=['module_scholarship'])
        else:
            # A super inviting a B40 staff role (admin/reviewer/qc) → bind to org #1 (BrightPath)
            # for the access fence. super stays global (NULL). (Per-org staff picker is future.)
            owning_org = PartnerOrganisation.objects.filter(code='brightpath').first()

        service_role_key = getattr(settings, 'SUPABASE_SERVICE_ROLE_KEY', '')
        supabase_url = getattr(settings, 'SUPABASE_URL', '')

        if not service_role_key or not supabase_url:
            return Response({'error': 'Supabase service role key not configured'}, status=500)

        # Option 1 (owner 2026-07-14): a Google address signs in with Google — never issue it a
        # password. Create ONLY the PartnerAdmin row (supabase_user_id stays None and links by
        # verified email on first Google sign-in, exactly like the already-registered path), and
        # send the no-password "sign in with Google" email. No Supabase account is created here — it
        # materialises when they first sign in with Google.
        if is_google_email(email):
            created, _, err = staff_reinvite.provision(
                reuse, email=email, name=name, role=role, org=org, owning_org=owning_org)
            if err:
                return exists
            # ⚠ `credential_issued=False`: a Google invitee is never given a password, so nothing of
            # theirs can EXPIRE. The screen must say "no reply", not "expired", or an org_admin goes
            # hunting for a password that never existed. This is the one moment we know which
            # branch was taken.
            inv = _record_invitation(created, role, owning_org or org, request,
                                     credential_issued=False)
            emailed = send_partner_welcome_email(email, name, role, temp_password=None, google=True)
            _record_invitation_send(inv, emailed)
            message = f'{name} added — they sign in with Google ({email}).'
            if not emailed:
                message = f'{name} was added, but the email could not be sent. Use Resend to try again.'
            return Response({
                'message': message, 'org': (org or owning_org).name if (org or owning_org) else None, 'role': role,
                'already_registered': False, 'google': True, 'emailed': emailed,
            }, status=201)

        # Non-Google: create the Supabase account OURSELVES rather than sending a Supabase invite
        # (see `_create_supabase_user` for why). The temp password never leaves this request except
        # in the welcome email, and expires after the 7-day TTL (login gate + expire cron).
        # The row (new, or the cancelled one brought back — TD-335) is written by `provision`.
        temp_password = generate_temp_password()
        created, already_registered, err = staff_reinvite.provision(
            reuse, email=email, name=name, role=role, org=org, owning_org=owning_org,
            temp_password=temp_password)
        if err == 'not_reusable':
            return exists
        if err:
            return Response({'error': 'Failed to create the partner account'}, status=502)

        # ⚠ `credential_issued` is FALSE on the already-registered branch — that person keeps the
        # login they already had and is sent no password, so like a Google invitee they can go
        # unanswered but cannot expire.
        inv = _record_invitation(created, role, owning_org or org, request,
                                 credential_issued=not already_registered)

        # The email is the ONLY carrier of the temp password, so a failed send strands the
        # invitee — report it instead of swallowing it, and the UI tells the owner to Resend.
        emailed = send_partner_welcome_email(
            email, name, role, temp_password=None if already_registered else temp_password,
        )
        _record_invitation_send(inv, emailed)

        message = (
            f'{name} already has an account — access granted. They can sign in as they always do.'
            if already_registered else f'Account created. Sign-in details emailed to {email}.'
        )
        if not emailed:
            message = f'{name} was added, but the email could not be sent. Use Resend to try again.'
        return Response({
            'message': message,
            'org': (org or owning_org).name if (org or owning_org) else None,
            'role': role,
            'already_registered': already_registered,
            'emailed': emailed,
        }, status=201)


class AdminResendView(PartnerAdminMixin, APIView):
    """POST /api/v1/admin/admins/<id>/resend/ - Re-send a partner's sign-in details.

    The reason this exists: the old Supabase invite link expired after 24 hours and there was NO
    way to send another one (this view's sibling 409s on an existing PartnerAdmin, and Supabase
    refuses to re-invite an address that already has an auth user), so a partner who missed the
    window was stuck — which is exactly what happened on 2026-07-10. Resending is safe now
    because the email carries no token: we simply rotate the temporary password and re-send it.
    """

    def post(self, request, admin_id):
        admin = self.get_admin(request)
        if not admin or not (admin.is_super or admin.role == 'org_admin'):
            return Response({'error': 'Super admin access required'}, status=403)

        target = PartnerAdmin.objects.filter(id=admin_id).first()
        if target is None or not _staff_target_manageable(admin, target):
            # Not found OR not manageable by this caller (cross-org / super target) — 404,
            # so an org_admin can't probe for the existence of other orgs' or platform staff.
            return Response({'error': 'Admin not found'}, status=404)
        # Switched off = cannot sign in, so a Resend would email a password that lets nobody in.
        if not target.is_active:
            return Response({'error': f'{target.name} cannot sign in — restore them first.',
                             'code': 'not_active'}, status=400)
        if supabase_admin.supabase_config() is None:
            return Response({'error': 'Supabase service role key not configured'}, status=500)

        # No UID = the account pre-existed ours (student/Google sign-up), so we never issued a
        # password and must not reset theirs. Re-send the "sign in as you always do" note.
        # A Resend gives a fresh temp password AND a fresh TTL clock (`issue_temp_password`).
        temp_password = None
        if target.supabase_user_id:
            temp_password = generate_temp_password()
            if not supabase_admin.issue_temp_password(
                    target.supabase_user_id, target.name, temp_password):
                return Response({'error': 'Failed to reset the password'}, status=502)

        # ⚠ A RE-SEND REFRESHES THE INVITATION, IT DOES NOT START A NEW ONE. `create_or_refresh`
        # finds the open row and moves ONE clock — the same clock the temp-password TTL just reset
        # above. Two clocks would let this screen say "still valid" about a password the login gate
        # already refuses. `credential_issued` reflects what THIS send did: a target with no UID is
        # sent no password, so it stays false and the screen says "no reply" rather than "expired".
        inv = _record_invitation(target, target.role, target.owning_organisation, request,
                                 credential_issued=bool(temp_password))

        emailed = send_partner_welcome_email(
            target.email, target.name, target.role, temp_password=temp_password,
        )
        _record_invitation_send(inv, emailed, 'send failed')
        if not emailed:
            return Response({'error': 'Failed to send the email', 'emailed': False}, status=502)
        return Response({
            'message': f'Sign-in details re-sent to {target.email}.',
            'emailed': True,
        })


class AdminListView(PartnerAdminMixin, APIView):
    """GET /api/v1/admin/admins/ — list staff. Super sees ALL; an org_admin or (matrix
    2026-07-15) an Admin-General sees only the non-super programme staff in their OWN
    organisation. Admin-General is READ-ONLY here — invite/resend/revoke stay super/org_admin."""

    def get(self, request):
        admin = self.get_admin(request)
        if not admin or not (admin.is_super or admin.role in ('org_admin', 'admin')):
            return Response({'error': 'Super admin access required'}, status=403)

        admins = PartnerAdmin.objects.select_related('org', 'owning_organisation').order_by('-created_at')
        if not admin.is_super:
            # ⚠ **SEEING IS NOT MANAGING (2026-09-09).** This used to filter the LIST by
            # `_ORG_ADMIN_MANAGEABLE_ROLES`, so an org_admin could not see the OTHER org_admins of
            # their own organisation at all. That is the right rule for acting on somebody and the
            # wrong one for listing them: when Organisation → People took over the roster from
            # Invitations (which fences on the invitation's organisation, not on role) the owner's
            # two fellow organisation admins simply vanished from the console. Everyone in the
            # tenant is listed; `manageable` below says who may be acted on, and
            # `_staff_target_manageable` still refuses at every write endpoint.
            admins = admins.filter(
                owning_organisation_id=admin.owning_organisation_id,
                role__in=PROGRAMME_STAFF_ROLES,
                is_super_admin=False,
            )
        admins = list(admins)
        invites = _invitations_for(admins)
        # Dormancy threshold per ROW, not per page (Org Config Sprint C): a super's list spans
        # organisations, and each person reads as dormant by THEIR org's `admin_dormant_days`.
        # The FE (`invitations.standingOf`) uses the served number; its constant is only the
        # fallback for a payload predating this field. Cached per org id.
        from . import org_config
        staff_footprint, _ = scholarship_staff()
        _dormant_cache = {}

        def _dormant_for(a):
            org_id = a.owning_organisation_id
            if org_id not in _dormant_cache:
                _dormant_cache[org_id] = org_config.value(
                    a.owning_organisation, 'admin_dormant_days')
            return _dormant_cache[org_id]

        data = []
        for a in admins:
            data.append({
                'id': a.id,
                'name': a.name,
                'email': a.email,
                'is_super_admin': a.is_super_admin,
                'role': 'super' if a.is_super else a.role,
                'is_active': a.is_active,
                'org_name': a.org.name if a.org else None,
                # Tenant binding (access boundary) — lets the panel's Add-tenant list show
                # which organisation an org_admin runs, and lets the FE derive the sole-
                # org-admin state (hide Revoke). NOT the referral org above.
                'owning_org_id': a.owning_organisation_id,
                'owning_org_name': a.owning_organisation.name if a.owning_organisation else None,
                'created_at': a.created_at.isoformat(),
                # ⚠ Pause is serialised by `AdminReviewerListView._reviewer_dict` and was NOT here,
                # so the Staff table and the Reviewers table showed the same people and disagreed
                # about who had stepped back — a reviewer reading "Active" on one screen and
                # "Paused" on the other. Same shape as the stored-field-with-no-surface cluster:
                # the column exists, one reader renders it, the other never asked. 2026-08-03.
                'paused': a.paused_at is not None,
                'paused_at': a.paused_at.isoformat() if a.paused_at else None,
                # ⚠ NULL is NOT RECORDED, never "never signed in". Both columns start empty for
                # everybody who was already here, and the Supabase backfill is best-effort, so a
                # screen that renders these must say "not recorded" rather than accuse somebody of
                # having ignored their invitation.
                'first_seen_at': a.first_seen_at.isoformat() if a.first_seen_at else None,
                'last_seen_at': a.last_seen_at.isoformat() if a.last_seen_at else None,
                'dormant_days': _dormant_for(a),
                # ⚠ MAY THIS CALLER ACT ON THIS ROW? Everyone in the tenant is LISTED; only some
                # may be revoked. Computed by the same `_staff_target_manageable` the write
                # endpoints enforce, so the screen cannot offer a button the server will refuse.
                'manageable': _staff_target_manageable(admin, a),
                # ⚠ AND MAY THEY BE DELETED? A staff row is deletable only when it belongs to an
                # admin-shaped role AND has never done any recorded work — see
                # `staff_footprint`, and `AdminDeleteView` for why a footprint rather than the
                # database's own protections. `work` says what stops it, so the screen can name
                # the reason instead of hiding a button for no visible cause.
                'deletable': _deletable_now(admin, a),
                'work': staff_footprint.footprint(a),
                # The invitation behind this person, and how far it got. Computed server-side so
                # the screen renders a word rather than re-deriving the rule — the same split
                # `_reviewer_dict` / `reviewerTable.ts` uses.
                'invitation': _invitation_dict(invites.get(a.id)),
            })
        return Response({'admins': data})


class AdminRevokeView(PartnerAdminMixin, APIView):
    """PATCH /api/v1/admin/admins/<id>/revoke/ - Revoke or restore admin access."""

    def patch(self, request, admin_id):
        admin = self.get_admin(request)
        if not admin or not (admin.is_super or admin.role == 'org_admin'):
            return Response({'error': 'Super admin access required'}, status=403)

        target = PartnerAdmin.objects.filter(id=admin_id).first()
        if target is None or not _staff_target_manageable(admin, target):
            # 404 for a missing row OR a target outside this caller's remit (cross-org / super).
            return Response({'error': 'Admin not found'}, status=404)

        if target.is_super_admin:
            return Response({'error': 'Cannot revoke super admin'}, status=400)

        action = request.data.get('action')
        # Last-org-admin protection (matrix 2026-07-15): never revoke the SOLE active
        # org_admin of a tenant — it would strand the organisation with no administrator.
        # (Only a super reaches this branch: _staff_target_manageable refuses an org_admin
        # caller a same-tier org_admin target.) Restore is unaffected.
        if (action == 'revoke' and target.role == 'org_admin' and target.is_active
                and target.owning_organisation_id is not None):
            has_other = (PartnerAdmin.objects
                         .filter(role='org_admin', is_active=True,
                                 owning_organisation_id=target.owning_organisation_id)
                         .exclude(id=target.id).exists())
            if not has_other:
                return Response({'error': 'last_org_admin', 'code': 'last_org_admin'}, status=400)
        if action == 'revoke':
            target.is_active = False
            target.save(update_fields=['is_active'])
            return Response({'message': f'{target.name} access revoked'})
        elif action == 'restore':
            target.is_active = True
            target.save(update_fields=['is_active'])
            return Response({'message': f'{target.name} access restored'})
        else:
            return Response({'error': 'action must be "revoke" or "restore"'}, status=400)
