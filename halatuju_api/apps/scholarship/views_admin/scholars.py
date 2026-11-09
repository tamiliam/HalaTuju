"""The officer's Scholars list, maintenance file and activity log (student maintenance Sprint 2).

Part of the `views_admin` package; every name below is re-exported from `views_admin/__init__.py`.
The reads are shaped in `apps/scholarship/scholars.py`; THIS module is the fence.

⚠ WHO SEES IT — ITS OWN KEY, `scholars` (sprint S1, owner 2026-11-09; `base.scholars_scope`). Until S1
it read by the Applications rule (`_b40_scope`; decisions.md 2026-10-29, superseded):
  * `scholars` (super, org_admin, the admin preset, or a saved set naming it) — every scholar in their
    own organisation (a super: every organisation, narrowed to a gift when they have no organisation
    — TD-334). The Growth, Surveys and Mentoring tabs still ask their own read key too (TD-498);
  * a mentor (a mentor login, or staff mentoring now) — ONLY their current students, read-only (S1b);
  * anyone else — 403: `review`, `qc` and `see_all` (Applications) alone open nothing here.
Across organisations the answer is 404, never 403.
WRITES on a scholar file (accepting or querying a result, letters, activity notes — `_may_write_file`)
are for `scholars` holders across their own organisation, no longer only the assignee, and no longer
`qc`; a closed file is read-only (409 `file_closed`). Placing a hold stays on the cockpit door
(`AdminMaintenanceSubstateView`, payments rights), as do the sub-state and Close (`_can_review_app`,
shared with Applications). Nothing here is ever served to a student.
"""
from django.db.models import Q
from rest_framework import status
from rest_framework.permissions import SAFE_METHODS
from rest_framework.response import Response

from apps.courses.search import people_search_term

from .. import activity, activity_people, mentor_desk, mentoring, scholars
from ..maintenance_scope import has_file, is_in_maintenance
from ..models import SemesterResult, StudentActivity
from .base import _AdminBase, scholars_scope


def _staff_names(emails):
    """``{email (lower): name}`` for the staff who wrote ``emails`` — ONE query (S1 ruling A)."""
    from apps.courses.models import PartnerAdmin
    emails = list({e for e in emails if e})
    if not emails:
        return {}
    return {e.lower(): n or '' for e, n in PartnerAdmin.objects.filter(email__in=emails)
            .values_list('email', 'name')}


def _int(value, default, lo, hi):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


class _ScholarsBase(_AdminBase):
    """The fence for every Scholars endpoint. ⚠ A MENTOR LOGIN reaches a view only on the methods it
    lists in `mentor_methods` (`get_admin`): the READ views list `('get',)` (S1-h), the writes nothing."""

    def _scholars_admin(self, request):
        """`(admin, scope, error)` — scope 'all' or 'mentor' (never 'none': 403)."""
        admin = self.get_admin(request)
        if not admin:
            return None, None, self._deny()
        scope = scholars_scope(admin)
        if scope == 'none':
            return None, None, self._deny_role()
        return admin, scope, None

    def _fenced(self, qs, admin, scope):
        qs = self._org_scoped(qs, admin)
        if scope == 'mentor':     # S1-h: ONLY their current students (`mentor_desk.current_assignments`)
            qs = qs.filter(pk__in=[a.application_id for a in mentor_desk.current_assignments(admin)])
        return qs

    @staticmethod
    def _as_mentor(admin):
        """True when this viewer reads the file AS A MENTOR (S1-h): no `scholars` key, mentoring now.
        Read-only, and the tabs' own read keys (TD-498) are not asked of them: the owner gave a mentor
        every tab of their own current student's file."""
        return scholars_scope(admin) == 'mentor'

    def _file_for(self, request, pk):
        """`(app, admin, error)`: the application IFF it has a file AND this admin may read it.
        Cross-org, unknown and no-file are all 404 — the same answer, so none confirms a record."""
        admin, scope, err = self._scholars_admin(request)
        if err:
            return None, None, err
        if scope == 'mentor':
            # S1-h: another mentor's student, an ended assignment, another organisation's file, their
            # own application and an unknown id are ONE 404; then every write on their student is 403.
            if mentor_desk.assignment_for(admin, pk) is None:
                return None, None, Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
            if request.method not in SAFE_METHODS:
                return None, None, self._deny_role()
        app = self._get_application(pk)
        if app is None or not has_file(app) or not self._org_allows(admin, app):
            return None, None, Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        return app, admin, None

    def _may_write_file(self, admin, app):
        """The scholar-file WRITE (S1-d): accept / query a result, issue a letter, add an activity note.
        A `scholars` holder (a super passes every key) on a file of their own organisation — no longer
        only the assignee, and no longer `qc`. `_can_review_app` is the Applications rule and stays there."""
        return scholars_scope(admin) == 'all' and self._org_allows(admin, app)


