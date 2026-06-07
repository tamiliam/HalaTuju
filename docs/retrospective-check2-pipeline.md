# Retrospective — Check 2: submission review → queries → SLA → claim-gated profile (Sprints 2–5)

**Dates:** 2026-06-07 → 2026-06-08
**Branch:** `feature/check-2` (batch-deploy at the end — user's call; not yet merged/deployed)
**Commits:** `b4ffa7d` (S2) · `c020488` (S3) · `e03ed89` (S4) · `59caf82` (S5), after the Sprint-1
prerequisites (`0c7a375`/`40668a2`/`b6b8089`) and the design doc.
**Gates at close:** **826 scholarship + 1037 courses/reports pytest · 274 jest · next build clean ·
i18n parity 2105.** Scholarship migrations through **0045** (0043 backfill, 0044 query kinds, 0045 SLA).

Built continuously across one session (the user asked for sprint-to-sprint flow without explicit
close/start prompts), pausing only at the one genuine decision point (the Sprint-5 cross-agent seam),
which the user resolved with "build all of Sprint 5".

## What Was Built

- **STEP 1 — the deterministic facts ledger** (`submission_review.py`): the auditable core. Every
  assertable claim → its verification (verified / reported / student_words / unverified) from the
  verdict engine + structured fields + read docs; plus completeness gaps and consistency flags. No LLM.
- **STEP 2 — the clarify-query stream** (`check2_queries.py`, `ResolutionItem.kind`/`source` extended):
  AI-vs-human triage; only factual one-line non-sensitive gaps reach the student, capped at 3;
  reuses the Action Centre; idempotent; reviewer-only `human` kind hidden from students.
- **STEP 2/3 — the 5-day SLA clock** (`services.query_sla` / `is_ready_for_assignment` /
  `send_query_reminders`): ready = no open queries OR lapsed; a single well-timed reminder email;
  cockpit surfacing of the clock + the proceed-with-open-queries flag.
- **STEP 3 — claim-gated generation + tone guardrail** (`profile_engine.py`): both prompts assert only
  verified claims (first-to-university gated on the sibling split), no hardship-mining; a flag-gated
  auto-generation trigger fires once an application is ready.

## What Went Well

- **The deterministic-first spine paid off twice.** Building STEP 1 as a pure, no-LLM ledger meant
  STEP 2's queries (completeness gaps), STEP 3's claim-gating (verification map), and the cockpit
  surface all read from one tested source — and every layer was serializer-safe and unit-testable
  without mocking Gemini.
- **Reuse over reinvention.** Queries rode the existing `ResolutionItem` + Action Centre; the SLA
  reminder rode the existing email + cron pattern; the STEP-3 store path was extracted from the admin
  view and shared. Each sprint added little new surface.
- **The Sprint-1 lessons held all the way through.** Cockpit data always went into the *admin*
  serializer's `Meta.fields`; every new doc/kind switch was set-membership; migrate-check stayed clean.
- **The cross-agent seam was respected.** I stopped at Sprint 5, confirmed (via `git log`/`git diff`)
  that I'd never touched `pool.py`/`profile_engine.py`, surfaced the decision, and only proceeded on
  the user's explicit go — then staged the sponsor-territory file with explicit `git add`.

## What Went Wrong / Watch-outs

1. **A view refactor silently broke two patch-target tests.** Extracting `generate_ready_profile`
   and having the admin view call it moved the Gemini seam from `views_admin.generate_sponsor_profile`
   to `profile_engine.generate_sponsor_profile`; two admin tests patched the old path and failed.
   *Fix:* repointed the patches. *Lesson:* when you relocate a function call behind a shared helper,
   grep the tests for the **old** patch target before assuming green — `@patch` binds to an import
   site, not the function.
2. **Scope discipline under "build all of Sprint 5".** The literal roadmap said "retire the dual
   profile", but that is a destructive change to live (flag-off) sponsor-pool storage, entangled with
   a parallel agent, and the user's own Q4 defers the redaction wording to the award stage. I built
   the *substance* (claim-gating + tone on both generators — the actual bug fix) and deferred the
   structural storage merge, documenting why. *Lesson:* "build all" still means building the
   highest-value, non-destructive interpretation and naming what's deferred — not ramming a risky
   structural change because a one-liner said so.
3. **Cost-gating the AI trigger.** Auto-generation on a cron makes billable Gemini calls per ready
   app. Left it behind `CHECK2_AUTO_GENERATE` (default off), mirroring the codebase's other
   billable-AI flags, so the pipeline is wired but costs nothing until deliberately switched on.

## Deferred / Next

- **Dual-profile retirement** (one PII-redacted profile; merge `anon_markdown`/`draft_markdown`; final
  redaction wording) → award-stage alignment + sponsor-agent coordination (design §6/Q4, §10).
- **Cockpit facts-ledger panel** — the ledger is exposed on the serializer; a dedicated officer panel
  pairs naturally with the dual-profile work.
- **Deploy** — batch deploy the whole branch (migrate-first 0043→0045 via MCP); add the two new daily
  cron jobs (`query-reminders`, and `autogenerate-profiles` only if `CHECK2_AUTO_GENERATE` is enabled).
- **LLM consistency enrichment** of STEP 1 (subtler narrative-vs-data contradictions) — optional, the
  deterministic layer covers the rest.

## Numbers

- 4 commits (S2–S5) + 3 (S1) + design doc; backend-heavy, FE for the query surface.
- Tests added this arc: STEP-1 ledger (14), clarify queries (6 + 4 view), SLA + STEP-3 (9 + 4),
  claim-gating (5). Scholarship suite 778 → 826.
- Migrations 0043 (sibling backfill), 0044 (query kinds + constraint), 0045 (SLA clock).
