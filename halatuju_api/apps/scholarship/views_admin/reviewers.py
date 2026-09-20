"""Reviewers: the workload maths, the roster, the pause and programme controls, own profile.

Moved verbatim from the package root at code health H12. Part of the `views_admin`
package: every name below is re-exported from `views_admin/__init__.py`, so `urls.py`
and every importer are unchanged.

⚠ TWO SPANS of the old root (lines 2285-2681 and 3492-3538). They were not adjacent there, but
they are one domain, and each span is byte-identical to the lines it came from.
"""
import logging

from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response
from apps.courses.models import PartnerAdmin
from ..models import ReviewerProfile, ScholarshipApplication
from ..serializers_admin import ReviewerProfileSerializer
from ..services import PauseError, set_paused

from .base import _AdminBase
from .gift_programmes import AdminProgrammeListView


# ⚠ THE PACKAGE'S name, spelled out — never `__name__`. A submodule logger reads
# `apps.scholarship.views_admin.<module>` and drops every audit line it carries out
# of the Cloud Logging scrape metric. Guarded by `AuditLoggerNameTest` (H11).
logger = logging.getLogger('apps.scholarship.views_admin')


#: Which languages count as "can review in this" — conversational or better. Mirrors
#: `AdminAssignableAdminsView.langs`; both read `ReviewerProfile`, so keep them in step.
_REVIEW_FLUENCY = ('conversational', 'fluent')

#: An application still waiting for this reviewer's verdict. Narrower than "not decided":
#: `ASSIGNABLE_STATUSES` is where a review is actually outstanding.
_REVIEWER_OPEN_STATUSES = ('profile_complete', 'interviewing')

#: A decided case that went FORWARD. `recommended` is the reviewer's own verdict; the rest are the
#: stages a recommended student passes through afterwards, and a case that reached them was
#: recommended on the way.
_REVIEWER_PROGRESSED_STATUSES = ('recommended', 'awarded', 'active', 'maintenance', 'closed')


def _reviewer_languages(admin):
    rp = getattr(admin, 'reviewer_profile', None)
    if rp is None:
        return []
    return [code for code, lvl in (('en', rp.english_fluency),
                                   ('ms', rp.bm_fluency),
                                   ('ta', rp.tamil_fluency)) if lvl in _REVIEW_FLUENCY]


def _median_days(values):
    """Median, not mean — with 13 reviewers and single-digit caseloads one slow case drags a mean
    somewhere no real turnaround sits. Returns None for an empty list rather than 0, because
    "no reviews yet" and "instant" must not render the same."""
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return round(ordered[mid], 1)
    return round((ordered[mid - 1] + ordered[mid]) / 2, 1)


