"""The officer's Scholars list, maintenance file and activity log (student maintenance Sprint 2).

Part of the `views_admin` package; every name below is re-exported from `views_admin/__init__.py`.
The reads are shaped in `apps/scholarship/scholars.py`; THIS module is the fence.

⚠ WHO SEES IT — THE APPLICATIONS RULE, NOT A NEW ONE (docs/decisions.md, 2026-10-29, maintenance S2).
A scholar file is a view of an application the officer can already open in the cockpit, so it reads
exactly as much as `_b40_scope` allows there:
  * `see_all` (super, org_admin, admin, qc presets) — every scholar in their own organisation
    (a super: every organisation, narrowed to a gift when they have no organisation — TD-334);
  * `review` without `see_all` (reviewer) — ONLY the scholars assigned to them;
  * neither (finance, partner) — 403. Finance never sees a name beside case data (the Spending rule).
Across organisations the answer is 404, never 403. Writing an activity entry needs the same read
right on that file (a note is a record, not a decision); placing a hold stays on the cockpit door
(`AdminMaintenanceSubstateView`, payments rights). Nothing here is ever served to a student.
"""
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response

from .. import activity, scholars
from ..maintenance_scope import has_file, is_in_maintenance
from ..models import SemesterResult, StudentActivity
from .base import _AdminBase


def _int(value, default, lo, hi):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


class _ScholarsBase(_AdminBase):
    """The fence for every Scholars endpoint."""

    def _scholars_admin(self, request):
        """`(admin, scope, error)` — scope 'all' or 'assigned' (never 'none')."""
        admin = self.get_admin(request)
        if not admin:
            return None, None, self._deny()
        scope = self._b40_scope(admin)
        if scope == 'none':
            return None, None, self._deny_role()
        return admin, scope, None

    def _fenced(self, qs, admin, scope):
        qs = self._org_scoped(qs, admin)
        return qs.filter(assigned_to=admin) if scope == 'assigned' else qs

    def _file_for(self, request, pk):
        """`(app, admin, error)`: the application IFF it has a file AND this admin may read it.
        Cross-org, unknown and no-file are all 404 — the same answer, so none confirms a record."""
        admin, scope, err = self._scholars_admin(request)
        if err:
            return None, None, err
        app = self._get_application(pk)
        if app is None or not has_file(app) or not self._org_allows(admin, app):
            return None, None, Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        if scope == 'assigned' and app.assigned_to_id != admin.id:
            return None, None, self._deny_role()
        return app, admin, None


class AdminScholarListView(_ScholarsBase):
    """GET admin/scholarship/scholars/ — `?programme=` `?closed=1` `?substate=` `?on_hold=1`
    `?search=` `?sort=` `?page=` `?page_size=`. Returns `{summary, count, page, page_size, results}`.
    `summary` counts the scoped in-maintenance population (closed or not, it is what the tiles say)."""

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
        qs = scholars.filter_rows(scholars.annotate(scoped(closed)), substate=q.get('substate', ''),
                                  on_hold=q.get('on_hold') == '1', search=q.get('search', ''),
                                  below=below if wanted == 'below_minimum' else None,
                                  overdue=overdue if wanted == 'results_overdue' else None)
        sort = q.get('sort') or scholars.DEFAULT_SORT
        qs = qs.order_by(*scholars.SORTS.get(sort, scholars.SORTS['name']))
        count = qs.count()
        size = _int(q.get('page_size'), 25, 1, scholars.MAX_PAGE_SIZE)
        page = _int(q.get('page'), 1, 1, max(1, -(-count // size)))
        page_rows = list(qs[(page - 1) * size:page * size])
        summary = scholars.summary(scholars.annotate(scoped(None)), below, overdue)
        return Response({'summary': summary, 'count': count, 'page': page, 'page_size': size,
                         'results': scholars.rows(page_rows)})


class AdminScholarFileView(_ScholarsBase):
    """GET admin/scholarship/scholars/<pk>/ — the file header + Overview cards."""

    def get(self, request, pk):
        app, admin, err = self._file_for(request, pk)
        if err:
            return err
        from .. import payments
        return Response({**scholars.file_payload(app), 'controls': scholars.controls(
            app, can_write=self._can_review_app(admin, app), can_hold=payments.may_prepare(admin))})


class AdminScholarResultsView(_ScholarsBase):
    """GET admin/scholarship/scholars/<pk>/results/ — every result, newest first, each with its
    review and its slip (signed URL). S4a."""

    def get(self, request, pk):
        app, _admin, err = self._file_for(request, pk)
        if err:
            return err
        from .. import results_review
        return Response({'results': [scholars.result_dict(r)
                                     for r in results_review.results_for_file(app)]})


class AdminScholarMoneyView(_ScholarsBase):
    """GET admin/scholarship/scholars/<pk>/money/ — the file's Money tab (S5a): award, paid,
    remaining and her last releases by the Payments rules (`scholar_money`), all as strings, plus
    her spending this term by category ONLY for a viewer holding the `spending` permission (the
    key is absent otherwise). Read-only, so a closed file reads the same."""

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
    is a WRITE on the case — `_can_review_app` (super, the organisation's qc holders, or the
    assignee), not merely a reader of the file. 409 `file_closed` on a closed file."""

    def post(self, request, pk, result_id):
        app, admin, err = self._file_for(request, pk)
        if err:
            return err
        if not self._can_review_app(admin, app):
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

    GET — the timeline, newest first, `?page=` `?page_size=` (≤ 100): `{count, page, results}`.
    POST `{kind: note|call|meeting|email, body, internal}` — a manual entry by this officer
    (`activity.add_entry`). 400 `{code}` on bad_kind / empty_body / too_long; 409 `file_closed` on
    a closed file — closed is READ-ONLY (owner ruling 2026-10-29), for staff as for the student."""

    def get(self, request, pk):
        app, _admin, err = self._file_for(request, pk)
        if err:
            return err
        qs = StudentActivity.objects.filter(application=app).order_by('-created_at', '-id')
        count = qs.count()
        size = _int(request.query_params.get('page_size'), 50, 1, scholars.MAX_PAGE_SIZE)
        page = _int(request.query_params.get('page'), 1, 1, max(1, -(-count // size)))
        return Response({'count': count, 'page': page, 'page_size': size,
                         'results': [scholars.activity_dict(r)
                                     for r in qs[(page - 1) * size:page * size]]})

    def post(self, request, pk):
        app, admin, err = self._file_for(request, pk)
        if err:
            return err
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
        return Response(scholars.activity_dict(row), status=status.HTTP_201_CREATED)
