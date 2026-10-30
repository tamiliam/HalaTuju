"""The officer's Scholars list and maintenance file — the READS (student maintenance Sprint 2).

Roadmap `docs/plans/2026-10-29-student-maintenance-roadmap.md`; design of record: the owner-approved
canvas (2026-10-29). The views in `views_admin/scholars.py` fence and scope; this module only shapes
what the fenced queryset holds, so nothing here can widen what an officer reaches.

WHO IS LISTED. `maintenance_scope.in_maintenance_q()` — the ONE predicate (awarded with a live wallet,
active, maintenance); `?closed=1` lists the closed students who still have a file
(`maintenance_scope.has_file_q()` minus the in-maintenance ones). Nothing else decides it.

STANDING (S4a) is `standing.py`'s, from the latest ACCEPTED result and the organisation's
thresholds; a result awaiting review never moves it (it reads `awaiting_review`).

⚠ WHAT IS DELIBERATELY NOT HERE YET, so nothing is invented:
  * MENTOR (Sprint 7), LETTERS (Sprint 6), SPENDING (Sprint 5) — served as null / [] / absent.
  * A signed-PDF link (Sprint 5) — the contract summary says only whether an agreement exists and
    its derived status.
"""
from decimal import Decimal

import re

from django.db.models import Count, Exists, F, OuterRef, Q, Subquery

from apps.courses.search import _digits_expr

from . import card_display, maintenance_scope, standing
from .results_review import PENDING, accepted, latest_accepted
from .models import (
    BursaryAgreement, Disbursement, ResultsExpectation, ScholarshipApplication, SemesterResult,
    StudentActivity,
)

#: The sub-states an officer may filter on (the model's choices).
SUBSTATES = ('on_track', 'probation', 'on_hold', 'ready_to_close')

#: `?sort=` keys → order_by. Every key ends on `id` so a page is stable. ⚠ A student with no
#: result / no activity sorts LAST in BOTH directions (`nulls_last`): Postgres puts NULLs first on
#: DESC, so "highest CGPA first" would otherwise open on every student who has none.
SORTS = {
    'name': ('profile__name', 'id'), '-name': ('-profile__name', '-id'),
    'cgpa': (F('latest_cgpa').asc(nulls_last=True), 'id'),
    '-cgpa': (F('latest_cgpa').desc(nulls_last=True), '-id'),
    'activity': (F('last_activity_at').asc(nulls_last=True), 'id'),
    '-activity': (F('last_activity_at').desc(nulls_last=True), '-id'),
    'due': (F('next_due').asc(nulls_last=True), 'id'),
    '-due': (F('next_due').desc(nulls_last=True), '-id'),
    'id': ('id',), '-id': ('-id',),
}
DEFAULT_SORT = 'name'
MAX_PAGE_SIZE = 100
_ZERO = Decimal('0')
_CENTS = Decimal('0.01')


def _two(value):
    """A money or CGPA figure as a 2dp string (a subquery / aggregate can hand back a float or a
    bare integer on some backends), or None."""
    return None if value is None else str(Decimal(str(value)).quantize(_CENTS))


def _latest(field):
    """The latest ACCEPTED result's `field` (S4a: only an accepted result counts)."""
    return Subquery(accepted(SemesterResult.objects.filter(application=OuterRef('pk')))
                    .order_by('-created_at', '-id').values(field)[:1])


def base_queryset(*, closed=False):
    """The population, before the fence (the VIEW applies it — `_org_scoped`). `closed=None` is
    EVERY file (in maintenance and closed) — the summary counts both in one query."""
    if closed is None:
        q = maintenance_scope.has_file_q()
    elif closed:
        q = maintenance_scope.has_file_q() & ~maintenance_scope.in_maintenance_q()
    else:
        q = maintenance_scope.in_maintenance_q()
    # org-fence: the population only — every caller is `views_admin/scholars.py`, which fences it
    # with `_org_scoped` (+ `assigned_to` for a reviewer) before a row is read.
    return ScholarshipApplication.objects.filter(q)


