"""The Staff list's rows (Sprint M1a, 2026-11-10; owner O2, O3, O7, O9). Brief §3.

`GET admin/staff/` (`apps.courses.views_staff_list`) picks the people; this module says, per row, what the
Staff tab draws, in a FIXED number of queries for the whole page, never one per row:

  footprints          `staff_footprint.footprints` (one)
  unfinished work     `staff_work.unfinished_counts` (one per Admins registry entry, open cases, scholars)
  photos              `staff_photo.team_cards` (one, plus one batch signing call), `photo_url` ONLY: no phone
                      and no email on this list (O9, O16)
  sole org admins     `staff_delete_rules.sole_org_admin_ids` (one, and only for a super with one listed)
  mentor records      two (assignments, sessions), only when a mentor login is on the page

Row fields:
  `kind`            `mentor` for a mentor's own login, else `staff` (a staff member who also mentors is staff)
  `groups`          the groups they sit in (`staff_tables.tables`). ⚠ LEAD (M1a): for a SUSPENDED row, the
                    groups a Restore gives back (read as if active), so Suspended never reads "No group"
  `manageable`      the write fence: `_staff_target_manageable` for staff, `mentor_invite.manageable` for a
                    mentor login. A `team_read` reader who is neither a super nor an org admin: false
  `delete_never`    why no Delete is drawn, or None: `self`, `not_manageable` (also a role never deleted),
                    `sole_org_admin`, `has_unfinished_work` (owner O7: anything still waiting on them)
  `delete_outcome`  what Delete does when it may: `erase` (no records) or `archive` (records; the web sends
                    `{"archive": true}`); None when `delete_never` is set
  `revocable`       the Suspend / Restore toggle (staff: `delete_fields`; a mentor login: manageable)
"""
import copy

from apps.courses import staff_tables
from apps.courses import staff_permissions as sp
from apps.courses.staff_delete_rules import delete_fields, sole_org_admin_ids
from apps.courses.staff_fence import _deletable_now, _staff_target_manageable

from . import mentor_invite, staff_footprint, staff_photo, staff_work
from .models import MentorAssignment, MentoringSession

STAFF, MENTOR = 'staff', 'mentor'


def _groups(a):
    """The groups ``a`` sits in; a suspended row is read as if active (the groups a Restore gives back)."""
    if a.is_active:
        return list(staff_tables.tables(a))
    back = copy.copy(a)
    back.is_active = True
    return list(staff_tables.tables(back))


def _mentor_records(admins):
    """The mentor ids on the page with any assignment or session ever (two queries, none without one)."""
    ids = {a.mentor_id for a in admins if a.is_mentor and a.mentor_id is not None}
    if not ids:
        return set()
    return (set(MentorAssignment.objects.filter(mentor_id__in=ids).values_list('mentor_id', flat=True))
            | set(MentoringSession.objects.filter(mentor_id__in=ids).values_list('mentor_id', flat=True)))


def _never(caller, a, rules, work):
    if a.pk == caller.pk:
        return 'self'
    if not rules['may_delete']:
        return 'not_manageable'
    if rules['alone']:
        return 'sole_org_admin'
    if staff_work.any_work(work):
        return 'has_unfinished_work'
    return None


def _staff_rules(caller, a, footprint, sole):
    """`delete_fields` (the Admins table's own answer) plus the fence: one rule for both screens."""
    fields = delete_fields(caller, a, work=footprint, sole=sole)
    manageable = _staff_target_manageable(caller, a)
    return manageable, {'may_delete': _deletable_now(caller, a, work={}), 'alone': manageable and a.pk in sole,
                        'revocable': fields['revocable'], 'records': bool(footprint)}


def _mentor_rules(caller, a, footprint, records):
    """The mentor Delete's rule (`mentor_invite.delete_mentor`): the caller manages the mentor."""
    manageable = mentor_invite.manageable(caller, a.mentor)
    return manageable, {'may_delete': manageable, 'alone': False,
                        'revocable': bool(manageable and a.pk != caller.pk),
                        'records': bool(footprint) or a.mentor_id in records}


def list_rows(caller, admins):
    """The Staff list's row dicts, in ``admins`` order."""
    admins = list(admins)
    works, cards = staff_footprint.footprints(admins), staff_photo.team_cards(admins)
    waiting = staff_work.unfinished_counts(admins)
    sole, records = sole_org_admin_ids(caller, admins), _mentor_records(admins)
    out = []
    for a in admins:
        footprint = works.get(a.pk, {})
        manageable, rules = (_mentor_rules(caller, a, footprint, records) if a.is_mentor
                             else _staff_rules(caller, a, footprint, sole))
        never = _never(caller, a, rules, waiting[a.pk])
        out.append({
            'id': a.pk, 'kind': MENTOR if a.is_mentor else STAFF, 'mentor_id': a.mentor_id, 'name': a.name,
            'photo_url': cards[a.pk]['photo_url'],
            'last_seen_at': a.last_seen_at.isoformat() if a.last_seen_at else None,
            'groups': _groups(a), 'lead': sp.is_lead_tier(a), 'suspended': not a.is_active,
            'manageable': manageable, 'work': waiting[a.pk],
            'deletable': never is None, 'delete_never': never,
            'delete_outcome': None if never else ('archive' if rules['records'] else 'erase'),
            'revocable': rules['revocable'],
        })
    return out
