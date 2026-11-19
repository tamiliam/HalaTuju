"""People → a person → "What <name> can do": the rules behind the staff-permission editor
(request #39 Sprint 4, 2026-10-21). The roadmap is `docs/plans/2026-10-19-staff-permissions-roadmap.md`.

The view (`views_admin/staff_permissions.py`) is the door — who may knock, the 404 fence, the AUDIT
line. This module decides what a change may be, what it would do, and writes it with its history.

⚠ WHOSE SET MAY CHANGE. A TEAM member's (`admin`, `finance`, `qc`, `reviewer`), and since M3c (D1) an
organisation admin's — by a SUPER only; never a super's, a referral partner's — and never your OWN.
The view's `_staff_target_manageable` already stops an org_admin reaching anybody else; a super passes
that fence for everyone, so `plan_change` refuses the rest here, for both callers (`may_edit`).

⚠ M3c (A12): YOU GIVE ONLY WHAT YOU HOLD. Somebody who is not a super may add a key of the organisation
admin's set (`ORG_ADMIN_SET`) only when it opens for them too (`not_held`). `review` and
`award_withdraw_request` are outside that set and stay exempt, as before (decisions.md "M3c"). S2 / M4a
(owner Q3, 19 Nov): the Payments switches count too — Organisation admin powers counts as holding View,
Prepare and Approve for GIVING, never Check, so only a super gives Check (`MONEY_GIVE`).

⚠ S2 / M4a (owner Q1): ORGANISATION ADMIN POWERS (`organisation.admin`) is stored on org admin rows only
and changed by a super only (`may_edit`); never on a team row (`org_admin_powers_team`), never taken from
an organisation's last holder (`last_org_admin_powers`).

⚠ A CHANGE MAY NOT STRAND A CASE (the S3 as-built notes). Somebody holding in-play cases keeps a key
that lets them work it (`services.works_cases`, TD-613's rule: in Reviewers and holding `review` or
`see_all`, which `qc` brings; sprint LABELS review rounds). Read under the target's ROW LOCK, and `assign_reviewer`
re-reads its target under the same lock, so an assignment racing a removal is serialised (TD-382
class): whichever commits second sees the first.

⚠ THE MONEY CONSEQUENCES ARE LIVE RULES, NOT STORED STATE (S2). Giving the first signed-in member
`payments_approve` turns the run's fallback OFF; taking it from the last one turns it back ON (since
S2 / M4a the fallback is anybody with Organisation admin powers or Approve who has not signed the run); the same for `payments_check` and the optional check step. The dry run names them so the
screen says it BEFORE the click, from the same holders the payment chain reads.

⚠ STORED AS THE PRESET WHEN IT IS THE PRESET. A set equal to the role's preset is saved as NULL, so
"custom" stays derivable (`permissions IS NOT NULL`) and a Change role later lands on the new preset.
M2b: v2 page keys are stored in the same list (`asked_set`); NULL only when no v2 key is held.
"""
import copy

from django.db import transaction