def annotate(qs):
    """The per-row facts a list needs, as subqueries on ONE query (no per-row read)."""
    return (qs.select_related('profile', 'programme', 'owning_organisation__configuration')
            .annotate(latest_cgpa=_latest('cgpa'), latest_semester=_latest('semester'),
                      latest_result_at=_latest('created_at'), latest_graduated=_latest('graduated'),
                      pending_review=Exists(SemesterResult.objects.filter(
                          application=OuterRef('pk'), review_status=PENDING)),
                      last_activity_at=Subquery(
                          StudentActivity.objects.filter(application=OuterRef('pk'))
                          .order_by('-created_at', '-id').values('created_at')[:1]),
                      # S4b: her earliest OPEN result term — its due date (past = late) and start.
                      next_due=Subquery(_open_term(OuterRef('pk')).values('due_on')[:1]),
                      next_due_starts=Subquery(_open_term(OuterRef('pk')).values('term_starts_on')[:1]))
            # Something she sent THIS term is waiting for the officer: not her lateness (review M3).
            .annotate(pending_for_due=Exists(SemesterResult.objects.filter(
                application=OuterRef('pk'), review_status=PENDING,
                created_at__date__gte=OuterRef('next_due_starts'))),
                      # A graduating result accepted: she has finished, never "not submitted" (review M2).
                      graduated_any=Exists(accepted(SemesterResult.objects.filter(
                          application=OuterRef('pk'), graduated=True)))))


def _open_term(app_ref):
    return (ResultsExpectation.objects.filter(application=app_ref, satisfied_by__isnull=True)
            .order_by('due_on', 'id'))


def overdue_q(custom=None, today=None):
    """S4b: the rows with an open result term past its due date AND THEIR organisation's grace
    (the Results overdue filter and tile), on an ANNOTATED queryset."""
    from datetime import timedelta
    from django.utils import timezone
    from apps.courses import org_config
    today = today or timezone.localdate()
    custom = (custom or custom_lines())['results_overdue_grace_days']
    cond = Q(next_due__lt=today - timedelta(days=org_config.default('results_overdue_grace_days'))) & ~Q(
        owning_organisation_id__in=list(custom))
    for org_id, grace in custom.items():
        cond |= Q(owning_organisation_id=org_id, next_due__lt=today - timedelta(days=grace))
    # ONE rule with the Standing column and the file (`results_expectations.late`, review M2/M4): in
    # maintenance, not finished (no accepted graduating result, not ready to close), and nothing she
    # sent this term waiting for the officer.
    finished = Q(maintenance_substate='ready_to_close') | Q(graduated_any=True)
    return cond & maintenance_scope.in_maintenance_q() & ~finished & Q(pending_for_due=False)


def custom_lines():
    """Every organisation's own minimum CGPA and overdue grace, in ONE query — for `below_minimum_q`
    and `overdue_q` together (the list's query budget)."""
    from apps.courses import org_config
    return org_config.custom_values_many(('maintenance_min_cgpa', 'results_overdue_grace_days'))


def below_minimum_q(custom=None):
    """S4a: the rows whose latest ACCEPTED CGPA is under THEIR organisation's minimum (the
    Underperforming filter and tile — failing included), on an ANNOTATED queryset. Every
    organisation's own minimum comes from `custom_lines()`; the rest follow the default."""
    from decimal import Decimal as _D
    from apps.courses import org_config
    custom = (custom or custom_lines())['maintenance_min_cgpa']
    custom = {o: _D(str(v)) for o, v in custom.items()}
    below = Q(latest_cgpa__isnull=False, latest_graduated=False)
    cond = Q(latest_cgpa__lt=_D(str(org_config.default('maintenance_min_cgpa')))) & ~Q(
        owning_organisation_id__in=list(custom))
    for org_id, minimum in custom.items():
        cond |= Q(owning_organisation_id=org_id, latest_cgpa__lt=minimum)
    return below & cond


def filter_rows(qs, *, substate='', on_hold=False, search='', below=None, overdue=None):
    """`below` (from `below_minimum_q`) narrows to the students under their minimum; `overdue`
    (from `overdue_q`) to those with a result past due and grace (S4b)."""
    if below is not None:
        qs = qs.filter(below)
    if overdue is not None:
        qs = qs.filter(overdue)
    if substate in SUBSTATES:
        qs = qs.filter(maintenance_substate=substate)
    if on_hold:
        qs = qs.filter(maintenance_substate='on_hold')
    text = (search or '').strip()
    if not text:
        return qs
    if text.startswith('#') and text[1:].isdigit():
        return qs.filter(pk=int(text[1:]))      # `#104` is an application number and nothing else
    # The Applications search (`apps.courses.search.apply_people_search`): name / IC / phone / email,
    # IC and phone matched DIGITS-ONLY on both sides, so `000101140001` and a `000101` prefix find
    # `000101-14-0001`. Its own expression is reused rather than the function, because a bare
    # number may ALSO be an application number, and that alternative has to join the same OR.
    cond = (Q(profile__name__icontains=text) | Q(profile__nric__icontains=text)
            | Q(profile__contact_email__icontains=text) | Q(notify_email__icontains=text))
    digits = re.sub(r'\D', '', text)
    if digits:
        qs = qs.annotate(_nric_digits=_digits_expr('profile__nric'),
                         _phone_digits=_digits_expr('profile__contact_phone'))
        cond |= Q(_nric_digits__icontains=digits) | Q(_phone_digits__icontains=digits)
    if text.isdigit():
        cond |= Q(pk=int(text))
    return qs.filter(cond)


