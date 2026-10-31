"""Payment runs — the admin endpoints, moved verbatim from `views_admin.py` at code health H11.

Part of the `views_admin` package. Every name below is re-exported from
`views_admin/__init__.py`, so `urls.py` and every importer are unchanged.
"""
from rest_framework import status
from rest_framework.response import Response

from ..models import ScholarshipApplication
from ..serializers_admin_gift import gift_ref
from .base import _AdminBase


# ── Payments module (Vircle payment runs) — org-fenced (P2), gated on PERMISSIONS (#39 S2) ────
# Access: `payments.may_read` (any payments_* key, or the organisation admin; super passes) to read,
# `payments.may_prepare` to create / edit / cancel; the run is org-fenced (a cross-org run is 404,
# never 403). Reviewer/qc/partner -> 403. The service (apps.scholarship.payments_chain) owns the
# state machine and `your_step`; these views are thin.
from decimal import Decimal as _Decimal

from ..maintenance import is_on_hold as _is_on_hold


def _payment_item_dict(item):
    app = item.application
    profile = getattr(app, 'profile', None)
    return {
        'id': item.id, 'application_id': app.id,
        'name': getattr(profile, 'name', '') or '',
        'nric': getattr(profile, 'nric', '') or '',
        'vircle_id': item.vircle_id_snapshot or (app.vircle_id or ''),
        # Advisory: has Vircle activated this eWallet? (mirrored from the relay sheet). Shown as a
        # "not yet activated" chip on the run; never blocks — a run item stays payable regardless.
        'activated': app.vircle_activated_at is not None,
        'award_amount': str(item.award_amount_snapshot),
        'paid_to_date': str(item.paid_to_date_snapshot),
        'amount': str(item.amount),
        'credit_applied': str(item.credit_applied),
        'included': item.included,
        'exclude_reason': item.exclude_reason,
        # Maintenance S1 (review L3): the student is on hold NOW — a run that still includes her
        # cannot be approved (`on_hold_in_run`). Shown as a chip on the run.
        'on_hold': _is_on_hold(app),
    }


def _sig(name, email, at):
    return {'name': name, 'email': email, 'at': at} if at else None


def _run_programme(run):
    """The gift a run pays from — ``{id, code, name}`` or None for a pre-P2b run. Shown beside the
    reference so an operator can tell two same-dated runs apart (references disambiguate with a
    `-02` suffix, which says there are two but not which is which).

    ⚠ `code` ADDED 2026-09-28 so the run page can tell the breadcrumb WHICH gift it is showing —
    a run belongs to exactly one gift, and a crumb that could be switched on a run page named a
    gift the page was not showing. `id` and `name` are unchanged; the shape is `gift_ref`'s, the
    one place the console is told a record's gift."""
    return gift_ref(getattr(run, 'programme', None))


def _payment_run_summary(run, admin=None, cache=None):
    from .. import payments
    included = [i for i in run.items.all() if i.included]
    total = sum((i.amount for i in included), _Decimal('0'))
    return {
        'id': run.id, 'reference': run.reference, 'payment_date': run.payment_date,
        'period_month': run.period_month, 'programme': _run_programme(run),
        'status': run.status, 'students': len(included), 'total': str(total),
        'created_at': run.created_at,
        # The step THIS caller may take now ('sign' / 'check' / 'approve') or None — the "Waiting
        # for you" block and the menu badge read it; `payments.sign` asks the same predicate.
        'your_step': payments.next_step_for(run, admin, cache),
    }