#: The dry run's consequence codes, worded by the screen (`admin.permEditor.effect.*`).
CHECK_ON, CHECK_OFF = 'check_on', 'check_off'
FALLBACK_ON, FALLBACK_OFF = 'approver_fallback_on', 'approver_fallback_off'
FILES_ALL = 'files_widened_all'            # gains `see_all`: EVERY student's file
FILES_ASSIGNED = 'files_widened_assigned'  # gains `review` from no file access: the assigned ones
PREPARE_AND_APPROVE = 'prepare_and_approve'
NOT_SIGNED_IN = 'not_signed_in'
#: A1.10a (TD-475): gaining `payments_approve` (`credit_steps.CHECKER_KEY`) also ARMS the wallet-credit
#: check when nobody else active in the organisation holds it. Counted as `credit_check_required`
#: counts: since TD-560 (S2) only holders who have signed in, so a never-signed-in target arms nothing.
CREDIT_CHECK_ON = 'credit_check_on'
#: S2 / M4a: unticking Organisation admin powers takes the powers listed in `ORG_ADMIN_POWERS` away.
ORG_ADMIN_POWERS_OFF = 'org_admin_powers_off'
#: S2 / M4a (owner Q3): the Payments switches Organisation admin powers counts as holding, for GIVING
#: only — never Check (`payments_check`), which only a super gives.
MONEY_GIVE = ('payments.view', 'payments_prepare', 'payments_approve')
MONEY_KEYS = (*MONEY_GIVE, 'payments_check')
#: A1.13b (owner ruling 2026-11-08): one person holding BOTH award-withdrawal seats (they still can
#: never approve their own request — `award_withdrawal_chain` — but the screen says it, as for runs);
#: and taking the approve seat from the last signed-in member who holds it, which leaves every request
#: in the organisation waiting with nobody to decide it.
WITHDRAW_REQUEST_AND_APPROVE = 'withdraw_request_and_approve'
WITHDRAW_LAST_CHECKER = 'withdraw_last_checker'
#: A1.13b review fix: the approve seat also needs case read scope 'all' (`see_all`, or `qc` which brings
#: it — `award_withdrawal_chain.reads_every_case`). Holding the key without it decides nothing, so the
#: screen says so when a change leaves a person in that state.
WITHDRAW_APPROVE_NEEDS_VIEW = 'withdraw_approve_needs_view'
#: M2d D7 (ruling 7): the set SAVED would hold an Engagement page (Announcements, Surveys, Development,
#: Mentoring) without Scholars — those pages name scholars, so they need every scholar's file
#: (`staff_permissions_v2.DEPENDS_ON_V2`). A note, never a refusal: nothing blocks the save. Added by
#: `plan_change` only, so the role and table changes that share `consequences` do not grow a code.
SCHOLARS_NEEDED = 'scholars_needed'
_READS_ALL = frozenset({'see_all', 'qc'})
_WD_REQUEST, _WD_APPROVE = 'award_withdraw_request', 'award_withdraw_approve'


class PermissionChangeRefused(Exception):
    """A refusal the view turns into a response: ``code``, ``status``, a sentence, extra fields."""

    def __init__(self, code, status, message, **extra):
        super().__init__(code)
        self.code, self.status, self.message, self.extra = code, status, message, extra


def editable_keys():
    """The keys the editor shows, in catalogue order: everything but the lead-tier-only ones."""
    from apps.courses import staff_permissions as sp
    return tuple(k for k in sp.CATALOGUE if k not in sp.LEAD_TIER_ONLY)


def asked_set(asked):
    """The asked list as a tuple — today's keys in catalogue order, then the v2 page keys in `V2_KEYS`
    order (M2b D7) — or `PermissionChangeRefused`.

    ⚠ It REFUSES what `staff_permissions.clean` would quietly drop: the editor must never save
    something other than what the person saw.

    ⚠ TEAM TABLES T5b: `qc` IMPLIES `see_all` (`staff_permissions.IMPLIES`) — "QC is self-sufficient".
    `['qc']` is no longer refused (`qc_needs_see_all` is retired); it is answered as `see_all + qc`, the
    set `clean` reads it as, so `after`, the history row and the stored list all say what the person can
    really do. The editor already ticks `see_all` with `qc` (`PermissionEditor`), so the screen agrees.

    M2b: a v2 page key is stored only when `GRANTABLE_V2`; its page's view comes with it
    (`with_implied_views`). Refused: `NEVER_GRANTABLE` (`never_grantable`), `manage_team` (`lead_tier`)
    and a key an old key already means (`alias_permission`: tick the old key).

    M3c (A9): the lead-only page keys are no longer refused here (whether the editor holds them is
    `plan_change`'s A12 question). A view one of them implies that an old key means (`students.edit` /
    `.approve` -> `students.view` = `see_all`; `scholars.approve` -> `scholars.view` = `scholars`) is
    stored through that old key (`VIEW_ALIAS_OLD`), never its v2 spelling."""
    from apps.courses import staff_permissions as sp
    v2 = _v2()
    if not isinstance(asked, (list, tuple)) or not all(isinstance(k, str) for k in asked):
        raise PermissionChangeRefused(
            'bad_request', 400, 'permissions must be a list of permission names.')
    unknown = sorted({k for k in asked if k not in sp.CATALOGUE and k not in v2.CATALOGUE_V2
                      and k != v2.ORG_ADMIN_KEY})
    if unknown:
        raise PermissionChangeRefused(
            'unknown_permission', 400, f'Unknown permission: {", ".join(unknown)}.', unknown=unknown)
    page = [k for k in asked if k in v2.CATALOGUE_V2]
    never = sorted({k for k in page if v2.refusal_reason(k) == 'never_grantable'})
    if never:
        raise PermissionChangeRefused(
            'never_grantable', 400, f'{", ".join(never)} stays with the organisation admin. It can '
            'never be given to a team member.', keys=never)
    if any(k in sp.LEAD_TIER_ONLY for k in asked):
        raise PermissionChangeRefused(
            'lead_tier', 400, 'Managing the team stays with the organisation admin. It cannot be '
            'given to a team member.')
    alias = sorted({k for k in page if v2.refusal_reason(k) == 'alias'})
    if alias:
        raise PermissionChangeRefused(
            'alias_permission', 400, f'{", ".join(alias)} is given by an existing permission. Tick '
            'that one instead.', keys=alias)
    pages = v2.with_implied_views(page)
    held = sp.with_implied([*(k for k in asked if k in sp.CATALOGUE),
                            *(v2.VIEW_ALIAS_OLD[k] for k in pages if k in v2.VIEW_ALIAS_OLD)])
    # S2 / M4a: the Payments View switch is stored by itself only; an old money key already means it.
    view_alone = not any(k.startswith('payments_') for k in held)
    return (*(k for k in sp.CATALOGUE if k in held),
            *(k for k in pages if k not in v2.ALIAS_V2 or (k == v2.PAYMENTS_VIEW and view_alone)),
            *((v2.ORG_ADMIN_KEY,) if v2.ORG_ADMIN_KEY in asked else ()))