class AdminScholarListView(_ScholarsBase):
    """GET admin/scholarship/scholars/ — `?programme=` `?closed=1` `?substate=` `?on_hold=1`
    `?search=` `?sort=` `?page=` `?page_size=` `?mentoring=no_mentor|asked_for_help` (S7b)
    `|mentor_concerned` (S7c).
    Returns `{summary, count, page, page_size, results}`.
    `summary` counts the scoped in-maintenance population (closed or not, it is what the tiles say).
    A mentor (S1-h) lists only their current students."""
    mentor_methods = ('get',)

    def get(self, request):
        admin, scope, err = self._scholars_admin(request)
        if err:
            return err
        programme, err = self._gift_narrowing(request, admin)
        err = err or self._gift_required_for_orgless_super(admin, programme)
        if err:
            return err
        q = request.query_params

        def scoped(closed):
            qs = self._fenced(scholars.base_queryset(closed=closed), admin, scope)
            if programme is None:
                return qs
            # ⚠ THE APPLICATIONS GIFT RULE (views_admin/applications.py): reach through the cohort
            # too. `programme` is denormalised at first save and SET ONCE, so a round moved to
            # another gift leaves its scholars on the OLD one; the column alone would hide them.
            return qs.filter(Q(programme=programme) | Q(cohort__programme=programme))

        closed = q.get('closed') == '1'
        lines = scholars.custom_lines()             # ONE read: every organisation's minimum + grace
        below, overdue = scholars.below_minimum_q(lines), scholars.overdue_q(lines)
        wanted = q.get('standing')
        # S7b: the mentor column, the two Mentoring pills and their counts are for the roles that
        # see the Mentoring tab (`mentoring.may_read_mentoring`, TD-498: a read); for the rest the keys are absent.
        sees_mentors = scope == 'mentor' or mentoring.may_read_mentoring(admin)
        staff = scope != 'mentor'                   # a mentor's "last activity" skips Staff-only rows
        qs = scholars.filter_rows(scholars.annotate(scoped(closed), with_internal=staff),
                                  substate=q.get('substate', ''),
                                  on_hold=q.get('on_hold') == '1',
                                  search=people_search_term(request, 'search'),  # TD-421
                                  below=below if wanted == 'below_minimum' else None,
                                  overdue=overdue if wanted == 'results_overdue' else None,
                                  mentoring=q.get('mentoring', '') if sees_mentors else '')
        sort = q.get('sort') or scholars.DEFAULT_SORT
        qs = qs.order_by(*scholars.SORTS.get(sort, scholars.SORTS['name']))
        count = qs.count()
        size = _int(q.get('page_size'), 25, 1, scholars.MAX_PAGE_SIZE)
        page = _int(q.get('page'), 1, 1, max(1, -(-count // size)))
        page_rows = list(qs[(page - 1) * size:page * size])
        summary = scholars.summary(scholars.annotate(scoped(None), with_internal=staff), below, overdue)
        results = scholars.rows(page_rows)
        if not sees_mentors:
            summary = {k: v for k, v in summary.items() if k not in scholars.MENTORING_KEYS}
            results = [{k: v for k, v in r.items() if k not in scholars.MENTORING_ROW_KEYS} for r in results]
        return Response({'summary': summary, 'count': count, 'page': page, 'page_size': size,
                         'results': results})


class AdminScholarFileView(_ScholarsBase):
    """GET admin/scholarship/scholars/<pk>/ — the file header + Overview cards. A mentor (S1-h) reads it
    with every control off: the file is read-only to them, and `mentor_view` says so (the screen draws
    every tab and no write from it, rather than working the scope out for itself)."""
    mentor_methods = ('get',)

    def get(self, request, pk):
        app, admin, err = self._file_for(request, pk)
        if err:
            return err
        from .. import payments
        as_mentor = self._as_mentor(admin)
        body = scholars.file_payload(app, with_internal=not as_mentor)
        if not (as_mentor or mentoring.may_read_mentoring(admin)):  # S7b: the Mentoring tab's readers' only
            body = {k: v for k, v in body.items() if k not in ('mentor', 'asked_for_help')}
        writes = not as_mentor
        return Response({**body, 'mentor_view': as_mentor, 'controls': scholars.controls(
            app, can_write=writes and self._can_review_app(admin, app),
            can_hold=writes and payments.may_prepare(admin),
            can_review_results=writes and self._may_write_file(admin, app))})


class AdminScholarResultsView(_ScholarsBase):
    """GET admin/scholarship/scholars/<pk>/results/ — every result, newest first, each with its
    review and its slip (signed URL). S4a."""
    mentor_methods = ('get',)

    def get(self, request, pk):
        app, admin, err = self._file_for(request, pk)
        if err:
            return err
        from .. import results_review
        rows = list(results_review.results_for_file(app))
        # S1 ruling A: a mentor sees the reviewer's NAME, never the address (one query).
        names = _staff_names([r.reviewed_by for r in rows]) if self._as_mentor(admin) else None
        return Response({'results': [scholars.result_dict(r, names=names) for r in rows]})


class AdminScholarMoneyView(_ScholarsBase):
    """GET admin/scholarship/scholars/<pk>/money/ — the file's Money tab (S5a): award, paid,
    remaining and her last releases by the Payments rules (`scholar_money`), all as strings, plus
    her spending this term by category ONLY for a viewer holding the `spending` permission (the
    key is absent otherwise). Read-only, so a closed file reads the same."""
    mentor_methods = ('get',)

    def get(self, request, pk):
        app, admin, err = self._file_for(request, pk)
        if err:
            return err
        from .. import scholar_money
        return Response(scholar_money.money_payload(app, may_see_spending=admin.has_perm('spending')))


class AdminScholarContractView(_ScholarsBase):
    """GET admin/scholarship/scholars/<pk>/contract/ — the file's Contract tab (S5a): the platform-
    signed (countersigned) agreement — dates, parties without IC numbers — or `{exists: false}`.
    `?link=1` also mints a 300-second signed PDF link; the tab asks only when someone opens the PDF.
    Not gated on the signing feature flag. Read-only."""
    mentor_methods = ('get',)

    def get(self, request, pk):
        app, _admin, err = self._file_for(request, pk)
        if err:
            return err
        from .. import scholar_money
        return Response(scholar_money.contract_payload(
            app, with_link=request.query_params.get('link') == '1'))


class AdminScholarResultReviewView(_ScholarsBase):
    """POST admin/scholarship/scholars/<pk>/results/<result_id>/review/ {decision: accepted|queried,
    note} — accept or query a result (a query needs a note the student sees). S4a.

    ⚠ WHO: reviewing a result decides what counts for standing and for every sponsor reader, so it
    is a WRITE on the file — `_may_write_file` (S1-d: a `scholars` holder of the file's organisation;
    until S1 `_can_review_app`: super, qc holders or the assignee). 409 `file_closed` on a closed file."""

    def post(self, request, pk, result_id):
        app, admin, err = self._file_for(request, pk)
        if err:
            return err
        if not self._may_write_file(admin, app):
            return self._deny_role()
        if not is_in_maintenance(app):
            return Response({'error': 'file_closed', 'code': 'file_closed'},
                            status=status.HTTP_409_CONFLICT)
        result = SemesterResult.objects.filter(pk=result_id, application=app).first()
        if result is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        from .. import results_review
        data = request.data if isinstance(request.data, dict) else {}
        note = data.get('note')
        try:
            results_review.review(result, decision=data.get('decision'),
                                  note=note if isinstance(note, str) else '',
                                  by_email=admin.email or '')
        except results_review.ResultsError as e:
            # `slip_required` is a state of the RESULT (no slip yet), not a bad request — 409.
            code = status.HTTP_409_CONFLICT if e.code == 'slip_required' else status.HTTP_400_BAD_REQUEST
            return Response({'error': e.code, 'code': e.code}, status=code)
        result.refresh_from_db()
        return Response(scholars.result_dict(result))


class AdminScholarActivityView(_ScholarsBase):
    """GET/POST admin/scholarship/scholars/<pk>/activity/.

    GET — the timeline, newest first, `?page=` `?page_size=` (≤ 100) `?show=all|notes|system`
    (sprint P1: filtered ON THE SERVER, so "Show older" pages the filter): `{count, page, page_size,
    counts: {all, notes, system}, results}`; `?counts=0` leaves `counts` out (the side panel). Each
    row carries `actor` (`activity_people`); `actor_email` only for an unknown writer.
    POST `{kind: note|call|meeting|email, body, internal}` — a manual entry by this officer
    (`activity.add_entry`). 400 `{code}` on bad_kind / empty_body / too_long; 409 `file_closed` on
    a closed file — closed is READ-ONLY (owner ruling 2026-10-29), for staff as for the student.

    A mentor (S1-h) reads the log WITHOUT the "Staff only" rows (`internal`) — they are not staff — and
    the counts leave them out too; the P1 actor rule (`activity_people`) serves them no known email.
    A mentor never writes here (a mentor login is refused by `get_admin`, staff who mentor by `_file_for`)."""
    mentor_methods = ('get',)

    def get(self, request, pk):
        app, admin, err = self._file_for(request, pk)
        if err:
            return err
        qs = StudentActivity.objects.filter(application=app).order_by('-created_at', '-id')
        as_mentor = self._as_mentor(admin)
        if as_mentor:
            qs = qs.exclude(internal=True)
        may_mentoring = as_mentor or mentoring.may_read_mentoring(admin)     # TD-498 (A1.10a): a read
        if not may_mentoring:
            # S7b review fix 2: the mentoring lines name the mentor; a role outside the Mentoring
            # tab (a reviewer, QC) never receives them — under EVERY filter, the counts included.
            qs = qs.exclude(event__in=mentoring.EVENTS)
        show = request.query_params.get('show') or activity_people.SHOW_ALL
        if show not in (activity_people.SHOW_NOTES, activity_people.SHOW_SYSTEM):
            show = activity_people.SHOW_ALL
        # `?counts=0` (the side panel, which has no filter): the plain count of the rows shown instead
        # of the grouped per-filter count, and no `counts` in the reply.
        want_counts = request.query_params.get('counts') != '0'
        counts = activity_people.counts(qs) if want_counts else None
        qs = activity_people.filtered(qs, show)
        count = counts[show] if want_counts else qs.count()
        size = _int(request.query_params.get('page_size'), 50, 1, scholars.MAX_PAGE_SIZE)
        page = _int(request.query_params.get('page'), 1, 1, max(1, -(-count // size)))
        rows = list(qs[(page - 1) * size:page * size])
        actors = activity_people.Actors(rows, app, may_see_mentors=may_mentoring)
        body = {'count': count, 'page': page, 'page_size': size,
                'results': [scholars.activity_dict(r, actors, names_only=as_mentor) for r in rows]}
        if want_counts:
            body['counts'] = counts
        return Response(body)

    def post(self, request, pk):
        app, admin, err = self._file_for(request, pk)
        if err:
            return err
        if not self._may_write_file(admin, app):     # S1-d: a write on the file
            return self._deny_role()
        if not is_in_maintenance(app):
            return Response({'error': 'file_closed', 'code': 'file_closed'},
                            status=status.HTTP_409_CONFLICT)
        data = request.data if isinstance(request.data, dict) else {}
        try:
            body = data.get('body')
            row = activity.add_entry(app, data.get('kind'), body if isinstance(body, str) else '',
                                     actor_email=admin.email or '',
                                     internal=data.get('internal') is True)
        except activity.ActivityError as e:
            return Response({'error': e.code, 'code': e.code}, status=status.HTTP_400_BAD_REQUEST)
        actors = activity_people.Actors([row], app, may_see_mentors=mentoring.may_read_mentoring(admin))
        return Response(scholars.activity_dict(row, actors), status=status.HTTP_201_CREATED)