def _payment_run_detail(run, admin=None):
    items = list(run.items.select_related('application', 'application__profile').all())
    included = [i for i in items if i.included]
    total = sum((i.amount for i in included), _Decimal('0'))
    # "Skipped this run" -- payable-status + started students who fail D4-4/5/6 (greyed,
    # shown not hidden). Computed live from the eligibility choke-point. A student who IS
    # an item of this run is never "skipped" by it -- without this, a COMPLETED run's own
    # students re-enter as already_paid (they now sit in a completed run for the period).
    from .. import payments
    item_app_ids = {i.application_id for i in items}
    skipped = []
    # Narrowed to the run's own programme (P2b) — a run pays ONE gift, so a student of another
    # gift was never a candidate and must not read as "skipped by this run". A legacy run with
    # no programme passes None and keeps the pre-P2b whole-org behaviour.
    for row in payments.eligible_rows(run.organisation, run.payment_date,
                                      period_month=run.period_month,
                                      programme=run.programme):
        if not row['eligible'] and row['application'].id not in item_app_ids:
            a = row['application']
            p = getattr(a, 'profile', None)
            skipped.append({'application_id': a.id, 'name': getattr(p, 'name', '') or '',
                            'nric': getattr(p, 'nric', '') or '', 'reasons': row['reasons']})
    from django.conf import settings as _settings
    cache = {}     # one holders() read per key for the whole payload
    in_flight = run.status in payments.EDITABLE_STATUSES
    # A check already collected keeps its column; otherwise: would somebody eligible check THIS run?
    check_now = bool(run.finance_signed_at) or (in_flight and payments.check_required_for(run, cache))
    return {
        'id': run.id, 'reference': run.reference, 'payment_date': run.payment_date,
        'period_month': run.period_month, 'programme': _run_programme(run),
        'vircle_email': getattr(_settings, 'VIRCLE_PAYMENTS_EMAIL', ''),
        'status': run.status, 'note': run.note, 'drive_file_url': run.drive_file_url,
        'created_by': run.created_by, 'created_at': run.created_at,
        'admin_signed': _sig(run.admin_signed_name, run.admin_signed_email, run.admin_signed_at),
        'finance_signed': _sig(run.finance_signed_name, run.finance_signed_email, run.finance_signed_at),
        # Whether THIS RUN's chain includes the check, computed server-side and read verbatim by the
        # frontend (review fix 2: per run — somebody eligible for this run could take it). The rule
        # lives in exactly one place (payments.check_required_for); mirroring it in TypeScript would
        # make it a keep-in-sync pair (see docs/lessons.md). The old key stays one release for old
        # bundles; `check_step_required` is its lasting name. Then: the step THIS caller may take;
        # whether the organisation admin approves because nobody else can (the page says why); and
        # whether this caller may edit / cancel.
        'finance_check_required': check_now,
        'check_step_required': check_now,
        'your_step': payments.next_step_for(run, admin, cache),
        'approver_fallback': in_flight and payments.approver_fallback(run, cache),
        'can_prepare': payments.may_prepare(admin),
        'org_admin_signed': _sig(run.org_admin_signed_name, run.org_admin_signed_email, run.org_admin_signed_at),
        'items': [_payment_item_dict(i) for i in items],
        'skipped': skipped,
        'students': len(included), 'total': str(total),
    }


#: The two gates, by name. Since #39 Sprint 2 they read PERMISSIONS (`payments.may_read` /
#: `payments.may_prepare`), not roles; for today's presets they admit exactly the old role sets
#: (read: super / admin / org_admin / finance; write: super / admin / org_admin — the golden table).
_PAYMENTS_READ = 'read'
_PAYMENTS_WRITE = 'write'


class _PaymentsBase(_AdminBase):
    """Shared gate + org-fenced run lookup for the Payments endpoints."""
    def _payments_admin(self, request, gate=_PAYMENTS_READ):
        """Gate a Payments endpoint. READ (the default: list, detail, CSV, funding summary, and
        Sign, whose per-step logic lives in `payments.sign`) admits any `payments_*` holder or the
        organisation admin. The MUTATING endpoints (create a run, edit an item, cancel) pass
        ``gate=_PAYMENTS_WRITE``: Prepare, or the organisation admin — Finance approves a run, it
        never authors or withdraws one. `payments.sign`'s refusal remains the backstop on signing."""
        from .. import payments
        admin = self.get_admin(request)
        if not admin:
            return None, self._deny()
        allowed = payments.may_prepare if gate == _PAYMENTS_WRITE else payments.may_read
        if not allowed(admin):
            return None, self._deny_role()
        return admin, None

    def _run_for(self, admin, pk):
        """The run IFF this admin's organisation owns it (super global); else None -> 404."""
        from ..models import PaymentRun
        run = PaymentRun.objects.filter(pk=pk).select_related('organisation').first()
        if run is None:
            return None
        if admin.is_super:
            return run
        if run.organisation_id != admin.owning_organisation_id:
            return None   # cross-org -> 404, no existence leak
        return run