def _v2():
    """`staff_permissions_v2`, through this module (the V2Importers allowlist names it, M2b)."""
    from apps.courses import staff_permissions_v2
    return staff_permissions_v2


def stored_page_keys(target):
    """M3c: the v2 page keys ``target``'s row stores, as the editor reads them — an organisation admin's
    through `org_admin_v2` (NULL reads as the full set), anybody else's through `stored_v2`."""
    from apps.courses import staff_permissions as sp
    v2 = _v2()
    return v2.org_admin_v2(target) if sp.is_lead_tier(target) else v2.stored_v2(target)


def held_set(target):
    """What `target` holds as the editor sees it: `resolve` (today's keys), then the stored v2 page keys
    (`stored_page_keys`; M2b, M3c), then Organisation admin powers when held (S2 / M4a)."""
    from apps.courses import staff_permissions as sp
    powers = (_v2().ORG_ADMIN_KEY,) if sp.holds_org_admin_powers(target) else ()
    return (*sp.resolve(target), *stored_page_keys(target), *powers)


def not_held(asked, by):
    """M3c (A12): the keys of ``asked`` that ``by`` may NOT give because they do not open for ``by`` —
    only keys of the organisation admin's set (`ORG_ADMIN_SET`) and, since S2 / M4a (owner Q3), the
    Payments switches (`MONEY_KEYS`) count; a super gives anything. An old key opens through `resolve`, a
    v2 page key through `effective_v2`; Organisation admin powers counts as holding `MONEY_GIVE` (never
    Check). In the order asked."""
    from apps.courses import staff_permissions as sp
    v2 = _v2()
    if by is None or by.is_super:
        return []
    old, page = set(sp.resolve(by)), set(v2.effective_v2(by))
    if sp.holds_org_admin_powers(by):
        old.update(MONEY_GIVE)
    return [k for k in asked if (k in v2.ORG_ADMIN_SET or k in MONEY_KEYS)
            and k not in (old if k in sp.CATALOGUE else page)]


