"""The "AI prediction" scoreboard — the part that reads the database (sprint LL1).

ONE home for it: the endpoint (`verdict-metrics/`) and the Programme Overview's `ai_prediction`
section both call `metrics(applications, admin)`, so the two can never disagree. The counting itself
is pure and lives in `ai_score.py` (the marks, F4) and `audit.py`; this module only builds the fenced
row set, reads the QC rows and turns a recorder's email into a person.

⚠ F4 (2026-11-23): no AI prediction card for a reviewer; `ai_team` (the "For the AI team" fold) is a
super's only and ABSENT for everyone else. The month trend and the QC "Decision" block are gone.

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

from . import ai_score
from . import audit
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


def _reviewer_rows(records, admin, qc_by_app) -> list:
    """The counts per recorder, as people — never an email. F4: plus `qc_accepted` / `qc_sent_back`,
    the QC decisions (`accept` / `reopen`) on that recorder's applications (``qc_by_app``)."""
    emails = {(r[4] or '').strip().lower() for r in records} - {''}
    staff = _staff_by_email(emails, admin)
    keyed, qc = [], {}
    for r in records:
        who = staff.get((r[4] or '').strip().lower())
        key = who[0] if who else UNMATCHED
        keyed.append((*r[:4], key))
        if r[4]:
            block = qc.setdefault(key, {'qc_accepted': 0, 'qc_sent_back': 0})
            got = qc_by_app.get(r[5], {})
            block['qc_accepted'] += got.get('accept', 0)
            block['qc_sent_back'] += got.get('reopen', 0)
    names = dict(staff.values())
    rows = []
    for key, block in audit.decider_counts(keyed).items():
        known = key in names
        rows.append({'id': key if known else None,
                     'name': names.get(key, ''),
                     'label_key': UNMATCHED if not known else (None if names[key] else UNNAMED),
                     **block, **qc.get(key, {'qc_accepted': 0, 'qc_sent_back': 0})})
    rows.sort(key=lambda r: (-r['green_failed'], -r['applications'], r['name'], r['id'] or 0))
    return rows


def _qc_by_application(decided) -> dict:
    """application id → {decision: count} over the `qc_decision` rows on ``decided`` (fenced set)."""
    out: dict = {}
    rows = (StaffActivity.objects
            .filter(verb='qc_decision', subject_type='application', subject_id__in=decided.values('id'))
            .values_list('subject_id', 'meta'))
    for subject_id, meta in rows:
        decision = (meta or {}).get('decision')
        if decision in ('accept', 'reopen', 'reject'):
            block = out.setdefault(subject_id, {})
            block[decision] = block.get(decision, 0) + 1
    return out


def may_see_ai_team(admin) -> bool:
    """F4: the "For the AI team" fold (doubts often passed, score by engine version) is a SUPER's only.
    Asked of the platform power `is_super` (a super passes every permission key, so no key can tell a
    super from an organisation admin who holds them all); never a role name, never a new choice."""
    return bool(admin is not None and admin.is_super)


def metrics(applications, admin) -> dict:
    """The whole answer for ``applications`` (a FENCED queryset), F4 shape (owner design 2026-11-23):

    * ``applications`` — decided applications counted; ``score`` — `ai_score.score` (the two tiles and
      "By fact"), WITHOUT its per-version part;
    * ``by_reviewer`` — the lead tier only (`may_see_reviewers`);
    * ``ai_team`` — a super only (`may_see_ai_team`): ``doubt_codes`` and ``by_version``.

    ⚠ WHO: the readers of the whole organisation only (`b40_scope` 'all': `see_all`, QC's implied one).
    A reviewer (`review` alone, scope 'assigned') sees NO AI prediction card (owner, F4): the endpoint
    refuses them and the Overview never builds the section; called directly anyway, this FAILS CLOSED
    and counts nothing. Partner / finance (scope 'none') the same.

    ⚠ Only RECORDED decisions count (`verdict_decided_at` set). A reject before interview writes its
    facts on the case without that stamp (`services.pre_interview._assessment_fields`) and on its
    `declined` activity row, which nothing here reads: neither teaches the learning loop."""
    from .views_admin.base import b40_scope   # in the function: the views package imports this module
    if b40_scope(admin) != 'all':
        applications = applications.none()
    decided = applications.filter(verdict_decided_at__isnull=False)
    records = list(decided.values_list(
        'ai_verdict_snapshot', 'officer_verdict', 'ai_verdict_engine_version',
        'verdict_decided_at', 'verdict_decided_by', 'id'))
    marks = ai_score.score(records)
    by_version = marks.pop('by_version')
    out = {'applications': len(records), 'score': marks}
    if may_see_reviewers(admin):
        out['by_reviewer'] = _reviewer_rows(records, admin, _qc_by_application(decided))
    if may_see_ai_team(admin):
        out['ai_team'] = {'doubt_codes': audit.override_metrics(records)['doubt_codes'],
                          'by_version': by_version}
    return out