class AdminPaymentRunListView(_PaymentsBase):
    """GET list (org-fenced, newest first, gift-narrowed) . POST create a draft run.

    ⚠ `?programme=<code>` narrows the list (TD-241, 2026-09-11, when Payments moved to the
    Programme section). It narrows INSIDE the organisation filter and can never widen it —
    `_gift_narrowing` only ever resolves a gift the caller's own organisation owns, and an
    unknown or cross-tenant code is a 404. Omitted means every gift the fence already allowed.
    """
    def get(self, request):
        admin, err = self._payments_admin(request)
        if err:
            return err
        programme, gift_err = self._gift_narrowing(request, admin)
        gift_err = gift_err or self._gift_required_for_orgless_super(admin, programme)  # TD-334
        if gift_err:
            return gift_err
        from ..models import PaymentRun
        qs = PaymentRun.objects.all().prefetch_related('items').order_by('-payment_date', '-id')
        if not admin.is_super:
            qs = qs.filter(organisation_id=admin.owning_organisation_id)
        if programme is not None:
            qs = qs.filter(programme=programme)
        from .. import payments
        cache = {}     # one holders() read per organisation for the whole list
        return Response({'runs': [_payment_run_summary(r, admin, cache) for r in qs],
                         'can_prepare': payments.may_prepare(admin)})

    def post(self, request):
        admin, err = self._payments_admin(request, gate=_PAYMENTS_WRITE)
        if err:
            return err
        org = admin.owning_organisation
        if org is None:
            # The payments module is org-scoped; a caller with no owning organisation
            # (e.g. a bare super) has no org context to create a run in.
            return Response({'error': 'no_org', 'code': 'no_org'}, status=status.HTTP_400_BAD_REQUEST)
        from django.utils.dateparse import parse_date
        pd = parse_date((request.data.get('payment_date') or '').strip())
        if pd is None:
            return Response({'error': 'bad_date', 'code': 'bad_date'}, status=status.HTTP_400_BAD_REQUEST)
        # The MONTH this run pays for (dedup key). Accepts 'YYYY-MM' or a full date; defaults to
        # the payment date's own month when omitted.
        pm_raw = (request.data.get('payment_month') or '').strip()
        if len(pm_raw) == 7:
            pm_raw += '-01'
        pm = parse_date(pm_raw) if pm_raw else pd
        if pm is None:
            return Response({'error': 'bad_month', 'code': 'bad_month'}, status=status.HTTP_400_BAD_REQUEST)
        # The GIFT this run pays from (P2b). Re-fenced on the caller's own organisation, so an
        # admin cannot create a run against another tenant's programme even by id. Omitted +
        # the org runs exactly one programme → that one is used; omitted + more than one → the
        # operator must say which (`programme_required`), never a silent pick.
        # ⚠ BY CODE, FROM THE BREADCRUMB — the page's own gift picker was REMOVED with this
        # change (owner, 2026-09-11). Two controls answering "which gift" is two chances to
        # create a run against a gift you are not looking at, and the money moves either way.
        from ..models import Programme
        org_programmes = Programme.objects.filter(organisation=org, is_active=True)
        code = (request.query_params.get('programme')
                or request.data.get('programme') or '').strip()
        if code:
            programme = org_programmes.filter(code=code).first()
            if programme is None:
                return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        else:
            candidates = list(org_programmes[:2])
            if len(candidates) != 1:
                return Response({'error': 'programme_required', 'code': 'programme_required'},
                                status=status.HTTP_400_BAD_REQUEST)
            programme = candidates[0]
        from .. import payments
        try:
            run = payments.create_run(org, programme, pd, pm,
                                      by_email=getattr(admin, 'email', '') or '', actor=admin)
        except payments.PaymentsError as e:
            body = {'error': e.code, 'code': e.code}
            if e.code == 'too_early':
                # Return the earliest valid pay date so the UI can name it in the message. The
                # rule lives ONLY in payments.earliest_payment_date — deliberately not mirrored
                # in the frontend, which would make it a keep-in-sync pair that drifts.
                body['earliest'] = payments.earliest_payment_date(pm).isoformat()
            return Response(body, status=status.HTTP_400_BAD_REQUEST)
        return Response(_payment_run_detail(run, admin), status=status.HTTP_201_CREATED)