def v2_editor(target, by=None):
    """M2b D9: the v2 page keys by group for the Permissions tab — each ``{key, page, level, grantable,
    reason, held}`` (``held`` = `effective_v2`, what opens today; ``reason`` = why it cannot be ticked)
    — ``v2_held``, the STORED grantable keys the editor's ticks start from, and ``v2_preset``, the role's
    v2 part (`V2_PRESETS`) that "Custom" and Reset weigh it against — served, so the web keeps no copy."""
    from apps.courses import staff_permissions as sp
    v2 = _v2()
    effective = set(v2.effective_v2(target))
    # M3c (A12): a key the viewer cannot give is served with the reason 'not_held'.
    cannot = set(not_held(v2.CATALOGUE_V2, by))

    def reason(k):
        return v2.refusal_reason(k) or ('not_held' if k in cannot else None)
    groups = [{'group': g, 'keys': [
        {'key': k, 'page': row[1], 'level': row[2], 'grantable': reason(k) is None,
         'reason': reason(k), 'held': k in effective}
        for k, row in v2.CATALOGUE_V2.items() if row[0] == g]} for g in v2.GROUPS]
    lead = sp.is_lead_tier(target)
    return {'v2_keys': groups, 'v2_held': list(stored_page_keys(target)),
            # S2 / M4a (owner Q1): an org admin card's Organisation admin powers switch and its plain list.
            'org_admin_powers': ({'held': sp.holds_org_admin_powers(target),
                                  'powers': [code for code, _gates in v2.ORG_ADMIN_POWERS]} if lead else None),
            'v2_preset': list(v2.ORG_ADMIN_V2 if lead else v2.V2_PRESETS.get(target.role, ())),
            # M3c (A12): today's keys the viewer cannot give (the v2 ones carry 'not_held').
            'keys_not_held': not_held(editable_keys(), by),
            # M2d D7: the pages short of Scholars for the person as held, for the tab's note at rest.
            'v2_gaps': scholars_gaps(held_set(target))}


def scholars_gaps(keys):
    """M2d D7: the PAGES (`CATALOGUE_V2` page names, in catalogue order) that `keys` — today's keys and
    v2 page keys, as `held_set` or `asked_set` spell them — open without their ruling-7 dependency.
    Today's keys are read through `ALIASES` (`scholars` IS `scholars.view`), after `IMPLIES`."""
    from apps.courses import staff_permissions as sp
    v2 = _v2()
    old = sp.with_implied(k for k in keys if k in sp.CATALOGUE)
    held = {*v2.through_aliases(old), *(k for k in keys if k in v2.CATALOGUE_V2)}
    gaps = v2.dependency_gaps(held)
    pages = [row[1] for k, row in v2.CATALOGUE_V2.items() if k in gaps]
    return list(dict.fromkeys(pages))


#: The roles People lists on the REVIEWERS tab only (`adminStaff.byCategory`), and the keys that put
#: somebody on that tab (`_ReviewersBase._reviewers`: team members holding `review` or `qc`).
REVIEWERS_TAB_ROLES = ('reviewer', 'qc')
REVIEWERS_TAB_KEYS = ('review', 'qc')


def _refuse_unlisted(target, after):
    """#39 S4 review fix 1: a Reviewer or QC whose set holds neither `review` nor `qc` would be on
    NEITHER People tab — the Admins tab lists by role, the Reviewers tab by those keys — so nobody
    could reach their card, Revoke or Delete again. Refused, so People always lists everyone."""
    if target.role in REVIEWERS_TAB_ROLES and not set(REVIEWERS_TAB_KEYS) & set(after):
        raise PermissionChangeRefused(
            'would_leave_people', 400,
            'A Reviewer or QC must keep "Review assigned students" or "Quality check", or they would '
            'disappear from People. For someone who only needs Spending or to view, invite them as '
            'an Admin instead.')


def may_edit(target, by):
    """Whether ``by`` may change ``target``'s permissions at all (the card's ``editable``, after the view's
    manage fence): a team member's, or since M3c (D1) an organisation admin's when ``by`` is a super —
    never your own, never a super's or a referral partner's, never a revoked person's."""
    from apps.courses import staff_permissions as sp
    if by is not None and target.pk == by.pk:
        return False
    if target.is_super or not target.is_active:
        return False
    return target.role in sp.TEAM_ROLES or (sp.is_lead_tier(target) and by is not None and by.is_super)


def _refuse_target(target, by):
    from apps.courses import staff_permissions as sp
    if by is not None and target.pk == by.pk:
        raise PermissionChangeRefused(
            'own_permissions', 403, 'You cannot change your own permissions.')
    lead_by_super = sp.is_lead_tier(target) and by is not None and by.is_super
    if target.is_super or (target.role not in sp.TEAM_ROLES and not lead_by_super):
        raise PermissionChangeRefused(
            'not_editable', 400, "An organisation admin's, a super's or a referral partner's "
                                 'permissions are fixed and cannot be edited here.')
    if not target.is_active:
        raise PermissionChangeRefused(
            'not_active', 400,
            f"{target.name}'s access is revoked. Restore them before changing what they can do.")


