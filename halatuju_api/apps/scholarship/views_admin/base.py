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

from apps.courses import public as courses_public

from .. import qc_separation
from ..models import ScholarshipApplication
from ..services import review_writes_closed
from ..staff_lifecycle import is_open_case


def b40_scope(admin):
    """B40 Applications access by PERMISSION (request #39 Sprint 3; the presets give exactly
    what the roles gave before — `apps/courses/tests/test_permission_presets.py`):
      'all'      — `see_all` (super, admin, qc, org_admin): every application in scope, read
      'assigned' — `review` without `see_all` (reviewer): only the applicants assigned to them
      'none'     — neither (partner, finance): B40 is not their page
    'all' is org-fenced downstream by _org_scoped/_org_allows (super global; the rest
    see only their own org). WHILE A CASE IS OPEN `qc` holders are org-wide WRITERS via
    `may_write_case` (review-all within their org); a plain `see_all` stays assigned-only for
    writes. After the award neither `qc` nor the assignment writes (POST-AWARD-CUT, 2026-11-17).

    The `finance` PRESET is 'none' BY DECISION (role matrix 2026-07-23): it never sees an
    applicant file, document, income figure or verdict; its only student data is the
    Payments funding-summary allowlist, which does not read this scope. ⚠ A Finance person
    GIVEN `review` reads the files of the students ASSIGNED to them, and nothing else (owner,
    2026-10-19, open question 1 — reachable only once a permission set is saved).
    """
    if admin is None:
        return 'none'
    # Team tables T5b: `qc` is self-sufficient — it reads ALL (`qc` brings `see_all` in `resolve`,
    # `staff_permissions.IMPLIES`; named here too so this door never hangs on that one line).
    if admin.has_perm('see_all') or admin.has_perm('qc'):
        return 'all'
    if admin.has_perm('review'):
        return 'assigned'
    return 'none'


def scholars_scope(admin):
    """Who reads the SCHOLARS page and a scholar's file (sprint S1, owner 2026-11-09). Its own key,
    no longer the Applications rule (`b40_scope`, which is unchanged):
      'all'    — a super, or the `scholars` key (the admin preset, the lead tier, or a saved set
                 naming it): every scholar in their own organisation (a super: every organisation).
                 It WINS over 'mentor': a holder who also mentors reads the whole organisation;
      'mentor' — a mentor login, or a staff member mentoring now (`mentor_desk.mentor_of`, S1-h):
                 ONLY their CURRENT students (`mentor_desk.current_assignments`), read-only;
      'none'   — everyone else: `review`, `qc` and `see_all` alone open nothing here (403).
    Across organisations the answer is 404, downstream (`_org_allows`). ⚠ NO ROLE LABEL IS READ
    (`test_role_is_display_only.py`): the key, then the mentor record."""
    if holds_scholars_key(admin):
        return 'all'
    if admin is None:
        return 'none'
    from ..mentor_desk import mentor_of      # in the function: mentor_desk imports the scholar rules
    if mentor_of(admin) is not None:
        return 'mentor'
    return 'none'


def holds_scholars_key(admin):
    """`scholars_scope(admin) == 'all'` without the mentor lookup (a mentor is never 'all'), so a
    write test asked on every case detail costs no query."""
    return admin is not None and admin.has_perm('scholars')


def org_allows(admin, app):
    """Row-level org fence: True if this admin's organisation owns ``app``. Super is global;
    everyone else must match owning_organisation. A cross-org answer must surface as 404 (never
    403) so existence isn't leaked. `_AdminBase._org_allows` is this."""
    if admin is None or app is None:
        return False
    if admin.is_super:
        return True
    return app.owning_organisation_id == admin.owning_organisation_id


def may_write_file(admin, app):
    """The scholar-file WRITE (S1-d): a `scholars` holder (a super passes every key) on a file of
    their own organisation. THE ONE DEFINITION — the scholar-file views ask it through
    `_may_write_file`, and `may_write_case` asks it for every case past the open stage."""
    return holds_scholars_key(admin) and org_allows(admin, app)


