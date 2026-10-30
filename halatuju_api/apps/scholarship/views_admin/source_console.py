"""The source console's API — a source user's own (source sign-in S3, 2026-10-30; read-only but for
S4's witness).

Roadmap: `docs/plans/2026-10-30-source-sign-in-roadmap.md` (S3; conflicts C11, C12, C14). Every route
is under `api/v1/admin/source/` and serves a SOURCE USER only:

- `GET / PATCH profile/` — their own name and email; their source's details, which they keep
  themselves once signed in (the other side of the Sources page's 409 `managed_by_source`, S2);
- `GET overview/?p=` — the folded stage counts, the scholar count, the contracts waiting for this
  source's witness and the chase list;
- `GET applications/?p=&q=&stage=` and `GET applications/<id>/`;
- `GET scholars/?p=` and `GET scholars/<id>/`;
- S4, the ONE write: `GET applications/<id>/agreement/` (the full contract, to the witness source
  only) and `POST applications/<id>/witness/` (it records its witness).

⚠ WHO: a source user, and NOBODY ELSE — not a super, not an organisation admin, not a reviewer (403).
A super may not look through a source's eyes: there is no impersonation, and this console is not a
staff screen. A switched-off source (`ReferralSource.is_active=False`) or a revoked user gets 403.

⚠ WHICH ROWS: ONLY `source_access` — `listed_applications_for` for the lists (the applications whose
own answer named this source, the partner emails' set) and `applications_for` for one application
(the listed ones plus the cases this source witnesses by override, which show the contract and
nothing else, C14). Out of scope is a 404, never a 403, so an id cannot confirm a student exists.

⚠ NEVER THE STAFF VIEWS (C11). `AdminApplicationDetailView`'s GET has side effects (it can email the
student) and serves income, NRIC, documents and verdicts; nothing here calls it or its serializer.
The payloads are `apps/scholarship/source_console.py`'s allowlists.

`?p=<gift code>` narrows to one of the source's own gifts (`source_access.programmes_for`; any other
code is a 404). ABSENT, it does not narrow — every gift the source may see, the `_gift_narrowing`
rule: the server never picks a gift for the client.
"""
from rest_framework import status
from rest_framework.response import Response

from halatuju.pagination import FlexiblePageNumberPagination

from .. import source_access, source_console
from .base import _AdminBase
from .sources import DETAIL_FIELDS
from .source_users import _bad_email

#: What the profile PATCH may change. The code, the organisation, `show_in_apply` and `is_active`
#: stay the organisation's (`AdminSourceDetailView`), and the email is the sign-in.
USER_FIELDS = ('name',)
SOURCE_FIELDS = tuple(field for field, _width in DETAIL_FIELDS)


def _error(code, http, **extra):
    return Response({'error': code, 'code': code, **extra}, status=http)


class _SourceConsoleBase(_AdminBase):
    """The gate every source-console view shares: an active source user of an active source."""
    source_partner_methods = ('get',)

    def _source_caller(self, request):
        """`(admin, source, None)` or `(None, None, 403)`. Staff — a super included — are refused:
        `get_admin` answers a staff row, which is not a source user."""
        admin = self.get_admin(request)
        if admin is None or not admin.is_source_user:
            return None, None, self._deny()
        source = source_access.source_of(admin)
        if source is None:
            return None, None, _error('source_unavailable', status.HTTP_403_FORBIDDEN)
        return admin, source, None

    def _gift(self, request, admin):
        """`(gift or None, error)` — `?p=` among the source's OWN gifts; another code is a 404."""
        code = (request.query_params.get('p') or '').strip()
        if not code:
            return None, None
        gift = source_access.programmes_for(admin).filter(code=code).first()
        if gift is None:
            return None, _error('not_found', status.HTTP_404_NOT_FOUND)
        return gift, None

    @staticmethod
    def _not_found():
        return _error('not_found', status.HTTP_404_NOT_FOUND)


def _listed(admin, gift):
    return source_console.in_gift(source_access.listed_applications_for(admin), gift)


def _with_rows(qs):
    """The joins every source payload reads, so a row costs no query of its own."""
    return qs.select_related('profile', 'programme', 'source', 'witness_org', 'bursary_agreement')


