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
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from . import staff_permissions

#: Source sign-in S1 (2026-10-30): the role of a referral SOURCE's own login. See `PartnerAdmin.source`.
SOURCE_ROLE = 'source_partner'


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
    #   source_partner — a referral SOURCE's own login (source sign-in S1, 2026-10-30; roadmap
    #              docs/plans/2026-10-30-source-sign-in-roadmap.md). NOT STAFF: it holds no
    #              permission (`staff_permissions.resolve` → ()), and `PartnerAdminMixin.get_admin`
    #              answers None for it on every view that has not opted in — DENY BY DEFAULT. Bound
    #              to one `source` and to that source's organisation (see `source` below).
    # ('viewer' retired 2026-06-09 → folded into 'admin'; 0 viewers existed on prod.)
    ROLE_CHOICES = [
        ('super', 'Super admin'),
        ('admin', 'Admin'),
        ('org_admin', 'Organisation admin'),
        ('partner', 'Partner'),
        ('reviewer', 'Reviewer'),
        ('qc', 'Quality control'),
        ('finance', 'Finance admin'),
        ('source_partner', 'Source partner'),   # a literal: the web's drift test parses this list
    ]
    SOURCE_ROLE = SOURCE_ROLE
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
    # ⚠ THE SOURCE A `source_partner` SIGNS IN FOR, AND NO OTHER ROW CARRIES ONE (source sign-in S1,
    # 2026-10-30). A `scholarship.ReferralSource`, NEVER `org` above: `org` is the platform REFERRAL
    # partner, a different thing (roadmap conflict C2). "role `source_partner` ⇔ source set, and
    # never a super" is a DATABASE check (Meta), so an `.update()` cannot break it either; `save`
    # adds the half a check cannot see — `owning_organisation` IS the source's organisation, which
    # is the fence every reader cuts on. PROTECT: a source with a login is switched off
    # (`ReferralSource.is_active`), never deleted. A string reference: no `courses → scholarship`
    # import. NOT access control on its own — `apps/scholarship/source_access.py` decides what it sees.
    source = models.ForeignKey(
        'scholarship.ReferralSource', on_delete=models.PROTECT,
        null=True, blank=True, related_name='users', db_column='source_id',
        help_text='The referral source a source_partner signs in for. NULL for every other role.',
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
    # ⚠ NULL MEANS "THE PRESET OF `role`", AND THERE IS NO BACKFILL (request #39, 2026-10-19).
    # Every person alive today and every future invitee holds their role's preset without anyone
    # writing a value — the invite, re-invite and factory doors never touch this column. A saved
    # edit (Sprint 4) stores the FULL explicit list, and a list equal to the preset is stored as
    # NULL, so "custom" is just `permissions IS NOT NULL`. NEVER READ THIS FIELD DIRECTLY: go
    # through `permission_set` / `has_perm`, which resolve NULL, the lead tier, a super and a
    # partner, and read a hand-written list fail-closed (`apps/courses/staff_permissions.py`).
    permissions = models.JSONField(
        null=True, blank=True,
        help_text='Staff permission keys (staff_permissions.CATALOGUE). NULL = the preset of role, '
                  'which is the default. Read through has_perm, never directly.',
    )

    class Meta:
        db_table = 'partner_admins'
        constraints = [
            # Source sign-in S1: every row alive on 2026-10-30 has `source` NULL and another role,
            # so this holds for production as it stands and is added with the column (courses 0089).
            models.CheckConstraint(
                condition=(Q(role=SOURCE_ROLE, source__isnull=False, is_super_admin=False)
                           | (~Q(role=SOURCE_ROLE) & Q(source__isnull=True))),
                name='partner_admin_source_iff_source_partner'),
        ]

    #: The columns a change to which can break the source binding; a `save(update_fields=…)` that
    #: names none of them (a sign-in stamp, a name edit) is not re-checked.
    _SOURCE_BINDING_FIELDS = frozenset({'role', 'source', 'source_id', 'owning_organisation',
                                        'owning_organisation_id', 'is_super_admin'})

    @property
    def is_source_user(self):
        """True for a referral source's own login (source sign-in S1). Never staff."""
        return self.role == SOURCE_ROLE

    def source_binding_problem(self):
        """Why this row breaks the source binding, or None. Reads the source only for a source user."""
        if self.is_source_user != (self.source_id is not None):
            return 'A source user needs its source, and no other account may have one.'
        if not self.is_source_user:
            return None
        if self.is_super_admin:
            return 'A source user is never a super admin.'
        if self.owning_organisation_id != self.source.organisation_id:
            return "A source user belongs to its source's organisation."
        return None

    def clean(self):
        super().clean()
        problem = self.source_binding_problem()
        if problem:
            raise ValidationError(problem)

    def save(self, *args, **kwargs):
        fields = kwargs.get('update_fields')
        if fields is None or self._SOURCE_BINDING_FIELDS & set(fields):
            problem = self.source_binding_problem()
            if problem:
                raise ValidationError(problem)
        super().save(*args, **kwargs)

    @property
    def is_super(self):
        """True for a super admin via either the new role or the legacy flag."""
        return self.role == 'super' or self.is_super_admin

    @property
    def is_paused(self):
        """True when this person has stepped back from NEW work. Never means revoked."""
        return self.paused_at is not None

    @property
    def permission_set(self):
        """The permission keys this person holds, a tuple in catalogue order (request #39)."""
        return staff_permissions.resolve(self)

    def has_perm(self, key):
        """Whether this person holds staff permission ``key``. A super passes every key; an
        unknown key raises. The payment gates read it since Sprint 2 and the student-file, QC,
        assignment and Spending gates since Sprint 3 (the golden table in
        `apps/courses/tests/test_permission_presets.py` proves the presets reproduce today)."""
        return staff_permissions.holds(self, key)

    def __str__(self):
        org_name = self.org.name if self.org else 'Super Admin'
        return f'{self.name} ({org_name})'