def _case_powers(target, keys):
    """What ``target`` could do with a held case if their row held ``keys``, asked of a copy (nothing
    saved): (WORK it, TD-613's own rule `services.works_cases`; OPEN it, `services.is_review_target`)."""
    from .services import is_review_target, works_cases
    shadow = copy.copy(target)
    shadow.permissions = [k for k in keys if isinstance(k, str)]
    return works_cases(shadow, seated=True), is_review_target(shadow)


def _refuse_stranding(target, before, after):
    """Keep somebody holding in-play cases able to open and work them (see the module docstring).

    Sprint LABELS review rounds: refused when the edit takes away a power the holder has over the case:
    WORKING it (TD-613's rule, `holder_can_review`'s `works_cases`: in Reviewers and a review target) or
    OPENING it (`is_review_target`: `review` or `see_all`). Swapping `review` for `qc` keeps both (`qc`
    seats a Reviewer and brings `see_all`); dropping `review` from an Admin or an organisation admin who
    keeps `see_all` takes the first (they leave Reviewers). An edit to someone who already could not work
    the case (TD-613 offers it to a new holder) is refused only if it would stop them opening it."""
    from . import staff_lifecycle
    was, now = _case_powers(target, before), _case_powers(target, after)
    if not any(b and not a for b, a in zip(was, now)):
        return
    n = staff_lifecycle.open_cases(target)
    if n:
        what = '"Review assigned students"' if 'review' not in after and 'review' in before else '"See all students"'
        raise PermissionChangeRefused(
            'has_open_cases', 409,
            f'{target.name} has {n} open case(s) assigned. Taking away {what} would leave them '
            'unable to work those cases, so hand the cases to someone else first.', open_cases=n)


def _others_hold(target, key):
    """Does an ACTIVE member of the target's organisation OTHER than the target, who has signed in,
    hold ``key``? The payment chain's own reading (`payments_chain._signed_in`)."""
    from apps.courses import staff_permissions as sp
    return any(a.pk != target.pk and a.first_seen_at is not None
               for a in sp.holders(target.owning_organisation_id, key))


def consequences(target, before, after):
    """What saving ``after`` over ``before`` would do beyond the keys themselves — codes, in a stable
    order. Pure apart from reads."""
    from apps.courses import staff_permissions as sp
    out = []
    gained, lost = set(after) - set(before), set(before) - set(after)
    signed_in = target.first_seen_at is not None
    if target.owning_organisation_id is not None:
        for key, on, off in (('payments_check', CHECK_ON, CHECK_OFF),
                             ('payments_approve', FALLBACK_OFF, FALLBACK_ON)):
            if signed_in and key in gained and not _others_hold(target, key):
                out.append(on)
            if signed_in and key in lost and not _others_hold(target, key):
                out.append(off)
        if not signed_in and gained & {'payments_check', 'payments_approve'}:
            out.append(NOT_SIGNED_IN)
        from .credit_steps import CHECKER_KEY
        if signed_in and CHECKER_KEY in gained and not _others_hold(target, CHECKER_KEY):   # TD-560
            out.append(CREDIT_CHECK_ON)
        if signed_in and _WD_APPROVE in lost and not _others_hold(target, _WD_APPROVE):
            out.append(WITHDRAW_LAST_CHECKER)
    # #39 S4 review fix 3: say WHICH files. `see_all` opens every student's (a Reviewer or Finance
    # person given it, or Finance switched to Admin); `review` from no file access opens only the
    # students assigned to them.
    if 'see_all' in gained:
        out.append(FILES_ALL)
    elif 'review' in gained and not ({'review', 'see_all'} & set(before)):
        out.append(FILES_ASSIGNED)
    if {'payments_prepare', 'payments_approve'} <= set(after) and not (
            {'payments_prepare', 'payments_approve'} <= set(before)):
        out.append(PREPARE_AND_APPROVE)
    if {_WD_REQUEST, _WD_APPROVE} <= set(after) and not {_WD_REQUEST, _WD_APPROVE} <= set(before):
        out.append(WITHDRAW_REQUEST_AND_APPROVE)
    if _approve_without_view(after) and not _approve_without_view(before):
        out.append(WITHDRAW_APPROVE_NEEDS_VIEW)
    if _v2().ORG_ADMIN_KEY in lost:
        out.append(ORG_ADMIN_POWERS_OFF)
    return out


def _approve_without_view(keys):
    keys = set(keys)
    return _WD_APPROVE in keys and not (_READS_ALL & keys)


