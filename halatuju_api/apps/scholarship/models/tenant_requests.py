"""
A tenant organisation's request, its thread, its attachments and its analysis.

Moved here VERBATIM from `apps/scholarship/models.py` at code health H15 (2026-09-20).
Moves only: no field, no `Meta`, no `db_table`, no `related_name` was touched, so the
database is untouched too — `makemigrations --check` reports no changes. See `__init__.py`.
"""
from django.db import models

# ── Requests component tree (Sprint 15.1) — the SINGLE source of truth ─────────────────
# A request's COMPONENT is the admin surface it is about. Parents are the org_admin-reachable
# surfaces (super-only Students + Course Data were REMOVED in 15.1); the only parent with
# sub-components is ``applications`` (the B40 pipeline stages). A sub-component's stored value is
# ``f'{parent}_{suffix}'`` (UNDERSCORE separator — a dot breaks the nested i18n lookup); every value
# is ≤30 chars (the column is varchar(30) with NO DB CHECK, so the app-level clamp
# ``org_requests.VALID_COMPONENTS`` — derived from this tree — MUST carry every value).
# ``org_requests.VALID_COMPONENTS`` and the model ``COMPONENT_CHOICES`` both derive from this map;
# the FE mirror + the i18n keys are pinned to it by ``test_org_requests`` so the three can never
# drift (never hand-enumerate — lessons.md).
REQUEST_COMPONENT_TREE = {
    'applications': (
        'student_details', 'documents', 'ai_prediction', 'queries', 'interview',
        'decision', 'agreement', 'student_profile',
    ),
    'sponsors': (),
    'payments': (),
    'contracts': (),
    'sources': (),
    'administration': (),
    'access': (),
    'other': (),
}

# English labels (human text — the VALUES derive from the tree, the labels are looked up here).
_REQUEST_COMPONENT_LABELS = {
    # ⚠ MATCHES THE MENU ROW, which stopped naming one programme on 2026-09-08 — this list
    # names the same console page, so the two must move together.
    'applications': 'Applications',
    'applications_student_details': 'Student details',
    'applications_documents': 'Documents',
    'applications_ai_prediction': 'AI Prediction & verdicts',
    'applications_queries': 'Queries & blockers',
    'applications_interview': 'Interview',
    'applications_decision': 'Recommendation & QC',
    'applications_agreement': 'Bursary agreement',
    'applications_student_profile': 'Student profile (sponsor-facing)',
    'sponsors': 'Sponsors',
    'payments': 'Payments',
    'contracts': 'Contracts',
    'sources': 'Sources',
    'administration': 'Administration',
    'access': 'Sign-in & access',
    'other': 'Other',
}


def flatten_component_tree(tree):
    """Ordered (value, ...) for the tree: each parent, followed by its ``parent_sub`` children."""
    out = []
    for parent, subs in tree.items():
        out.append(parent)
        out.extend(f'{parent}_{sub}' for sub in subs)
    return tuple(out)