def may_write_case(admin, app, status=None):
    """May this admin WRITE (act) on this application? THE ONE RULE (`_can_review_app`, and the
    `can_write` the case detail serves so the cockpit never re-derives it).

    super — always. While the case is OPEN (`staff_lifecycle.is_open_case`: before the award, or a
    REOPENED decision at any status) the rule is unchanged: a B40 scope, the own organisation, then
    `qc` org-wide or the case ASSIGNED to them. Once it is NOT open, neither the assignment nor `qc`
    writes (owner R5 2026-11-12, 16 and 17 Nov: the reviewer's relationship ends at awarded; QCs are
    reviewers with additional permission); the writer is a `scholars` holder of the own organisation
    (`may_write_file`) — who may hold no B40 scope at all, so that branch is asked first. Reads are
    untouched: an assigned reviewer still SEES their past students (`_scoped_application`).
    `status` judges the case at another status — ONLY `may_cancel_held_decline` passes it."""
    if admin is None or app is None:
        return False
    if admin.is_super:
        return True
    if not is_open_case(status or app.status, app.decision_reopened_at):
        return may_write_file(admin, app)
    if b40_scope(admin) == 'none' or not org_allows(admin, app):
        return False
    return admin.has_perm('qc') or app.assigned_to_id == admin.id


def may_cancel_held_decline(admin, app):
    """cancel-decline's own door (owner, 17 Nov: "Reviewer + QC"). A decline still EMBARGOED (the
    student not told) that was taken BEFORE the award is judged as the open case the cancel returns
    it to, so the assignee and `qc` keep the door; every other case asks the one rule unchanged.
    For this door only: no other write on a rejected case reopens."""
    from ..services.decline import held_decline_restore_target   # no query: the facts are on the row
    back_to = held_decline_restore_target(app) if app is not None else None
    if back_to and is_open_case(back_to, None):
        return may_write_case(admin, app, status=back_to)
    return may_write_case(admin, app)