class AdminSourceProfileView(_SourceConsoleBase):
    """GET / PATCH `admin/source/profile/` — `{user: {name, email}, source: {name, code,
    contact_person, contact_email, phone, organisation}}`.

    PATCH `{user?: {name}, source?: {name, contact_person, contact_email, phone}}` — the same
    columns and widths as the Sources page (`sources.DETAIL_FIELDS`); a blank name is 400
    `name_required` / `source_name_required`, a malformed contact email 400 `bad_email` (the source
    invite's rule); any other key is 400 `not_editable` with `fields` — the code never changes.
    Answers with the GET payload.
    """
    source_partner_methods = ('get', 'patch')

    def get(self, request):
        admin, source, err = self._source_caller(request)
        if err:
            return err
        return Response(source_console.profile_dict(admin, source))

    def patch(self, request):
        admin, source, err = self._source_caller(request)
        if err:
            return err
        if not isinstance(request.data, dict):
            return _error('bad_request', status.HTTP_400_BAD_REQUEST)
        user = request.data.get('user') or {}
        details = request.data.get('source') or {}
        if not isinstance(user, dict) or not isinstance(details, dict):
            return _error('bad_request', status.HTTP_400_BAD_REQUEST)
        refused = sorted({f'user.{k}' for k in user if k not in USER_FIELDS}
                         | {f'source.{k}' for k in details if k not in SOURCE_FIELDS}
                         | {k for k in request.data if k not in ('user', 'source')})
        if refused:
            return _error('not_editable', status.HTTP_400_BAD_REQUEST, fields=refused)
        name = None
        if 'name' in user:
            name = (user.get('name') or '').strip()[:200]
            if not name:
                return _error('name_required', status.HTTP_400_BAD_REQUEST)
        cleaned = {field: (details.get(field) or '').strip()[:width]
                   for field, width in DETAIL_FIELDS if field in details}
        if 'name' in cleaned and not cleaned['name']:
            return _error('source_name_required', status.HTTP_400_BAD_REQUEST)
        if cleaned.get('contact_email') and _bad_email(cleaned['contact_email']):
            return _error('bad_email', status.HTTP_400_BAD_REQUEST)
        if name is not None:
            admin.name = name
            admin.save(update_fields=['name'])
        if cleaned:
            for field, value in cleaned.items():
                setattr(source, field, value)
            source.save(update_fields=list(cleaned))
        return Response(source_console.profile_dict(admin, source))


class AdminSourceOverviewView(_SourceConsoleBase):
    """GET `admin/source/overview/?p=` — `{programme, counts: {<stage>: n, …, total}, scholars,
    witness_waiting: [{application_id, student_name}], missing_items: [{application_id,
    student_name, applied, last_activity}]}`.

    `witness_waiting` is empty while `BURSARY_AGREEMENT_ENABLED` is off; it reads `applications_for`
    (a witness-only case included), the counts and the chase list `listed_applications_for`.
    """

    def get(self, request):
        admin, source, err = self._source_caller(request)
        if err:
            return err
        gift, err = self._gift(request, admin)
        if err:
            return err
        from django.conf import settings
        from .. import maintenance_scope
        listed = _listed(admin, gift)
        apps = list(listed.only(
            'id', 'status', 'pending_rejection_category', 'pre_decline_status'))
        waiting = []
        if getattr(settings, 'BURSARY_AGREEMENT_ENABLED', False):
            candidates = _with_rows(source_console.in_gift(
                source_access.applications_for(admin), gift).filter(
                    bursary_agreement__guarantor_signed_at__isnull=False,
                    bursary_agreement__witness_signed_at__isnull=True))
            waiting = source_console.witness_waiting(candidates.order_by('id'), source)
        return Response({
            'programme': source_console.gift_dict(gift),
            'counts': source_console.stage_counts(apps),
            'scholars': listed.filter(maintenance_scope.has_file_q()).count(),
            'witness_waiting': waiting,
            'missing_items': source_console.missing_items(listed),
        })


