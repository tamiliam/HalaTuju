"""The Requests space payloads: what an ORGANISATION may see, and what only the OWNER may.

Moves only, split out of `serializers_admin.py` on 2026-10-29 because that file was already
sitting ON its 1,234-line allowance before this sprint touched it, and recording WHO accepted a
quote (TD-418) pushed it over. The 600-line standard asks for a split, not for prose to be trimmed
until the number passes (`docs/lessons.md`, TD-413).

⚠ **`OrgRequestOrgSerializer` IS AN ALLOWLIST, AND THAT IS THE POINT OF THIS FILE.** A field the
organisation must not see is a field we must not SEND — the AI draft, the owner's triage, the
engineer's hours, and who accepted a quote all stay on the owner payload. A guard in
`test_org_requests_endpoints.py` pins the org payload's exact key set, so adding a key here is a
deliberate act with a test to answer to. Keeping the two classes side by side in one small file is
what makes the asymmetry readable.

Re-exported from `serializers_admin` so every existing import keeps working.
"""
from rest_framework import serializers

from . import org_requests
from .models import OrgRequest, OrgRequestAnalysis


# ── Requests space (Sprint 15) ────────────────────────────────────────────────────

def _serialize_org_request_attachments(org_request):
    """The attachment list carried by BOTH request serializers (Sprint 15.1). Each entry is a
    minimal allowlist — {id, original_filename, content_type, size, created_at, download_url}. The
    ``download_url`` is a signed URL with the SAME org assertion as ``ApplicantDocumentSerializer``:
    a blob whose key-org disagrees with the request's org signs to None (belt-and-braces cross-org
    guard on top of the org-fenced endpoint reads)."""
    from .storage import create_signed_download_url, resolve_org_for_path
    org_id = getattr(org_request, 'organisation_id', None)
    out = []
    for att in org_request.attachments.all():
        path_org = resolve_org_for_path(att.storage_path)
        download_url = (None if (path_org is not None and org_id is not None and path_org != org_id)
                        else create_signed_download_url(att.storage_path))
        out.append({
            'id': att.id,
            'original_filename': att.original_filename,
            'content_type': att.content_type,
            'size': att.size,
            'created_at': att.created_at,
            'download_url': download_url,
        })
    return out


def _comment_dicts(req, *, viewer_is_org):
    """The discussion as this viewer may see it (TD-201).

    ⚠ The visibility filter is a ROW filter, and that is why it cannot live in the serializer's
    field list. An allowlist protects against a FIELD reaching the wrong audience; it does nothing
    about a row the audience may not read — a serializer naming `body` renders an internal comment
    just as happily as a shared one. So both serializers call this, and the org one passes
    ``viewer_is_org=True``.

    `author_name` is the person, resolved for display; the AI has none.
    """
    from . import org_requests
    out = []
    for c in org_requests.comments_for(req, viewer_is_org=viewer_is_org):
        out.append({
            'id': c.id,
            'author_kind': c.author_kind,
            'author_name': getattr(c.author_admin, 'name', '') or '',
            'body': c.body,
            'visibility': c.visibility,
            'awaiting_reply': c.awaiting_reply,
            'created_at': c.created_at,
        })
    return out


