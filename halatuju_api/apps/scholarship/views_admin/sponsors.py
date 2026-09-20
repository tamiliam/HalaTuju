"""Sponsors: the queue, the NRIC lock, the review decision and the sponsor detail payload.

Moved verbatim from the package root at code health H12. Part of the `views_admin`
package: every name below is re-exported from `views_admin/__init__.py`, so `urls.py`
and every importer are unchanged.
"""
import logging

from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from .. import pool
from ..models import Donation, ScholarshipApplication, Sponsor, Sponsorship
from ..serializers_admin import AdminApplicationDetailSerializer
from .. import sponsorship as sponsorship_service

from .base import _AdminBase
from .gift_programmes import AdminProgrammeListView

from .credits import _credit_dict


# ⚠ THE PACKAGE'S name, spelled out — never `__name__`. A submodule logger reads
# `apps.scholarship.views_admin.<module>` and drops every audit line it carries out
# of the Cloud Logging scrape metric. Guarded by `AuditLoggerNameTest` (H11).
logger = logging.getLogger('apps.scholarship.views_admin')


def _sponsor_dict(s):
    return {
        'id': s.id, 'name': s.name, 'email': s.email, 'phone': s.phone,
        'source': s.source, 'organisation': s.organisation,
        'note': s.note, 'status': s.status, 'reviewed_at': s.reviewed_at,
        'reviewed_by': s.reviewed_by, 'created_at': s.created_at,
        # Added 2026-07-27 so the list can be scanned rather than merely read: `last_seen_at`
        # answers "is this sponsor still with us" (nothing recorded it before), and `given`
        # is what an admin actually looks for. `given` + `students` are annotated THROUGH THE
        # SAME FENCE as the detail page — an org sees its own share, never another tenant's.
        'last_seen_at': s.last_seen_at,
        'given': sponsorship_service._amount_str(getattr(s, 'given_total', None)),
        # Money given says what they have put in; students says what it is DOING. The pair is
        # the whole point of the row — a large balance with no students is the case an admin
        # most needs to spot. Counted the same way the detail page's per-wallet `students` is
        # (HOLDING allocations), so the list and the page can never disagree.
        'students': getattr(s, 'students_total', None) or 0,
    }


class AdminSponsorListView(_AdminBase):
    """Phase E: GET .../admin/sponsors/[?status=pending] — self-registered sponsor
    ACCOUNTS for vetting (distinct from the old sponsor-interest leads)."""
    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        # Matrix (2026-07-23): the Sponsors surface is visible to super / org_admin /
        # Admin-General / finance. qc + reviewer are refused (nav + endpoint). Finance sees
        # sponsors READ-ONLY — who funds the programme is finance's business; approving them
        # is not, so the review gate (AdminSponsorReviewView) stays super/org_admin.
        if not (admin.is_super or admin.role in ('org_admin', 'admin', 'finance')):
            return self._deny_role()
        # Deterministic ordering (TD audit 2026-06-14) — without it the row order was
        # undefined. Full pagination is deferred: these are low-cardinality admin tables and
        # the sponsors table FE does not yet handle a paged envelope (would truncate to 25).
        # tenancy: cross-org by design until Sprint 10 (D-1). A Sponsor is a platform-
        # level account (no owning_organisation; may fund across programmes), so the
        # vetting list is intentionally NOT org-fenced. Sponsor accounts carry no
        # student identity, so this is not an applicant-data leak.
        qs = Sponsor.objects.all().order_by('-id')
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        # `given` per row in ONE query (no N+1 over the list). CONFIRMED money only — the
        # same rule `visible_donations` applies — and org-fenced for a non-super caller, so
        # the account stays cross-org while the MONEY inside it does not.
        money = Q(donations__status=Donation.STATUS_CONFIRMED)
        if not self.has_role(admin, 'super'):
            money &= Q(donations__programme__organisation_id=admin.owning_organisation_id)
        qs = qs.annotate(given_total=Sum('donations__amount', filter=money))

        # Students is counted in its OWN query, deliberately NOT a second annotate() on the
        # line above: two multi-valued joins in one queryset multiply each other, and the
        # usual `distinct=True` cure is wrong for a Sum (it would collapse two credits of the
        # same amount into one). One extra aggregate query, no N+1, no inflated money.
        held = Q(status__in=Sponsorship.HOLDING)
        if not self.has_role(admin, 'super'):
            # Students fence on the APPLICATION's owner, not the programme's — a sponsorship
            # belongs to a student an organisation owns. Same split as the detail page.
            held &= Q(application__owning_organisation_id=admin.owning_organisation_id)
        rows = list(qs)
        # org-fence: `held` carries application__owning_organisation_id for a non-super
        # caller (built above), so this count never crosses a tenant boundary.
        counts = dict(
            Sponsorship.objects.filter(held, sponsor__in=rows)
            .values('sponsor_id')
            .annotate(n=Count('id'))
            .values_list('sponsor_id', 'n')
        )
        for s in rows:
            s.students_total = counts.get(s.id, 0)
        return Response({'sponsors': [_sponsor_dict(s) for s in rows]})


