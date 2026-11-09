"""Sprint T2 review (N2-N4): whether a staff row may be Revoked or Deleted, as every Team screen draws it.

Three answers, served on every Team table and person page by ONE function (`delete_fields`), so a screen
never offers a button the server refuses:

  * `deletable`    - Delete is live: the caller may delete them AND they have no work on record.
  * `delete_never` - no Delete is drawn at all, because nobody can delete this row here whatever work it
                     has: a super, a source/partner/mentor login, a role outside `_DELETABLE_ROLES`, a row
                     outside the caller's remit, or the SOLE active org admin of their organisation (N4).
                     A row that is neither shows a greyed Delete with its work as the reason.
  * `revocable`    - the Revoke / Restore toggle may be drawn (N3): the caller manages them, they are not a
                     super, not the caller, and not the sole active org admin (Revoke refuses that too).

The sole-org-admin guard (`is_sole_org_admin`) is the one `AdminRevokeView` and `AdminDeleteView` both
enforce, with the organisation's org admins locked first (`lock_org_admins_of`). Only a super can
reach an org admin at all (`_staff_target_manageable`), so a table read by anybody else never pays
its query.

Lives in its own module because `views_admin.py` is on the oversize ledger with no room to grow.
"""
from django.db.models import Count

from .models import PartnerAdmin


def _live_org_admin(target):
    return target.role == 'org_admin' and target.is_active and target.owning_organisation_id is not None


def _org_admins(**where):
    """The active org admins matching ``where`` (the one place this module reads the role)."""
    return PartnerAdmin.objects.filter(role='org_admin', is_active=True, **where)


def lock_org_admins_of(admin_id):
    """Inside the Revoke / Delete transaction, BEFORE the target row is locked: when ``admin_id`` is a
    live org admin, lock every active org admin of that organisation, in id order (T2 review, race).

    Two supers each removing one of an organisation's two org admins at once would otherwise both
    count "one other left" and leave none. Taking the whole set first, always in the same order,
    makes the second wait for the first and then count afresh; taking it AFTER each locked its own
    target would deadlock the pair instead. A peek (no lock) finds the organisation; a non-org-admin
    target locks nothing more. `is_sole_org_admin(..., lock=True)` locks again on the count itself,
    so a target that BECAME an org admin after the peek is still covered."""
    organisation_id = (_org_admins(id=admin_id).exclude(owning_organisation_id=None)
                       .values_list('owning_organisation_id', flat=True).first())
    if organisation_id:
        list(_org_admins(owning_organisation_id=organisation_id).select_for_update().order_by('id')
             .values_list('id', flat=True))


def is_sole_org_admin(target, lock=False):
    """Whether ``target`` is the ONLY active org admin of their organisation (one query). Revoking or
    deleting them would strand the organisation with no administrator (matrix 2026-07-15; N4).
    ``lock=True`` (inside a transaction: the Revoke and Delete doors) counts with the rows locked."""
    if not _live_org_admin(target):
        return False
    others = _org_admins(owning_organisation_id=target.owning_organisation_id).exclude(id=target.id)
    if lock:
        return not list(others.select_for_update().order_by('id').values_list('id', flat=True))
    return not others.exists()


def sole_org_admin_ids(caller, targets):
    """The ids among ``targets`` that are their organisation's sole active org admin: ONE grouped query
    for a whole table, and none at all unless the caller is a super with an active org admin listed."""
    live = [t for t in targets if _live_org_admin(t)]
    if caller is None or not caller.is_super or not live:
        return set()
    counts = (PartnerAdmin.objects
              .filter(role='org_admin', is_active=True,
                      owning_organisation_id__in={t.owning_organisation_id for t in live})
              .values('owning_organisation_id').annotate(n=Count('id')).order_by())
    alone = {r['owning_organisation_id'] for r in counts if r['n'] == 1}
    return {t.id for t in live if t.owning_organisation_id in alone}


def delete_fields(caller, target, work=None, sole=None):
    """`work`, `deletable`, `delete_never` and `revocable` for one row. ``work`` is the row's entry of
    `staff_footprint.footprints` (a table) or None to read this one person's; ``sole`` is the table's
    `sole_org_admin_ids`, or None to ask for this one person."""
    from .views_admin import _deletable_now, _staff_target_manageable, scholarship_staff
    if work is None:
        staff_footprint, _ = scholarship_staff()
        work = staff_footprint.footprint(target)
    manageable = _staff_target_manageable(caller, target)
    alone = manageable and (target.id in sole if sole is not None else is_sole_org_admin(target))
    # `_deletable_now` with NO work answers the rule alone: may this caller ever delete this row?
    never = alone or not _deletable_now(caller, target, work={})
    return {'work': work, 'deletable': not never and not work, 'delete_never': never,
            'revocable': bool(manageable and not target.is_super and target.pk != caller.pk and not alone)}
