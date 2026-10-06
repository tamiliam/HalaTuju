# Retrospective — Verification-Model Roadmap Sprint V3 (Query Lifecycle & Check-3 Handoff)

**Date:** 2026-07-03
**Branch/worktree:** `feat/verify-v3` in `.worktrees/verify-model` (off main incl. V1+V2)
**Roadmap:** `docs/plans/2026-07-03-verification-model-roadmap.md` (V3 of V1–V6)
**Findings source:** `docs/plans/2026-07-03-check-model-audit.md` (#6–#9 + owner decisions 3 & 4)
**Migration:** NONE.
**Tests:** 2046 scholarship pytest (+6 net) + 413 jest; tsc clean.
**Owner checkpoint:** this sprint closes the V1–V3 block. Two design forks were taken to the owner
mid-sprint (below) rather than guessed.

## What Was Built

Check 2 stops asking the unanswerable and stops losing the asked; Check 3 inherits the full picture.

- **#6 — no query or email fires after the answering window locks.** `sync_check2_queries` and
  `sync_resolution_items` now gate every CREATE / RE-OPEN on `not services.querying_locked(app)`
  (auto-resolve housekeeping still runs); `QUERY_SLA_ACTIVE_STATUSES` drops `interviewed` so no
  notify/reminder email invites an answer the resolve endpoint refuses. **Owner decision:** existing
  doc requests stay answerable post-lock (an upload still resolves them) — only new queries close;
  a locked app still SHOWS pre-existing items, it just creates none.
- **#7 — the clarify cap is fair.** `MAX_CLARIFY` now counts only CONCURRENTLY-OPEN clarifies
  (a waived/resolved one frees a slot), so a few soft queries can no longer permanently crowd out a
  higher-priority income-story question. `reporting_date_unknown` is carved OUT of the cap (a
  sponsor-profile input of equal standing). A new `clarify_overflow_count` surfaces a cockpit note
  ("N more queries waiting") so a capped-out gap stays visible.
- **#8 — per-item SLA.** `query_sla` now runs each open query on its OWN clock
  (`ResolutionItem.created_at + SLA`), so a query raised on day 6 is no longer born already-lapsed
  ("notified but reminder-less"); the reminder fires ~2 days before each query's own deadline.
  **Owner decision:** `is_ready_for_assignment` keeps a submit-window FLOOR (submit + SLA),
  decoupled from a late query's clock, so a late query can't push the review start back forever.
- **#9 — the interview inherits everything.** New `interview_agenda_full` folds, alongside the
  anomaly flags: OPEN carried-over queries (ask verbally), the four "confirm at interview" verdict
  ambers (`income_unverified_needs_interview`, `income_above_b40_line`, `academic_grade_uncertain`,
  `ic_service_down` — over-the-line phrased interviewer-only, owner decision 4), and a STANDING
  **Motivation & grit** section (always present, seeded rich when the statement of intent is thin —
  motivation stays human, owner decision 3). Surfaced on the detail serializer + folded into the
  cockpit agenda; reviewer **Guide + FAQ updated** in the same change.

## What Went Well

- **Taking the two forks to the owner mid-sprint was the right call.** The SLA floor (per-item vs
  submit-window) and the "does a locked app still show review items" question were genuine product
  decisions, not implementation details — guessing either would have shipped the wrong behaviour to
  a live student system. Both answers ("submit+5 floor"; "show pre-existing, create none") then
  drove clean, confident implementations + test reconciliations.
- **V3 rode V1/V2's groundwork.** #6's member-tagged requests and #9's open-query folding both lean
  on V1.3's `params`; the whole arc composes.
- **The shared `_gap_sets` extraction** made `clarify_overflow_count` a clean read (no duplicated
  gap logic) — the #7 cockpit note came almost for free.

## What Went Wrong

1. **Four tests broke on intended behaviour changes, and two of them encoded a real design fork,
   not a fixture typo.** The clarify-cap test assumed reporting_date was capped (it's now carved
   out); the SLA tests assumed a submit-anchored lapse (it's now per-item); the funded-set-aside
   tests jumped straight to a locked status and expected sync to CREATE items (#6 now only shows
   pre-existing).
   - *Root cause:* the tests pinned the OLD lifecycle semantics; distinguishing "just update the
     fixture" from "this needs an owner decision" required reading each one's intent, not just its
     assertion.
   - *Fix:* the fixture-only ones (reporting-date carve-out) were updated in place; the two design
     ones drove the owner questions, and the fixtures were then rebuilt to match the funnel
     (create items while non-locked, then flip status; back-date a query's `created_at` for a
     per-item lapse). **System note:** when a lifecycle change breaks a test, classify it first —
     an intended-semantics change that a stakeholder owns is a decision to surface, not a fixture to
     silently rewrite. (Mid-sprint WIP was committed "DO NOT MERGE" while the forks were open, so
     nothing shipped half-decided.)

## Design Decisions

Logged in `docs/decisions.md` (V3 block): the post-lock rule (create none, show pre-existing,
uploads stay answerable); the per-item SLA with a decoupled submit-window assignment floor; the
clarify cap counting concurrently-open with a reporting-date carve-out; and the Check-3 agenda
folding (open queries + needs-interview ambers interviewer-only + standing Motivation section).

## Numbers

- 4 findings closed (#6, #7, #8, #9); 0 migrations; ~11 files (backend 5, FE 4, i18n 3, Guide/FAQ 2).
- +6 net scholarship tests (lock-gate ×2, cap-counts-open, overflow, per-item SLA regression,
  agenda-full) + fixture reconciliations. 2046 pytest + 413 jest.
- **New/changed reviewer-facing copy for owner review** — see the sprint report (agenda ambers +
  Motivation + overflow note, en/ms/ta; Tamil is first-draft).
