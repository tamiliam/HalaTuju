"""Which gifts a reviewer covers — TD-501 / SEC-17 (A1.3) and multi-gift tagging (owner, 2026-11-06).

⚠ THE GIFTS LIVE IN `ReviewerGift` ROWS, AND NO ROWS MEANS EVERY GIFT (owner's default). Rows
NARROW the offer. `PartnerAdmin.programme` is no longer read anywhere: `set_gifts` keeps it as a
write-only rollback mirror (one gift -> that id, otherwise NULL), to be dropped by TD-540.

A reviewer INVITE must still say what it chose (owner ruling "b", A1.3) — a list of gifts:

- ``programme_ids: [..]`` — the owning organisation's gifts; ``[]`` means every gift;
- the old one-gift form (``gift_scope='one'`` + ``programme_id``, or ``gift_scope='every'``) is
  still read, so a page loaded before the deploy keeps working.

No choice at all is a 400 ``gift_required``. A gift outside the organisation is a 404, never a 403
(a 403 would confirm another tenant's gift exists — the `AdminReviewerProgrammeView` rule).

⚠ EVERY GIFT IS THE REVIEWER'S OWN ORGANISATION'S: rows are written ONLY by `set_gifts`, and only
with gifts `resolve_gifts` found inside that organisation. A database check cannot see across the
two foreign keys, so this is the one door.

⚠ ROLES OTHER THAN THE REVIEWER ARE UNCHANGED: admins, QC, finance, org admins and partners are
never asked, and the source and mentor invites never come here.

⚠ THE GIFT IS NOT A READ FENCE: what a reviewer can READ is fenced by the organisation and by
assignment (`views_admin.base._scoped_application`). Since 2026-11-06 (owner ruling) it BLOCKS
ASSIGNMENT: `assign_reviewer` refuses `gift_mismatch` (`services.assignment.gift_allows`).
"""
from django.apps import apps
from django.db import transaction
from django.db.models import Aggregate, CharField, OuterRef, Subquery, TextField, Value
from django.db.models.functions import Cast, Concat
from rest_framework.response import Response

#: Roles whose invite must name a gift. Only the reviewer: the gift decides which cases a
#: reviewer is offered. An admin, QC or finance person is not offered cases by gift.
GIFT_SCOPED_ROLES = frozenset({'reviewer'})

ONE = 'one'
EVERY = 'every'
CHOICES = (ONE, EVERY)


def _gift_refusal(code, status, message):
    return Response({'error': message, 'code': code}, status=status)


def _not_found():
    return _gift_refusal('not_found', 404, 'Gift not found.')


def _as_id(raw):
    """A positive integer id, or None. A bool is never an id (``True`` would read as 1)."""
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw if raw > 0 else None
    if isinstance(raw, str) and raw.strip().isdigit():
        value = int(raw.strip())
        return value if value > 0 else None
    return None


def staff_invite_org(admin):
    """The organisation a reviewer/admin/qc/finance invite by ``admin`` binds to — ONE home, read
    by `AdminInviteView` (the binding) and by `reviewer_gift_choices` (the picker), so the gifts
    offered and the gifts `for_invite` accepts cannot disagree (A1.3 review, 2026-11-06).

    An org_admin: their own organisation. A super: BrightPath (org #1; a per-org staff picker is
    future work). A partner or a new organisation admin is bound elsewhere and never comes here."""
    if admin.role != 'org_admin' and admin.is_super:
        PartnerOrganisation = apps.get_model('courses', 'PartnerOrganisation')
        return PartnerOrganisation.objects.filter(code='brightpath').first()
    return admin.owning_organisation


def reviewer_gift_choices(admin):
    """The ACTIVE gifts a reviewer invite by ``admin`` may name: only the gifts of the organisation
    the invite binds to (`staff_invite_org`). Before, a super was offered every organisation's
    gifts and then refused 404 on any that was not BrightPath's."""
    Programme = apps.get_model('scholarship', 'Programme')
    org = staff_invite_org(admin)
    if org is None:
        return Programme.objects.none()
    return Programme.objects.filter(organisation=org, is_active=True).order_by('code')


def resolve_gifts(raw, organisation_id):
    """``(gifts, refusal)`` for a LIST of gift ids that must all be ``organisation_id``'s.

    ``[]`` -> ``([], None)``: every gift. Not a list -> 400 ``gift_required``. Any id that is not
    an id, unknown, or another organisation's -> 404 ``not_found`` — one answer, so nothing about
    another tenant leaks. The gifts come back ordered by code, each once."""
    if not isinstance(raw, (list, tuple)):
        return None, _gift_refusal('gift_required', 400,
                                   'Send the list of gifts; an empty list means every gift.')
    ids = [_as_id(v) for v in raw]
    if not ids:
        return [], None
    if None in ids or organisation_id is None:
        return None, _not_found()
    wanted = set(ids)
    Programme = apps.get_model('scholarship', 'Programme')
    gifts = list(Programme.objects.filter(pk__in=wanted, organisation_id=organisation_id)
                 .order_by('code'))
    if len(gifts) != len(wanted):
        return None, _not_found()
    return gifts, None