def plan_change(target, asked, *, by=None):
    """What saving ``asked`` for ``target`` would do, or `PermissionChangeRefused`. Read-only.

    Returns ``{'before', 'after', 'added', 'removed', 'stored', 'custom', 'v2_held', 'v2_gaps',
    'consequences'}`` — the
    keys as lists, today's in catalogue order then the v2 page keys (`held_set`); ``stored`` is what
    the column will hold (None = the preset: M2b D7, only when the old part IS the role's preset and
    no v2 key is asked). M2d D7: ``v2_gaps`` are the pages ``after`` holds short of Scholars, and
    ``consequences`` ends with `SCHOLARS_NEEDED` whenever there is one."""
    from apps.courses import staff_permissions as sp
    _refuse_target(target, by)
    lead = sp.is_lead_tier(target)
    if lead and isinstance(asked, (list, tuple)):
        # S2 / M4a: the card serves an organisation admin's `manage_team` (`resolve`) and sends it back; it
        # comes with the powers key (`_lead_after`), so it is not "given" here and never refused `lead_tier`.
        asked = [k for k in asked if k not in sp.LEAD_BY_ROLE]
    after = asked_set(asked)
    before = held_set(target)
    if lead:
        after = _lead_after(after)
        _refuse_last_powers(target, before, after)
    elif _v2().ORG_ADMIN_KEY in after:
        raise PermissionChangeRefused(
            'org_admin_powers_team', 400, 'Organisation admin powers are only for organisation admins. '
            'They cannot be given to a team member.')
    gives = not_held([k for k in after if k not in before], by)
    if gives:
        raise PermissionChangeRefused(
            'not_held', 403, 'You can only give a permission you hold yourself.', keys=gives)
    _refuse_unlisted(target, after)
    _refuse_stranding(target, before, after)
    old = tuple(k for k in after if k in sp.CATALOGUE)
    if lead:     # M3c (D1): always a list; `manage_team` comes with the key (S2), never stored
        stored = [k for k in after if k not in sp.LEAD_BY_ROLE]
    else:
        stored = None if old == sp.preset_for(target.role) and old == after else list(after)
    shadow = copy.copy(target)
    shadow.permissions = stored
    gaps = scholars_gaps(after)
    return {
        'before': list(before), 'after': list(after),
        'added': [k for k in after if k not in before],
        'removed': [k for k in before if k not in after],
        'stored': stored, 'custom': sp.is_custom(shadow), 'v2_held': list(stored_page_keys(shadow)),
        'v2_gaps': gaps, 'org_admin_powers_held': _v2().ORG_ADMIN_KEY in after,
        'consequences': [*consequences(target, before, after), *([SCHOLARS_NEEDED] if gaps else [])],
    }


#: S2 / M4a (TD-629; was M3c's "by role until M4"): the Payments switches an organisation admin's row
#: never stores — their Payments reach comes through Organisation admin powers (`payments_chain`). A
#: stored old money key would still count for the old image's `holders()` (and `resolve` keeps it), so a
#: super's edit may not store one: refused with `money_through_org_admin`.
LEAD_MONEY_OLD = MONEY_KEYS


def _lead_after(after):
    """M3c (D1): an organisation admin's asked set as the row will hold it — `manage_team` put back
    through Organisation admin powers (S2 / M4a: only when the asked set keeps the key; the editor never
    offers `manage_team`), in catalogue order; a Payments switch refused (`LEAD_MONEY_OLD`)."""
    from apps.courses import staff_permissions as sp
    money = [k for k in after if k in LEAD_MONEY_OLD]
    if money:
        raise PermissionChangeRefused(
            'money_through_org_admin', 400, "An organisation admin's payment powers come with "
            'Organisation admin powers. They cannot be changed here.', keys=money)
    powers = sp.LEAD_BY_ROLE if _v2().ORG_ADMIN_KEY in after else ()
    old = sp.with_implied([*(k for k in after if k in sp.CATALOGUE), *powers])
    return (*(k for k in sp.CATALOGUE if k in old), *(k for k in after if k not in sp.CATALOGUE))