class AdminPaymentRunDetailView(_PaymentsBase):
    """GET a run's detail: items + greyed skipped list + totals + signatures."""
    def get(self, request, pk):
        admin, err = self._payments_admin(request)
        if err:
            return err
        run = self._run_for(admin, pk)
        if run is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(_payment_run_detail(run, admin))


class AdminPaymentRunItemView(_PaymentsBase):
    """PATCH a run item -- toggle include/exclude(+reason), edit amount (draft only)."""
    def patch(self, request, pk, item_id):
        admin, err = self._payments_admin(request, gate=_PAYMENTS_WRITE)
        if err:
            return err
        run = self._run_for(admin, pk)
        if run is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        from ..models import PaymentRunItem
        item = (PaymentRunItem.objects.filter(pk=item_id, run=run)
                .select_related('application', 'run').first())
        if item is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        kwargs = {}
        if 'included' in request.data:
            kwargs['included'] = bool(request.data.get('included'))
        if 'exclude_reason' in request.data:
            kwargs['exclude_reason'] = request.data.get('exclude_reason')
        if 'amount' in request.data:
            kwargs['amount'] = request.data.get('amount')
        from .. import payments
        try:
            payments.set_item(item, **kwargs)
        except payments.PaymentsError as e:
            return Response({'error': e.code, 'code': e.code}, status=status.HTTP_400_BAD_REQUEST)
        run.refresh_from_db()
        return Response(_payment_run_detail(run, admin))


class AdminPaymentRunSignView(_PaymentsBase):
    """POST {typed_name} -- admin (maker) sign, finance (checker) sign when the org's chain
    includes that step, or org_admin (approver) countersign (which completes the run). The
    per-step role logic + name/pairwise-distinctness checks live in payments.sign; this view
    admits every payments role and lets the service refuse the wrong step."""
    def post(self, request, pk):
        admin, err = self._payments_admin(request)
        if err:
            return err
        run = self._run_for(admin, pk)
        if run is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        from .. import payments
        try:
            payments.sign(run, admin, request.data.get('typed_name') or '')
        except payments.PaymentsError as e:
            body = {'error': e.code, 'code': e.code}
            if e.count is not None:
                body['count'] = e.count       # on_hold_in_run: how many held students
            return Response(body, status=status.HTTP_400_BAD_REQUEST)
        run.refresh_from_db()
        return Response(_payment_run_detail(run, admin))


class AdminPaymentRunCancelView(_PaymentsBase):
    """POST -- cancel a run at any pre-completion status. Prepare holders / org_admin only."""
    def post(self, request, pk):
        admin, err = self._payments_admin(request, gate=_PAYMENTS_WRITE)
        if err:
            return err
        run = self._run_for(admin, pk)
        if run is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        from .. import payments
        try:
            payments.cancel(run, by=getattr(admin, 'email', '') or '')
        except payments.PaymentsError as e:
            return Response({'error': e.code, 'code': e.code}, status=status.HTTP_400_BAD_REQUEST)
        run.refresh_from_db()
        return Response(_payment_run_detail(run, admin))