class AdminSourceApplicationListView(_SourceConsoleBase):
    """GET `admin/source/applications/?p=&q=&stage=&page=&page_size=` — `{count, total_pages, page,
    page_size, next, previous, applications: [{id, student_name, school, state, level, programme,
    submitted_at, stage}]}`, newest first.

    `q` matches the student's NAME only (never an NRIC, a phone or an email). `stage` is one of
    `source_console.STAGES` (an unknown one is 400 `bad_stage`). The stage is folded per row in
    Python — it masks what the student has not been told, which a column filter cannot — then the
    list is paged, as the staff Applications list pages its sorted list.
    """

    def get(self, request):
        admin, source, err = self._source_caller(request)
        if err:
            return err
        gift, err = self._gift(request, admin)
        if err:
            return err
        stage = (request.query_params.get('stage') or '').strip()
        if stage and stage not in source_console.STAGES:
            return _error('bad_stage', status.HTTP_400_BAD_REQUEST)
        qs = _with_rows(_listed(admin, gift))
        text = (request.query_params.get('q') or '').strip()
        if text:
            qs = qs.filter(profile__name__icontains=text)
        rows = [source_console.application_row(app)
                for app in qs.order_by('-submitted_at', '-id')]
        if stage:
            rows = [row for row in rows if row['stage'] == stage]
        paginator = FlexiblePageNumberPagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        return paginator.envelope(page, results_key='applications')


class AdminSourceApplicationDetailView(_SourceConsoleBase):
    """GET `admin/source/applications/<id>/` — 404 unless in `source_access.applications_for`.

    A LISTED application: `{id, kind: 'listed', student_name, school, state, level, programme,
    submitted_at, stage, phone, email, told_at, missing_items: [part, …], contract}`. A case this
    source only WITNESSES: `{id, kind: 'witness_only', student_name, programme, contract}` and
    nothing else. `contract` is `{status, student_signed_at, guarantor_signed_at, witness_signed_at,
    foundation_signed_at, witness_is_you}` or null. No side effects.
    """

    def get(self, request, pk):
        admin, source, err = self._source_caller(request)
        if err:
            return err
        app = _with_rows(source_access.applications_for(admin)).filter(pk=pk).first()
        if app is None:
            return self._not_found()
        if app.source_id == source.pk:
            return Response(source_console.application_detail(app, source))
        return Response(source_console.witness_only_detail(app, source))


def _scholars(admin, gift):
    """The source's scholars: LISTED applications with a maintenance file (the officer Scholars
    list's population, `maintenance_scope.has_file_q`). A witness-only case is never one."""
    from .. import maintenance_scope
    return _with_rows(_listed(admin, gift).filter(maintenance_scope.has_file_q()))


class AdminSourceScholarListView(_SourceConsoleBase):
    """GET `admin/source/scholars/?p=&page=&page_size=` — `{count, total_pages, page, page_size, next,
    previous, scholars: [{id, student_name, programme, institution, course, status,
    contract_stage}]}`, by name. No money, no payments, no results, no semester data."""

    def get(self, request):
        admin, source, err = self._source_caller(request)
        if err:
            return err
        gift, err = self._gift(request, admin)
        if err:
            return err
        paginator = FlexiblePageNumberPagination()
        page = paginator.paginate_queryset(
            _scholars(admin, gift).order_by('profile__name', 'id'), request, view=self)
        names = source_console.course_names(page)
        return paginator.envelope([source_console.scholar_row(app, names) for app in page],
                                  results_key='scholars')


class AdminSourceScholarDetailView(_SourceConsoleBase):
    """GET `admin/source/scholars/<id>/` — the row plus `phone`, `email` and `contract` (as on the
    application page). 404 unless one of this source's LISTED scholars."""

    def get(self, request, pk):
        admin, source, err = self._source_caller(request)
        if err:
            return err
        app = _scholars(admin, None).filter(pk=pk).first()
        if app is None:
            return self._not_found()
        return Response(source_console.scholar_detail(app, source))


# ── The witness step (source sign-in S4) ─────────────────────────────────────────────────────────
#: The witness's typed name is stored in `BursaryAgreement.witness_name`; a longer one is refused,
#: never cut — it is a signature.
WITNESS_NAME_MAX = 200


def _witness_case(admin, source, pk):
    """The application, when it is in this source's scope (`applications_for`) AND this source is
    its resolved witness; else None (a 404). Re-resolved on every call, so an override moved to
    another source after the page was opened takes the case away at once."""
    app = _with_rows(source_access.applications_for(admin)).filter(pk=pk).first()
    if (app is None or not source_console.agreements_on()
            or not source_console.witness_is(app, source)):
        return None
    return app