def _refuse_last_powers(target, before, after):
    """S2 / M4a: never take Organisation admin powers from the organisation's last active holder (as
    the sole-org-admin guard, `staff_delete_rules`: zero holders only, never a limit on how many).
    `change_permissions` locks the organisation's org admins first (`lock_org_admins_of`)."""
    from apps.courses import staff_permissions as sp
    key = _v2().ORG_ADMIN_KEY
    if key not in before or key in after or target.owning_organisation_id is None:
        return
    if not any(a.pk != target.pk and sp.holds_org_admin_powers(a)
               for a in sp.org_staff(target.owning_organisation_id)):
        raise PermissionChangeRefused(
            'last_org_admin_powers', 409, f'{target.name} is the last person in the organisation with '
            'Organisation admin powers. Give them to another organisation admin first.')


def record(target, before, after, *, by, kind):
    """One history row. Written inside the caller's transaction.

    The ONE writer of a permission change — the editor's PATCH (`change_permissions`, kind 'edit')
    and a role change that reset a custom set (`staff_lifecycle.change_role`, kind 'role_change')
    both come through here — so it is also where ``by`` gets the `permissions_changed` row on their
    own activity list (common profile S3): the subject is the person changed, never a copied name."""
    from . import staff_activity
    from .models import StaffPermissionChange
    row = StaffPermissionChange.objects.create(
        target=target, target_email=target.email or '', organisation_id=target.owning_organisation_id,
        kind=kind, role=target.role, before=list(before), after=list(after),
        changed_by_email=(getattr(by, 'email', '') or ''),
        changed_by_role=('super' if getattr(by, 'is_super', False) else getattr(by, 'role', '')) or '')
    staff_activity.record(by, staff_activity.PERMISSIONS_CHANGED, target, meta=lambda: {
        'kind': kind, 'added': [k for k in after if k not in before],
        'removed': [k for k in before if k not in after]})
    return row


def history_held(target):
    """What ``target`` holds, as a history row records it: `resolve`, then the stored v2 page keys (an
    organisation admin's through `org_admin_v2`, whose NULL reads as the full set; anybody else's through
    `stored_v2`)."""
    return list(held_set(target))


def record_role_reset(old, new, *, by):
    """M3a review (2026-11-14): the Django admin screen changed ``new``'s role and set its `permissions` to
    NULL; ``old`` is the row as it was. One 'role_change' row (as `staff_lifecycle.change_role`), through
    `record`. Registered as `staff_activity_hook.PERMISSION_RECORDER`."""
    return record(new, history_held(old), history_held(new), by=by, kind='role_change')


def change_permissions(target_id, asked, *, by, dry_run=False, with_v2=True, with_powers=True):
    """Plan, and unless ``dry_run`` apply, the change. Returns ``(target, plan)``; ``plan['changed']``
    says whether anything was written.

    M2b: ``with_v2=False`` is a caller that cannot see v2 keys (a browser tab opened before M2b): the
    target's stored v2 keys are KEPT, never stripped by a list that could not show them. S2 / M4a: the
    same for ``with_powers=False`` (a tab opened before S2) and Organisation admin powers.

    The row is LOCKED for the plan and the write (see the module docstring), and the UPDATE carries
    the role and the active flag it planned against, belt and braces."""
    from apps.courses import staff_permissions as sp
    from apps.courses.models import PartnerAdmin
    from apps.courses.public import lock_org_admins_of
    with transaction.atomic():
        if not dry_run:
            lock_org_admins_of(target_id)      # S2: the last-holder count, serialised (org admins first)
        target = PartnerAdmin.objects.select_for_update().filter(pk=target_id, archived_at=None).first()
        if target is None:
            raise PermissionChangeRefused('not_found', 404, 'Admin not found')
        if not with_v2 and isinstance(asked, (list, tuple)):
            asked = [*asked, *stored_page_keys(target)]
        if not with_powers and isinstance(asked, (list, tuple)) and sp.holds_org_admin_powers(target):
            asked = [*asked, _v2().ORG_ADMIN_KEY]
        plan = plan_change(target, asked, by=by)
        # #39 S4 review fix 10: "changed" means what the person can DO changed. A list that resolves
        # to the same keys (a reordered or hand-written one) writes nothing and records nothing.
        plan['changed'] = plan['before'] != plan['after']
        if dry_run or not plan['changed']:
            return target, plan
        PartnerAdmin.objects.filter(pk=target.pk, role=target.role, is_active=True).update(
            permissions=plan['stored'])
        target.permissions = plan['stored']
        record(target, plan['before'], plan['after'], by=by, kind='edit')
    return target, plan
