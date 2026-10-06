# Retrospective — Platform Sprint 1: Organisation record + BrightPath as org #1 (2026-07-15)

First sprint of the multi-tenant platform roadmap (`docs/plans/2026-07-14-platform-roadmap-draft.md`,
Phase 1). Commit `a473a171`; live on revision `halatuju-api-00749-zzq`.

## What Was Built

- **`PartnerOrganisation` grew into the tenant Organisation record** (decision D-6): 19 additive
  columns — per-language programme names / persona names / team sign-offs (en/ms/ta), logo URL,
  brand colour, sender identities (from / reply-to / support), frontend URL, and four module flags
  (scholarship / sponsor pool / WhatsApp comms / payout — unenforced until platform Sprint 10).
  Existing referral rows are untouched (all defaults neutral). Migration `courses/0061`.
- **`ScholarshipCohort.owning_organisation`** — the source of truth for which tenant owns a
  programme (D-8), `on_delete=PROTECT`. Named per the build-for-tenancy conventions: never a plain
  `org`, because `PartnerAdmin.org` already means *referring* organisation. Migration
  `scholarship/0097`.
- **Seed migration `scholarship/0098`**: BrightPath created as organisation #1 with today's live
  branding/sender constants captured verbatim (so Sprints 5/6 can render byte-identically from
  config); every existing cohort backfilled. Idempotent; reverse detaches cohorts, keeps the org row.
- **Prod migrate-first runbook** `docs/plans/2026-07-15-sprint1-migrate-first.md` — hand-written
  Postgres DDL with pre-checks (right-table guards, already-applied guard) and post-checks, applied
  via the Supabase MCP before the push.
- Tests: `apps/scholarship/tests/test_platform_organisation.py` (+6) — seed values, idempotency,
  backfill-only-unowned, referral-role neutrality, PROTECT semantics.

Behaviourally invisible: nothing reads the new columns yet. Serializer exposure consciously
deferred to platform Sprint 10 (the only org endpoint today is an invite dropdown with no consumer
for tenant config).

## What Went Well

- **The migrate-first runbook worked first-try, end to end.** All 3 pre-checks passed, all 3 DDL
  steps committed cleanly, all 4 post-checks exact-matched. The pre-checks earned their place: the
  legacy-table guard (`partner_organisations` must already have `contact_person`) and the
  already-applied guard make the runbook safe to hand to a fresh session.
- **The deploy gate travelled in the commit message.** Build and deploy happened in different
  sessions; "DEPLOY GATE: apply <runbook> BEFORE this commit is pushed" in `a473a171`'s message plus
  the IN-PROGRESS note in CLAUDE.md made the handoff unambiguous — the deploying session knew
  exactly what to run and in what order, with zero re-derivation.
- **Smoke went beyond page-loads.** `/api/v1/scholarship/intake/` is public and queries
  `ScholarshipCohort` through the new ORM model — a 200 there proves live code ↔ migrated schema
  alignment, not just that the frontend serves. (Plus: web 200, public API 200, gated admin
  401-not-500, zero error logs since deploy.)
- **Backend-only commit → only the api Cloud Build trigger fired.** No wasted web build.

## What Went Wrong

Nothing material. The migration, build, and smoke all passed on the first attempt. (The runbook
discipline this sprint inherited — hand-written Postgres DDL, never `sqlmigrate` output; pre/post
checks; migrate-first — exists because earlier sprints DID get these wrong; the lesson bank already
carries those entries.)

## Design Decisions

- **Grow `PartnerOrganisation` rather than add a new `Organisation` model** (D-6, roadmap): one org
  table with two roles (referrer and tenant owner) kept visible in the schema by the FK naming rule.
- **`owning_organisation`, never `org`** (review §2.5): referrer ≠ owner must stay readable at the
  schema level.
- **Seed captures today's live constants verbatim** so per-org rendering (Sprints 5/6) can be
  verified byte-identical against current behaviour before any second tenant exists.
- **Defer serializer exposure to Sprint 10** — no consumer for tenant config yet; exposing early
  would be surface without a reader.

## Numbers

| Metric | Value |
|---|---|
| Migrations | 3 (courses/0061, scholarship/0097, scholarship/0098) — all additive, applied migrate-first |
| New columns | 19 on `partner_organisations` + 1 FK (+index) on `scholarship_cohorts` |
| Tests | +6 new; full suite **3664 pytest passed** (jest untouched at 501 — backend-only) |
| Deploys | 1 (Cloud Build `814c6827` SUCCESS → revision `halatuju-api-00749-zzq`, 100% traffic) |
| Smoke | web 200 · public API 200 · gated 401 · intake-via-new-model 200 · 0 error logs |
| Complexity (roadmap estimate vs actual) | Low — accurate |