def _reviewer_workloads(admins, *, organisation_id=None, programme=None, cohort=None):
    """`{admin_id: {...figures}}` for every reviewer, in ONE query, grouped in Python.

    ⚠ NOT `annotate()`. Two counts over two multi-valued relations multiply each other, and
    `Sum(distinct=True)` — the reflex cure — is wrong for a sum (see `AdminSponsorListView` and
    `test_sponsor_detail.test_money_and_students_do_not_inflate_each_other`). Grouping a few hundred
    rows in Python cannot fan out at all, so the class of bug is absent rather than guarded against.

    ⚠ **EVERY DECIDED CASE ASSIGNED TO THEM COUNTS — including one somebody else recorded the
    verdict on** (owner, 2026-08-02). The first cut excluded those, reasoning that another person's
    judgement should not land on a volunteer's record. That was wrong, and production said so:
    application #13 was assigned to Balan, HE interviewed the student and submitted his findings,
    and only the final verdict click was the owner's. Excluding it erased a case he genuinely
    reviewed and left a footnote nobody could act on. Who pressed the button is an attribution
    detail for the audit trail; the OUTCOME belongs on the record of whoever did the review — which
    is exactly why `rejected_after_review` is a band of its own and not folded into `declined`.

    ⚠ The four outcome bands **partition** the decided cases, so they always sum to `completed`.
    Before `awaiting_qc` existed the bar quietly fell short of the figure printed above it. If a new
    status ever escapes all four, `test_the_bands_account_for_every_decided_case` fails rather than
    the screen silently under-reporting.

    ⚠ **`programme` NARROWS ALONGSIDE THE ORGANISATION FILTER, NEVER INSTEAD OF IT** (2026-09-15,
    for the Programme Overview's `mine.pace`). The organisation stays the SECURITY fence and the
    gift is a restriction inside it; the Reviewers surface passes no gift and is byte-unchanged.
    The pair below is the Applications list's own (`views_admin.py:380`) so a reviewer's pace on
    a gift counts exactly the cases that gift's list shows — `ScholarshipApplication.programme` is
    set once at first save, so a cohort later moved between gifts would otherwise read as empty.
    """
    ids = [a.id for a in admins]
    if not ids:
        return {}
    rows = ScholarshipApplication.objects.filter(assigned_to_id__in=ids)
    if organisation_id is not None:
        # org-fence: the caller is a non-super, so only their own tenant's applications count.
        rows = rows.filter(owning_organisation_id=organisation_id)
    if programme is not None:
        rows = rows.filter(Q(programme=programme) | Q(cohort__programme=programme))
    if cohort is not None:
        # The intake round inside the gift (Overview phase 2) — narrows, never widens; the
        # Reviewers surface passes none and is byte-unchanged.
        rows = rows.filter(cohort=cohort)
    by_email = {a.id: (a.email or '').strip().lower() for a in admins}
    out = {i: {'open_now': 0, 'completed': 0, 'recommended': 0, 'declined': 0,
               'rejected_after_review': 0, 'awaiting_qc': 0, 'unaccounted': 0, '_days': []}
           for i in ids}
    for aid, status, assigned_at, decided_at, verdict in rows.values_list(
            'assigned_to_id', 'status', 'assigned_at', 'verdict_decided_at', 'officer_verdict'):
        slot = out[aid]
        if decided_at is None:
            if status in _REVIEWER_OPEN_STATUSES:
                slot['open_now'] += 1
            continue
        slot['completed'] += 1
        if status in _REVIEWER_PROGRESSED_STATUSES:
            slot['recommended'] += 1
        elif status == 'rejected':
            # ⚠ THE SPLIT READS THE RECORDED VERDICT, NOT `rejected_by`. Keying on who stamped the
            # rejection is WRONG and shipped wrong on 2026-08-02: a reviewer's decline always routes
            # through QC, and QC ACCEPTING that decline stamps `rejected_by` with the QC's name. So
            # "the rejector is not the reviewer" is the ORDINARY path for a decline, not the rare
            # one — it mislabelled 6 of BrightPath's 13 rejections, telling five volunteers they had
            # been overruled when they had simply declined a student and been agreed with.
            #
            # An overturn is the case where the reviewer said ACCEPT and the student was rejected
            # anyway. That claim needs positive evidence, so anything else — a decline, a blank
            # verdict, a draft — counts as their own decline rather than an accusation.
            # (`officerCockpit.rejectionTrail` already read it this way; this now agrees with it.)
            if (verdict or {}).get('overall') == 'accept':
                slot['rejected_after_review'] += 1
            else:
                slot['declined'] += 1
        elif status == 'interviewed':
            slot['awaiting_qc'] += 1
        else:
            # A decided case in none of the bands above. Counted so the arithmetic still closes and
            # a test can see it; today this is always 0.
            slot['unaccounted'] += 1
        if assigned_at:
            slot['_days'].append((decided_at - assigned_at).total_seconds() / 86400.0)
    for slot in out.values():
        slot['turnaround_days'] = _median_days(slot.pop('_days'))
    return out


def _reviewer_dict(admin, work):
    """One row of the reviewers table. Allowlist — an exact-key-set test pins it.

    ⚠ NO corrections figure here, by decision (2026-08-02). See `reopen.reviewer_reopens`.
    """
    return {
        'id': admin.id,
        'name': admin.name,
        'email': admin.email,
        'role': 'super' if admin.is_super else admin.role,
        'languages': _reviewer_languages(admin),
        'open_now': work['open_now'],
        'completed': work['completed'],
        'turnaround_days': work['turnaround_days'],
        'paused': admin.paused_at is not None,
        'paused_at': admin.paused_at,
        # ⚠ REVOKED IS NOT PAUSED, AND THE TABLE HAS TO SAY WHICH (2026-09-09). Paused means
        # stepped back from NEW work and still able to sign in; revoked means the account is
        # closed. The staff list served `is_active` and this one did not, so the two screens
        # showing the same people could disagree — the same drift that made one say Active while
        # the other said Paused until 2026-08-03.
        'is_active': admin.is_active,
        # ⚠ NULL IS "NOT RECORDED", NEVER "never signed in" — the backfill is best-effort and
        # everybody predating the column is empty. 20 of 21 staff carry a value on production; the
        # screen must say "not recorded" rather than accuse somebody of never turning up.
        'last_seen_at': admin.last_seen_at,
        # ⚠ THE GIFT COLUMN IS BACK, AND ITS OWN TRIGGER IS WHY (S-ASSIGN, 2026-09-04). This
        # used to be an explicit ABSENCE: "with one programme every reviewer serves it, so the
        # column could only ever say one thing… it returns when a second programme exists". The
        # owner created a second gift on 2026-09-03, so the condition that ruling named has
        # fired. The old note is rewritten rather than deleted so the reasoning survives.
        #
        # ⚠ NULL MEANS EVERY GIFT and is the permissive default — every one of the 17 org-scoped
        # staff on production still has it, and there is NO BACKFILL. A blank here is "as
        # before", never a missing value; the screen must not render it as one.
        'programme_id': admin.programme_id,
        'programme_name': (admin.programme.name_en or admin.programme.code)
                          if admin.programme_id else '',
    }


