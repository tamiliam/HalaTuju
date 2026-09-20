"""An awarded application's later life: witness, disbursements, closure, maintenance, scope.

Moved verbatim from the package root at code health H12. Part of the `views_admin`
package: every name below is re-exported from `views_admin/__init__.py`, so `urls.py`
and every importer are unchanged.
"""
from rest_framework import status
from rest_framework.response import Response
from apps.courses.models import PartnerAdmin, PartnerOrganisation
from .. import reopen as reopen_service
from .. import disbursement as disbursement_service
from .. import maintenance as maintenance_service
from .. import closure as closure_service
from ..models import Disbursement, Programme, ScholarshipApplication
from ..serializers_admin import AdminApplicationDetailSerializer

from .base import _AdminBase

from .sources import _SourcesBase


class AdminApplicationWitnessView(_SourcesBase):
    """PATCH .../admin/scholarship/applications/<pk>/witness/ {witness_org: <code|id|null>} —
    assign (or clear) the witness-organisation OVERRIDE for a (typically sourceless) application.
    NULL/'' clears the override (bursary witness resolution then falls back to the referring org,
    else straight to the Foundation countersignature)."""
    def patch(self, request, pk):
        admin, err = self._sources_admin(request)
        if err:
            return err
        app = self._get_application(pk)
        if app is None:
            return Response({'error': 'not_found', 'code': 'not_found'},
                            status=status.HTTP_404_NOT_FOUND)
        if 'witness_org' not in request.data:
            return Response({'error': 'witness_org_required', 'code': 'witness_org_required'},
                            status=status.HTTP_400_BAD_REQUEST)
        previous_org_id = app.witness_org_id
        raw = request.data.get('witness_org')
        if raw in (None, '', 'none'):
            app.witness_org = None
        else:
            from apps.courses.models import PartnerOrganisation
            key = str(raw).strip()
            org = PartnerOrganisation.objects.filter(code=key).first()
            if org is None and key.isdigit():
                org = PartnerOrganisation.objects.filter(pk=int(key)).first()
            if org is None:
                return Response({'error': 'unknown_organisation', 'code': 'unknown_organisation'},
                                status=status.HTTP_400_BAD_REQUEST)
            app.witness_org = org
        app.save(update_fields=['witness_org'])
        # Partner comms (2026-07-26): tell the organisation a student has joined its bursary
        # students. Inline — an explicit admin action with nothing to revert — and fully
        # best-effort, so an email problem can never fail the assignment. A CLEARED witness
        # (None) emails nobody; a reassignment emails the NEW organisation only.
        if app.witness_org is not None:
            from .. import partner_notify
            partner_notify.notify_partner_assigned(app, app.witness_org)
        # Request #3 (2026-08-01): tell the STUDENT too. That organisation may witness their
        # bursary contract and can see details of their application in order to do it, and until
        # now only the organisation was told. Requester: "We DO NOT want the student's consent, but
        # a notification is a must." Same best-effort contract as the line above, and the same
        # stored template — the owner switches it and edits its wording on the Sources screen
        # beside the five organisation emails, with its recipient labelled there.
        #
        # Only on a CHANGE of organisation: re-saving the same one is an administrator tidying a
        # form, and the student has already been told that fact. (The organisation's own email
        # deliberately keeps its existing behaviour and fires on every save — narrowing it is a
        # change to partner comms nobody asked for.) A CLEARED assignment emails nobody: "your
        # organisation has been removed" is a different message, and one the requester has not
        # asked for — they do not intend to reassign at all.
        if app.witness_org is not None and app.witness_org_id != previous_org_id:
            from .. import partner_notify
            partner_notify.notify_student_assigned(app, app.witness_org)
        return Response({
            'id': app.id,
            'witness_org': app.witness_org.code if app.witness_org else None,
            'witness_org_name': app.witness_org.name if app.witness_org else None,
        })