class AdminSponsorPendingCountView(_AdminBase):
    """GET .../admin/sponsors/pending-count/ — {count} of sponsor accounts awaiting vetting.
    A lean COUNT for the nav + Administration-hub badges (so an always-loaded nav needn't fetch the
    full sponsor list on every page). Same role-gate as the list (super / org_admin /
    Admin-General / finance) — kept deliberately in lockstep so a role that can open the list
    never 403s on its badge; cross-org by design (a sponsor is a platform-level account)."""
    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not (admin.is_super or admin.role in ('org_admin', 'admin', 'finance')):
            return self._deny_role()
        return Response({'count': Sponsor.objects.filter(status='pending').count()})


class AdminReleaseNricLockView(_AdminBase):
    """POST .../applications/<pk>/release-nric-lock/ {reason} — the break-glass. SUPER ONLY.

    An IC lock is one-way by design: once the uploaded MyKad confirms the typed number, the
    student can never change it and neither can an admin. That is right, and it has one failure
    mode with a victim who did nothing wrong.

    Somebody uploads a card that is not theirs — a sibling's, say — and types that card's name
    and number so the two agree. It locks. Their own results slip then carries a different name,
    fails the academic gate, and the account is unusable, so they abandon it. **But the abandoned
    account still holds a live claim on a real person's IC number.** When the true owner
    registers, uniqueness refuses them their own number, and without this endpoint nobody can
    free it — they cannot apply at all.

    So this is a housekeeping power over an ORPHANED CLAIM, not an appeal against a decision.
    It clears ``nric_verified`` so the number stops blocking; it does not blank the number, does
    not touch the application, and does not re-open anything else.

    SUPER ONLY (owner, 2026-07-29), deliberately narrower than the gate that TAKES the lock —
    verify-&-accept admits org_admin, qc and the assigned reviewer. Setting an identity is
    routine casework; unsetting one is not.

    The reason is mandatory and goes to the audit log. There is no audit TABLE in this system
    (``audit.py`` is verdict-override metrics), so the structured log is the record — which is
    also why this cannot be done with a direct database write.

    ⚠ **This reaches the lock THROUGH an application, while the lock itself lives on the
    PROFILE.** That is safe only because both routes to a lock require an application — reading
    an uploaded MyKad (the document hangs off one) and verify-&-accept (a bursary review). So a
    locked profile always has an application to address it by, and production agrees: 0 locked
    profiles without one, against 643 course-selector profiles that have no application at all.

    **If you ever add a route that locks a profile WITHOUT an application** — the obvious
    candidate is confirming a course-selector identity for Lentera's longitudinal tracking,
    which is what ``nric_verified`` was originally added for — then this endpoint can no longer
    reach it: there is no ``pk`` to put in the URL, and that student's lock becomes permanent
    with no escape. Re-address it by profile at that point, and note it widens the reachable set
    from 143 records to 786, which is why it is not built that way today.

    The note sits here rather than in a debt register on purpose: nothing is owed while the
    invariant holds, and this is where somebody would be standing when they broke it.
    """
    def post(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not self.has_role(admin, 'super'):
            return self._deny_role()
        # Unfenced BY CONSTRUCTION: the gate above admits super only, and a super's scope is
        # every organisation, so no tenant dimension is left to narrow. Widen this to org_admin
        # and it needs `self._org_scoped(...)` like every other application lookup.
        # org-fence: super-only endpoint — no org dimension
        app = ScholarshipApplication.objects.filter(pk=pk).select_related('profile').first()
        if app is None or app.profile is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        reason = (request.data.get('reason') or '').strip()
        if not reason:
            return Response({'error': 'A reason is required to release an identity lock.',
                             'code': 'reason_required'},
                            status=status.HTTP_400_BAD_REQUEST)
        profile = app.profile
        if not profile.nric_verified:
            return Response({'error': 'This IC is not locked.', 'code': 'not_locked'},
                            status=status.HTTP_400_BAD_REQUEST)
        profile.nric_verified = False
        profile.save(update_fields=['nric_verified'])
        # The record of who unset an identity, and why. Deliberately logged BEFORE anything can
        # fail afterwards, and with the application id rather than the NRIC — the log must not
        # become a place identity numbers accumulate.
        logger.info('AUDIT nric_lock_released admin_id=%s app_id=%s reason=%r',
                    admin.id, pk, reason[:200])
        return Response(AdminApplicationDetailSerializer(app).data)


class AdminSponsorReviewView(_AdminBase):
    """Phase E: POST .../admin/sponsors/<pk>/review/ {action: approve|reject|suspend}
    — vet a sponsor account. Matrix (2026-07-15): sponsor vetting is a super or ORG_ADMIN
    power (migrated off the old reviewer gate); stamps who/when."""
    _ACTION_STATUS = {'approve': 'approved', 'reject': 'rejected', 'suspend': 'suspended'}

    def post(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not (admin.is_super or admin.role == 'org_admin'):
            return self._deny_role()
        sponsor = Sponsor.objects.filter(pk=pk).first()
        if sponsor is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        new_status = self._ACTION_STATUS.get(request.data.get('action'))
        if not new_status:
            return Response({'error': 'bad_action'}, status=status.HTTP_400_BAD_REQUEST)
        previous_status = sponsor.status
        sponsor.status = new_status
        sponsor.reviewed_at = timezone.now()
        sponsor.reviewed_by = admin.email
        sponsor.save(update_fields=['status', 'reviewed_at', 'reviewed_by', 'updated_at'])
        # Vetting the ACCOUNT settles their membership of the gift they registered into, which is
        # what migration 0123 did for every sponsor who predates the programme layer. Without it
        # an approved sponsor sees no students and can hold no wallet.
        #
        # ⚠ THE SAME GIFT THE REGISTRATION RESOLVED, AND ONLY THAT ONE. `signup_programme_for` is
        # stable across both moments because the invitation outlives the registration — so the
        # account's own row settles and a SECOND gift's membership, which is that organisation's
        # separate acceptance decision, is never flipped as a side-effect of account vetting.
        sponsorship_service.sync_account_membership(
            sponsor, sponsorship_service.signup_programme_for(sponsor), vetted_by=admin.email)
        # S3: until now this endpoint flipped a field and returned — eight people on production
        # were approved and never told. `previous_status` is read BEFORE the write because an
        # approval that lifts a suspension is a REINSTATEMENT, and the two read very differently
        # to the person receiving them. Dark until the template is switched on; best-effort.
        from .. import sponsor_notify
        sponsor_notify.send_vetting_outcome(sponsor, new_status, previous_status=previous_status)
        return Response(_sponsor_dict(sponsor))


def _chain_organisations(programmes, credit_rows, membership_rows):
    """Every organisation whose finance setting governs a credit on this screen.

    Three sources, because a credit can exist before its wallet does: a wallet appears only
    once a credit is CONFIRMED (`visible_donations`), so a freshly-recorded credit awaiting
    its signatures — the one whose chain the screen must draw correctly — belongs to a
    programme with no wallet row. The approved memberships cover the step before that, when
    the maker is about to record a first credit into a gift.
    """
    orgs = {p.organisation for p in programmes if p is not None}
    orgs |= {c.programme.organisation for c in credit_rows if c.programme_id}
    orgs |= {m.programme.organisation for m in membership_rows
             if m.programme_id and m.status == 'approved'}
    return {o for o in orgs if o is not None}


def _sponsor_detail_dict(sponsor, admin, base):
    """The one sponsor, built field-by-field — NEVER a ModelSerializer.

    An exact-key-set test pins this payload, so a column added to `Sponsor` later cannot
    reach an admin screen (or a log, or a CSV) by accident. Same reasoning as the sponsor
    pool's allowlist, applied in the other direction.

    **The account is platform-level; the money and the students inside it are NOT.** A
    `Sponsor` deliberately has no organisation (`AdminSponsorListView` is classified
    cross-org-by-design), but a credit belongs to a programme owned by an org, and a
    sponsorship belongs to an application owned by an org. So identity is shown whole and
    everything with money or a student in it is fenced through ``base`` — the same split
    the credit endpoints already make. `fenced` tells the screen to say whose share it is.
    """
    from .. import payments as payments_service

    programmes = base.programmes
    ledger = [
        {
            'programme_id': row['programme'].id if row['programme'] else None,
            'programme_name': getattr(row['programme'], 'name_en', '') or '',
            'given': row['given'],
            'committed': row['committed'],
            'available': row['available'],
            'credits': row['credits'],
            'students': row['students'],
        }
        for row in sponsorship_service.programme_ledger(sponsor)
        if base.covers(row['programme'])
    ]

    # The credits ledger shows EVERY state including draft/cancelled — an admin has to see
    # an unsigned credit in order to sign it. That is the opposite of the sponsor-facing
    # read, which narrows through `visible_donations`; the tiles above use that seam, this
    # list deliberately does not. Both are correct for their audience.
    #
    # REUSES `_credit_dict` (the credit endpoints' own allowlist) rather than spelling the
    # fields again — two copies of a money payload is two places for the next column to be
    # added to only one.
    # org-fence: fenced on programme→organisation via base.credits(), never all donations.
    credit_rows = list(base.credits())
    credits = [_credit_dict(d) for d in credit_rows]

    membership_rows = [
        m for m in sponsor.programme_memberships.select_related('programme__organisation')
        if base.covers(m.programme)
    ]

    sponsorships = [
        {
            'id': sp.id,
            'application_id': sp.application_id,
            'ref': pool.pool_ref(sp.application_id),
            'programme_name': getattr(sp.application.programme, 'name_en', '') or '',
            'amount': str(sp.amount),
            'status': sp.status,
            'offered_at': sp.offered_at,
            'decided_at': sp.decided_at,
        }
        for sp in base.sponsorships()
    ]

    return {
        'id': sponsor.id,
        'name': sponsor.name,
        'email': sponsor.email,
        'phone': sponsor.phone,
        'organisation': sponsor.organisation,
        'source': sponsor.source,
        'note': sponsor.note,
        'status': sponsor.status,
        'is_trusted': sponsor.is_trusted,
        'created_at': sponsor.created_at,
        'reviewed_at': sponsor.reviewed_at,
        'reviewed_by': sponsor.reviewed_by,
        'last_seen_at': sponsor.last_seen_at,
        'consent_at': sponsor.consent_at,
        'consent_version': sponsor.consent_version,
        'notify_frequency': sponsor.notify_frequency,
        'last_digest_sent_at': sponsor.last_digest_sent_at,
        'programmes': ledger,
        'credits': credits,
        'sponsorships': sponsorships,
        'referrals': [
            {
                'id': r.id,
                'invitee_name': r.invitee_name,
                'invitee_email': r.invitee_email,
                'status': r.status,
                'created_at': r.created_at,
                'joined_at': r.joined_at,
            }
            for r in sponsor.referrals_sent.all()
        ],
        'memberships': [
            {
                # `programme_id` is what the credit form posts (S2). It has to come from the
                # MEMBERSHIPS and not the wallet ledger above: `record_admin_credit` refuses
                # `sponsor_not_in_programme`, so the creditable set is "gifts they were
                # accepted into" — which includes a gift they hold no money in yet, and that
                # is exactly the case a FIRST credit is being recorded for.
                'programme_id': m.programme_id,
                'programme_name': getattr(m.programme, 'name_en', '') or '',
                'status': m.status,
                'vetted_by': m.vetted_by,
                'vetted_at': m.vetted_at,
            }
            for m in membership_rows
        ],
        # Every gift this ADMIN may accept the benefactor into — the choices behind the accept /
        # move panel. Deliberately NOT derived from `memberships` (which lists gifts they are
        # ALREADY in): the whole point of the panel is the gift they are not in yet.
        #
        # ⚠ `_programmes_for` INCLUDES INACTIVE gifts, and that is the case this exists for. A
        # second gift is created switched OFF and staffed before it opens, so a list of active
        # gifts would offer nothing at exactly the moment somebody needs to accept its first
        # benefactor — the defect the owner hit on their own first use of THE SHAPE.
        'assignable_programmes': [
            {'id': p.id, 'code': p.code, 'name': p.name_en or p.code,
             'is_active': p.is_active}
            for p in AdminProgrammeListView()._programmes_for(admin).order_by('code')
        ],
        # Live, never stored — appointing a finance admin arms the middle step of the credit
        # chain retroactively, so the screen must ask at read time, exactly as the sign
        # service does.
        #
        # Asked across the WALLETS, the CREDITS and the approved MEMBERSHIPS, not the wallets
        # alone. A wallet only exists once a credit is CONFIRMED (`visible_donations`), so a
        # first credit — recorded, then awaiting its signatures — belongs to a programme with
        # no wallet yet. Reading wallets only, the screen would draw a two-step chain and
        # offer an org_admin a countersign the service then refuses with
        # `finance_check_required`, which is exactly the mismatch this flag exists to prevent.
        'finance_check_required': any(
            payments_service.finance_check_required(org)
            for org in _chain_organisations(programmes, credit_rows, membership_rows)
        ),
        # True when this caller sees only their own organisation's share of the account, so
        # the screen can say so rather than implying it is the sponsor's whole giving record.
        'fenced': base.is_fenced,
    }


class _SponsorScope:
    """How much of one sponsor's money + students this caller may see.

    Super sees everything. Everyone else sees only what their organisation owns — the
    programmes it runs and the applications it owns. Built once per request so the three
    fenced reads cannot drift apart.
    """
    def __init__(self, sponsor, org_id, is_super):
        self.sponsor = sponsor
        self.org_id = org_id
        self.is_fenced = not is_super
        self.programmes = [
            p for p in sponsorship_service._wallet_programmes(sponsor)
            if self.covers(p)
        ]

    def covers(self, programme):
        if not self.is_fenced:
            return True
        # A NULL-programme wallet belongs to no organisation, so a fenced caller never sees
        # it. Bare test fixtures self-partition the same way the org fence does.
        return programme is not None and programme.organisation_id == self.org_id

    def credits(self):
        qs = self.sponsor.donations.select_related('programme').order_by('-created_at')
        if self.is_fenced:
            qs = qs.filter(programme__organisation_id=self.org_id)
        return qs

    def sponsorships(self):
        qs = (self.sponsor.sponsorships
              .select_related('application', 'application__programme')
              .order_by('-offered_at'))
        if self.is_fenced:
            qs = qs.filter(application__owning_organisation_id=self.org_id)
        return qs
