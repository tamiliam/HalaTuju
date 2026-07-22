# Small-Change Consolidation Log

Tracks one-off small-lane changes between full sprints. Every ~10 pending entries triggers a
Consolidation Review (see `Settings/_workflows/small-change-lane.md` Part B).

## Pending
- 2026-07-23 fix(cockpit): missing i18n string for verdict item `pathway_type_switch` (messages en/ms/ta) + new backend guard test_verdict_item_i18n.py covering the whole class
- 2026-07-22 fix(web): witness card moved into the right column + both right-column cards stage-gated (admin/scholarship/[id]/page.tsx, officerCockpit.ts, +11 tests)
- 2026-07-22 fix(web): hide cancelled payment runs behind a toggle (admin/payments/page.tsx, i18n x3) — chosen by the owner INSTEAD of deleting a cancelled run; `payments.cancel` has no delete counterpart by design
- 2026-07-15 fix(admin): platform panels show per-panel lists (administration/page.tsx, adminStaff.ts, AdminListView payload, i18n x3)
- 2026-07-15 fix(admin): administration staff-table world split (administration/page.tsx, lib/adminStaff.ts, i18n x3)

- 2026-07-01 fix(web): STR-not-current verdict copy rendered raw ICU `select` — replaced with flat per-status keys (`halatuju-web` messages en/ms/ta, `officerCockpit.verdictItemKey`, cockpit `[id]/page.tsx`, +test)
- 2026-07-01 feat/fix(web): STR Status (Lulus) chip + verdict detail leads with the finding (`officerCockpit` strStatusFactStatus, `docsDrawer.fact.status` en/ms/ta, cockpit `[id]/page.tsx` render order, +tests)
- 2026-07-01 STR-proof refinement — **MEANS-TEST logic** (payment guard + band matrix + date-only Current chip; MODEL_VERSION→1.2.1; `income_engine`/`verdict_engine`/`officerCockpit`/spec/en·ms·ta; revises over-B40→red). Cluster of STR-proof changes (S1/S2 + copy fix + this) → **candidate to promote to a consolidated STR-proof sprint retro** at the next review.
- 2026-07-01 feat(web): prescriptive Check-2 verdict copy — lean + action, never "can't tell"; "Unsure" reads as "asked the student" (Action-Centre query). Officer-only (verdict.item en·ms·ta + spec §4); Gopal/help_engine untouched (stays tolerant). Part of the STR-proof cluster above.

