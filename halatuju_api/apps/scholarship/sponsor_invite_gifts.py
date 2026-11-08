"""Which gifts a SPONSOR invitation names (Invitations I3, 2026-11-08; owner ruling 1, open point B).

Until I3 a sponsor invitation held ONE gift (`Invitation.programme`). Now it names several gifts
(`InvitationGift` rows) or Every gift (`Invitation.every_gift`), like a reviewer's invite. This is
the one home for that: `choose` reads the invite form, `set_gifts` is the ONE writer, `stated` the
one reader, and `joined_on_registration` turns the invitation into the gifts a registration joins.

⚠ IT STILL GRANTS NOTHING. Each gift becomes ONE PENDING membership on registration, vetted as
today (`sponsorship.open_signup_memberships`); the invitation is a prompt, never a way round the
public registration, the terms or vetting.

⚠ EVERY GIFT IS NOT A LIVE RULE (open point B). A sponsor's acceptance is per gift, so Every gift
means *every gift active in the invitation's organisation when they register* — resolved ONCE then
and FROZEN into rows, with `Invitation.every_gift_resolved_at` stamped even when it resolved to
none, so account vetting later settles exactly those, and a gift started afterwards is never
joined by itself. (I3 review: an empty resolution used to leave nothing frozen, so vetting resolved
again against the gifts of the day.)

`Invitation.programme` is kept as the ROLLBACK MIRROR (one gift -> that id; several or every ->
NULL), exactly as `PartnerAdmin.programme` is for reviewers; the reader falls back to it only when
an invitation has no rows and no flag (written before 0207, or by the old image in the deploy gap).
"""
from django.db import transaction
from rest_framework import status
from rest_framework.response import Response

from apps.courses.staff_gift import _as_id


def _gift_refusal(code, http, programmes=None):
    body = {'error': code, 'code': code}
    if programmes is not None:
        body['programmes'] = [{'id': p.id, 'code': p.code, 'name': p.name_en or p.code}
                              for p in programmes.order_by('code')]
    return Response(body, status=http)


def nameable(admin):
    """The ACTIVE gifts a sponsor invite by ``admin`` may name — the form's choices and the POST's
    check, one home. An admin with an organisation names only ITS gifts, even a super: the
    invitation is filed under their organisation, so another tenant's gift would be a mismatch (I3
    review; the reviewer invite's rule). Only an organisation-less super reaches every tenant's."""
    from .views_admin.gift_programmes import AdminProgrammeListView
    programmes = AdminProgrammeListView()._programmes_for(admin).filter(is_active=True)
    if admin.owning_organisation_id is not None:
        programmes = programmes.filter(organisation_id=admin.owning_organisation_id)
    return programmes


def choose(admin, data, email):
    """``(choice, refusal)`` for the sponsor invite form.

    ``choice`` is ``(gifts, every)`` to store, or None for a RESEND that keeps what is stored.

    - ``programme_ids`` (a list): ``[]`` = Every gift; otherwise each id must be an ACTIVE gift
      this admin may name (`nameable`). Not a list -> 400 ``gift_required``; an unknown,
      inactive or other-tenant id -> 404 ``not_found`` (one answer, nothing leaks). An
      organisation-less super must name gifts (TD-334: Every gift has no organisation to mean),
      and their gifts must belong to ONE organisation — and, on a WAITING invitation, to THAT
      invitation's organisation, which their request leaves in place (400
      ``gift_not_in_invitation_org``, I3 third review; `_fits_the_waiting_row`).
    - ``programme_id`` (the one-gift form before I3, kept for the deploy window): that gift.
    - Neither: a waiting invitation for this address is a RESEND and is never re-homed: it keeps
      its organisation AND its gifts. That holds for the inviter's own organisation's invitation
      and for ANY super's bare invite (the web's Resend on a super's unfenced list, I3 second
      review); the view then leaves the row's organisation alone. Only a non-super from ANOTHER
      organisation makes a fresh choice, and `set_gifts` replaces that organisation's gifts
      outright (I3 review; the row moving to them is an owner question). Otherwise the
      sole active gift, none when there are none, and 400 ``programme_required`` with the choices
      when there are several — never a silent pick (the P2b / PF-1 rule).
    """
    from . import invitations as inv_service
    programmes = nameable(admin)
    if 'programme_ids' in data:
        raw = data.get('programme_ids')
        if not isinstance(raw, (list, tuple)):
            return None, _gift_refusal('gift_required', status.HTTP_400_BAD_REQUEST)
        if not raw:
            if admin.owning_organisation is None:
                return None, _gift_refusal('programme_required', status.HTTP_400_BAD_REQUEST, programmes)
            return ([], True), None
        ids = {_as_id(v) for v in raw}
        if None in ids:
            return None, _gift_refusal('not_found', status.HTTP_404_NOT_FOUND)
        gifts = list(programmes.filter(pk__in=ids).order_by('code'))
        if len(gifts) != len(ids):
            return None, _gift_refusal('not_found', status.HTTP_404_NOT_FOUND)
        if len({g.organisation_id for g in gifts}) > 1:
            return None, _gift_refusal('gifts_span_organisations', status.HTTP_400_BAD_REQUEST)
        return _fits_the_waiting_row(admin, email, gifts)
    asked = data.get('programme_id')
    if asked not in (None, ''):
        gift = programmes.filter(pk=_as_id(asked)).first() if _as_id(asked) else None
        if gift is None:
            return None, _gift_refusal('not_found', status.HTTP_404_NOT_FOUND)
        return _fits_the_waiting_row(admin, email, [gift])
    waiting = inv_service.open_invitation('sponsor', email)
    if waiting is not None and (admin.is_super
                                or admin.owning_organisation_id in (None, waiting.organisation_id)):
        return None, None            # a resend: what was asked stays asked
    live = list(programmes.order_by('code')[:2])
    if len(live) > 1:
        return None, _gift_refusal('programme_required', status.HTTP_400_BAD_REQUEST, programmes)
    return (live, False), None