class AdminDisbursementScheduleView(_AdminBase):
    """Post-award S4: POST .../applications/<pk>/disbursements/ {amount, sequence?, label?,
    scheduled_for?} — schedule one tranche against a funded application. Reviewer-gated.
    Returns the refreshed application detail (the cockpit re-renders its disbursement panel)."""
    def post(self, request, pk):
        app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        seq = request.data.get('sequence')
        try:
            seq = int(seq) if seq not in (None, '') else None
        except (TypeError, ValueError):
            return Response({'error': 'bad_sequence'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            disbursement_service.schedule_tranche(
                app,
                amount=request.data.get('amount'),
                sequence=seq,
                label=request.data.get('label', ''),
                scheduled_for=request.data.get('scheduled_for') or None,
            )
        except disbursement_service.DisbursementError as e:
            return Response({'error': e.code}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AdminApplicationDetailSerializer(app).data)


class AdminDisbursementActionView(_AdminBase):
    """Post-award S4: POST .../disbursements/<pk>/<action>/ where action ∈
    release | withhold | return | mark_due. Reviewer-gated + access-scoped via the
    tranche's application. A 'release' (the first one) flips the app active → maintenance.
    Returns the refreshed application detail."""
    def post(self, request, pk, action):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        writer = disbursement_service.ACTIONS.get(action)
        if writer is None:
            return Response({'error': 'bad_action'}, status=status.HTTP_400_BAD_REQUEST)
        disb = (Disbursement.objects.select_related('application', 'application__profile',
                                                    'application__cohort')
                .filter(pk=pk).first())
        if disb is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        # Assignment-based write: super, or the admin/reviewer assigned to the tranche's application.
        if not self._can_review_app(admin, disb.application):
            return self._deny_role()
        try:
            writer(disb, by_email=admin.email,
                   note=request.data.get('note', ''))
        except disbursement_service.DisbursementError as e:
            return Response({'error': e.code}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AdminApplicationDetailSerializer(disb.application).data)


class AdminCloseApplicationView(_AdminBase):
    """Post-award S6: POST .../applications/<pk>/close/ {closure_reason} — manually close a
    funded application (active/maintenance) with a reason (graduated/completed/withdrawn/
    lapsed/terminated). Reviewer-gated + access-scoped. Terminal. Returns the refreshed detail."""
    def post(self, request, pk):
        app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        try:
            closure_service.close_application(
                app, closure_reason=request.data.get('closure_reason'), by_email=admin.email)
        except closure_service.ClosureError as e:
            return Response({'error': e.code}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AdminApplicationDetailSerializer(app).data)


class AdminMaintenanceSubstateView(_AdminBase):
    """Post-award S5: POST .../applications/<pk>/maintenance/ {substate} — set the
    operational maintenance sub-state (on_track | probation | on_hold | ready_to_close).
    Reviewer-gated + access-scoped. `on_hold` pauses tranche releases. Returns the
    refreshed application detail."""
    def post(self, request, pk):
        app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        try:
            maintenance_service.set_substate(app, request.data.get('substate'))
        except maintenance_service.MaintenanceError as e:
            return Response({'error': e.code}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AdminApplicationDetailSerializer(app).data)


class AdminScopeListView(_AdminBase):
    """GET .../scopes/ — the organisations and programmes this admin may LOOK AT (nav/IA N3a).

    Feeds the console's breadcrumb switchers. Until now the breadcrumb was static text and the
    programme crumb was hardcoded `undefined`, so it never rendered at all — the approved design
    had two switchers and the build had neither.

    ⚠ THIS IS NOT THE FENCE, and the switcher built on it must never become one.
    The org fence is `_org_scoped` / `_org_allows`, unchanged. This endpoint answers "what may I
    look at", and its answer is DERIVED from the same `owning_organisation` the fence uses — so it
    cannot widen anything. A client that ignores it entirely reaches exactly the same data.

    Specifically forbidden, and the reason the roadmap called it out: the selected scope must not
    travel as a global header, a cookie, or a middleware rewrite. That would relocate the fence
    into the client, which is the 2026-07-15 surface-partition incident in a new costume. For a
    super it is a DISPLAY preference and nothing more.

    Who sees what:
      super      — every active organisation and programme (they genuinely work across tenants)
      everyone   — exactly their own `owning_organisation`, and that org's active programmes
      partner    — nothing. A referral organisation is an attribution relationship, NEVER an
                   access scope (`PartnerAdmin.org` / `referred_by_org`); handing a school a
                   scope switcher would say otherwise.
      no org     — empty lists, not a 500. A reviewer with `owning_organisation` NULL is a real
                   row in production and must get a usable console.

    Programme codes are `Programme.code`, which is what PF-1 settled a programme is identified by
    (`/scholarship/apply?p=<code>`) — one vocabulary for "which programme", not two.

    Names come from the trilingual `name_*` columns with the en-fallback convention used across
    branding: a blank `ms`/`ta` falls back to `en` rather than rendering empty.
    """

    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()

        lang = (request.query_params.get('lang') or 'en').lower()
        if lang not in ('en', 'ms', 'ta'):
            lang = 'en'

        # A referral-org rep has no scope to switch between, and saying so with empty lists is
        # the honest answer — not an error, because nothing has gone wrong.
        if admin.role == 'partner':
            return Response({'organisations': [], 'programmes': []})

        # ⚠ TENANTS ONLY — `partner_organisations` also holds REFERRAL organisations
        # (schools, NGOs that send us students) with no flag between them. The rule and the
        # reason it is BOTH conditions live on the manager, so nobody has to know it here.
        orgs = PartnerOrganisation.objects.tenants().filter(is_active=True).order_by('name')
        # ⚠ INACTIVE PROGRAMMES ARE INCLUDED, AND THE PRODUCT RULE IS WHY (2026-09-03).
        # A gift is CREATED INACTIVE by design (Sabah S2: an active second programme changes live
        # behaviour the instant it exists) and must then be configured — its rules, what it asks
        # for, its first intake year — BEFORE it is switched on. So "not switched on yet" is
        # precisely the state an org_admin spends the most time standing inside, and a switcher
        # that could not reach it made the gift they had just created unreachable: the crumb
        # discarded the selection and fell back to the only ACTIVE gift, silently showing them
        # somebody else's settings. Reported by the owner on the first real use.
        # The ORGANISATION list keeps its `is_active` filter — an inactive tenant is a different
        # question, and nobody configures one.
        programmes = (Programme.objects.all()
                      .select_related('organisation').order_by('organisation__name', 'code'))
        if not self.has_role(admin, 'super'):
            # Derived from the SAME column the fence uses — so this can never widen access.
            # NULL owning_organisation narrows to nothing, which is correct and not an error.
            org_id = admin.owning_organisation_id
            orgs = orgs.filter(id=org_id) if org_id else orgs.none()
            programmes = programmes.filter(organisation_id=org_id) if org_id else programmes.none()

        def _name(p):
            return getattr(p, f'name_{lang}', '') or p.name_en

        return Response({
            'organisations': [
                {'id': o.id, 'code': o.code, 'name': o.name} for o in orgs
            ],
            'programmes': [
                {'id': p.id, 'code': p.code, 'name': _name(p),
                 # So a switcher can SAY a gift is not switched on yet, rather than the reader
                 # discovering it from the screen underneath.
                 'is_active': p.is_active,
                 'organisation_id': p.organisation_id} for p in programmes
            ],
        })


class AdminAssignableAdminsView(_AdminBase):
    """GET .../assignable-admins/ — active REVIEWERS, ADMINS (+ supers) for the assignment
    dropdown. Only roles that can be assigned an applicant appear (mirrors services._can_review):
    a view-all 'admin' and the senior 'qc' role can be assigned selective review work (assignment
    grants WRITE on the assigned application while their read stays all), so admins + qc are listed;
    'partner' and 'finance' have no review role and are excluded. (A qc's own reviewed case is QC'd
    by someone else — the self-QC guard in _require_qc.)"""
    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        from django.db.models import Q
        # tenancy: list-fenced (2026-07-15). Super sees every assignable staff member; a
        # non-super (org_admin) sees only their OWN org's assignable staff — so a delegated
        # assignment can't reach across tenants. (A PartnerAdmin list, not applicant data.)
        admins = (PartnerAdmin.objects.filter(is_active=True)
                  .filter(Q(is_super_admin=True) | Q(role__in=['reviewer', 'super', 'admin', 'qc', 'org_admin']))
                  .select_related('reviewer_profile', 'programme').order_by('name'))
        if not self.has_role(admin, 'super'):
            admins = admins.filter(owning_organisation_id=admin.owning_organisation_id,
                                   is_super_admin=False)
        # Internal-only "corrections" tally per reviewer (reopened decisions that led
        # to a real change). Never shown to sponsors/students — an internal quality
        # signal for whoever assigns reviewers.
        corrections = reopen_service.reviewer_correction_counts()

        def langs(a):
            # Languages the reviewer can conduct a review in (conversational or better),
            # for matching against the student's preferred call language. Codes: en/ms/ta.
            rp = getattr(a, 'reviewer_profile', None)
            if rp is None:
                return []
            ok = ('conversational', 'fluent')
            return [code for code, lvl in (('en', rp.english_fluency),
                                           ('ms', rp.bm_fluency),
                                           ('ta', rp.tamil_fluency)) if lvl in ok]

        # "Past reviewers" for the list-page assignee FILTER (owner 2026-07-16): anyone still on
        # record as an application's ASSIGNEE (any status incl. closed/rejected) — filtering by
        # them returns their old cases. Deliberately INDEPENDENT of is_active/role, so an inactive
        # or role-changed past reviewer stays filterable; and deliberately NOT AssignmentEvent
        # history (a fully-reassigned person filters to zero rows — a dead option).
        # org-fence: _org_scoped below — a non-super sees only their own org's past assignees.
        assigned_apps = self._org_scoped(
            ScholarshipApplication.objects.filter(assigned_to__isnull=False), admin)
        past = (PartnerAdmin.objects
                .filter(id__in=assigned_apps.values_list('assigned_to_id', flat=True).distinct())
                .order_by('name'))

        # ⚠ A PAUSED reviewer is FLAGGED, never filtered out (request #10, 2026-08-02). The cockpit
        # unions the current assignee in from this very list, so dropping anybody reproduces bug
        # #66 — the case reads as "Unassigned" when it is nothing of the sort. The dropdown renders
        # them disabled with "Paused" as the reason, which also answers the reader's next question
        # instead of leaving a name mysteriously absent.
        #
        # ⚠ A reviewer's GIFT travels the same way, and for the same reason (S-ASSIGN,
        # 2026-09-04). `programme_id` NULL means EVERY gift — the owner's ruling and the
        # permissive default every one of the 17 org-scoped staff on production still has — so a
        # client that ignores this field behaves exactly as before. It is a NARROWING of who is
        # offered work, never a fence: the org fence is `_org_scoped`, and a reviewer somehow
        # handed another gift's case still passes it. The screen greys the row and says which
        # gift they cover rather than hiding the name.
        return Response({'admins': [
            {'id': a.id, 'name': a.name, 'email': a.email,
             'role': 'super' if a.is_super else a.role, 'languages': langs(a),
             'paused': a.paused_at is not None,
             'programme_id': a.programme_id,
             'programme_name': (a.programme.name_en or a.programme.code) if a.programme_id else '',
             'corrections': corrections.get(a.id, 0)}
            for a in admins
        ], 'past_assignees': [{'id': p.id, 'name': p.name} for p in past]})