class OrgRequest(models.Model):
    """An organisation's bug report / feature request, managed through the Requests space
    (Sprint 15). Named ``OrgRequest`` (not ``Request``) to stay grep-unambiguous against the
    HTTP request; the service module is ``org_requests.py`` (not ``requests.py``, which collides
    with the live HTTP library import).

    Flow: an org_admin submits → the AI reviewer (``org_requests.run_ai_review``, via the
    ``contracts._gemini_generate`` seam) classifies bug/feature, estimates work in HOURS, and may
    ask the requestee clarifying questions (which flow to the submitter DIRECTLY — no owner gate);
    the owner triages (authoritative, may reclassify per the adjudication rule) and sends an
    owner-gated quote in hours. The requestee accepts / rejects / defers / modifies.

    The AI DRAFT (``ai_draft_*`` + ``triage_note``) is NEVER in the org-facing serializer — only
    the owner sees it. The org sees the QUOTE the owner sends, not the AI's estimate.

    Adjudication rule (published verbatim, owner 2026-07-24): behaviour contradicting the role
    matrix / manual = bug (free); working-as-documented-but-wanted-different = feature (priced).
    Quotes are hours-only in v1 (no money — no hourly rate exists yet).
    """
    KIND_CHOICES = [('bug', 'Bug report'), ('feature', 'Feature request')]
    LANE_CHOICES = [('small_change', 'Small change'), ('sprint', 'Sprint')]
    # Bugzilla-style optional scoping fields (Sprint 15 increment, owner 2026-07-24). COMPONENT is
    # the admin surface the request is about — the user-facing MODULE names the admin nav uses
    # (halatuju-web/src/app/admin/layout.tsx + the Administration hub). URGENCY is the ORG's own
    # signal (the owner still adjudicates). All three are OPTIONAL ('' allowed).
    # Derived from REQUEST_COMPONENT_TREE (single source of truth, Sprint 15.1). Students +
    # Course Data removed (super-only surfaces); the 8 ``applications_*`` sub-components added.
    COMPONENT_CHOICES = [
        (value, _REQUEST_COMPONENT_LABELS.get(value, value))
        for value in flatten_component_tree(REQUEST_COMPONENT_TREE)
    ]
    URGENCY_CHOICES = [
        ('blocking', 'Blocking'),
        ('important', 'Important'),
        ('nice_to_have', 'Nice to have'),
    ]
    STATUS_CHOICES = [
        ('submitted', 'Submitted'),
        ('triaged', 'Triaged'),
        ('quoted', 'Quoted'),
        ('approved', 'Approved'),
        ('deferred', 'Deferred'),
        ('scheduled', 'Scheduled'),
        ('done', 'Done'),
        ('declined', 'Declined'),
    ]

    organisation = models.ForeignKey(
        'courses.PartnerOrganisation', on_delete=models.PROTECT, related_name='org_requests',
    )
    submitted_by = models.ForeignKey(
        'courses.PartnerAdmin', on_delete=models.PROTECT, related_name='submitted_org_requests',
    )
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='submitted')

    # Optional scoping (Sprint 15 increment) — org-submitted, org-visible.
    component = models.CharField(max_length=30, choices=COMPONENT_CHOICES, blank=True, default='')
    urgency = models.CharField(max_length=20, choices=URGENCY_CHOICES, blank=True, default='')
    steps_to_reproduce = models.TextField(blank=True, default='')

    # Clarification thread (AI ↔ requestee — flows FREE, no owner gate; owner CC'd by email).
    # Each entry: {question, asked_at, answer|null, answered_at|null}. modify() appends an old
    # description here as history too.
    clarifications = models.JSONField(default=list, blank=True)
    ai_run_count = models.PositiveSmallIntegerField(default=0)   # auto-run cap = 3

    # AI draft — NEVER in the org-facing payload (owner-only). The hours estimate stays here
    # until the owner sends a quote.
    ai_draft_kind = models.CharField(max_length=10, blank=True, default='')
    ai_draft_lane = models.CharField(max_length=20, blank=True, default='')
    ai_draft_hours = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    ai_draft_note = models.TextField(blank=True, default='')
    ai_draft_model = models.CharField(max_length=50, blank=True, default='')
    ai_draft_at = models.DateTimeField(null=True, blank=True)

    # Owner triage (authoritative — may reclassify kind per the adjudication rule).
    triaged_kind = models.CharField(max_length=10, blank=True, default='')
    lane = models.CharField(max_length=20, blank=True, default='')
    triage_note = models.TextField(blank=True, default='')
    triaged_at = models.DateTimeField(null=True, blank=True)

    # Owner quote (hours only, v1).
    quote_hours = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    quote_margin_pct = models.PositiveSmallIntegerField(null=True, blank=True)
    quote_note = models.TextField(blank=True, default='')
    quoted_at = models.DateTimeField(null=True, blank=True)

    approved_at = models.DateTimeField(null=True, blank=True)
    scheduled_for = models.DateField(null=True, blank=True)
    decline_reason = models.TextField(blank=True, default='')
    # Who ended it at 'declined': 'super' (decline) or 'org_admin' (withdraw) — audit.
    declined_by_role = models.CharField(max_length=20, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'org_requests'
        ordering = ('-created_at',)

    def __str__(self):
        return f'OrgRequest #{self.pk} [{self.status}] {self.title[:40]}'


class OrgRequestAttachment(models.Model):
    """A screenshot attached to an OrgRequest (Sprint 15.1, closes TD-172). Images ONLY, ≤5 per
    request. Mirrors ``ApplicantDocument``'s metadata shape — only the storage path + metadata live
    here; the file bytes go browser→Supabase via a signed URL and never pass through Django.

    Org-fenced by construction: the storage key is ``requests/<org_id>/<request_id>/<uuid>`` (via
    ``storage.build_request_attachment_key``); the signed download URL is refused when the key's org
    disagrees with the request's org (``storage.resolve_org_for_path``), and every endpoint reaches
    an attachment only through the org-fenced request lookup (a cross-org request id is 404).
    """
    org_request = models.ForeignKey(
        OrgRequest, on_delete=models.CASCADE, related_name='attachments',
    )
    storage_path = models.CharField(max_length=500)
    original_filename = models.CharField(max_length=255, blank=True, default='')
    content_type = models.CharField(max_length=100, blank=True, default='')
    size = models.IntegerField(default=0)
    uploaded_by = models.ForeignKey(
        'courses.PartnerAdmin', on_delete=models.PROTECT, related_name='org_request_attachments',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'org_request_attachments'
        ordering = ['id']

    def __str__(self):
        return f'OrgRequestAttachment #{self.pk} for OrgRequest #{self.org_request_id}'


class OrgRequestComment(models.Model):
    """One entry in an OrgRequest's DISCUSSION (TD-201, owner 2026-07-31).

    Replaces ``OrgRequest.clarifications`` — a ``JSONField`` list of ``{question, answer}`` PAIRS,
    which could carry a question and its single reply and nothing else. The owner's model is
    Bugzilla: *"open discussion/debate, even after it has been assigned to someone"*. A pairs list
    cannot express a statement, a second voice, or a remark that expects no reply, and the module's
    one verb reaching the requester was ``ask`` — so a conclusion ("here is what we would build, and
    why") had to travel as a quote note or not at all.

    **A question is a comment awaiting a reply** (``awaiting_reply``), which is what makes this ONE
    stream rather than a comment table sitting beside a question table.

    ⚠ **``visibility`` is the load-bearing column and it INHERITS TD-202's ruling** — do not
    re-decide it per feature. ``shared`` reaches the requesting organisation; ``internal`` never
    does. The rule settled on 2026-07-30 is *shared reasoning, private judgement*: the reviewer's
    rationale goes out, the owner's private assessment does not, because the owner has to stay free
    to write bluntly. Retrofitting "who may read this" onto a table that assumed everyone sees
    everything is the expensive version of this change, which is why the column exists from the
    first migration rather than being added when it is first needed.

    ⚠ **The window is WIDER than ``OPEN_FOR_SHAPING``** (owner, 2026-07-31). Answering and attaching
    close when the quote is accepted, because both change what was priced. A comment does not, and
    Bugzilla-style discussion explicitly continues after assignment — so commenting stays open until
    the request is terminal (``done``/``declined``). Two windows, deliberately, each with its reason.

    ``author_kind`` exists because the reviewer has no ``PartnerAdmin`` row; ``author_admin`` is
    SET_NULL so removing a person never deletes the history they wrote.
    """
    AUTHOR_CHOICES = [
        ('ai', 'AI reviewer'),
        ('owner', 'Platform owner'),
        ('org', 'Requesting organisation'),
        # The engineer's analysis, posted by OrgRequestAnalysis.approve (TD-204). Distinct from
        # 'owner' because the two carry different authority: the owner decides, the engineer read
        # the code. Never written from a request body — the comment endpoint derives author_kind
        # from the caller's role, so an org_admin cannot forge one.
        ('engineer', 'Engineer'),
    ]
    VISIBILITY_CHOICES = [
        ('shared', 'Shared with the organisation'),
        ('internal', 'Platform-internal only'),
    ]

    org_request = models.ForeignKey(
        OrgRequest, on_delete=models.CASCADE, related_name='comments',
    )
    author_kind = models.CharField(max_length=10, choices=AUTHOR_CHOICES)
    # Null for the AI, and for a human whose admin record is later removed.
    author_admin = models.ForeignKey(
        'courses.PartnerAdmin', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='org_request_comments',
    )
    body = models.TextField()
    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default='shared')
    # A question is a comment awaiting a reply; a statement is not. Cleared when replied to.
    awaiting_reply = models.BooleanField(default=False)
    replied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'org_request_comments'
        ordering = ['id']            # flat stream, oldest first — the order it was said in
        indexes = [
            models.Index(fields=['org_request', 'id']),
        ]

    def __str__(self):
        return f'OrgRequestComment #{self.pk} on OrgRequest #{self.org_request_id}'


class OrgRequestAnalysis(models.Model):
    """The ENGINEER'S WORKING PAPER behind one comment (TD-204, owner ruling 2026-07-31).

    Owner: *"Gemini's role is only initial analysis. It has no access to the codebase and cannot
    reliably do much. You have to do the proper analysis and estimate the workload, and I want you
    to post as well, with my approval."*

    ⚠ **THIS IS NOT A SECOND THREAD.** The prose still travels as an ``OrgRequestComment``
    (``posted_comment``), so the discussion stays ONE stream and TD-201 is intact. This row holds
    the EVIDENCE and the APPROVAL LIFECYCLE that a comment cannot carry.

    ⚠ **Why not columns on OrgRequestComment**, since the next tidying pass will want to merge them:
      * a DRAFT would have to sit at ``visibility='internal'`` and be flipped to ``'shared'`` on
        approval — re-deciding the one column TD-202 settled and this file forbids re-deciding per
        feature, and it would be the first mutation of ``visibility`` anywhere in the codebase;
      * comments are append-only (``ordering = ['id']``, "the order it was said in") with no
        ``updated_at``, and a draft must be revisable;
      * ``_comment_dicts`` is shared by BOTH serializers, so ``cited_files`` would sit one line of
        code from the org payload with only a snapshot test in between.

    ⚠ **``cited_files`` AND ``estimated_hours`` ARE OWNER-ONLY, and no org-facing serializer names
    this table.** Neither is secrecy:
      * the requester cannot open ``referrals.py``, so a citation buys them nothing, while the owner
        can, so it buys him everything — and the paths disclose the internal shape of a MULTI-TENANT
        platform to one tenant, a surface that grows silently with every analysis;
      * a second hours figure in front of the requester rebuilds exactly the problem TD-202 removed
        when the AI stopped pricing — the owner must stay free to quote 6h on a 4h analysis
        (bundling, goodwill, margin) without visibly contradicting his own engineer.
    Do not "finish the job" by exposing either. The prose IS shared, and that is the whole of what
    the requester needs: the reasoning, so a price never looks arbitrary.

    ⚠ **``cited_files`` is the point of the record.** The standing rule in CLAUDE.md is that the
    estimate must cite its files — 3.5h on request #3 named the mailer and the hook and was
    checkable in a minute; 24h on the sponsor invite named nothing and was wrong by a factor of six.
    An approved analysis with an empty list cannot satisfy the quote gate, by construction.
    """

    org_request = models.ForeignKey(
        OrgRequest, on_delete=models.CASCADE, related_name='analyses',
    )
    # The prose. Shared with the organisation verbatim when approved — write it for them.
    body = models.TextField()
    # OWNER-ONLY. See the class docstring before exposing this anywhere.
    estimated_hours = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    # OWNER-ONLY. Repo-relative paths, validated to EXIST at record time by the command that
    # writes them — an unchecked citation is decoration, not evidence.
    cited_files = models.JSONField(default=list, blank=True)
    # Who did the reading (e.g. 'claude-opus-5'). Rendered in the cockpit in the same change that
    # added it — this project has five stored-but-never-surfaced fields already.
    authored_by = models.CharField(max_length=50, blank=True, default='')
    # The commit the analysis was read against. An estimate citing files at a SHA three weeks old
    # has silently rotted, and this is the only thing that can say so.
    repo_sha = models.CharField(max_length=40, blank=True, default='')
    # sha256 of the request description at record time — the audit trail behind supersession.
    description_sha = models.CharField(max_length=64, blank=True, default='')

    # ── The engineer's PROPOSED triage (2026-08-01) ───────────────────────────────────────────
    # A RECOMMENDATION, never an application. It prefills the owner's triage form and nothing else;
    # the request's own `triaged_kind` / `lane` change only when the owner presses Run, exactly as
    # before. That split is the point — these two values decide whether the organisation is
    # CHARGED (a bug is free, a feature is priced), so the last hand on them must be human.
    #
    # ⚠ THIS IS THE THIRD OPINION ON ONE SCREEN. Gemini's `ai_draft_kind`/`ai_draft_lane` already
    # prefill that form. The engineer's proposal WINS where present — it is the one that read the
    # codebase — and the form says whose reading it took. An unattributed default is how the form
    # came to sit on 'feature'/'sprint' for every bug, one press away from charging for free work.
    #
    # Blank means "no opinion", which is not the same as agreeing with the AI. Kept as plain
    # CharFields mirroring `OrgRequest.triaged_kind`/`lane` (same widths, same vocabulary) so the
    # two cannot drift into different spellings of 'feature'.
    proposed_kind = models.CharField(max_length=10, blank=True, default='')
    proposed_lane = models.CharField(max_length=20, blank=True, default='')

    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        'courses.PartnerAdmin', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='approved_org_request_analyses',
    )
    # The comment approval posted. SET_NULL so deleting a comment never deletes the working paper.
    posted_comment = models.ForeignKey(
        OrgRequestComment, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    # Stamped when the requester MODIFIES the request — the description this was written against no
    # longer exists, so the analysis can no longer satisfy the quote gate. NOT derived by comparing
    # timestamps: `updated_at` is auto_now and our own sweeps bump it (a trap this project has
    # already been bitten by once, on partner "last activity").
    superseded_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'org_request_analyses'
        ordering = ['id']
        indexes = [
            models.Index(fields=['org_request', 'id']),
        ]
        verbose_name_plural = 'org request analyses'

    def __str__(self):
        return f'OrgRequestAnalysis #{self.pk} on OrgRequest #{self.org_request_id}'

    @property
    def is_approved(self):
        return self.approved_at is not None

    @property
    def is_superseded(self):
        return self.superseded_at is not None
