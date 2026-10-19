"""Staff accounts: `PartnerAdmin`.

Moved verbatim out of `models.py` (staff permissions Sprint 1, request #39, 2026-10-19), a
moves-only split: `models.py` is a ledgered oversize file (see `halatuju_api/CLAUDE.md`, `## Code
standards`) and sat at 1240 of its 1244 allowance, and Sprint 1 adds the `permissions` field here.
`models.py` re-exports the name at its foot, so every `from apps.courses.models import
PartnerAdmin` and every migration's `courses.PartnerAdmin` is unchanged. The only edit is that
the two foreign keys name `'PartnerOrganisation'` as a string — the same model, resolved by
Django's registry — because a module imported from the foot of `models.py` must not import
`models.py` back (the `models_stpm.py` precedent).
"""
from django.db import models


class PartnerAdmin(models.Model):
    """Admin user for a partner organisation. Separate from StudentProfile."""
    # Role categories. Kept ALONGSIDE is_super_admin (expand-contract): is_super_admin
    # is backfilled into role and still read by legacy code; a later TD drops it once
    # role is the sole source of truth.
    #   super    — PLATFORM superadmin (the owner). Everything, cross-org; the only role
    #              that sees the platform surfaces (Dashboard / Students directory / Course
    #              Data) — those are super-only from the surface-partition sprint (2026-07-15).
    #   admin    — a B40 staff role, org-scoped: sees its OWN organisation's B40 applications
    #              (read; write only where assigned). NO LONGER sees the platform Students/
    #              Dashboard/Course-Data surfaces (that admin-branch became super-only in the
    #              surface partition). "View-only admin" in the UI.
    #   org_admin — ORGANISATION superadmin (e.g. BrightPath's programme lead): org-wide B40
    #              READ + the QC gate + STAFF MANAGEMENT (invite/list/resend/revoke reviewers,
    #              admins, qc) for its OWN organisation only. Never cross-org, never the
    #              platform surfaces, never super. Includes QC powers (small-team compromise,
    #              owner decision 2026-07-15). UI label: "Organisation admin".
    #   partner  — a REFERRAL organisation rep: Dashboard + Students + Profile, scoped to their
    #              OWN referral org's students only (referral semantics, not the B40 tenant fence).
    #   reviewer — an individual volunteer: B40 Applications + Profile, scoped to the
    #              applicants ASSIGNED to them only; records the verdict → 'interviewed' (awaiting QC).
    #   qc       — quality control: reads its org's B40 applications but its only WRITE is the
    #              QC gate on an 'interviewed' case — Accept (→ recommended) or Reopen (→ back to
    #              the reviewer with comments). Cannot record verdicts / verify / interview.
    #   finance  — org FINANCE admin: the payment-run CHECKER (the middle signature between the
    #              maker and the approver), plus Payments read and the funding summary. NO B40
    #              scope at all (`_b40_scope` → 'none'): no applicant list, no cockpit, no
    #              documents, no income, no verdicts — its only student data is the
    #              award/paid/remaining/eWallet allowlist inside the Payments module. Sponsors
    #              view-only; Administration view-only. Never reviews, QCs or takes an
    #              assignment. **The chain's finance step is DORMANT until the organisation has
    #              ≥1 active finance admin** — evaluated live, never stored on the run.
    # ('viewer' retired 2026-06-09 → folded into 'admin'; 0 viewers existed on prod.)
    ROLE_CHOICES = [
        ('super', 'Super admin'),
        ('admin', 'Admin'),
        ('org_admin', 'Organisation admin'),
        ('partner', 'Partner'),
        ('reviewer', 'Reviewer'),
        ('qc', 'Quality control'),
        ('finance', 'Finance admin'),
    ]
    supabase_user_id = models.CharField(
        max_length=100, unique=True, null=True, blank=True,
        help_text='Set on first login via UID or email match',
    )
    org = models.ForeignKey(
        'PartnerOrganisation', on_delete=models.CASCADE,
        null=True, blank=True, related_name='admins',
        help_text='NULL for super admin',
    )
    # Platform tenancy (Sprint 3a): the organisation whose programme this staff
    # member works within — the ACCESS-CONTROL boundary for B40 applications.
    # DISTINCT from `org` above: `org` is the *referring* organisation (referral
    # attribution, used for the partner-students list + bursary witness), never for
    # access control. NULL = platform-level: `super` (global, sees every org) and
    # `partner` (no B40 access — `_b40_scope` returns 'none'). A non-super B40 staff
    # role (admin/reviewer/qc) is bound to exactly one owning organisation.
    owning_organisation = models.ForeignKey(
        'PartnerOrganisation', on_delete=models.PROTECT,
        null=True, blank=True, related_name='staff',
        help_text='Tenant org this staff member is scoped to for B40 access '
                  '(NULL = platform-level: super/partner). Never the referral org.',
    )
    # ⚠ NULL MEANS EVERY GIFT, AND THAT IS THE OWNER'S RULING (2026-09-04). Which gift a reviewer
    # covers is a NARROWING, not a fence: `owning_organisation` above is the boundary, and this
    # only says "offer this person the Sabah cases, not the flagship's". So NULL is the permissive
    # default, every one of the 17 org-scoped staff on production keeps working untouched, and
    # THERE IS NO BACKFILL — which is the point. Migration 0123 once populated a column for
    # everybody alive that day and nothing kept doing it for the next person; a default that means
    # "as before" cannot go stale that way (lessons.md, 2026-07-29).
    #
    # ⚠ ONE gift, not a list. With two gifts "NULL = both" covers every case; a person who should
    # cover two of three cannot be expressed and would need a join table. That limit is accepted
    # deliberately (owner, 2026-09-04) and is unreachable until a third gift exists.
    #
    # ⚠ IT IS NOT A FENCE, AND MUST NEVER BECOME ONE. The org fence is `_org_scoped`/`_org_allows`;
    # a reviewer bound to a gift who is somehow handed another gift's case still passes the fence,
    # because the fence is about the ORGANISATION. This decides who is OFFERED work.
    programme = models.ForeignKey(
        'scholarship.Programme', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='staff',
        help_text='Gift programme this person is scoped to. NULL = every gift the organisation '
                  'runs, which is the default and what every existing staff member has.',
    )
    is_super_admin = models.BooleanField(default=False)
    role = models.CharField(
        max_length=20, choices=ROLE_CHOICES, default='reviewer',
        help_text='super / admin / partner / reviewer. Backfilled from is_super_admin.',
    )
    is_active = models.BooleanField(default=True)
    # ⚠ READ THIS BEFORE REACHING FOR `is_active` TO MEAN "step back for a while".
    #
    # `is_active=False` is REVOKED — the account is gone. `get_admin` (courses/views_admin.py)
    # filters on it, so an inactive admin cannot even sign in; it also drops them from
    # notification sets, disarms the finance check and feeds the last-org-admin guard.
    #
    # `paused_at` is PAUSED — a volunteer taking a breather, and the whole point is that they
    # keep their account: they sign in, finish the interviews already theirs, and un-pause
    # themselves. It blocks ONE thing, NEW assignment (`services._can_review`), and deliberately
    # not `scheduling._can_review`, because a paused reviewer must still be able to propose times
    # for a case they are already holding.
    #
    # Two flags that nearly mean the same thing WILL be confused (lessons.md, IC lock 2026-07-29),
    # so the difference is named here rather than left to be inferred, and
    # `test_reviewer_pause.py` asserts pause ≠ revoke on each behaviour that separates them.
    # NULL = participating. Request #10, 2026-08-02.
    paused_at = models.DateTimeField(
        null=True, blank=True,
        help_text='When this reviewer stepped back. NULL = participating. Blocks NEW assignment '
                  'only — never sign-in, and never work already theirs. NOT a revoke: that is '
                  'is_active.',
    )
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # ⚠ UNTIL 2026-08-03 THIS SYSTEM COULD NOT SAY WHETHER AN INVITED PERSON EVER TURNED UP.
    # There was no last_login, no accepted_at, nothing — so somebody invited five minutes ago and a
    # colleague of a year both read "Active" on the staff table. These two fields answer the two
    # different questions that were being asked of one missing fact.
    #
    # ⚠ `supabase_user_id` IS NOT THE SIGNAL, and it looks like one. It is written at INVITE time
    # for a non-Google address (the account is provisioned then), and stays NULL for a Google or
    # already-registered invitee until `get_admin` backfills it. So it records how somebody was
    # provisioned, not whether they came. Do not reach for it again.
    #
    # NULL is "NOT RECORDED", never "never signed in" — both columns start empty for everybody who
    # was already here, and the backfill from Supabase is best-effort. Any screen must say so.
    first_seen_at = models.DateTimeField(
        null=True, blank=True,
        help_text='First time this person opened the console. Set once, never updated — it is what '
                  'closes their invitation. NULL means not recorded, not "never came".',
    )
    last_seen_at = models.DateTimeField(
        null=True, blank=True,
        help_text='Most recent console session, throttled to about once a day. Answers "are they '
                  'still with us?". NULL means not recorded.',
    )

    class Meta:
        db_table = 'partner_admins'

    @property
    def is_super(self):
        """True for a super admin via either the new role or the legacy flag."""
        return self.role == 'super' or self.is_super_admin

    @property
    def is_paused(self):
        """True when this person has stepped back from NEW work. Never means revoked."""
        return self.paused_at is not None

    def __str__(self):
        org_name = self.org.name if self.org else 'Super Admin'
        return f'{self.name} ({org_name})'