class _ReviewersBase(_AdminBase):
    """Shared gate + fence for the reviewers surface (Organisation → Reviewers).

    Same role set as the organisation's other staff-facing screens. **List-fenced**: a `PartnerAdmin`
    carries `owning_organisation`, so a non-super sees only their own organisation's people.
    """

    def _side(self, request):
        admin = self.get_admin(request)
        if not admin:
            return None, None, self._deny()
        if not (admin.is_super or admin.role in ('org_admin', 'admin', 'finance')):
            return None, None, self._deny_role()
        org_id = None if self.has_role(admin, 'super') else admin.owning_organisation_id
        return admin, org_id, None

    def _reviewers(self, org_id, include_revoked=False):
        """The organisation's reviewers. ACTIONABLE ones by default; the LIST and the DETAIL page
        pass ``include_revoked`` and get the closed accounts too.

        ⚠ **THE SPLIT IS NEW (2026-09-09) AND REVERSES A NARROWER RULING ON PURPOSE.** Until now a
        revoked reviewer was absent everywhere — *"revoking is an account kill-switch; they cannot
        act, so they are not staff to look at"*. That held while revoking happened on another
        screen. The owner has now asked for Revoke on this table, and a kill-switch you cannot see
        or undo from the only screen that lists people is a trap: revoke somebody and they vanish,
        with no way back. So they stay LISTED, marked revoked, with Restore beside them.
        **What did NOT change is what they may do:** pause and set-gift still take the default and
        404 on a revoked account, and assignment reads its own `is_active=True` queryset
        (`AdminAssignableView`), so a revoked reviewer can still never be handed a case.
        """
        from django.db.models import Q
        # org-fence: narrowed by owning_organisation for a non-super (org_id set by `_side`).
        qs = (PartnerAdmin.objects
              .filter(Q(is_super_admin=True) | Q(role__in=['reviewer', 'qc']))
              .select_related('reviewer_profile', 'programme').order_by('name'))
        if not include_revoked:
            qs = qs.filter(is_active=True)
        if org_id is not None:
            qs = qs.filter(owning_organisation_id=org_id, is_super_admin=False)
        return qs

    def _gift_choices(self, admin):
        """The gifts this admin may scope a reviewer to.

        INCLUDES inactive gifts, for the same reason the sponsor accept panel does: a gift is
        created switched off and STAFFED before it opens, so an active-only list would offer
        nothing at exactly the moment somebody needs to put a reviewer on the new gift.
        """
        return [
            {'id': p.id, 'code': p.code, 'name': p.name_en or p.code, 'is_active': p.is_active}
            for p in AdminProgrammeListView()._programmes_for(admin).order_by('code')
        ]


class AdminReviewerListView(_ReviewersBase):
    """GET admin/reviewers/ — the people who review this organisation's applications.

    Request #10. Staff (`/admin/organisation/staff`) invites and revokes; this is where you look at
    somebody: what they carry, how long cases sit with them, and how their cases ended.
    """

    def get(self, request):
        admin, org_id, err = self._side(request)
        if err:
            return err
        rows = list(self._reviewers(org_id, include_revoked=True))
        work = _reviewer_workloads(rows, organisation_id=org_id)
        return Response({
            'reviewers': [_reviewer_dict(r, work[r.id]) for r in rows],
            # The gift choices behind the per-reviewer picker. Sent with the LIST so the screen
            # can offer the change wherever a reviewer is shown, without a second round trip.
            'programmes': self._gift_choices(admin),
        })


