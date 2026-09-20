"""The shared admin base view — moved verbatim from `views_admin.py` at code health H11.

`_AdminBase` is where the organisation fence lives (tenancy rule 3: org scoping sits in the
base gates), so every view in this package inherits it, moved or not. `_MONTH_RE` and
`_org_or_none` sit here for the same reason: each is read by a moved module AND by the
package root, and a rule with two homes is what this arc is removing.

⚠ `PartnerAdminMixin` MOVED HERE RATHER THAN BEING IMPORTED AGAIN. `_AdminBase` was its only
reader, so the line left the package root instead of being copied — the app-boundary standard
counts every import that crosses into `apps.courses`, and a split that repeats the same import
in each new module makes the boundary read wider while nothing about it has changed. Every
other `apps.courses` import in this package sits inside the function that needs it, exactly
where it was before the move.

Part of the `views_admin` package. Every name below is re-exported from
`views_admin/__init__.py`, so `urls.py` and every importer are unchanged.
"""
import re

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses.views_admin import PartnerAdminMixin

from ..models import ScholarshipApplication
from ..services import review_writes_closed


class _AdminBase(PartnerAdminMixin, APIView):
    """Shared 403-if-not-admin guard + own-application lookup."""

    def _deny(self):
        return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)

    def _deny_role(self):
        return Response({'error': 'Your admin role cannot perform this action.'},
                        status=status.HTTP_403_FORBIDDEN)

    def _require_reviewer(self, request):
        """Auth prologue for reviewer-gated admin WRITES: returns ``(admin, None)`` when the
        caller is an active admin with the reviewer role, else ``(None, error_response)``.
        Centralises the get_admin + reviewer-role check (TD audit 2026-06-14) so a write
        endpoint can't silently forget the role gate and under-protect PII/consent actions
        (a plain 'admin' has full B40 scope but is read-only — the role check is the guard)."""
        admin = self.get_admin(request)
        if not admin:
            return None, self._deny()
        if not self.has_role(admin, 'reviewer'):
            return None, self._deny_role()
        return admin, None

    def _get_application(self, pk):
        # org-fence: the shared lookup; every caller re-gates via _org_allows /
        # _scoped_application / _require_app_write / _require_qc before use.
        return ScholarshipApplication.objects.select_related('profile', 'cohort').filter(pk=pk).first()

    def _b40_scope(self, admin):
        """B40 Applications access by role:
          'all'      — super + admin + qc + org_admin (see every application in scope, read)
          'assigned' — reviewer (only the applicants assigned to them)
          'none'     — partner / finance / anyone else (B40 is not their page)
        'all' is org-fenced downstream by _org_scoped/_org_allows (super global; the rest
        see only their own org). qc + org_admin are org-wide WRITERS via _can_review_app
        (review-all within their org); a plain 'admin' stays assigned-only for writes.

        `finance` is 'none' BY DECISION (role matrix 2026-07-23), not by omission: it never
        sees an applicant file, document, income figure or verdict. Its only student data is
        the award/paid/remaining/eWallet allowlist served by the Payments funding summary,
        which is a Payments endpoint and does not read this scope.
        """
        if admin is None or admin.role in ('partner', 'finance'):
            return 'none'
        if self.has_role(admin, 'admin') or admin.role in ('qc', 'org_admin'):  # super + admin + qc + org_admin
            return 'all'
        if admin.role == 'reviewer':
            return 'assigned'
        return 'none'

    # ── Organisation fence (platform Sprint 3a) ────────────────────────────────
    # The tenant wall on the B40 admin surface. Access control keys off
    # PartnerAdmin.owning_organisation (NOT the referral `org`). Invisible while
    # BrightPath is the only organisation (every staff/application pair is same-org),
    # and the real fence the moment a second organisation exists. NULL owning_org is
    # a safe degenerate bucket (=None → IS NULL) so bare test fixtures self-partition.
    def _org_scoped(self, qs, admin, field='owning_organisation_id'):
        """Fence an applications queryset (or any model reaching an application by
        ``field``, e.g. 'application__owning_organisation_id') to the caller's
        organisation. Super is global; everyone else is filtered to their own org."""
        if admin is not None and self.has_role(admin, 'super'):
            return qs
        org_id = admin.owning_organisation_id if admin is not None else None
        return qs.filter(**{field: org_id})

    def _programme_by_code(self, admin, code):
        """Resolve a `?programme=<code>` narrowing INSIDE the caller's own organisation.

        ⚠ THIS IS NOT A FENCE AND MUST NOT BECOME ONE. The organisation wall stays
        `_org_scoped` / `_org_allows`; this only says WHICH of the caller's own gifts a list
        was asked to narrow to. It is derived from the same `owning_organisation` the fence
        uses, so it can never widen anything — a client that omits the parameter reaches
        exactly the rows the fence already allowed.

        Returns None for an unknown code AND for another tenant's code — the caller turns both
        into a 404, never a 403, so a cross-tenant code cannot confirm that gift exists.
        `_ProgrammeScopedBase._programmes_for` runs the same query, but its ROLES gate is
        org_admin-only; the Applications list is read by reviewers and admins too, so the
        lookup lives here where the role gate is the reading view's own.
        """
        from ..models import Programme
        qs = Programme.objects.all()
        if not self.has_role(admin, 'super'):
            org_id = admin.owning_organisation_id if admin is not None else None
            qs = qs.filter(organisation_id=org_id) if org_id else qs.none()
        return qs.filter(code=code).first()

    def _gift_narrowing(self, request, admin):
        """Read `?programme=<code>` and resolve it. Returns `(programme|None, error|None)`.

        **The ONE place a Programme-scope page asks "which gift is this request about?"** —
        added for TD-241 (2026-09-11), when Payments and Spending moved from the Organisation
        section to the Programme section. Both screens go through here so they cannot drift into
        two different answers, which is the whole reason the owner's request was one request.

        ⚠⚠ **AN ABSENT PARAMETER MEANS "DO NOT NARROW", NOT "PICK ONE FOR THEM".** Choosing a
        gift server-side when none was named is the 2026-09-03 defect exactly: the console showed
        the owner a DIFFERENT programme's settings than the one they had opened. `programmeScope`
        on the client already resolves the single-gift case and refuses to guess between several
        (`chosen` stays `''`), so a missing value here means the client genuinely could not say —
        and the honest response to that is every gift the fence already allows, not a guess.

        ⚠ **IT NARROWS INSIDE THE FENCE AND CAN NEVER WIDEN.** `_programme_by_code` resolves only
        within the caller's own organisation, so an unknown code and another tenant's code are
        indistinguishable — both `None` — and both become a 404 here, never a 403: a cross-tenant
        code must not confirm that gift exists.
        """
        code = (request.query_params.get('programme') or '').strip()
        if not code:
            return None, None
        programme = self._programme_by_code(admin, code)
        if programme is None:
            return None, Response({'error': 'not_found', 'code': 'not_found'},
                                  status=status.HTTP_404_NOT_FOUND)
        return programme, None

    def _intake_narrowing(self, request, admin, programme):
        """Read `?intake=<cohort id>` and resolve it. Returns `(cohort|None, error|None)`.

        The intake-round sibling of `_gift_narrowing` (Programme Overview phase 2, 2026-09-18),
        and on `_AdminBase` for the same reason: the Applications list is the obvious next
        caller, and two pages must not answer "which round?" two ways.

        ⚠ AN ABSENT PARAMETER MEANS "DO NOT NARROW". ⚠ IT NARROWS INSIDE THE FENCE AND CAN
        NEVER WIDEN: a non-super resolves only within their own organisation, and when a gift
        was named the round must belong to it. An unknown id, another tenant's, another gift's
        and a non-integer are all one answer — 404, never 403 and never 400 — because a
        cross-tenant id must not confirm that round exists.
        """
        from ..models import ScholarshipCohort

        raw = (request.query_params.get('intake') or '').strip()
        if not raw:
            return None, None
        not_found = Response({'error': 'not_found', 'code': 'not_found'},
                             status=status.HTTP_404_NOT_FOUND)
        try:
            cohort_id = int(raw)
        except ValueError:
            return None, not_found
        # org-fence: owning_organisation for every non-super; a super is fenced by the gift below
        # (and sees every tenant without one, which is the platform scope this page gives them).
        qs = ScholarshipCohort.objects.filter(pk=cohort_id)
        if not self.has_role(admin, 'super'):
            qs = qs.filter(owning_organisation_id=admin.owning_organisation_id)
        if programme is not None:
            qs = qs.filter(programme=programme)
        cohort = qs.first()
        if cohort is None:
            return None, not_found
        return cohort, None

    def _org_allows(self, admin, app):
        """Row-level org fence: True if this admin's organisation owns ``app``.
        Super is global; everyone else must match owning_organisation. A cross-org
        answer must surface as 404 (never 403) so existence isn't leaked."""
        if admin is None or app is None:
            return False
        if self.has_role(admin, 'super'):
            return True
        return app.owning_organisation_id == admin.owning_organisation_id

    def _scoped_application(self, request, pk):
        """The application IFF this admin may access it (reviewer assignment-scoped;
        partner none). Returns (app, error_response|None)."""
        admin = self.get_admin(request)
        if not admin:
            return None, self._deny()
        scope = self._b40_scope(admin)
        if scope == 'none':
            return None, self._deny_role()
        app = self._get_application(pk)
        if app is None:
            return None, Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        if not self._org_allows(admin, app):
            # Cross-org: 404, not 403 — don't leak that another org's app exists.
            return None, Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        if scope == 'assigned' and app.assigned_to_id != admin.id:
            return None, self._deny_role()   # reviewer, not assigned to them
        return app, None

    def _can_review_app(self, admin, app):
        """True if this admin may WRITE (review-act) on this application:
          super              — acts on any application;
          org_admin / qc     — act on ANY application in their OWN org (org_admin = the
                               organisation superadmin; qc = the hybrid review-all role);
          admin / reviewer   — act ONLY on applications ASSIGNED to them;
          partner            — never.
        (Assignment-based review permission, 2026-07 — a plain 'admin' has full READ scope
        via _b40_scope='all' but assigned-only WRITE, so a view-all admin can be given a
        selective review remit. org_admin/qc write across the org is safe because the QC
        recorder guard in _require_qc stops anyone QC-ing a verdict they themselves recorded.
        `finance` never reaches here: its _b40_scope is 'none', so the first test refuses it.)"""
        if admin is None or app is None:
            return False
        if self._b40_scope(admin) == 'none':          # partner / non-B40
            return False
        if self.has_role(admin, 'super'):
            return True
        if not self._org_allows(admin, app):          # cross-org (Sprint 3a)
            return False
        if admin.role in ('org_admin', 'qc'):         # org-wide write (same-org guaranteed above)
            return True
        return app.assigned_to_id == admin.id

    def _require_app_write(self, request, pk):
        """Auth prologue for a per-application WRITE. Returns (app, admin, None) when the caller
        may act on this application (super, or the assigned admin/reviewer), else
        (None, None, error_response). Replaces the old _require_reviewer + _scoped_application
        pair for per-application mutations (the role-only _require_reviewer stays for the few
        non-application writes: sponsor review, graduation review, reviewer profile)."""
        admin = self.get_admin(request)
        if not admin:
            return None, None, self._deny()
        app = self._get_application(pk)
        if app is None:
            return None, None, Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        if not self._org_allows(admin, app):
            # Cross-org: 404 (don't leak existence). Distinct from the 403 below, which
            # is a SAME-org app the caller simply isn't assigned to.
            return None, None, Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        if not self._can_review_app(admin, app):
            return None, None, self._deny_role()
        return app, admin, None

    def _require_open_case(self, request, pk):
        """Auth prologue for a REVIEW-track write (interview capture, gap suggestion, verdict).

        `_require_app_write` plus one thing it deliberately does not check: whether there is
        still a review to write into. It has no status gate at all, so on a case that expired
        or was rejected before anyone reviewed it, every one of these endpoints answered 200 —
        `record-verdict` would have stamped a verdict AND an award amount onto a rejected file
        (the same defect the 2026-07-30 sprint fixed, reached through a different door), and
        `suggest-gaps` would have spent a Gemini call on it.

        ⚠ ADD A NEW REVIEW-TRACK WRITE HERE, NOT TO `_require_app_write`. The two are separate
        because the majority of per-application writes are legitimate on a closed case
        (cancelling a decline, correcting a reporting date, re-running a document read); making
        the status gate universal would break them. See `services.review_writes_closed` for why
        a REOPENED case is open however terminal its status reads.
        """
        app, admin, err = self._require_app_write(request, pk)
        if err:
            return None, None, err
        if review_writes_closed(app):
            return None, None, Response(
                {'error': 'This case is closed — there is no review left to record.',
                 'code': 'case_closed', 'status': app.status},
                status=status.HTTP_400_BAD_REQUEST)
        return app, admin, None

    def _require_qc(self, request, pk):
        """Auth prologue for the QC gate. Returns (app, admin, None) when the caller may QC this
        application — a `super` or a `qc`-role admin, and the app is in the AWAITING-QC stage
        (`interviewed`) — else (None, None, error_response). QC is deliberately NOT assignment-
        scoped (it checks a reviewer's work across the queue) and is distinct from reviewer writes.

        Self-QC guard: the senior `qc`/`org_admin` roles can also REVIEW their assigned cases, so
        they must NOT QC a case they were the assigned reviewer of — that routes to another QC /
        super. (Super is the owner override and is exempt.)

        `finance` is refused by the role list below — it is a money checker, not a case checker,
        and has no B40 scope to QC with."""
        admin = self.get_admin(request)
        if not admin:
            return None, None, self._deny()
        if not (self.has_role(admin, 'super') or admin.role in ('qc', 'org_admin')):
            return None, None, self._deny_role()
        app = self._get_application(pk)
        if app is None:
            return None, None, Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        if not self._org_allows(admin, app):
            # Cross-org QC: 404, don't leak existence (super is exempt via _org_allows).
            return None, None, Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        if app.status != 'interviewed':
            return None, None, Response(
                {'error': 'This case is not awaiting QC.', 'code': 'not_awaiting_qc'},
                status=status.HTTP_400_BAD_REQUEST)
        if not self.has_role(admin, 'super') and app.assigned_to_id == admin.id:
            return None, None, Response(
                {'error': 'You reviewed this case — it must be QC-checked by someone else.',
                 'code': 'self_qc_forbidden'}, status=status.HTTP_403_FORBIDDEN)
        # Recorder guard (2026-07-15): with org_admin/qc able to record a verdict on ANY
        # own-org case, assignment no longer proves who recorded it. Two-person control
        # (models.py:482) means the person who RECORDED the verdict must never QC it —
        # match on the recorder's email (the stable staff key). Super is the owner override.
        recorder = (app.verdict_decided_by or '').strip().lower()
        if not self.has_role(admin, 'super') and recorder and recorder == (getattr(admin, 'email', '') or '').strip().lower():
            return None, None, Response(
                {'error': 'You recorded this verdict — it must be QC-checked by someone else.',
                 'code': 'self_verdict_qc_forbidden'}, status=status.HTTP_403_FORBIDDEN)
        return app, admin, None


#: `YYYY-MM`. Read by the billing screens in the package root AND by the invoices
#: module, which is why it sits here rather than inside either of them (H11).
_MONTH_RE = re.compile(r'^\d{4}-\d{2}$')


def _org_or_none(org_id):
    from apps.courses.models import PartnerOrganisation
    # org-fence: super-only callers reach this; the org id is validated, not trusted.
    return PartnerOrganisation.objects.filter(pk=org_id).first()
