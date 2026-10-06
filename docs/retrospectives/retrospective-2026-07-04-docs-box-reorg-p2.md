# Retrospective — Officer Documents box reorganisation, Phase 2 (2026-07-04)

Plan: `.claude/plans/draw-up-the-roadmap-majestic-raccoon.md` (officer Documents box reorg + version
history, 3 phases). This is **Phase 2 — document version history** (backend; migration `0093`,
additive; the read-site audit is the load-bearing risk). P1 (frontend re-grouping) shipped earlier
today; P3 (enforce-in-logic, re-banding-gated) is still to come.

## What Was Built

A re-upload no longer HARD-deletes the replaced document. `ApplicantDocument` gains `superseded_at`
(null = live) + a self-FK `superseded_by`; the upload replace path now stamps the old row and points
it at the replacement **and keeps its Storage blob**, so there is a durable audit trail of what was
replaced. The officer cockpit shows the retained copies under a muted **OLD / REPLACED** list; the
student's own documents listing shows only the live copy. An explicit student "Remove" is the one
path that still truly deletes — it hard-deletes the live row plus its whole superseded ancestor chain
and sweeps every blob.

**The load-bearing risk was the read-site audit**: any verdict / gate / completeness read that forgot
to exclude superseded rows would let a replaced document silently count. A full audit
(`Explore` agent) mapped every `.documents.` / `ApplicantDocument.objects` read across the app; each
verdict/gate/completeness/student-facing read now filters `superseded_at__isnull=True`, while the
write/upload/sweep paths, the ops outage monitor, the reprocess commands, and the admin serializer
(which shows history) are deliberately left unfiltered.

## What Went Well

- **Choke points first.** The three verdict_engine funnels (`_latest_doc`,
  `_latest_doc_for_member`, `_present_doc_types`) plus income_engine `_cluster_docs`/`_member_ic_doc`
  and the utility `_latest_doc` cover the large majority of reads — patched at source.
- **A static guard test** scans the pure read-only engine modules (verdict/income/anomaly/pathway/
  profile/submission_review/check2) and fails loudly if any future `.documents.` read omits the
  `superseded_at` filter — so the class of bug can't silently regrow (mirrors the repo's
  no-icu-messageformat / subject-drift guards).
- **No filtering default manager.** The default manager stays unfiltered so the admin serializer
  keeps returning superseded rows for the history list; a single `ApplicantDocument.live(qs)` helper
  documents the intent. Documented so it isn't "simplified" back into a filtering manager.

## What Went Wrong / Watch

- **The supersede chain is multi-generation.** A slot replaced twice is A←B←C; one level of
  `.supersedes.all()` misses A. The student-delete walk is transitive (BFS up `superseded_by`) and a
  guard test pins it.
- **Blob growth.** Retained blobs accumulate — `cleanup_orphan_blobs` MUST keep seeing superseded
  rows (else it would treat their live blobs as orphans and delete them); left unfiltered on purpose.
- **Five document tests encoded the old hard-delete contract** (assert old row gone, blob swept) —
  updated to the soft-supersede contract (row retained + superseded, blob NOT swept). Expected, not a
  regression.

## Numbers

- 2074 scholarship pytest (+ the new `test_superseded_documents.py` guard suite + one API
  student-GET-exclusion test; 5 replace tests updated to the new contract). 433 jest (+1 grouping
  test). Golden masters intact. tsc clean on the touched source files (officerCockpit.ts / admin-api.ts
  / page.tsx). i18n en/ms/ta parity held (+1 key/locale: `group.superseded`, Tamil first-draft).
- Migration `0093` — additive (`superseded_at` + `superseded_by_id` FK), applied migrate-first via
  Supabase MCP.

## Next

Phase 3 (enforce shared-IC + STR-overrides-route verdict — the #63 class) — **re-banding-gated**:
mandatory V5-style re-banding audit + owner sign-off before it ships, because it changes live income
verdicts.

## Carry (owner)

- **Copy review** still due: the P1 sub-section headings + this P2 `group.superseded` (Tamil
  first-drafts), on top of the V4–V6 Tamil strings.
- **Slot uniqueness (TD-115):** a future `UniqueConstraint(application, doc_type, household_member[,
  request_code])` must be **partial** (`WHERE superseded_at IS NULL`) — retained history rows share the
  slot key. Not added here.