def _fits_the_waiting_row(admin, email, gifts):
    """``((gifts, False), None)``, or the refusal when the gifts would land on a waiting invitation
    of ANOTHER organisation.

    An admin with an organisation names only its gifts and the invitation moves to it, so the two
    always agree. An organisation-less super passes no organisation, so `create_or_refresh` KEEPS
    the waiting row's: their gifts must be that organisation's, or its list would show another
    tenant's gift names under a letter naming it (I3 third review). A new row, or a waiting one
    with no organisation, keeps the one-organisation rule alone."""
    from . import invitations as inv_service
    if admin.owning_organisation_id is None and gifts:
        waiting = inv_service.open_invitation('sponsor', email)
        if (waiting is not None and waiting.organisation_id is not None
                and any(g.organisation_id != waiting.organisation_id for g in gifts)):
            return None, _gift_refusal('gift_not_in_invitation_org', status.HTTP_400_BAD_REQUEST)
    return (gifts, False), None


def set_gifts(inv, gifts, every):
    """THE ONE WRITER: afterwards ``inv`` names exactly ``gifts``, or Every gift when ``every``.

    A FULL replacement: no earlier row, flag or Every-gift resolution survives (I3 review — another
    organisation's invite may take the row over). Also writes the rollback mirror
    `Invitation.programme` (one gift -> that id, else NULL) with a queryset update, so no `save`
    side effect runs."""
    from .models import Invitation, InvitationGift
    wanted = set() if every else {g.pk for g in gifts}
    mirror = next(iter(wanted)) if len(wanted) == 1 else None
    with transaction.atomic():
        InvitationGift.objects.filter(invitation=inv).exclude(programme_id__in=wanted).delete()
        InvitationGift.objects.bulk_create(
            [InvitationGift(invitation=inv, programme_id=pk) for pk in sorted(wanted)],
            ignore_conflicts=True)
        Invitation.objects.filter(pk=inv.pk).update(
            programme_id=mirror, every_gift=bool(every), every_gift_resolved_at=None)
    inv.programme_id, inv.every_gift, inv.every_gift_resolved_at = mirror, bool(every), None
    getattr(inv, '_prefetched_objects_cache', {}).pop('gift_rows', None)


def stated(inv):
    """``(gifts, every)`` — what ``inv`` asked for. Rows win; then the flag; then the mirror (an
    invitation from before 0207); ``([], False)`` = nothing stated. Gifts are ordered by code."""
    rows = [r.programme for r in inv.gift_rows.all()]
    if rows:
        return sorted(rows, key=lambda p: p.code), inv.every_gift
    if inv.every_gift:
        return [], True
    if inv.programme_id:
        return [inv.programme], False
    return [], False


def row_payload(inv):
    """The waiting row's gift fields: ``gifts`` [{id, code, name}] and ``every_gift``."""
    gifts, every = stated(inv)
    return {
        'gifts': [{'id': p.id, 'code': p.code, 'name': p.name_en or p.code} for p in gifts],
        'every_gift': every,
    }


def stating_invitation(email):
    """The latest non-withdrawn sponsor invitation for ``email`` that states any gift, or None.

    Accepted ones count: the invitation outlives the registration, so registration and account
    vetting read the same answer."""
    from django.db.models import Q
    from .models import Invitation
    email = (email or '').strip()
    if not email:
        return None
    return (Invitation.objects
            .filter(Q(programme__isnull=False) | Q(every_gift=True) | Q(gift_rows__isnull=False),
                    audience='sponsor', email__iexact=email, revoked_at__isnull=True)
            .distinct().order_by('-created_at').first())


def joined_on_registration(inv, *, freeze=False):
    """The gifts ``inv`` files its registrant into.

    Named gifts -> those. Every gift resolves EXACTLY ONCE: to each gift ACTIVE in the invitation's
    organisation at that moment (none when it has no organisation — an org-less super cannot send
    Every gift). With ``freeze`` the answer is written as rows and `every_gift_resolved_at` is
    stamped, EVEN WHEN IT IS EMPTY; from then on every read returns those rows, possibly none, and
    never resolves live again. Registration freezes; so does account vetting, which therefore only
    ever resolves an invitation that was never frozen (registered under the old image during a
    rollback) — every other vetting reads what registration froze. Without ``freeze`` an unresolved
    invitation is only previewed."""
    from django.utils import timezone
    from .models import Invitation, InvitationGift, Programme
    gifts, every = stated(inv)
    if not every:
        return gifts
    if inv.every_gift_resolved_at is not None or gifts:
        return gifts                                   # resolved: the frozen rows, possibly none

    def live():
        if inv.organisation_id is None:
            return []
        return list(Programme.objects.filter(organisation_id=inv.organisation_id, is_active=True)
                    .order_by('code'))

    if not freeze:
        return live()
    with transaction.atomic():
        locked = Invitation.objects.select_for_update().get(pk=inv.pk)
        if locked.every_gift_resolved_at is None:      # nobody resolved it while we waited
            InvitationGift.objects.bulk_create(
                [InvitationGift(invitation=inv, programme=p) for p in live()],
                ignore_conflicts=True)
            locked.every_gift_resolved_at = timezone.now()
            Invitation.objects.filter(pk=inv.pk).update(
                every_gift_resolved_at=locked.every_gift_resolved_at)
    inv.every_gift_resolved_at = locked.every_gift_resolved_at
    getattr(inv, '_prefetched_objects_cache', {}).pop('gift_rows', None)
    return stated(inv)[0]