SUMMARY_KEYS = ('in_programme', 'on_hold', 'probation', 'ready_to_close', 'closed', 'below_minimum',
                'results_overdue')


def summary(qs, below, overdue):
    """The tiles, counted in ONE query over the scoped files (annotated — `base_queryset(closed=None)`):
    the in-maintenance counts, the closed files, and the students under their minimum (S4a)."""
    live = maintenance_scope.in_maintenance_q()
    row = qs.aggregate(
        in_programme=Count('id', filter=live),
        on_hold=Count('id', filter=live & Q(maintenance_substate='on_hold')),
        probation=Count('id', filter=live & Q(maintenance_substate='probation')),
        ready_to_close=Count('id', filter=live & Q(maintenance_substate='ready_to_close')),
        closed=Count('id', filter=~live),
        below_minimum=Count('id', filter=live & below),
        results_overdue=Count('id', filter=live & overdue))
    return {k: row[k] or 0 for k in SUMMARY_KEYS}


def _gift(app):
    p = getattr(app, 'programme', None)
    return {'code': p.code, 'name': p.name_en} if p is not None else None


def _result(cgpa, semester, at):
    if at is None:
        return None
    return {'cgpa': _two(cgpa), 'semester': semester or '', 'at': at}


def _scholar_identity(app, names=None):
    from .maintenance import is_on_hold
    prof = getattr(app, 'profile', None)
    return {
        'id': app.id,
        'name': getattr(prof, 'name', '') or '',
        'gift': _gift(app),
        'course': card_display.resolve_course(app, names=names),
        'institution': card_display.resolve_institution(app),
        'status': app.status,
        'maintenance_substate': app.maintenance_substate,
        'is_on_hold': is_on_hold(app),
    }


def rows(apps):
    """List rows for one PAGE of annotated applications (catalogue names in two queries; one
    thresholds read per organisation on the page)."""
    names = card_display.catalogue_course_names(
        (a.chosen_programme or {}).get('course_id') if isinstance(a.chosen_programme, dict) else ''
        for a in apps)
    from . import results_expectations
    lines = {}
    out = []
    for app in apps:
        if app.owning_organisation_id not in lines:
            org = app.owning_organisation
            lines[app.owning_organisation_id] = (*standing.thresholds(org),
                                                 results_expectations.settings_for(org)[2])
        minimum, failing, grace = lines[app.owning_organisation_id]
        live = maintenance_scope.is_in_maintenance(app)
        latest = _result(app.latest_cgpa, app.latest_semester, app.latest_result_at)
        out.append({
            **_scholar_identity(app, names),
            'latest_result': latest,
            'pending_review': bool(app.pending_review),
            'standing': standing.standing_for(
                app.latest_cgpa, bool(app.latest_graduated), has_accepted=latest is not None,
                has_pending=bool(app.pending_review), minimum=minimum, failing=failing,
                overdue=(live and app.maintenance_substate != 'ready_to_close' and not app.graduated_any
                         and not app.pending_for_due and results_expectations.is_overdue(app.next_due, grace))),
            # A closed file has no next due date (review M2).
            'next_due': app.next_due if live else None,
            'mentor': None,
            'last_activity_at': app.last_activity_at,
        })
    return out


