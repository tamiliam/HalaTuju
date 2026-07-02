# Retrospective — Bind sponsor visibility to the QC-Accept transition — 2026-07-02

## What shipped
Sponsor visibility now switches on at **exactly one arrow in the state machine — QC Accept** (→
`recommended`). The reviewer's Accept only **prepares** the sponsor profile (generates `final_markdown`/
`anon_markdown` + the card blurb, unpublished); `pool.publish_profile_to_pool(app)` publishes it from
`AdminQcDecisionView`'s accept branch. Belt-and-suspenders: the pool read gate and `sponsorship.is_fundable`
now hard-require `status == 'recommended'`, so a stray publish can't leak a not-yet-cleared case.

State machine, with the single publish point marked:
```
Under review —[Reviewer Accept]→ Awaiting QC —[QC Accept ⇒ PUBLISH]→ Recommended —[Sponsor Support]→ Awarded
                                     └────────[QC Reopen]→ back to reviewer (stays hidden)
```

## Why this was the right framing
Three earlier attempts circled the problem (a Send-to-QC button; a status-based pool-hide) and the owner
correctly rejected them as "not a solution — we need a clear transition." The real defect was a **side-effect
wired to the wrong button**: publishing fired on the *reviewer's* verdict, which happens *before* QC — so a
student was visible to (and fundable by) sponsors while still awaiting QC. Reframing it as a state machine
made the fix obvious and small: move the publish to the QC-Accept arrow, and make the data model match the
states (unpublished until cleared) rather than papering over it in the read layer.

## What went well
- **The publish logic was already isolated** in the record-verdict finalise branch, so extracting it into an
  idempotent, PII-backstopped `pool.publish_profile_to_pool` and calling it from QC-Accept was a clean move,
  not a rewrite.
- **The legacy 12 need no data step.** They still carry `anon_markdown`/`anon_blurb`/share-consent (verified
  via MCP), so QC-Accept re-publishes each automatically — and organically, one per acceptance, so sponsors
  aren't hit with a bulk "new students" blast.
- **Only one existing test broke** (`test_rerecord_counts_correction_and_republishes`) — it correctly encoded
  the OLD timing (re-record republishes); updated to the new flow (re-record re-locks + counts the
  correction; the republish now happens when the corrected case passes QC again). Small, expected, meaningful.
- **No migration.** Two independent guards (publish-at-QC + status read-gate) so the invariant holds even if
  one path is bypassed.

## What to watch / carried
- `publish_profile_to_pool` calls `generate_anon_blurb` **only** as a fallback (when the blurb is missing);
  the reviewer's finalise normally builds it, so QC-Accept usually does zero Gemini work. The 12 already have
  blurbs → no calls.
- `pool.IN_PROGRAMME_OR_BEYOND` is now unused by the pool gate (kept as documentation of the funded states).
- Deploy is code-only; **no data backfill**. After deploy, Suresh QCs the 12 the normal way and accepted ones
  return to the pool automatically.

## Verification
1960 scholarship pytest (net; +5 new in `TestPublishBoundToQc`, 1 reopen test updated) green. No FE change
(the reviewer message "final profile generated" stays accurate; the pool is backend-gated). No migration.