class AdminSourceAgreementView(_SourceConsoleBase):
    """GET `admin/source/applications/<id>/agreement/?link=1` — the full contract, for the WITNESS
    source only, on the witness step and after (owner ruling 2026-10-30):

    `{status, student_signed_at, guarantor_signed_at, witness_signed_at, foundation_signed_at,
    witness_is_you, can_witness, application_id, student_name, pdf_url, pdf_expires_in,
    rendered: false}`.

    `pdf_url` is null unless `?link=1` (a click), then a signed link to the PDF for
    `pdf_expires_in` (300) seconds — the Scholars contract tab's rule (`scholar_money.pdf_url`).
    404 unless `source_console.witness_step_reached`: the applicant's own source that is NOT the
    witness, an agreement the guarantor has not signed, or agreements switched off. No side
    effects.
    """

    def get(self, request, pk):
        admin, source, err = self._source_caller(request)
        if err:
            return err
        app = _witness_case(admin, source, pk)
        if app is None or not source_console.witness_step_reached(app, source):
            return self._not_found()
        with_link = request.query_params.get('link') == '1'
        return Response(source_console.agreement_dict(app, source, with_link=with_link))


class AdminSourceWitnessView(_SourceConsoleBase):
    """POST `admin/source/applications/<id>/witness/` `{witness_name, confirm: true}` — the witness
    source records its witness (roadmap C13). Answers the agreement payload (no link).

    Refusals, in this order: 403 not a source user (or `source_unavailable`); 404 out of scope, not
    the resolved witness, or agreements switched off; 400 `not_ready` (no agreement, or the
    guarantor has not signed); 409 `already_witnessed`; 409 `contract_not_live` (the application is
    no longer `awarded` / `active` / `maintenance` — `source_console.WITNESS_STATUSES`); 400
    `confirm_required` (`confirm` is not literally true); 400 `name_required` (blank once trimmed);
    400 `name_too_long` (over `WITNESS_NAME_MAX`).

    The record is `source_witness.record_once` → `bursary.record_witness` with `by_name` = the
    caller's name and `witness_name` = the typed one, under a row lock; then `witness_ip` (the
    caller's address, read as the student's and guarantor's signing reads it) and `witness_admin`
    (the caller). Everything after — the re-render, the Foundation's nudge or the executed
    distribution — is `record_witness`'s, unchanged.
    """
    source_partner_methods = ('post',)

    def post(self, request, pk):
        admin, source, err = self._source_caller(request)
        if err:
            return err
        app = _witness_case(admin, source, pk)
        if app is None:
            return self._not_found()
        agreement = source_console.agreement_of(app)
        if agreement is None or agreement.guarantor_signed_at is None:
            return _error('not_ready', status.HTTP_400_BAD_REQUEST)
        if agreement.witness_signed_at is not None:
            return _error('already_witnessed', status.HTTP_409_CONFLICT)
        if app.status not in source_console.WITNESS_STATUSES:
            return _error('contract_not_live', status.HTTP_409_CONFLICT)
        data = request.data if isinstance(request.data, dict) else {}
        if data.get('confirm') is not True:
            return _error('confirm_required', status.HTTP_400_BAD_REQUEST)
        raw = data.get('witness_name')
        name = raw.strip() if isinstance(raw, str) else ''
        if not name:
            return _error('name_required', status.HTTP_400_BAD_REQUEST)
        if len(name) > WITNESS_NAME_MAX:
            return _error('name_too_long', status.HTTP_400_BAD_REQUEST, max_length=WITNESS_NAME_MAX)
        from .. import source_witness
        try:
            source_witness.record_once(
                agreement, org=source, by_name=(admin.name or admin.email or ''),
                witness_name=name, admin=admin, ip=request.META.get('REMOTE_ADDR'))
        except source_witness.AlreadyWitnessed:
            return _error('already_witnessed', status.HTTP_409_CONFLICT)
        app = _with_rows(source_access.applications_for(admin)).get(pk=app.pk)
        return Response(source_console.agreement_dict(app, source))