class OrgRequestOrgSerializer(serializers.Serializer):
    """The ORG-FACING view of an OrgRequest (what a submitting org_admin sees).

    **Allowlist by construction** — a plain ``Serializer`` with every field explicit and ZERO model
    passthrough, so nothing reaches the org that is not named here. An exact-key snapshot test pins
    the set, so a new field cannot slip in and a deliberate change has to be made twice.

    **The AI split (owner ruling, TD-202, 2026-07-30). The three ``ai_draft_*`` fields do NOT
    deserve the same answer:**

    * ``ai_draft_note`` + ``ai_draft_model`` — **SENT.** This is the reasoning that justifies the
      quote, and withholding it made a price look arbitrary. The owner found the gap by filing
      request #4 as an org_admin and seeing silence: the reviewer had in fact answered in 21
      seconds with an accurate reading of the bug, into a room the requester was not in.
    * ``ai_draft_hours`` — **WITHHELD**, and NOT for commercial reasons (the margin is already
      absent and ``quote_hours`` is sent when the owner quotes). The estimate is *demonstrably
      unreliable*: the model has no codebase context, so it quoted 24h for work that was largely
      already built and 8h for a change whose mailer already existed. Publishing an untrustworthy
      number as the justification for a price makes it the figure the real quote must argue against.
    * ``triaged_kind`` / ``lane`` / ``triage_note`` — **WITHHELD.** The owner's private judgement.
      They already have two channels that DO reach the org (the ``ask`` thread and the quote note)
      and used the quote note for exactly this on #3; opening the private note would cost the
      ability to be blunt and buy nothing.

    ⚠ **``ai_draft_note`` is free-form model prose, so it MAY state an hours figure even though
    ``ai_draft_hours`` is withheld.** Accepted knowingly: the owner sets the final quote regardless,
    so this is negotiation optics, not correctness. If it becomes a nuisance, the cheap fix is an
    instruction in the review prompt telling the reviewer not to state hours in its rationale —
    not a filter here.

    The org also sees: the QUOTE (hours + note — **the MARGIN is not sent**, owner 2026-07-30), the
    schedule/approval stamps, and the clarification thread.

    Input is an ``OrgRequest``.
    """
    id = serializers.IntegerField()
    kind = serializers.CharField()
    title = serializers.CharField()
    description = serializers.CharField()
    # Optional Bugzilla-style scoping (Sprint 15 increment) — org-SUBMITTED, so org-visible.
    component = serializers.CharField()
    urgency = serializers.CharField()
    steps_to_reproduce = serializers.CharField()
    status = serializers.CharField()
    # TD-201: the discussion, filtered to SHARED. `clarifications` is retired — nothing reads it
    # after 2026-07-31 (the column survives one sprint so the migrated copy can be verified against
    # the original on production; its drop is logged as its own follow-up).
    comments = serializers.SerializerMethodField()
    # The reviewer's REASONING and which model produced it — sent, per TD-202. `ai_draft_hours`
    # stays absent: see the class docstring for why the three fields split three ways.
    ai_draft_note = serializers.CharField()
    ai_draft_model = serializers.CharField()
    ai_draft_at = serializers.DateTimeField()
    quote_hours = serializers.SerializerMethodField()
    # `analyses` is DELIBERATELY ABSENT (TD-204, owner 2026-07-31). The engineer's analysis reaches
    # this organisation as PROSE, through `comments` — that is the reasoning, and TD-202 settled
    # that reasoning is shared. What stays behind is the CITED FILES (internal shape of a
    # multi-tenant platform, and unopenable by the requester anyway) and the ENGINEER'S HOURS (a
    # second figure in front of them recreates exactly what removing the AI's estimate fixed).
    # Read OrgRequestAnalysis's docstring before adding a counterpart here; the omission is a
    # decision, not an oversight.
    # quote_margin_pct is DELIBERATELY ABSENT (owner, 2026-07-30): "do not mention the margin".
    # Removed from the PAYLOAD, not merely hidden in the UI — a field the org must not see is a
    # field we must not send, which is the whole point of this allowlist. `quote_hours` is the
    # figure they accept and the only one anything bills on; nothing multiplies by the margin.
    # It remains on OrgRequestOwnerSerializer for the quote form.
    quote_note = serializers.CharField()
    quoted_at = serializers.DateTimeField()
    approved_at = serializers.DateTimeField()
    # ⚠ WHO accepted is OWNER-ONLY, and the allowlist test is why that is a decision rather
    # than a default. `approved_by_name` can be a SUPER's name when the platform accepted on
    # the organisation's behalf, and this payload must not disclose platform staff to a
    # tenant. The ORG already knows it accepted; the owner is the one who needs the
    # provenance, because a feature cannot be billed without an acceptance (TD-418).
    scheduled_for = serializers.DateField()
    decline_reason = serializers.CharField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    submitted_by_name = serializers.SerializerMethodField()
    # Screenshot attachments (Sprint 15.1) — org-SUBMITTED evidence, so org-visible. Adds ONE key
    # to the exact-key snapshot (19 → 20); still no ai_* / triage key.
    attachments = serializers.SerializerMethodField()

    def get_comments(self, obj):
        # viewer_is_org=True — the ROW filter. An internal comment must never appear here.
        return _comment_dicts(obj, viewer_is_org=True)

    def get_quote_hours(self, obj):
        return str(obj.quote_hours) if obj.quote_hours is not None else None

    def get_submitted_by_name(self, obj):
        return (getattr(obj.submitted_by, 'name', '') or '').strip()

    def get_attachments(self, obj):
        return _serialize_org_request_attachments(obj)