_(Not logged here as a small change: the **Check-2 case summary** LLM feature — `verdict_narrative.py` + `AdminVerdictSummaryView` + FE lead paragraph, DARK behind `VERDICT_CASE_SUMMARY_ENABLED`. It's a feature, tracked as STR-proof S4 (dark) in CHANGELOG + halatuju.md + CLAUDE.md Next-Sprint; retro to follow after the owner live-validates the voice and flips the flag.)_

## Reviews

### 2026-06-16 — Live-review round (9 small changes)
**Reflect.** The 9 changes touched three surfaces: the **AI profile generator** (5: distil-all-inputs,
interest-quiz, statement-of-intent, grades-grouping/ethnicity, prompt-versioning), **web i18n hygiene**
(3: TD-118, TD-120, cockpit copy tweaks), and **reviewer access** (2: hide assignee filter, set-password page).
Most were genuine fixes; the profile ones were additive improvements, not symptom-patching.

**Cohere — clusters promoted:**
- **Profile completeness & safety (5).** Not five fixes — one coherent body of work: "make the AI profile use ALL
  the data the student gave us (typed fields, quiz, statement-of-intent), summarised well, and without leaking PII or
  ethnicity." Recognised as a mini-feature; the prompt is now **versioned** so it can evolve safely. Captured in
  `decisions.md` (prompt versioning; grades-by-group; generalise-ethnicity).
- **i18n drift after redesigns (3).** Recurring class: cockpit redesigns leave orphaned `admin.scholarship` keys.
- **Reviewer onboarding (2).** Non-Google invitees couldn't onboard; the set-password page closes the systemic gap.

**Anticipate — guardrails (recurring fix → prevention):**
- i18n orphans → **guardrail test added** (`messages/__tests__/admin-scholarship-i18n.test.ts`, dynamic-aware) — the
  class can no longer silently regrow. ✅
- Stale AI drafts after a prompt change (the #18 trap) → **PROMPT_VERSION + version-aware backfill added** — staleness
  is now detectable by version, and re-running the backfill only refreshes stale drafts. ✅
- **Candidate (not built):** schedule the version-aware backfill (or trigger it on a `PROMPT_VERSION` bump) so drafts
  self-heal without a manual cron call. Logged for a future pass.

**Close out.** Pending cleared (counter reset). Guardrails landed in the same round. Folded into the 2026-06-16
sprint-close (retrospective `docs/retrospective-2026-06-16-livereview-round.md`).

### 2026-06-29 — Consolidation review (15 small changes)
Covers the 14 `## Pending` entries (2026-06-16 → 2026-06-29) plus one reviewer-FAQ-docs entry that had been
misfiled under this section.

**Reflect.** The 15 changes touched five areas:
- **Document extraction & income computation (5)** — SPM 2-column slip under-read; handwritten salary-voucher
  `ringgit|sen` mis-read; salary-route earner Optional/undeclared (#90); `document_unreadable_blockers` list-vs-app
  bug; IC/parent_ic silent-OCR self-heal. All genuine fixes — but all the *same shape*: a document reads wrong and a
  B40 decision turns on the bad read.
- **Reviewer features (4)** — Guide + FAQ pages; language fluency (migration 0059); advance-notice email (migration
  0060); a follow-up FAQ-content update. These were **features with migrations**, not small changes.
- **Check-2 / Action-Centre student visibility (2)** — reviewer-raised requests now notify the student; system
  "couldn't read your doc" requests surfaced to the form-locked student.
- **Interview/status flow (2)** — fold the two interview-question buttons into one; advance `profile_complete →
  interviewing` when slots are proposed.
- **Copy + display casing (2)** — "Sponsor profile (draft)" → "Student profile (draft)"; ALL-CAPS offer programme
  name leaking to the sponsor pool (#107).

**Cohere — clusters promoted:**
- **Document-extraction & income robustness (5) → [TD-151].** The dominant cluster, and the one that keeps
  regenerating: five isolated point-fixes that are really one hardening pass (a scrubbed extraction-regression
  corpus + an income read-sanity gate + a generalised silent-OCR self-heal). Promoted to `technical-debt.md`
  TD-151 as a 1-sprint pass, not an N+1th point fix.
- **Reviewer features rode the small lane (4) → process drift.** Per `small-change-lane.md` step 1, a feature or a
  migration is a **sprint**, not a small change — these four (two with migrations) should have been one
  "reviewer-onboarding & comms" sprint. Shipped fine, but the boundary slipped four times; this is the recurring
  *process* class, addressed by the guardrail below.

**Anticipate — guardrail landed this round:**
- **`wat_lint` now flags a misclassified small-lane entry** — any `## Pending` line containing `feat:` or
  `migration` is reported as "should have been a SPRINT" (`small-change-lane.md` step 1). Converts the recurring
  feature-rode-the-lane drift from a thing-we-notice-in-hindsight into a mechanical catch at the next lint.
- **Display-value leak via a non-canonical write path** (the #107 casing leak) was already converted to prevention
  in the same hotfix (idempotent `title_case_programme` guard + a `docs/lessons.md` rule to grep every writer of a
  normalised field). No further action.

**Close out.** Pending cleared (counter reset). Guardrail (`wat_lint` misclassification check) and the casing guard
landed in-cycle; the extraction cluster is parked as TD-151 for a dedicated sprint.