def for_invite(data, role, owning_org):
    """``(gifts, refusal Response | None)`` for a staff invite of ``role``; ``[]`` = every gift.

    A role outside `GIFT_SCOPED_ROLES` -> ``([], None)``: nothing is asked and nothing changes.
    A gift-scoped role -> the explicit choice above, or a refusal the view returns as it stands.
    """
    if role not in GIFT_SCOPED_ROLES:
        return [], None
    org_id = owning_org.pk if owning_org is not None else None
    if 'programme_ids' in data:
        return resolve_gifts(data.get('programme_ids'), org_id)
    scope = data.get('gift_scope')     # the one-gift form of before multi-gift (deploy window)
    scope = scope.strip().lower() if isinstance(scope, str) else ''
    if scope not in CHOICES:
        return None, _gift_refusal('gift_required', 400,
                                   'Choose the gifts this reviewer covers, or every gift.')
    raw = data.get('programme_id')
    if scope == EVERY:
        if raw not in (None, ''):
            return None, _gift_refusal('gift_conflict', 400,
                                       'Every gift was chosen, so no single gift can be named.')
        return [], None
    programme_id = _as_id(raw)
    if programme_id is None:
        return None, _gift_refusal('gift_required', 400, 'Choose the gift this reviewer covers.')
    return resolve_gifts([programme_id], org_id)


def set_gifts(admin, gifts):
    """THE ONE WRITER of ``admin``'s gift rows: afterwards they are exactly ``gifts`` (``[]`` =
    every gift). The caller has already resolved ``gifts`` inside ``admin``'s organisation.

    Also writes the ROLLBACK MIRROR `PartnerAdmin.programme` (one gift -> that id, otherwise NULL)
    with a queryset update, so no `save` side effect runs. Never read it (TD-540 drops it)."""
    ReviewerGift = apps.get_model('courses', 'ReviewerGift')
    wanted = {g.pk for g in gifts}
    with transaction.atomic():
        ReviewerGift.objects.filter(partner_admin=admin).exclude(programme_id__in=wanted).delete()
        ReviewerGift.objects.bulk_create(
            [ReviewerGift(partner_admin=admin, programme_id=pk) for pk in sorted(wanted)],
            ignore_conflicts=True)
        mirror = next(iter(wanted)) if len(wanted) == 1 else None
        if admin.programme_id != mirror:
            type(admin).objects.filter(pk=admin.pk).update(programme_id=mirror)
            admin.programme_id = mirror
    getattr(admin, '_prefetched_objects_cache', {}).pop('gift_rows', None)
    admin.__dict__.pop(PACKED, None)          # a list's packed gifts are now stale


#: Separators inside the packed annotation: ASCII "record" and "unit" separators, which no gift
#: code or name contains.
_ROW, _FIELD = '', ''
PACKED = 'gifts_packed'


class _Joined(Aggregate):
    """The rows' text joined by a separator — STRING_AGG on Postgres, GROUP_CONCAT on SQLite (any
    version; both take ``(text, separator)``). Order is not relied on: the reader sorts by code."""
    function = 'STRING_AGG'
    output_field = TextField()

    def as_sqlite(self, compiler, connection, **extra):
        return super().as_sql(compiler, connection, function='GROUP_CONCAT', **extra)


def gift_annotation():
    """For a LIST of staff: ``.annotate(**staff_gift.gift_annotation())`` — each person's gifts
    packed into ONE correlated subquery of the list's own query, so the list costs NO extra query
    (the staff lists' query budgets are frozen at 6; a prefetch would cost a seventh)."""
    ReviewerGift = apps.get_model('courses', 'ReviewerGift')
    one = Concat(Cast('programme_id', CharField()), Value(_FIELD), 'programme__code', Value(_FIELD),
                 'programme__name_en', output_field=TextField())
    packed = (ReviewerGift.objects.filter(partner_admin=OuterRef('pk')).order_by()
              .values('partner_admin').annotate(p=_Joined(one, Value(_ROW))).values('p'))
    return {PACKED: Subquery(packed, output_field=TextField())}


def _unpacked(text):
    rows = (part.split(_FIELD, 2) for part in (text or '').split(_ROW) if part)
    return sorted(({'id': int(pk), 'code': code, 'name': name or code} for pk, code, name in rows),
                  key=lambda g: g['code'])


def gifts_of(admin):
    """The gifts ``admin`` covers, ordered by code; ``[]`` = every gift. One query (a single
    person); a LIST reads the packed annotation through `gifts_payload` instead."""
    cache = getattr(admin, '_prefetched_objects_cache', {})
    rows = cache['gift_rows'] if 'gift_rows' in cache else admin.gift_rows.select_related('programme')
    return sorted((row.programme for row in rows), key=lambda p: p.code)


def gifts_payload(admin):
    """What the screens are SERVED: ``[{id, code, name}]`` by code, ``[]`` = every gift. Read from
    the `gift_annotation` when the list carries it (no query), else one query."""
    if PACKED in admin.__dict__:
        return _unpacked(admin.__dict__[PACKED])
    return [{'id': p.id, 'code': p.code, 'name': p.name_en or p.code} for p in gifts_of(admin)]


def unchosen_rows():
    """The staff rows who REVIEW and have no gift rows — for `staff_gift_report` (D5). READ-ONLY.

    Who reviews is the assignable list's own rule (`team_holding(('review',))`, as in
    `AdminAssignableAdminsView`): the reviewer role, plus any team member given `review`. Before,
    this read `role='reviewer'` only and missed an admin who holds `review` (A1.3 review).

    No rows reads as "every gift" — the owner's default — but for rows from before TD-501 nobody is
    known to have chosen it. The owner decides each row. A super is never listed: global by design."""
    from . import staff_permissions
    from .models import PartnerAdmin
    return (PartnerAdmin.objects
            .filter(staff_permissions.team_holding(('review',)))
            .filter(gift_rows__isnull=True)
            .exclude(role='super')
            .select_related('owning_organisation')
            .order_by('owning_organisation__code', 'id'))
