"""TD-501 / SEC-17 (audit fix A1.3, 2026-11-06) — a reviewer invite must NAME its gift.

Until now a reviewer was invited with no gift at all, and a NULL `PartnerAdmin.programme` reads as
"every gift" (`me.programmes_of`). So every new reviewer silently covered every gift of their
organisation, and nobody had chosen that.

Owner ruling "b": the invite of a GIFT-SCOPED role asks for an explicit choice —

- ``gift_scope='one'`` with a ``programme_id`` of the owning organisation's gifts, or
- ``gift_scope='every'`` (and no ``programme_id``).

No choice is a 400 ``gift_required``. A gift outside the owning organisation is a 404, never a 403
(a 403 would confirm another tenant's gift exists — the `AdminReviewerProgrammeView` rule).

⚠ ROLES OTHER THAN THE REVIEWER ARE UNCHANGED: admins, QC, finance, org admins and partners are
never asked, and the source and mentor invites never come here.

⚠ "EVERY GIFT" IS STILL STORED AS NULL. The model cannot yet tell an explicit "every gift" from
"never chosen" (rows from before this change, or a gift deleted under `SET_NULL`). Telling them
apart needs a model field, which is the owner's call (TD-501). Until then the INVITE is what
refuses "not chosen"; `staff_gift_report` lists the NULL rows for the owner to decide (D5).

⚠ THE GIFT IS NOT A READ FENCE: what a reviewer can READ is fenced by the organisation and by
assignment (`views_admin.base._scoped_application`). Since 2026-11-06 (owner ruling) it BLOCKS
ASSIGNMENT: `assign_reviewer` refuses `gift_mismatch` (`services.assignment.gift_allows`).
"""
from django.apps import apps
from rest_framework.response import Response

#: Roles whose invite must name a gift. Only the reviewer: the gift decides which cases a
#: reviewer is offered. An admin, QC or finance person is not offered cases by gift.
GIFT_SCOPED_ROLES = frozenset({'reviewer'})

ONE = 'one'
EVERY = 'every'
CHOICES = (ONE, EVERY)


def _gift_refusal(code, status, message):
    return Response({'error': message, 'code': code}, status=status)


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


def for_invite(data, role, owning_org):
    """``(programme | None, refusal Response | None)`` for a staff invite of ``role``.

    A role outside `GIFT_SCOPED_ROLES` → ``(None, None)``: nothing is asked and nothing changes.
    A gift-scoped role → the explicit choice above, or a refusal the view returns as it stands.
    """
    if role not in GIFT_SCOPED_ROLES:
        return None, None
    scope = data.get('gift_scope')
    scope = scope.strip().lower() if isinstance(scope, str) else ''
    if scope not in CHOICES:
        return None, _gift_refusal('gift_required', 400,
                             'Choose one gift or every gift for this reviewer.')
    raw = data.get('programme_id')
    given = raw not in (None, '')
    if scope == EVERY:
        if given:
            return None, _gift_refusal('gift_conflict', 400,
                                 'Every gift was chosen, so no single gift can be named.')
        return None, None
    programme_id = _as_id(raw)
    if programme_id is None:
        return None, _gift_refusal('gift_required', 400, 'Choose the gift this reviewer covers.')
    if owning_org is None:
        return None, _gift_refusal('not_found', 404, 'Gift not found.')
    Programme = apps.get_model('scholarship', 'Programme')
    programme = Programme.objects.filter(pk=programme_id, organisation=owning_org).first()
    if programme is None:
        return None, _gift_refusal('not_found', 404, 'Gift not found.')
    return programme, None


def unchosen_rows():
    """The staff rows who REVIEW and whose gift is NULL — for `staff_gift_report` (D5). READ-ONLY.

    Who reviews is the assignable list's own rule (`team_holding(('review',))`, as in
    `AdminAssignableAdminsView`): the reviewer role, plus any team member given `review`. Before,
    this read `role='reviewer'` only and missed an admin who holds `review` (A1.3 review).

    NULL reads as "every gift" today, but for these rows nobody is known to have chosen it (they
    predate TD-501, or their gift was deleted under `SET_NULL`). The owner decides each row.
    A super is never listed: a super is global by design."""
    from . import staff_permissions
    from .models import PartnerAdmin
    return (PartnerAdmin.objects
            .filter(staff_permissions.team_holding(('review',)))
            .filter(programme__isnull=True, is_super_admin=False)
            .exclude(role='super')
            .select_related('owning_organisation')
            .order_by('owning_organisation__code', 'id'))
