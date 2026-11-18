"""The "AI prediction" scoreboard — the part that reads the database (sprint LL1).

ONE home for it: the endpoint (`verdict-metrics/`) and the Programme Overview's `ai_prediction`
section both call `metrics(applications, admin)`, so the two can never disagree. The counting itself
is pure and lives in `audit.py`; this module only builds the fenced row set, reads the QC rows and
turns a recorder's email into a person.

⚠ THE FENCE IS THE CALLER'S. `applications` must already be inside the organisation fence (and
narrowed by gift / round); nothing here widens it. The QC rows are reached ONLY through that same
set (`subject_id` in it), never from their own filters.

⚠ `by_reviewer` IS FOR THE LEAD TIER ONLY (a super, or an organisation admin), and the key is ABSENT
for everyone else. It never carries an email: a recorder is shown as the staff record's id and name,
and every email that matches no staff row folds into ONE neutral row (`label_key`).
"""
from __future__ import annotations

from django.db.models.functions import Lower

from apps.courses import public as courses_public

from . import audit
from . import second_look
from .models import StaffActivity

UNMATCHED = 'unmatched_reviewer'   # label key: a recorder with no staff row
UNNAMED = 'unnamed_reviewer'       # label key: a staff row with no name


def may_see_reviewers(admin) -> bool:
    """The lead tier: a super (platform) or an organisation admin. Asked by KEY, not by label:
    `manage_team` is lead-tier-only (held by role, never storable for a team member), so a super and
    an organisation admin hold it and nobody else does."""
    return bool(admin is not None and admin.has_perm('manage_team'))


def _staff_by_email(emails, admin):
    """lowercased email → (id, name) for the staff rows holding any of ``emails`` (one query),
    fenced to the caller's organisation (a super reads every organisation)."""
    if not emails:
        return {}
    staff = courses_public.PartnerAdmin.objects.all()
    if not admin.is_super:
        if admin.owning_organisation_id is None:
            return {}   # no organisation, no staff to name (never `IS NULL`, which would match supers)
        staff = staff.filter(owning_organisation_id=admin.owning_organisation_id)   # org-fence
    rows = (staff.annotate(email_lower=Lower('email'))
            .filter(email_lower__in=emails).order_by('-pk').values_list('email_lower', 'pk', 'name'))
    return {email: (pk, name or '') for email, pk, name in rows}   # oldest row wins (ordered -pk)


def _reviewer_rows(records, admin) -> list:
    """The four counts per recorder, as people — never an email."""
    emails = {(r[4] or '').strip().lower() for r in records} - {''}
    staff = _staff_by_email(emails, admin)
    keyed = []
    for r in records:
        who = staff.get((r[4] or '').strip().lower())
        keyed.append((*r[:4], who[0] if who else UNMATCHED))
    names = dict(staff.values())
    rows = []
    for key, block in audit.decider_counts(keyed).items():
        known = key in names
        rows.append({'id': key if known else None,
                     'name': names.get(key, ''),
                     'label_key': UNMATCHED if not known else (None if names[key] else UNNAMED),
                     **block})
    rows.sort(key=lambda r: (-r['green_failed'], -r['applications'], r['name'], r['id'] or 0))
    return rows


def _qc_block():
    return {'accept': 0, 'reopen': 0, 'reject': 0}


def _qc_finish(block):
    block['total'] = block['accept'] + block['reopen'] + block['reject']
    block['accept_rate'] = round(block['accept'] / block['total'], 4) if block['total'] else 0.0
    block['few'] = block['total'] < audit.FEW_BELOW
    return block


def qc_agreement(applications) -> dict:
    """QC decisions (`qc_decision` rows) on ``applications``, overall and per month (Malaysia time).
    Every row counts, so an application with several QC rows counts each."""
    rows = (StaffActivity.objects
            .filter(verb='qc_decision', subject_type='application',
                    subject_id__in=applications.values('id'))
            .values_list('meta', 'created_at'))
    overall, by_month = _qc_block(), {}
    for meta, created_at in rows:
        decision = (meta or {}).get('decision')
        if decision not in overall:
            continue
        overall[decision] += 1
        month = audit.month_key(created_at)
        by_month.setdefault(month, _qc_block())[decision] += 1
    out = _qc_finish(overall)
    out['by_month'] = {m: _qc_finish(by_month[m]) for m in sorted(by_month)}
    return out


def metrics(applications, admin) -> dict:
    """The whole answer for ``applications`` (a FENCED queryset): `audit.override_metrics`, the QC
    agreement, and — for the lead tier only — `by_reviewer`.

    ONE narrowing, for both callers: a `review`-only holder (`b40_scope` 'assigned') is counted over
    the applications assigned to them, the same rule the Applications list applies. `counted_scope`
    says which ('all' / 'assigned') so the page never works it out. FAILS CLOSED: scope 'none'
    (partner, finance without `review`) counts nothing, reported as 'assigned' (their share is none)."""
    from .views_admin.base import b40_scope   # in the function: the views package imports this module
    scope = b40_scope(admin)
    counted = 'all' if scope == 'all' else 'assigned'
    if scope == 'none':
        applications = applications.none()
    elif counted == 'assigned':
        applications = applications.filter(assigned_to=admin)
    decided = applications.filter(verdict_decided_at__isnull=False)
    records = list(decided.values_list(
        'ai_verdict_snapshot', 'officer_verdict', 'ai_verdict_engine_version',
        'verdict_decided_at', 'verdict_decided_by'))
    out = audit.override_metrics(records)
    out['qc_agreement'] = qc_agreement(decided)
    out['qc_checked'] = second_look.counts(records)   # LL2b: the facts in doubt, checked by the QC
    out['counted_scope'] = counted
    if may_see_reviewers(admin):
        out['by_reviewer'] = _reviewer_rows(records, admin)
    return out