class AdminReviewerDetailView(_ReviewersBase):
    """GET admin/reviewers/<pk>/ — one reviewer, whole.

    ⚠ The contact block is a deliberate PII WIDENING and is deliberately PARTIAL. `ReviewerProfile`
    also holds a home address; an org_admin assigning work has no reason to read it, so it is not
    serialised here. Recorded in `docs/scholarship/role-matrix.md`.
    """

    def get(self, request, pk):
        admin, org_id, err = self._side(request)
        if err:
            return err
        # org-fence: `_reviewers` is already narrowed, so a cross-org id 404s rather than resolving.
        # ⚠ 404, never 403 — a 403 would confirm that another tenant's staff member exists.
        # ⚠ `include_revoked`: a closed account's record must still OPEN, or Restore on the list
        # would send somebody to a 404 (2026-09-09).
        target = self._reviewers(org_id, include_revoked=True).filter(pk=pk).first()
        if target is None:
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        work = _reviewer_workloads([target], organisation_id=org_id)[target.id]
        rp = getattr(target, 'reviewer_profile', None)
        from .. import reopen as reopen_service
        payload = _reviewer_dict(target, work)
        payload.update({
            # The four outcome bands. They partition the decided cases, so they sum to `completed`
            # — the bar and the figure above it can never disagree.
            'recommended': work['recommended'],
            'declined': work['declined'],
            'rejected_after_review': work['rejected_after_review'],
            'awaiting_qc': work['awaiting_qc'],
            'created_at': target.created_at,
            'qualification': getattr(rp, 'highest_qualification', '') or '',
            'university': getattr(rp, 'university', '') or '',
            'graduation_year': getattr(rp, 'graduation_year', None),
            'field_of_study': getattr(rp, 'field_of_study', '') or '',
            'phone': getattr(rp, 'phone', '') or '',
            'share_phone_with_students': bool(getattr(rp, 'share_phone_with_students', False)),
            'reopens': [
                {'id': r.id,
                 'application_id': r.application_id,
                 'reason': r.reason,
                 'reopened_by': r.reopened_by,
                 'at': r.closed_at or r.created_at}
                for r in reopen_service.reviewer_reopens(target, organisation_id=org_id)
            ],
            'programmes': self._gift_choices(admin),
        })
        return Response(payload)


class AdminReviewerPauseView(_ReviewersBase):
    """POST admin/reviewers/<pk>/pause/ {paused: bool} — step somebody back, or bring them back.

    The complement of the reviewer's own switch on their profile. It exists because a volunteer who
    has gone quiet cannot always press it themselves, and because a control with no way back is a
    one-way conversation — un-pause is the same endpoint with `false`.

    ⚠ **NARROWER than reading this surface.** `admin` and `finance` may look at the reviewers list;
    changing who gets work is staff management, which the role matrix gives to super + org_admin
    only. The list gate would have admitted all four, so this re-gates rather than inheriting.
    """

    def post(self, request, pk):
        admin, org_id, err = self._side(request)
        if err:
            return err
        if not (admin.is_super or self.has_role(admin, 'org_admin')):
            return self._deny_role()
        # org-fence: `_reviewers` is already narrowed, so a cross-org id 404s rather than resolving.
        # ⚠ NO `include_revoked` HERE, deliberately: pausing a closed account is meaningless, so a
        # revoked target 404s exactly as it did before.
        target = self._reviewers(org_id).filter(pk=pk).first()
        if target is None:
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        try:
            set_paused(target, request.data.get('paused'))
        except PauseError as e:
            return Response({'error': e.code, 'code': e.code},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({'id': target.id,
                         'paused': target.paused_at is not None,
                         'paused_at': target.paused_at})


class AdminReviewerProgrammeView(_ReviewersBase):
    """POST admin/reviewers/<pk>/programme/ {programme_id} — which gift this person covers.

    ⚠ **A NARROWING, NOT A FENCE, AND IT MUST NEVER BECOME ONE.** The organisation boundary is
    `_org_scoped`/`_org_allows`; this only decides who is OFFERED a case. A reviewer scoped to
    Sabah who is somehow handed a flagship case still passes the fence and can still work it —
    deliberately, because the alternative is stranding an in-flight review the day somebody
    tidies a dropdown.

    ⚠ **`programme_id` NULL / absent CLEARS IT, and clearing means EVERY GIFT** — the permissive
    default and what all 17 org-scoped staff on production have. So this endpoint can only ever
    narrow or widen the offer; it can never lock somebody out of work they already hold.

    ⚠ **NARROWER THAN READING THIS SURFACE**, exactly like `AdminReviewerPauseView`: `admin` and
    `finance` may look at the reviewers list, but deciding who gets which work is staff
    management, which the role matrix gives to super + org_admin. The list gate would admit all
    four, so this re-gates rather than inheriting.

    The gift is resolved through `_programmes_for`, so a gift outside the caller's organisation
    is **404, never 403** — a 403 would confirm the other tenant's gift exists.
    """

    def post(self, request, pk):
        admin, org_id, err = self._side(request)
        if err:
            return err
        if not (admin.is_super or self.has_role(admin, 'org_admin')):
            return self._deny_role()
        # org-fence: `_reviewers` is already narrowed, so a cross-org id 404s rather than resolving.
        target = self._reviewers(org_id).filter(pk=pk).first()
        if target is None:
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)

        asked = request.data.get('programme_id')
        programme = None
        if asked not in (None, ''):
            programme = AdminProgrammeListView()._programmes_for(admin).filter(pk=asked).first()
            if programme is None:
                return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)

        old = target.programme.code if target.programme_id else ''
        target.programme = programme
        target.save(update_fields=['programme'])
        logger.info('AUDIT reviewer_programme_set admin=%s old=%s new=%s by=%s',
                    target.id, old or '(every gift)',
                    (programme.code if programme else '(every gift)'), admin.email or '')
        return Response({
            'id': target.id,
            'programme_id': target.programme_id,
            'programme_name': (programme.name_en or programme.code) if programme else '',
        })


