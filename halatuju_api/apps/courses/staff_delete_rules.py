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

The sole-org-admin guard (`is_sole_org_admin`: the only active org admin, or the last one holding
Organisation admin powers, S2 / M4a review) is the one `AdminRevokeView`, `AdminDeleteView` and Archive
enforce, with the organisation's org admins locked first (`lock_org_admins_of`). Only a super can
reach an org admin at all (`_staff_target_manageable`), so a table read by anybody else never pays
its query.

Lives in its own module because `views_admin.py` is on the oversize ledger with no room to grow.
"""
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


def powers_holder_ids(organisation_id, lock=False):
    """S2 / M4a review: THE ONE COUNTING RULE for Organisation admin powers' last holder, as a set of
    ids: the organisation's active org admins for whom `staff_permissions.holds_org_admin_powers` is
    true. The editor's untick (`staff_permissions_admin._refuse_last_powers`), Archive, Revoke and Delete
    (`is_sole_org_admin`) and the tables (`sole_org_admin_ids`) all count through it. ``lock=True``
    (inside a transaction) counts with the rows locked, in id order."""
    from .staff_permissions import holds_org_admin_powers
    rows = _org_admins(owning_organisation_id=organisation_id)
    if lock:
        rows = rows.select_for_update().order_by('id')
    return {a.id for a in rows if holds_org_admin_powers(a)}


def _last_holder(target, holders):
    """Whether ``target`` holds the powers and nobody else in ``holders`` does (zero left, never a cap)."""
    return target.id in holders and not holders - {target.id}


def is_sole_org_admin(target, lock=False):
    """Whether removing ``target`` would leave their organisation with no administrator: they are its
    ONLY active org admin (matrix 2026-07-15; N4), or the last active one holding Organisation admin
    powers (S2 / M4a review: an org admin whose powers a super unticked does not count). Archive, Revoke
    and Delete all refuse it. ``lock=True`` (inside a transaction: those doors) counts with the rows
    locked."""
    if not _live_org_admin(target):
        return False
    others = _org_admins(owning_organisation_id=target.owning_organisation_id).exclude(id=target.id)
    if lock:
        if not list(others.select_for_update().order_by('id').values_list('id', flat=True)):
            return True
    elif not others.exists():
        return True
    return _last_holder(target, powers_holder_ids(target.owning_organisation_id, lock=lock))


def sole_org_admin_ids(caller, targets):
    """The ids among ``targets`` that `is_sole_org_admin` would refuse: ONE query for a whole table (the
    organisations' active org admins, counted and then read for the powers), and none at all unless the
    caller is a super with an active org admin listed."""
    from .staff_permissions import holds_org_admin_powers
    live = [t for t in targets if _live_org_admin(t)]
    if caller is None or not caller.is_super or not live:
        return set()
    rows, holders = {}, set()
    for a in _org_admins(owning_organisation_id__in={t.owning_organisation_id for t in live}):
        rows.setdefault(a.owning_organisation_id, set()).add(a.id)
        if holds_org_admin_powers(a):
            holders.add(a.id)
    return {t.id for t in live
            if rows.get(t.owning_organisation_id, set()) <= {t.id}
            or _last_holder(t, holders & rows.get(t.owning_organisation_id, set()))}


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
    never = alone or target.pk == caller.pk or not _deletable_now(caller, target, work={})   # M1a: never yourself
    return {'work': work, 'deletable': not never and not work, 'delete_never': never,
            'revocable': bool(manageable and not target.is_super and target.pk != caller.pk and not alone)}
