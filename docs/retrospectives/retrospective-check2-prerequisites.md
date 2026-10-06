# Retrospective — Check 2, Sprint 1: prerequisites (P1–P3)

**Date:** 2026-06-07
**Branch:** `feature/check-2` (not yet merged/deployed — deploy strategy is an open decision, see below)
**Commits:** `0c7a375` (P1) · `40668a2` (P2) · `b6b8089` (P3), on top of `62879b2` (design doc) + `4c75f7f` (WIP helper).
**Gates at close:** **785 scholarship + 1037 courses/reports pytest · 274 jest · next build clean · i18n parity 2097.**
Migration `0043` (data‑only backfill, no schema change).

The first sprint of the Check‑2 roadmap. Check 2 turns a submitted application into a sponsor‑ready
profile (plus queries) without asserting anything unverified — but the design review (`check2-design.md`
§3) found the submission review couldn't yet "use all the information": the letter of intent was never
read, the sibling split was ignored, and utility/income consistency wasn't checked. This sprint closes
those three gaps so the STEP‑1 facts ledger (Sprint 2) has clean inputs.

## What Was Built

1. **P1 — read the letter of intent (`statement_of_intent`).** It was uploaded and never OCR'd (no
   `student_verdict`, no text). Wired the standalone `vision.read_text_document` helper into the upload
   handler (`TEXT_READ_DOC_TYPES`) and the admin re‑run‑vision action, so its plain text lands in
   `vision_fields['text']` for the submission review to read. Soft, never blocks.
2. **P2 — sibling school/tertiary split is authoritative.** `_sibling_tertiary_count` reads the split
   first (legacy 0 → tertiary 0; positive legacy with no split → `None` = a future clarify‑query). The
   first‑to‑university anomaly now **auto‑resolves** when tertiary == 0 — siblings only in *school* no
   longer falsely contradict the claim — and flags only on a genuine tertiary sibling or an
   unresolvable legacy count. Migration `0043` backfills the unambiguous legacy‑0 case. Both counts now
   render in the officer cockpit (admin serializer `Meta.fields` + FE type + page + en/ms/ta).
3. **P3 — utility‑spend‑high‑vs‑income flag.** `_detect_utility_high_vs_income` fires when utility bills
   exceed ~20% of declared monthly income, carrying the real numbers for the reviewer. (EPF balances and
   utility bands already surfaced in the cockpit via the income‑cluster data points and bill facts — so
   "surface the values" was largely already true; the new piece was the missing consistency check.)

## What Went Well

- **Continuous multi‑prerequisite flow.** P1→P2→P3 ran without a stop‑and‑restart between each; each
  prerequisite was self‑contained (helper + wiring + test) and committed independently, so the branch
  stayed green throughout and the gates only had to run once at the end.
- **The "extraction = doc‑type‑set membership" lesson paid off immediately.** P1 was a two‑line wiring
  job precisely because the prior sprint had established that a doc's schema existing ≠ the pipeline runs
  it — the fix was adding `statement_of_intent` to a set, not writing new extraction code.
- **The cockpit‑serializer lesson held.** P2's counts showed up first try because the fields went into
  `AdminApplicationDetailSerializer.Meta.fields` (not just the student serializer) from the start.
- **Reused existing seams.** P3's flag slotted into the anomaly engine's documented recipe (write
  `_detect_*`, register, two i18n keys, one test) with zero new surface.

## What Went Wrong / Watch‑outs

1. **"Surface utility/EPF values" was partly already done — scope had to be trimmed mid‑P3.**
   *Symptom:* the design listed "surface utility per‑capita + EPF values" as work, but the cockpit
   already shows EPF balances (cluster data points) and utility bands (bill facts).
   *Fix:* re‑checked what existed before building, and narrowed P3 to the genuinely missing piece (the
   consistency flag). Lesson: a design written before reading the current cockpit can over‑state the
   gap — verify what's already surfaced before adding a "surface it" task.
2. **Shared `[Unreleased]` CHANGELOG cycle with a parallel agent.** Same hazard as the last two sprints
   — used explicit `git add <paths>` (never `-A`) and inserted the Check‑2 block as a distinct top entry
   under `### Added` to avoid colliding with the other workstream's edits.
3. **Migration `0043` not yet applied to prod.** It's a harmless data‑only backfill, but it must go
   migrate‑first via MCP when the branch deploys — folded into the open deploy‑strategy decision.

## Open decision (for the user)

**Deploy strategy for the Check‑2 branch:** deploy per sprint (test each increment on prod, costs build
minutes each time) **vs** batch all of Check 2 and deploy once at the end. These prerequisites are
backend‑only, soft, and non‑breaking, so batching is cheap and low‑risk; I've left the branch unmerged
and unpushed‑to‑main pending this call. (Migration `0043` rides along whenever we deploy.)

## Next (Check 2 roadmap)

- **Sprint 2 — STEP 1 AI submission review + facts ledger** (claims + verification status + gap/
  inconsistency list; firewall‑safe). Consumes P1's letter text, P2's split, P3's flag.
- Sprint 3 — STEP 2 queries (`ResolutionItem.kind` += `clarify`/`human`; AI‑vs‑human triage; capped
  student queries; reviewer suggested‑questions).
- Sprint 4 — 5‑day SLA clock.
- Sprint 5 — STEP 3+4 gated single profile + refine ⚠️ **cross‑agent** (sponsor generator seam — PAUSE
  and coordinate before building).