class OrgRequestOwnerSerializer(serializers.Serializer):
    """The OWNER-FACING view (super) — every field incl. the AI draft + triage, plus the org
    id/name. Deliberately a SEPARATE serializer from the org one (never a shared serializer with a
    role-conditional field): the two payloads share no code, so a change to the owner view can't
    accidentally widen the org view. Input is an ``OrgRequest``."""
    id = serializers.IntegerField()
    organisation_id = serializers.IntegerField()
    organisation_name = serializers.SerializerMethodField()
    submitted_by_name = serializers.SerializerMethodField()
    kind = serializers.CharField()
    title = serializers.CharField()
    description = serializers.CharField()
    component = serializers.CharField()
    urgency = serializers.CharField()
    steps_to_reproduce = serializers.CharField()
    status = serializers.CharField()
    comments = serializers.SerializerMethodField()   # TD-201: the FULL thread, internal included
    analyses = serializers.SerializerMethodField()   # TD-204: OWNER-ONLY — files + hours live here
    ai_run_count = serializers.IntegerField()
    ai_draft_kind = serializers.CharField()
    ai_draft_lane = serializers.CharField()
    ai_draft_hours = serializers.SerializerMethodField()
    ai_draft_note = serializers.CharField()
    ai_draft_model = serializers.CharField()
    ai_draft_at = serializers.DateTimeField()
    triaged_kind = serializers.CharField()
    lane = serializers.CharField()
    triage_note = serializers.CharField()
    triaged_at = serializers.DateTimeField()
    quote_hours = serializers.SerializerMethodField()
    quote_margin_pct = serializers.IntegerField()
    quote_note = serializers.CharField()
    quoted_at = serializers.DateTimeField()
    approved_at = serializers.DateTimeField()
    # WHO accepted the quote, and in which capacity (TD-418). Shown to BOTH sides on purpose: a
    # feature cannot be billed without an acceptance, so this is the provenance of a charge, and
    # an organisation is entitled to see that its own acceptance is recorded against a name. The
    # NAME, never the admin's primary key. Empty for every row accepted before 2026-10-29 —
    # honestly unknown rather than back-filled with a guess.
    approved_by_name = serializers.SerializerMethodField()
    approved_by_role = serializers.CharField()
    scheduled_for = serializers.DateField()
    decline_reason = serializers.CharField()
    declined_by_role = serializers.CharField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    attachments = serializers.SerializerMethodField()

    def get_attachments(self, obj):
        return _serialize_org_request_attachments(obj)

    def get_organisation_name(self, obj):
        return (getattr(obj.organisation, 'name', '') or '').strip()

    def get_submitted_by_name(self, obj):
        return (getattr(obj.submitted_by, 'name', '') or '').strip()

    def get_approved_by_name(self, obj):
        return (getattr(obj.approved_by, 'name', '') or '').strip()

    def get_ai_draft_hours(self, obj):
        return str(obj.ai_draft_hours) if obj.ai_draft_hours is not None else None

    def get_comments(self, obj):
        # The owner sees the whole thread, internal notes included.
        return _comment_dicts(obj, viewer_is_org=False)

    def get_analyses(self, obj):
        """The engineer's working papers (TD-204) — OWNER-ONLY, newest first.

        ⚠ This is the ONE place `cited_files` and `estimated_hours` are serialised anywhere. The
        org-facing serializer deliberately has no counterpart: see OrgRequestAnalysis's docstring
        for why neither is secrecy (a citation the requester cannot open buys them nothing, and a
        second hours figure recreates the problem TD-202 removed from the AI). If you are adding a
        matching field to the org payload, read that docstring first — the omission is a decision.
        """
        from . import org_requests
        current = org_requests.approved_analysis(obj)
        out = []
        loaded = org_requests.prefetched_rows(obj, 'analyses')   # the LIST prefetches (TD-291)
        for a in (sorted(loaded, key=lambda x: -x.id) if loaded is not None else
                  obj.analyses.all().select_related('approved_by').order_by('-id')):
            out.append({
                'id': a.id,
                'body': a.body,
                'estimated_hours': str(a.estimated_hours) if a.estimated_hours is not None else None,
                'cited_files': list(a.cited_files or []),
                'authored_by': a.authored_by,
                'repo_sha': a.repo_sha,
                # The engineer's PROPOSED triage — prefills the owner's form, applies nothing.
                # OWNER-ONLY like everything else here: what the organisation is told is the prose,
                # and "we think this one is chargeable" is not a conclusion to hand them before the
                # owner has ruled on it.
                'proposed_kind': a.proposed_kind,
                'proposed_lane': a.proposed_lane,
                'created_at': a.created_at,
                'approved_at': a.approved_at,
                'approved_by_name': (getattr(a.approved_by, 'name', '') or '').strip(),
                'superseded_at': a.superseded_at,
                # The one the quote gate reads — so the screen and the gate cannot disagree about
                # which analysis is standing.
                'is_current': bool(current and a.id == current.id),
            })
        return out

    def get_quote_hours(self, obj):
        return str(obj.quote_hours) if obj.quote_hours is not None else None