class AdminPaymentRunCsvView(_PaymentsBase):
    """GET the run's payment CSV (any status >= admin_signed) as a download."""
    def get(self, request, pk):
        admin, err = self._payments_admin(request)
        if err:
            return err
        run = self._run_for(admin, pk)
        if run is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        # finance_checked included: the checker must be able to READ the payment file to check
        # it, and a run stays at that status while awaiting countersignature.
        if run.status not in ('admin_signed', 'finance_checked', 'completed'):
            return Response({'error': 'not_ready', 'code': 'not_ready'},
                            status=status.HTTP_400_BAD_REQUEST)
        from django.http import HttpResponse
        from .. import sheets
        resp = HttpResponse(sheets.payment_csv_text(run), content_type='text/csv')
        resp['Content-Disposition'] = f'attachment; filename="{run.reference}.csv"'
        return resp


class AdminPaymentFundingSummaryView(_PaymentsBase):
    """GET /api/v1/admin/payments/funding-summary/ — the org's payable students with award /
    paid / remaining / eWallet, plus org totals for the footer (Sprint 14).

    Rides `_PaymentsBase` with the DEFAULT read gate, so it is visible to super / admin /
    org_admin / finance and refused to reviewer / qc / partner. It lives inside the Payments
    module by design: it is the funding-side view of the same cohort the runs pay, and it is the
    only student data a `finance` admin can reach (`_b40_scope` = 'none').

    Serialised by `FundingSummaryRowSerializer` — an explicit allowlist, NOT a model dump.

    tenancy: org-fenced on `owning_organisation`, the same fence `payments.eligible_rows` uses;
    a super with no org context gets `no_org` (there is no "every tenant's students" reading of
    this page). Classified in test_org_fence.py.
    """
    def get(self, request):
        admin, err = self._payments_admin(request)
        if err:
            return err
        programme, gift_err = self._gift_narrowing(request, admin)
        gift_err = gift_err or self._gift_required_for_orgless_super(admin, programme)  # TD-334
        if gift_err:
            return gift_err
        # ⚠⚠ **A SUPER SEES EVERY ORGANISATION HERE TOO (2026-09-12).** This endpoint returned
        # `400 no_org` to a super, which is the SAME defect the owner reported on the Spending
        # page the day before — found in the live logs rather than reported, because the page
        # around it still renders and only the money summary comes back empty. Fixing one screen
        # and not its neighbour is how a console teaches people that some pages "just do not work
        # for you". `owning_organisation` stays the fence for everybody else.
        org = admin.owning_organisation
        every_org = admin.is_super and org is None
        if org is None and not every_org:
            return Response({'error': 'no_org', 'code': 'no_org'},
                            status=status.HTTP_400_BAD_REQUEST)
        from .. import payments
        from ..serializers_admin import FundingSummaryRowSerializer
        # A caller with no org context was refused with `no_org` above, so the filter below
        # can never be a no-op and this can never run unfenced.
        # org-fence: owning_organisation=org (the fence payments.eligible_rows uses).
        qs = (ScholarshipApplication.objects
              .filter(status__in=payments.PAYABLE_STATUSES)
              .select_related('profile').order_by('id'))
        if not every_org:
            # org-fence: owning_organisation=org (the fence payments.eligible_rows uses).
            qs = qs.filter(owning_organisation=org)
        if programme is not None:
            # ⚠ Narrows INSIDE the org filter above, the same rule `payments.eligible_rows`
            # states: the organisation is the fence, the gift is a restriction within it.
            qs = qs.filter(programme=programme)
        rows = FundingSummaryRowSerializer(qs, many=True).data
        totals = {
            'students': len(rows),
            'award_total': str(sum(_Decimal(r['award_amount']) for r in rows)),
            'paid_total': str(sum(_Decimal(r['paid_to_date']) for r in rows)),
            'remaining_total': str(sum(_Decimal(r['remaining']) for r in rows)),
            # TD-244: funded students holding a wallet Vircle has not reported live.
            'wallet_not_live': sum(1 for r in rows if r['wallet_not_live']),
        }
        return Response({'rows': rows, 'totals': totals})