class AdminReviewerSystemEmailsView(_ReviewersBase):
    """GET admin/reviewers/system-emails/ — the reviewer emails nobody can edit, rendered in full.

    Owner ruling, 2026-08-02: *"their existence and content are known to the org_admin. If not
    specified, they'll exist in the background without anyone paying attention to them until
    something breaks."* So the Emails tab shows the editable five AND these seven, and the
    difference between the two lists is stated rather than left to be discovered.

    ⚠ **THE BODIES COME FROM THE SENDERS' OWN BUILDERS**, not from a copy of the prose kept here or
    on the front end — see `reviewer_system_emails`. Read-only by construction: there is no PATCH,
    no switch and no template row behind any of it.

    Carries NO organisation data — the same seven strings for every tenant — so the fence has
    nothing to narrow. It is gated to the reviewers-surface audience anyway, because a screen about
    our own volunteers belongs to the people who run them.
    """

    def get(self, request):
        admin, org_id, err = self._side(request)
        if err:
            return err
        from .. import reviewer_system_emails
        return Response({'emails': reviewer_system_emails.rendered()})


class ReviewerProfileView(_AdminBase):
    """GET/PATCH /api/v1/admin/reviewer-profile/ — a reviewer's OWN credentials +
    contact details (F6). Self-scoped: it only ever reads/writes the calling admin's
    own row (resolved from the JWT via get_admin), so one admin can never see or edit
    another's. Reviewer + super only — a viewer (read-only staff) gets 403. The
    sensitive PII (phone/address) lives in its own table and is exposed by no other
    serializer."""

    def _payload(self, profile, admin):
        """The profile, plus the pause state — which lives on `PartnerAdmin`, not here.

        ⚠ `paused` is deliberately NOT a `ReviewerProfile` column. Pause governs assignment, and
        assignment reads `PartnerAdmin`; a second copy on the profile row would be a second truth
        to drift. It rides along on this payload because ONE screen owns "how I take part", and
        splitting it across two calls would be an implementation detail leaking into the UI.
        """
        data = dict(ReviewerProfileSerializer(profile).data)
        data['paused'] = admin.paused_at is not None
        data['paused_at'] = admin.paused_at
        return data

    def get(self, request):
        admin, err = self._require_reviewer(request)
        if err:
            return err
        profile, _ = ReviewerProfile.objects.get_or_create(partner_admin=admin)
        return Response(self._payload(profile, admin))

    def patch(self, request):
        admin, err = self._require_reviewer(request)
        if err:
            return err
        profile, _ = ReviewerProfile.objects.get_or_create(partner_admin=admin)
        # Split off `paused` before the serializer sees it — it belongs to a different model, and
        # an unknown key would otherwise be silently ignored, leaving the reviewer pressing a
        # switch that does nothing.
        body = {k: v for k, v in request.data.items() if k not in ('paused', 'paused_at')}
        serializer = ReviewerProfileSerializer(profile, data=body, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        if 'paused' in request.data:
            try:
                set_paused(admin, request.data.get('paused'))
            except PauseError as e:
                return Response({'error': e.code, 'code': e.code},
                                status=status.HTTP_400_BAD_REQUEST)
        return Response(self._payload(profile, admin))
