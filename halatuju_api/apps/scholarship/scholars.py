"""The officer's Scholars list and maintenance file — the READS (student maintenance Sprint 2).

Roadmap `docs/plans/2026-10-29-student-maintenance-roadmap.md`; design of record: the owner-approved
canvas (2026-10-29). The views in `views_admin/scholars.py` fence and scope; this module only shapes
what the fenced queryset holds, so nothing here can widen what an officer reaches.

WHO IS LISTED. `maintenance_scope.in_maintenance_q()` — the ONE predicate (awarded with a live wallet,
active, maintenance); `?closed=1` lists the closed students who still have a file
(`maintenance_scope.has_file_q()` minus the in-maintenance ones). Nothing else decides it.

⚠ WHAT IS DELIBERATELY NOT HERE YET, so nothing is invented:
  * STANDING — Sprint 4 derives performing / underperforming / failing / not submitted from the
    organisation's settings. Until then a row says only whether ANY result exists
    (`no_result_yet` / `has_result`) and never judges a CGPA.
  * MENTOR (Sprint 7), LETTERS (Sprint 6), SPENDING (Sprint 5) — served as null / [] / absent.
  * A signed-PDF link (Sprint 5) — the contract summary says only whether an agreement exists and
    its derived status.
"""
from decimal import Decimal

import re

from django.db.models import Count, F, OuterRef, Q, Subquery

from apps.courses.search import _digits_expr

from . import card_display, maintenance_scope
from .models import (
    BursaryAgreement, Disbursement, ScholarshipApplication, SemesterResult, StudentActivity,
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
    return Subquery(SemesterResult.objects.filter(application=OuterRef('pk'))
                    .order_by('-created_at', '-id').values(field)[:1])


def base_queryset(*, closed=False):
    """The population, before the fence (the VIEW applies it — `_org_scoped`)."""
    if closed:
        q = maintenance_scope.has_file_q() & ~maintenance_scope.in_maintenance_q()
    else:
        q = maintenance_scope.in_maintenance_q()
    # org-fence: the population only — every caller is `views_admin/scholars.py`, which fences it
    # with `_org_scoped` (+ `assigned_to` for a reviewer) before a row is read.
    return ScholarshipApplication.objects.filter(q)


def annotate(qs):
    """The per-row facts a list needs, as subqueries on ONE query (no per-row read)."""
    return (qs.select_related('profile', 'programme')
            .annotate(latest_cgpa=_latest('cgpa'), latest_semester=_latest('semester'),
                      latest_result_at=_latest('created_at'),
                      last_activity_at=Subquery(
                          StudentActivity.objects.filter(application=OuterRef('pk'))
                          .order_by('-created_at', '-id').values('created_at')[:1])))


def filter_rows(qs, *, substate='', on_hold=False, search=''):
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


def summary(qs):
    """The four tiles, counted over the SCOPED population in one query."""
    row = qs.aggregate(
        in_programme=Count('id'),
        on_hold=Count('id', filter=Q(maintenance_substate='on_hold')),
        probation=Count('id', filter=Q(maintenance_substate='probation')),
        ready_to_close=Count('id', filter=Q(maintenance_substate='ready_to_close')))
    return {k: row[k] or 0 for k in ('in_programme', 'on_hold', 'probation', 'ready_to_close')}


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
    """List rows for one PAGE of annotated applications (catalogue names in two queries)."""
    names = card_display.catalogue_course_names(
        (a.chosen_programme or {}).get('course_id') if isinstance(a.chosen_programme, dict) else ''
        for a in apps)
    out = []
    for app in apps:
        latest = _result(app.latest_cgpa, app.latest_semester, app.latest_result_at)
        out.append({
            **_scholar_identity(app, names),
            'latest_result': latest,
            # Sprint 4 replaces this with the real standing; until then it never judges a CGPA.
            'standing': 'has_result' if latest else 'no_result_yet',
            'mentor': None,
            'last_activity_at': app.last_activity_at,
        })
    return out


def file_payload(app):
    """The file header + Overview cards for ONE application the view has fenced."""
    from .payments import _remaining, paid_to_date
    latest = (SemesterResult.objects.filter(application=app)
              .order_by('-created_at', '-id').values('cgpa', 'semester', 'created_at').first())
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
        'standing': 'has_result' if result else 'no_result_yet',
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
        'letters': [],
        'last_activity_at': last_activity,
    }


def activity_dict(row):
    return {
        'id': row.id, 'kind': row.kind, 'event': row.event, 'body': row.body,
        'meta': row.meta or {}, 'actor_email': row.actor_email, 'internal': row.internal,
        'created_at': row.created_at,
    }