def file_payload(app):
    """The file header + Overview cards for ONE application the view has fenced."""
    from . import results_expectations
    from .payments import _remaining, paid_to_date
    latest = latest_accepted(app)
    latest = {'cgpa': latest.cgpa, 'semester': latest.semester, 'created_at': latest.created_at} if latest else None
    paid = paid_to_date(app)
    award = app.award_amount
    last = (Disbursement.objects.filter(application=app, status__in=Disbursement.PAID)
            .order_by('-released_at', '-id').values('amount', 'released_at').first())
    agreement = BursaryAgreement.objects.filter(application=app).first()
    last_activity = (StudentActivity.objects.filter(application=app)
                     .order_by('-created_at', '-id').values_list('created_at', flat=True).first())
    result = _result(latest['cgpa'], latest['semester'], latest['created_at']) if latest else None
    return {
        **_scholar_identity(app),
        'in_maintenance': maintenance_scope.is_in_maintenance(app),
        'has_file': maintenance_scope.has_file(app),
        'closure_reason': app.closure_reason,
        'awarded_at': app.awarded_at,
        'vircle_activated_at': app.vircle_activated_at,
        'closed_at': app.closed_at,
        'latest_result': result,
        'standing': standing.standing_of(app),
        'next_due': results_expectations.next_due(app),
        'thresholds': dict(zip(('minimum', 'failing'),
                               (_two(v) for v in standing.thresholds(app.owning_organisation)))),
        'money': {
            'award_amount': _two(award),
            'paid_to_date': _two(paid),
            # The Payments funding summary's own rule (`payments._remaining`): no award reads 0
            # remaining, never a blank, so the two screens can never disagree about one student.
            'remaining': _two(_remaining(app)),
            'last_payment': ({'amount': _two(last['amount']), 'at': last['released_at']}
                             if last else None),
        },
        'contract': {'exists': agreement is not None,
                     'status': agreement.status if agreement is not None else None},
        'mentor': None,
        'letters': _letters_summary(app),   # S6b
        'last_activity_at': last_activity,
    }


def controls(app, *, can_write, can_hold):
    """What the file's header may OFFER this officer (maintenance S3 — the sub-state and Close moved
    here from the cockpit). An offer, never the gate: `AdminMaintenanceSubstateView` and
    `AdminCloseApplicationView` judge every request again.

      * `can_set_substate` — may write this case (`_can_review_app`) and the case takes a sub-state
        (`maintenance.can_set_substate`);
      * `can_hold` — may move it to or from `on_hold`: payments rights (`payments.may_prepare`, S1 M1);
      * `close_reasons` — the closure table for this status (`closure.reasons_for`), empty when the
        close would be refused;
      * `close_refusal` — `sponsorship_open` for an AWARDED case still holding the sponsor's offer or
        paid money: `close_application` refuses it and no admin door releases it (TD-366). Said, not
        silently hidden (S1 review L4).
    """
    from . import closure
    from .maintenance import can_set_substate
    post_award = app.status in closure.POST_AWARD_STATUSES
    refusal = ''
    if post_award and app.status not in closure.FUNDED_STATUSES and closure.has_live_money(app):
        refusal = 'sponsorship_open'
    return {
        # S4a: accepting / querying a result is a write on the case, and only while she is in it.
        'can_review_results': bool(can_write and maintenance_scope.is_in_maintenance(app)),
        'can_set_substate': bool(can_write and can_set_substate(app)),
        'can_hold': bool(can_hold),
        'close_reasons': (list(closure.reasons_for(app.status))
                          if can_write and post_award and not refusal else []),
        'close_refusal': refusal,
    }


def result_dict(row):
    """One result for the officer's Results tab — the slip by signed URL (org-fenced by the key)."""
    slip = row.results_slip
    url = None
    if slip is not None:
        from .storage import create_signed_download_url, resolve_org_for_path
        path_org = resolve_org_for_path(slip.storage_path)
        if path_org is None or path_org == row.application.owning_organisation_id:
            url = create_signed_download_url(slip.storage_path)
    return {
        'id': row.id, 'semester': row.semester, 'cgpa': _two(row.cgpa), 'graduated': row.graduated,
        'note': row.note, 'created_at': row.created_at,
        'review_status': row.review_status, 'review_note': row.review_note,
        'reviewed_by': row.reviewed_by, 'reviewed_at': row.reviewed_at,
        'slip': ({'url': url, 'filename': slip.original_filename, 'content_type': slip.content_type}
                 if slip is not None else None),
    }


def activity_dict(row):
    return {
        'id': row.id, 'kind': row.kind, 'event': row.event, 'body': row.body,
        'meta': row.meta or {}, 'actor_email': row.actor_email, 'internal': row.internal,
        'created_at': row.created_at,
    }


def _letters_summary(app):
    from .letters import summary
    return summary(app)