class _AdminBase(courses_public.PartnerAdminMixin, APIView):
    """Shared 403-if-not-admin guard + own-application lookup."""

    def _deny(self):
        return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)

    def _deny_role(self):
        return Response({'error': 'Your admin role cannot perform this action.'},
                        status=status.HTTP_403_FORBIDDEN)

    def _get_application(self, pk):
        # `programme` (the GIFT) is joined here, not fetched later: every detail payload now names
        # it (`serializers_admin_gift`, 2026-09-28), and a join costs no query where a lazy FK
        # read cost one — `test_query_budgets.py` measured 38 -> 39 without it. `source` likewise
        # (sources Sprint C: the cockpit's `source` key; an applicant WITH a source is measured).
        # org-fence: the shared lookup; every caller re-gates via _org_allows /
        # _scoped_application / _require_app_write / _require_qc before use.
        return ScholarshipApplication.objects.select_related(
            'profile', 'cohort', 'programme', 'source', 'assigned_to',
            'owning_organisation').filter(pk=pk).first()

    def _b40_scope(self, admin):
        """The B40 read scope — `b40_scope` (module level, so a non-view rule such as
        `award_withdrawal_chain` asks the SAME question the case detail asks)."""
        return b40_scope(admin)

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

    def _gift_required_for_orgless_super(self, admin, programme):
        """TD-334 (2026-10-05): a 400 `programme_required` when a super with NO organisation of
        their own names no gift on a money read (Payments list, funding summary, Spending).

        For them "do not narrow" (above) meant every organisation pooled into one list — the web
        gift gate never sends that request, but the server must not depend on it. A super WITH an
        organisation, and an organisation's own admins, keep exactly what they read before.
        """
        if programme is None and admin.is_super and admin.owning_organisation_id is None:
            return Response({'error': 'programme_required', 'code': 'programme_required'},
                            status=status.HTTP_400_BAD_REQUEST)
        return None

    def _org_narrowing(self, request, admin):
        """Read `?org=<organisation code>` — the ORGANISATION crumb (TD-228, 2026-10-05). Returns
        `(organisation|None, error|None)`; the sibling of `_gift_narrowing`, by the same rules.

        ⚠ ABSENT MEANS "DO NOT NARROW". ⚠ IT NARROWS INSIDE THE FENCE AND CAN NEVER WIDEN: a
        super (who alone sees more than one organisation, and alone is shown the crumb) may name
        any organisation; anybody else resolves only their OWN, so another organisation's code and
        an unknown one are the same answer — 404, never 403 — and cannot confirm it exists.
        """
        code = (request.query_params.get('org') or '').strip()
        if not code:
            return None, None
        from apps.courses.models import PartnerOrganisation
        qs = PartnerOrganisation.objects.filter(code=code)
        if not self.has_role(admin, 'super'):
            own = admin.owning_organisation_id if admin is not None else None
            qs = qs.filter(pk=own) if own else qs.none()
        org = qs.first()
        if org is None:
            return None, Response({'error': 'not_found', 'code': 'not_found'},
                                  status=status.HTTP_404_NOT_FOUND)
        return org, None

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
        return org_allows(admin, app)

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
        """True if this admin may WRITE (review-act) on this application — `may_write_case`, the one
        rule. While the case is open: super; `qc` holders on ANY case of their OWN org; anyone else
        in scope ONLY on cases ASSIGNED to them; partner/finance never (no B40 scope). Past the open
        stage (awarded onwards, and terminal cases not reopened): super, or a `scholars` holder of
        the own org — the assignment and `qc` no longer write (POST-AWARD-CUT, 2026-11-17).
        (org_admin/qc writing across the org is safe because the QC separation guard in _require_qc
        (`qc_separation.refusal`) stops anyone QC-ing a case they were assigned (ever), interviewed,
        verify-accepted or recorded the verdict on.)"""
        return may_write_case(admin, app)

    def _may_write_file(self, admin, app):
        """The scholar-file write — `may_write_file` (lifted here from `_ScholarsBase`, 2026-11-17)."""
        return may_write_file(admin, app)

    def _require_app_write(self, request, pk, judge=None):
        """Auth prologue for a per-application WRITE. Returns (app, admin, None) when the caller
        may act on this application (`_can_review_app`, or a door's own `judge`), else
        (None, None, error_response). Replaced the old role-only reviewer prologue + _scoped_application
        pair for per-application mutations (that prologue is gone: its last caller, the graduation
        thank-you review, asks the `review` key since sprint THANKS)."""
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
        if not (judge or self._can_review_app)(admin, app):
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
        because some per-application writes are legitimate on a closed case (cancelling a decline,
        correcting a reporting date, re-running a document read); making the status gate universal
        would break them. Since POST-AWARD-CUT (2026-11-17) those are done by a `scholars` holder or a
        super, not the assignee — `may_write_case`. See `services.review_writes_closed` for why
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

        Self-QC guard (Team tables T5b, owner: "QC never decides their own"): a QC holder must NOT
        QC a case they are or WERE assigned, interviewed (a draft counts), verify-accepted, or
        recorded the verdict on — that routes to another QC / super. The whole rule is
        `qc_separation.refusal`; 403 with its code. (Super is the owner override and is exempt.)

        `finance` is refused by the role list below — it is a money checker, not a case checker,
        and has no B40 scope to QC with."""
        admin = self.get_admin(request)
        if not admin:
            return None, None, self._deny()
        if not admin.has_perm('qc'):                  # #39 S3: qc / org_admin / super, as before
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
        # Separation of duties (2026-07-15 recorder guard, widened in T5b): with org_admin/qc able
        # to work ANY own-org case, the current assignment no longer proves who worked it.
        code = qc_separation.refusal(admin, app)
        if code:
            return None, None, Response({'error': qc_separation.MESSAGES[code], 'code': code},
                                        status=status.HTTP_403_FORBIDDEN)
        return app, admin, None


#: `YYYY-MM`. Read by the billing screens in the package root AND by the invoices
#: module, which is why it sits here rather than inside either of them (H11).
_MONTH_RE = re.compile(r'^\d{4}-\d{2}$')


def _org_or_none(org_id):
    from apps.courses.models import PartnerOrganisation
    # org-fence: super-only callers reach this; the org id is validated, not trusted.
    return PartnerOrganisation.objects.filter(pk=org_id).first()


def _id_or_no_match(raw):
    """A row id from untrusted input, or -1 — which matches no row.

    ⚠ DIGITS, not `int(...)`. `filter(pk='abc')` raises, but `int()` is the wrong refusal because
    it ACCEPTS what this is not: `int(1.5)` is 1 and `int(True)` is 1, so a float or a boolean
    would quietly act on row 1.

    It lives here, beside `_MONTH_RE`, for the same reason that does: more than one module in this
    package takes an id off a request body, and two spellings of "is this an id?" eventually
    disagree about `True`. (2026-10-29)
    """
    text = '' if raw is None else str(raw).strip()
    if isinstance(raw, bool) or not text.isdigit():
        return -1
    return int(text)
